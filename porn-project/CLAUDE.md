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

# Refresh videos.json (scrapes profile, downloads thumbnails)
python generate_grid.py

# Build the React frontend (required before serve.py has anything to serve)
cd frontend && npm install && npm run build

# Serve the app at http://localhost:8888 (auto-opens Chrome)
python serve.py

# React dev server with hot reload (proxies /api and /thumbs to serve.py on 8888)
cd frontend && npm run dev

# Test yt-dlp format extraction
python test_api.py

# Test HLS proxy logic
python test_proxy.py

cd frontend && npm run lint   # oxlint
```

## Key Files

| File | Purpose |
|---|---|
| `generate_grid.py` | Scrapes Pornhub profile, downloads thumbnails to `thumbs/`, writes `videos.json` |
| `serve.py` | HTTP server (port 8888, binds `127.0.0.1` by default); serves `frontend/dist/`, exposes `/api/streams` (yt-dlp formats) and `/api/proxy` (allowlisted CORS proxy for HLS) |
| `frontend/` | React UI (Vite build to `frontend/dist/`) — the only supported frontend; see below |
| `categories.json` | Persists user video categories (public / least / average / most / pending / explode) |
| `blacklist.txt` | Viewkeys excluded from the grid |
| `manual_videos.json` | Manually added video entries |
| `first_seen.json` | Persistent, append-only viewkey → ISO date first observed. Powers "sort by date added"; can't be reconstructed if lost |
| `history.json` | Object keyed by viewkey: `{lastWatched, count, lastPosition}` — watch history + resume-playback position |

## Data Flow

```
Pornhub profile → generate_grid.py → videos.json + first_seen.json
                        ↓
                  thumbs/ (local thumbnail cache)

frontend/ (React, Vite) → npm run build → frontend/dist/

serve.py → serves frontend/dist/ at "/"
         → /api/streams  (yt-dlp extracts video formats, cached ~2h per URL)
         → /api/proxy    (proxies m3u8 for CORS; hostname allowlisted)
         → /api/<resource> (GET/POST categories, blacklist, videos, playlists, tags, history, first_seen)
```

## Frontend (React, `frontend/`)

The React+Vite "Cinematic Dark" UI (see `plans/ui_redesign.md` for the original spec) is the
**only** frontend as of 2026-08-03 — the legacy single-file `z3ncoding_videos_grid.html` /
`z3ncoding_videos_grid.template.html` were retired once this reached feature parity (folder
sync via the File System Access API, backup export/import, blacklist management, tag/playlist
browsing). See `plans/improvements_audit.md` for the full rationale and history. Stack: React 19,
Zustand (state), TanStack Virtual (virtualized grid), Framer Motion, Chart.js.

```
frontend/src/
  App.jsx        — root component
  components/    — UI components
  hooks/         — custom React hooks
  stores/useVideoStore.js — all app state (data, filtering, player, folder sync)
  utils/         — api.js (serve.py client), formatters.js, fsSync.js (File System Access)
```

`serve.py` serves `frontend/dist/index.html` at `/` and falls through to `/api/*` for data.
If `frontend/dist/index.html` is missing, `serve.py` prints a warning on startup — run
`npm run build` in `frontend/` first.

## serve.py API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/streams?url=<url>` | GET | yt-dlp format extraction (cached ~2h per URL) |
| `/api/proxy?url=<url>` | GET | CORS proxy for m3u8, hostname allowlisted (see `ALLOWED_PROXY_SUFFIXES` in serve.py) |
| `/api/<resource>` | GET | Read JSON/text data files |
| `/api/<resource>` | POST | Write JSON/text data files |

Resources: `categories`, `blacklist`, `videos`, `playlists`, `tags`, `history`, `first_seen`, `filter_presets`.

## Development Notes

- **Python environment:** Use `.venv` (Python 3.11). System Python is 3.14 and breaks ML/scraping deps.
- **Security:** `serve.py` binds `127.0.0.1` by default (set `BIND_HOST=0.0.0.0` to deliberately expose on LAN). `/api/proxy` only forwards to an allowlisted set of CDN hostnames — it is not an open proxy.
- **Caching:** `/thumbs/*` responses are sent with `Cache-Control: public, max-age=31536000, immutable`. Everything else (`/api/*`, the HTML shell) stays `no-store`.
- **Thumbnail caching:** `thumbs/` is ~650MB of cached images. Scraper checks local cache before fetching.
- **Pagination:** Scraper supports up to 100 pages; rate-limited at 1.5s between pages.
- **Category persistence:** Categories are stored in `categories.json` (server-side, via `/api/categories`) and optionally mirrored to a user-chosen folder via the File System Access API (`frontend/src/utils/fsSync.js`) if the user clicks "Connect Folder" in the sidebar.
- **Utility scripts** in `scratch/` are for bulk data manipulation; some predate the React migration and reference the retired `write_html_grid` function — check the top-of-file comments before running.
