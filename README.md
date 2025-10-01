# 1Fichier Download Manager by RGS

Lightweight GUI & CLI downloader for the free and premium tiers of [1fichier](https://1fichier.com) (Python + Tkinter + asyncio/httpx).

> Français : voir **README_FR.md**

## ✅ Main Features (User Friendly)
- Simple graphical interface (paste multiple links, one per line)
- **Premium Mode via API**: Downloads without wait time using your 1fichier API key
- **Automatic Fallback**: If premium API fails, automatically switches to free mode
- **Real-time Speed & ETA**: Live download speed and estimated time remaining display
- **API Key Management**: Save and automatically reload your API key in GUI
- **Enhanced Interface**: Scrollable logs with right-click context menus for easy copying
- **Table Context Menus**: Right-click on files to copy URLs, filenames, or full information
- Automatic wait time detection & countdown display (free mode)
- Sequential downloads with per‑file & global progress
- Resume support when the server allows partial content (creates `.part` file)
- Pause / Resume / Stop (graceful after current file)
- Filename pre‑fetch (names shown before first download starts)
- Bilingual UI (FR / EN) + log line translation

## 🔑 Premium Usage (New!)
1. Get your premium API key from [1fichier.com](https://1fichier.com) (API section in your premium account)
2. **Test your API key**: `python test_api.py YOUR_API_KEY`
3. In the GUI, enter your API key in the "Premium API Key" field
4. Downloads will automatically use the premium API (no wait time)
5. If API fails (invalid key, limit reached), the system automatically falls back to free mode

### 🧪 API Key Testing
```powershell
# Test with API key and default URL
python test_api.py your_api_key_here

# Test with API key and specific URL
python test_api.py your_api_key_here https://1fichier.com/?abc123def456
```

## 🔽 Get the App (No Python Needed)
Download the latest ready‑to‑run Windows executable:

➡️ https://github.com/RetroGameSets/1fichier/releases/latest/download/1fichier_gui.exe

Just double‑click `1fichier_gui.exe` (GUI opens by default).

## 🖥 GUI Usage
1. **(New!) API Key Management**: Enter your premium API key and click "Save" to store it securely for future use
2. Paste one 1fichier URL per line
3. Select output folder (or keep default `downloads`)
4. Click Add then Start (or directly Start if already queued)
5. Use Pause / Resume / Stop as needed
6. Monitor real-time download speed, ETA, and progress for each file
7. **(New!) Right-click context menus**: 
   - **In logs**: Copy all/selection, clear logs
   - **In file table**: Copy URL, filename, or complete line information

The API key is automatically saved and reloaded between sessions. Use the "Clear" button to remove it.

**API Key Storage Details:**
- **Location**: `~/.1fichier_config.json` (user home directory)
- **Security**: Base64 encoded (not plain text storage)
- **Automatic**: Loaded on startup, saved on click

**Enhanced interface features:**
- **Speed column**: Real-time download speed (KB/s, MB/s, etc.)
- **ETA column**: Estimated time remaining (formatted as 1m30s, 2h05m, etc.)
- **Scrollable logs**: Navigate through long logs with the integrated scrollbar
- **Context menus**: Right-click to easily copy information from logs or file table

## 🧪 CLI Usage (Optional)
Run with API key for premium downloads:
```powershell
python main.py https://1fichier.com/AAA https://1fichier.com/BBB -o downloads --api-key YOUR_API_KEY
```
Traditional free mode:
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
| `--api-key KEY` | Premium API key for downloads without wait time |
| `--test-api` | Test API key without downloading |
| `--gui` | Launch GUI |
| `--debug` | Extra verbose + save intermediary HTML (for troubleshooting) |

If you launch without URLs, an interactive prompt appears in CLI mode.

## 🔑 Premium API Usage (Detailed)

### Getting Your API Key
1. Create an account on [1fichier.com](https://1fichier.com)
2. Subscribe to a premium plan
3. Go to your profile/settings
4. Generate an API key in the "API Access" section

### CLI Examples with API

#### Download with premium API
```powershell
python main.py --api-key YOUR_API_KEY https://1fichier.com/?abcd1234
```

#### Test your API key
```powershell
python main.py --api-key YOUR_API_KEY --test-api
```

#### Quick API test with dedicated script
```powershell
python test_api_quick.py YOUR_API_KEY
```

#### Automatic fallback (premium → free)
```powershell
# If API fails, automatically switches to free mode
python main.py --api-key INVALID_KEY https://1fichier.com/?file123
```

### Premium Advantages
- **No waiting time**: Instant downloads without countdown
- **Full speed**: Premium bandwidth without limitations
- **Better reliability**: Less risk of captcha or interruptions
- **Multiple downloads**: Parallel downloads support
- **Native resume**: Built-in resume capability

### Common API Error Messages

**401 - Not authenticated**
```
❌ HTTP error retrieving info: 401 - {"status":"KO","message":"Not authenticated #247"}
💡 Invalid or expired API key
```

**Account not premium**
```
❌ API info error: Account not premium
💡 Check that your API key is valid and you have an active premium account
```

**Download limit reached**
```
❌ API download error: Download limit reached
💡 Premium download limit exceeded
```

### Manual API Testing
```powershell
# Test connectivity with curl
curl -X POST https://api.1fichier.com/v1/file/info.cgi \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://1fichier.com/?egbirg99i0xnyikzmqhj"}'
```

Expected response (valid key):
```json
{
  "status": "OK",
  "filename": "example_file.zip",
  "size": "1073741824",
  "url": "https://1fichier.com/?egbirg99i0xnyikzmqhj"
}
```

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
| 🔑 Attempting premium download via API | Premium mode activated with your API key |
| ⚠️ Premium download failed, switching to free mode | Premium API failed, automatic fallback |
| Captcha detected | Manual action required in browser |
| Done → filename | File finished successfully |
| Waiting XmYs | Countdown before allowed to start next download (free mode) |

## � Disclaimer
Use at your own risk. Respect 1fichier Terms of Service and copyright laws.

## 🤝 Contributing
Issues / PRs welcome (better captcha handling, tests, UX polish).

## 📄 License
No explicit license yet; treat as personal use unless a license is later added.

---
Happy downloading!
