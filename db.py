"""
db.py — SQLite helpers for storing articles and notification state.
"""

import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Optional


def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            summary      TEXT,
            category     TEXT DEFAULT 'general',
            source       TEXT,
            url          TEXT,
            is_hot       INTEGER DEFAULT 0,
            time_ago     TEXT,
            notified     INTEGER DEFAULT 0,
            ai_generated INTEGER DEFAULT 0,
            fetched_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    # Migrate existing DBs that lack the ai_generated column
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN ai_generated INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()


def _article_id(title: str) -> str:
    """Stable ID from title hash."""
    return hashlib.md5(title.strip().lower().encode()).hexdigest()[:16]


def save_articles(conn: sqlite3.Connection, articles: List[Dict]) -> int:
    """Insert new articles, skip duplicates. Returns count of newly inserted."""
    new_count = 0
    for a in articles:
        aid = _article_id(a.get("title", ""))
        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (id, title, summary, category, source, url, is_hot, time_ago, ai_generated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    aid,
                    a.get("title", ""),
                    a.get("summary", ""),
                    a.get("category", "general"),
                    a.get("source", ""),
                    a.get("url", ""),
                    1 if a.get("is_hot") else 0,
                    a.get("time_ago", ""),
                    1 if a.get("ai_generated") else 0,
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                new_count += 1
        except Exception as e:
            print(f"[db] insert error: {e}")
    conn.commit()
    return new_count


def get_recent_articles(conn: sqlite3.Connection, limit=30) -> List[Dict]:
    rows = conn.execute(
        """SELECT id, title, summary, category, source, url, is_hot, time_ago, ai_generated
           FROM articles ORDER BY fetched_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    cols = ["id", "title", "summary", "category", "source", "url", "is_hot", "time_ago", "ai_generated"]
    return [dict(zip(cols, r)) for r in rows]


def get_unnotified(conn: sqlite3.Connection) -> List[Dict]:
    rows = conn.execute(
        """SELECT id, title, summary, category, source, url, is_hot, time_ago, ai_generated
           FROM articles WHERE notified=0 ORDER BY is_hot DESC, fetched_at DESC"""
    ).fetchall()
    cols = ["id", "title", "summary", "category", "source", "url", "is_hot", "time_ago", "ai_generated"]
    return [dict(zip(cols, r)) for r in rows]


def mark_notified(conn: sqlite3.Connection, article_id: str):
    conn.execute("UPDATE articles SET notified=1 WHERE id=?", (article_id,))
    conn.commit()
