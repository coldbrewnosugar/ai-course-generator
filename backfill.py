#!/usr/bin/env python3
"""
backfill.py — One-time script to generate sessions for the past N days.

Fetches all available RSS feed entries, buckets them by publish date,
and runs the generation pipeline for each day that has articles.

Usage:
    python3 backfill.py                    # backfill 7 days, general track
    python3 backfill.py --days 5           # backfill 5 days
    python3 backfill.py --track image-gen  # specific track
    python3 backfill.py --all-tracks       # all tracks (respects schedule)
    python3 backfill.py --dry-run          # show what would be generated
"""

import sys
import json
import time
import logging
import argparse
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from config import TRACKS, OUTPUT_DIR, SITE_DIR, LOG_DIR, SCHEDULE_DAYS
from fetch_feeds import fetch_track_articles, _parse_date, HEADERS, FETCH_TIMEOUT, extract_tags

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

# ── Logging ────────────────────────────────────────────────────────────────────
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
today_str = datetime.now().strftime("%Y-%m-%d")
log_file = Path(LOG_DIR) / f"backfill_{today_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
MAX_ARTICLE_CHARS = 3500
CRAWL_DELAY = 0.5


def fetch_all_feed_entries(track_name: str) -> list[dict]:
    """Fetch ALL entries from a track's feeds (no time cutoff)."""
    if track_name not in TRACKS:
        raise ValueError(f"Unknown track: {track_name!r}")

    track = TRACKS[track_name]
    feeds = track["feeds"]
    articles = []

    log.info("Fetching all entries from %d feeds for track '%s'", len(feeds), track_name)

    for feed_cfg in feeds:
        url = feed_cfg["url"]
        tier = feed_cfg["tier"]
        name = feed_cfg.get("name", url)
        log.info("  Parsing feed: %s", name)

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            log.warning("  Failed to parse %s: %s", url, exc)
            continue

        for entry in parsed.entries:
            pub_dt = _parse_date(entry)
            if not pub_dt:
                continue  # can't bucket without a date

            link = getattr(entry, "link", "")
            title = getattr(entry, "title", "(untitled)")
            summary = getattr(entry, "summary", "")

            if summary:
                summary = BeautifulSoup(summary, "lxml").get_text(separator=" ", strip=True)
                summary = summary[:800]

            articles.append({
                "title": title,
                "url": link,
                "source": name,
                "tier": tier,
                "published": pub_dt.isoformat(),
                "published_dt": pub_dt,
                "summary": summary,
                "body": "",
            })

    log.info("Fetched %d total entries across all feeds", len(articles))
    return articles


def bucket_by_date(articles: list[dict], days: int) -> dict[str, list[dict]]:
    """Group articles into daily buckets for the past N days."""
    today = datetime.now(tz=timezone.utc).date()
    buckets = defaultdict(list)

    for art in articles:
        pub_date = art["published_dt"].date()
        days_ago = (today - pub_date).days

        # Only include articles within the backfill window
        # Skip today (day 0) since the daily cron handles that
        if 1 <= days_ago <= days:
            date_str = pub_date.strftime("%Y-%m-%d")
            buckets[date_str].append(art)

    # Sort each bucket: tier 1 first, then newest
    for date_str in buckets:
        buckets[date_str].sort(key=lambda a: (
            a["tier"],
            -(a["published_dt"].timestamp())
        ))

    return dict(buckets)


