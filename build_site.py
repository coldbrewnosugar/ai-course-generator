#!/usr/bin/env python3
"""
build_site.py — Render session JSON to HTML and regenerate the site index.

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
import re
from datetime import datetime, timezone
from pathlib import Path
from html import escape as html_escape
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from config import TRACKS, OUTPUT_DIR, SITE_DIR, LOG_DIR, GITHUB_REPO

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


# ── Session CSS ───────────────────────────────────────────────────────────────

SESSION_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');
:root {
  --bg: #FDFAF6;
  --ink: #2D2A26;
  --ink-secondary: #4A4641;
  --muted: #8C8578;
  --red: #C4533A;
  --blue: #3D6B99;
  --yellow: #D4952B;
  --green: #3A7D5C;
  --light-gray: #F5F1EB;
  --border-gray: #DDD5CA;
  --mono: 'Space Mono', monospace;
  --sans: 'DM Sans', system-ui, sans-serif;
  --border: 1px solid var(--border-gray);
  --max-w: 720px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  line-height: 1.7;
  font-size: 18px;
}

/* ── Layout ── */
.session-container {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 1.5rem 4rem;
}

/* ── Back link ── */
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  text-decoration: none;
  padding: 1.5rem 0 1rem;
  transition: color 0.15s;
}
.back-link:hover { color: var(--ink); }

/* ── Hero ── */
.session-hero {
  border-bottom: 1px solid var(--border-gray);
  padding: 2.5rem 0 2rem;
  margin-bottom: 2.5rem;
}
.session-hero .hero-tag {
  display: inline-block;
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #fff;
  background: var(--red);
  padding: 0.25rem 0.75rem;
  margin-bottom: 1rem;
  border-radius: 6px;
}
.session-hero h1 {
  font-family: var(--mono);
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
  margin-bottom: 0.5rem;
}
.session-hero .hero-subtitle {
  font-size: 1.1rem;
  color: var(--ink-secondary);
  font-weight: 400;
}
.session-hero .hero-meta {
  display: flex;
  gap: 1.5rem;
  margin-top: 1rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
  letter-spacing: 0.04em;
}
.hero-meta .tag {
  display: inline-block;
  background: var(--light-gray);
  border: 1px solid var(--border-gray);
  padding: 0.15rem 0.5rem;
  font-size: 0.65rem;
  border-radius: 6px;
}

/* ── Section divider ── */
.section-divider {
  border: none;
  border-top: 1px solid var(--border-gray);
  margin: 3rem 0;
}

/* ── Context block ── */
.context-block {
  background: var(--light-gray);
  border-left: 4px solid var(--ink);
  padding: 1.5rem 1.75rem;
  margin-bottom: 2.5rem;
  border-radius: 12px;
}
.context-block h2 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.75rem;
}
.context-block p { margin-bottom: 0.75rem; }
.context-block p:last-child { margin-bottom: 0; }

/* ── Steps ── */
.step-section { margin-bottom: 3rem; }
.step-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.step-number {
  flex-shrink: 0;
  width: 48px; height: 48px;
  background: var(--ink);
  color: #fff;
  font-family: var(--mono);
  font-size: 1.2rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}
.step-header h2 {
  font-family: var(--mono);
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  padding-top: 0.3rem;
}
.step-body p { margin-bottom: 0.75rem; }
.step-body ul, .step-body ol { margin: 0.5rem 0 0.75rem 1.5rem; }
.step-body li { margin-bottom: 0.3rem; }
.step-body strong { font-weight: 600; }
.step-body a { color: var(--blue); }

/* ── Code blocks ── */
.code-block {
  position: relative;
  margin: 1.25rem 0;
  background: var(--light-gray);
  border: 1px solid var(--border-gray);
  border-left: 3px solid var(--blue);
  border-radius: 12px;
  overflow: hidden;
}
.code-caption {
  display: block;
  padding: 0.5rem 1rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--muted);
  border-bottom: 1px solid var(--border-gray);
  letter-spacing: 0.04em;
}
.code-block pre {
  padding: 1rem;
  overflow-x: auto;
  margin: 0;
}
.code-block code {
  font-family: var(--mono);
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--ink);
}
.copy-btn {
  position: absolute;
  top: 0.4rem;
  right: 0.5rem;
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--ink);
  color: #fff;
  border: none;
  padding: 0.3rem 0.6rem;
  cursor: pointer;
  transition: background 0.15s;
  border-radius: 8px;
}
.copy-btn:hover { background: var(--blue); }
.copy-btn.copied { background: var(--green); }

/* ── Callouts ── */
.callout {
  border-left: 4px solid;
  padding: 1.25rem 1.5rem;
  margin: 1.25rem 0;
  font-size: 0.95rem;
  border-radius: 12px;
}
.callout-tip {
  border-color: var(--blue);
  background: rgba(61,107,153,0.06);
}
.callout-warning {
  border-color: var(--red);
  background: rgba(196,83,58,0.06);
}
.callout-api-key-note {
  border-color: var(--yellow);
  background: rgba(212,149,43,0.1);
}
.callout-label {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 0.3rem;
}
.callout-tip .callout-label { color: var(--blue); }
.callout-warning .callout-label { color: var(--red); }
.callout-api-key-note .callout-label { color: #b8860b; }

/* ── Reveals (details/summary) ── */
.reveal {
  margin: 1rem 0;
  border: 1px solid var(--border-gray);
  border-radius: 12px;
  overflow: hidden;
}
.reveal summary {
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.75rem 1rem;
  cursor: pointer;
  background: var(--light-gray);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: background 0.15s;
}
.reveal summary:hover { background: #EAE5DD; }
.reveal summary::before {
  content: "\25B6";
  font-size: 0.6rem;
  transition: transform 0.2s;
}
.reveal[open] summary::before {
  transform: rotate(90deg);
}
.reveal .reveal-body {
  padding: 1rem;
  border-top: 1px solid var(--border-gray);
  font-size: 0.95rem;
}
.reveal .reveal-body p { margin-bottom: 0.5rem; }
.reveal .reveal-body p:last-child { margin-bottom: 0; }

/* ── Checkpoint ── */
.checkpoint {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  background: var(--ink);
  color: #fff;
  margin: 2rem 0;
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border-radius: 12px;
}
.checkpoint-icon {
  flex-shrink: 0;
  width: 32px; height: 32px;
  border: 2px solid #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
}

/* ── Decision point ── */
.decision-point {
  border: 1px solid var(--border-gray);
  margin: 2rem 0;
  padding: 1.5rem;
  border-radius: 12px;
}
.decision-point h3 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.decision-point .question {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}
.decision-option {
  margin-bottom: 0.75rem;
}
.decision-option input[type="radio"] {
  display: none;
}
.decision-option label {
  display: block;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-gray);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
  border-radius: 8px;
}
.decision-option label:hover {
  border-color: var(--ink);
  background: var(--light-gray);
}
.decision-option input:checked + label {
  border-color: var(--ink);
  border-width: 2px;
  background: var(--light-gray);
}
.decision-feedback {
  display: none;
  padding: 0.75rem 1rem;
  margin-top: 0.25rem;
  font-size: 0.9rem;
  border-left: 3px solid;
  border-radius: 8px;
}
.decision-option input:checked ~ .decision-feedback {
  display: block;
}
.decision-feedback.correct {
  border-color: var(--green);
  background: rgba(58,125,92,0.06);
  color: var(--green);
}
.decision-feedback.incorrect {
  border-color: var(--red);
  background: rgba(196,83,58,0.06);
  color: var(--red);
}

/* ── Agent interaction ── */
.agent-interaction {
  margin: 1.5rem 0;
  border: 1px solid var(--border-gray);
  border-radius: 12px;
  overflow: hidden;
}
.agent-goal {
  padding: 1rem 1.25rem;
  background: var(--ink);
  color: #fff;
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 700;
}
.agent-goal-label {
  font-size: 0.6rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.6);
  margin-bottom: 0.3rem;
}
.agent-hints {
  padding: 1rem 1.25rem;
  background: rgba(61,107,153,0.04);
  border-bottom: 1px solid var(--border-gray);
}
.agent-hints-label {
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 0.5rem;
}
.agent-hints ul {
  list-style: none;
  padding: 0;
}
.agent-hints li {
  padding: 0.3rem 0 0.3rem 1.5rem;
  position: relative;
  font-size: 0.95rem;
  font-style: italic;
  color: var(--ink-secondary);
}
.agent-hints li::before {
  content: "?";
  position: absolute;
  left: 0;
  color: var(--blue);
  font-weight: 700;
  font-style: normal;
  font-family: var(--mono);
}

/* ── Your turn ── */
.your-turn {
  border: 1px solid var(--blue);
  padding: 1.5rem;
  margin: 2rem 0;
  border-radius: 12px;
}
.your-turn h3 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 0.5rem;
}
.your-turn .your-turn-goal {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}
.your-turn .your-turn-context {
  font-size: 0.95rem;
  color: var(--ink-secondary);
  margin-bottom: 1rem;
}

/* ── Recap ── */
.recap-section {
  border-top: 1px solid var(--border-gray);
  padding-top: 2.5rem;
  margin-top: 3rem;
}
.recap-section h2 {
  font-family: var(--mono);
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 1rem;
}
.recap-body { margin-bottom: 1.5rem; }
.recap-body p { margin-bottom: 0.75rem; }
.takeaways-list {
  list-style: none;
  padding: 0;
  margin-bottom: 1.5rem;
}
.takeaways-list li {
  padding: 0.5rem 0 0.5rem 1.5rem;
  position: relative;
  border-bottom: 1px solid var(--border-gray);
}
.takeaways-list li::before {
  content: "\2713";
  position: absolute;
  left: 0;
  color: var(--green);
  font-weight: 700;
}
.next-steps h3 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.next-steps ul {
  list-style: none;
  padding: 0;
}
.next-steps li {
  padding: 0.3rem 0 0.3rem 1.5rem;
  position: relative;
}
.next-steps li::before {
  content: "\2192";
  position: absolute;
  left: 0;
  color: var(--blue);
  font-weight: 700;
}

/* ── Sources ── */
.sources-section {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-gray);
}
.sources-section h3 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.75rem;
}
.sources-list {
  list-style: none;
  padding: 0;
}
.sources-list li {
  padding: 0.3rem 0;
}
.sources-list a {
  color: var(--blue);
  text-decoration: none;
  font-size: 0.9rem;
}
.sources-list a:hover { text-decoration: underline; }
.sources-list .source-name {
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
  margin-left: 0.5rem;
}

/* ── Other articles ── */
.other-articles {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-gray);
}
.other-articles h3 {
  font-family: var(--mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.other-articles .oa-intro {
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 1rem;
}
.other-article-card {
  border: 1px solid var(--border-gray);
  padding: 1rem 1.25rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  border-radius: 10px;
}
.other-article-card:hover {
  border-color: var(--ink);
}
.oa-info {
  flex: 1;
  min-width: 0;
}
.oa-title {
  font-weight: 600;
  font-size: 0.95rem;
  margin-bottom: 0.15rem;
}
.oa-summary {
  font-size: 0.85rem;
  color: var(--ink-secondary);
  margin: 0.15rem 0;
  line-height: 1.4;
}
.oa-meta {
  font-family: var(--mono);
  font-size: 0.65rem;
  color: var(--muted);
  letter-spacing: 0.04em;
}
.oa-votes {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}
.oa-toggle {
  display: none;
}
.oa-toggle-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px; height: 36px;
  font-size: 1.1rem;
  border: 1px solid var(--border-gray);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--light-gray);
  user-select: none;
  border-radius: 8px;
}
.oa-toggle-label:hover {
  border-color: var(--ink);
  background: #fff;
}
.oa-toggle:checked + .oa-toggle-label.vote-up {
  border-color: var(--green);
  background: rgba(58,125,92,0.1);
}
.oa-toggle:checked + .oa-toggle-label.vote-down {
  border-color: var(--red);
  background: rgba(196,83,58,0.1);
}
.oa-submit-row {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.oa-submit-btn {
  font-family: var(--mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.6rem 1.5rem;
  background: var(--ink);
  color: #fff;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  border-radius: 8px;
}
.oa-submit-btn:hover { background: var(--blue); }
.oa-submit-btn:disabled {
  background: var(--border-gray);
  color: var(--muted);
  cursor: default;
}
.oa-submit-hint {
  font-size: 0.75rem;
  color: var(--muted);
}

/* ── Footer ── */
.session-footer {
  text-align: center;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.6rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 3rem;
  padding: 1.5rem 0 2.5rem;
  border-top: 1px solid var(--border-gray);
}
.session-footer span { color: var(--ink); font-weight: 700; }

/* ── Responsive ── */
@media (max-width: 600px) {
  body { font-size: 16px; }
  .session-hero h1 { font-size: 1.5rem; }
  .step-number { width: 36px; height: 36px; font-size: 1rem; }
  .session-container { padding: 0 1rem 3rem; }
  .hero-meta { flex-wrap: wrap; gap: 0.75rem; }
}
"""

