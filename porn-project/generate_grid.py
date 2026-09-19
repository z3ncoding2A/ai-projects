import requests
from bs4 import BeautifulSoup
import time
import os
import re
import json
import datetime
from xml.sax.saxutils import escape
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

# Base URL and user profile
BASE_URL = "https://www.pornhub.com"
PROFILE_VIDEOS_URL = "https://www.pornhub.com/users/z3ncoding/videos/recent"
CATEGORIES_FILE = "categories.json"
MANUAL_VIDEOS_FILE = "manual_videos.json"
THUMBS_DIR = "thumbs"
# Persistent viewkey -> ISO date first observed. Only ever appended to — never
# regenerated wholesale — since "date added" can't be reconstructed after the fact.
FIRST_SEEN_FILE = "first_seen.json"


def load_first_seen():
    if os.path.exists(FIRST_SEEN_FILE):
        try:
            with open(FIRST_SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {FIRST_SEEN_FILE}: {e}")
    return {}


def update_first_seen(first_seen, all_videos):
    """Add today's date for any viewkey not already tracked. Returns True if changed."""
    today = datetime.date.today().isoformat()
    changed = False
    for vid in all_videos:
        vk = vid.get("viewkey")
        if vk and vk not in first_seen:
            first_seen[vk] = today
            changed = True
    if changed:
        with open(FIRST_SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(first_seen, f, indent=2, ensure_ascii=False)
    return changed

if not os.path.exists(THUMBS_DIR):
    os.makedirs(THUMBS_DIR)

def atomic_json_dump(data, path, **json_kwargs):
    """Write JSON via a temp file + os.replace so readers never see a partial file."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="UTF-8") as f:
        json.dump(data, f, **json_kwargs)
    os.replace(tmp_path, path)

# Headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

def is_valid_thumbnail(url):
    """Checks if a thumbnail URL is valid and not a placeholder."""
    if not url:
        return False
    # Known placeholders and blank images
    placeholders = [
        "blank.gif", 
        "data:image", 
        "default-thumbnail", 
        "clear.png", 
        "ph-video-placeholder",
        "transparent",
        "1x1",
        "loading"
    ]
    if any(p in url.lower() for p in placeholders):
        return False
    return True

def verify_thumbnail_url(url):
    """Verifies that the thumbnail URL is actually accessible."""
    if not is_valid_thumbnail(url):
        return False
    try:
        # Some CDNs block HEAD requests or return 403, so we try HEAD then a partial GET
        response = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return True
        
        # Fallback to GET with Range header to minimize data usage
        response = requests.get(url, headers=HEADERS, timeout=5, stream=True)
        if response.status_code == 200:
            response.close()
            return True
    except Exception:
        pass
    return False

def get_thumbnail_via_ytdlp(video_url):
    """Uses yt-dlp to extract the most reliable thumbnail URL."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'user_agent': HEADERS['User-Agent'],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            thumb = info.get('thumbnail')
            if verify_thumbnail_url(thumb):
                return thumb
    except Exception:
        pass
    return ""

def get_thumbnail_from_video_page(video_url):
    """Fetches the video page to find the thumbnail in meta tags or scripts."""
    try:
        response = requests.get(video_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Try og:image meta tag
            og_image = soup.find('meta', property='og:image')
            if og_image and verify_thumbnail_url(og_image.get('content')):
                return og_image['content']
            
            # 2. Try link rel="image_src"
            img_src = soup.find('link', rel='image_src')
            if img_src and verify_thumbnail_url(img_src.get('href')):
                return img_src['href']
                
            # 3. Try player scripts for image_url or poster
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and ('image_url' in script.string or 'poster' in script.string):
                    # Try to find JSON-like "image_url":"..."
                    match = re.search(r'"image_url"\s*:\s*"([^"]+)"', script.string)
                    if match:
                        t = match.group(1).replace('\\/', '/')
                        if verify_thumbnail_url(t):
                            return t
                    
                    match = re.search(r'poster\s*:\s*"([^"]+)"', script.string)
                    if match:
                        t = match.group(1).replace('\\/', '/')
                        if verify_thumbnail_url(t):
                            return t
    except Exception:
        pass
    return ""



def download_thumbnail(url, local_path):
    """Downloads the thumbnail image from a URL and saves it to the local path."""
    if not url:
        return False
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, stream=True)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"  [!] Error downloading thumbnail: {e}")
    return False

def get_robust_thumbnail(video_url, initial_thumb):
    """Ensures a valid and accessible thumbnail is obtained and cached locally.
    Returns (display_url, remote_url)"""
    viewkey = get_viewkey(video_url)
    local_path = os.path.join(THUMBS_DIR, f"{viewkey}.jpg")
    
    remote_url = initial_thumb if is_valid_thumbnail(initial_thumb) else ""
    
    # Check if we already have it locally
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return local_path, remote_url

    # Check if initial thumb is valid. If so, download and return local path.
    if verify_thumbnail_url(initial_thumb):
        if download_thumbnail(initial_thumb, local_path):
            return local_path, initial_thumb
        return initial_thumb, initial_thumb
    
    # Fallback methods
    methods = [
        ("Video Page Parse", lambda: get_thumbnail_from_video_page(video_url)),
        ("YT-DLP Extract", lambda: get_thumbnail_via_ytdlp(video_url))
    ]
    
    for name, method in methods:
        thumb_url = method()
        if thumb_url: 
            print(f"  [+] Success: Found valid thumbnail via {name} for {viewkey}.")
            if download_thumbnail(thumb_url, local_path):
                return local_path, thumb_url
            return thumb_url, thumb_url
        
    return initial_thumb, initial_thumb


def get_viewkey(url):
    match = re.search(r'viewkey=([a-zA-Z0-9]*)', url)
    return match.group(1) if match else url

def parse_duration(d_str):
    if not d_str: return 0
    parts = d_str.strip().split(':')
    try:
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: return int(parts[0])*60 + int(parts[1])
    except:
        pass
    return 0

def parse_views(v_str):
    if not v_str: return 0
    v = v_str.lower().replace('views', '').strip()
    num_str = re.sub(r'[^0-9.]', '', v)
    if not num_str: return 0
    try:
        num = float(num_str)
        if 'm' in v: return int(num * 1000000)
        if 'k' in v: return int(num * 1000)
        return int(num)
    except:
        return 0

def process_video_item(item):
    """Processes a single video item from the page to extract metadata and robust thumbnails."""
    try:
        link_tag = item.select_one('a.linkVideoThumb, a[href*="view_video.php"]')
        if not link_tag:
            return None
            
        video_url = BASE_URL + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
        video_title = link_tag.get('title', '').strip()
        
        if not video_title:
            title_tag = item.select_one('span.title, div.title, a.title')
            if title_tag:
                video_title = title_tag.text.strip()
        
        if not video_title:
            video_title = "No Title"

        img_tag = item.find('img')
        thumbnail_url = ""
        if img_tag:
            # Try all known attribute variations where PH hides the real image
            thumbnail_url = (img_tag.get('data-thumb_url') or 
                             img_tag.get('data-src') or 
                             img_tag.get('data-medium') or 
                             img_tag.get('data-image') or 
                             img_tag.get('src', ''))
            
            # If it's a transparent/blank gif, try falling back
            if not is_valid_thumbnail(thumbnail_url):
                thumbnail_url = img_tag.get('data-image') or img_tag.get('data-src') or thumbnail_url

        # Force load if still invalid
        thumbnail_url, remote_thumbnail = get_robust_thumbnail(video_url, thumbnail_url)

        # Extract duration
        duration_tag = item.select_one('var.duration, span.duration')
        duration = duration_tag.text.strip() if duration_tag else ""
        raw_duration = parse_duration(duration)

        # Extract views
        views_tag = item.select_one('span.views')
        views = views_tag.text.strip() if views_tag else ""
        raw_views = parse_views(views)

        return {
            'title': video_title,
            'url': video_url,
            'thumbnail': thumbnail_url,
            'remote_thumbnail': remote_thumbnail,
            'duration': duration,
            'raw_duration': raw_duration,
            'views': views,
            'raw_views': raw_views,
            'viewkey': get_viewkey(video_url)
        }
    except Exception as e:
        print(f"  [!] Error processing item: {e}")
        return None

def get_videos_from_page(page_num):
    url = f"{PROFILE_VIDEOS_URL}?page={page_num}"
    print(f"Fetching page {page_num}...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        video_items = soup.select('li.videoblock, li.videoBox, li.ph-video-item')
        
        extracted_videos = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_video_item, video_items))
            extracted_videos = [v for v in results if v is not None]
            
        return extracted_videos
    except Exception as e:
        print(f"Error on page {page_num}: {e}")
        return []

