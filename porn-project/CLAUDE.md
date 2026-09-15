# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This project follows a 3-layer architecture (see AGENTS.md for full detail):

1. **Directive Layer** — SOPs in Markdown files (`directives/`, `plans/`). Living documents; update them when you discover API constraints, better approaches, or edge cases.
2. **Orchestration Layer** — You (the AI). Read directives, route to execution scripts, handle errors, and self-anneal (fix → test → update directive).
3. **Execution Layer** — Deterministic Python scripts. Do not manually replicate what a script already does; check `scratch/` and the project root first.

**Before writing new code**, check if an existing script covers the task.

## Running the Project

```bash
# Use .venv Python, not system Python 3.14
source .venv/bin/activate   # or prefix commands with .venv/bin/python

python generate_grid.py     # Generate/refresh the video grid HTML
python serve.py             # Serve the grid locally (auto-opens Chrome)
python test_api.py          # Test yt-dlp format extraction
python test_proxy.py        # Test HLS proxy logic
```

## Data Flow

```
Pornhub profile → generate_grid.py → z3ncoding_videos_grid.html
                        ↓
                  thumbs/ (local thumbnail cache)

serve.py → /api/streams  (yt-dlp extracts video formats)
         → /api/proxy    (proxies m3u8 / MP4 for CORS)
```

## Frontend (React, `frontend/`)

The React+Vite app is the primary UI. `serve.py` serves `frontend/dist` at `/`,
falling back to the project root for `/thumbs/*`, the legacy grid, and data files
(see `plans/consolidation.md`). Vite builds with `base: "./"`, so moving the bundle
needs no rebuild.

- `python serve.py` opens the React app; `--legacy` opens the old generated grid.
- After changing anything in `frontend/src/`, run `npm run build` in `frontend/` —
  `serve.py` serves the built `dist`, not the dev server.
- `npm run dev` (port 5173) proxies `/api` and `/thumbs` to 8888 for hot reload.

## Development Notes

- **Python environment:** Use `.venv` (Python 3.11). System Python is 3.14 and breaks ML/scraping deps.
- **Legacy grid (being retired):** `z3ncoding_videos_grid.template.html` is the old UI; `z3ncoding_videos_grid.html` is regenerated from it by `generate_grid.py` and should not be hand-edited. Reachable via `serve.py --legacy`.
- **Thumbnail caching:** `thumbs/` is ~794MB across ~29.5k images (~20k are orphans from removed videos; see `plans/consolidation.md`). Scraper checks local cache before fetching.
- **Pagination:** Scraper supports up to 100 pages; rate-limited at 1.5s between pages.
- **Category persistence:** Categories are stored in both `categories.json` (server-side) and `localStorage` (client-side); the HTML UI exports/imports between them.
- **Utility scripts** in `scratch/` are for bulk data manipulation (category edits, template regeneration); run them directly as needed.
