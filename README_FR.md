# Gestionnaire de Téléchargements 1Fichier par RGS

Gestionnaire léger (GUI & CLI) pour le mode gratuit et premium de [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> English: see **README.md**

## ✅ Fonctionnalités principales (côté utilisateur)
- Interface graphique simple (coller plusieurs liens, un par ligne)
- **Mode Premium via API** : Téléchargements sans attente avec votre clé API 1fichier
- **Fallback automatique** : Si l'API premium échoue, passage automatique en mode gratuit
- **Vitesse et ETA en temps réel** : Affichage de la vitesse et du temps restant estimé
- **Gestion de clé API** : Sauvegarde et rechargement automatique de votre clé API
- **Interface Améliorée** : Logs défilables avec menus contextuels pour copier facilement
- **Menus Contextuels Tableau** : Clic droit sur les fichiers pour copier URLs, noms ou informations complètes
- Détection automatique de l'attente + compte à rebours (mode gratuit)
- Téléchargements séquentiels avec progression par fichier + progression globale
- Reprise si le serveur accepte les requêtes partielles (fichier `.part`)
- Pause / Reprise / Stop (arrêt propre après le fichier en cours)
- Pré‑récupération des noms (affichés avant le premier téléchargement)
- Interface bilingue (FR / EN) + traduction basique des logs
- **Emplacement** : `~/.1fichier_config.json` (dossier utilisateur)
- **Sécurité** : Encodage Base64 (pas de stockage en texte brut)
- **Automatique** : Chargée au démarrage, sauvée au clic

**Fonctionnalités améliorées de l'interface :**
- **Colonne Vitesse** : Vitesse de téléchargement en temps réel (KB/s, MB/s, etc.)
- **Colonne Temps restant** : Temps estimé restant (formaté comme 1m30s, 2h05m, etc.)
- **Logs défilables** : Naviguez dans les longs logs avec la barre de défilement intégrée
- **Menus contextuels** : Clic droit pour copier facilement les informations des logs ou du tableauaire léger (GUI & CLI) pour le mode gratuit et premium de [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> English: see **README.md**

La clé API est automatiquement sauvegardée et rechargée entre les sessions. Utilisez le bouton "Effacer" pour la supprimer.

**Fonctionnalités améliorées de l'interface :**
- **Colonne Vitesse** : Vitesse de téléchargement en temps réel (KB/s, MB/s, etc.)
- **Colonne Temps restant** : Temps estimé restant (formaté comme 1m30s, 2h05m, etc.)
- **Logs défilables** : Naviguez dans les longs logs avec la barre de défilement intégrée
- **Menus contextuels** : Clic droit pour copier facilement les informations des logs ou du tableau

Gestionnaire léger (GUI & CLI) pour le mode gratuit et premium de [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> English: see **README.md**

## ✅ Fonctionnalités principales (côté utilisateur)
- Interface graphique simple (coller plusieurs liens, un par ligne)
- **Mode Premium via API** : Téléchargements sans attente avec votre clé API 1fichier
- **Fallback automatique** : Si l'API premium échoue, passage automatique en mode gratuit
- **Vitesse et ETA en temps réel** : Affichage de la vitesse et du temps restant estimé
- **Gestion de clé API** : Sauvegarde et rechargement automatique de votre clé API
- **Interface Améliorée** : Logs défilables avec menus contextuels pour copier facilement
- **Menus Contextuels Tableau** : Clic droit sur les fichiers pour copier URLs, noms ou informations complètes
- Détection automatique de l'attente + compte à rebours (mode gratuit)
- Téléchargements séquentiels avec progression par fichier + progression globale
- Reprise si le serveur accepte les requêtes partielles (fichier `.part`)
- Pause / Reprise / Stop (arrêt propre après le fichier en cours)
- Pré‑récupération des noms (affichés avant le premier téléchargement)
- Interface bilingue (FR / EN) + traduction basique des logs

## 🔑 Utilisation Premium (Nouveau!)
1. Obtenez votre clé API premium sur [1fichier.com](https://1fichier.com) (section API dans votre compte premium)
2. **Testez votre clé API** : `python test_api.py VOTRE_CLE_API`
3. Dans l'interface graphique, saisissez votre clé API dans le champ "Clé API Premium"
4. Les téléchargements utiliseront automatiquement l'API premium (sans attente)
5. En cas d'échec API (clé invalide, limite atteinte), le système bascule automatiquement vers le mode gratuit

### 🧪 Test de clé API
```powershell
# Test avec clé API et URL par défaut
python test_api.py votre_cle_api_ici

# Test avec clé API et URL spécifique
python test_api.py votre_cle_api_ici https://1fichier.com/?abc123def456
```

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
| `--api-key KEY` | Clé API premium pour téléchargements sans attente |
| `--test-api` | Tester la clé API sans télécharger |
| `--gui` | Lance la GUI |
| `--debug` | Verbosité + sauvegarde HTML intermédiaire (diagnostic) |

Sans URL, une invite interactive apparaît en mode CLI.

## 🔑 Utilisation API Premium (Détaillée)

### Obtention de votre clé API
1. Créez un compte sur [1fichier.com](https://1fichier.com)
2. Souscrivez à un abonnement premium
3. Allez dans votre profil/paramètres
4. Générez une clé API dans la section "Accès API"

### Exemples CLI avec API

#### Téléchargement premium avec clé API
```powershell
python main.py --api-key VOTRE_CLE_API https://1fichier.com/?abcd1234
```

#### Tester votre clé API
```powershell
python main.py --api-key VOTRE_CLE_API --test-api
```

#### Test rapide avec script dédié
```powershell
python test_api_quick.py VOTRE_CLE_API
```

#### Basculement automatique (premium → gratuit)
```powershell
# Si l'API échoue, bascule automatiquement en mode gratuit
python main.py --api-key CLE_INVALIDE https://1fichier.com/?file123
```

### Avantages du mode premium
- **Pas d'attente** : Téléchargements instantanés sans compte à rebours
- **Vitesse maximale** : Bande passante premium sans limitations
- **Meilleure fiabilité** : Moins de risques de captcha ou d'interruptions
- **Téléchargements multiples** : Support de téléchargements parallèles
- **Reprise native** : Capacité de reprise intégrée

### Messages d'erreur API courants

**401 - Non authentifié**
```
❌ Erreur HTTP lors de la récupération des infos: 401 - {"status":"KO","message":"Not authenticated #247"}
💡 Clé API invalide ou expirée
```

**Compte non premium**
```
❌ Erreur API info: Account not premium
💡 Vérifiez que votre clé API est valide et que vous avez un compte premium actif
```

**Limite de téléchargement atteinte**
```
❌ Erreur API téléchargement: Download limit reached
💡 Limite de téléchargement premium dépassée
```

### Test manuel de l'API
```powershell
# Test de connectivité avec curl
curl -X POST https://api.1fichier.com/v1/file/info.cgi \
  -H "Authorization: Bearer VOTRE_CLE_API" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://1fichier.com/?egbirg99i0xnyikzmqhj"}'
```

Réponse attendue (clé valide) :
```json
{
  "status": "OK",
  "filename": "exemple_fichier.zip",
  "size": "1073741824",
  "url": "https://1fichier.com/?egbirg99i0xnyikzmqhj"
}
```

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
| 🔑 Tentative téléchargement premium via API | Mode premium activé avec votre clé API |
| ⚠️ Échec téléchargement premium, passage en mode gratuit | L'API premium a échoué, fallback automatique |
| Captcha detected / Captcha détecté | Action manuelle requise dans le navigateur |
| Done → fichier | Téléchargement terminé |
| Waiting XmYs / Attente XmYs | Compte à rebours avant le prochain fichier (mode gratuit) |

## ⚠️ Avertissement
Usage à vos risques. Respectez les CGU de 1fichier et le droit d'auteur.

## 🤝 Contributions
Issues / PR bienvenues (captcha, tests, ergonomie).

## 📄 Licence
Pas de licence explicite pour l'instant ; usage personnel tant que rien n'est ajouté.

---
Bon téléchargement !
