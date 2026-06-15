# 🛰 TechRadar — AI Tech News Briefing

Runs silently in your Windows system tray. Fetches the latest tech news on every login using **Groq (llama-3.3-70b)**, sends desktop notifications for breaking stories, and opens a local HTML dashboard.

---

## Quick start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your Groq API key

Edit `config.json`:

```json
{
  "groq_api_key": "gsk_your_key_here",
  ...
}
```

Get a free key at → **https://console.groq.com**

### 3. (Optional) Add a free news API key for live headlines

For real-time headlines instead of AI-generated ones, add one of:

- **NewsAPI** (free, 100 req/day) → https://newsapi.org  
  Set `"newsapi_key": "your_key"`

- **GNews** (free, 100 req/day) → https://gnews.io  
  Set `"gnews_key": "your_key"`

Without either key, Groq generates plausible recent tech news on its own.

### 4. Run the app

```bash
python main.py
```

A radar icon appears in your system tray. The app fetches news immediately, then every 60 minutes.

### 5. Register to run on Windows login

```bash
python install_startup.py
```

This uses Windows Task Scheduler (no admin needed). Alternatively:

```bash
python install_startup.py --bat
```

Places a `.bat` file in your Startup folder — always works.

---

## Tray menu

| Option | What it does |
|---|---|
| Refresh now | Fetch news immediately |
| Open dashboard | Opens `dashboard.html` in browser |
| Settings | Opens `config.json` in Notepad |
| Quit | Exits the app |

---

## Config options

| Key | Default | Description |
|---|---|---|
| `groq_api_key` | — | Required. From console.groq.com |
| `newsapi_key` | `""` | Optional. Live headlines from newsapi.org |
| `gnews_key` | `""` | Optional. Live headlines from gnews.io |
| `refresh_interval_minutes` | `60` | How often to auto-refresh |
| `notify_hot_only` | `false` | If true, only notify for 🔴 Hot stories |
| `categories` | all | Filter which categories to track |

---

## How it works

```
Startup / Timer trigger
        ↓
NewsAPI / GNews  →  raw headlines (20 articles)
        ↓
Groq llama-3.3-70b  →  curate top 8, summarize, categorize
        ↓
SQLite  →  deduplicate (skip already-seen stories)
        ↓
plyer  →  Windows desktop notifications
        ↓
dashboard.html  →  local browser view of all stories
```

---

## File structure

```
techradar/
├── main.py              # Entry point + tray icon
├── fetcher.py           # Groq + NewsAPI integration
├── db.py                # SQLite helpers
├── config.py            # Config loader
├── config.json          # Your settings (edit this)
├── install_startup.py   # Windows startup registration
├── requirements.txt
├── README.md
└── db/
    └── news.db          # Auto-created SQLite database
```

---

## Remove from startup

```bash
python install_startup.py --remove
```