# ── Inline JS ─────────────────────────────────────────────────────────────────

SESSION_JS = r"""
document.addEventListener('DOMContentLoaded', function() {
  // Copy-to-clipboard
  document.querySelectorAll('.copy-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var code = btn.closest('.code-block').querySelector('code').textContent;
      navigator.clipboard.writeText(code).then(function() {
        btn.textContent = 'COPIED';
        btn.classList.add('copied');
        setTimeout(function() {
          btn.textContent = 'COPY';
          btn.classList.remove('copied');
        }, 2000);
      });
    });
  });
});
"""


# ── Markdown-to-HTML (minimal, no dependency) ────────────────────────────────

def md_to_html(text: str) -> str:
    """Convert simple markdown to HTML. Handles bold, italic, links, code, paragraphs."""
    if not text:
        return ""

    lines = text.strip().split("\n")
    html_parts = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        # Empty line — close list if open
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
                list_type = None
            html_parts.append("")
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            content = re.sub(r"^[-*]\s+", "", stripped)
            html_parts.append(f"<li>{_inline_md(content)}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+", stripped)
        if ol_match:
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r"^\d+\.\s+", "", stripped)
            html_parts.append(f"<li>{_inline_md(content)}</li>")
            continue

        # Close list if we hit non-list content
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = None

        # Headings
        h_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if h_match:
            level = len(h_match.group(1))
            html_parts.append(f"<h{level}>{_inline_md(h_match.group(2))}</h{level}>")
            continue

        # Regular paragraph
        html_parts.append(f"<p>{_inline_md(stripped)}</p>")

    if in_list:
        html_parts.append(f"</{list_type}>")

    return "\n".join(html_parts)


