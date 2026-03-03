"""
article_history.py — Track which article URLs have been used in generated sessions.

Prevents the same article from appearing across sessions within a day or across days.
History is stored in ~/ai-courses/used_articles.json and entries expire after 7 days.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import USED_ARTICLES_PATH, USED_ARTICLES_MAX_AGE_DAYS

log = logging.getLogger(__name__)


def load_history() -> dict:
    """Load used-article history. Returns {url: date_str} mapping."""
    path = Path(USED_ARTICLES_PATH)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("urls", {})
    except Exception as exc:
        log.warning("Could not load article history: %s", exc)
        return {}


def save_history(urls: dict) -> None:
    """Save used-article history, pruning entries older than max age."""
    cutoff = (datetime.now() - timedelta(days=USED_ARTICLES_MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    pruned = {url: date for url, date in urls.items() if date >= cutoff}

    path = Path(USED_ARTICLES_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"urls": pruned}, fh, indent=2, ensure_ascii=False)
    log.info("Saved article history: %d URLs (pruned %d expired)",
             len(pruned), len(urls) - len(pruned))


def record_used_urls(new_urls: list[str], date_str: str | None = None) -> None:
    """Add URLs to the history file."""
    if not new_urls:
        return
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    history = load_history()
    for url in new_urls:
        if url:
            history[url] = date_str
    save_history(history)


def filter_used_articles(articles: list[dict], label: str = "") -> list[dict]:
    """Remove articles whose URLs are already in the history.

    Returns the filtered list.  Skipped articles are logged.
    """
    history = load_history()
    if not history:
        return articles

    filtered = []
    skipped = 0
    for a in articles:
        url = a.get("url", "")
        if url and url in history:
            skipped += 1
            log.info("Skipping already-used article: %s (used on %s)",
                     a.get("title", url)[:80], history[url])
        else:
            filtered.append(a)

    if skipped:
        log.info("[%s] Filtered out %d already-used articles, %d remaining",
                 label or "dedup", skipped, len(filtered))
    return filtered
