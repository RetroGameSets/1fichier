# 1Fichier Download Manager by RGS

Lightweight GUI & CLI downloader for the free tier of [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> Français : voir **README_FR.md**

## ✅ Main Features (User Friendly)
- Simple graphical interface (paste multiple links, one per line)
- Automatic wait time detection & countdown display
- Sequential downloads with per‑file & global progress
- Resume support when the server allows partial content (creates `.part` file)
- Pause / Resume / Stop (graceful after current file)
- Filename pre‑fetch (names shown before first download starts)
- Bilingual UI (FR / EN) + log line translation

## 🔽 Get the App (No Python Needed)
Download the latest ready‑to‑run Windows executable:

➡️ https://github.com/RetroGameSets/1fichier/releases/latest/download/1fichier_gui.exe

Just double‑click `1fichier_gui.exe` (GUI opens by default).

## 🖥 GUI Usage
1. Paste one 1fichier URL per line
2. Select output folder (or keep default `downloads`)
3. Click Add then Start (or directly Start if already queued)
4. Use Pause / Resume / Stop as needed
5. Progress bar + textual global progress (File X/Y: Z%)

## 🧪 CLI Usage (Optional)
Run with Python if you prefer terminal mode:
```powershell
python main.py https://1fichier.com/AAA https://1fichier.com/BBB -o downloads
```
GUI directly:
```powershell
python main.py --gui
```

Basic options:
| Option | Meaning |
| ------ | ------- |
| `-o DIR` | Output directory |
| `--gui` | Launch GUI |
| `--debug` | Extra verbose + save intermediary HTML (for troubleshooting) |

If you launch without URLs, an interactive prompt appears in CLI mode.

## � Resume Logic (Simple)
If a previous partial file `name.ext.part` exists and the server supports HTTP range, download resumes; otherwise it restarts from zero.

## 🛠 Build From Source
Prerequisites: Python 3.11+ & pip.
```powershell
pip install -r requirements.txt
python main.py --gui
```

### Build Windows Executable Yourself
```powershell
pip install pyinstaller
pyinstaller 1fichier_gui.spec
```
Result: `dist/1fichier_gui.exe`

### (Optional) One‑file CLI build
```powershell
pyinstaller --onefile --name 1fichier_cli main.py
```

## 🌐 Language
Use the combo box (top right) to switch FR / EN at any time; existing statuses & some log lines are translated on the fly.

## ℹ️ Common Messages
| Message | Meaning |
| ------- | ------- |
| Captcha detected | Manual action required in browser |
| Done → filename | File finished successfully |
| Waiting XmYs | Countdown before allowed to start next download |

## � Disclaimer
Use at your own risk. Respect 1fichier Terms of Service and copyright laws.

## 🤝 Contributing
Issues / PRs welcome (better captcha handling, tests, UX polish).

## 📄 License
No explicit license yet; treat as personal use unless a license is later added.

---
Happy downloading!
