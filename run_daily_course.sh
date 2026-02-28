#!/usr/bin/env bash
# run_daily_course.sh — Master orchestrator for the Daily AI Course Generator
#
# Runs all tracks scheduled for today, converts to HTML, pushes to GitHub Pages.
# Designed to be called by cron at 5:30 AM daily.

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
LOG_DIR="${SCRIPT_DIR}/logs"
SITE_DIR="${HOME}/ai-courses-site"

DATE_STR=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)   # 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun

LOG_FILE="${LOG_DIR}/course_${DATE_STR}.log"
mkdir -p "${LOG_DIR}"

# Redirect all output to log file AND stdout
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================"
echo "  AI Course Generator — ${DATE_STR} (day=${DAY_OF_WEEK})"
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

# ── Track schedule ─────────────────────────────────────────────────────────────
# Returns true (exit 0) if track should run today
should_run_track() {
    local track="$1"
    case "${track}" in
        general)
            return 0  # daily
            ;;
        image-gen)
            # Mon=1, Wed=3, Fri=5
            if [[ "${DAY_OF_WEEK}" == "1" || "${DAY_OF_WEEK}" == "3" || "${DAY_OF_WEEK}" == "5" ]]; then
                return 0
            fi
            return 1
            ;;
        audio)
            # Tue=2, Thu=4
            if [[ "${DAY_OF_WEEK}" == "2" || "${DAY_OF_WEEK}" == "4" ]]; then
                return 0
            fi
            return 1
            ;;
        *)
            echo "WARNING: Unknown track '${track}'"
            return 1
            ;;
    esac
}

# ── Process one track ──────────────────────────────────────────────────────────
run_track() {
    local track="$1"
    echo ""
    echo "── Track: ${track} ──────────────────────────────────────────────"
    echo "   Step 1/3: Fetching RSS feeds..."

    # fetch_feeds.py prints the JSON output path to stdout
    JSON_PATH=$("${PYTHON}" "${SCRIPT_DIR}/fetch_feeds.py" "${track}" | tail -1)

    if [[ -z "${JSON_PATH}" || ! -f "${JSON_PATH}" ]]; then
        echo "   ERROR: fetch_feeds.py did not produce a valid JSON file (got: '${JSON_PATH}')"
        return 1
    fi
    echo "   Articles JSON: ${JSON_PATH}"

    echo "   Step 2/3: Generating course notebook..."
    NB_PATH=$("${PYTHON}" "${SCRIPT_DIR}/generate_course.py" "${track}" "${JSON_PATH}" | tail -1)

    if [[ -z "${NB_PATH}" || ! -f "${NB_PATH}" ]]; then
        echo "   ERROR: generate_course.py did not produce a notebook (got: '${NB_PATH}')"
        rm -f "${JSON_PATH}"
        return 1
    fi
    echo "   Notebook: ${NB_PATH}"

    echo "   Step 3/3: Building HTML..."
    "${PYTHON}" "${SCRIPT_DIR}/build_site.py" "${track}" "${DATE_STR}"

    # Cleanup temp JSON
    rm -f "${JSON_PATH}"
    echo "   ✓ Track '${track}' complete"
}

# ── Main loop ──────────────────────────────────────────────────────────────────
TRACKS_RUN=()
TRACKS_SKIPPED=()
TRACKS_FAILED=()

for track in general image-gen audio; do
    if should_run_track "${track}"; then
        if run_track "${track}"; then
            TRACKS_RUN+=("${track}")
        else
            echo "   FAILED: ${track}"
            TRACKS_FAILED+=("${track}")
        fi
    else
        echo "   Skipping '${track}' (not scheduled today)"
        TRACKS_SKIPPED+=("${track}")
    fi
done

echo ""
echo "── Summary ──────────────────────────────────────────────────"
echo "   Completed:  ${TRACKS_RUN[*]:-none}"
echo "   Skipped:    ${TRACKS_SKIPPED[*]:-none}"
echo "   Failed:     ${TRACKS_FAILED[*]:-none}"

# Regenerate index with all tracks
if [[ ${#TRACKS_RUN[@]} -gt 0 ]]; then
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
            COMMIT_MSG="Courses: ${DATE_STR} | tracks: ${TRACKS_RUN[*]}"
            git commit -m "${COMMIT_MSG}"
            git push
            echo "   ✓ Pushed to GitHub Pages"
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

# Exit non-zero if any tracks failed
if [[ ${#TRACKS_FAILED[@]} -gt 0 ]]; then
    exit 1
fi
exit 0