def get_videos_from_search(query, page_num):
    encoded_query = requests.utils.quote(query)
    url = f"{BASE_URL}/video/search?search={encoded_query}&page={page_num}"
    print(f"Searching for '{query}' (Page {page_num})...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        video_items = soup.select('li.videoblock, li.videoBox, li.ph-video-item')
        
        extracted_videos = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_video_item, video_items))
            extracted_videos = [v for v in results if v is not None]
            
        return extracted_videos
    except Exception as e:
        print(f"Error searching for '{query}' on page {page_num}: {e}")
        return []

def scrape_video_page_sections(viewkey):
    """Visits a video page and scrapes both Related and Recommended video sections.
    Returns (related_videos, recommended_videos) as two separate lists."""
    url = f"{BASE_URL}/view_video.php?viewkey={viewkey}"
    print(f"  Scraping Related & Recommended for {viewkey}...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ── Related Videos ──
        # The "Related" tab is the default active tab, its content is in the initial HTML.
        # Try specific containers first, then broader selectors.
        related_items = soup.select('ul#relatedVideosListing li.videoblock, ul#relatedVideosCenter li.videoblock, ul#relatedVideosCenter li.videoBox')
        if not related_items:
            related_items = soup.select('.related-videos-container li.videoblock, .related-videos-container li.videoBox')
        
        # ── Recommended Videos ──
        # The "Recommended" tab content may be pre-loaded but hidden, or loaded via AJAX.
        # Try known Pornhub container IDs/classes.
        recommended_items = soup.select('ul#recommendedVideosListing li.videoblock, ul#recommendedVideosVPage li.videoblock, ul#recommendedVideosVPage li.videoBox')
        if not recommended_items:
            recommended_items = soup.select('#recommendedVideos li.videoblock, #recommendedVideos li.videoBox')
        if not recommended_items:
            # Try broader selector for any section with "recommended" in its attributes
            rec_container = soup.find(id=re.compile(r'recommend', re.I))
            if rec_container:
                recommended_items = rec_container.select('li.videoblock, li.videoBox')
        
        # Process Related items
        related = []
        if related_items:
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(process_video_item, related_items))
                related = [v for v in results if v is not None and viewkey not in v.get('url', '')]
            print(f"    Found {len(related)} related videos")
        else:
            print(f"    No related videos found in HTML")
        
        # Process Recommended items
        recommended = []
        if recommended_items:
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(process_video_item, recommended_items))
                recommended = [v for v in results if v is not None and viewkey not in v.get('url', '')]
            print(f"    Found {len(recommended)} recommended videos")
        else:
            print(f"    No recommended videos found in HTML (may require auth/AJAX)")
        
        return related, recommended
    except Exception as e:
        print(f"  Error scraping video page for {viewkey}: {e}")
        return [], []


