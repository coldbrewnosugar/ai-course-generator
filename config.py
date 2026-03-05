"""
Configuration for the Daily AI Course Generator.
All tracks, feeds, constants, and schedules defined here.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.expanduser("~/ai-courses")       # session JSON storage
SITE_DIR    = os.path.expanduser("~/ai-courses-site")  # GitHub Pages repo
LOG_DIR     = os.path.join(BASE_DIR, "logs")

# ── Fetch settings ─────────────────────────────────────────────────────────────
LOOKBACK_HOURS   = 30     # articles published within this window
MAX_ARTICLES     = 12     # cap per track per run
MAX_ARTICLE_CHARS = 3500  # truncate body at this length
USED_ARTICLES_PATH = os.path.join(os.path.expanduser("~/ai-courses"), "used_articles.json")
USED_ARTICLES_MAX_AGE_DAYS = 7  # forget articles after this many days

# ── Claude CLI settings ────────────────────────────────────────────────────────
SESSIONS_PER_DAY = 3  # number of different sessions to generate per track per day

CLAUDE_MODEL   = "claude-opus-4-6"
CLAUDE_TIMEOUT = 1800  # seconds (30 min — plenty of room for scheduled runs)

# ── Track definitions ──────────────────────────────────────────────────────────
TRACKS = {
    "general": {
        "label": "General AI",
        "schedule": "daily",
        "prompt_focus": (
            "Focus on large language models, model releases, research papers, "
            "and new tools/platforms. Prioritize understanding what's new, "
            "why it matters, and how someone could try it with an AI agent."
        ),
        "feeds": [
            # Tier 1 — technical / research
            {"url": "https://www.anthropic.com/rss.xml",                      "tier": 1, "name": "Anthropic"},
            {"url": "https://openai.com/blog/rss.xml",                        "tier": 1, "name": "OpenAI"},
            {"url": "https://deepmind.google/blog/rss/",                      "tier": 1, "name": "Google DeepMind"},
            {"url": "http://googleresearch.blogspot.com/atom.xml",            "tier": 1, "name": "Google Research"},
            {"url": "https://huggingface.co/blog/feed.xml",                   "tier": 1, "name": "Hugging Face"},
            {"url": "https://ai.meta.com/blog/rss/",                          "tier": 1, "name": "Meta AI"},
            {"url": "https://www.fast.ai/atom.xml",                           "tier": 1, "name": "fast.ai"},
            {"url": "https://sebastianraschka.com/rss_feed.xml",              "tier": 1, "name": "Sebastian Raschka"},
            {"url": "https://karpathy.github.io/feed.xml",                    "tier": 1, "name": "Andrej Karpathy"},
            {"url": "https://www.deeplearning.ai/the-batch/feed/",            "tier": 1, "name": "The Batch"},
            {"url": "https://lastweekin.ai/feed",                             "tier": 1, "name": "Import AI"},
            # Tier 1 — community / trending
            {"url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml", "tier": 1, "name": "GitHub Trending Python"},
            {"url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude&points=50", "tier": 1, "name": "Hacker News AI"},
            {"url": "https://hnrss.org/show?q=AI+OR+LLM&points=30",                    "tier": 1, "name": "HN Show"},
            # Tier 2 — journalism
            {"url": "https://www.technologyreview.com/feed/",                 "tier": 2, "name": "MIT Tech Review"},
            {"url": "https://www.wired.com/feed/tag/ai/rss",                  "tier": 2, "name": "Wired AI"},
            {"url": "https://lexfridman.com/feed/podcast/",                   "tier": 2, "name": "Lex Fridman"},
            {"url": "https://www.producthunt.com/feed?category=ai",           "tier": 2, "name": "Product Hunt AI"},
        ],
    },

    "image-gen": {
        "label": "Image & Video Generation",
        "schedule": "mon,wed,fri",
        "prompt_focus": (
            "Focus on diffusion models, image generation, video AI, and vision models. "
            "Cover new tools, techniques, and workflows. Prioritize things people can "
            "actually try — new models, new platforms, creative pipelines."
        ),
        "feeds": [
            {"url": "https://stability.ai/blog/rss.xml",                                    "tier": 1, "name": "Stability AI"},
            {"url": "https://huggingface.co/blog/feed.xml",                                 "tier": 1, "name": "Hugging Face"},
            {"url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",           "tier": 1, "name": "NVIDIA AI"},
            {"url": "https://paperswithcode.com/rss/trend/computer-vision",                 "tier": 1, "name": "Papers With Code CV"},
            {"url": "http://googleresearch.blogspot.com/atom.xml",                          "tier": 1, "name": "Google Research"},
            {"url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml",      "tier": 1, "name": "GitHub Trending Python"},
            {"url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude&points=50",    "tier": 1, "name": "Hacker News AI"},
            {"url": "https://www.technologyreview.com/feed/",                               "tier": 2, "name": "MIT Tech Review"},
            {"url": "https://www.wired.com/feed/tag/ai/rss",                               "tier": 2, "name": "Wired AI"},
        ],
    },

    "audio": {
        "label": "Audio AI",
        "schedule": "tue,thu",
        "prompt_focus": (
            "Focus on text-to-speech, speech-to-text, speech synthesis, music generation, "
            "and sound design AI. Cover new tools, models, and creative workflows. "
            "Prioritize things people can try — new APIs, new models, interesting applications."
        ),
        "feeds": [
            {"url": "https://elevenlabs.io/blog/rss",                         "tier": 1, "name": "ElevenLabs"},
            {"url": "https://www.assemblyai.com/blog/rss",                    "tier": 1, "name": "AssemblyAI"},
            {"url": "https://openai.com/blog/rss.xml",                        "tier": 1, "name": "OpenAI"},
            {"url": "https://huggingface.co/blog/feed.xml",                   "tier": 1, "name": "Hugging Face"},
            {"url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml", "tier": 1, "name": "GitHub Trending Python"},
            {"url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude&points=50", "tier": 1, "name": "Hacker News AI"},
            {"url": "https://www.technologyreview.com/feed/",                 "tier": 2, "name": "MIT Tech Review"},
        ],
    },
}

# ── GitHub repo for voting ───────────────────────────────────────────────────
GITHUB_REPO = "coldbrewnosugar/ai-course"

# ── System prompts ─────────────────────────────────────────────────────────────

PLAN_SYSTEM_PROMPT = """You are a technical editor selecting ONE topic from today's articles for a structured workshop session.

