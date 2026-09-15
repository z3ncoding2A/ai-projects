#!/usr/bin/env python3
"""
execution/scraper_pipeline.py
Deterministic pipeline tool for:
- Scraping profile / search video pages with pagination
- Verifying & downloading thumbnails to thumbs/
- Checking video stream availability
- Auditing and reconciling catalog integrity (videos.json, categories.json, blacklist.txt)
"""

import os
import sys
import re
import json
import time
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.sax.saxutils import escape

# Optional imports with fallbacks
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests
    HAS_CURL_CFFI = False

import requests
from bs4 import BeautifulSoup

# Base paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_FILE = os.path.join(ROOT_DIR, "videos.json")
CATEGORIES_FILE = os.path.join(ROOT_DIR, "categories.json")
CATEGORIES_SCHEMA_FILE = os.path.join(ROOT_DIR, "categories-schema.json")
BLACKLIST_FILE = os.path.join(ROOT_DIR, "blacklist.txt")
MANUAL_VIDEOS_FILE = os.path.join(ROOT_DIR, "manual_videos.json")
VIDEOS_TO_ADD_FILE = os.path.join(ROOT_DIR, "videos-to-add.txt")
THUMBS_DIR = os.path.join(ROOT_DIR, "thumbs")

os.makedirs(THUMBS_DIR, exist_ok=True)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ── Utility Functions ────────────────────────────────────────────────────────

def get_viewkey(url: str) -> str:
    if not url:
        return ""
    match = re.search(r'viewkey=([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    # xHamster pattern
    match_xh = re.search(r'videos/[\w-]+-(\w+)$', url) or re.search(r'(\w{6,8})$', url)
    if match_xh:
        return match_xh.group(1)
    return url

def parse_duration(d_str: str) -> int:
    if not d_str:
        return 0
    parts = d_str.strip().split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        pass
    return 0

def format_duration(seconds: int) -> str:
    if not seconds:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def parse_views(v_str: str) -> int:
    if not v_str:
        return 0
    v = v_str.lower().replace('views', '').strip()
    num_str = re.sub(r'[^0-9.]', '', v)
    if not num_str:
        return 0
    try:
        num = float(num_str)
        if 'm' in v:
            return int(num * 1_000_000)
        if 'k' in v:
            return int(num * 1_000)
        return int(num)
    except Exception:
        return 0

def format_views(raw: int) -> str:
    if not raw:
        return "0 views"
    if raw >= 1_000_000:
        return f"{raw / 1_000_000:.1f}M views"
    if raw >= 1_000:
        return f"{raw / 1_000:.1f}K views"
    return f"{raw} views"

def is_valid_thumbnail(url: str) -> bool:
    if not url:
        return False
    placeholders = ["blank.gif", "data:image", "default-thumbnail", "clear.png", "ph-video-placeholder", "transparent", "1x1", "loading"]
    return not any(p in url.lower() for p in placeholders)

def verify_thumbnail_url(url: str) -> bool:
    if not is_valid_thumbnail(url):
        return False
    try:
        res = requests.head(url, headers=DEFAULT_HEADERS, timeout=5, allow_redirects=True)
        if res.status_code == 200:
            return True
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=5, stream=True)
        if res.status_code == 200:
            res.close()
            return True
    except Exception:
        pass
    return False

def download_thumbnail(url: str, local_path: str) -> bool:
    if not url:
        return False
    try:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=8, stream=True)
        if res.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in res.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False

def get_thumbnail_via_ytdlp(video_url: str) -> str:
    try:
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--dump-json",
            "--no-warnings",
            "--skip-download",
            "--impersonate", "chrome",
            video_url,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=20)
        info = json.loads(out)
        thumb = info.get("thumbnail")
        if thumb and verify_thumbnail_url(thumb):
            return thumb
    except Exception:
        pass
    return ""

def get_thumbnail_from_page(video_url: str) -> str:
    try:
        if HAS_CURL_CFFI:
            res = curl_requests.get(video_url, impersonate="chrome", timeout=10)
        else:
            res = requests.get(video_url, headers=DEFAULT_HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'html.parser')
            og = soup.find('meta', property='og:image')
            if og and verify_thumbnail_url(og.get('content')):
                return og['content']
            link = soup.find('link', rel='image_src')
            if link and verify_thumbnail_url(link.get('href')):
                return link['href']
    except Exception:
        pass
    return ""

