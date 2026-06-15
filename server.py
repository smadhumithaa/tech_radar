"""
server.py — lightweight HTTP server for the TechRadar dashboard.
Serves dashboard.html and provides JSON API endpoints.
"""

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "db" / "news.db"
CONFIG_PATH = APP_DIR / "config.json"
DASHBOARD_PATH = APP_DIR / "dashboard.html"

PORT = 7474
_refresh_callback = None  # Set by main.py


def set_refresh_callback(fn):
    global _refresh_callback
    _refresh_callback = fn


def _get_articles(limit=50, category=None, hot_only=False):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM articles"
        conditions = []
        params = []
        if category and category != "all":
            conditions.append("category = ?")
            params.append(category)
        if hot_only:
            conditions.append("is_hot = 1")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _get_stats():
    if not DB_PATH.exists():
        return {"total": 0, "hot": 0, "categories": {}}
    conn = sqlite3.connect(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        hot = conn.execute("SELECT COUNT(*) FROM articles WHERE is_hot=1").fetchone()[0]
        cat_rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category"
        ).fetchall()
        cats = {r[0]: r[1] for r in cat_rows}
        last_fetch = conn.execute(
            "SELECT MAX(fetched_at) FROM articles"
        ).fetchone()[0]
        return {"total": total, "hot": hot, "categories": cats, "last_fetch": last_fetch}
    finally:
        conn.close()


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default access logs

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/dashboard":
            if DASHBOARD_PATH.exists():
                self._send_html(DASHBOARD_PATH.read_text(encoding="utf-8"))
            else:
                self._send_html("<h1>Dashboard not generated yet.</h1>")

        elif path == "/api/articles":
            category = qs.get("category", ["all"])[0]
            hot_only = qs.get("hot_only", ["false"])[0] == "true"
            limit = int(qs.get("limit", ["60"])[0])
            articles = _get_articles(limit=limit, category=category, hot_only=hot_only)
            self._send_json({"articles": articles, "count": len(articles)})

        elif path == "/api/stats":
            self._send_json(_get_stats())

        elif path == "/api/config":
            if CONFIG_PATH.exists():
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                # Mask the API key partially for display
                if cfg.get("groq_api_key"):
                    k = cfg["groq_api_key"]
                    cfg["groq_api_key_masked"] = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
                self._send_json(cfg)
            else:
                self._send_json({})

        elif path == "/api/refresh":
            if _refresh_callback:
                threading.Thread(target=_refresh_callback, daemon=True).start()
                self._send_json({"status": "refresh_started"})
            else:
                self._send_json({"status": "no_callback"}, 503)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                new_cfg = json.loads(body)
                if CONFIG_PATH.exists():
                    existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                else:
                    existing = {}
                # Only update safe fields (don't allow overwriting keys blindly)
                allowed = ["refresh_interval_minutes", "notify_hot_only", "categories",
                           "newsapi_key", "gnews_key", "groq_api_key"]
                for k in allowed:
                    if k in new_cfg:
                        existing[k] = new_cfg[k]
                CONFIG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                self._send_json({"status": "saved"})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 400)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_server():
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[TechRadar] Dashboard server running at http://127.0.0.1:{PORT}")
    return server
