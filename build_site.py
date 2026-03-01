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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;0,9..144,800;1,9..144,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {
  --bg: #FAFAFA;
  --bg-subtle: #F4F4F5;
  --bg-elevated: #FFFFFF;
  --ink: #18181B;
  --ink-secondary: #52525B;
  --muted: #A1A1AA;
  --accent: #E5484D;
  --accent-hover: #CD2B31;
  --accent-light: rgba(229,72,77,0.06);
  --accent-subtle: rgba(229,72,77,0.12);
  --blue: #3B82F6;
  --red: #EF4444;
  --yellow: #EAB308;
  --green: #22C55E;
  --surface: #F4F4F5;
  --border: #E4E4E7;
  --border-subtle: #F4F4F5;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.03);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.02);
  --mono: 'IBM Plex Mono', monospace;
  --display: 'Fraunces', Georgia, serif;
  --sans: 'Inter', -apple-system, system-ui, sans-serif;
  --max-w: 680px;
  --max-w-wide: 780px;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  line-height: 1.7;
  font-size: 17px;
  border-top: 3px solid var(--accent);
}

/* ── Track color worlds ── */
body.track-general { /* default coral — uses :root values */ }
body.track-image-gen { --accent: #8B5CF6; --accent-hover: #7C3AED; --accent-light: rgba(139,92,246,0.06); --accent-subtle: rgba(139,92,246,0.12); }
body.track-audio { --accent: #F59E0B; --accent-hover: #D97706; --accent-light: rgba(245,158,11,0.06); --accent-subtle: rgba(245,158,11,0.12); }

/* ── Layout ── */
.session-container {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 1.5rem 5rem;
}

/* ── Back link ── */
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  padding: 2rem 0 1.25rem;
  transition: color 0.15s;
}
.back-link:hover { color: var(--accent); }

/* ── Hero ── */
.session-hero {
  padding: 1rem 0 2.5rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border);
}
.session-hero .hero-tag {
  display: inline-block;
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-light);
  padding: 0.3rem 0.75rem;
  margin-bottom: 1.25rem;
  border-radius: var(--radius-sm);
}
.session-hero h1 {
  font-family: var(--display);
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.025em;
  margin-bottom: 0.6rem;
  font-optical-sizing: auto;
}
.session-hero .hero-subtitle {
  font-size: 1.1rem;
  color: var(--ink-secondary);
  font-weight: 400;
  line-height: 1.5;
}
.session-hero .hero-meta {
  display: flex;
  gap: 1.25rem;
  margin-top: 1.25rem;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
  letter-spacing: 0.02em;
}
.hero-meta .tag {
  display: inline-block;
  background: var(--surface);
  padding: 0.2rem 0.55rem;
  font-size: 0.65rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

/* ── Section divider ── */
.section-divider {
  border: none;
  width: 32px;
  height: 2px;
  background: var(--accent);
  margin: 3rem 0;
}

/* ── Context block ── */
.context-block {
  background: var(--bg-elevated);
  padding: 1.5rem 1.75rem;
  margin-bottom: 2.5rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}
.context-block h2 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
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
  margin-bottom: 1.25rem;
}
.step-number {
  flex-shrink: 0;
  width: 44px; height: 44px;
  background: var(--ink);
  color: #fff;
  font-family: var(--mono);
  font-size: 0.9rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
}
.step-header h2 {
  font-family: var(--display);
  font-size: 1.3rem;
  font-weight: 700;
  line-height: 1.25;
  padding-top: 0.35rem;
}
.step-body p { margin-bottom: 0.75rem; }
.step-body ul, .step-body ol { margin: 0.5rem 0 0.75rem 1.5rem; }
.step-body li { margin-bottom: 0.35rem; }
.step-body strong { font-weight: 600; }
.step-body a { color: var(--accent); text-decoration: underline; text-decoration-color: var(--accent-subtle); text-underline-offset: 2px; }
.step-body a:hover { text-decoration-color: var(--accent); }

