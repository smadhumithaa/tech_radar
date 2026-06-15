"""
TechRadar — AI-powered tech news tray app
Runs on Windows startup, fetches news via Groq, sends desktop notifications.
"""

import sys
import threading
import time
import json
import sqlite3
import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path

# ── Third-party (installed via requirements.txt) ──────────────────────────────
try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
    from plyer import notification
    from groq import Groq
    import requests
except ImportError as e:
    print(f"Missing dependency: {e}\nRun: pip install -r requirements.txt")
    sys.exit(1)

from config import load_config
from db import init_db, save_articles, get_recent_articles, mark_notified, get_unnotified
from fetcher import fetch_tech_news
import server as dashboard_server

# ── Globals ───────────────────────────────────────────────────────────────────
APP_NAME   = "TechRadar"
APP_DIR    = Path(__file__).parent
DB_PATH    = APP_DIR / "db" / "news.db"
CONFIG     = load_config()
tray_icon  = None
last_fetch = None
fetch_thread = None


# ── Tray icon image (generated, no external file needed) ─────────────────────
def make_icon(color="#1a73e8"):
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    # Simple "R" letter for Radar
    draw.rectangle([18, 16, 24, 48], fill="white")
    draw.ellipse([18, 14, 44, 32], outline="white", width=3)
    draw.line([28, 30, 46, 48], fill="white", width=3)
    return img


def make_icon_alert():
    return make_icon("#e53935")


def make_icon_idle():
    return make_icon("#5c6bc0")


# ── Desktop notification ──────────────────────────────────────────────────────
def push_notification(title: str, message: str, urgent=False):
    try:
        notification.notify(
            title=f"{'🔴 ' if urgent else ''}TechRadar: {title}",
            message=message[:200],
            app_name=APP_NAME,
            timeout=8,
        )
    except Exception as e:
        print(f"[notify] {e}")


# ── Core fetch + notify loop ──────────────────────────────────────────────────
def fetch_and_notify(silent=False):
    global last_fetch, tray_icon

    print(f"[{datetime.now():%H:%M:%S}] Fetching tech news via Groq...")

    if tray_icon:
        try:
            tray_icon.icon = make_icon("#f59e0b")   # amber = fetching
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    try:
        articles = fetch_tech_news(CONFIG["groq_api_key"])
        if not articles:
            print("No articles returned.")
            return

        new_count = save_articles(conn, articles)
        last_fetch = datetime.now()
        print(f"  → {len(articles)} fetched, {new_count} new")

        # Notify for new articles
        unnotified = get_unnotified(conn)
        hot = [a for a in unnotified if a.get("is_hot")]
        normal = [a for a in unnotified if not a.get("is_hot")]

        # Hot stories first — individual notifications
        for a in hot[:3]:
            push_notification(a["title"], a["summary"], urgent=True)
            mark_notified(conn, a["id"])
            time.sleep(1.5)

        # Batch normal stories
        if normal and not silent:
            titles = " | ".join(a["title"][:50] for a in normal[:3])
            push_notification(
                f"{len(normal)} new tech stories",
                titles,
                urgent=False,
            )
            for a in normal:
                mark_notified(conn, a["id"])

        if tray_icon:
            icon_img = make_icon_alert() if hot else make_icon()
            try:
                tray_icon.icon = icon_img
                tray_icon.title = f"TechRadar — {len(articles)} stories • {last_fetch:%H:%M}"
            except Exception:
                pass

    except Exception as e:
        print(f"[fetch error] {e}")
        if tray_icon:
            try:
                tray_icon.icon = make_icon_idle()
            except Exception:
                pass
    finally:
        conn.close()


def background_refresh():
    """Runs on a thread — refresh every N minutes as configured."""
    interval_minutes = CONFIG.get("refresh_interval_minutes", 60)
    while True:
        time.sleep(interval_minutes * 60)
        fetch_and_notify()


# ── Tray menu actions ─────────────────────────────────────────────────────────
def action_refresh(_icon, _item):
    threading.Thread(target=fetch_and_notify, daemon=True).start()


