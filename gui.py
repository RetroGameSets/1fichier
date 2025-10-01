"""Interface graphique Tkinter pour le téléchargeur 1fichier.

Ce module encapsule la logique GUI autour des fonctions asynchrones définies
dans `main.py` (récupération de nom de fichier, téléchargement, gestion de la
file, attente entre téléchargements, pause/reprise, etc.).

Principes clefs:
 - Thread principal: uniquement pour Tkinter.
 - Thread worker: lance un event loop asyncio (asyncio.run) pour exécuter les
     opérations réseau (httpx) et les coroutines de téléchargement.
 - Communication UI <-> worker via:
         * Queue LOG_QUEUE (texte log + progression) + polling .after()
         * Callbacks `progress_cb` / `wait_cb` renvoyant dans le thread principal
             via root.after.
 - Pause: asyncio.Event (set = actif, clear = en pause) consultée dans le
     code core.download_file pour geler les boucles (attente + flux).
 - Compte à rebours attente: mis à jour par wait_cb. Si après reprise aucun
     nouveau callback ne survient (cas edge), un fallback local décrémente le
     compteur côté GUI.
"""

import asyncio
import threading
import queue
import os
import io
import json
import base64
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import main as core  # le fichier main.py existant
import re

# ---------------- Traductions (FR / EN) ----------------
TEXT = {
    'fr': {
        'title': "1Fichier Download Manager par RetroGameSets",
        'output_dir': "Dossier de sortie:",
        'browse': "Parcourir",
        'urls_box': "URLs (une par ligne)",
        'api_key_label': "Clé API Premium:",
        'api_key_placeholder': "Optionnel: votre clé API 1fichier pour téléchargements premium",
        'api_key_save': "Sauvegarder",
        'api_key_clear': "Effacer",
        'api_key_saved': "Clé API sauvegardée",
        'api_key_cleared': "Clé API effacée",
        'api_key_load_error': "Erreur chargement clé API:",
        'add': "Ajouter",
        'start': "Démarrer",
        'pause': "Pause",
        'resume': "Reprendre",
        'stop': "Stop",
        'files': "Fichiers",
        'logs': "Logs",
        'speed': "Vitesse",
        'eta': "Temps restant",
        'info_add_disabled': "Ajout désactivé pendant un téléchargement en cours.",
        'warn_no_url': "Aucune URL à ajouter.",
        'err_create_dir': "Impossible de créer le dossier:",
        'info_downloading_exists': "Téléchargement déjà en cours.",
        'prefetch_start': "🔍 Pré-récupération des noms...",
        'prefetch_error': "[Préfetch noms] Erreur:",
        'prefetch_summary_header': "— Récapitulatif —",
        'prefetch_unknown_name': "(nom inconnu)",
        'stop_info': "L'arrêt prendra effet à la fin du fichier courant.",
        'status_waiting': "En attente",
        'status_running': "En cours",
        'status_paused': "En pause",
        'status_done': "Terminé",
        'status_error': "Erreur",
        'status_cancelled': "Annulé",
        'wait_prefix': "Attente ",
        'time_hms': "{h}h{m:02d}m{s:02d}s",
        'time_ms': "{m}m{s:02d}s",
        'time_s': "{s}s",
        'lang_toggle': "Français / English",
        'lang_label': "Langue:" ,
    },
    'en': {
        'title': "1Fichier Download Manager by RetroGameSets",
        'output_dir': "Output folder:",
        'browse': "Browse",
        'urls_box': "URLs (one per line)",
        'api_key_label': "Premium API Key:",
        'api_key_placeholder': "Optional: your 1fichier API key for premium downloads",
        'api_key_save': "Save",
        'api_key_clear': "Clear",
        'api_key_saved': "API key saved",
        'api_key_cleared': "API key cleared",
        'api_key_load_error': "API key loading error:",
        'add': "Add",
        'start': "Start",
        'pause': "Pause",
        'resume': "Resume",
        'stop': "Stop",
        'files': "Files",
        'logs': "Logs",
        'speed': "Speed",
        'eta': "ETA",
        'info_add_disabled': "Add disabled while a download is running.",
        'warn_no_url': "No URL to add.",
        'err_create_dir': "Cannot create directory:",
        'info_downloading_exists': "Download already running.",
        'prefetch_start': "🔍 Prefetching names...",
        'prefetch_error': "[Prefetch names] Error:",
        'prefetch_summary_header': "— Summary —",
        'prefetch_unknown_name': "(unknown name)",
        'stop_info': "Stop will occur after current file finishes.",
        'status_waiting': "Waiting",
        'status_running': "Running",
        'status_paused': "Paused",
        'status_done': "Done",
        'status_error': "Error",
        'status_cancelled': "Cancelled",
        'wait_prefix': "Waiting ",
        'time_hms': "{h}h{m:02d}m{s:02d}s",
        'time_ms': "{m}m{s:02d}s",
        'time_s': "{s}s",
        'lang_toggle': "Français / English",
        'lang_label': "Language:",
    }
}

LOG_QUEUE = queue.Queue()

class QueueWriter(io.TextIOBase):
    def write(self, s):  # type: ignore[override]
        if s:
            LOG_QUEUE.put(s)
        return len(s)
    def flush(self):  # type: ignore[override]
        return

