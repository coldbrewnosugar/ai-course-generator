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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,700;0,9..144,900;1,9..144,400&family=Outfit:wght@300;400;500;600;700&display=swap');
:root {
  --bg: #f6f3ed;
  --bg-dot: #e0dbd2;
  --surface: #fffefa;
  --surface-hover: #faf7f0;
  --border: #e5e0d5;
  --border-strong: #cdc6b8;
  --ink: #1a1a2e;
  --ink-secondary: #3d3b4a;
  --muted: #8a8694;
  --accent: #c03d1a;
  --accent-hover: #a83415;
  --accent-surface: rgba(192,61,26,0.04);
  --track-green: #1a7a4c;
  --track-green-bg: rgba(26,122,76,0.06);
  --track-blue: #2563a0;
  --track-blue-bg: rgba(37,99,160,0.06);
  --track-violet: #7c3aad;
  --track-violet-bg: rgba(124,58,173,0.06);
  --serif: 'Fraunces', 'Georgia', serif;
  --sans: 'Outfit', system-ui, sans-serif;
  --radius: 12px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

/* ── Dot-grid background (notebook paper) ── */
.page-dots {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: radial-gradient(circle, var(--bg-dot) 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.5;
}

.container {
  max-width: 820px; margin: 0 auto; padding: 0 1.5rem;
  position: relative; z-index: 1;
}

/* ── Hero ── */
.hero {
  padding: 5.5rem 0 1.5rem;
  position: relative;
}
.hero-mono {
  font-family: var(--serif);
  font-size: 3.8rem;
  font-weight: 900;
  font-style: italic;
  color: var(--accent);
  line-height: 1;
  letter-spacing: -0.04em;
  opacity: 0.12;
  position: absolute;
  top: 1.8rem;
  right: 0;
  user-select: none;
  pointer-events: none;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 0.5rem;
  font-size: 0.68rem; font-weight: 600;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 1.25rem;
}
.hero-badge::before {
  content: '';
  width: 24px; height: 1px;
  background: var(--accent);
}
.hero h1 {
  font-family: var(--serif);
  font-size: 3rem;
  font-weight: 900;
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: var(--ink);
  max-width: 520px;
}
.hero h1 em {
  font-style: italic;
  font-weight: 300;
  color: var(--accent);
}
.hero-sub {
  font-size: 1rem;
  line-height: 1.7;
  color: var(--ink-secondary);
  margin-top: 1.25rem;
  max-width: 480px;
  font-weight: 300;
}
.hero-rule {
  width: 100%; height: 1px;
  background: var(--border);
  margin: 2.5rem 0 2rem;
  border: none;
}

/* ── Section heading ── */
.section-label {
  font-family: var(--sans);
  font-size: 0.68rem; font-weight: 600;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 1.5rem;
}

/* ── Track cards ── */
.tracks { display: flex; flex-direction: column; gap: 1rem; }
.track-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--card-color, var(--accent));
  border-radius: 2px var(--radius) var(--radius) 2px;
  padding: 1.75rem 1.75rem 1.75rem 1.5rem;
  position: relative;
  transition: transform 0.3s cubic-bezier(0.23,1,0.32,1),
              box-shadow 0.3s cubic-bezier(0.23,1,0.32,1);
  animation: card-in 0.6s cubic-bezier(0.23,1,0.32,1) both;
}
.track-card:nth-child(1) { animation-delay: 0.05s; }
.track-card:nth-child(2) { animation-delay: 0.15s; }
.track-card:nth-child(3) { animation-delay: 0.25s; }
@keyframes card-in {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.track-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(26,26,46,0.08), 0 2px 8px rgba(26,26,46,0.04);
}
.track-card.color-green  { --card-color: var(--track-green); }
.track-card.color-blue   { --card-color: var(--track-blue); }
.track-card.color-violet { --card-color: var(--track-violet); }

/* Track number watermark */
.track-card .track-num {
  position: absolute;
  top: 0.75rem; right: 1.25rem;
  font-family: var(--serif);
  font-size: 3.2rem;
  font-weight: 900;
  line-height: 1;
  color: var(--card-color, var(--accent));
  opacity: 0.06;
  user-select: none;
  pointer-events: none;
}

.track-header {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  margin-bottom: 1.25rem;
}
.track-icon {
  width: 38px; height: 38px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: 1rem;
  background: var(--card-bg, var(--accent-surface));
  color: var(--card-color, var(--accent));
  border: 1px solid color-mix(in srgb, var(--card-color, var(--accent)) 15%, transparent);
}
.track-card.color-green  .track-icon { background: var(--track-green-bg); }
.track-card.color-blue   .track-icon { background: var(--track-blue-bg); }
.track-card.color-violet .track-icon { background: var(--track-violet-bg); }
.track-meta { flex: 1; min-width: 0; }
.track-title {
  font-family: var(--serif);
  font-size: 1.15rem; font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink);
}
.track-desc {
  font-size: 0.8rem; color: var(--muted);
  margin-top: 0.2rem; font-weight: 400;
}
.schedule-tag {
  font-size: 0.6rem; font-weight: 600;
  padding: 0.3rem 0.65rem;
  border-radius: 4px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
  margin-top: 0.15rem;
  flex-shrink: 0;
}
.tag-daily  { background: var(--track-green-bg); color: var(--track-green); border: 1px solid color-mix(in srgb, var(--track-green) 18%, transparent); }
.tag-mwf    { background: var(--track-blue-bg);  color: var(--track-blue);  border: 1px solid color-mix(in srgb, var(--track-blue) 18%, transparent); }
.tag-tt     { background: var(--track-violet-bg); color: var(--track-violet); border: 1px solid color-mix(in srgb, var(--track-violet) 18%, transparent); }

