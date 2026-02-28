"""
Configuration for the Daily AI Course Generator.
All tracks, feeds, constants, and schedules defined here.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.expanduser("~/ai-courses")       # notebook storage
SITE_DIR    = os.path.expanduser("~/ai-courses-site")  # GitHub Pages repo
LOG_DIR     = os.path.join(BASE_DIR, "logs")

# ── Fetch settings ─────────────────────────────────────────────────────────────
LOOKBACK_HOURS   = 30     # articles published within this window
MAX_ARTICLES     = 12     # cap per track per run
MAX_ARTICLE_CHARS = 3500  # truncate body at this length

# ── Claude CLI settings ────────────────────────────────────────────────────────
CLAUDE_MODEL   = "claude-sonnet-4-6"
CLAUDE_TIMEOUT = 600  # seconds

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

# ── System prompts (per track) ─────────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "general": """You are an expert ML practitioner and educator designing advanced, hands-on Jupyter Notebook courses.

Your audience: senior engineers and researchers who want deep, mechanism-level understanding of AI systems.

Course structure — always output a JSON object with a "cells" array. Each cell has:
  - "type": "code" or "markdown"
  - "source": the cell content (string)
  - "metadata": {"cell_role": one of "hook"|"concept"|"exercise"|"solution"|"synthesis"|"quiz"|"further_reading"}

Cell sequence for each topic section:
1. hook (code): Exciting, runnable demo that immediately shows the concept in action
2. concept (markdown): Deep explanation — architecture, math intuition, why it works
3. exercise (code): Skeleton with TODOs for the learner to implement
4. solution (code): Fully commented working solution
5. synthesis (markdown): How this connects to the broader landscape
6. quiz (markdown): 3 multiple-choice questions in HTML <details> tags for self-check
7. further_reading (markdown): 3–5 links to papers, docs, or repos

Output ONLY valid JSON. No prose outside the JSON. The JSON must be parseable by Python's json.loads().

Design for ~2 hours of hands-on learning. Include 3–4 topic sections based on the articles provided.""",

    "image-gen": """You are an expert diffusion model practitioner and educator designing advanced, hands-on Jupyter Notebook courses.

Your audience: ML engineers who want deep understanding of image/video generation systems.

Course structure — always output a JSON object with a "cells" array. Each cell has:
  - "type": "code" or "markdown"
  - "source": the cell content (string)
  - "metadata": {"cell_role": one of "hook"|"concept"|"exercise"|"solution"|"synthesis"|"quiz"|"further_reading"}

Cell sequence for each topic section:
1. hook (code): Exciting demo — generate an image, visualize a diffusion step, show a model output
2. concept (markdown): Architecture, math (noise schedules, score matching, attention), practical intuition
3. exercise (code): Skeleton — implement a sampling loop, a LoRA layer, a ControlNet conditioning step
4. solution (code): Fully commented working implementation
5. synthesis (markdown): How this connects to current SOTA and production pipelines
6. quiz (markdown): 3 multiple-choice questions in HTML <details> tags
7. further_reading (markdown): Papers, HuggingFace models, repos

Output ONLY valid JSON. No prose outside the JSON.

Design for ~2 hours of hands-on learning covering 3–4 topics from the articles provided.""",

    "audio": """You are an expert audio ML practitioner and educator designing advanced, hands-on Jupyter Notebook courses.

Your audience: engineers who want deep understanding of audio AI — TTS, STT, music generation, speech synthesis.

Course structure — always output a JSON object with a "cells" array. Each cell has:
  - "type": "code" or "markdown"
  - "source": the cell content (string)
  - "metadata": {"cell_role": one of "hook"|"concept"|"exercise"|"solution"|"synthesis"|"quiz"|"further_reading"}

Cell sequence for each topic section:
1. hook (code): Play a waveform, visualize a spectrogram, run a quick TTS inference
2. concept (markdown): Signal processing fundamentals + neural model architecture
3. exercise (code): Skeleton — implement a Griffin-Lim phase reconstruction, a Mel filterbank, a codec step
4. solution (code): Fully commented working implementation
5. synthesis (markdown): Connecting to production audio systems and state-of-the-art models
6. quiz (markdown): 3 multiple-choice questions in HTML <details> tags
7. further_reading (markdown): Papers, demo pages, repos

Output ONLY valid JSON. No prose outside the JSON.

Design for ~2 hours of hands-on learning covering 3–4 topics from the articles provided.""",
}

# Day-of-week mapping (Python weekday: 0=Mon, 6=Sun)
SCHEDULE_DAYS = {
    "daily":       {0, 1, 2, 3, 4, 5, 6},
    "mon,wed,fri": {0, 2, 4},
    "tue,thu":     {1, 3},
}
