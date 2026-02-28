# AI Course Generator

Automatically fetches the latest AI research and news daily, synthesizes it into hands-on ~2-hour Jupyter Notebook courses, and publishes them to GitHub Pages.

**Live site:** https://coldbrewnosugar.github.io/ai-course/

---

## How It Works

Every day at 5:30 AM the server:
1. Fetches articles from curated RSS feeds
2. Sends them to Claude (via `claude -p`) to generate a structured Jupyter Notebook
3. Converts the notebook to HTML
4. Pushes to GitHub Pages

---

## Course Tracks

| Track | Schedule | Focus |
|-------|----------|-------|
| **General AI** | Daily | LLMs, model releases, research, coding |
| **Image & Video Generation** | Mon / Wed / Fri | Diffusion models, image/video gen, vision |
| **Audio AI** | Tue / Thu | TTS, STT, music generation, speech |

---

## File Structure

```
ai-course/
├── config.py            # Tracks, RSS feeds, Claude system prompts, constants
├── fetch_feeds.py       # RSS ingestion + article body extraction
├── generate_course.py   # Claude CLI call + Jupyter Notebook builder
├── build_site.py        # nbconvert → HTML + index.html generator
├── run_daily_course.sh  # Daily orchestrator (fetch → generate → build → push)
├── setup_github_pages.sh
└── requirements.txt
```

---

## Making Changes

This repo is designed so you can describe changes in plain English to Claude Code and it will create a branch, make the edits, open a PR, and push — you just review and merge.

### Examples of things you can ask Claude Code to do

**Styling:**
> "Make the course index page use a light theme instead of dark"
> "Add a search bar to the index page"
> "Make the track cards show a preview of the first paragraph"

**Content:**
> "Add a new RSS feed from Simon Willison's blog to the General AI track"
> "Make the course exercises harder — add a second challenge problem to each section"
> "Change the quiz format to use inline answers instead of hidden details tags"

**Tracks:**
> "Add a new track for AI Agents — runs on Saturdays, focused on tool use and agentic frameworks"

**Prompts:**
> "Make the General AI system prompt focus more on practical coding and less on theory"

### Workflow

When you ask Claude Code for a change it will:
1. Create a branch (e.g. `improve-styling`)
2. Edit the relevant files
3. Commit with a descriptive message
4. Push the branch
5. Open a Pull Request on GitHub

You review the PR at `github.com/coldbrewnosugar/ai-course-generator/pulls`, merge it, and the change takes effect on the next scheduled run.

To apply a change immediately after merging:
```bash
bash /home/umbrel/claude/ai-course/run_daily_course.sh
```

---

## Manual Run

```bash
bash /home/umbrel/claude/ai-course/run_daily_course.sh
```

Logs are written to `/home/umbrel/claude/ai-course/logs/course_YYYY-MM-DD.log`.

---

## Dependencies

- Python venv at `.venv/` — install with `uv pip install -r requirements.txt`
- [Claude Code](https://claude.ai/code) — `claude` CLI must be on PATH
- Systemd user timer — runs at 05:30 UTC daily

---

## Repos

| Repo | Purpose |
|------|---------|
| [`ai-course-generator`](https://github.com/coldbrewnosugar/ai-course-generator) | This repo — source code, edit here |
| [`ai-course`](https://github.com/coldbrewnosugar/ai-course) | Generated HTML output — do not edit manually |
