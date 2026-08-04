# Webpage Improvements — Audit & Ranked Proposal

Audited 2026-08-03. Covers `z3ncoding_videos_grid.template.html` (2,165 lines), `serve.py` (394),
`generate_grid.py` (583), and `frontend/` (~2,140 lines React).

---

## 0. Correction: the React migration is already live

`CLAUDE.md` says the React frontend is "not yet wired into the Python server." That is no longer true:

- `serve.py:22` — `FILE = "index.html" if frontend/dist/index.html exists else z3ncoding_videos_grid.html`
- `serve.py` serves `frontend/dist/index.html` at `/` and `frontend/dist/assets/*` at `/assets/*`
- `frontend/dist/` is built (Aug 2) — 389 KB JS + 19 KB CSS

**So `python serve.py` already opens the React app, not the legacy grid.** The legacy HTML is only
reachable by explicit URL. This changes the priority of everything below: most legacy-template bugs
are only worth fixing if you intend to keep that file alive.

**Decision to make first:** commit to React and retire the template, or keep both. Maintaining both is
the direct cause of the rot listed in §1 — those bugs sat undetected because the page isn't the one
being opened.

---

## 1. Broken code in the legacy template (free wins, ~1 hour total)

Ranked by severity. All are real, verified defects — not style opinions.

| # | Issue | Location | Effect |
|---|---|---|---|
| 1 | `renderGrid()` is called but **never defined anywhere in the file** | lines 1996, 2014 | Bulk-select mode throws `ReferenceError` on every click and on Cancel. Bulk mode is entirely non-functional. |
| 2 | `saveCategories()` is called but **never defined** | lines 1947, 2026 | "Apply" in the bulk bar and backup import both throw before persisting. Changes are lost. |
| 3 | `toggleSelection(v[8])` invoked with 1 arg; signature is `(viewkey, index, shiftKey)` | 1147 vs 2001 | `index`/`shiftKey` are `undefined` → shift-click range select never works, `lastClickedIndex` is always `undefined`. |
| 4 | `startPreview()` reads `wrap.getAttribute('data-preview')`, but `createVideoItem` never sets that attribute — and `videos.json` has no preview field at all | 1225 vs 1119 | The entire ~60-line frame-rotation hover-preview engine is dead code. Nothing ever animates. |
| 5 | Category dot uses raw `v[9]` instead of `getVideoCategory(v)` | 1115 | The colored dot shows the *baked-in* category and ignores your localStorage edits until you re-run `generate_grid.py`. |
| 6 | `categories` is assigned at line 1086 but **never declared** (`let`/`const`/`var`) | 1086 | Implicit global — works only in sloppy mode. Adding `"use strict"` or converting to a module breaks the page instantly. |
| 7 | Scraped titles interpolated raw into `innerHTML` and into `onclick="…'${v[8]}'"` | 1129–1141 | Any title containing `'`, `"`, `<`, or `&` corrupts the card markup. With 8,103 scraped titles this is happening today. |
| 8 | Auto-next is a fixed `setTimeout(duration + 2s)` | 1463–1467 | Fires while you're paused, scrubbed back, or watching a shorter iframe ad-roll. Skips to the next video mid-watch. |

**Fix cost:** #1–#3 and #5–#6 are one-liners to a few lines each. #4 needs either a `preview` field
added to the scraper output or deletion of the dead engine. #7 needs an `escapeHtml()` helper + moving
to `addEventListener` instead of inline `onclick`. #8 should hook `nativePlayer.onended` (already
wired) and drop the timer for the native path.

---

## 2. Performance / scale

Current numbers: **8,103 videos**, 5.2 MB `videos.json`, 3.7 MB generated HTML, **658 MB** in `thumbs/`,
11,052 category assignments (6,916 `recommended` + 3,622 `related` dominate).

### 2.1 Stop inlining the dataset — **highest impact, lowest effort**

`generate_grid.py:460` substitutes the whole 5.2 MB array into `__VIDEOS_JSON_DATA__`. The browser must
parse 8,103 × 12 nested JS array literals before a single pixel renders — JS-literal parsing is
substantially slower than `JSON.parse` on the same bytes.