class DownloaderGUI:
    def __init__(self, root: tk.Tk):
        """Initialise la fenêtre et l'état interne.

        Paramètres
        ----------
        root : tk.Tk
            Instance racine Tkinter fournie par l'appelant.
        """
        self.lang = 'fr'
        self.root = root
        root.title(TEXT[self.lang]['title'])
        root.geometry("900x600")
        # État interne (initialiser avant les widgets car certains callbacks les consultent)
        self._original_stdout = None
        self.worker_thread = None
        self.stop_requested = False
        self.urls_in_progress = {}
        self.queued_order = []
        self.pause_event = None
        self.downloading = False
        self.current_url = None
        self.wait_remaining = {}
        self.wait_countdown_threads = set()
        
        # Configuration file path
        self.config_file = os.path.join(os.path.expanduser("~"), ".1fichier_config.json")
        
        # Widgets (peut appeler _update_total_progress_label qui dépend maintenant des attributs ci‑dessus)
        self._build_widgets()
        
        # Charger la clé API sauvegardée
        self._load_api_key()
        # Lancement polling logs
        self.root.after(150, self._poll_log_queue)
        # Prépare motifs de traduction logs FR->EN
        self._log_translate_patterns = [
            (re.compile(r'^🔗 Traitement de (.+)$'), '🔗 Processing \\1'),
            (re.compile(r'^📄 Nom: (.+)$'), '📄 Name: \\1'),
            (re.compile(r'^📄 Nom détecté: (.+) ← (.+)$'), '📄 Name detected: \\1 ← \\2'),
            (re.compile(r"^📄 Nom introuvable \(pour l'instant\) ← (.+)$"), '📄 Name not found (yet) ← \\1'),
            (re.compile(r'^⏳ Attente (.+)$'), '⏳ Waiting \\1'),
            (re.compile(r'^✅ Terminé → (.+)$'), '✅ Done → \\1'),
            (re.compile(r'^✅ Terminé → (.+) \(sans attente\)$'), '✅ Done → \\1 (no wait)'),
            (re.compile(r'^🔑 Tentative téléchargement premium via API \(ID: (.+)\)$'), '🔑 Attempting premium download via API (ID: \\1)'),
            (re.compile(r'^📄 Nom via API: (.+)$'), '📄 Name via API: \\1'),
            (re.compile(r'^⬇️ Téléchargement premium → (.+)$'), '⬇️ Premium downloading → \\1'),
            (re.compile(r'^✅ Téléchargement premium terminé → (.+)$'), '✅ Premium download completed → \\1'),
            (re.compile(r'^⚠️ Échec téléchargement premium, passage en mode gratuit\.\.\.$'), '⚠️ Premium download failed, switching to free mode...'),
            (re.compile(r'^⚠️ Erreur API premium: (.+), passage en mode gratuit\.\.\.$'), '⚠️ Premium API error: \\1, switching to free mode...'),
            (re.compile(r'^❌ Page reçue indique indisponibilité / conditions\. \(Fichier supprimé ou limites atteintes\.\)$'), '❌ Page indicates unavailability / conditions (File removed or limits reached).'),
            (re.compile(r'^⚠️ Captcha détecté\. Résolution manuelle requise.*$'), '⚠️ Captcha detected. Manual resolution required (open in browser, solve, then reuse cookie/token).'),
            (re.compile(r'^⚠️ Captcha détecté après soumission\. Abandon\.$'), '⚠️ Captcha detected after submission. Aborting.'),
            (re.compile(r'^⚠️ Captcha détecté après attente\. Abandon\.$'), '⚠️ Captcha detected after wait. Aborting.'),
            (re.compile(r'^📝 Soumission du formulaire de téléchargement…$'), '📝 Submitting download form…'),
            (re.compile(r'^❌ Échec soumission formulaire \(tentative (\d+)\): (.+)$'), r'❌ Form submission failed (attempt \\1): \\2'),
            (re.compile(r"^❌ Impossible de trouver le lien direct \(peut-être Captcha ou changement de page\)\. Active --debug pour plus d'info\.$"), '❌ Unable to find direct link (maybe Captcha or page changed). Enable --debug for more info.'),
            (re.compile(r'^❌ Page HTML reçue au lieu du fichier .*Aucune sauvegarde\.$'), '❌ HTML page received instead of file (probably unavailable / removed / conditions). No save.'),
            (re.compile(r'^▶️ Reprise à ([0-9.]+) MB$'), '▶️ Resuming at \\1 MB'),
            (re.compile(r'^ℹ️ Reprise impossible, redémarrage complet\.$'), 'ℹ️ Resume not possible, restarting from beginning.'),
            (re.compile(r'^⬇️ Téléchargement → (.+)$'), '⬇️ Downloading → \\1'),
            (re.compile(r'^— Récapitulatif —$'), '— Summary —'),
            (re.compile(r'^\(nom inconnu\)$'), '(unknown name)'),
        ]

    def _build_widgets(self):
        """Construit tous les widgets de l'interface (layout principal)."""
        # Barre supérieure
        frm_top = ttk.Frame(self.root)
        frm_top.pack(fill=tk.X, padx=8, pady=5)
        self.lbl_outdir = ttk.Label(frm_top, text=TEXT[self.lang]['output_dir'])
        self.lbl_outdir.pack(side=tk.LEFT)
        self.outdir_var = tk.StringVar(value=os.path.abspath("downloads"))
        self.outdir_entry = ttk.Entry(frm_top, textvariable=self.outdir_var, width=60)
        self.outdir_entry.pack(side=tk.LEFT, padx=5)
        self.btn_browse = ttk.Button(frm_top, text=TEXT[self.lang]['browse'], command=self.browse_outdir)
        self.btn_browse.pack(side=tk.LEFT)
        # Sélecteur langue (coin droit)
        lang_frame = ttk.Frame(frm_top)
        lang_frame.pack(side=tk.RIGHT, padx=4)
        self.lang_var = tk.StringVar(value='Français' if self.lang == 'fr' else 'English')
        self.lang_select = ttk.Combobox(lang_frame, state='readonly', width=10,
                                        values=['Français', 'English'], textvariable=self.lang_var)
        self.lang_select.pack(side=tk.RIGHT)
        self.lang_select.bind('<<ComboboxSelected>>', self.on_language_change)

        # Clé API Premium avec boutons de sauvegarde
        frm_api = ttk.Frame(self.root)
        frm_api.pack(fill=tk.X, padx=8, pady=2)
        self.lbl_api_key = ttk.Label(frm_api, text=TEXT[self.lang]['api_key_label'])
        self.lbl_api_key.pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value="")
        self.api_key_entry = ttk.Entry(frm_api, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Boutons de gestion de la clé API
        self.api_save_btn = ttk.Button(frm_api, text=TEXT[self.lang]['api_key_save'], command=self._save_api_key)
        self.api_save_btn.pack(side=tk.LEFT, padx=2)
        self.api_clear_btn = ttk.Button(frm_api, text=TEXT[self.lang]['api_key_clear'], command=self._clear_api_key)
        self.api_clear_btn.pack(side=tk.LEFT, padx=2)
        
        # Tooltip/placeholder pour la clé API
        self.api_key_entry.bind("<FocusIn>", self._on_api_key_focus_in)
        self.api_key_entry.bind("<FocusOut>", self._on_api_key_focus_out)
        self._api_key_placeholder_active = False
        self._set_api_key_placeholder()

        # Zone URLs
        self.frm_urls = ttk.LabelFrame(self.root, text=TEXT[self.lang]['urls_box'])
        self.frm_urls.pack(fill=tk.BOTH, expand=False, padx=8, pady=5)
        self.urls_text = tk.Text(self.frm_urls, height=6)
        self.urls_text.pack(fill=tk.BOTH, expand=True)

        # Actions & progression globale
        frm_actions = ttk.Frame(self.root)
        frm_actions.pack(fill=tk.X, padx=8, pady=5)
        self.add_btn = ttk.Button(frm_actions, text=TEXT[self.lang]['add'], command=self.add_to_queue)
        self.add_btn.pack(side=tk.LEFT)
        self.start_btn = ttk.Button(frm_actions, text=TEXT[self.lang]['start'], command=self.start_downloads)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn = ttk.Button(frm_actions, text=TEXT[self.lang]['pause'], command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(frm_actions, text=TEXT[self.lang]['stop'], command=self.request_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.global_progress = ttk.Progressbar(frm_actions, length=300)
        self.global_progress.pack(side=tk.LEFT, padx=15)
        self.total_progress_label_var = tk.StringVar(value='')
        self.total_progress_label = ttk.Label(frm_actions, textvariable=self.total_progress_label_var)
        self.total_progress_label.pack(side=tk.LEFT)

        # Tableau fichiers
        self.frm_table = ttk.LabelFrame(self.root, text=TEXT[self.lang]['files'])
        self.frm_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        columns = ("display", "status", "progress", "speed", "eta", "url")
        self.tree = ttk.Treeview(self.frm_table, columns=columns, show="headings")
        headers = [
            "Nom" if self.lang=='fr' else 'Name',
            "Statut" if self.lang=='fr' else 'Status',
            "Progression" if self.lang=='fr' else 'Progress',
            "Vitesse" if self.lang=='fr' else 'Speed',
            "Temps restant" if self.lang=='fr' else 'ETA',
            "URL"
        ]
        for col, txt in zip(columns, headers):
            self.tree.heading(col, text=txt)
            if col == "display":
                base_w = 200
            elif col == "url":
                base_w = 200
            elif col in ("speed", "eta"):
                base_w = 100
            else:
                base_w = 120
            self.tree.column(col, anchor=tk.W, stretch=True, width=base_w)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Menu contextuel pour le tableau
        self.tree_context_menu = tk.Menu(self.root, tearoff=0)
        self._setup_tree_context_menu()
        self.tree.bind("<Button-3>", self._show_tree_context_menu)

        # Logs avec ascenseur
        self.frm_log = ttk.LabelFrame(self.root, text=TEXT[self.lang]['logs'])
        self.frm_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)
        
        # Frame pour le Text et la Scrollbar
        log_frame = ttk.Frame(self.frm_log)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=10, wrap="word")
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(state=tk.DISABLED)
        
        # Menu contextuel pour les logs
        self.log_context_menu = tk.Menu(self.root, tearoff=0)
        self._setup_log_context_menu()
        self.log_text.bind("<Button-3>", self._show_log_context_menu)
        
        # Init libellé progression globale
        self._update_total_progress_label()

    def _set_api_key_placeholder(self):
        """Affiche le placeholder dans le champ API key s'il est vide."""
        if not self.api_key_var.get():
            self._api_key_placeholder_active = True
            self.api_key_entry.config(show="")
            self.api_key_entry.config(foreground="gray")
            self.api_key_var.set(TEXT[self.lang]['api_key_placeholder'])

    def _clear_api_key_placeholder(self):
        """Supprime le placeholder du champ API key."""
        if self._api_key_placeholder_active:
            self._api_key_placeholder_active = False
            self.api_key_entry.config(show="*")
            self.api_key_entry.config(foreground="black")
            self.api_key_var.set("")

    def _on_api_key_focus_in(self, event):
        """Événement quand le champ API key prend le focus."""
        self._clear_api_key_placeholder()

    def _on_api_key_focus_out(self, event):
        """Événement quand le champ API key perd le focus."""
        if not self.api_key_var.get():
            self._set_api_key_placeholder()

    def get_api_key(self) -> str | None:
        """Retourne la clé API saisie ou None si placeholder/vide."""
        if self._api_key_placeholder_active:
            return None
        key = self.api_key_var.get().strip()
        return key if key else None

    def _setup_log_context_menu(self):
        """Configure le menu contextuel pour les logs."""
        # Supprimer tous les éléments existants
        self.log_context_menu.delete(0, tk.END)
        
        # Ajouter les options selon la langue
        if self.lang == 'fr':
            self.log_context_menu.add_command(label="Copier tout", command=self._copy_all_logs)
            self.log_context_menu.add_command(label="Copier sélection", command=self._copy_selected_logs)
            self.log_context_menu.add_separator()
            self.log_context_menu.add_command(label="Effacer logs", command=self._clear_logs)
        else:
            self.log_context_menu.add_command(label="Copy all", command=self._copy_all_logs)
            self.log_context_menu.add_command(label="Copy selection", command=self._copy_selected_logs)
            self.log_context_menu.add_separator()
            self.log_context_menu.add_command(label="Clear logs", command=self._clear_logs)

    def _show_log_context_menu(self, event):
        """Affiche le menu contextuel des logs."""
        try:
            self.log_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_context_menu.grab_release()

    def _copy_all_logs(self):
        """Copie tout le contenu des logs dans le presse-papiers."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_text.get("1.0", tk.END))

    def _copy_selected_logs(self):
        """Copie la sélection des logs dans le presse-papiers."""
        try:
            selected_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            # Aucune sélection
            pass

    def _clear_logs(self):
        """Efface tous les logs."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _setup_tree_context_menu(self):
        """Configure le menu contextuel pour le tableau des fichiers."""
        # Supprimer tous les éléments existants
        self.tree_context_menu.delete(0, tk.END)
        
        # Ajouter les options selon la langue
        if self.lang == 'fr':
            self.tree_context_menu.add_command(label="Copier URL", command=self._copy_tree_url)
            self.tree_context_menu.add_command(label="Copier nom fichier", command=self._copy_tree_filename)
            self.tree_context_menu.add_command(label="Copier ligne complète", command=self._copy_tree_full_line)
        else:
            self.tree_context_menu.add_command(label="Copy URL", command=self._copy_tree_url)
            self.tree_context_menu.add_command(label="Copy filename", command=self._copy_tree_filename)
            self.tree_context_menu.add_command(label="Copy full line", command=self._copy_tree_full_line)

    def _show_tree_context_menu(self, event):
        """Affiche le menu contextuel du tableau."""
        # Sélectionner l'item sous la souris
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            try:
                self.tree_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.tree_context_menu.grab_release()

    def _copy_tree_url(self):
        """Copie l'URL de l'élément sélectionné."""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            url = self.tree.item(item, 'values')[5]  # La colonne URL est à l'index 5
            self.root.clipboard_clear()
            self.root.clipboard_append(url)

    def _copy_tree_filename(self):
        """Copie le nom du fichier de l'élément sélectionné."""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            filename = self.tree.item(item, 'values')[0]  # La colonne nom est à l'index 0
            self.root.clipboard_clear()
            self.root.clipboard_append(filename)

    def _copy_tree_full_line(self):
        """Copie toute la ligne de l'élément sélectionné."""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            headers = [
                "Nom" if self.lang=='fr' else 'Name',
                "Statut" if self.lang=='fr' else 'Status',
                "Progression" if self.lang=='fr' else 'Progress',
                "Vitesse" if self.lang=='fr' else 'Speed',
                "Temps restant" if self.lang=='fr' else 'ETA',
                "URL"
            ]
            # Créer une ligne formatée avec les en-têtes
            line_parts = []
            for header, value in zip(headers, values):
                line_parts.append(f"{header}: {value}")
            full_line = " | ".join(line_parts)
            self.root.clipboard_clear()
            self.root.clipboard_append(full_line)

    def _apply_language_update(self):
        """Applique les textes correspondant à la langue courante (self.lang)."""
        self.root.title(TEXT[self.lang]['title'])
        self.lbl_outdir.config(text=TEXT[self.lang]['output_dir'])
        self.btn_browse.config(text=TEXT[self.lang]['browse'])
        self.lbl_api_key.config(text=TEXT[self.lang]['api_key_label'])
        self.api_save_btn.config(text=TEXT[self.lang]['api_key_save'])
        self.api_clear_btn.config(text=TEXT[self.lang]['api_key_clear'])
        self.frm_urls.config(text=TEXT[self.lang]['urls_box'])
        self.add_btn.config(text=TEXT[self.lang]['add'])
        self.start_btn.config(text=TEXT[self.lang]['start'])
        self.pause_btn.config(text=TEXT[self.lang]['resume'] if (self.pause_event and not self.pause_event.is_set()) else TEXT[self.lang]['pause'])
        self.stop_btn.config(text=TEXT[self.lang]['stop'])
        self.frm_table.config(text=TEXT[self.lang]['files'])
        self.frm_log.config(text=TEXT[self.lang]['logs'])
        # Mise à jour du menu contextuel des logs
        self._setup_log_context_menu()
        # Mise à jour du menu contextuel du tableau
        self._setup_tree_context_menu()
        # Mise à jour du placeholder API key
        if self._api_key_placeholder_active:
            self.api_key_var.set(TEXT[self.lang]['api_key_placeholder'])
        # Libellé progression globale
        self._update_total_progress_label()
        # En-têtes tableau
        headers = [
            "Nom" if self.lang=='fr' else 'Name',
            "Statut" if self.lang=='fr' else 'Status',
            "Progression" if self.lang=='fr' else 'Progress',
            "Vitesse" if self.lang=='fr' else 'Speed',
            "Temps restant" if self.lang=='fr' else 'ETA',
            "URL"
        ]
        for col, txt in zip(("display","status","progress","speed","eta","url"), headers):
            self.tree.heading(col, text=txt)
        # Traduction statuts existants
        map_fr_en = {
            'En attente': 'Waiting',
            'En cours': 'Running',
            'En pause': 'Paused',
            'Terminé': 'Done',
            'Erreur': 'Error',
            'Annulé': 'Cancelled'
        }
        map_en_fr = {v: k for k, v in map_fr_en.items()}
        for url, data in self.urls_in_progress.items():
            st = data.get('status', '')
            base = st
            if st.startswith(TEXT['fr']['wait_prefix'].strip()) or st.startswith('Attente '):
                if self.lang == 'en':
                    suf = st.split(' ', 1)[1] if ' ' in st else ''
                    base = f"{TEXT['en']['wait_prefix']}{suf}"
            elif st.startswith(TEXT['en']['wait_prefix']):
                if self.lang == 'fr':
                    suf = st[len(TEXT['en']['wait_prefix']):]
                    base = f"{TEXT['fr']['wait_prefix']}{suf}"
            else:
                if self.lang == 'en':
                    base = map_fr_en.get(st, st)
                else:
                    base = map_en_fr.get(st, st)
            data['status'] = base
            try:
                self.tree.set(data['iid'], 'status', base)
            except Exception:
                pass

    def on_language_change(self, event=None):
        sel = self.lang_var.get()
        new_lang = 'fr' if sel.startswith('Fr') else 'en'
        if new_lang != self.lang:
            self.lang = new_lang
            self._apply_language_update()

    def browse_outdir(self):
        """Ouvre un sélecteur de dossier et met à jour le chemin de sortie."""
        path = filedialog.askdirectory()
        if path:
            self.outdir_var.set(path)

    def append_log(self, msg: str):
        """Ajoute une chaîne dans la zone de logs (en conservant le scroll en bas)."""
        if self.lang == 'en':
            msg = self._translate_log_text(msg)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _poll_log_queue(self):
        """Récupère périodiquement les messages de LOG_QUEUE et met à jour UI.

        - Gère les retours chariot (\r) pour écraser la dernière ligne (progression inline).
        - Déclenche recalcul progression globale.
        """
        updated_any = False
        while True:
            try:
                item = LOG_QUEUE.get_nowait()
            except queue.Empty:
                break
            else:
                # Gérer les retours chariot (\r) pour progression inline
                if "\r" in item:
                    parts = item.split("\r")
                    for p in parts[:-1]:  # lignes complètes avant le dernier segment
                        if p:
                            self._update_progress_from_line(p + "\n")
                    last = parts[-1]
                    if last:
                        # Remplacer dernière ligne du widget
                        self._replace_last_log_line(last)
                        self._update_progress_from_line(last)
                else:
                    self.append_log(item)
                    self._update_progress_from_line(item)
                updated_any = True
        if updated_any:
            self._recompute_global_progress()
        self.root.after(150, self._poll_log_queue)

    def _replace_last_log_line(self, text):
        """Remplace la dernière ligne du widget log par `text` (utilisé pour \r)."""
        if self.lang == 'en':
            text = self._translate_log_text(text)
        self.log_text.configure(state=tk.NORMAL)
        # Trouver dernière ligne
        end_index = self.log_text.index("end-1c")
        line_start = self.log_text.index("end-2l linestart")
        self.log_text.delete(line_start, end_index)
        self.log_text.insert(line_start, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _translate_log_text(self, msg: str) -> str:
        """Convertit une ligne (ou bloc) de log FR -> EN si motifs connus.

        Traite ligne par ligne pour préserver les retours multi-lignes.
        """
        lines = msg.splitlines(keepends=True)
        out = []
        for ln in lines:
            core_line = ln.rstrip('\n')
            replaced = core_line
            for pat, repl in self._log_translate_patterns:
                if pat.search(core_line):
                    replaced = pat.sub(repl, core_line)
                    break
            out.append(replaced + ('\n' if ln.endswith('\n') else ''))
        return ''.join(out)

    def _update_progress_from_line(self, line: str):
        """Interprète une ligne de log pour en extraire des informations.

        Actions:
        - Capture et affecte un nom de fichier si log correspondant.
        - Marque un fichier terminé quand une ligne '✅ Terminé' apparaît.
        """
        # Capture nom affiché logué par main.py (souple sur le texte exact)
        if "📄" in line and ("Nom" in line or "Nom :" in line):
            # Extraire après le dernier ':'
            parts = line.split(":")
            if len(parts) > 1:
                name = parts[-1].strip()
                if name:
                    for url, data in self.urls_in_progress.items():
                        if not data.get('display'):
                            data['display'] = name
                            self.tree.set(data['iid'], 'display', name)
                            break
        elif line.startswith("✅ Terminé"):
            for url, data in self.urls_in_progress.items():
                if data['status'] == 'En cours':
                    data['status'] = 'Terminé'
                    data['pct'] = 100.0
                    self.tree.set(data['iid'], 'status', 'Terminé')
                    self.tree.set(data['iid'], 'progress', '100%')

    def _recompute_global_progress(self):
        """Calcule la moyenne simple des pourcentages des URLs suivies."""
        if not self.urls_in_progress:
            self.global_progress['value'] = 0
            self._update_total_progress_label()
            return
        total = sum(d.get('pct', 0) for d in self.urls_in_progress.values())
        avg = total / len(self.urls_in_progress)
        self.global_progress['value'] = avg
        self._update_total_progress_label()

    def _update_total_progress_label(self):
        """Met à jour le texte 'Fichier X/Y : Z%' ou 'File X/Y: Z%' selon langue."""
        total_files = len(self.urls_in_progress)
        if total_files == 0:
            self.total_progress_label_var.set('')
            return
        # Compter combien sont terminés (>=100%) pour index actuel
        finished = sum(1 for d in self.urls_in_progress.values() if d.get('pct',0) >= 100)
        # Position actuelle = fichiers complétés + 1 si un en cours
        current_index = finished
        any_running = any(d.get('status') in (TEXT[self.lang]['status_running'], TEXT[self.lang]['status_paused']) or (isinstance(d.get('pct'), float) and 0 < d.get('pct',0) < 100) for d in self.urls_in_progress.values())
        if any_running and finished < total_files:
            current_index = finished + 1
        percent = self.global_progress['value']
        if self.lang == 'fr':
            txt = f"Fichier {current_index}/{total_files} : {percent:.1f}%"
        else:
            txt = f"File {current_index}/{total_files}: {percent:.1f}%"
        self.total_progress_label_var.set(txt)

    def add_to_queue(self):
        """Ajoute les URLs saisies dans la file (sans démarrer)."""
        if self.downloading:
            messagebox.showinfo("Info", TEXT[self.lang]['info_add_disabled'])
            return
        urls_raw = self.urls_text.get("1.0", tk.END).strip().splitlines()
        urls = [u.strip() for u in urls_raw if u.strip()]
        if not urls:
            messagebox.showwarning("Info", TEXT[self.lang]['warn_no_url'])
            return
        outdir = self.outdir_var.get().strip()
        if not os.path.isdir(outdir):
            try:
                os.makedirs(outdir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"{TEXT[self.lang]['err_create_dir']} {e}")
                return
        new_urls = []
        for u in urls:
            if u in self.urls_in_progress:
                continue
            initial_status = TEXT[self.lang]['status_waiting']
            iid = self.tree.insert('', tk.END, values=('', initial_status, '0%', '', '', u))
            self.urls_in_progress[u] = {'iid': iid, 'status': initial_status, 'pct': 0.0, 'display': '', 'url': u, 'speed': '', 'eta': ''}
            self.queued_order.append(u)
            new_urls.append(u)
        # Efface la zone texte après ajout
        self.urls_text.delete("1.0", tk.END)
        # Préfetch des noms pour les nouvelles URLs (thread séparé)
        if new_urls:
            threading.Thread(target=self._prefetch_names_thread, args=(new_urls,), daemon=True).start()
        # Mettre à jour le libellé de progression globale (nombre de fichiers total changé)
        self._update_total_progress_label()

    def start_downloads(self):
        """Démarre l'exécution séquentielle des URLs en file (thread séparé)."""
        if self.downloading:
            messagebox.showinfo("Info", TEXT[self.lang]['info_downloading_exists'])
            return
        if not self.queued_order:
            # tenter d'ajouter ce qui est dans la zone
            self.add_to_queue()
            if not self.queued_order:
                return
        self.stop_requested = False
        self.downloading = True
        self.start_btn.configure(state=tk.DISABLED)
        self.add_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.NORMAL, text=TEXT[self.lang]['pause'])
        self.worker_thread = threading.Thread(target=self._thread_run, args=(self.outdir_var.get().strip(),), daemon=True)
        self.worker_thread.start()

    def _prefetch_names_thread(self, urls):
        """Enveloppe synchrone pour lancer l'extraction des noms en thread."""
        try:
            asyncio.run(self._async_prefetch_names(urls))
        except Exception as e:
            LOG_QUEUE.put(f"[Préfetch noms] Erreur: {e}\n")

    async def _async_prefetch_names(self, urls):
        """Coroutine: pré-récupère (en parallèle) les noms affichables des URLs.

        Utilise `core.prefetch_display_names` (limite de concurrence gérée dans core).
        La mise à jour de la Treeview est tolérante (try/except) car elle peut
        survenir alors que l'utilisateur manipule l'interface.
        """
        async with core.httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}):
            # Utilise une nouvelle session pour chaque (limitation mineure). On peut optimiser.
            async with core.httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:  # type: ignore[attr-defined]
                name_map = await core.prefetch_display_names(client, urls, log_cb=lambda m: LOG_QUEUE.put(m + ("\n" if not m.endswith("\n") else "")))
            for u, name in name_map.items():
                if name and u in self.urls_in_progress:
                    data = self.urls_in_progress[u]
                    if not data.get('display'):
                        data['display'] = name
                        try:
                            self.tree.set(data['iid'], 'display', name)
                        except Exception:
                            pass

    def toggle_pause(self):
        """Met en pause ou reprend les opérations (attente + téléchargement).

        - En pause: on efface (clear) l'Event -> les boucles asynchrones se bloquent.
        - Reprise: set() l'Event -> reprise des boucles. Si on était en 'Attente',
            on restaure le compte à rebours formatté; sinon 'En cours'.
        """
        if not self.downloading or not self.pause_event:
            return
        if self.pause_event.is_set():  # passer en pause
            self.pause_event.clear()
            self.pause_btn.configure(text=TEXT[self.lang]['resume'])
            for u, data in self.urls_in_progress.items():
                if data['status'] in (TEXT[self.lang]['status_running'],) or data['status'].startswith(TEXT[self.lang]['wait_prefix']):
                    data['status'] = TEXT[self.lang]['status_paused']
                    self.tree.set(data['iid'], 'status', data['status'])
        else:
            # reprise
            self.pause_event.set()
            self.pause_btn.configure(text=TEXT[self.lang]['pause'])
            # Restaurer 'En cours' pour l'URL active suivie ou sinon première en pause
            target = None
            if self.current_url and self.current_url in self.urls_in_progress and self.urls_in_progress[self.current_url]['status'] == 'En pause':
                target = self.current_url
            else:
                for u, d in self.urls_in_progress.items():
                    if d['status'] == 'En pause':
                        target = u
                        break
            if target:
                d = self.urls_in_progress[target]
                # Si encore en phase d'attente connue, restaurer le compte à rebours
                rem = self.wait_remaining.get(target)
                if isinstance(rem, int) and rem and rem > 0:
                    if rem >= 3600:
                        disp_t = TEXT[self.lang]['time_hms'].format(h=rem//3600, m=(rem%3600)//60, s=rem%60)
                    elif rem >= 60:
                        disp_t = TEXT[self.lang]['time_ms'].format(m=rem//60, s=rem%60)
                    else:
                        disp_t = TEXT[self.lang]['time_s'].format(s=rem)
                    d['status'] = f"{TEXT[self.lang]['wait_prefix']}{disp_t}"
                else:
                    d['status'] = TEXT[self.lang]['status_running']
                self.tree.set(d['iid'], 'status', d['status'])
                # Démarre un fallback de compte à rebours local si on est en attente
                if d['status'].startswith(TEXT[self.lang]['wait_prefix']):
                    self._ensure_local_wait_countdown(target)

    def request_stop(self):
        """Demande l'arrêt après le fichier courant (implémentation douce)."""
        # Pas de stop propre implémenté dans le code de base; on se contente d'un flag.
        self.stop_requested = True
        messagebox.showinfo("Info", TEXT[self.lang]['stop_info'])

    def _thread_run(self, outdir):
        """Point d'entrée du thread worker: exécute l'event loop asyncio."""
        # Rediriger stdout
        try:
            asyncio.run(self._async_download(outdir))
        except Exception as e:
            LOG_QUEUE.put(f"\n[Erreur] {e}\n")
        finally:
            self.root.after(0, self._on_all_done)

    async def _async_download(self, outdir):
        """Coroutine principale: préfetch des noms puis téléchargement séquentiel.

        Gère aussi l'initialisation de l'Event de pause et la mise à jour des
        colonnes de statut avant chaque fichier.
        """
        async with core.httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:  # type: ignore[attr-defined]
            # pause_event initialisé (set = fonctionnement normal)
            self.pause_event = asyncio.Event()
            self.pause_event.set()
            # Pré-récupération des noms (utile surtout si plusieurs URLs)
            try:
                urls = list(self.queued_order)
                if len(urls) > 0:
                    LOG_QUEUE.put(TEXT[self.lang]['prefetch_start'] + "\n")
                    name_map = await core.prefetch_display_names(
                        client,
                        urls,
                        log_cb=lambda m: LOG_QUEUE.put(m + ("\n" if not m.endswith("\n") else "")),
                    )
                    # Mise à jour de la colonne Nom
                    for u, name in name_map.items():
                        if not name:
                            continue
                        data = self.urls_in_progress.get(u)
                        if data:
                            data['display'] = name
                            try:
                                self.tree.set(data['iid'], 'display', name)
                            except Exception:
                                pass
                    LOG_QUEUE.put(TEXT[self.lang]['prefetch_summary_header'] + "\n")
                    for idx, u in enumerate(urls, 1):
                        nm = name_map.get(u) or TEXT[self.lang]['prefetch_unknown_name']
                        LOG_QUEUE.put(f"{idx:2d}. {nm}\n")
                    LOG_QUEUE.put("\n")
            except Exception as e:
                LOG_QUEUE.put(f"{TEXT[self.lang]['prefetch_error']} {e}\n")
            for url in list(self.queued_order):
                if self.stop_requested:
                    break
                data = self.urls_in_progress.get(url)
                if data:
                    data['status'] = TEXT[self.lang]['status_running']
                    self.tree.set(data['iid'], 'status', data['status'])
                self.current_url = url
                try:
                    await core.download_file(
                        client,
                        url,
                        outdir=outdir,
                        log_cb=lambda m, u=url: LOG_QUEUE.put(m + ("\n" if not m.endswith("\n") else "")),
                        progress_cb=self._progress_callback,
                        wait_cb=self._wait_callback,
                        pause_event=self.pause_event,
                        api_key=self.get_api_key(),
                    )
                except Exception as e:
                    LOG_QUEUE.put(f"\n❌ {TEXT[self.lang]['status_error']} {url}: {e}\n")
                    if data:
                        data['status'] = TEXT[self.lang]['status_error']
                        self.tree.set(data['iid'], 'status', data['status'])

    def _progress_callback(self, url, filename, downloaded, total, percent):
        """Callback progression (depuis core.download_file).

        Re-synchronisé vers le thread principal via root.after.
        Met à jour: pourcentage individuel + statut + progression globale + vitesse + ETA.
        """
        # Exécuter modifications UI dans le thread principal
        def _apply():
            data = self.urls_in_progress.get(url)
            if not data:
                return
            
            current_time = time.time()
            
            # Initialiser le temps de début si nécessaire
            if 'start_time' not in data:
                data['start_time'] = current_time
                data['last_update'] = current_time
                data['last_downloaded'] = downloaded
            
            # Calculer la vitesse (octets par seconde)
            time_diff = current_time - data.get('last_update', current_time)
            if time_diff > 0.5:  # Mettre à jour la vitesse toutes les 0.5 secondes
                bytes_diff = downloaded - data.get('last_downloaded', 0)
                speed_bps = bytes_diff / time_diff if time_diff > 0 else 0
                
                # Formater la vitesse
                if speed_bps < 1024:
                    speed_str = f"{speed_bps:.0f} B/s"
                elif speed_bps < 1024*1024:
                    speed_str = f"{speed_bps/1024:.1f} KB/s"
                elif speed_bps < 1024*1024*1024:
                    speed_str = f"{speed_bps/(1024*1024):.1f} MB/s"
                else:
                    speed_str = f"{speed_bps/(1024*1024*1024):.1f} GB/s"
                
                data['speed'] = speed_str
                data['last_update'] = current_time
                data['last_downloaded'] = downloaded
                
                # Calculer l'ETA
                if total and speed_bps > 0:
                    remaining_bytes = total - downloaded
                    eta_seconds = remaining_bytes / speed_bps
                    
                    if eta_seconds < 60:
                        eta_str = f"{eta_seconds:.0f}s"
                    elif eta_seconds < 3600:
                        minutes = int(eta_seconds // 60)
                        seconds = int(eta_seconds % 60)
                        eta_str = f"{minutes}m{seconds:02d}s"
                    else:
                        hours = int(eta_seconds // 3600)
                        minutes = int((eta_seconds % 3600) // 60)
                        eta_str = f"{hours}h{minutes:02d}m"
                    data['eta'] = eta_str
                else:
                    data['eta'] = '--'
                
                # Mettre à jour l'affichage
                self.tree.set(data['iid'], 'speed', data['speed'])
                self.tree.set(data['iid'], 'eta', data['eta'])
            
            if percent is not None:
                data['pct'] = percent
                self.tree.set(data['iid'], 'progress', f"{percent:.1f}%")
                # Si revenu de pause et statut resté 'En pause', remettre 'En cours'
                if data['status'] == TEXT[self.lang]['status_paused'] and (not self.pause_event or self.pause_event.is_set()):
                    data['status'] = TEXT[self.lang]['status_running']
                    self.tree.set(data['iid'], 'status', data['status'])
            
            if percent == 100 or (total and downloaded >= total):
                data['status'] = TEXT[self.lang]['status_done']
                data['speed'] = '--'
                data['eta'] = '--'
                self.tree.set(data['iid'], 'status', data['status'])
                self.tree.set(data['iid'], 'speed', data['speed'])
                self.tree.set(data['iid'], 'eta', data['eta'])
            
            self._recompute_global_progress()
        try:
            self.root.after(0, _apply)
        except Exception:
            pass

    def _wait_callback(self, url, remaining, total_wait):
        """Callback attente (compte à rebours) invoked par download_file.

        Sauvegarde `remaining` pour permettre restauration après pause.
        Formatage h/m/s cohérent avec la version CLI.
        """
        def _human(secs: int) -> str:
            if secs >= 3600:
                return f"{secs//3600}h{(secs%3600)//60:02d}m{secs%60:02d}s"
            if secs >= 60:
                return f"{secs//60}m{secs%60:02d}s"
            return f"{secs}s"
        def _apply():
            data = self.urls_in_progress.get(url)
            if not data:
                return
            # Mémorise le restant pour reprise
            self.wait_remaining[url] = remaining
            if remaining > 0:
                if data['status'] != TEXT[self.lang]['status_paused']:
                    r = remaining
                    if r >= 3600:
                        disp_t = TEXT[self.lang]['time_hms'].format(h=r//3600, m=(r%3600)//60, s=r%60)
                    elif r >= 60:
                        disp_t = TEXT[self.lang]['time_ms'].format(m=r//60, s=r%60)
                    else:
                        disp_t = TEXT[self.lang]['time_s'].format(s=r)
                    data['status'] = f"{TEXT[self.lang]['wait_prefix']}{disp_t}"
            else:
                if data['status'].startswith(TEXT[self.lang]['wait_prefix']):
                    data['status'] = TEXT[self.lang]['status_running']
            self.tree.set(data['iid'], 'status', data['status'])
        self.root.after(0, _apply)

    # -------- Countdown fallback GUI --------
    def _ensure_local_wait_countdown(self, url):
        """Démarre un thread léger qui décrémente localement le compte à rebours.

        Utilisé uniquement après reprise si le serveur ne renvoie plus de
        callbacks d'attente (cas rare). S'arrête dès qu'un changement d'état
        intervient ou que le temps atteint 0.
        """
        if url in self.wait_countdown_threads:
            return
        self.wait_countdown_threads.add(url)
        def runner():
            import time
            try:
                while True:
                    if not self.pause_event or not self.pause_event.is_set():
                        time.sleep(0.2)
                        continue
                    rem = self.wait_remaining.get(url)
                    if not isinstance(rem, int) or rem <= 0:
                        break
                    data = self.urls_in_progress.get(url)
                    if not data or not data['status'].startswith(TEXT[self.lang]['wait_prefix']):
                        break
                    time.sleep(1)
                    new_rem = self.wait_remaining.get(url)
                    if not isinstance(new_rem, int) or new_rem <= 0:
                        break
                    if new_rem == rem:  # aucun callback externe, décrément local
                        new_rem -= 1
                        self.wait_remaining[url] = new_rem
                        def _upd():
                            d = self.urls_in_progress.get(url)
                            if not d:
                                return
                            if isinstance(new_rem, int) and new_rem > 0 and d['status'].startswith(TEXT[self.lang]['wait_prefix']):
                                r = new_rem
                                if r >= 3600:
                                    disp_t = TEXT[self.lang]['time_hms'].format(h=r//3600, m=(r%3600)//60, s=r%60)
                                elif r >= 60:
                                    disp_t = TEXT[self.lang]['time_ms'].format(m=r//60, s=r%60)
                                else:
                                    disp_t = TEXT[self.lang]['time_s'].format(s=r)
                                d['status'] = f"{TEXT[self.lang]['wait_prefix']}{disp_t}"
                                self.tree.set(d['iid'], 'status', d['status'])
                            elif isinstance(new_rem, int) and new_rem <= 0:
                                d['status'] = TEXT[self.lang]['status_running']
                                self.tree.set(d['iid'], 'status', d['status'])
                        self.root.after(0, _upd)
            finally:
                self.wait_countdown_threads.discard(url)
        threading.Thread(target=runner, daemon=True).start()

    def _on_all_done(self):
        """Nettoyage UI une fois tous les téléchargements terminés ou arrêtés."""
        # Mettre les restants non terminés en 'Annulé'
        for url, data in self.urls_in_progress.items():
            if data['status'] in (TEXT[self.lang]['status_waiting'], TEXT[self.lang]['status_running']) or data['status'].startswith(TEXT[self.lang]['wait_prefix']):
                    if self.stop_requested:
                        data['status'] = TEXT[self.lang]['status_cancelled']
                        self.tree.set(data['iid'], 'status', data['status'])
                        self.start_btn.configure(state=tk.NORMAL)
                        self.stop_btn.configure(state=tk.DISABLED)

    def _save_api_key(self):
        """Sauvegarde la clé API dans un fichier de configuration."""
        api_key = self.get_api_key()
        if not api_key:
            messagebox.showwarning("Attention", "Aucune clé API à sauvegarder")
            return
        
        try:
            # Chiffrement simple (base64) pour éviter le stockage en clair
            encoded_key = base64.b64encode(api_key.encode('utf-8')).decode('utf-8')
            
            config = {}
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except:
                    config = {}
            
            config['api_key'] = encoded_key
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo("Succès", TEXT[self.lang]['api_key_saved'])
            
        except Exception as e:
            messagebox.showerror("Erreur", f"{TEXT[self.lang]['api_key_load_error']} {e}")

    def _clear_api_key(self):
        """Efface la clé API sauvegardée."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if 'api_key' in config:
                    del config['api_key']
                    
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2)
            
            # Effacer le champ
            self.api_key_var.set("")
            self._set_api_key_placeholder()
            
            messagebox.showinfo("Succès", TEXT[self.lang]['api_key_cleared'])
            
        except Exception as e:
            messagebox.showerror("Erreur", f"{TEXT[self.lang]['api_key_load_error']} {e}")

    def _load_api_key(self):
        """Charge la clé API depuis le fichier de configuration."""
        try:
            if not os.path.exists(self.config_file):
                return
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            encoded_key = config.get('api_key')
            if encoded_key:
                try:
                    # Déchiffrement
                    api_key = base64.b64decode(encoded_key.encode('utf-8')).decode('utf-8')
                    self.api_key_var.set(api_key)
                    self._api_key_placeholder_active = False
                    self.api_key_entry.config(show="*")
                    self.api_key_entry.config(foreground="black")
                except:
                    # Si le déchiffrement échoue, ignorer silencieusement
                    pass
                    
        except Exception:
            # Ignorer les erreurs de chargement silencieusement
            pass


def launch_gui():
    root = tk.Tk()
    app = DownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    launch_gui()
