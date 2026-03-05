#!/usr/bin/env bash
# run_daily_course.sh — Master orchestrator for Tinker (daily AI workshop generator)
#
# Fetches articles, scores them with Claude, generates sessions for qualifying
# articles, renders to HTML, and pushes to GitHub Pages.
# Designed to be called by cron at 5:30 AM daily.

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
LOG_DIR="${SCRIPT_DIR}/logs"
SITE_DIR="${HOME}/ai-courses-site"

DATE_STR=$(date +%Y-%m-%d)

LOG_FILE="${LOG_DIR}/course_${DATE_STR}.log"
mkdir -p "${LOG_DIR}"

# Redirect all output to log file AND stdout
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================"
echo "  Tinker — ${DATE_STR}"
echo "  Started at $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "============================================================"

# ── Python interpreter ─────────────────────────────────────────────────────────
if [[ -f "${VENV_PYTHON}" ]]; then
    PYTHON="${VENV_PYTHON}"
else
    PYTHON=$(command -v python3 || true)
    if [[ -z "${PYTHON}" ]]; then
        echo "ERROR: Python 3 not found. Aborting."
        exit 1
    fi
    echo "WARNING: venv not found, using system Python: ${PYTHON}"
fi
echo "Using Python: ${PYTHON}"

TRACK="general"
FAILED=0

echo ""
echo "── Step 1/5: Refreshing preferences from votes..."
"${PYTHON}" "${SCRIPT_DIR}/preferences.py" || echo "   WARNING: preferences.py failed (continuing anyway)"

echo ""
echo "── Step 2/5: Fetching RSS feeds..."
JSON_PATH=$("${PYTHON}" "${SCRIPT_DIR}/fetch_feeds.py" "${TRACK}" | tail -1)

if [[ -z "${JSON_PATH}" || ! -f "${JSON_PATH}" ]]; then
    echo "   ERROR: fetch_feeds.py did not produce a valid JSON file (got: '${JSON_PATH}')"
    exit 1
fi
echo "   Articles JSON: ${JSON_PATH}"

echo ""
echo "── Step 3/5: Scoring articles with Claude..."
SCORED_PATH=$("${PYTHON}" "${SCRIPT_DIR}/generate_course.py" "${TRACK}" "${JSON_PATH}" --score-only | tail -1)

if [[ -z "${SCORED_PATH}" || ! -f "${SCORED_PATH}" ]]; then
    echo "   ERROR: Scoring failed (got: '${SCORED_PATH}')"
    rm -f "${JSON_PATH}"
    exit 1
fi
echo "   Scored JSON: ${SCORED_PATH}"

# Read number of qualifying articles
NUM_SESSIONS=$("${PYTHON}" -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['count'])" "${SCORED_PATH}" 2>/dev/null || echo "0")
echo "   Qualifying articles: ${NUM_SESSIONS}"

if [[ "${NUM_SESSIONS}" -eq 0 ]]; then
    echo "   No articles met the scoring threshold. Skipping generation."
    rm -f "${JSON_PATH}" "${SCORED_PATH}"
    exit 0
fi

echo ""
echo "── Step 4/5: Generating ${NUM_SESSIONS} workshop sessions..."

exclude_topics=""
slot_failures=0

for slot in $(seq 1 "${NUM_SESSIONS}"); do
    echo "   ── Slot ${slot}/${NUM_SESSIONS}..."
    gen_start=$(date +%s)

    if [[ -n "${exclude_topics}" ]]; then
        SESSION_PATH=$("${PYTHON}" "${SCRIPT_DIR}/generate_course.py" "${TRACK}" "${SCORED_PATH}" --slot "${slot}" --exclude-topics "${exclude_topics}" | tail -1)
    else
        SESSION_PATH=$("${PYTHON}" "${SCRIPT_DIR}/generate_course.py" "${TRACK}" "${SCORED_PATH}" --slot "${slot}" | tail -1)
    fi
    gen_end=$(date +%s)
    echo "      Generation took $(( gen_end - gen_start ))s"

    if [[ -z "${SESSION_PATH}" || ! -f "${SESSION_PATH}" ]]; then
        echo "      WARNING: Slot ${slot} failed (got: '${SESSION_PATH}')"
        slot_failures=$(( slot_failures + 1 ))
        continue
    fi
    echo "      Session: ${SESSION_PATH}"

    # Extract the topic title from the session JSON to exclude from future slots
    topic_title=$("${PYTHON}" -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('session_title',''))" "${SESSION_PATH}" 2>/dev/null || true)
    if [[ -n "${topic_title}" ]]; then
        if [[ -n "${exclude_topics}" ]]; then
            exclude_topics="${exclude_topics}||${topic_title}"
        else
            exclude_topics="${topic_title}"
        fi
    fi
done

if [[ ${slot_failures} -eq ${NUM_SESSIONS} ]]; then
    echo "   ERROR: All ${NUM_SESSIONS} slots failed"
    FAILED=1
fi

echo ""
echo "── Step 5/5: Building HTML..."
for slot in $(seq 1 "${NUM_SESSIONS}"); do
    slot_date="${DATE_STR}-${slot}"
    "${PYTHON}" "${SCRIPT_DIR}/build_site.py" "${TRACK}" "${slot_date}" 2>/dev/null || true
done

# Cleanup temp JSON
rm -f "${JSON_PATH}" "${SCORED_PATH}"

echo ""
echo "── Summary ──────────────────────────────────────────────────"
echo "   Sessions attempted: ${NUM_SESSIONS}"
echo "   Slot failures:      ${slot_failures}"

if [[ ${FAILED} -eq 0 ]]; then
    echo ""
    echo "── Regenerating site index..."
    "${PYTHON}" "${SCRIPT_DIR}/build_site.py" --index-only || true

    # ── Git push to GitHub Pages ───────────────────────────────────────────────
    echo ""
    echo "── Pushing to GitHub Pages..."
    if [[ -d "${SITE_DIR}/.git" ]]; then
        cd "${SITE_DIR}"

        # Configure git identity if not already set
        git config user.name  "AI Course Bot" 2>/dev/null || true
        git config user.email "ai-course-bot@localhost" 2>/dev/null || true

        git add -A

        # Only commit if there are changes
        if git diff --cached --quiet; then
            echo "   No changes to commit."
        else
            COMMIT_MSG="Sessions: ${DATE_STR} | ${NUM_SESSIONS} sessions (scored)"
            git commit -m "${COMMIT_MSG}"
            git push
            echo "   Pushed to GitHub Pages"
        fi
        cd - > /dev/null
    else
        echo "   WARNING: ${SITE_DIR} is not a git repo — skipping push."
        echo "   Run the GitHub Pages setup steps first (see README)."
    fi
fi

echo ""
echo "============================================================"
echo "  Finished at $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "============================================================"

if [[ ${FAILED} -ne 0 ]]; then
    exit 1
fi
exit 0
