# Gestionnaire de Téléchargements 1Fichier

Gestionnaire léger (GUI & CLI) pour le mode gratuit de [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> English: see **README.md**

## ✅ Fonctionnalités principales (côté utilisateur)
- Interface graphique simple (coller plusieurs liens, un par ligne)
- Détection automatique de l'attente + compte à rebours
- Téléchargements séquentiels avec progression par fichier + progression globale
- Reprise si le serveur accepte les requêtes partielles (fichier `.part`)
- Pause / Reprise / Stop (arrêt propre après le fichier en cours)
- Pré‑récupération des noms (affichés avant le premier téléchargement)
- Interface bilingue (FR / EN) + traduction basique des logs

## 🔽 Téléchargement (sans installer Python)
Récupérez l'exécutable Windows prêt à l'emploi :

➡️ https://github.com/RetroGameSets/1fichier/releases/latest/download/1fichier_gui.exe

Double‑cliquez simplement sur `1fichier_gui.exe` (la GUI s'ouvre par défaut).

## � Utilisation GUI
1. Coller une URL 1fichier par ligne
2. Choisir le dossier de sortie (ou garder `downloads`)
3. Cliquer sur Ajouter puis Démarrer (ou directement Démarrer si déjà en file)
4. Utiliser Pause / Reprendre / Stop si besoin
5. Barre de progression + texte global (Fichier X/Y : Z%)

## 🧪 Utilisation CLI (optionnel)
Exécution en terminal :
```powershell
python main.py https://1fichier.com/AAA https://1fichier.com/BBB -o downloads
```
GUI directement :
```powershell
python main.py --gui
```

Options basiques :
| Option | Signification |
| ------ | ------------- |
| `-o DIR` | Dossier de sortie |
| `--gui` | Lance la GUI |
| `--debug` | Verbosité + sauvegarde HTML intermédiaire (diagnostic) |

Sans URL, une invite interactive apparaît en mode CLI.

## � Reprise (simple)
Si un fichier partiel `nom.ext.part` existe et que le serveur supporte HTTP Range, la reprise continue; sinon redémarrage complet.

## 🛠 Construire depuis la source
Pré‑requis : Python 3.11+ et pip.
```powershell
pip install -r requirements.txt
python main.py --gui
```

### Construire l'exécutable Windows
```powershell
pip install pyinstaller
pyinstaller 1fichier_gui.spec
```
Résultat : `dist/1fichier_gui.exe`

### (Optionnel) Build CLI mono‑fichier
```powershell
pyinstaller --onefile --name 1fichier_cli main.py
```

## 🌐 Langue
Utilisez la liste déroulante (en haut à droite) pour basculer FR / EN à tout moment ; les statuts existants et certaines lignes de log sont traduits à la volée.

## ℹ️ Messages courants
| Message | Signification |
| ------- | ------------- |
| Captcha detected / Captcha détecté | Action manuelle requise dans le navigateur |
| Done → fichier | Téléchargement terminé |
| Waiting XmYs / Attente XmYs | Compte à rebours avant le prochain fichier |

## ⚠️ Avertissement
Usage à vos risques. Respectez les CGU de 1fichier et le droit d'auteur.

## 🤝 Contributions
Issues / PR bienvenues (captcha, tests, ergonomie).

## 📄 Licence
Pas de licence explicite pour l'instant ; usage personnel tant que rien n'est ajouté.

---
Bon téléchargement !