def scrape_related_and_recommended(saved_categories, all_videos, seen_viewkeys):
    """For every video categorized as 'most', visit its page and scrape
    Related and Recommended sections. Returns (new_related, new_recommended) lists
    and updates saved_categories in-place."""
    
    # Find all viewkeys currently categorized as "most"
    most_viewkeys = [vk for vk, cat in saved_categories.items() if cat == 'most']
    
    if not most_viewkeys:
        print("\nNo videos in 'MOST LIKED' category. Skipping Related/Recommended scraping.")
        return [], []
    
    print(f"\n{'='*60}")
    print(f"SCRAPING RELATED & RECOMMENDED FROM {len(most_viewkeys)} 'MOST LIKED' VIDEOS")
    print(f"{'='*60}")
    
    new_related = []
    new_recommended = []
    total_related_found = 0
    total_recommended_found = 0
    
    for i, vk in enumerate(most_viewkeys, 1):
        print(f"\n[{i}/{len(most_viewkeys)}] Processing viewkey: {vk}")
        
        related, recommended = scrape_video_page_sections(vk)
        
        # Add Related videos (deduplicate against everything seen so far)
        for vid in related:
            total_related_found += 1
            if vid['viewkey'] not in seen_viewkeys:
                seen_viewkeys.add(vid['viewkey'])
                new_related.append(vid)
                # Only set category if not already categorized
                if vid['viewkey'] not in saved_categories:
                    saved_categories[vid['viewkey']] = 'related'
        
        # Add Recommended videos (deduplicate against everything seen so far)
        for vid in recommended:
            total_recommended_found += 1
            if vid['viewkey'] not in seen_viewkeys:
                seen_viewkeys.add(vid['viewkey'])
                new_recommended.append(vid)
                # Only set category if not already categorized
                if vid['viewkey'] not in saved_categories:
                    saved_categories[vid['viewkey']] = 'recommended'
        
        # Rate limit to avoid being blocked
        if i < len(most_viewkeys):
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"RELATED/RECOMMENDED SCRAPING COMPLETE")
    print(f"  Related:     {total_related_found} total found, {len(new_related)} new unique")
    print(f"  Recommended: {total_recommended_found} total found, {len(new_recommended)} new unique")
    print(f"{'='*60}")
    
    return new_related, new_recommended

