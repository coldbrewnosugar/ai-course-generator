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

INDEX_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');
:root {
  --bg: #ffffff;
  --ink: #0a0a0a;
  --ink-secondary: #333;
  --muted: #888;
  --red: #E63226;
  --blue: #1B3F8B;
  --yellow: #F5B731;
  --mono: 'Space Mono', monospace;
  --sans: 'DM Sans', system-ui, sans-serif;
  --border: 2px solid var(--ink);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* ── Header ── */
.header {
  display: flex;
  align-items: stretch;
  border-bottom: 3px solid var(--ink);
  margin-top: 2rem;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem 1.5rem 1.5rem 0;
  border-right: 3px solid var(--ink);
  flex-shrink: 0;
}
.header-mark {
  width: 48px; height: 48px;
  background: var(--red);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.header-mark span {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 1.1rem;
  color: #fff;
}
.header-text h1 {
  font-family: var(--mono);
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.header-text .tagline {
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 0.2rem;
  font-weight: 400;
}
.header-shapes {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 0 1.5rem;
}
.geo-circle {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: var(--red);
}
.geo-square {
  width: 22px; height: 22px;
  background: var(--blue);
}
.geo-triangle {
  width: 0; height: 0;
  border-left: 13px solid transparent;
  border-right: 13px solid transparent;
  border-bottom: 24px solid var(--yellow);
}

/* ── Week navigation ── */
.week-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 1rem 0;
  border-bottom: var(--border);
}
.week-nav button {
  font-family: var(--mono);
  font-size: 1.2rem;
  font-weight: 700;
  background: var(--ink);
  color: #fff;
  border: none;
  width: 40px; height: 40px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s;
}
.week-nav button:hover { background: var(--red); }
.week-nav .week-label {
  font-family: var(--mono);
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  min-width: 240px;
  text-align: center;
}
.week-nav .today-btn {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: none;
  color: var(--muted);
  border: 1px solid var(--muted);
  width: auto;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
}
.week-nav .today-btn:hover {
  color: var(--ink);
  border-color: var(--ink);
  background: none;
}

/* ── Calendar grid ── */
.week-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border-left: var(--border);
  border-bottom: var(--border);
}
.day-col {
  border-right: var(--border);
  min-height: 160px;
  display: flex;
  flex-direction: column;
}
.day-header {
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: center;
  padding: 0.6rem 0.4rem 0.15rem;
  color: var(--muted);
  border-bottom: 1px solid #ddd;
}
.day-num {
  font-family: var(--mono);
  font-size: 1.4rem;
  font-weight: 700;
  text-align: center;
  padding: 0.3rem 0 0.5rem;
  color: var(--ink);
}
.day-col.is-today .day-num {
  background: var(--ink);
  color: #fff;
}
.day-col.is-today {
  box-shadow: inset 0 0 0 3px var(--red);
}
.day-col.empty-day {
  background: #fafafa;
}
.day-courses {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
}
.course-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  text-decoration: none;
  font-size: 0.68rem;
  font-weight: 500;
  color: var(--ink);
  border: 1px solid #ddd;
  transition: all 0.15s;
  line-height: 1.25;
  word-break: break-word;
}
.course-pill:hover {
  border-color: var(--ink);
  background: #f5f5f5;
}
.course-pill .pill-shape {
  flex-shrink: 0;
  font-size: 0.85rem;
  line-height: 1;
}
.course-pill.track-general  { border-left: 3px solid var(--red); }
.course-pill.track-image-gen { border-left: 3px solid var(--blue); }
.course-pill.track-audio    { border-left: 3px solid var(--yellow); }
.course-pill.track-general:hover  { background: rgba(230,50,38,0.06); }
.course-pill.track-image-gen:hover { background: rgba(27,63,139,0.06); }
.course-pill.track-audio:hover    { background: rgba(245,183,49,0.06); }

/* ── Legend ── */
.legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  padding: 1.25rem 0;
  border-bottom: var(--border);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.legend-shape {
  font-size: 1rem;
  line-height: 1;
}
.legend-item.track-general  .legend-shape { color: var(--red); }
.legend-item.track-image-gen .legend-shape { color: var(--blue); }
.legend-item.track-audio    .legend-shape { color: var(--yellow); }
.legend-swatch {
  display: inline-block;
  width: 12px; height: 12px;
}
.legend-item.track-general  .legend-swatch { background: var(--red); }
.legend-item.track-image-gen .legend-swatch { background: var(--blue); }
.legend-item.track-audio    .legend-swatch { background: var(--yellow); }

/* ── Stats bar ── */
.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  padding: 0.75rem 0;
  font-family: var(--mono);
  font-size: 0.65rem;
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.stats-bar strong {
  color: var(--ink);
}

/* ── Footer ── */
footer {
  text-align: center;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 3rem;
  padding: 1.5rem 0 2.5rem;
  border-top: 3px solid var(--ink);
}
footer span { color: var(--ink); font-weight: 700; }

