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
        logging.StreamHandler(sys.stderr),
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --bg: #08090d;
  --surface: #12141c;
  --surface-hover: #181b26;
  --border: #1e2231;
  --border-light: #282d3e;
  --accent: #7c5cfc;
  --accent-glow: rgba(124,92,252,0.15);
  --accent-light: #a78bfa;
  --accent-surface: rgba(124,92,252,0.06);
  --text: #eaecf4;
  --text-secondary: #b0b8cd;
  --muted: #6b7394;
  --tag-daily-bg: rgba(52,211,153,0.1);
  --tag-daily-border: rgba(52,211,153,0.25);
  --tag-daily-text: #6ee7b7;
  --tag-mwf-bg: rgba(96,165,250,0.1);
  --tag-mwf-border: rgba(96,165,250,0.25);
  --tag-mwf-text: #93c5fd;
  --tag-tt-bg: rgba(232,121,249,0.1);
  --tag-tt-border: rgba(232,121,249,0.25);
  --tag-tt-text: #e879f9;
  --radius: 16px;
  --radius-sm: 10px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
.page-grain {
  position: fixed; inset: 0; z-index: 0; pointer-events: none; opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 256px;
}
.container { max-width: 860px; margin: 0 auto; padding: 0 1.5rem; position: relative; z-index: 1; }

/* ── Hero ── */
.hero {
  padding: 5rem 0 3.5rem;
  text-align: center;
  position: relative;
}
.hero::before {
  content: '';
  position: absolute;
  top: -60px; left: 50%; transform: translateX(-50%);
  width: 480px; height: 480px;
  background: radial-gradient(circle, rgba(124,92,252,0.08) 0%, transparent 70%);
  pointer-events: none;
}
.hero-eyebrow {
  display: inline-flex; align-items: center; gap: 0.5rem;
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent-light);
  background: var(--accent-surface);
  border: 1px solid rgba(124,92,252,0.15);
  border-radius: 100px;
  padding: 0.4rem 1rem;
  margin-bottom: 1.5rem;
}
.hero-eyebrow .pulse {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-light);
  animation: pulse 2.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(167,139,250,0.5); }
  50% { opacity: 0.6; box-shadow: 0 0 0 6px rgba(167,139,250,0); }
}
.hero h1 {
  font-size: 2.8rem;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.03em;
  color: var(--text);
}
.hero h1 .grad {
  background: linear-gradient(135deg, #a78bfa 0%, #7c5cfc 40%, #60a5fa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-sub {
  color: var(--text-secondary);
  font-size: 1.05rem;
  line-height: 1.6;
  margin-top: 1rem;
  max-width: 540px;
  margin-left: auto; margin-right: auto;
}

/* ── Section heading ── */
.section-label {
  font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 1.25rem;
  padding-left: 0.25rem;
}

/* ── Track cards ── */
.track-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.75rem;
  margin-bottom: 1.25rem;
  transition: border-color 0.2s, box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}