def write_videos_data(all_videos, saved_categories, first_seen=None):
    """
    Writes videos.json for the React frontend (frontend/dist/, served by serve.py).
    Used to also generate a self-contained z3ncoding_videos_grid.html from
    z3ncoding_videos_grid.template.html; that legacy path was removed once the
    React rewrite reached feature parity (folder sync, backup export/import,
    blacklist management, tag/playlist browsing) — see plans/improvements_audit.md.
    The old template/HTML files may still be sitting in the repo; they're inert
    now and safe to delete manually.
    """
    print("Generating videos.json...")
    import json
    first_seen = first_seen or {}

    # Prepare JSON data for embedding
    json_videos = []
    for idx, vid in enumerate(all_videos):
        viewkey = vid['viewkey']
        category = saved_categories.get(viewkey, "none")

        # Auto-categorize based on keywords
        if category == "none":
            title_lower = vid['title'].lower()
            public_keywords = ["public", "exhibition", "watched", "being watched"]
            if any(kw in title_lower for kw in public_keywords):
                category = "public"

        remote_thumb = vid.get('remote_thumbnail', '')
        if not remote_thumb and vid['thumbnail'].startswith('http'):
            remote_thumb = vid['thumbnail']

        json_videos.append([
            idx,
            vid['title'],
            vid['url'],
            vid['thumbnail'],
            vid['duration'],
            vid['raw_duration'],
            vid['views'],
            vid['raw_views'],
            viewkey,
            category,
            vid['title'].lower(),
            remote_thumb, # Index 11
            first_seen.get(viewkey, "") # Index 12
        ])

    # Save the videos to videos.json for the React UI (as objects, not arrays)
    react_videos = []
    for item in json_videos:
        react_videos.append({
            "idx": item[0],
            "title": item[1],
            "url": item[2],
            "thumbnail": item[3],
            "duration": item[4],
            "rawDuration": item[5],
            "views": item[6],
            "rawViews": item[7],
            "viewkey": item[8],
            "category": item[9],
            "searchText": item[10],
            "remoteThumbnail": item[11],
            "firstSeen": item[12]
        })

    videos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos.json")
    with open(videos_json_path, "w", encoding="UTF-8") as f:
        json.dump(react_videos, f, indent=2, ensure_ascii=False)

    # Also save the videos to videos.json for the modern React UI (as objects, not arrays)
    react_videos = []
    for item in json_videos:
        react_videos.append({
            "idx": item[0],
            "title": item[1],
            "url": item[2],
            "thumbnail": item[3],
            "duration": item[4],
            "rawDuration": item[5],
            "views": item[6],
            "rawViews": item[7],
            "viewkey": item[8],
            "category": item[9],
            "searchText": item[10],
            "remoteThumbnail": item[11]
        })

    videos_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos.json")
    atomic_json_dump(react_videos, videos_json_path, indent=2, ensure_ascii=False)

