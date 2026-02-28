#!/usr/bin/env python3
"""
generate_course.py — Call Claude CLI to generate a course, then build a Jupyter Notebook.

Uses a multi-call strategy:
  1. Planning call: pick topics from articles (fast, small response)
  2. Per-topic calls: generate one section at a time (parallel-safe, medium response)
  3. Stitch all sections into one notebook

Usage:
    python3 generate_course.py <track_name> <articles_json_path>
    python3 generate_course.py general /tmp/ai_course_articles_general_2026-02-28.json

Saves notebook to ~/ai-courses/{track}/YYYY-MM-DD.ipynb.
"""

import re
import sys
import json
import time
import shutil
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

# Per-call timeout (each call is smaller now, but give Opus room)
CALL_TIMEOUT = min(CLAUDE_TIMEOUT, 600)


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


# ── Claude CLI call ────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_prompt: str, label: str = "",
                timeout: int | None = None) -> str | None:
    """
    Call `claude -p` via subprocess. Returns raw stdout string, or None on failure.
    `label` is for logging only.
    """
    timeout = timeout or CALL_TIMEOUT

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(user_prompt)
        tmp_path = tmp.name

    claude_path = shutil.which("claude")
    log.info("[%s] Calling Claude (model=%s, timeout=%ds, prompt=%d chars, binary=%s)",
             label, CLAUDE_MODEL, timeout, len(user_prompt), claude_path)

    start_time = time.time()

    try:
        with open(tmp_path, "r", encoding="utf-8") as prompt_fh:
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
                timeout=timeout,
            )

        elapsed = time.time() - start_time
        log.info("[%s] Finished in %.1fs (exit code %d)", label, elapsed, result.returncode)

        if result.stderr.strip():
            log.info("[%s] stderr: %s", label, result.stderr[:300])

        if result.returncode != 0:
            log.error("[%s] Exit code %d: %s", label, result.returncode, result.stderr[:500])
            return None

        output = result.stdout.strip()
        log.info("[%s] Response: %d chars — preview: %s...", label, len(output), output[:150])
        return output

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        log.error("[%s] Timed out after %.1fs", label, elapsed)
        return None
    except FileNotFoundError:
        log.error("[%s] 'claude' not found on PATH", label)
        return None
    except Exception as exc:
        log.error("[%s] Unexpected error: %s", label, exc)
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── JSON extraction ───────────────────────────────────────────────────────────

def extract_json_from_response(raw: str) -> dict | list | None:
    """Try to extract JSON from Claude's response."""
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find outermost JSON
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        start = raw.find(open_ch)
        end = raw.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass

    return None


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_articles_context(articles: list[dict]) -> str:
    """Format articles into a text block for prompts."""
    parts = []
    for i, art in enumerate(articles, 1):
        parts.append(f"### Article {i}: {art['title']}")
        parts.append(f"**Source:** {art['source']}  |  **Published:** {art.get('published','unknown')}")
        parts.append(f"**URL:** {art.get('url','')}")
        if art.get("summary"):
            parts.append(f"\n**Summary:**\n{art['summary']}")
        if art.get("body"):
            parts.append(f"\n**Full text (truncated):**\n{art['body']}")
        parts.append("")
    return "\n".join(parts)


PLAN_SYSTEM = """You are an AI course planner. Given a set of articles, you pick the best topics for a hands-on Jupyter Notebook course.

Output ONLY valid JSON. No markdown fences. No prose."""

def build_plan_prompt(track_name: str, articles: list[dict], date_str: str) -> str:
    track = TRACKS[track_name]
    articles_text = build_articles_context(articles)

    return f"""# Course Planning — {track['label']} — {date_str}

**Track focus:** {track['prompt_focus']}

## Today's Articles
{articles_text}
---

Pick 2-3 of the most interesting and technically rich topics from these articles.

Return a JSON object:
{{
  "course_title": "Overall course title (engaging, specific)",
  "topics": [
    {{
      "title": "Topic title",
      "article_refs": [1, 2],
      "key_concepts": ["concept1", "concept2"],
      "description": "One sentence on what the section will cover"
    }}
  ]
}}

Output ONLY valid JSON."""


SECTION_SYSTEM = """You are an expert ML practitioner and educator. You generate ONE section of a hands-on Jupyter Notebook course.

Output ONLY a JSON object with a "cells" array. Each cell has:
  - "type": "code" or "markdown"
  - "source": the full cell content as a string

Keep the section focused and concise. Aim for 5-8 cells total.

Output ONLY valid JSON. No markdown fences. No prose."""

