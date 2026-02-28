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
CLAUDE_MODEL   = "claude-opus-4-6"
CLAUDE_TIMEOUT = 1800  # seconds (30 min — plenty of room for scheduled runs)

# ── Track definitions ──────────────────────────────────────────────────────────
TRACKS = {
    "general": {
        "label": "General AI",
        "schedule": "daily",
        "prompt_focus": (
            "Focus on large language models, model releases, research papers, "
            "and coding advances. Prioritize implementation-level understanding, "
            "architectural insights, and practical coding exercises."
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
            # Tier 2 — journalism
            {"url": "https://www.technologyreview.com/feed/",                 "tier": 2, "name": "MIT Tech Review"},
            {"url": "https://www.wired.com/feed/tag/ai/rss",                  "tier": 2, "name": "Wired AI"},
            {"url": "https://lexfridman.com/feed/podcast/",                   "tier": 2, "name": "Lex Fridman"},
        ],
    },

    "image-gen": {
        "label": "Image & Video Generation",
        "schedule": "mon,wed,fri",
        "prompt_focus": (
            "Focus on diffusion models, image generation, video AI, and vision models. "
            "Cover architecture details, sampling methods, ControlNet/LoRA fine-tuning, "
            "and practical generation pipelines. Include hands-on exercises using "
            "diffusers or similar libraries."
        ),
        "feeds": [
            {"url": "https://stability.ai/blog/rss.xml",                                    "tier": 1, "name": "Stability AI"},
            {"url": "https://huggingface.co/blog/feed.xml",                                 "tier": 1, "name": "Hugging Face"},
            {"url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",           "tier": 1, "name": "NVIDIA AI"},
            {"url": "https://paperswithcode.com/rss/trend/computer-vision",                 "tier": 1, "name": "Papers With Code CV"},
            {"url": "http://googleresearch.blogspot.com/atom.xml",                          "tier": 1, "name": "Google Research"},
            {"url": "https://www.technologyreview.com/feed/",                               "tier": 2, "name": "MIT Tech Review"},
            {"url": "https://www.wired.com/feed/tag/ai/rss",                               "tier": 2, "name": "Wired AI"},
        ],
    },

    "audio": {
        "label": "Audio AI",
        "schedule": "tue,thu",
        "prompt_focus": (
            "Focus on text-to-speech, speech-to-text, speech synthesis, music generation, "
            "and sound design AI. Cover signal processing fundamentals, neural audio models, "
            "codec architectures, and practical exercises using libraries like transformers, "
            "torchaudio, or speechbrain."
        ),
        "feeds": [
            {"url": "https://elevenlabs.io/blog/rss",                         "tier": 1, "name": "ElevenLabs"},
            {"url": "https://www.assemblyai.com/blog/rss",                    "tier": 1, "name": "AssemblyAI"},
            {"url": "https://openai.com/blog/rss.xml",                        "tier": 1, "name": "OpenAI"},
            {"url": "https://huggingface.co/blog/feed.xml",                   "tier": 1, "name": "Hugging Face"},
            {"url": "https://www.technologyreview.com/feed/",                 "tier": 2, "name": "MIT Tech Review"},
        ],
    },
}

# ── System prompts ─────────────────────────────────────────────────────────────

PLAN_SYSTEM_PROMPT = """You are a chill AI study-buddy who picks ONE buildable topic from today's news articles.

Your job: scan the articles and choose the single most interesting, hands-on topic that someone could actually build something with. Think "weekend hack night" energy, not "enterprise architecture review."

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

Your output is a structured JSON session. Each section has a "type" that maps to a visual component.

IMPORTANT RULES:
- NEVER include raw code for the user to write. All code appears only as "expected agent output" — what Claude/ChatGPT would give back
- Steps use "agent_interaction" blocks: give the user a GOAL and HINTS that provoke them to think about what to prompt, then show what a good agent response looks like
- Hints should be guiding questions, not instructions: "What inputs does this need?" not "Tell the agent to accept two parameters"
- "your_turn" sections challenge the user to come up with their own prompt for a new task — no starter code, just a goal and thinking hints
- Use callouts for tips, warnings, and especially API key reminders
- Include "reveals" (expandable sections) for deeper dives that might break the flow
- Decision points should test understanding of when/how to use AI agents effectively
- The recap should make someone feel like they built something real — using AI as their collaborator

Output ONLY valid JSON matching the session schema. No markdown fences. No prose outside the JSON."""

# Day-of-week mapping (Python weekday: 0=Mon, 6=Sun)
SCHEDULE_DAYS = {
    "daily":       {0, 1, 2, 3, 4, 5, 6},
    "mon,wed,fri": {0, 2, 4},
    "tue,thu":     {1, 3},
}