def action_open_dashboard(_icon, _item):
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{dashboard_server.PORT}")


def action_open_settings(_icon, _item):
    config_file = APP_DIR / "config.json"
    os.startfile(str(config_file))


def action_quit(icon, _item):
    icon.stop()


# ── HTML dashboard generator ──────────────────────────────────────────────────
def generate_dashboard_html():
    conn = sqlite3.connect(DB_PATH)
    articles = get_recent_articles(conn, limit=30)
    conn.close()

    cat_colors = {
        "launch":   ("#E6F1FB", "#0C447C"),
        "ai":       ("#EEEDFE", "#3C3489"),
        "alert":    ("#FCEBEB", "#791F1F"),
        "security": ("#FAEEDA", "#633806"),
        "hardware": ("#EAF3DE", "#27500A"),
        "general":  ("#F1EFE8", "#444441"),
    }

    cards_html = ""
    for a in articles:
        bg, fg = cat_colors.get(a.get("category","general"), cat_colors["general"])
        hot_badge = '<span style="background:#FCEBEB;color:#A32D2D;padding:2px 8px;border-radius:20px;font-size:11px;margin-left:6px">🔴 Hot</span>' if a.get("is_hot") else ""
        url = a.get("url","#") or "#"
        cards_html += f"""
        <a href="{url}" target="_blank" style="display:block;text-decoration:none;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin-bottom:10px;transition:box-shadow .15s" onmouseover="this.style.boxShadow='0 2px 12px rgba(0,0,0,.08)'" onmouseout="this.style.boxShadow='none'">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500">{(a.get('category','general')).upper()}</span>
            {hot_badge}
            <span style="margin-left:auto;font-size:11px;color:#9ca3af">{a.get('source','')} · {a.get('time_ago','')}</span>
          </div>
          <div style="font-size:15px;font-weight:500;color:#111;margin-bottom:6px;line-height:1.4">{a.get('title','')}</div>
          <div style="font-size:13px;color:#6b7280;line-height:1.6">{a.get('summary','')}</div>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TechRadar Dashboard</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;color:#111;padding:24px}}
  .header{{max-width:760px;margin:0 auto 24px;display:flex;align-items:center;justify-content:space-between}}
  h1{{font-size:22px;font-weight:600}}
  .sub{{font-size:13px;color:#6b7280;margin-top:2px}}
  .feed{{max-width:760px;margin:0 auto}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>🛰 TechRadar</h1>
    <div class="sub">Last updated: {datetime.now():%d %b %Y, %H:%M} · {len(articles)} stories</div>
  </div>
</div>
<div class="feed">{cards_html if cards_html else '<p style="color:#9ca3af;text-align:center;padding:3rem">No articles yet — click Refresh from the tray icon.</p>'}</div>
</body>
</html>"""

    with open(APP_DIR / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    init_db(DB_PATH)

    # Start dashboard HTTP server
    dashboard_server.set_refresh_callback(fetch_and_notify)
    dashboard_server.start_server()

    # Initial fetch on startup
    threading.Thread(target=lambda: fetch_and_notify(silent=False), daemon=True).start()

    # Background refresh thread
    threading.Thread(target=background_refresh, daemon=True).start()

    # Tray icon setup
    global tray_icon
    menu = pystray.Menu(
        item("Refresh now",         action_refresh),
        item("Open dashboard",      action_open_dashboard),
        pystray.Menu.SEPARATOR,
        item("Settings",            action_open_settings),
        pystray.Menu.SEPARATOR,
        item("Quit TechRadar",      action_quit),
    )

    tray_icon = pystray.Icon(
        APP_NAME,
        make_icon(),
        f"{APP_NAME} — AI tech briefing",
        menu,
    )

    print(f"[TechRadar] Running in system tray. Refresh every {CONFIG['refresh_interval_minutes']} min.")
    tray_icon.run()


if __name__ == "__main__":
    main()