`GET /api/videos` **already exists** in `serve.py`. Swapping the inline blob for a fetch drops the HTML
from 3.7 MB to roughly 90 KB and lets the page paint its shell immediately. *~30 min.*

### 2.2 Cache thumbnails

`serve.py:35–38` sets `Cache-Control: no-cache, no-store, must-revalidate` on **every** response,
including `/thumbs/*`. Every reload re-fetches every visible thumbnail from a 658 MB directory.
Restrict no-store to `/api/*` and send `Cache-Control: public, max-age=31536000, immutable` for
`/thumbs/*`. *~15 min, very noticeable.*

### 2.3 Virtualize the list (legacy only)

`renderNextBatch` appends 50 items at a time and never removes any. Opening the `recommended` tab and
scrolling produces up to 6,916 live DOM nodes plus their `<img>` elements. The React version already
uses `@tanstack/react-virtual` with `overscan: 5` — this is the single strongest argument for
retiring the template rather than patching it.

### 2.4 Cache yt-dlp stream extraction

`_get_streams` spawns a `yt-dlp` subprocess per play (30 s timeout, typically 2–5 s). Re-playing the
same video re-runs it. An in-process dict keyed by URL with a ~2 h TTL makes replays instant. *~20 min.*

### 2.5 Cheaper filtering

`filterAndSort` re-filters **and re-sorts** all 8,103 entries on every debounced keystroke. Skip the
sort when only the query changed, and precompute the tab→viewkey index once. Real but second-order
next to 2.1–2.3.

### 2.6 Range requests

`/api/proxy` forwards neither the client's `Range` header nor `Accept-Ranges`. Fine for HLS segments,
but it means a direct-MP4 fallback path can never seek. Worth fixing only if you re-enable MP4 formats
(currently skipped at `serve.py:_get_streams`, "Skip direct MP4s").

---

## 3. Security — worth doing regardless of the rest

`serve.py:BIND_HOST` defaults to `0.0.0.0`. Two consequences on any shared or untrusted network:

1. **`/api/proxy?url=` is an unauthenticated open proxy.** Anyone who can reach port 8888 can route
   arbitrary traffic through your machine, including to `127.0.0.1` and other LAN hosts (classic SSRF).
2. **`POST /api/<resource>` is unauthenticated write access** to `categories.json`, `blacklist.txt`,
   `playlists.json`, `tags.json`, `history.json`. Anyone on the LAN can wipe 11,052 category assignments.

Given the nature of this library, the LAN exposure is also a privacy issue in itself.

**Fix:** default `BIND_HOST` to `127.0.0.1` (keep the env-var override for deliberate LAN use), and
allowlist proxy target hostnames to the CDN domains you actually stream from. *~20 min.*

---

## 4. New features, ranked by value-per-effort

| Feature | Why | Effort |
|---|---|---|
| **Resume playback position** | `history.json` already tracks 129 watched viewkeys as a flat list. Storing `{viewkey: seconds}` instead gives resume + a progress bar on each card. | S |
| **Duplicate detection** | 8,103 entries built from profile + related + recommended crawls; the same video almost certainly appears under multiple viewkeys. Fuzzy-match on normalized title + duration, offer a merge/blacklist pass. | M |
| **Browse by tag** | Tags are addable in the details modal and persisted to `tags.json`, but there is **no way to filter or browse by them**. The feature is currently write-only. | S |
| **Playlists as a playback source** | Same problem: `playlists.json` is written and read, but a playlist can't be opened as a tab or queued. | S |
| **Saved filter presets** | Advanced search (min views / min duration / regex) resets on every reload. Persist named presets to the sidebar. | S |
| **Sort by date added** | No date field exists in the data at all. Requires `generate_grid.py` to record `first_seen` per viewkey on scrape — cheap now, impossible retroactively, so worth adding early. | S (but do it soon) |
| **Dead-link pruning** | A HEAD-check pass over 8k URLs flagging 404s, run from `scratch/`. | M |
| **Richer stats** | Current panel shows 3 numbers + a pie chart. Category totals by *watch time*, watched-over-time, and per-category duration would use data you already have. | M |
| **Shuffle / radio mode** | Fill the queue with N random videos matching the current filter. Trivial given the queue already exists. | S |