/* ── Code blocks ── */
.code-block {
  position: relative;
  margin: 1.25rem 0;
  background: var(--ink);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.code-caption {
  display: block;
  padding: 0.55rem 1rem;
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 500;
  color: rgba(255,255,255,0.4);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  letter-spacing: 0.03em;
}
.code-block pre {
  padding: 1rem;
  overflow-x: auto;
  margin: 0;
  background: transparent;
}
.code-block code {
  font-family: var(--mono);
  font-size: 0.82rem;
  line-height: 1.6;
  color: #E4E4E7;
}
.copy-btn {
  position: absolute;
  top: 0.45rem;
  right: 0.5rem;
  font-family: var(--mono);
  font-size: 0.55rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.5);
  border: none;
  padding: 0.25rem 0.55rem;
  cursor: pointer;
  transition: all 0.15s;
  border-radius: var(--radius-sm);
}
.copy-btn:hover { background: rgba(255,255,255,0.2); color: #fff; }
.copy-btn.copied { background: var(--green); color: #fff; }

/* ── Callouts ── */
.callout {
  padding: 1rem 1.25rem;
  margin: 1.25rem 0;
  font-size: 0.92rem;
  border-radius: var(--radius-md);
  border: 1px solid;
  background: var(--bg-elevated);
}
.callout-tip {
  border-color: rgba(59,130,246,0.25);
  background: rgba(59,130,246,0.04);
}
.callout-warning {
  border-color: rgba(239,68,68,0.4);
  background: rgba(239,68,68,0.04);
}
.callout-api-key-note {
  border-color: rgba(234,179,8,0.3);
  background: rgba(234,179,8,0.05);
}
.callout-label {
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}
.callout-tip .callout-label { color: var(--blue); }
.callout-warning .callout-label { color: var(--red); }
.callout-api-key-note .callout-label { color: #CA8A04; }

/* ── Reveals (details/summary) ── */
.reveal {
  margin: 1rem 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
}
.reveal summary {
  font-family: var(--sans);
  font-size: 0.85rem;
  font-weight: 600;
  padding: 0.75rem 1rem;
  cursor: pointer;
  background: var(--bg-elevated);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: background 0.15s;
}
.reveal summary:hover { background: var(--surface); }
.reveal summary::before {
  content: "+";
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent);
}
.reveal[open] summary::before {
  content: "\2212";
}
.reveal .reveal-body {
  padding: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.92rem;
}
.reveal .reveal-body p { margin-bottom: 0.5rem; }
.reveal .reveal-body p:last-child { margin-bottom: 0; }

/* ── Checkpoint ── */
.checkpoint {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.85rem 1.25rem;
  background: var(--accent-light);
  color: var(--ink);
  margin: 2rem 0;
  font-family: var(--sans);
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: var(--radius-md);
  border: 1px solid var(--accent-subtle);
}
.checkpoint-icon {
  flex-shrink: 0;
  width: 26px; height: 26px;
  background: var(--accent);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  color: #fff;
}

/* ── Decision point ── */
.decision-point {
  margin: 2rem 0;
  padding: 1.5rem;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
}
.decision-point h3 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.5rem;
}
.decision-point .question {
  font-family: var(--display);
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  line-height: 1.35;
}
.decision-option {
  margin-bottom: 0.5rem;
}
.decision-option input[type="radio"] {
  display: none;
}
.decision-option label {
  display: block;
  padding: 0.7rem 1rem;
  background: var(--surface);
  border: 1.5px solid var(--border);
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
  font-size: 0.92rem;
  border-radius: var(--radius-md);
}
.decision-option label:hover {
  background: var(--accent-light);
  border-color: var(--accent);
}
.decision-option input:checked + label {
  border-color: var(--accent);
  background: var(--accent-light);
}
.decision-feedback {
  display: none;
  padding: 0.65rem 0.85rem;
  margin-top: 0.35rem;
  font-size: 0.85rem;
  border-left: 3px solid;
  border-radius: var(--radius-sm);
}
.decision-option input:checked ~ .decision-feedback {
  display: block;
}
.decision-feedback.correct {
  border-color: var(--green);
  background: rgba(34,197,94,0.06);
  color: #15803D;
}
.decision-feedback.incorrect {
  border-color: var(--red);
  background: rgba(239,68,68,0.05);
  color: #DC2626;
}

/* ── Agent interaction ── */
.agent-interaction {
  margin: 1.5rem calc((var(--max-w) - var(--max-w-wide)) / 2);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border);
}
.agent-goal {
  padding: 1rem 1.25rem;
  background: var(--ink);
  color: #E4E4E7;
  font-family: var(--mono);
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.5;
}
.agent-goal::before {
  content: none;
}
.agent-goal-label {
  font-size: 0.55rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 0.4rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: rgba(255,255,255,0.35);
}
.agent-goal-label::before {
  content: "";
  display: inline-block;
  width: 6px; height: 6px;
  background: var(--green);
  border-radius: 50%;
}
.agent-hints {
  padding: 1rem 1.25rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.agent-hints-label {
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.5rem;
}
.agent-hints ul {
  list-style: none;
  padding: 0;
}
.agent-hints li {
  padding: 0.3rem 0 0.3rem 1.25rem;
  position: relative;
  font-size: 0.9rem;
  font-style: italic;
  color: var(--ink-secondary);
}
.agent-hints li::before {
  content: "\203A";
  position: absolute;
  left: 0;
  color: var(--accent);
  font-weight: 700;
  font-style: normal;
  font-family: var(--mono);
}

/* Agent interaction reveals */
.agent-interaction .reveal {
  border-radius: 0;
  border: none;
  border-top: 1px solid var(--border);
}
.agent-interaction .reveal summary {
  font-size: 0.8rem;
  background: var(--surface);
}

/* ── Your turn ── */
.your-turn {
  padding: 1.5rem;
  margin: 2rem 0;
  border-radius: var(--radius-md);
  background: var(--accent-light);
  border: 1.5px solid var(--accent-subtle);
}
.your-turn h3 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 0.5rem;
}
.your-turn .your-turn-goal {
  font-family: var(--sans);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  line-height: 1.4;
}
.your-turn .your-turn-context {
  font-size: 0.92rem;
  color: var(--ink-secondary);
  margin-bottom: 1rem;
}