def get_robust_thumbnail(video_url: str, initial_thumb: str, viewkey: str):
    local_path = os.path.join(THUMBS_DIR, f"{viewkey}.jpg")
    relative_path = f"thumbs/{viewkey}.jpg"

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return relative_path, (initial_thumb if is_valid_thumbnail(initial_thumb) else "")

    if verify_thumbnail_url(initial_thumb):
        if download_thumbnail(initial_thumb, local_path):
            return relative_path, initial_thumb
        return initial_thumb, initial_thumb

    # Fallback to page scraping or yt-dlp
    found = get_thumbnail_from_page(video_url)
    if not found:
        found = get_thumbnail_via_ytdlp(video_url)

    if found:
        if download_thumbnail(found, local_path):
            return relative_path, found
        return found, found

    return initial_thumb, initial_thumb

# ── Scraping Implementation ──────────────────────────────────────────────────

def fetch_page(url: str):
    try:
        if HAS_CURL_CFFI:
            res = curl_requests.get(url, impersonate="chrome", timeout=15)
        else:
            res = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"[!] Request error for {url}: {e}")
    return None

def parse_video_item(item):
    try:
        title_el = item.select_one('.title a, .videoTitle a, a[title]')
        if not title_el:
            return None

        title = title_el.get('title') or title_el.text.strip()
        link = title_el.get('href', '')
        if not link:
            return None
        if not link.startswith('http'):
            link = f"https://www.pornhub.com{link}"

        viewkey = get_viewkey(link)
        if not viewkey:
            return None

        # Duration
        dur_el = item.select_one('.duration, .time, .videoDuration')
        duration_str = dur_el.text.strip() if dur_el else ""
        raw_dur = parse_duration(duration_str)
        if not duration_str and raw_dur:
            duration_str = format_duration(raw_dur)

        # Views
        views_el = item.select_one('.views var, .views, .videoViews')
        views_str = views_el.text.strip() if views_el else "0"
        raw_views = parse_views(views_str)

        # Thumbnail
        img = item.select_one('img')
        thumb_url = ""
        if img:
            thumb_url = img.get('data-src') or img.get('data-thumb_url') or img.get('data-mediumthumb') or img.get('src') or ""

        local_thumb, remote_thumb = get_robust_thumbnail(link, thumb_url, viewkey)

        return {
            "title": title,
            "url": link,
            "thumbnail": local_thumb,
            "duration": duration_str,
            "rawDuration": raw_dur,
            "views": format_views(raw_views),
            "rawViews": raw_views,
            "viewkey": viewkey,
            "category": "none",
            "searchText": title.lower(),
            "remoteThumbnail": remote_thumb,
        }
    except Exception as e:
        print(f"[!] Error parsing video item: {e}")
        return None

def scrape_url(target_url: str, max_pages: int = 1):
    discovered = []
    seen_viewkeys = set()

    for page in range(1, max_pages + 1):
        page_url = target_url
        if page > 1:
            sep = "&" if "?" in target_url else "?"
            page_url = f"{target_url}{sep}page={page}"

        print(f"[*] Scraping page {page}/{max_pages}: {page_url}")
        html = fetch_page(page_url)
        if not html:
            print(f"[!] Failed to fetch {page_url}")
            break

        soup = BeautifulSoup(html, 'html.parser')
        video_items = soup.select('.videoItem, .phimage, .pcVideoListItem, li[data-video-vkey]')
        if not video_items:
            # Fallback broader selector
            video_items = soup.select('ul#videoCategory li, ul#showAllChanelVideos li, .videoblock')

        print(f"    Found {len(video_items)} potential video cards.")
        if not video_items:
            break

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(parse_video_item, it) for it in video_items]
            for fut in as_completed(futures):
                res = fut.result()
                if res and res["viewkey"] not in seen_viewkeys:
                    seen_viewkeys.add(res["viewkey"])
                    discovered.append(res)

        time.sleep(1.0)  # Gentle delay between pages

    return discovered