def _inline_md(text: str) -> str:
    """Convert inline markdown: bold, italic, code, links."""
    # Escape HTML first
    text = html_escape(text)
    # Code spans (must come before bold/italic to avoid conflicts)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


# ── Section renderers ────────────────────────────────────────────────────────

def render_hero(section: dict, session: dict) -> str:
    title = html_escape(section.get("title", session.get("session_title", "")))
    subtitle = html_escape(section.get("subtitle", session.get("session_subtitle", "")))
    minutes = session.get("estimated_minutes", "")
    tags = session.get("tags", [])

    tags_html = ""
    for tag in tags:
        tags_html += f' <span class="tag">{html_escape(tag)}</span>'

    return f"""
    <div class="session-hero">
      <div class="hero-tag">Workshop</div>
      <h1>{title}</h1>
      <div class="hero-subtitle">{subtitle}</div>
      <div class="hero-meta">
        <span>{minutes} min</span>
        <span>{tags_html}</span>
      </div>
    </div>"""


def render_context(section: dict) -> str:
    body_html = md_to_html(section.get("body", ""))
    return f"""
    <div class="context-block">
      <h2>What's happening</h2>
      {body_html}
    </div>"""


def render_code_snippet(snippet: dict) -> str:
    language = html_escape(snippet.get("language", ""))
    code = html_escape(snippet.get("code", ""))
    caption = snippet.get("caption", "")

    caption_html = ""
    if caption:
        caption_html = f'<span class="code-caption">{html_escape(caption)}</span>'

    return f"""
      <div class="code-block">
        {caption_html}
        <button class="copy-btn">COPY</button>
        <pre><code class="language-{language}">{code}</code></pre>
      </div>"""