/* ── Recap ── */
.recap-section {
  padding-top: 2.5rem;
  margin-top: 3rem;
  border-top: 1px solid var(--border);
}
.recap-section h2 {
  font-family: var(--display);
  font-size: 1.35rem;
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
  padding: 0.55rem 0 0.55rem 1.75rem;
  position: relative;
  font-size: 0.95rem;
}
.takeaways-list li::before {
  content: "\2713";
  position: absolute;
  left: 0;
  color: var(--green);
  font-weight: 700;
  font-size: 0.85rem;
}
.next-steps h3 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
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
  color: var(--accent);
  font-weight: 700;
}

/* ── Sources ── */
.sources-section {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}
.sources-section h3 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
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
  color: var(--accent);
  text-decoration: underline;
  text-decoration-color: var(--accent-subtle);
  text-underline-offset: 2px;
  font-size: 0.9rem;
}
.sources-list a:hover { text-decoration-color: var(--accent); }
.sources-list .source-name {
  font-family: var(--mono);
  font-size: 0.65rem;
  color: var(--muted);
  margin-left: 0.35rem;
}

/* ── Other articles ── */
.other-articles {
  margin-top: 2.5rem;
  padding-top: 1.5rem;
}
.other-articles h3 {
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.other-articles .oa-intro {
  font-size: 0.82rem;
  color: var(--muted);
  margin-bottom: 1rem;
}
.other-article-card {
  padding: 0.85rem 1rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  transition: all 0.15s;
}
.other-article-card:hover {
  border-color: var(--accent-subtle);
  background: var(--accent-light);
}
.oa-info {
  flex: 1;
  min-width: 0;
}
.oa-title {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.1rem;
}
.oa-summary {
  font-size: 0.82rem;
  color: var(--ink-secondary);
  margin: 0.1rem 0;
  line-height: 1.4;
}
.oa-meta {
  font-family: var(--mono);
  font-size: 0.6rem;
  color: var(--muted);
  letter-spacing: 0.02em;
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
  width: 34px; height: 34px;
  font-size: 0.9rem;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--bg-elevated);
  user-select: none;
  border-radius: var(--radius-sm);
}
.oa-toggle-label:hover {
  background: var(--surface);
  border-color: var(--muted);
}
.oa-toggle:checked + .oa-toggle-label.vote-up {
  background: rgba(34,197,94,0.1);
  border-color: var(--green);
  color: var(--green);
}
.oa-toggle:checked + .oa-toggle-label.vote-down {
  background: rgba(239,68,68,0.08);
  border-color: var(--red);
  color: var(--red);
}
.oa-submit-row {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.oa-submit-btn {
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.55rem 1.25rem;
  background: var(--ink);
  color: #fff;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  border-radius: var(--radius-md);
}
.oa-submit-btn:hover { background: #27272A; }
.oa-submit-btn:disabled {
  background: var(--surface);
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
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 4rem;
  padding: 1.5rem 0 2.5rem;
  border-top: 1px solid var(--border);
}
.session-footer span { color: var(--ink); font-weight: 600; }

/* ── Responsive ── */
@media (max-width: 600px) {
  body { font-size: 16px; }
  .session-hero h1 { font-size: 1.75rem; }
  .step-number { width: 36px; height: 36px; font-size: 0.8rem; }
  .session-container { padding: 0 1.15rem 3rem; }
  .hero-meta { flex-wrap: wrap; gap: 0.75rem; }
  .agent-interaction { margin-left: 0; margin-right: 0; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
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
            <label for="vote_{i}_up" class="oa-toggle-label vote-up" title="More like this">&#x25B2;</label>
            <input type="radio" name="vote_{i}" value="down" id="vote_{i}_down" class="oa-toggle" data-idx="{i}">
            <label for="vote_{i}_down" class="oa-toggle-label vote-down" title="Not interested">&#x25BC;</label>
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

    track_class = f" track-{track_name}" if track_name else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Tinker</title>
  <style>{SESSION_CSS}</style>
</head>
<body class="{track_class.strip()}">
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
    """Render session JSON to HTML. Returns the output HTML path, or None on failure.

    date_str can be 'YYYY-MM-DD' (legacy) or 'YYYY-MM-DD-N' (slot).
    """
    session_path = Path(OUTPUT_DIR) / track_name / f"{date_str}.json"
    out_dir = Path(SITE_DIR) / track_name
    out_path = out_dir / f"{date_str}.html"

    if not session_path.exists():
        log.error("Session JSON not found: %s", session_path)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)

    # Extract the base date for render (strip slot suffix if present)
    render_date = date_str[:10] if len(date_str) > 10 else date_str

    html = render_session_html(session_path, track_name, render_date)
    if html is None:
        return None

    out_path.write_text(html, encoding="utf-8")
    log.info("HTML written to %s (%d bytes)", out_path, len(html))
    return out_path


# ── Title extraction ───────────────────────────────────────────────────────────

def get_course_title(track_name: str, date_str: str) -> str:
    """Extract title from session JSON, or return a default.

    date_str can be 'YYYY-MM-DD' (legacy) or 'YYYY-MM-DD-N' (slot).
    """
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;0,9..144,800;1,9..144,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {
  --bg: #FAFAFA;
  --bg-subtle: #F4F4F5;
  --ink: #18181B;
  --ink-secondary: #52525B;
  --muted: #A1A1AA;
  --accent: #E5484D;
  --accent-hover: #CD2B31;
  --accent-light: rgba(229,72,77,0.06);
  --accent-subtle: rgba(229,72,77,0.12);
  --red: #EF4444;
  --blue: #3B82F6;
  --yellow: #EAB308;
  --green: #22C55E;
  --surface: #F4F4F5;
  --border: #E4E4E7;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.03);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.02);
  --mono: 'IBM Plex Mono', monospace;
  --display: 'Fraunces', Georgia, serif;
  --sans: 'Inter', -apple-system, system-ui, sans-serif;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  border-top: 3px solid #E5484D;
}

.container {
  max-width: 920px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* ── Header ── */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2.5rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border);
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-shrink: 0;
}
.header-mark {
  width: 40px; height: 40px;
  background: var(--ink);
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.header-mark span {
  font-family: var(--display);
  font-weight: 800;
  font-size: 1.15rem;
  color: #fff;
}
.header-text h1 {
  font-family: var(--display);
  font-size: 1.4rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.header-text .tagline {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.1rem;
  font-weight: 400;
}
.header-shapes { display: none; }

/* ── Explainer ── */
.explainer {
  max-width: 520px;
  margin: 0 auto;
  padding: 1.25rem 0 0.25rem;
  text-align: center;
}
.explainer p {
  font-family: var(--sans);
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--muted);
  margin: 0;
  text-wrap: balance;
}
.explainer strong {
  color: var(--ink);
  font-weight: 600;
}

/* ── Week navigation ── */
.week-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.5rem 0 1rem;
}
.week-nav button {
  font-family: var(--sans);
  font-size: 0.9rem;
  font-weight: 600;
  background: var(--bg);
  color: var(--ink);
  border: 1px solid var(--border);
  width: 36px; height: 36px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
  border-radius: var(--radius-sm);
}
.week-nav button:hover { background: var(--surface); border-color: var(--ink); }
.week-nav .week-label {
  font-family: var(--sans);
  font-size: 0.9rem;
  font-weight: 600;
  min-width: 220px;
  text-align: center;
}
.week-nav .today-btn {
  font-family: var(--mono);
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--bg);
  color: var(--ink-secondary);
  border: 1px solid var(--border);
  width: auto;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
  border-radius: var(--radius-sm);
}
.week-nav .today-btn:hover {
  background: var(--surface);
  border-color: var(--ink);
}

/* ── Calendar grid ── */
.week-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.day-col {
  min-height: 155px;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.day-header {
  font-family: var(--mono);
  font-size: 0.55rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-align: center;
  padding: 0.65rem 0.4rem 0.15rem;
  color: var(--muted);
}
.day-num {
  font-family: var(--mono);
  font-size: 1.15rem;
  font-weight: 600;
  text-align: center;
  padding: 0.25rem 0 0.4rem;
  color: var(--ink);
}
.day-col.is-today .day-num {
  background: var(--ink);
  color: #fff;
  margin: 0 auto;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  padding: 0;
}
.day-col.is-today {
  background: var(--accent-light);
}
.day-col.empty-day {
  background: var(--bg);
}
.day-courses {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 3px;
}
.course-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 7px;
  text-decoration: none;
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--ink);
  background: var(--surface);
  border: none;
  transition: all 0.15s;
  line-height: 1.25;
  word-break: break-word;
  border-radius: var(--radius-sm);
}
.course-pill:hover {
  background: var(--accent-light);
}
.course-pill .pill-shape {
  flex-shrink: 0;
  font-size: 0.5rem;
  line-height: 1;
}
.course-pill.track-general  { border-left: 3px solid #E5484D; }
.course-pill.track-image-gen { border-left: 3px solid #8B5CF6; }
.course-pill.track-audio    { border-left: 3px solid #F59E0B; }
.course-pill.track-general:hover  { background: rgba(229,72,77,0.06); }
.course-pill.track-image-gen:hover { background: rgba(139,92,246,0.06); }
.course-pill.track-audio:hover    { background: rgba(245,158,11,0.06); }

/* ── Legend ── */
.legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 1.25rem 0;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--ink-secondary);
}
.legend-shape {
  font-size: 0.5rem;
  line-height: 1;
}
.legend-item.track-general  .legend-shape { color: #E5484D; }
.legend-item.track-image-gen .legend-shape { color: #8B5CF6; }
.legend-item.track-audio    .legend-shape { color: #F59E0B; }
.legend-swatch {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 2px;
}
.legend-item.track-general  .legend-swatch { background: #E5484D; }
.legend-item.track-image-gen .legend-swatch { background: #8B5CF6; }
.legend-item.track-audio    .legend-swatch { background: #F59E0B; }

/* ── Stats bar ── */
.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 0.5rem 0;
  font-family: var(--mono);
  font-size: 0.6rem;
  color: var(--muted);
  letter-spacing: 0.04em;
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
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 2.5rem;
  padding: 1.5rem 0 2.5rem;
  border-top: 1px solid var(--border);
}
footer span { color: var(--ink); font-weight: 600; }

/* ── Responsive ── */
@media (max-width: 700px) {
  .header { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
  .week-grid {
    display: flex;
    flex-direction: column;
    gap: 0;
    border-radius: var(--radius-md);
  }
  .day-col {
    min-height: auto;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid var(--border);
  }
  .day-col:last-child { border-bottom: none; }
  .day-col.empty-day { display: none; }
  .day-header {
    flex-shrink: 0;
    width: 2.5rem;
    text-align: left;
    padding: 0;
  }
  .day-num {
    flex-shrink: 0;
    width: 2rem;
    text-align: center;
    padding: 0;
    font-size: 0.95rem;
  }
  .day-col.is-today .day-num {
    width: 28px; height: 28px;
    margin: 0;
    font-size: 0.85rem;
  }
  .day-courses {
    flex: 1;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 4px;
    padding: 0;
  }
  .legend { flex-wrap: wrap; gap: 0.75rem; }
  .week-nav .week-label { min-width: auto; font-size: 0.75rem; }
  .week-nav { gap: 0.5rem; }
}
@media (max-width: 480px) {
  .header-text h1 { font-size: 1.2rem; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
"""

TRACK_META = {
    "general": {
        "color": "#E5484D",
        "shape": "\u25cf",
        "label_short": "GEN",
        "css_class": "track-general",
        "desc": "LLMs, research papers &amp; coding advances",
    },
    "image-gen": {
        "color": "#8B5CF6",
        "shape": "\u25a0",
        "label_short": "IMG",
        "css_class": "track-image-gen",
        "desc": "Diffusion models, video AI &amp; vision",
    },
    "audio": {
        "color": "#F59E0B",
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
    # Collect all course HTML files
    # all_dates: {date -> {track -> [{title, url, slot}]}}
    courses: dict[str, list[dict]] = {t: [] for t in TRACK_ORDER}
    all_dates: dict[str, dict] = {}  # date -> track -> list of sessions

    for track_name in TRACK_ORDER:
        track_dir = site_dir / track_name
        if not track_dir.is_dir():
            continue
        # Match both legacy (YYYY-MM-DD.html) and slot (YYYY-MM-DD-N.html)
        for html_file in sorted(track_dir.glob("????-??-??*.html"), reverse=True):
            stem = html_file.stem  # e.g. "2026-03-01" or "2026-03-01-2"
            # Parse date and optional slot
            import re as _re
            m = _re.match(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?$", stem)
            if not m:
                continue
            base_date = m.group(1)
            slot = m.group(2)  # None for legacy files

            title    = get_course_title(track_name, stem)
            rel_path = f"{track_name}/{html_file.name}"
            courses[track_name].append({
                "date": base_date, "title": title, "rel_path": rel_path,
                "slot": slot,
            })
            if base_date not in all_dates:
                all_dates[base_date] = {}
            if track_name not in all_dates[base_date]:
                all_dates[base_date][track_name] = []
            all_dates[base_date][track_name].append({
                "title": title, "url": rel_path, "slot": slot,
            })

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
                entries = day_data[track_name]  # list of sessions
                for entry in entries:
                    title_esc = _html_escape(entry["title"])
                    slot_label = f' #{entry["slot"]}' if entry.get("slot") else ""
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
    const hasCourses = Object.values(dayData).some(v => Array.isArray(v) ? v.length > 0 : !!v);
    const todayCls = isToday ? " is-today" : "";
    const emptyCls = !hasCourses ? " empty-day" : "";

    let pills = "";
    TRACK_ORDER.forEach(t => {
      if (dayData[t]) {
        const m = TRACK_META[t];
        const entries = Array.isArray(dayData[t]) ? dayData[t] : [dayData[t]];
        entries.forEach(entry => {
          const title = entry.title.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
          pills += '<a href="'+entry.url+'" class="course-pill '+m.css+'" title="'+title+'">' +
            '<span class="pill-shape">'+m.shape+'</span>'+title+'</a>';
        });
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

    <div class="explainer">
      <p>Auto-generated daily workshops on what's happening in AI. Pick a session, open your agent, and follow along.</p>
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
                        help="Date string YYYY-MM-DD or YYYY-MM-DD-N (slot)")
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
