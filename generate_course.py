#!/usr/bin/env python3
"""
generate_course.py — Call Claude CLI to generate a workshop session JSON.

Uses a two-call strategy:
  1. Planning call: pick ONE buildable topic from articles
  2. Session call: generate the full interactive session JSON

Usage:
    python3 generate_course.py <track_name> <articles_json_path>
    python3 generate_course.py general /tmp/ai_course_articles_general_2026-02-28.json

Saves session to ~/ai-courses/{track}/YYYY-MM-DD.json.
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

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    TRACKS, PLAN_SYSTEM_PROMPT, SESSION_SYSTEM_PROMPT, OUTPUT_DIR, LOG_DIR,
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

# Per-call timeout (give Opus room)
CALL_TIMEOUT = CLAUDE_TIMEOUT


# ── Fallback session ──────────────────────────────────────────────────────────

def build_fallback_session(track_name: str, date_str: str, reason: str) -> dict:
    """Return a minimal valid session when content generation fails."""
    track_label = TRACKS[track_name]["label"]
    return {
        "session_title": f"{track_label} — {date_str}",
        "session_subtitle": "Today's session could not be generated",
        "estimated_minutes": 5,
        "tags": [],
        "sections": [
            {
                "type": "hero",
                "title": f"{track_label} — {date_str}",
                "subtitle": "Session unavailable"
            },
            {
                "type": "context",
                "body": f"**Note:** Today's session could not be fully generated.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"Please check back tomorrow or run the pipeline manually."
            },
            {
                "type": "recap",
                "body": "No content was available today.",
                "takeaways": ["Check back tomorrow for fresh content"],
                "next_steps": ["Try running the pipeline manually"]
            }
        ],
        "sources": []
    }


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


def build_plan_prompt(track_name: str, articles: list[dict], date_str: str) -> str:
    track = TRACKS[track_name]
    articles_text = build_articles_context(articles)

    return f"""# Workshop Planning — {track['label']} — {date_str}

**Track focus:** {track['prompt_focus']}

## Today's Articles
{articles_text}
---

Pick the ONE most interesting, buildable topic from these articles. Something someone could actually sit down and hack on.

Return a JSON object:
{{
  "topic_title": "What we're building (specific and exciting)",
  "subtitle": "One line — what you'll walk away with",
  "article_refs": [1, 2],
  "tags": ["tag1", "tag2"],
  "key_concepts": ["concept1", "concept2"],
  "estimated_minutes": 35,
  "description": "2-3 sentences on what the session will cover and what we'll build"
}}

Output ONLY valid JSON."""


def build_session_prompt(track_name: str, plan: dict, articles: list[dict],
                         date_str: str) -> str:
    track = TRACKS[track_name]

    # Only include referenced articles
    ref_articles = []
    for ref in plan.get("article_refs", []):
        if 1 <= ref <= len(articles):
            ref_articles.append(articles[ref - 1])
    if not ref_articles:
        ref_articles = articles[:3]

    articles_text = build_articles_context(ref_articles)

    # Build sources list for the prompt
    sources_hint = []
    for art in ref_articles:
        sources_hint.append(f'  {{"title": "{art["title"]}", "url": "{art.get("url", "")}", "source_name": "{art["source"]}"}}')
    sources_json = ",\n".join(sources_hint)

    return f"""# Workshop Session — {track['label']} — {date_str}

**Topic:** {plan.get('topic_title', 'TBD')}
**Subtitle:** {plan.get('subtitle', '')}
**Key concepts:** {', '.join(plan.get('key_concepts', []))}
**Description:** {plan.get('description', '')}
**Estimated time:** {plan.get('estimated_minutes', 35)} minutes

## Reference Articles
{articles_text}
---

Generate a complete interactive workshop session as JSON. The session should feel like a study buddy walking someone through building something cool — using AI agents as the tool, not writing code by hand.

AGENT-FIRST APPROACH:
- The user never writes code from scratch. They prompt an AI agent (Claude, ChatGPT, etc.) to build things for them.
- Each step gives a GOAL ("get the agent to build X") and HINTS (guiding questions that help the user think about what to ask for)
- Hints should provoke thinking, not give answers: "What format should the output be in?" not "Tell it to output JSON"
- After the hints, show EXPECTED OUTPUT — what a good agent response looks like, so they can compare
- "your_turn" sections are prompting challenges — give a new goal and thinking hints, hide a sample prompt behind a reveal

Use this EXACT structure:

{{
  "session_title": "{plan.get('topic_title', 'Workshop Session')}",
  "session_subtitle": "{plan.get('subtitle', '')}",
  "estimated_minutes": {plan.get('estimated_minutes', 35)},
  "tags": {json.dumps(plan.get('tags', []))},
  "sections": [
    {{"type": "hero", "title": "...", "subtitle": "..."}},
    {{"type": "context", "body": "markdown — what happened in the news and why we care"}},
    {{"type": "step", "step_number": 1, "title": "...", "body": "markdown explanation",
     "agent_interactions": [{{
       "goal": "What we want the agent to build for us",
       "hints": ["Guiding question 1?", "What about X?", "Think about Y..."],
       "expected_output": {{"language": "python", "code": "what the agent would give back", "caption": "What you should get"}}
     }}],
     "callouts": [{{"style": "tip", "text": "..."}}],
     "reveals": [{{"label": "Why does this matter?", "body": "deeper explanation"}}]}},
    ... more steps (aim for 3-5 steps) ...,
    {{"type": "checkpoint", "message": "You should have X working by now"}},
    {{"type": "decision_point", "question": "Which approach should we use?",
     "options": [{{"label": "Option A", "correct": true, "explanation": "why"}},
                 {{"label": "Option B", "correct": false, "explanation": "why not"}}]}},
    {{"type": "your_turn", "goal": "Now get your agent to do Y — a new challenge",
     "context": "Brief setup for why this task matters",
     "hints": ["What does the agent need to know?", "How should you describe the output format?"],
     "sample_prompt": "A full example prompt the user could have written (hidden behind a reveal)"}},
    {{"type": "recap", "body": "what we built and why it matters",
     "takeaways": ["key insight 1", "key insight 2", "key insight 3"],
     "next_steps": ["what to explore next 1", "what to explore next 2"]}}
  ],
  "sources": [
{sources_json}
  ]
}}

