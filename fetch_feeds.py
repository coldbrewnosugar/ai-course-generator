#!/usr/bin/env python3
"""
fetch_feeds.py — RSS ingestion + article body extraction for a given track.

Usage:
    python3 fetch_feeds.py <track_name>
    python3 fetch_feeds.py general

Outputs JSON to /tmp/ai_course_articles_{track}_{date}.json and prints the path.
"""

import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

sys.path.insert(0, str(Path(__file__).parent))
from config import TRACKS, LOOKBACK_HOURS, MAX_ARTICLES, MAX_ARTICLE_CHARS, LOG_DIR

# ── Logging ────────────────────────────────────────────────────────────────────
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
today_str = datetime.now().strftime("%Y-%m-%d")
log_file = Path(LOG_DIR) / f"course_{today_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── HTTP helpers ───────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AICourseBot/1.0; "
        "+https://github.com/umbrel/ai-courses)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

FETCH_TIMEOUT = 10  # seconds per request
CRAWL_DELAY   = 0.5  # seconds between full-page fetches


def _parse_date(entry) -> datetime | None:
    """Return timezone-aware UTC datetime from a feedparser entry, or None."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                import calendar
                ts = calendar.timegm(t)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
    # fallback to raw string fields
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = dateutil_parser.parse(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def fetch_article_body(url: str) -> str:
    """
    Fetch full article text from URL.
    Targets <article> or <main> tags; falls back to <body>.
    Returns truncated plain text.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove boilerplate elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "figure", "noscript"]):
            tag.decompose()

        # Try article-level containers first
        container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=lambda c: c and any(
                kw in c.lower() for kw in ["post-content", "article-body",
                                            "entry-content", "content-body"]))
            or soup.body
        )
        text = container.get_text(separator="\n", strip=True) if container else ""

        # Collapse whitespace
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        text = "\n".join(lines)

        return text[:MAX_ARTICLE_CHARS]

    except Exception as exc:
        log.warning("Could not fetch %s: %s", url, exc)
        return ""


def fetch_track_articles(track_name: str) -> list[dict]:
    """
    Fetch and filter articles for the given track.
    Returns list of article dicts sorted by tier then recency.
    """
    if track_name not in TRACKS:
        raise ValueError(f"Unknown track: {track_name!r}. Valid: {list(TRACKS)}")

    track    = TRACKS[track_name]
    feeds    = track["feeds"]
    cutoff   = datetime.now(tz=timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    articles = []

    log.info("Fetching %d feeds for track '%s' (cutoff: %s)",
             len(feeds), track_name, cutoff.isoformat())

    for feed_cfg in feeds:
        url  = feed_cfg["url"]
        tier = feed_cfg["tier"]
        name = feed_cfg.get("name", url)
        log.info("  Parsing feed: %s (%s)", name, url)

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            log.warning("  Failed to parse %s: %s", url, exc)
            continue

        if parsed.bozo and parsed.bozo_exception:
            log.debug("  Feed bozo warning for %s: %s", name, parsed.bozo_exception)

        for entry in parsed.entries:
            pub_dt = _parse_date(entry)

            # Skip articles outside the time window
            if pub_dt and pub_dt < cutoff:
                continue

            link    = getattr(entry, "link", "")
            title   = getattr(entry, "title", "(untitled)")
            summary = getattr(entry, "summary", "")

            # Strip HTML from summary
            if summary:
                summary = BeautifulSoup(summary, "lxml").get_text(separator=" ", strip=True)
                summary = summary[:800]

            articles.append({
                "title":      title,
                "url":        link,
                "source":     name,
                "tier":       tier,
                "published":  pub_dt.isoformat() if pub_dt else "",
                "summary":    summary,
                "body":       "",   # filled in below
            })

    log.info("Found %d recent articles before dedup/sort", len(articles))

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique = []
    for a in articles:
        if a["url"] and a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            unique.append(a)

    # Sort: tier 1 first, then newest first within tier
    unique.sort(key=lambda a: (
        a["tier"],
        -(dateutil_parser.parse(a["published"]).timestamp()
          if a["published"] else 0)
    ))

    # Cap total
    selected = unique[:MAX_ARTICLES]
    log.info("Selected %d articles (cap=%d)", len(selected), MAX_ARTICLES)

    # Fetch full article bodies
    for i, article in enumerate(selected):
        if article["url"]:
            log.info("  [%d/%d] Fetching body: %s", i + 1, len(selected), article["url"])
            article["body"] = fetch_article_body(article["url"])
            time.sleep(CRAWL_DELAY)

    return selected


def main():
    parser = argparse.ArgumentParser(description="Fetch RSS articles for an AI course track.")
    parser.add_argument("track", choices=list(TRACKS.keys()),
                        help="Track to fetch articles for")
    args = parser.parse_args()

    track_name = args.track
    date_str   = datetime.now().strftime("%Y-%m-%d")
    out_path   = f"/tmp/ai_course_articles_{track_name}_{date_str}.json"

    articles = fetch_track_articles(track_name)

    payload = {
        "track":   track_name,
        "date":    date_str,
        "count":   len(articles),
        "articles": articles,
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    log.info("Wrote %d articles to %s", len(articles), out_path)
    print(out_path)  # consumed by shell script
    return 0


if __name__ == "__main__":
    sys.exit(main())