def render_callout(callout: dict) -> str:
    style = callout.get("style", "tip")
    css_class = f"callout-{style.replace('_', '-')}"
    label_map = {"tip": "Tip", "warning": "Warning", "api-key-note": "API Key Note"}
    label = label_map.get(style, style.title())
    text = _inline_md(callout.get("text", ""))

    return f"""
      <div class="callout {css_class}">
        <div class="callout-label">{label}</div>
        {text}
      </div>"""


def render_reveal(reveal: dict) -> str:
    label = html_escape(reveal.get("label", "More details"))
    body = md_to_html(reveal.get("body", ""))

    return f"""
      <details class="reveal">
        <summary>{label}</summary>
        <div class="reveal-body">{body}</div>
      </details>"""


def render_agent_interaction(interaction: dict) -> str:
    goal = html_escape(interaction.get("goal", ""))
    hints = interaction.get("hints", [])
    expected = interaction.get("expected_output", "")

    hints_html = ""
    if hints:
        items = "".join(f"<li>{html_escape(h)}</li>" for h in hints)
        hints_html = f"""
        <div class="agent-hints">
          <div class="agent-hints-label">Think about it</div>
          <ul>{items}</ul>
        </div>"""

    expected_html = ""
    if expected:
        if isinstance(expected, dict) and expected.get("code"):
            # Legacy format: {language, code, caption}
            expected_code = render_code_snippet(expected)
            reveal_body = expected_code
        elif isinstance(expected, str):
            # New format: plain English description (may contain markdown)
            reveal_body = md_to_html(expected)
        else:
            reveal_body = ""

        if reveal_body:
            expected_html = f"""
      <details class="reveal">
        <summary>What the agent gives back</summary>
        <div class="reveal-body">{reveal_body}</div>
      </details>"""

    return f"""
      <div class="agent-interaction">
        <div class="agent-goal">
          <div class="agent-goal-label">Ask your agent</div>
          {goal}
        </div>
        {hints_html}
        {expected_html}
      </div>"""


