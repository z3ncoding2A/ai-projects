# SOP: Autonomous Video Scraper & Pipeline Orchestrator

## 1. Objective
Orchestrate an autonomous, reliable pipeline that discovers new videos, verifies thumbnail accessibility, caches local assets, audits catalog integrity, and verifies stream playback links. The system must self-anneal when encountering rate limits, bot checks, or missing assets.

---

## 2. Architecture & Components

```
┌───────────────────────────────────────────────────────────┐
│ Layer 1: Directive (This document)                        │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│ Layer 2: Antigravity Orchestrator Agent                   │
│ (orchestrator_agent.py using google.antigravity SDK)       │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│ Layer 3: Deterministic Execution Tools                    │
│ (execution/scraper_pipeline.py, serve.py API, yt-dlp)     │
└───────────────────────────────────────────────────────────┘
```

---

## 3. Workflow Steps

### Step 1: Catalog Ingestion & Target Selection
- **Input**: Target profile URL, tag search query, or manual URL list (`videos-to-add.txt`).
- **Tool**: `execution/scraper_pipeline.py --mode scrape --url <target_url> --pages <count>`
- **Output**: Discovered video entries normalized into `{viewkey, title, url, duration, rawDuration, views, rawViews, thumbnail, remoteThumbnail, category, searchText}`.

### Step 2: Asset Verification & Thumbnail Caching
- Verify that every video in the catalog has a valid accessible thumbnail image.
- If thumbnail URL fails HTTP verification (404/403/CDN expiry):
  1. Try parsing video landing page meta tags (`og:image`, `link[rel=image_src]`).
  2. Fallback to `yt-dlp` info extraction.
  3. Download image to `thumbs/<viewkey>.jpg`.
- **Tool**: `execution/scraper_pipeline.py --mode verify_thumbs --limit <N>`

### Step 3: Stream Validation & Health Checks
- Verify that stream URLs can be resolved via `/api/streams?url=...` or `yt-dlp`.
- **Tool**: `execution/scraper_pipeline.py --mode verify_streams --limit <N>`

### Step 4: Catalog Reconciliation & Persistence
- Deduplicate newly found videos against existing `videos.json` and `blacklist.txt`.
- Append new videos to `videos.json`.
- Log newly imported video count and updated category counts.

---

## 4. Self-Annealing & Error Handling Rules

1. **HTTP 403 / Cloudflare / Bot Protection**:
   - Use browser-impersonation headers (`curl_cffi` chrome impersonation).
   - Back off with jittered exponential delay (2s -> 5s -> 10s).
2. **Missing or Expired CDN Thumbnails**:
   - Automatically fall back from CDN URLs to yt-dlp extraction and store locally in `thumbs/`.
3. **Corrupted JSON Files**:
   - Automatically create backup snapshots before mutations (`videos.json.bak`).
   - Validate JSON syntax before saving.

---

## 5. Deliverables & Outputs
- `videos.json`: Updated library database.
- `thumbs/`: Cached thumbnail image files.
- `scraper.log`: Structured execution log of every pipeline run.