Your task: evaluate the articles and identify the single most significant development for practitioners in the AI field. Apply the following priority ranking:

1. **New tools and platforms** — a newly available API, library, or system with practical utility
2. **Technique advancements** — a novel method that materially improves existing workflows (RAG, LoRA, chain-of-thought, etc.)
3. **Model releases** — a newly published model with demonstrated capabilities or notable benchmarks

Exclude the following categories:
- Business or funding announcements — no educational value
- Policy or ethics commentary — outside scope
- Incremental version updates — insufficient substance
- Purely theoretical papers with no practical application

Select the topic with the highest combination of practical relevance and educational potential.

Output ONLY valid JSON. No markdown fences. No prose outside the JSON."""

SESSION_SYSTEM_PROMPT = """You are a technical author producing a structured workshop session. Write in an academic yet accessible register — precise, authoritative, and well-organized, comparable to a high-quality textbook or technical review article.

Your tone:
- Formal and precise. Avoid colloquialisms, filler phrases, and forced enthusiasm.
- Use clear, declarative sentences. State what something is and why it matters.
- First-person plural ("we") is acceptable when guiding the reader through a procedure.
- Employ precise technical vocabulary; define terms where necessary.
- Use analogies sparingly and only when they genuinely clarify a concept.
- Never use phrases like "so here's the deal", "let's dive in", "pretty cool", or similar informal language.

CRITICAL PHILOSOPHY — AGENT-FIRST LEARNING:
This is not a coding tutorial. It is a structured workshop on building WITH an AI agent.
The reader does not write code from scratch. Instead, they develop competence in:
1. Defining clear objectives for an AI agent
2. Formulating effective prompts to achieve those objectives
3. Evaluating and validating agent output
4. Iterating through refinement cycles

ABSOLUTELY CRITICAL — MINIMAL CODE:
- This is primarily a reading experience. Code blocks must not exceed 5-10 lines.
- Prefer zero code when possible. Explain concepts through precise prose and, where helpful, concise analogies.
- When code is necessary (an API call signature, a configuration example), keep it brief and accompany it with a clear prose explanation.
- The "expected_output" in agent_interactions should be a concise prose description of the agent's output, not full source code. Example: "The agent should produce a Flask application with two endpoints — one accepting file uploads and one returning analysis results — using the OpenAI client library with streaming enabled." A minimal code excerpt (3-5 lines) may follow if essential.
- The content should remain fully comprehensible without executing any code.

CONTENT APPROACH:
- Provide structured prompting guidance alongside conceptual exposition of underlying mechanisms.
- Explain technical concepts through precise definitions and, where appropriate, well-chosen analogies.
- Emphasize the rationale (why) and the architecture (what), not implementation minutiae (how).
- Each step should present a clear objective, relevant background, and systematic guidance.
- The reader should gain genuine understanding of the underlying concepts, not merely procedural knowledge.

Your output is a structured JSON session. Each section has a "type" that maps to a visual component.

IMPORTANT RULES:
- Steps use "agent_interaction" blocks: present the user with a GOAL and HINTS — guiding questions that develop the reader's reasoning about prompt construction.
- After hints, provide a concise prose description of the expected agent output, with at most a minimal code excerpt.
- Hints should be analytical questions, not directives: "What input parameters does this task require?" not "Tell the agent to accept two parameters."
- "your_turn" sections present a new challenge requiring independent prompt formulation — state the objective and provide guiding questions.
- Use callouts for technical notes, important caveats, and prerequisite reminders.
- Include "reveals" (expandable sections) for supplementary detail and deeper analysis.
- Decision points should assess conceptual understanding, not syntax recall.
- The recap should consolidate key concepts and identify clear avenues for further exploration.

Output ONLY valid JSON matching the session schema. No markdown fences. No prose outside the JSON."""

# Day-of-week mapping (Python weekday: 0=Mon, 6=Sun)
SCHEDULE_DAYS = {
    "daily":       {0, 1, 2, 3, 4, 5, 6},
    "mon,wed,fri": {0, 2, 4},
    "tue,thu":     {1, 3},
}