/* ── Latest course row ── */
.latest-course {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem;
  margin-bottom: 0.75rem;
  background: var(--surface-hover);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color 0.2s;
}
.latest-course:hover { border-color: var(--border-strong); }
.latest-info { min-width: 0; }
.latest-label {
  font-size: 0.58rem; text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--card-color, var(--accent));
  font-weight: 700;
}
.latest-title {
  font-size: 0.9rem; color: var(--ink);
  margin-top: 0.2rem; line-height: 1.35;
  font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.latest-date {
  font-size: 0.72rem; color: var(--muted);
  margin-top: 0.15rem; font-weight: 400;
}
.btn {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-family: var(--sans);
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  color: #fff;
  background: var(--card-color, var(--accent));
  transition: all 0.2s cubic-bezier(0.23,1,0.32,1);
}
.btn:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--card-color, var(--accent)) 25%, transparent);
}
.btn svg { width: 13px; height: 13px; stroke-width: 2.5; }

/* ── Archive ── */
.archive-toggle {
  font-size: 0.75rem; font-weight: 500;
  color: var(--muted);
  cursor: pointer; user-select: none;
  padding: 0.3rem 0;
  display: inline-flex; align-items: center; gap: 0.4rem;
  transition: color 0.15s;
}
.archive-toggle:hover { color: var(--ink-secondary); }
.archive-toggle .chevron {
  display: inline-block;
  transition: transform 0.25s cubic-bezier(0.23,1,0.32,1);
  font-size: 0.55rem;
}
details[open] .archive-toggle .chevron { transform: rotate(90deg); }
.archive-list {
  list-style: none;
  margin-top: 0.6rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
}
.archive-list li {
  display: flex; align-items: center;
  padding: 0.45rem 0.5rem;
  margin: 0.1rem 0;
  border-radius: 6px;
  gap: 1rem;
  transition: background 0.15s;
}
.archive-list li:hover { background: var(--surface-hover); }
.archive-date {
  color: var(--muted); font-size: 0.75rem;
  min-width: 6rem; font-variant-numeric: tabular-nums;
  font-weight: 400;
}
.archive-title {
  font-size: 0.82rem; flex: 1; color: var(--ink-secondary);
  font-weight: 400;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.archive-link {
  font-size: 0.72rem; font-weight: 600;
  color: var(--card-color, var(--accent));
  text-decoration: none;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  transition: all 0.15s;
}
.archive-link:hover {
  background: var(--accent-surface);
  text-decoration: none;
}
.empty-state {
  color: var(--muted); font-size: 0.85rem;
  padding: 0.5rem 0; font-style: italic;
}

/* ── Footer ── */
footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.7rem;
  letter-spacing: 0.03em;
  margin-top: 4rem;
  padding: 2rem 0 3rem;
  border-top: 1px solid var(--border);
}
footer .footer-brand {
  font-family: var(--serif);
  font-weight: 700; font-style: italic;
  color: var(--ink-secondary);
}

/* ── Responsive ── */
@media (max-width: 640px) {
  .hero { padding: 3.5rem 0 1rem; }
  .hero h1 { font-size: 2rem; }
  .hero-mono { font-size: 2.4rem; top: 1.2rem; }
  .hero-sub { font-size: 0.9rem; }
  .track-card { padding: 1.25rem 1.25rem 1.25rem 1.15rem; }
  .track-card .track-num { font-size: 2.2rem; }
  .latest-course {
    flex-direction: column; align-items: stretch;
  }
  .btn { justify-content: center; }
  .archive-list li { flex-wrap: wrap; gap: 0.25rem; }
  .archive-date { min-width: auto; }
  .track-header { flex-wrap: wrap; }
}
"""

SCHEDULE_TAG_MAP = {
    "daily":       ("Daily", "tag-daily"),
    "mon,wed,fri": ("Mon · Wed · Fri", "tag-mwf"),
    "tue,thu":     ("Tue · Thu", "tag-tt"),
}

TRACK_META = {
    "general": {
        "icon_char":   "&#9671;",    # diamond outline
        "card_class":  "color-green",
        "num":         "01",
        "desc": "LLMs, research papers &amp; coding advances",
    },
    "image-gen": {
        "icon_char":   "&#9633;",    # square outline
        "card_class":  "color-blue",
        "num":         "02",
        "desc": "Diffusion models, video AI &amp; vision",
    },
    "audio": {
        "icon_char":   "&#9835;",    # music note
        "card_class":  "color-violet",
        "num":         "03",
        "desc": "TTS, speech synthesis &amp; music generation",
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

        icon_char   = meta.get("icon_char", "&#9671;")
        card_class  = meta.get("card_class", "")
        track_num   = meta.get("num", "00")
        desc        = meta.get("desc", "")

        if entries:
            latest = entries[0]
            latest_date_display = _format_date_display(latest['date'])
            latest_html = f"""
        <div class="latest-course">
          <div class="latest-info">
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
        <div class="track-card {card_class}">
          <span class="track-num">{track_num}</span>
          <div class="track-header">
            <div class="track-icon">{icon_char}</div>
            <div class="track-meta">
              <div class="track-title">{_html_escape(label)}</div>
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
  <div class="page-dots"></div>
  <div class="container">
    <div class="hero">
      <div class="hero-mono">AI</div>
      <div class="hero-badge">Synthesized daily</div>
      <h1>AI Daily<br><em>Courses</em></h1>
      <p class="hero-sub">Hands-on Jupyter Notebook courses built from the latest AI research &amp; news. Deep dives into models, architectures, and code.</p>
      <hr class="hero-rule">
    </div>
    <div class="section-label">{total_courses} Course{"s" if total_courses != 1 else ""} &middot; {len(TRACK_ORDER)} Tracks</div>
    <div class="tracks">
    {cards_html}
    </div>
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