def build_section_prompt(track_name: str, topic: dict, articles: list[dict],
                         date_str: str, section_num: int) -> str:
    track = TRACKS[track_name]

    # Only include referenced articles
    ref_articles = []
    for ref in topic.get("article_refs", []):
        if 1 <= ref <= len(articles):
            ref_articles.append(articles[ref - 1])

    if not ref_articles:
        ref_articles = articles[:2]

    articles_text = build_articles_context(ref_articles)

    return f"""# Section {section_num}: {topic['title']}

**Track:** {track['label']} — {date_str}
**Focus:** {track['prompt_focus']}
**Key concepts:** {', '.join(topic.get('key_concepts', []))}
**Description:** {topic.get('description', '')}

## Reference Articles
{articles_text}
---

Generate this ONE course section with these cells in order:
1. Section header (markdown) — "## Section {section_num}: {{title}}" with a brief intro
2. Hook (code) — exciting runnable demo showing the concept
3. Concept (markdown) — deep explanation with architecture/math details
4. Exercise (code) — skeleton with TODO comments for the learner
5. Solution (code) — fully commented working solution
6. Quiz (markdown) — 2-3 MCQs in HTML <details> tags for self-check

Return ONLY a JSON object: {{"cells": [...]}}
Each cell: {{"type": "code"|"markdown", "source": "..."}}

Be thorough in explanations but keep code focused. Output ONLY valid JSON."""


# ── Notebook builder ──────────────────────────────────────────────────────────

def build_notebook(
    course_title: str,
    section_cells: list[list[dict]],
    track_name: str,
    date_str: str,
    track_label: str,
) -> nbformat.NotebookNode:
    """Stitch overview + section cells into one notebook."""
    nb_cells = []

    # Title cell
    nb_cells.append(new_markdown_cell(
        f"# {course_title}\n\n"
        f"**{track_label}** — {date_str}\n\n"
        f"*Auto-generated hands-on course from the latest AI research.*"
    ))

    # Section cells
    for cells in section_cells:
        for cell_def in cells:
            cell_type = cell_def.get("type", "markdown")
            source = cell_def.get("source", "")
            if cell_type == "code":
                nb_cells.append(new_code_cell(source))
            else:
                nb_cells.append(new_markdown_cell(source))

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

    total_start = time.time()

    # ── Step 1: Plan topics ───────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("STEP 1/2: Planning topics...")
    plan_prompt = build_plan_prompt(track_name, articles, date_str)
    plan_raw = call_claude(PLAN_SYSTEM, plan_prompt, label="plan")

    if plan_raw is None:
        log.error("Planning call failed — fallback")
        nb = build_fallback_notebook(track_name, date_str, "Planning call failed.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    plan = extract_json_from_response(plan_raw)
    if plan is None or "topics" not in plan:
        log.error("Could not parse plan JSON — fallback")
        debug_path = Path("/tmp") / f"claude_plan_{track_name}_{date_str}.txt"
        debug_path.write_text(plan_raw, encoding="utf-8")
        log.error("Raw plan saved to %s", debug_path)
        nb = build_fallback_notebook(track_name, date_str, "Plan JSON parse error.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    course_title = plan.get("course_title", f"{track_label} — {date_str}")
    topics = plan["topics"]
    log.info("Course title: %s", course_title)
    log.info("Topics planned: %d", len(topics))
    for i, t in enumerate(topics, 1):
        log.info("  Topic %d: %s", i, t.get("title", "?"))

    # ── Step 2: Generate each section ─────────────────────────────────────────
    all_section_cells = []
    for i, topic in enumerate(topics, 1):
        log.info("-" * 60)
        log.info("STEP 2/%d: Generating section %d/%d — %s",
                 len(topics), i, len(topics), topic.get("title", "?"))

        section_prompt = build_section_prompt(
            track_name, topic, articles, date_str, i
        )
        section_raw = call_claude(SECTION_SYSTEM, section_prompt,
                                  label=f"section-{i}")

        if section_raw is None:
            log.warning("Section %d failed — skipping", i)
            continue

        section_json = extract_json_from_response(section_raw)
        if section_json is None:
            log.warning("Section %d JSON parse failed — skipping", i)
            debug_path = Path("/tmp") / f"claude_section{i}_{track_name}_{date_str}.txt"
            debug_path.write_text(section_raw, encoding="utf-8")
            log.warning("Raw section saved to %s", debug_path)
            continue

        cells = section_json.get("cells", section_json if isinstance(section_json, list) else [])
        if not cells:
            log.warning("Section %d returned empty cells — skipping", i)
            continue

        log.info("Section %d: got %d cells", i, len(cells))
        all_section_cells.append(cells)

    total_elapsed = time.time() - total_start
    log.info("=" * 60)
    log.info("All calls complete in %.1fs — got %d/%d sections",
             total_elapsed, len(all_section_cells), len(topics))

    if not all_section_cells:
        log.error("No sections generated — fallback")
        nb = build_fallback_notebook(track_name, date_str, "All section calls failed.")
        nbformat.write(nb, str(out_path))
        print(str(out_path))
        return 1

    # ── Stitch notebook ───────────────────────────────────────────────────────
    nb = build_notebook(course_title, all_section_cells, track_name, date_str, track_label)

    try:
        nbformat.validate(nb)
        log.info("Notebook validation passed")
    except nbformat.ValidationError as exc:
        log.warning("Notebook validation warning: %s", exc)

    nbformat.write(nb, str(out_path))
    log.info("Notebook saved to %s (%d cells)", out_path, len(nb.cells))

    title = extract_title(nb, track_label, date_str)
    log.info("Course title: %s", title)

    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
