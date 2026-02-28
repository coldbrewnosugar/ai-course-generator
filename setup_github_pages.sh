#!/usr/bin/env bash
# setup_github_pages.sh — One-time setup to connect ~/ai-courses-site to GitHub Pages.
#
# Usage:
#   1. Create a GitHub repo (e.g. https://github.com/YOUR_USERNAME/ai-courses)
#   2. Run: bash setup_github_pages.sh YOUR_USERNAME ai-courses
#
# After this script, run_daily_course.sh will automatically push to GitHub Pages.

set -euo pipefail

GITHUB_USER="${1:?Usage: $0 <github_username> <repo_name>}"
REPO_NAME="${2:?Usage: $0 <github_username> <repo_name>}"
SITE_DIR="${HOME}/ai-courses-site"

echo "Setting up GitHub Pages: https://${GITHUB_USER}.github.io/${REPO_NAME}/"
echo "Site directory: ${SITE_DIR}"
echo ""

# Init git repo if not already
cd "${SITE_DIR}"
if [[ ! -d .git ]]; then
    git init
    git checkout -b main
    echo "✓ Initialized git repo"
else
    echo "  Git repo already initialized"
fi

# Set remote
REMOTE_URL="git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
if git remote get-url origin &>/dev/null; then
    git remote set-url origin "${REMOTE_URL}"
    echo "✓ Updated remote to ${REMOTE_URL}"
else
    git remote add origin "${REMOTE_URL}"
    echo "✓ Added remote: ${REMOTE_URL}"
fi

# Configure git identity
git config user.name  "AI Course Bot"
git config user.email "${GITHUB_USER}@users.noreply.github.com"
echo "✓ Git identity configured"

# Commit current index.html (if any)
if [[ -f index.html ]]; then
    git add -A
    if ! git diff --cached --quiet; then
        git commit -m "Initial site setup"
        echo "✓ Initial commit created"
    else
        echo "  Nothing to commit"
    fi
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Next steps:"
echo ""
echo "  1. Make sure the GitHub repo exists:"
echo "     https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo ""
echo "  2. Push to GitHub:"
echo "     cd ${SITE_DIR}"
echo "     git push -u origin main"
echo ""
echo "  3. Enable GitHub Pages in repo Settings:"
echo "     Settings → Pages → Branch: main → Folder: / (root)"
echo ""
echo "  4. Your site will be live at:"
echo "     https://${GITHUB_USER}.github.io/${REPO_NAME}/"
echo ""
echo "  5. For SSH authentication, ensure ~/.ssh/id_ed25519 is added"
echo "     to your GitHub account's SSH keys."
echo "════════════════════════════════════════════════════════"