def fetch_article_body(url: str) -> str:
    """Fetch full article text from URL (same as fetch_feeds.py)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "figure", "noscript"]):
            tag.decompose()

        container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=lambda c: c and any(
                kw in c.lower() for kw in ["post-content", "article-body",
                                            "entry-content", "content-body"]))
            or soup.body
        )
        text = container.get_text(separator="\n", strip=True) if container else ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        text = "\n".join(lines)
        return text[:MAX_ARTICLE_CHARS]

    except Exception as exc:
        log.warning("Could not fetch %s: %s", url, exc)
        return ""


def should_run_track_on_date(track_name: str, date_str: str) -> bool:
    """Check if a track is scheduled for a given date."""
    track = TRACKS[track_name]
    schedule = track.get("schedule", "daily")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = date_obj.weekday()  # 0=Mon, 6=Sun
    return weekday in SCHEDULE_DAYS.get(schedule, set())


def run_generation(track_name: str, date_str: str, articles: list[dict],
                   dry_run: bool = False) -> bool:
    """Run generate_course.py + build_site.py for a single day."""
    out_dir = Path(OUTPUT_DIR) / track_name
    out_path = out_dir / f"{date_str}.json"

    # Skip if session already exists
    if out_path.exists():
        log.info("  Session already exists: %s — skipping", out_path)
        return True

    if dry_run:
        log.info("  [DRY RUN] Would generate session for %s/%s (%d articles)",
                 track_name, date_str, len(articles))
        return True

    # Cap at 12 articles, fetch bodies for the selected ones
    selected = articles[:12]
    log.info("  Fetching article bodies for %d articles...", len(selected))
    for i, art in enumerate(selected):
        if art["url"] and not art["body"]:
            log.info("    [%d/%d] %s", i + 1, len(selected), art["url"])
            art["body"] = fetch_article_body(art["url"])
            time.sleep(CRAWL_DELAY)

    # Add tags to all articles
    for art in articles:
        if "tags" not in art:
            art["tags"] = extract_tags(art["title"], art.get("summary", ""))

    # Build candidate articles list
    selected_urls = {a["url"] for a in selected}
    candidate_articles = []
    for a in articles:
        candidate_articles.append({
            "title": a["title"],
            "url": a["url"],
            "source": a["source"],
            "tags": a.get("tags", []),
            "published": a["published"],
            "summary": a.get("summary", ""),
            "score": 0,
            "selected": a["url"] in selected_urls,
        })

    # Write articles JSON to /tmp
    payload = {
        "track": track_name,
        "date": date_str,
        "count": len(selected),
        "articles": [
            {k: v for k, v in art.items() if k != "published_dt"}
            for art in selected
        ],
        "candidate_articles": candidate_articles,
    }
    articles_path = f"/tmp/ai_course_articles_{track_name}_{date_str}.json"
    with open(articles_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    # Run generate_course.py
    python = str(SCRIPT_DIR / ".venv" / "bin" / "python3")
    if not Path(python).exists():
        python = shutil.which("python3") or "python3"

    log.info("  Running generate_course.py for %s/%s...", track_name, date_str)
    gen_start = time.time()
    try:
        result = subprocess.run(
            [python, str(SCRIPT_DIR / "generate_course.py"), track_name, articles_path],
            capture_output=True, text=True, timeout=1800,
        )
        gen_elapsed = time.time() - gen_start
        log.info("  Generation took %.0fs (exit code %d)", gen_elapsed, result.returncode)

        if result.returncode != 0:
            log.error("  generate_course.py failed: %s", result.stderr[:500])
            return False

        session_path = result.stdout.strip().split("\n")[-1]
        if not Path(session_path).exists():
            log.error("  Session file not created: %s", session_path)
            return False

    except subprocess.TimeoutExpired:
        log.error("  Generation timed out for %s/%s", track_name, date_str)
        return False

    # Run build_site.py
    log.info("  Running build_site.py for %s/%s...", track_name, date_str)
    try:
        result = subprocess.run(
            [python, str(SCRIPT_DIR / "build_site.py"), track_name, date_str],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.error("  build_site.py failed: %s", result.stderr[:500])
            return False
    except subprocess.TimeoutExpired:
        log.error("  build_site.py timed out")
        return False

    # Clean up temp articles
    Path(articles_path).unlink(missing_ok=True)

    log.info("  Done: %s/%s", track_name, date_str)
    return True


def main():
    parser = argparse.ArgumentParser(description="Backfill sessions for past days")
    parser.add_argument("--days", type=int, default=7,
                        help="Number of days to backfill (default: 7)")
    parser.add_argument("--track", choices=list(TRACKS.keys()),
                        help="Specific track to backfill (default: general)")
    parser.add_argument("--all-tracks", action="store_true",
                        help="Backfill all tracks (respects schedule)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without running")
    args = parser.parse_args()

    if args.all_tracks:
        tracks_to_run = list(TRACKS.keys())
    elif args.track:
        tracks_to_run = [args.track]
    else:
        tracks_to_run = ["general"]

    log.info("=" * 60)
    log.info("Backfill started: %d days, tracks: %s", args.days, tracks_to_run)
    log.info("=" * 60)

    results = {"generated": [], "skipped": [], "failed": []}

    for track_name in tracks_to_run:
        log.info("")
        log.info("── Track: %s ──", track_name)

        # Fetch all available entries
        all_articles = fetch_all_feed_entries(track_name)
        buckets = bucket_by_date(all_articles, args.days)

        log.info("Found articles for %d days: %s",
                 len(buckets),
                 ", ".join(f"{d} ({len(a)})" for d, a in sorted(buckets.items())))

        # Process each day (oldest first)
        for date_str in sorted(buckets.keys()):
            day_articles = buckets[date_str]

            # Check schedule
            if not should_run_track_on_date(track_name, date_str):
                log.info("  %s: skipping (not scheduled for %s)", date_str, track_name)
                results["skipped"].append(f"{track_name}/{date_str}")
                continue

            log.info("  %s: %d articles available", date_str, len(day_articles))

            if run_generation(track_name, date_str, day_articles, dry_run=args.dry_run):
                results["generated"].append(f"{track_name}/{date_str}")
            else:
                results["failed"].append(f"{track_name}/{date_str}")

    # Regenerate index
    if results["generated"] and not args.dry_run:
        log.info("")
        log.info("── Regenerating site index...")
        python = str(SCRIPT_DIR / ".venv" / "bin" / "python3")
        if not Path(python).exists():
            python = shutil.which("python3") or "python3"
        subprocess.run(
            [python, str(SCRIPT_DIR / "build_site.py"), "--index-only"],
            timeout=60,
        )

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("Backfill complete")
    log.info("  Generated: %d — %s", len(results["generated"]),
             ", ".join(results["generated"]) or "none")
    log.info("  Skipped:   %d — %s", len(results["skipped"]),
             ", ".join(results["skipped"]) or "none")
    log.info("  Failed:    %d — %s", len(results["failed"]),
             ", ".join(results["failed"]) or "none")
    log.info("=" * 60)

    return 1 if results["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
