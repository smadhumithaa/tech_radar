"""
fetcher.py — pulls tech news via Groq (llama-3.3-70b) with web search context.
Uses NewsAPI for raw headlines, then Groq to summarize + categorize them.
Falls back to Groq-only if no NewsAPI key is configured.
"""

import json
import re
import time
from datetime import datetime
from typing import List, Dict

try:
    from groq import Groq
    import requests
except ImportError:
    pass


CATEGORIES = ["launch", "ai", "alert", "security", "hardware", "general"]

SYSTEM_PROMPT = """You are a sharp, concise tech news curator. 
Given a list of raw tech headlines, return a JSON array of exactly 8 of the most important stories.

Each object must have:
- title       : string (max 90 chars, rewrite for clarity if needed)
- summary     : string (2 sentences max, your own words — why it matters)
- category    : one of: launch | ai | alert | security | hardware | general
- source      : string (publication name)
- url         : string (original URL or empty string)
- is_hot      : boolean (true only for major breaking stories)
- time_ago    : string (e.g. "2h ago", "just now", "5h ago")

Return ONLY the raw JSON array. No markdown, no backticks, no explanation."""


def fetch_headlines_newsapi(api_key: str) -> List[Dict]:
    """Fetch raw headlines from NewsAPI (free tier: 100 req/day)."""
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "technology",
            "language": "en",
            "pageSize": 20,
            "apiKey": api_key,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        return [
            {
                "title":  a.get("title", ""),
                "source": a.get("source", {}).get("name", ""),
                "url":    a.get("url", ""),
                "desc":   a.get("description", ""),
            }
            for a in articles if a.get("title")
        ]
    except Exception as e:
        print(f"[NewsAPI] {e}")
        return []


def fetch_headlines_gnews(api_key: str) -> List[Dict]:
    """Fallback: GNews API (free: 100 req/day)."""
    try:
        url = "https://gnews.io/api/v4/top-headlines"
        params = {
            "category": "technology",
            "lang": "en",
            "max": 20,
            "token": api_key,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        return [
            {
                "title":  a.get("title", ""),
                "source": a.get("source", {}).get("name", ""),
                "url":    a.get("url", ""),
                "desc":   a.get("description", ""),
            }
            for a in articles if a.get("title")
        ]
    except Exception as e:
        print(f"[GNews] {e}")
        return []


def groq_curate(groq_api_key: str, raw_headlines: List[Dict]) -> List[Dict]:
    """Send raw headlines to Groq for curation, summarization, categorization."""
    client = Groq(api_key=groq_api_key)

    # Build the user message
    headlines_text = "\n".join(
        f"{i+1}. [{h['source']}] {h['title']} — {h['desc']} ({h['url']})"
        for i, h in enumerate(raw_headlines)
    )

    today = datetime.now().strftime("%A, %d %B %Y, %H:%M")
    user_msg = f"Today is {today}.\n\nHere are the latest tech headlines:\n\n{headlines_text}\n\nCurate and return the top 8 as a JSON array."

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    raw = resp.choices[0].message.content.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        raise ValueError(f"No JSON array in Groq response:\n{raw[:300]}")
    return json.loads(match.group(0))


def groq_only_fetch(groq_api_key: str) -> List[Dict]:
    """
    Fallback: ask Groq directly to generate recent tech news 
    (no live data — uses training knowledge, good enough for a demo).
    """
    client = Groq(api_key=groq_api_key)
    today = datetime.now().strftime("%A, %d %B %Y")

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Today is {today}. Generate 8 realistic, plausible recent tech news stories "
                    "that a tech enthusiast would care about — product launches, AI releases, "
                    "outages, security incidents, hardware announcements. "
                    "Use realistic source names (TechCrunch, The Verge, Wired, ArsTechnica, etc). "
                    "Return ONLY the JSON array."
                ),
            },
        ],
        temperature=0.5,
        max_tokens=1500,
    )

    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        raise ValueError(f"No JSON in Groq fallback response:\n{raw[:300]}")
    return json.loads(match.group(0))


def fetch_tech_news(groq_api_key: str) -> List[Dict]:
    """
    Main entry point.
    1. Try NewsAPI → Groq curate
    2. Try GNews  → Groq curate  
    3. Groq-only fallback
    """
    from config import load_config
    cfg = load_config()

    raw = []

    # Try NewsAPI
    if cfg.get("newsapi_key"):
        raw = fetch_headlines_newsapi(cfg["newsapi_key"])

    # Try GNews
    if not raw and cfg.get("gnews_key"):
        raw = fetch_headlines_gnews(cfg["gnews_key"])

    if raw:
        print(f"  [fetcher] Got {len(raw)} raw headlines, sending to Groq...")
        try:
            return groq_curate(groq_api_key, raw)
        except Exception as e:
            print(f"  [fetcher] Groq curate failed: {e}")

    # Fallback: Groq-only
    print("  [fetcher] Using Groq-only mode (no live news API key configured)...")
    return groq_only_fetch(groq_api_key)