def render_step(section: dict) -> str:
    step_num = section.get("step_number", "")
    title = html_escape(section.get("title", ""))
    body = md_to_html(section.get("body", ""))

    # Agent-first: render agent_interactions
    interactions_html = ""
    for interaction in section.get("agent_interactions", []):
        interactions_html += render_agent_interaction(interaction)

    # Backwards compat: also render code_snippets if present (legacy sessions)
    snippets_html = ""
    for snippet in section.get("code_snippets", []):
        snippets_html += render_code_snippet(snippet)

    callouts_html = ""
    for callout in section.get("callouts", []):
        callouts_html += render_callout(callout)

    reveals_html = ""
    for reveal in section.get("reveals", []):
        reveals_html += render_reveal(reveal)

    return f"""
    <div class="step-section">
      <div class="step-header">
        <div class="step-number">{step_num}</div>
        <h2>{title}</h2>
      </div>
      <div class="step-body">
        {body}
        {interactions_html}
        {snippets_html}
        {callouts_html}
        {reveals_html}
      </div>
    </div>"""


def render_checkpoint(section: dict) -> str:
    message = html_escape(section.get("message", ""))
    return f"""
    <div class="checkpoint">
      <div class="checkpoint-icon">&#10003;</div>
      <div>{message}</div>
    </div>"""


def render_decision_point(section: dict, section_idx: int) -> str:
    question = html_escape(section.get("question", ""))
    options = section.get("options", [])
    group_name = f"decision_{section_idx}"

    options_html = ""
    for i, opt in enumerate(options):
        label = html_escape(opt.get("label", ""))
        explanation = html_escape(opt.get("explanation", ""))
        is_correct = opt.get("correct", False)
        feedback_class = "correct" if is_correct else "incorrect"
        prefix = "&#10003; Correct!" if is_correct else "&#10007; Not quite."
        opt_id = f"{group_name}_opt{i}"

        options_html += f"""
        <div class="decision-option">
          <input type="radio" name="{group_name}" id="{opt_id}">
          <label for="{opt_id}">{label}</label>
          <div class="decision-feedback {feedback_class}">{prefix} {explanation}</div>
        </div>"""

    return f"""
    <div class="decision-point">
      <h3>Quick Check</h3>
      <div class="question">{question}</div>
      {options_html}
    </div>"""


def render_your_turn(section: dict) -> str:
    goal = html_escape(section.get("goal", ""))
    context = html_escape(section.get("context", ""))
    hints = section.get("hints", [])
    sample_prompt = section.get("sample_prompt", "")

    context_html = f'<div class="your-turn-context">{context}</div>' if context else ""

    hints_html = ""
    if hints:
        items = "".join(f"<li>{html_escape(h)}</li>" for h in hints)
        hints_html = f"""
      <div class="agent-hints">
        <div class="agent-hints-label">Think about it</div>
        <ul>{items}</ul>
      </div>"""

    sample_html = ""
    if sample_prompt:
        sample_html = f"""
      <details class="reveal">
        <summary>See a sample prompt</summary>
        <div class="reveal-body">
          <div class="code-block">
            <span class="code-caption">One way you could prompt it</span>
            <button class="copy-btn">COPY</button>
            <pre><code>{html_escape(sample_prompt)}</code></pre>
          </div>
        </div>
      </details>"""

    return f"""
    <div class="your-turn">
      <h3>Your Turn</h3>
      <div class="your-turn-goal">{goal}</div>
      {context_html}
      {hints_html}
      {sample_html}
    </div>"""


def render_try_it(section: dict) -> str:
    """Legacy renderer for old try_it sections."""
    return render_your_turn({
        "goal": section.get("prompt", ""),
        "context": "",
        "hints": [],
        "sample_prompt": (section.get("solution", {}) or {}).get("code", ""),
    })


