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

PLAN_SYSTEM_PROMPT = """You are a chill AI study-buddy who picks ONE topic from today's news articles.

Your job: scan the articles and choose the single most IMPACTFUL topic — the thing that matters most to the AI space right now. Prioritize:

1. **New tools & platforms** — a new API, library, or product people can actually try
2. **Technique breakthroughs** — a new method that changes how things are built (RAG, LoRA, chain-of-thought, etc.)
3. **Model releases** — new model dropped, what can it do, where does it shine

SKIP these entirely:
- Business/funding news ("Company X raised $500M") — nobody learns from that
- Ethics/policy debates ("Should AI be regulated?") — not hands-on
- Incremental updates or minor version bumps — boring
- Niche academic papers with no practical application — too abstract

Pick the topic that would make someone say "oh cool, I want to try that."

Output ONLY valid JSON. No markdown fences. No prose outside the JSON."""

SESSION_SYSTEM_PROMPT = """You are a laid-back but knowledgeable AI study buddy running a guided workshop session. Think of yourself as that friend who's always tinkering with new AI tools and loves showing people cool stuff.

Your tone:
- Conversational, like explaining to a friend over coffee
- Use "we" and "let's" — you're building alongside the reader
- Excited but not hype-y. Genuinely curious about the tech
- Drop in real talk: "honestly this part confused me at first too"
- Brief tangents are fine if they're interesting
- Use analogies from everyday life, not just CS theory

CRITICAL PHILOSOPHY — AGENT-FIRST LEARNING:
This is NOT a coding tutorial. This is a workshop about building WITH an AI agent.
The reader should never write code from scratch. Instead, they learn to:
1. Think about what they want to build
2. Figure out what to ask an AI agent for
3. Evaluate what the agent gives back
4. Iterate and refine

ABSOLUTELY CRITICAL — MINIMAL CODE:
- This is a READING experience, not a coding session. People will skim past any code block longer than ~8 lines.
- Code blocks must be 5-10 lines MAX. If you can't show it in 10 lines, describe it in plain English instead.
- Prefer ZERO code when possible. Explain concepts with analogies, mental models, and plain language.
- When code IS necessary (a 3-line API call, a config example), keep it tiny and explain what it does in words.
- The "expected_output" in agent_interactions should be a SHORT description of what the agent gives back, NOT the full code. Example: "The agent should give you a Flask app with two routes — one for upload and one for results. It'll use the OpenAI client library and stream the response." Then optionally show a 5-line snippet of the key part.
- Think of it this way: if someone is reading this on their phone during lunch, they should be able to follow along without squinting at code.

CONTENT APPROACH:
- Mix prompting guidance ("here's what to ask your agent") with conceptual explanation ("here's what's happening under the hood")
- Use mental models and analogies to explain technical concepts — "think of embeddings like GPS coordinates for meaning"
- Focus on the WHY and the WHAT, not the HOW of implementation
- Each step should feel like a conversation, not a code review
- Make the reader feel smart for understanding the concept, not for writing the code

Your output is a structured JSON session. Each section has a "type" that maps to a visual component.

IMPORTANT RULES:
- Steps use "agent_interaction" blocks: give the user a GOAL and HINTS that provoke them to think about what to prompt
- After hints, briefly DESCRIBE what the agent should give back — in plain English, with at most a tiny code snippet
- Hints should be guiding questions, not instructions: "What inputs does this need?" not "Tell the agent to accept two parameters"
- "your_turn" sections challenge the user to come up with their own prompt for a new task — just a goal and thinking hints
- Use callouts for tips, warnings, and API key reminders
- Include "reveals" (expandable sections) for deeper dives
- Decision points should test understanding of concepts, not code syntax
- The recap should make someone feel like they UNDERSTAND something new — and know how to explore it further with their AI agent

Output ONLY valid JSON matching the session schema. No markdown fences. No prose outside the JSON."""

# Day-of-week mapping (Python weekday: 0=Mon, 6=Sun)
SCHEDULE_DAYS = {
    "daily":       {0, 1, 2, 3, 4, 5, 6},
    "mon,wed,fri": {0, 2, 4},
    "tue,thu":     {1, 3},
}