# ── Pipeline Modes ───────────────────────────────────────────────────────────

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_scrape(target_url: str, max_pages: int, auto_save: bool = True):
    print(f"=== Starting Scrape Pipeline for: {target_url} (pages: {max_pages}) ===")
    existing_videos = load_json(VIDEOS_FILE, [])
    existing_by_vk = {v["viewkey"]: v for v in existing_videos if "viewkey" in v}

    blacklist = []
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
            blacklist = [line.strip() for line in f if line.strip()]
    blacklist_set = set(blacklist)

    discovered = scrape_url(target_url, max_pages)
    new_added = 0
    updated = 0

    for vid in discovered:
        vk = vid["viewkey"]
        if vk in blacklist_set:
            continue
        if vk in existing_by_vk:
            # Update thumbnail or views if better
            existing = existing_by_vk[vk]
            if vid["rawViews"] > (existing.get("rawViews") or 0):
                existing["views"] = vid["views"]
                existing["rawViews"] = vid["rawViews"]
                updated += 1
            if not existing.get("remoteThumbnail") and vid.get("remoteThumbnail"):
                existing["remoteThumbnail"] = vid["remoteThumbnail"]
        else:
            vid["idx"] = len(existing_videos)
            existing_videos.append(vid)
            existing_by_vk[vk] = vid
            new_added += 1

    if auto_save and (new_added > 0 or updated > 0):
        # Backup first
        save_json(f"{VIDEOS_FILE}.bak", existing_videos)
        save_json(VIDEOS_FILE, existing_videos)
        print(f"[✓] Saved {len(existing_videos)} total videos ({new_added} new, {updated} updated).")

    summary = {
        "status": "success",
        "scraped_count": len(discovered),
        "new_added": new_added,
        "updated": updated,
        "total_catalog": len(existing_videos),
    }
    print(json.dumps(summary, indent=2))
    return summary

def run_verify_thumbs(limit: int = 50):
    print(f"=== Verifying Thumbnails (batch size: {limit}) ===")
    videos = load_json(VIDEOS_FILE, [])
    repaired = 0
    checked = 0

    for vid in videos:
        if checked >= limit:
            break
        vk = vid.get("viewkey")
        local_thumb = os.path.join(ROOT_DIR, vid.get("thumbnail", ""))
        needs_repair = not os.path.exists(local_thumb) or os.path.getsize(local_thumb) == 0

        if needs_repair:
            checked += 1
            print(f"[*] Repairing thumbnail for {vk} - {vid.get('title', '')[:40]}...")
            new_local, remote = get_robust_thumbnail(vid.get("url", ""), vid.get("remoteThumbnail", ""), vk)
            if os.path.exists(os.path.join(ROOT_DIR, new_local)):
                vid["thumbnail"] = new_local
                if remote:
                    vid["remoteThumbnail"] = remote
                repaired += 1

    if repaired > 0:
        save_json(VIDEOS_FILE, videos)
        print(f"[✓] Repaired {repaired} thumbnails.")

    summary = {
        "checked": checked,
        "repaired": repaired,
        "total_videos": len(videos)
    }
    print(json.dumps(summary, indent=2))
    return summary

def run_audit():
    print("=== Catalog Health Audit ===")
    videos = load_json(VIDEOS_FILE, [])
    categories = load_json(CATEGORIES_FILE, {})
    blacklist = []
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
            blacklist = [line.strip() for line in f if line.strip()]

    missing_thumbs = 0
    missing_durations = 0
    categorized = 0

    for vid in videos:
        vk = vid.get("viewkey")
        local_thumb = os.path.join(ROOT_DIR, vid.get("thumbnail", ""))
        if not os.path.exists(local_thumb) or os.path.getsize(local_thumb) == 0:
            missing_thumbs += 1
        if not vid.get("rawDuration"):
            missing_durations += 1
        if vk in categories and categories[vk] != 'none':
            categorized += 1

    report = {
        "total_videos": len(videos),
        "categorized_count": categorized,
        "uncategorized_count": len(videos) - categorized,
        "blacklisted_count": len(blacklist),
        "missing_local_thumbnails": missing_thumbs,
        "missing_durations": missing_durations,
        "health_score": f"{((len(videos) - missing_thumbs) / max(1, len(videos))) * 100:.1f}%",
    }
    print(json.dumps(report, indent=2))
    return report

# ── Main Entrypoint ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomous Scraper Pipeline Tool")
    parser.add_argument("--mode", choices=["scrape", "verify_thumbs", "audit"], default="audit")
    parser.add_argument("--url", default="https://www.pornhub.com/users/z3ncoding/videos/recent")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()

    if args.mode == "scrape":
        run_scrape(args.url, args.pages)
    elif args.mode == "verify_thumbs":
        run_verify_thumbs(args.limit)
    elif args.mode == "audit":
        run_audit()

if __name__ == "__main__":
    main()