.track-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--card-accent, var(--accent)), transparent);
  opacity: 0;
  transition: opacity 0.3s;
}
.track-card:hover { border-color: var(--border-light); box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
.track-card:hover::before { opacity: 1; }
.track-card.accent-green  { --card-accent: #34d399; }
.track-card.accent-blue   { --card-accent: #60a5fa; }
.track-card.accent-purple { --card-accent: #c084fc; }
.track-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.track-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.15rem;
  flex-shrink: 0;
}
.track-icon.icon-general  { background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.2); }
.track-icon.icon-image    { background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.2); }
.track-icon.icon-audio    { background: rgba(192,132,252,0.1); border: 1px solid rgba(192,132,252,0.2); }
.track-meta { flex: 1; }
.track-title { font-size: 1.1rem; font-weight: 700; letter-spacing: -0.01em; }
.track-desc { font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; }
.schedule-tag {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.3rem 0.7rem;
  border-radius: 100px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}
.tag-daily  { background: var(--tag-daily-bg);  color: var(--tag-daily-text); border: 1px solid var(--tag-daily-border); }
.tag-mwf    { background: var(--tag-mwf-bg);    color: var(--tag-mwf-text);   border: 1px solid var(--tag-mwf-border); }
.tag-tt     { background: var(--tag-tt-bg);     color: var(--tag-tt-text);    border: 1px solid var(--tag-tt-border); }

/* ── Latest course row ── */
.latest-course {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--accent-surface);
  border: 1px solid rgba(124,92,252,0.12);
  border-radius: var(--radius-sm);
  padding: 1rem 1.15rem;
  margin-bottom: 1rem;
  gap: 1rem;
  transition: border-color 0.2s, background 0.2s;
}
.latest-course:hover {
  border-color: rgba(124,92,252,0.25);
  background: rgba(124,92,252,0.09);
}
.latest-label {
  font-size: 0.6rem; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--accent-light); font-weight: 700;
}
.latest-title { font-size: 0.92rem; color: var(--text); margin-top: 0.2rem; line-height: 1.35; }
.latest-date { font-size: 0.75rem; color: var(--muted); margin-top: 0.15rem; }
.btn {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.55rem 1.15rem;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  background: var(--accent);
  color: #fff;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(124,92,252,0.3);
}
.btn:hover {
  background: #8b6ffd;
  box-shadow: 0 4px 16px rgba(124,92,252,0.35);
  transform: translateY(-1px);
}
.btn svg { width: 14px; height: 14px; }

/* ── Archive ── */
.archive-toggle {
  font-size: 0.78rem;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
  padding: 0.4rem 0;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  transition: color 0.15s;
}
.archive-toggle:hover { color: var(--text-secondary); }
.archive-toggle .chevron {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 0.65rem;
}
details[open] .archive-toggle .chevron { transform: rotate(90deg); }
.archive-list {
  list-style: none;
  margin-top: 0.75rem;
  border-top: 1px solid var(--border);
  padding-top: 0.5rem;
}
.archive-list li {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.5rem;
  margin: 0.15rem 0;
  border-radius: 8px;
  gap: 1rem;
  transition: background 0.15s;
}
.archive-list li:hover { background: var(--surface-hover); }
.archive-date {
  color: var(--muted); font-size: 0.78rem; min-width: 6.5rem;
  font-variant-numeric: tabular-nums;
}
.archive-title { font-size: 0.85rem; flex: 1; color: var(--text-secondary); }
.archive-link {
  font-size: 0.75rem; font-weight: 500; color: var(--accent-light);
  text-decoration: none; padding: 0.2rem 0.6rem;
  border-radius: 6px; transition: all 0.15s;
}
.archive-link:hover { background: var(--accent-surface); }
.empty-state {
  color: var(--muted); font-size: 0.85rem; padding: 0.5rem 0;
  font-style: italic;
}

/* ── Footer ── */
footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  margin-top: 4rem;
  padding: 2rem 0;
  border-top: 1px solid var(--border);
}
footer .footer-brand { font-weight: 600; color: var(--text-secondary); }

