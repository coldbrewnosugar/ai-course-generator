#!/usr/bin/env python3
"""
build_site.py — Convert a Jupyter Notebook to HTML and regenerate the site index.

Usage:
    python3 build_site.py <track_name> <date>
    python3 build_site.py general 2026-02-28

    # Regenerate only the index (after multiple tracks are built):
    python3 build_site.py --index-only
"""

import sys
import json
import logging
import argparse
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

import nbformat

sys.path.insert(0, str(Path(__file__).parent))
from config import TRACKS, OUTPUT_DIR, SITE_DIR, LOG_DIR

# ── Logging ────────────────────────────────────────────────────────────────────
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
today_str = datetime.now().strftime("%Y-%m-%d")
log_file  = Path(LOG_DIR) / f"course_{today_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── nbconvert ─────────────────────────────────────────────────────────────────

def convert_notebook_to_html(
    track_name: str, date_str: str
) -> Path | None:
    """
    Run `jupyter nbconvert --to html` on the notebook for the given track/date.
    Returns the output HTML path, or None on failure.
    """
    nb_path   = Path(OUTPUT_DIR) / track_name / f"{date_str}.ipynb"
    out_dir   = Path(SITE_DIR) / track_name
    out_path  = out_dir / f"{date_str}.html"

    if not nb_path.exists():
        log.error("Notebook not found: %s", nb_path)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine the venv python / jupyter path
    venv_jupyter = Path(__file__).parent / ".venv" / "bin" / "jupyter"
    jupyter_cmd  = str(venv_jupyter) if venv_jupyter.exists() else "jupyter"

    cmd = [
        jupyter_cmd, "nbconvert",
        "--to", "html",
        "--template", "lab",
        "--output", str(out_path),
        str(nb_path),
    ]

    log.info("Running nbconvert: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("nbconvert failed (exit %d): %s", result.returncode, result.stderr[:500])
        # Try without --template lab as fallback
        cmd_fallback = [
            jupyter_cmd, "nbconvert",
            "--to", "html",
            "--output", str(out_path),
            str(nb_path),
        ]
        log.info("Retrying without --template lab")
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result2.returncode != 0:
            log.error("nbconvert fallback also failed: %s", result2.stderr[:500])
            return None

    log.info("HTML written to %s", out_path)
    return out_path


# ── Title extraction ───────────────────────────────────────────────────────────

def get_course_title(track_name: str, date_str: str) -> str:
    """Extract H1 title from notebook, or return a default."""
    nb_path = Path(OUTPUT_DIR) / track_name / f"{date_str}.ipynb"
    try:
        nb = nbformat.read(str(nb_path), as_version=4)
        for cell in nb.cells:
            if cell.cell_type == "markdown":
                match = re.search(r"^#\s+(.+)$", cell.source, re.MULTILINE)
                if match:
                    return match.group(1).strip()
    except Exception:
        pass
    label = TRACKS.get(track_name, {}).get("label", track_name)
    return f"{label} — {date_str}"


# ── Index page generation ──────────────────────────────────────────────────────

INDEX_CSS = """
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --border: #2a2d3a;
  --accent: #6366f1;
  --accent-light: #818cf8;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --tag-daily: #065f46;
  --tag-mwf: #1e3a5f;
  --tag-tt: #4a1942;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  padding: 2rem 1rem;
}
.container { max-width: 900px; margin: 0 auto; }
header { margin-bottom: 3rem; text-align: center; }
header h1 {
  font-size: 2.2rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-light), #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
header p { color: var(--muted); margin-top: 0.5rem; font-size: 0.95rem; }
.track-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.track-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.track-title { font-size: 1.2rem; font-weight: 600; }
.schedule-tag {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.25rem 0.6rem;
  border-radius: 20px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.tag-daily  { background: var(--tag-daily);  color: #6ee7b7; }
.tag-mwf    { background: var(--tag-mwf);    color: #7dd3fc; }
.tag-tt     { background: var(--tag-tt);     color: #e879f9; }
.latest-course {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(99,102,241,0.08);
  border: 1px solid rgba(99,102,241,0.2);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin-bottom: 1rem;
  gap: 1rem;
}
.latest-label { font-size: 0.72rem; text-transform: uppercase;
                letter-spacing: 0.08em; color: var(--accent-light); font-weight: 600; }
.latest-title { font-size: 0.95rem; color: var(--text); margin-top: 0.15rem; }
.btn {
  display: inline-block;
  padding: 0.45rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  background: var(--accent);
  color: #fff;
  transition: background 0.15s;
}
.btn:hover { background: var(--accent-light); }
.archive-toggle {
  font-size: 0.82rem;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
  padding: 0.3rem 0;
  display: inline-block;
}
.archive-toggle:hover { color: var(--text); }
.archive-list {
  list-style: none;
  margin-top: 0.6rem;
  border-top: 1px solid var(--border);
  padding-top: 0.6rem;
}
.archive-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  gap: 1rem;
}
.archive-list li:last-child { border-bottom: none; }
.archive-date { color: var(--muted); font-size: 0.82rem; min-width: 7rem; }
.archive-title { font-size: 0.88rem; flex: 1; color: var(--text); }
.archive-link { font-size: 0.82rem; color: var(--accent-light); text-decoration: none; }
.archive-link:hover { text-decoration: underline; }
footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.8rem;
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}
"""

SCHEDULE_TAG_MAP = {
    "daily":       ("Daily", "tag-daily"),
    "mon,wed,fri": ("Mon · Wed · Fri", "tag-mwf"),
    "tue,thu":     ("Tue · Thu", "tag-tt"),
}

TRACK_ORDER = ["general", "image-gen", "audio"]


def generate_index_html(site_dir: Path) -> Path:
    """
    Scan site_dir for all HTML course files, build and write index.html.
    Returns the index path.
    """
    # Collect all course HTML files
    # Structure: site_dir/{track}/{date}.html
    courses: dict[str, list[dict]] = {t: [] for t in TRACK_ORDER}

    for track_name in TRACK_ORDER:
        track_dir = site_dir / track_name
        if not track_dir.is_dir():
            continue
        for html_file in sorted(track_dir.glob("????-??-??.html"), reverse=True):
            date_str = html_file.stem
            title    = get_course_title(track_name, date_str)
            rel_path = f"{track_name}/{html_file.name}"
            courses[track_name].append({
                "date":     date_str,
                "title":    title,
                "rel_path": rel_path,
            })

    # Build HTML cards
    cards_html = ""
    for track_name in TRACK_ORDER:
        track_cfg  = TRACKS.get(track_name, {})
        label      = track_cfg.get("label", track_name)
        schedule   = track_cfg.get("schedule", "")
        tag_label, tag_class = SCHEDULE_TAG_MAP.get(schedule, (schedule, "tag-daily"))
        entries    = courses[track_name]

        if entries:
            latest    = entries[0]
            latest_html = f"""
        <div class="latest-course">
          <div>
            <div class="latest-label">Latest</div>
            <div class="latest-title">{_html_escape(latest['title'])}</div>
          </div>
          <a href="{latest['rel_path']}" class="btn">View &rarr;</a>
        </div>"""

            archive_items = ""
            for e in entries[1:]:
                archive_items += f"""
            <li>
              <span class="archive-date">{e['date']}</span>
              <span class="archive-title">{_html_escape(e['title'])}</span>
              <a href="{e['rel_path']}" class="archive-link">View</a>
            </li>"""

            if archive_items:
                archive_section = f"""
        <details>
          <summary class="archive-toggle">Archive ({len(entries)-1} courses) ▸</summary>
          <ul class="archive-list">{archive_items}
          </ul>
        </details>"""
            else:
                archive_section = ""
        else:
            latest_html     = '<p style="color:var(--muted);font-size:0.9rem;">No courses yet — check back soon.</p>'
            archive_section = ""

        cards_html += f"""
      <div class="track-card">
        <div class="track-header">
          <span class="track-title">{label}</span>
          <span class="schedule-tag {tag_class}">{tag_label}</span>
        </div>
        {latest_html}
        {archive_section}
      </div>"""

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Daily Courses</title>
  <style>{INDEX_CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>AI Daily Courses</h1>
      <p>Hands-on Jupyter Notebook courses synthesized daily from the latest AI research &amp; news.</p>
    </header>
    {cards_html}
    <footer>
      Generated by AI Course Bot &middot; Updated {now_str}
    </footer>
  </div>
</body>
</html>"""

    index_path = site_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    log.info("index.html written (%d bytes)", len(html))
    return index_path


def _html_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert notebook to HTML and regenerate site index."
    )
    parser.add_argument("track", nargs="?", choices=list(TRACKS.keys()),
                        help="Track name")
    parser.add_argument("date",  nargs="?",
                        help="Date string YYYY-MM-DD")
    parser.add_argument("--index-only", action="store_true",
                        help="Only regenerate index.html, skip nbconvert")
    args = parser.parse_args()

    site_dir = Path(SITE_DIR)
    site_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0

    if not args.index_only and args.track and args.date:
        html_path = convert_notebook_to_html(args.track, args.date)
        if html_path is None:
            log.error("nbconvert step failed for %s/%s", args.track, args.date)
            exit_code = 1
        else:
            log.info("Conversion successful: %s", html_path)

    # Always regenerate index
    index_path = generate_index_html(site_dir)
    log.info("Site index: %s", index_path)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