Section type rules:
- MUST start with "hero" and end with "recap"
- Include at least 3 "step" sections — these are the meat of the workshop
- Include at least 1 "checkpoint" between steps
- Include at least 1 "decision_point" to test understanding
- Include at least 1 "your_turn" for hands-on prompting practice
- "context" goes right after "hero" — sets the scene from the news
- Steps should build on each other — each one gets us closer to the finished thing
- agent_interactions, callouts, and reveals within steps are all optional arrays (can be empty)
- The expected_output in agent_interactions is what the AI agent would produce — it's reference output, not something the user types
- Hints should be 2-4 guiding questions that make the user think about their prompt BEFORE seeing the expected output

Callout styles: "tip" (blue), "warning" (red), "api-key-note" (yellow)

Output ONLY valid JSON. Make it substantial — this is a real workshop, not a summary."""


# ── Session validation ────────────────────────────────────────────────────────

def validate_session(session: dict) -> list[str]:
    """Check session JSON has required structure. Returns list of issues."""
    issues = []

    if "session_title" not in session:
        issues.append("Missing session_title")
    if "sections" not in session or not isinstance(session.get("sections"), list):
        issues.append("Missing or invalid sections array")
        return issues

    sections = session["sections"]
    if len(sections) == 0:
        issues.append("Empty sections array")
        return issues

    types = [s.get("type") for s in sections]

    if types[0] != "hero":
        issues.append("First section must be 'hero'")
    if types[-1] != "recap":
        issues.append("Last section must be 'recap'")
    if "step" not in types:
        issues.append("Must have at least one 'step' section")

    return issues


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a workshop session JSON using Claude CLI."
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
    out_path = out_dir / f"{date_str}.json"

    # Fallback if no articles
    if len(articles) == 0:
        log.warning("No articles found — generating fallback session")
        session = build_fallback_session(track_name, date_str,
                                         "No recent articles found in RSS feeds.")
        out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        log.info("Fallback session saved to %s", out_path)
        print(str(out_path))
        return 0

    total_start = time.time()

    # ── Step 1: Plan topic ───────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("STEP 1/2: Planning topic...")
    plan_prompt = build_plan_prompt(track_name, articles, date_str)
    plan_raw = call_claude(PLAN_SYSTEM_PROMPT, plan_prompt, label="plan")

    if plan_raw is None:
        log.error("Planning call failed — fallback")
        session = build_fallback_session(track_name, date_str, "Planning call failed.")
        out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        print(str(out_path))
        return 1

    plan = extract_json_from_response(plan_raw)
    if plan is None or "topic_title" not in plan:
        log.error("Could not parse plan JSON — fallback")
        debug_path = Path("/tmp") / f"claude_plan_{track_name}_{date_str}.txt"
        debug_path.write_text(plan_raw, encoding="utf-8")
        log.error("Raw plan saved to %s", debug_path)
        session = build_fallback_session(track_name, date_str, "Plan JSON parse error.")
        out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        print(str(out_path))
        return 1

    log.info("Topic: %s", plan.get("topic_title", "?"))
    log.info("Subtitle: %s", plan.get("subtitle", "?"))
    log.info("Tags: %s", plan.get("tags", []))

    # ── Step 2: Generate full session ────────────────────────────────────────
    log.info("=" * 60)
    log.info("STEP 2/2: Generating full session...")
    session_prompt = build_session_prompt(track_name, plan, articles, date_str)
    session_raw = call_claude(SESSION_SYSTEM_PROMPT, session_prompt, label="session")

    if session_raw is None:
        log.error("Session generation failed — fallback")
        session = build_fallback_session(track_name, date_str, "Session generation call failed.")
        out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        print(str(out_path))
        return 1

    session = extract_json_from_response(session_raw)
    if session is None:
        log.error("Could not parse session JSON — fallback")
        debug_path = Path("/tmp") / f"claude_session_{track_name}_{date_str}.txt"
        debug_path.write_text(session_raw, encoding="utf-8")
        log.error("Raw session saved to %s", debug_path)
        session = build_fallback_session(track_name, date_str, "Session JSON parse error.")
        out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        print(str(out_path))
        return 1

    # Validate
    issues = validate_session(session)
    if issues:
        log.warning("Session validation issues: %s", issues)
        # Still save it — partial content is better than fallback
    else:
        log.info("Session validation passed")

    total_elapsed = time.time() - total_start
    log.info("=" * 60)
    log.info("Session generated in %.1fs", total_elapsed)
    log.info("Title: %s", session.get("session_title", "?"))
    log.info("Sections: %d", len(session.get("sections", [])))

    # Save
    out_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    log.info("Session saved to %s", out_path)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
