"""
config.py — loads/creates config.json next to main.py
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULTS = {
    "groq_api_key": "YOUR_GROQ_API_KEY_HERE",
    "newsapi_key":  "",       # optional — free at newsapi.org (100 req/day)
    "gnews_key":    "",       # optional — free at gnews.io (100 req/day)
    "refresh_interval_minutes": 60,
    "notify_hot_only": False,
    "categories": ["launch", "ai", "alert", "security", "hardware", "general"],
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULTS)
        print(f"[config] Created default config at {CONFIG_PATH}")
        return dict(DEFAULTS)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge with defaults for any missing keys
    merged = {**DEFAULTS, **data}
    return merged


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
