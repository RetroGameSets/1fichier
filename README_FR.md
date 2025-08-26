# 1fichier Downloader par RGS

Téléchargeur (mode gratuit) pour [1fichier](https://1fichier.com) avec heuristiques robustes : gestion du temps d'attente, détection de lien direct, reprise, interface graphique Tkinter et mode ligne de commande asynchrone (httpx + asyncio).

## ✨ Fonctionnalités principales
- Interface graphique simple (Tkinter)
- Détection automatique du compte à rebours et attente avec affichage
- Heuristiques pour trouver le lien direct (formulaires, ancres, meta refresh, regex)
- Reprise si le serveur annonce `Accept-Ranges: bytes` (fichier *.part*)
- Détection basique Captcha et arrêt propre
- Extraction du nom de fichier affiché sur la page (meilleur feedback)
- Sauvegarde optionnelle de pages HTML intermédiaires (--save-html / F1_DEBUG)

## ⚙️ Installation
Pré‑requis : Python 3.11+ (testé jusqu'à 3.13) et `pip`.

```powershell
pip install -r requirements.txt
```

## 🚀 Utilisation CLI
Syntaxe de base :
```powershell
python main.py URL1 URL2 ... -o downloads
```

Options disponibles :
| Option | Description |
| ------ | ----------- |
| `-o, --output DIR` | Dossier de sortie (créé si absent) |
| `--debug` | Verbosité + sauvegarde de pages intermédiaires `debug_*.html` |
| `--save-html` | Force la sauvegarde des pages clés (utile diagnostic) |
| `--force-wait` | (Réservé / actuellement sans effet fonctionnel) |
| `--gui` | Ouvre directement l'interface graphique |

Sans URL sur la ligne de commande, une invite interactive apparaît.

Exemples :
```powershell
# Téléchargement unique
python main.py https://1fichier.com/XXXXXXXXXX -o downloads

# Plusieurs URLs + debug
python main.py https://1fichier.com/AAA https://1fichier.com/BBB --debug -o dl

# Interface graphique
python main.py --gui
```

## 🖥️ Interface graphique (GUI)
Lancement :
```powershell
python main.py --gui
```
Fonctions :
1. Coller une URL par ligne
2. Choisir le dossier de sortie
3. Démarrer : progression individuelle + progression moyenne
4. Bouton Stop : annule après le fichier courant

Astuce : Le binaire PyInstaller (voir plus bas) lancé sans arguments ouvre automatiquement la GUI.

## 🔄 Reprise de téléchargement
Un fichier partiel est stocké sous `nom.ext.part`. Si un téléchargement est relancé et que le serveur supporte la reprise (`Accept-Ranges: bytes`), le transfert reprend à partir de la taille existante. Sinon le téléchargement redémarre depuis zéro.

## 🧪 Variables d'environnement utiles
| Variable | Effet |
| -------- | ----- |
| `F1_DEBUG=1` | Active le mode debug même sans `--debug` |
| `F1_FAST=2` (ex.) | Accélère artificiellement l'attente (divise le temps par la valeur). Utile pour tests. |

Exemple (PowerShell) :
```powershell
$env:F1_DEBUG=1; python main.py URL
```

## 🧩 Fichiers générés en debug
Des fichiers `debug_<timestamp>_<label>.html` aident à diagnostiquer un changement de structure côté site.

## 🔐 Captcha
Si un Captcha est détecté le programme s'arrête pour l'URL correspondante. Il faut alors :
1. Ouvrir l'URL dans un navigateur
2. Résoudre le Captcha / se connecter si nécessaire
3. Relancer (un cookie réutilisable n'est pas encore géré automatiquement — contribution bienvenue)

## 🛠️ Construction d'un exécutable (PyInstaller)
Le fichier `1fichier_gui.spec` est fourni.

Installation PyInstaller :
```powershell
pip install pyinstaller
```
Build :
```powershell
pyinstaller 1fichier_gui.spec
```
En sortie : `dist/1fichier_gui.exe`. Ouvrez-le (double‑clic) pour la GUI.

Pour un build console (débogage) rapide :
```powershell
pyinstaller --onefile --name 1fichier_cli main.py
```

## 🧵 Architecture rapide
- `main.py` : logique cœur (analyse HTML, attente, reprise, téléchargement)
- `gui.py` : couche Tkinter + redirection logs + callbacks de progression
- `requirements.txt` : dépendances minimales (`httpx`, `beautifulsoup4`)

| Message | Signification / Action |
| ------- | ---------------------- |
| `⚠️ Captcha détecté` | Intervention manuelle requise |
| `❌ Page reçue indique indisponibilité` | Fichier supprimé / quota / DMCA |
| `❌ Impossible de trouver le lien direct` | Structure modifiée → relancer avec `--debug` et ouvrir les HTML sauvegardés |

## 🚧 Limitations / TODO
- Gestion automatique Captcha (non implémentée)
- Pas de limite de vitesse intégrée

## 🤝 Contributions
Issues / PR bienvenues : amélioration de détection de lien, gestion Captcha, tests unitaires.

## ⚖️ Avertissement
Utilisation à vos risques. Respectez les conditions d'utilisation du service 1fichier et la législation sur le droit d'auteur. Ce projet est fourni « tel quel » sans garantie.

## 📄 Licence
Aucune licence explicite fournie. Considérez l'usage personnel sauf indication contraire.

---
Bon téléchargement !