def render_recap(section: dict) -> str:
    body = md_to_html(section.get("body", ""))
    takeaways = section.get("takeaways", [])
    next_steps = section.get("next_steps", [])

    takeaways_html = ""
    if takeaways:
        items = "".join(f"<li>{_inline_md(t)}</li>" for t in takeaways)
        takeaways_html = f'<ul class="takeaways-list">{items}</ul>'

    next_html = ""
    if next_steps:
        items = "".join(f"<li>{_inline_md(s)}</li>" for s in next_steps)
        next_html = f"""
      <div class="next-steps">
        <h3>Where to go next</h3>
        <ul>{items}</ul>
      </div>"""

    return f"""
    <div class="recap-section">
      <h2>Recap</h2>
      <div class="recap-body">{body}</div>
      {takeaways_html}
      {next_html}
    </div>"""


def render_sources(sources: list) -> str:
    if not sources:
        return ""

    items = ""
    for src in sources:
        title = html_escape(src.get("title", ""))
        url = html_escape(src.get("url", "#"))
        source_name = html_escape(src.get("source_name", ""))
        name_span = f' <span class="source-name">({source_name})</span>' if source_name else ""
        items += f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>{name_span}</li>'

    return f"""
    <div class="sources-section">
      <h3>Sources</h3>
      <ul class="sources-list">{items}</ul>
    </div>"""


def render_other_articles(candidate_articles: list, track_name: str, date_str: str) -> str:
    """Render the 'other articles' section with vote toggles and a single submit button."""
    # Filter to non-selected articles only
    others = [a for a in candidate_articles if not a.get("selected", False)]
    if not others:
        return ""

    # Cap at 10 to keep the page reasonable
    others = others[:10]

    # Build article data for JS
    articles_js_data = []
    cards_html = ""
    for i, art in enumerate(others):
        title = art.get("title", "(untitled)")
        source = art.get("source", "")
        summary = art.get("summary", "")
        tags = art.get("tags", [])
        pub = art.get("published", "")

        # Truncate summary to one line (~120 chars)
        if summary and len(summary) > 120:
            summary = summary[:117].rsplit(" ", 1)[0] + "..."

        # Format date for display
        pub_display = ""
        if pub:
            try:
                dt = datetime.fromisoformat(pub)
                pub_display = dt.strftime("%b %-d")
            except Exception:
                pub_display = pub[:10]

        meta_parts = []
        if source:
            meta_parts.append(html_escape(source))
        if pub_display:
            meta_parts.append(pub_display)
        meta_str = " · ".join(meta_parts)

        tags_str = ",".join(tags) if tags else ""
        articles_js_data.append({
            "title": title,
            "tags": tags_str,
            "source": source,
        })

        summary_html = ""
        if summary:
            summary_html = f'\n            <div class="oa-summary">{html_escape(summary)}</div>'

        cards_html += f"""
        <div class="other-article-card">
          <div class="oa-info">
            <div class="oa-title">{html_escape(title)}</div>{summary_html}
            <div class="oa-meta">{meta_str}</div>
          </div>
          <div class="oa-votes">
            <input type="radio" name="vote_{i}" value="up" id="vote_{i}_up" class="oa-toggle" data-idx="{i}">
            <label for="vote_{i}_up" class="oa-toggle-label vote-up" title="More like this">&#x1F44D;</label>
            <input type="radio" name="vote_{i}" value="down" id="vote_{i}_down" class="oa-toggle" data-idx="{i}">
            <label for="vote_{i}_down" class="oa-toggle-label vote-down" title="Not interested">&#x1F44E;</label>
          </div>
        </div>"""

    # Inline JS for collecting votes and opening a single issue
    articles_json = json.dumps(articles_js_data, ensure_ascii=False)
    vote_js = f"""
    (function() {{
      var articles = {articles_json};
      var repo = "{GITHUB_REPO}";
      var track = "{track_name}";
      var date = "{date_str}";

      var toggles = document.querySelectorAll('.oa-toggle');
      var btn = document.getElementById('oa-submit');
      var hint = document.getElementById('oa-hint');

      function updateBtn() {{
        var any = false;
        toggles.forEach(function(t) {{ if (t.checked) any = true; }});
        btn.disabled = !any;
        hint.textContent = any ? '' : 'Select at least one vote';
      }}
      toggles.forEach(function(t) {{ t.addEventListener('change', updateBtn); }});

      btn.addEventListener('click', function() {{
        var lines = [];
        for (var i = 0; i < articles.length; i++) {{
          var up = document.getElementById('vote_' + i + '_up');
          var down = document.getElementById('vote_' + i + '_down');
          var vote = '';
          if (up && up.checked) vote = 'up';
          if (down && down.checked) vote = 'down';
          if (vote) {{
            lines.push(vote + ' | ' + articles[i].title + ' | tags:' + articles[i].tags + ' | source:' + articles[i].source);
          }}
        }}
        if (lines.length === 0) return;

        var body = 'track:' + track + '\\ndate:' + date + '\\n\\n' + lines.join('\\n');
        var title = 'Votes from ' + date + ' (' + track + ')';
        var url = 'https://github.com/' + repo + '/issues/new?labels=vote&title=' +
          encodeURIComponent(title) + '&body=' + encodeURIComponent(body);
        window.open(url, '_blank');
      }});
    }})();"""

    return f"""
    <div class="other-articles">
      <h3>What else was in the news</h3>
      <p class="oa-intro">These articles were also available today. Vote to help shape future sessions.</p>
      {cards_html}
      <div class="oa-submit-row">
        <button id="oa-submit" class="oa-submit-btn" disabled>Submit votes</button>
        <span id="oa-hint" class="oa-submit-hint">Select at least one vote</span>
      </div>
    </div>
    <script>{vote_js}</script>"""