---

## 5. Look & feel

Both UIs share the same "Cinematic Dark" token set (`--bg-base: #0a0b10`, `--accent: #f43f5e`), so
these are polish items, not a redesign.

- **Top bar is overloaded.** Nine buttons across two rows with mixed emoji labels (🎬 📊 ⚙️ Adv ☑️ Bulk
  📤 📥 📁 🔄). Collapse to a single icon row with an overflow menu; move Export/Import/Reset into it.
- **The sidebar from `plans/ui_redesign.md` never landed in the template.** Nine category tabs are still
  horizontal buttons at lines 834–842. React has the vertical sidebar; the legacy page doesn't.
- **Chart.js loads from CDN on every page load** (line 9) for a modal most sessions never open.
  Lazy-load it on first Stats click — saves ~200 KB and a blocking request.
- **Google Fonts is render-blocking** (line 8). Offline or on a slow link the page stalls on it. Add
  `font-display: swap` or self-host Inter.
- **Category colors are inconsistent.** The CSS variables use `--cat-public: #10b981`, but the stats
  pie chart hardcodes `#2ecc71` for the same category (line ~2100). Same for several others.
- **No empty/loading state in the legacy grid** — a filter with zero matches renders a blank column.

---

## 6. Finishing the React rewrite

Current state — more complete than expected. 13 components, ~2,140 lines:

```
App.jsx (153) · useVideoStore.js (392) · api.js (99) · formatters.js (88) · useKeyboardNav.js (85)
VideoCard (198) · PlayerPanel (196) · StatsPanel (145) · TopBar (127) · VideoDetailsPanel (115)
Sidebar (108) · VideoGrid (108) · QueueWidget (92) · MiniPlayer (69) · AdvancedSearchModal (72) · HeroBanner (70)
```

Already there: virtualized grid, Zustand store with debounced per-resource saves, toasts, theater
mode, bulk categorize, keyboard nav, hover preview, queue, stats.

**Gaps vs. the legacy page:**

1. **File System Access folder sync** — no `showDirectoryPicker` anywhere in `frontend/`. The legacy
   page can write `categories.json`/`blacklist.txt` straight to disk without the server. React relies
   entirely on `POST /api/*`, which is arguably better; just confirm you're not relying on the offline path.
2. **Export / import backup** — `exportBackup` / `importBackup` exist only in the template. Given
   11,052 category assignments represent real manual work, a backup path is worth porting.
3. **Blacklist management UI** — the store loads and saves `blacklist`, but there's no modal to review
   or clear the 67 current entries.

**Recommended sequence:** port those three → verify parity against your actual workflow → delete
`z3ncoding_videos_grid.template.html`, the generated HTML, and the inline-JSON path in
`generate_grid.py` (keeping only the `videos.json` writer). That deletes ~2,200 lines and every bug in §1.

---

## Suggested order

1. **§3 security** — 20 min, unbounded downside if skipped.
2. **§2.2 thumbnail caching** — 15 min, immediately felt on every reload.
3. **§6 decision** — React or template. Everything else branches off this.
4. If React: port the three gaps, then delete the template.
   If template: fix §1 (#1, #2, #3, #5, #7 first), then §2.1 and §2.3.
5. **§2.4 stream cache** — applies to both.
6. **§4 "date added"** — add the field to the scraper now; it can't be backfilled.
7. Then the rest of §4 / §5 by taste.

---

## Repo hygiene (unrelated but noticed)

`temp_script.js` (1.0 MB) and `test_page.html` (1.4 MB) sit in the project root and appear to be
scraper debris. `AGENTS.md~`, `blacklist.txt~`, `plans/ui_redesign.md~`, and `categories.json.save`
are editor backup files. `.chrome_profile/` (34 dirs) is in the project root while `serve.py` uses
`~/.cache/porn-project-chrome-profile` — one of the two is stale.