def main():
    import sys
    # Load categories
    saved_categories = {}
    if os.path.exists(CATEGORIES_FILE):
        print(f"Loading {CATEGORIES_FILE}...")
        try:
            with open(CATEGORIES_FILE, "r") as f:
                saved_categories = json.load(f)
            print(f"Found {len(saved_categories)} categorized videos.")
        except Exception as e:
            print(f"Error loading categories: {e}")

    # Load blacklist
    blacklist = set()
    if os.path.exists("blacklist.txt"):
        print("Loading blacklist.txt...")
        with open("blacklist.txt", "r") as f:
            blacklist = {line.strip() for line in f if line.strip()}
        print(f"Found {len(blacklist)} blacklisted viewkeys.")

    all_videos = []
    seen_viewkeys = blacklist.copy() 
    
    # Load manual videos
    if os.path.exists(MANUAL_VIDEOS_FILE):
        print(f"Loading {MANUAL_VIDEOS_FILE}...")
        try:
            with open(MANUAL_VIDEOS_FILE, "r") as f:
                manual_vids = json.load(f)
                for vid in manual_vids:
                    if vid['viewkey'] not in seen_viewkeys:
                        seen_viewkeys.add(vid['viewkey'])
                        all_videos.append(vid)
                print(f"Added {len(manual_vids)} manual videos.")
        except Exception as e:
            print(f"Error loading manual videos: {e}")

    page = 1
    
    print("Starting Scraper (HTML Grid Mode)...")
    
    while True:
        videos = get_videos_from_page(page)
        if not videos:
            print(f"No more videos found on page {page}. Finishing...")
            break
        
        new_count = 0
        for vid in videos:
            if vid['viewkey'] not in seen_viewkeys:
                seen_viewkeys.add(vid['viewkey'])
                all_videos.append(vid)
                new_count += 1
        
        print(f"Page {page}: Found {len(videos)} videos, {new_count} were new.")
        print(f"Total unique videos: {len(all_videos)}")
        
        if new_count == 0 and len(videos) > 0:
            print("Found only duplicates on this page. Might be the end or overlap.")
            # If we find a page with 0 new videos, we've likely hit the old ones
            break
        
        page += 1
        time.sleep(1.5) 

        if page > 100: 
            break


    if not all_videos:
        print("No videos found. Check the profile URL or network connection.")
        return

    # ── Scrape Related & Recommended from all MOST LIKED videos ──
    new_related, new_recommended = scrape_related_and_recommended(
        saved_categories, all_videos, seen_viewkeys
    )
    all_videos.extend(new_related)
    all_videos.extend(new_recommended)

    # ── Track first-seen dates (append-only; can't be reconstructed later) ──
    first_seen = load_first_seen()
    if update_first_seen(first_seen, all_videos):
        print(f"Updated {FIRST_SEEN_FILE} ({len(first_seen)} viewkeys tracked).")

    # Save updated categories back to file
    if new_related or new_recommended:
        print(f"\nSaving updated categories.json with {len(new_related)} related + {len(new_recommended)} recommended...")
        atomic_json_dump(saved_categories, CATEGORIES_FILE, indent=2)

    write_videos_data(all_videos, saved_categories, first_seen)

    print(f"\nSUCCESS! Wrote videos.json")
    print(f"Total unique videos processed: {len(all_videos)}")
    print(f"  - Profile videos: {len(all_videos) - len(new_related) - len(new_recommended)}")
    print(f"  - Related:        {len(new_related)}")
    print(f"  - Recommended:    {len(new_recommended)}")

if __name__ == "__main__":
    main()
