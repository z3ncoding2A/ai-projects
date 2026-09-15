# Frontend Consolidation & Server Performance

## Objective
Retire the generated 4 MB HTML grid in favour of the React app in `frontend/`,
and fix the server-side policies that made the library feel slow: blanket
`no-store` caching, uncompressed API payloads, and per-request re-parsing of
`videos.json`.

## Background

The project carried two UIs in parallel:

| | `z3ncoding_videos_grid.html` (legacy) | `frontend/` (React) |
|---|---|---|
| Data loading | 9,397 videos inline on one 4 MB line | `/api/videos`, virtualized |
| DOM nodes | every card materialized | 40 rendered of 9,397 |
| Features | grid, search, flat categories | queue, mini-player, theater mode, category *tree*, inspector, stats, bulk select, keyboard nav |

The legacy file's problem is data architecture, not styling: `const ALL_VIDEOS = [...]`
forces the browser to parse 4 MB of JavaScript before first paint, and every
regeneration rewrites the whole file. CSS work cannot fix that, so the React app
is the consolidation target.

`CLAUDE.md` described the React app as "not yet wired into the Python server".
That was stale — `frontend/src/utils/api.js` already targeted the exact `/api/*`
resources `serve.py` serves. The app was reachable at `/frontend/dist/index.html`
but broken there: cards emit `src="thumbs/<id>.jpg"` relative, which from that
subdirectory resolved to `/frontend/dist/thumbs/` → 404. Every local thumbnail
rendered as a blank rectangle.

## Completed

### 1. Serve the React app at "/"  (`serve.py`)
`translate_path` now resolves static requests against `frontend/dist` first and
the project root second. Vite builds with `base: "./"`, so relative asset paths
resolve correctly from the root — **no rebuild required**.

- `ROOT_OWNED_PREFIXES = ("thumbs/",)` keeps `/thumbs/*` pinned to the project
  root, which is what fixes the blank thumbnails.
- `/z3ncoding_videos_grid.html` and the JSON data files still resolve from root,
  so nothing that previously worked broke.
- `super().translate_path()` runs first, so its `..` sanitization still applies
  before anything is joined onto `FRONTEND_DIST`.
- Startup opens `/` by default; `--legacy` opens the old grid. If
  `frontend/dist/index.html` is missing, it warns and falls back to legacy.
- The printed URL now uses `BIND_HOST` — it previously advertised `localhost`,
  which never reached a server bound to the Tailscale IP.

### 2. Cache headers by content lifetime  (`serve.py`)
`end_headers` previously stamped `no-cache, no-store, must-revalidate` on *every*
response, including 794 MB of thumbnails — so every scroll re-downloaded images.
Replaced with `_cache_control()`:

| Path | Policy | Why |
|---|---|---|
| `/thumbs/*`, `/assets/*` | `public, max-age=31536000, immutable` | thumbs are named by viewkey; Vite asset names are content-hashed |
| `/api/*` | `no-store` | mutates on every categorization |
| everything else | `no-cache` | HTML entry points: cache but always revalidate (enables 304) |

`send_response` is overridden to record the status code so error responses are
never marked immutable.

### 3. gzip + in-memory payload cache  (`serve.py`)
`_read_json_file` ran per request, so every `/api/videos` hit re-read and
re-parsed ~6 MB from disk and re-serialized it, uncompressed, under
`ThreadingTCPServer`.

`_cached_payload()` caches the serialized *and* gzipped bytes keyed on
`(st_mtime_ns, st_size)`, so a write to the underlying file invalidates the
entry automatically; POST also calls `_invalidate_payload()` explicitly. The
payload is built outside the lock — a cold-cache race duplicates work rather
than blocking every request behind a 6 MB parse.

**Measured on `/api/videos`:** wire size dropped from 5,511,772 B to
1,306,944 B — a 4.2× reduction, and the figure that matters, since the server is
reached over Tailscale rather than loopback. Warm-cache responses complete in
~16 ms locally vs ~160 ms uncompressed, but both are loopback numbers dominated
by writing 5.5 MB into a socket; treat the wire size as the real win.

## Verification performed
- `/` serves the SPA; `/assets/*`, `/thumbs/*`, `/z3ncoding_videos_grid.html` all 200.
- Cache-Control confirmed per-path; `If-Modified-Since` on a thumb returns 304.
- gzip confirmed via `Content-Encoding` + `Vary: Accept-Encoding`.
- POST→GET round-trip on `/api/tags` confirmed cache invalidation (sentinel value
  appeared immediately), then restored.
- Headless Chromium render of `/` against the full dataset: 40 cards virtualized
  out of 9,397, thumbnails loading.

`plans/ui_redesign.md` is obsolete: it specifies a redesign of the generated
HTML grid this plan retires. Left in place as history.

## Remaining

### 4. Thumbnail pipeline (not started)
`thumbs/` is 794 MB across 29,506 files, largest 560 KB, served into cards ~320 px wide.
- **~20,000 orphans.** 29,506 files for 9,397 videos, with no preview-rotation
  suffixes (all flat `<id>.jpg`) — leftovers from removed/blacklisted videos.
  A prune script keyed on `videos.json` viewkeys reclaims most of the disk.
- **No resizing.** Downscaling to 480px WebP should cut the remainder ~10×.

Do the prune first; it is non-destructive to the app and shrinks the input to
the resize step.

### 5. `HEAD /api/*` returns 404
`do_GET` handles `/api/`, but `do_HEAD` falls through to
`SimpleHTTPRequestHandler`, which looks for a file on disk. Harmless today —
`/api/*` is `no-store`, so nothing revalidates — but worth routing for
correctness.

**If you route `do_HEAD` to the API handler, you must also restore a
`if self.command != "HEAD"` guard around the `self.wfile.write(body)` in
`_send_bytes`.** It is currently absent because that path is unreachable; adding
the route without the guard would write a body on a HEAD response and
desynchronize the connection.

### 6. Retire the legacy grid
Once the React app has run as the default for a while, `generate_grid.py` can
drop `write_html_grid` and become a pure data exporter, and
`z3ncoding_videos_grid{,.template}.html` can be deleted.
