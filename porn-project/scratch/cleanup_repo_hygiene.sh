#!/usr/bin/env bash
# Run this yourself, in a real terminal (not through the agent) — the agent's
# sandbox mount blocks file deletion, so it couldn't run this itself.
# Generated 2026-08-03 as part of plans/improvements_audit.md §"Repo hygiene".
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Removing scraper/debug debris..."
rm -f temp_script.js test_page.html screenshot.png

echo "Removing editor backup files..."
rm -f AGENTS.md~ blacklist.txt~ "plans/ui_redesign.md~"
rm -f categories.json.save  # superseded by categories.json; kept as a .save so check first if unsure

echo "Removing legacy single-file UI (stubbed by the agent, safe to delete now)..."
rm -f z3ncoding_videos_grid.html z3ncoding_videos_grid.template.html

echo "Removing orphaned Vite build chunks (old content-hashed files from"
echo "repeated builds; only the ones referenced by dist/index.html are live)..."
KEEP=$(grep -o 'assets/[^"]*' frontend/dist/index.html 2>/dev/null | sed 's#assets/##' || true)
if [ -d frontend/dist/assets ]; then
  for f in frontend/dist/assets/*; do
    name=$(basename "$f")
    if ! grep -qx "$name" <<< "$KEEP"; then
      rm -f "$f"
    fi
  done
fi

echo ""
echo "Not touched — review manually before removing:"
echo "  .chrome_profile/   (34 dirs in project root; serve.py actually uses ~/.cache/porn-project-chrome-profile,"
echo "                      so this looks stale, but it's a full browser profile — check before rm -rf)"
echo ""
echo "Done."
