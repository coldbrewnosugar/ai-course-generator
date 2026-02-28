#!/usr/bin/env python3
"""
generate_course.py — Call Claude CLI to generate a course, then build a Jupyter Notebook.

Usage:
    python3 generate_course.py <track_name> <articles_json_path>
    python3 generate_course.py general /tmp/ai_course_articles_general_2026-02-28.json

Saves notebook to ~/ai-courses/{track}/YYYY-MM-DD.ipynb.
"""

import re
import sys
import json
import time
import logging
import argparse
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    TRACKS, SYSTEM_PROMPTS, OUTPUT_DIR, LOG_DIR,
    CLAUDE_MODEL, CLAUDE_TIMEOUT
)

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


# ── Fallback notebook ──────────────────────────────────────────────────────────

def build_fallback_notebook(track_name: str, date_str: str, reason: str) -> nbformat.NotebookNode:
    """Return a minimal notebook when content generation fails."""
    track_label = TRACKS[track_name]["label"]
    cells = [
        new_markdown_cell(f"# {track_label} — {date_str}\n\n"
                          f"> **Note:** Today's course could not be fully generated.\n\n"
                          f"**Reason:** {reason}\n\n"
                          "Please check back tomorrow or run the pipeline manually."),
        new_code_cell("# Placeholder — no articles were available today\nprint('No content today.')"),
    ]
    nb = new_notebook(cells=cells)
    nb.metadata["course_track"] = track_name
    nb.metadata["course_date"]  = date_str
    nb.metadata["kernelspec"]   = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python", "version": "3.13.5"}
    return nb


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_user_prompt(track_name: str, articles: list[dict], date_str: str) -> str:
    track   = TRACKS[track_name]
    label   = track["label"]
    focus   = track["prompt_focus"]

    parts = [
        f"# Daily AI Course — {label} — {date_str}",
        "",
        f"**Track focus:** {focus}",
        "",
        f"## Today's Articles ({len(articles)} items)",
        "",
    ]

    for i, art in enumerate(articles, 1):
        parts.append(f"### Article {i}: {art['title']}")
        parts.append(f"**Source:** {art['source']}  |  **Published:** {art.get('published','unknown')}")
        parts.append(f"**URL:** {art.get('url','')}")
        if art.get("summary"):
            parts.append(f"\n**Summary:**\n{art['summary']}")
        if art.get("body"):
            parts.append(f"\n**Full text (truncated):**\n{art['body']}")
        parts.append("")

    parts += [
        "---",
        "",
        "## Instructions",
        "",
        "Based on the articles above, design a comprehensive ~2-hour hands-on Jupyter Notebook course.",
        "Choose 3–4 of the most interesting and technically rich topics from these articles.",
        "",
        "Return ONLY a JSON object with a 'cells' array. Each cell object must have:",
        "  - 'type': 'code' or 'markdown'",
        "  - 'source': the full cell content as a string",
        "  - 'metadata': {'cell_role': one of 'hook'|'concept'|'exercise'|'solution'|'synthesis'|'quiz'|'further_reading'}",
        "",
        "Start with a title/overview markdown cell (role: 'concept').",
        "Then for each topic section, follow this sequence:",
        "  1. hook (code) — exciting demo that runs and shows the concept",
        "  2. concept (markdown) — deep explanation with math/architecture details",
        "  3. exercise (code) — skeleton with TODO comments",
        "  4. solution (code) — fully commented working solution",
        "  5. synthesis (markdown) — connects to broader landscape",
        "  6. quiz (markdown) — 3 MCQs in HTML <details> tags",
        "  7. further_reading (markdown) — 3–5 links",
        "",
        "Output ONLY valid JSON. No markdown fences. No prose before or after the JSON.",
        "The JSON must be directly parseable by Python's json.loads().",
    ]

    return "\n".join(parts)


# ── Claude CLI call ────────────────────────────────────────────────────────────

def call_claude(track_name: str, prompt_text: str) -> str | None:
    """
    Call `claude -p --model opus` via subprocess.
    Returns raw stdout string, or None on failure.
    """
    system_prompt = SYSTEM_PROMPTS[track_name]

    # Write prompt to temp file (avoids shell quoting issues with large inputs)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(prompt_text)
        tmp_path = tmp.name

    log.info("Calling Claude CLI (model=%s, prompt_file=%s, timeout=%ds)",
             CLAUDE_MODEL, tmp_path, CLAUDE_TIMEOUT)
    log.info("System prompt length: %d chars", len(system_prompt))

    import shutil
    claude_path = shutil.which("claude")
    log.info("Claude binary: %s", claude_path)

    start_time = time.time()

    try:
        with open(tmp_path, "r", encoding="utf-8") as prompt_fh:
            log.info("Starting subprocess...")
            result = subprocess.run(
                [
                    "claude", "-p",
                    "--model", CLAUDE_MODEL,
                    "--system-prompt", system_prompt,
                    "--output-format", "text",
                ],
                stdin=prompt_fh,
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT,
            )

        elapsed = time.time() - start_time
        log.info("Claude CLI finished in %.1fs (exit code %d)", elapsed, result.returncode)

        if result.stderr.strip():
            log.info("Claude stderr: %s", result.stderr[:500])

        if result.returncode != 0:
            log.error("Claude CLI exited with code %d: %s",
                      result.returncode, result.stderr[:500])
            return None

        output = result.stdout.strip()
        log.info("Claude returned %d characters", len(output))
        if output:
            log.info("Response preview: %s...", output[:200])
        return output

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        log.error("Claude CLI timed out after %.1fs (limit=%ds)", elapsed, CLAUDE_TIMEOUT)
        return None
    except FileNotFoundError:
        log.error("'claude' command not found — is Claude CLI installed and on PATH?")
        return None
    except Exception as exc:
        log.error("Unexpected error calling Claude CLI: %s", exc)
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── JSON → Notebook ────────────────────────────────────────────────────────────