/* ── Responsive ── */
@media (max-width: 600px) {
  .hero { padding: 3rem 0 2.5rem; }
  .hero h1 { font-size: 1.8rem; }
  .hero-sub { font-size: 0.92rem; }
  .track-card { padding: 1.25rem; }
  .latest-course { flex-direction: column; align-items: stretch; text-align: center; }
  .btn { justify-content: center; }
  .archive-list li { flex-wrap: wrap; gap: 0.25rem; }
  .archive-date { min-width: auto; }
}
"""

SCHEDULE_TAG_MAP = {
    "daily":       ("Daily", "tag-daily"),
    "mon,wed,fri": ("Mon · Wed · Fri", "tag-mwf"),
    "tue,thu":     ("Tue · Thu", "tag-tt"),
}

TRACK_META = {
    "general": {
        "icon_class": "icon-general",
        "icon_char":  "&#9670;",    # diamond
        "card_accent": "accent-green",
        "desc": "LLMs, research papers & coding advances",
    },
    "image-gen": {
        "icon_class": "icon-image",
        "icon_char":  "&#9635;",    # square with fill
        "card_accent": "accent-blue",
        "desc": "Diffusion models, video AI & vision",
    },
    "audio": {
        "icon_class": "icon-audio",
        "icon_char":  "&#9836;",    # beamed notes
        "card_accent": "accent-purple",
        "desc": "TTS, speech synthesis & music generation",
    },
}

TRACK_ORDER = ["general", "image-gen", "audio"]


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD as 'Feb 28, 2026' for display."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %-d, %Y")
    except Exception:
        return date_str


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

    # Count total courses
    total_courses = sum(len(v) for v in courses.values())

    # Build HTML cards
    cards_html = ""
    for track_name in TRACK_ORDER:
        track_cfg  = TRACKS.get(track_name, {})
        meta       = TRACK_META.get(track_name, {})
        label      = track_cfg.get("label", track_name)
        schedule   = track_cfg.get("schedule", "")
        tag_label, tag_class = SCHEDULE_TAG_MAP.get(schedule, (schedule, "tag-daily"))
        entries    = courses[track_name]

        icon_class  = meta.get("icon_class", "icon-general")
        icon_char   = meta.get("icon_char", "&#9670;")
        card_accent = meta.get("card_accent", "")
        desc        = meta.get("desc", "")

        if entries:
            latest = entries[0]
            latest_date_display = _format_date_display(latest['date'])
            latest_html = f"""
        <div class="latest-course">
          <div>
            <div class="latest-label">Latest Course</div>
            <div class="latest-title">{_html_escape(latest['title'])}</div>
            <div class="latest-date">{latest_date_display}</div>
          </div>
          <a href="{latest['rel_path']}" class="btn">Open <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
        </div>"""

            archive_items = ""
            for e in entries[1:]:
                date_display = _format_date_display(e['date'])
                archive_items += f"""
            <li>
              <span class="archive-date">{date_display}</span>
              <span class="archive-title">{_html_escape(e['title'])}</span>
              <a href="{e['rel_path']}" class="archive-link">View</a>
            </li>"""

            if archive_items:
                archive_section = f"""
        <details>
          <summary class="archive-toggle"><span class="chevron">&#9654;</span> Previous courses ({len(entries)-1})</summary>
          <ul class="archive-list">{archive_items}
          </ul>
        </details>"""
            else:
                archive_section = ""
        else:
            latest_html     = '<p class="empty-state">No courses yet &mdash; check back soon.</p>'
            archive_section = ""

        cards_html += f"""
      <div class="track-card {card_accent}">
        <div class="track-header">
          <div class="track-icon {icon_class}">{icon_char}</div>
          <div class="track-meta">
            <div class="track-title">{label}</div>
            <div class="track-desc">{desc}</div>
          </div>
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
  <meta name="description" content="Hands-on Jupyter Notebook courses synthesized daily from the latest AI research.">
  <style>{INDEX_CSS}</style>
</head>
<body>
  <div class="page-grain"></div>
  <div class="container">
    <div class="hero">
      <div class="hero-eyebrow"><span class="pulse"></span> Updated daily</div>
      <h1><span class="grad">AI Daily</span> Courses</h1>
      <p class="hero-sub">Hands-on Jupyter Notebook courses synthesized from the latest AI research &amp; news. Deep dives into models, architectures, and code &mdash; delivered fresh.</p>
    </div>
    <div class="section-label">Learning Tracks &middot; {total_courses} course{"s" if total_courses != 1 else ""}</div>
    {cards_html}
    <footer>
      <span class="footer-brand">AI Daily Courses</span> &middot; Auto-generated &middot; {now_str}
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
