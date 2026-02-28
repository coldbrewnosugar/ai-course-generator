#!/usr/bin/env python3
"""
preferences.py — Read vote issues from GitHub, tally preferences, write preferences.json.

Reads all issues with the `vote` label from the site repo via `gh api`.
Parses issue body for structured vote data and tallies tag/source scores.

Usage:
    python3 preferences.py
"""

import sys
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import GITHUB_REPO, BASE_DIR, LOG_DIR

# ── Logging ────────────────────────────────────────────────────────────────────
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
today_str = datetime.now().strftime("%Y-%m-%d")
log_file = Path(LOG_DIR) / f"course_{today_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger(__name__)

PREFS_PATH = Path(BASE_DIR) / "preferences.json"


def fetch_vote_issues() -> list[dict]:
    """Fetch all issues with the `vote` label using gh api with pagination."""
    all_issues = []

    try:
        result = subprocess.run(
            [
                "gh", "api",
                "--paginate",
                f"repos/{GITHUB_REPO}/issues?labels=vote&state=all&per_page=100",
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.error("gh api failed: %s", result.stderr[:500])
        else:
            # --paginate concatenates JSON arrays, parse them
            raw = result.stdout.strip()
            if raw:
                issues = json.loads(raw)
                if isinstance(issues, list):
                    all_issues.extend(issues)

    except subprocess.TimeoutExpired:
        log.error("gh api timed out")
    except json.JSONDecodeError as exc:
        log.error("Failed to parse gh api response: %s", exc)

    log.info("Fetched %d vote issues from %s", len(all_issues), GITHUB_REPO)
    return all_issues


def parse_vote_body(body: str) -> list[dict]:
    """Parse structured vote data from issue body.

    Batch format (one issue, multiple votes):
        track:general
        date:2026-02-28

        up | Article Title | tags:tag1,tag2 | source:SourceName
        down | Another Article | tags:tag3 | source:OtherSource

    Returns a list of parsed vote dicts.
    """
    if not body:
        return []

    lines = body.strip().splitlines()
    metadata = {}
    votes = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Metadata lines (key:value without pipes)
        if "|" not in line and ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip().lower()] = value.strip()
            continue

        # Vote lines: "up | Title | tags:x,y | source:Z"
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue

        vote_dir = parts[0].lower()
        if vote_dir not in ("up", "down"):
            continue

        vote_data = {
            "vote": vote_dir,
            "tags": [],
            "source": "",
            "date": metadata.get("date", ""),
            "track": metadata.get("track", ""),
        }

        for part in parts[2:]:
            part = part.strip()
            if part.startswith("tags:"):
                vote_data["tags"] = [t.strip() for t in part[5:].split(",") if t.strip()]
            elif part.startswith("source:"):
                vote_data["source"] = part[7:].strip()

        votes.append(vote_data)

    return votes


def tally_preferences(issues: list[dict]) -> dict:
    """Tally tag and source scores from vote issues."""
    tag_scores: dict[str, int] = {}
    source_scores: dict[str, int] = {}
    total_votes = 0

    for issue in issues:
        body = issue.get("body", "")
        votes = parse_vote_body(body)

        for parsed in votes:
            total_votes += 1
            weight = 1 if parsed["vote"] == "up" else -1

            for tag in parsed["tags"]:
                tag_scores[tag] = tag_scores.get(tag, 0) + weight

            if parsed["source"]:
                source_scores[parsed["source"]] = source_scores.get(parsed["source"], 0) + weight

    return {
        "tags": tag_scores,
        "sources": source_scores,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_votes": total_votes,
    }


def main():
    log.info("Refreshing preferences from vote issues...")

    issues = fetch_vote_issues()
    prefs = tally_preferences(issues)

    PREFS_PATH.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote preferences to %s (%d votes, %d tags, %d sources)",
             PREFS_PATH, prefs["total_votes"],
             len(prefs["tags"]), len(prefs["sources"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