/* ── Responsive ── */
@media (max-width: 700px) {
  .header { flex-direction: column; }
  .header-brand { border-right: none; border-bottom: 3px solid var(--ink); padding: 1rem; }
  .header-shapes { padding: 0.75rem 1rem; justify-content: flex-start; }
  .week-grid {
    grid-template-columns: repeat(7, minmax(80px, 1fr));
    overflow-x: auto;
  }
  .day-col { min-height: 120px; }
  .legend { flex-wrap: wrap; gap: 1rem; }
  .week-nav .week-label { min-width: auto; font-size: 0.75rem; }
}
@media (max-width: 480px) {
  .header-text h1 { font-size: 1.2rem; }
  .week-grid {
    grid-template-columns: repeat(7, minmax(65px, 1fr));
  }
}
"""

TRACK_META = {
    "general": {
        "color": "#E63226",
        "shape": "\u25cf",
        "label_short": "GEN",
        "css_class": "track-general",
        "desc": "LLMs, research papers &amp; coding advances",
    },
    "image-gen": {
        "color": "#1B3F8B",
        "shape": "\u25a0",
        "label_short": "IMG",
        "css_class": "track-image-gen",
        "desc": "Diffusion models, video AI &amp; vision",
    },
    "audio": {
        "color": "#F5B731",
        "shape": "\u25b2",
        "label_short": "AUD",
        "css_class": "track-audio",
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
    Scan site_dir for all HTML course files, build a weekly calendar index.
    Returns the index path.
    """
    # Collect all course HTML files: {date_str: {track: {title, url}}}
    courses: dict[str, list[dict]] = {t: [] for t in TRACK_ORDER}
    all_dates: dict[str, dict] = {}  # date -> track -> {title, rel_path}

    for track_name in TRACK_ORDER:
        track_dir = site_dir / track_name
        if not track_dir.is_dir():
            continue
        for html_file in sorted(track_dir.glob("????-??-??.html"), reverse=True):
            date_str = html_file.stem
            title    = get_course_title(track_name, date_str)
            rel_path = f"{track_name}/{html_file.name}"
            courses[track_name].append({
                "date": date_str, "title": title, "rel_path": rel_path,
            })
            if date_str not in all_dates:
                all_dates[date_str] = {}
            all_dates[date_str][track_name] = {
                "title": title, "url": rel_path,
            }

    total_courses = sum(len(v) for v in courses.values())

    # Build JSON blob for client-side navigation
    courses_json = json.dumps(all_dates, separators=(",", ":"))

    # Determine the current week (Mon–Sun containing today)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    weekday_idx = today.weekday()  # 0=Mon
    week_start = today - __import__("datetime").timedelta(days=weekday_idx)

    # Pre-render the initial week server-side
    day_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    initial_week_html = ""
    week_start_str = week_start.strftime("%Y-%m-%d")

    for i in range(7):
        day = week_start + __import__("datetime").timedelta(days=i)
        d_str = day.strftime("%Y-%m-%d")
        day_num = day.day
        is_today = (d_str == today_str)
        day_data = all_dates.get(d_str, {})
        has_courses = len(day_data) > 0

        today_cls = " is-today" if is_today else ""
        empty_cls = " empty-day" if not has_courses else ""

        pills_html = ""
        for track_name in TRACK_ORDER:
            if track_name in day_data:
                meta = TRACK_META[track_name]
                entry = day_data[track_name]
                title_esc = _html_escape(entry["title"])
                pills_html += (
                    f'<a href="{entry["url"]}" class="course-pill {meta["css_class"]}" title="{title_esc}">'
                    f'<span class="pill-shape">{meta["shape"]}</span>'
                    f'{title_esc}</a>'
                )

        initial_week_html += f"""
      <div class="day-col{today_cls}{empty_cls}">
        <div class="day-header">{day_names[i]}</div>
        <div class="day-num">{day_num}</div>
        <div class="day-courses">{pills_html}</div>
      </div>"""

    # Week label
    week_end = week_start + __import__("datetime").timedelta(days=6)
    if week_start.month == week_end.month:
        week_label = f"{week_start.strftime('%b')} {week_start.day} – {week_end.day}, {week_end.year}"
    else:
        week_label = f"{week_start.strftime('%b')} {week_start.day} – {week_end.strftime('%b')} {week_end.day}, {week_end.year}"

    # Legend
    legend_html = ""
    for track_name in TRACK_ORDER:
        meta = TRACK_META[track_name]
        label = TRACKS.get(track_name, {}).get("label", track_name)
        schedule = TRACKS.get(track_name, {}).get("schedule", "")
        sched_display = {"daily": "Daily", "mon,wed,fri": "M/W/F", "tue,thu": "T/Th"}.get(schedule, schedule)
        legend_html += (
            f'<div class="legend-item {meta["css_class"]}">'
            f'<span class="legend-swatch"></span>'
            f'<span class="legend-shape">{meta["shape"]}</span>'
            f'{_html_escape(label)}'
            f'<span style="color:var(--muted);font-size:0.6rem">({sched_display})</span>'
            f'</div>'
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Inline JS for week navigation
    inline_js = r"""
const COURSES = __COURSES_JSON__;
const TRACK_ORDER = __TRACK_ORDER__;
const TRACK_META = __TRACK_META_JS__;
const DAY_NAMES = ["MON","TUE","WED","THU","FRI","SAT","SUN"];
const TODAY = "__TODAY__";

let refDate = new Date("__WEEK_START__" + "T00:00:00");

function fmt(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,"0");
  const day = String(d.getDate()).padStart(2,"0");
  return y+"-"+m+"-"+day;
}

function getWeekDates(start) {
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    dates.push(d);
  }
  return dates;
}

function renderWeek() {
  const dates = getWeekDates(refDate);
  const grid = document.getElementById("week-grid");
  const end = dates[6];
  const startM = dates[0].toLocaleDateString("en",{month:"short"});
  const endM = end.toLocaleDateString("en",{month:"short"});
  let label;
  if (dates[0].getMonth() === end.getMonth()) {
    label = startM+" "+dates[0].getDate()+" – "+end.getDate()+", "+end.getFullYear();
  } else {
    label = startM+" "+dates[0].getDate()+" – "+endM+" "+end.getDate()+", "+end.getFullYear();
  }
  document.getElementById("week-label").textContent = label;

  let html = "";
  dates.forEach((d, i) => {
    const ds = fmt(d);
    const isToday = ds === TODAY;
    const dayData = COURSES[ds] || {};
    const hasCourses = Object.keys(dayData).length > 0;
    const todayCls = isToday ? " is-today" : "";
    const emptyCls = !hasCourses ? " empty-day" : "";

    let pills = "";
    TRACK_ORDER.forEach(t => {
      if (dayData[t]) {
        const m = TRACK_META[t];
        const title = dayData[t].title.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
        pills += '<a href="'+dayData[t].url+'" class="course-pill '+m.css+'" title="'+title+'">' +
          '<span class="pill-shape">'+m.shape+'</span>'+title+'</a>';
      }
    });

    html += '<div class="day-col'+todayCls+emptyCls+'">' +
      '<div class="day-header">'+DAY_NAMES[i]+'</div>' +
      '<div class="day-num">'+d.getDate()+'</div>' +
      '<div class="day-courses">'+pills+'</div></div>';
  });
  grid.innerHTML = html;
}

function navigate(offset) {
  refDate.setDate(refDate.getDate() + offset * 7);
  renderWeek();
}

function goToday() {
  const t = new Date(TODAY + "T00:00:00");
  const wd = t.getDay() === 0 ? 6 : t.getDay() - 1;
  refDate = new Date(t);
  refDate.setDate(refDate.getDate() - wd);
  renderWeek();
}

document.getElementById("prev-week").addEventListener("click", () => navigate(-1));
document.getElementById("next-week").addEventListener("click", () => navigate(1));
document.getElementById("today-btn").addEventListener("click", goToday);
"""

    # Build JS track meta for client-side
    track_meta_js = "{"
    for i, t in enumerate(TRACK_ORDER):
        m = TRACK_META[t]
        track_meta_js += f'"{t}":{{"shape":"{m["shape"]}","css":"{m["css_class"]}"}}'
        if i < len(TRACK_ORDER) - 1:
            track_meta_js += ","
    track_meta_js += "}"

    track_order_js = json.dumps(TRACK_ORDER)

    final_js = (inline_js
        .replace("__COURSES_JSON__", courses_json)
        .replace("__TRACK_ORDER__", track_order_js)
        .replace("__TRACK_META_JS__", track_meta_js)
        .replace("__TODAY__", today_str)
        .replace("__WEEK_START__", week_start_str))

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
  <div class="container">

    <div class="header">
      <div class="header-brand">
        <div class="header-mark"><span>AI</span></div>
        <div class="header-text">
          <h1>Daily Courses</h1>
          <div class="tagline">Synthesized from the latest AI research</div>
        </div>
      </div>
      <div class="header-shapes">
        <div class="geo-circle"></div>
        <div class="geo-square"></div>
        <div class="geo-triangle"></div>
      </div>
    </div>

    <div class="week-nav">
      <button id="prev-week" aria-label="Previous week">&#9664;</button>
      <div id="week-label" class="week-label">{week_label}</div>
      <button id="next-week" aria-label="Next week">&#9654;</button>
      <button id="today-btn" class="today-btn">Today</button>
    </div>

    <div class="week-grid" id="week-grid">{initial_week_html}
    </div>

    <div class="legend">{legend_html}</div>

    <div class="stats-bar">
      <div><strong>{total_courses}</strong> course{"s" if total_courses != 1 else ""}</div>
      <div><strong>{len(TRACK_ORDER)}</strong> tracks</div>
      <div>Updated <strong>{now_str}</strong></div>
    </div>

    <footer>
      <span>AI Daily Courses</span> &middot; Auto-generated
    </footer>

  </div>
  <script>
{final_js}
  </script>
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