# ── Session page renderer ────────────────────────────────────────────────────

def render_session_html(session_path: Path, track_name: str = "", date_str: str = "") -> str | None:
    """Read session JSON and render to a full HTML page."""
    try:
        with open(session_path, encoding="utf-8") as fh:
            session = json.load(fh)
    except Exception as exc:
        log.error("Failed to read session JSON %s: %s", session_path, exc)
        return None

    # Infer track/date from path if not provided
    if not track_name:
        track_name = session_path.parent.name
    if not date_str:
        date_str = session_path.stem

    sections_html = ""
    for idx, section in enumerate(session.get("sections", [])):
        section_type = section.get("type", "")

        if section_type == "hero":
            sections_html += render_hero(section, session)
        elif section_type == "context":
            sections_html += render_context(section)
        elif section_type == "step":
            sections_html += render_step(section)
        elif section_type == "checkpoint":
            sections_html += render_checkpoint(section)
        elif section_type == "decision_point":
            sections_html += render_decision_point(section, idx)
        elif section_type == "your_turn":
            sections_html += render_your_turn(section)
        elif section_type == "try_it":
            sections_html += render_try_it(section)
        elif section_type == "recap":
            sections_html += render_recap(section)
            sections_html += render_sources(session.get("sources", []))
            sections_html += render_other_articles(
                session.get("candidate_articles", []), track_name, date_str)
        else:
            log.warning("Unknown section type '%s' — skipping", section_type)

    title = html_escape(session.get("session_title", "Workshop Session"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Tinker</title>
  <style>{SESSION_CSS}</style>
</head>
<body>
  <div class="session-container">
    <a href="../index.html" class="back-link">&larr; Back to calendar</a>
    {sections_html}
    <footer class="session-footer">
      <span>Tinker</span> &middot; Build with AI, daily
    </footer>
  </div>
  <script>{SESSION_JS}</script>
</body>
</html>"""


def convert_session_to_html(track_name: str, date_str: str) -> Path | None:
    """Render session JSON to HTML. Returns the output HTML path, or None on failure."""
    session_path = Path(OUTPUT_DIR) / track_name / f"{date_str}.json"
    out_dir = Path(SITE_DIR) / track_name
    out_path = out_dir / f"{date_str}.html"

    if not session_path.exists():
        log.error("Session JSON not found: %s", session_path)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)

    html = render_session_html(session_path, track_name, date_str)
    if html is None:
        return None

    out_path.write_text(html, encoding="utf-8")
    log.info("HTML written to %s (%d bytes)", out_path, len(html))
    return out_path


# ── Title extraction ───────────────────────────────────────────────────────────

def get_course_title(track_name: str, date_str: str) -> str:
    """Extract title from session JSON, or return a default."""
    session_path = Path(OUTPUT_DIR) / track_name / f"{date_str}.json"
    try:
        with open(session_path, encoding="utf-8") as fh:
            session = json.load(fh)
        return session.get("session_title", "").strip() or f"{TRACKS.get(track_name, {}).get('label', track_name)} — {date_str}"
    except Exception:
        pass
    label = TRACKS.get(track_name, {}).get("label", track_name)
    return f"{label} — {date_str}"


# ── Index page generation ──────────────────────────────────────────────────────

INDEX_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');
:root {
  --bg: #FDFAF6;
  --ink: #2D2A26;
  --ink-secondary: #4A4641;
  --muted: #8C8578;
  --red: #C4533A;
  --blue: #3D6B99;
  --yellow: #D4952B;
  --green: #3A7D5C;
  --light-gray: #F5F1EB;
  --border-gray: #DDD5CA;
  --mono: 'Space Mono', monospace;
  --sans: 'DM Sans', system-ui, sans-serif;
  --border: 1px solid var(--border-gray);
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
  border-bottom: 1px solid var(--border-gray);
  margin-top: 2rem;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem 1.5rem 1.5rem 0;
  border-right: 1px solid var(--border-gray);
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
  border-radius: 8px;
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
  border-radius: 6px;
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
  border-bottom: 1px solid var(--border-gray);
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
  box-shadow: inset 0 0 0 2px var(--red);
}
.day-col.empty-day {
  background: #F8F4EE;
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
  border: 1px solid var(--border-gray);
  transition: all 0.15s;
  line-height: 1.25;
  word-break: break-word;
  border-radius: 8px;
}
.course-pill:hover {
  border-color: var(--ink);
  background: var(--light-gray);
}
.course-pill .pill-shape {
  flex-shrink: 0;
  font-size: 0.85rem;
  line-height: 1;
}
.course-pill.track-general  { border-left: 3px solid var(--red); }
.course-pill.track-image-gen { border-left: 3px solid var(--blue); }
.course-pill.track-audio    { border-left: 3px solid var(--yellow); }
.course-pill.track-general:hover  { background: rgba(196,83,58,0.08); }
.course-pill.track-image-gen:hover { background: rgba(61,107,153,0.08); }
.course-pill.track-audio:hover    { background: rgba(212,149,43,0.08); }

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
  border-top: 1px solid var(--border-gray);
}
footer span { color: var(--ink); font-weight: 700; }

/* ── Responsive ── */
@media (max-width: 700px) {
  .header { flex-direction: column; }
  .header-brand { border-right: none; border-bottom: 1px solid var(--border-gray); padding: 1rem; }
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
        "color": "#C4533A",
        "shape": "\u25cf",
        "label_short": "GEN",
        "css_class": "track-general",
        "desc": "LLMs, research papers &amp; coding advances",
    },
    "image-gen": {
        "color": "#3D6B99",
        "shape": "\u25a0",
        "label_short": "IMG",
        "css_class": "track-image-gen",
        "desc": "Diffusion models, video AI &amp; vision",
    },
    "audio": {
        "color": "#D4952B",
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
    weekday_idx = (today.weekday() + 1) % 7  # 0=Sun
    week_start = today - __import__("datetime").timedelta(days=weekday_idx)

    # Pre-render the initial week server-side
    day_names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
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
const DAY_NAMES = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
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
  const wd = t.getDay();
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
  <title>Tinker</title>
  <meta name="description" content="Daily hands-on workshops — build real projects with AI agents.">
  <style>{INDEX_CSS}</style>
</head>
<body>
  <div class="container">

    <div class="header">
      <div class="header-brand">
        <div class="header-mark"><span>T</span></div>
        <div class="header-text">
          <h1>Tinker</h1>
          <div class="tagline">Build with AI, daily</div>
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
      <div><strong>{total_courses}</strong> session{"s" if total_courses != 1 else ""}</div>
      <div><strong>{len(TRACK_ORDER)}</strong> tracks</div>
      <div>Updated <strong>{now_str}</strong></div>
    </div>

    <footer>
      <span>Tinker</span> &middot; Build with AI, daily
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
        description="Render session JSON to HTML and regenerate site index."
    )
    parser.add_argument("track", nargs="?", choices=list(TRACKS.keys()),
                        help="Track name")
    parser.add_argument("date",  nargs="?",
                        help="Date string YYYY-MM-DD")
    parser.add_argument("--index-only", action="store_true",
                        help="Only regenerate index.html, skip session rendering")
    args = parser.parse_args()

    site_dir = Path(SITE_DIR)
    site_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0

    if not args.index_only and args.track and args.date:
        html_path = convert_session_to_html(args.track, args.date)
        if html_path is None:
            log.error("Session rendering failed for %s/%s", args.track, args.date)
            exit_code = 1
        else:
            log.info("Rendering successful: %s", html_path)

    # Always regenerate index
    index_path = generate_index_html(site_dir)
    log.info("Site index: %s", index_path)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