def extract_json_from_response(raw: str) -> dict | None:
    """
    Try to extract a JSON object from Claude's response.
    Handles cases where Claude wraps JSON in markdown code fences.
    """
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find the outermost JSON object
    brace_start = raw.find("{")
    brace_end   = raw.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(raw[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def build_notebook_from_json(
    cells_data: list[dict],
    track_name: str,
    date_str: str,
    track_label: str,
) -> nbformat.NotebookNode:
    """Convert the JSON cells list into an nbformat notebook."""
    nb_cells = []

    for cell_def in cells_data:
        cell_type = cell_def.get("type", "markdown")
        source    = cell_def.get("source", "")
        role      = cell_def.get("metadata", {}).get("cell_role", "concept")

        if cell_type == "code":
            cell = new_code_cell(source)
        else:
            cell = new_markdown_cell(source)

        cell.metadata["cell_role"] = role
        nb_cells.append(cell)

    nb = new_notebook(cells=nb_cells)
    nb.metadata["course_track"] = track_name
    nb.metadata["course_date"]  = date_str
    nb.metadata["course_label"] = track_label
    nb.metadata["kernelspec"]   = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {
        "name": "python",
        "version": "3.13.5",
        "mimetype": "text/x-python",
        "codemirror_mode": {"name": "ipython", "version": 3},
    }
    return nb


# ── Extract course title from notebook ────────────────────────────────────────

def extract_title(nb: nbformat.NotebookNode, track_label: str, date_str: str) -> str:
    """Pull first H1 from first markdown cell, or generate a default."""
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            match = re.search(r"^#\s+(.+)$", cell.source, re.MULTILINE)
            if match:
                return match.group(1).strip()
    return f"{track_label} — {date_str}"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Jupyter Notebook AI course using Claude CLI."
    )
    parser.add_argument("track",         choices=list(TRACKS.keys()),
                        help="Track name")
    parser.add_argument("articles_json", help="Path to articles JSON from fetch_feeds.py")
    args = parser.parse_args()

    track_name   = args.track
    articles_path = Path(args.articles_json)
    track_label  = TRACKS[track_name]["label"]

    # Load articles
    if not articles_path.exists():
        log.error("Articles file not found: %s", articles_path)
        sys.exit(1)

    with open(articles_path, encoding="utf-8") as fh:
        payload = json.load(fh)

    articles  = payload.get("articles", [])
    date_str  = payload.get("date", datetime.now().strftime("%Y-%m-%d"))

    log.info("Loaded %d articles for track '%s' (date=%s)",
             len(articles), track_name, date_str)

    # Output path
    out_dir = Path(OUTPUT_DIR) / track_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.ipynb"

    # Fallback if no articles
    if len(articles) == 0:
        log.warning("No articles found — generating fallback notebook")
        nb = build_fallback_notebook(track_name, date_str, "No recent articles found in RSS feeds.")
        nbformat.write(nb, str(out_path))
        log.info("Fallback notebook saved to %s", out_path)
        print(str(out_path))
        return 0

    # Build prompt
    prompt_text = build_user_prompt(track_name, articles, date_str)
    log.info("User prompt: %d characters", len(prompt_text))

    # Call Claude
    raw_response = call_claude(track_name, prompt_text)

    if raw_response is None:
        log.error("Claude CLI call failed — generating fallback notebook")
        nb = build_fallback_notebook(track_name, date_str, "Claude CLI call failed.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    # Parse JSON response
    course_json = extract_json_from_response(raw_response)

    if course_json is None:
        log.error("Could not parse JSON from Claude response — fallback notebook")
        # Save raw response for debugging
        debug_path = Path("/tmp") / f"claude_raw_{track_name}_{date_str}.txt"
        debug_path.write_text(raw_response, encoding="utf-8")
        log.error("Raw response saved to %s", debug_path)
        nb = build_fallback_notebook(track_name, date_str,
                                     "JSON parse error — see /tmp debug file.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    cells_data = course_json.get("cells", [])
    if not cells_data:
        log.error("No cells in JSON response — fallback notebook")
        nb = build_fallback_notebook(track_name, date_str, "Claude returned empty cells array.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    log.info("Parsed %d cells from Claude response", len(cells_data))

    # Build notebook
    nb = build_notebook_from_json(cells_data, track_name, date_str, track_label)

    # Validate
    try:
        nbformat.validate(nb)
        log.info("Notebook validation passed")
    except nbformat.ValidationError as exc:
        log.warning("Notebook validation warning: %s", exc)

    # Save
    nbformat.write(nb, str(out_path))
    log.info("Notebook saved to %s (%d cells)", out_path, len(nb.cells))

    title = extract_title(nb, track_label, date_str)
    log.info("Course title: %s", title)

    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
