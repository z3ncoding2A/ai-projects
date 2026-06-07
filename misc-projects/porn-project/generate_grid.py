import requests
from bs4 import BeautifulSoup
import time
import os
import re
import json
from xml.sax.saxutils import escape
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

# Base URL and user profile
BASE_URL = "https://www.pornhub.com"
PROFILE_VIDEOS_URL = "https://www.pornhub.com/users/z3ncoding/videos/recent"
CATEGORIES_FILE = "categories.json"
MANUAL_VIDEOS_FILE = "manual_videos.json"
THUMBS_DIR = "thumbs"

if not os.path.exists(THUMBS_DIR):
    os.makedirs(THUMBS_DIR)

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

def get_related_videos(viewkey):
    url = f"{BASE_URL}/view_video.php?viewkey={viewkey}"
    print(f"Scraping related videos for {viewkey}...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        # Related videos are often in #relatedVideosCenter or similar videoblocks
        video_items = soup.select('ul#relatedVideosCenter li.videoblock, ul#relatedVideosCenter li.videoBox, .related-videos-container li.videoblock')
        
        if not video_items:
            # Fallback to any videoblocks if specific related container not found
            video_items = soup.select('li.videoblock, li.videoBox')

        extracted_videos = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_video_item, video_items))
            # For related videos, we might want to skip the current video
            extracted_videos = [v for v in results if v is not None and viewkey not in v['url']]
            
        return extracted_videos
    except Exception as e:
        print(f"Error scraping related for {viewkey}: {e}")
        return []

def write_html_grid(all_videos, filename, saved_categories):
    print(f"Generating optimized HTML grid: {filename}...")
    import json
    
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
            remote_thumb # Index 11
        ])

    # Optimized dynamic HTML template - Cinematic Dark Redesign
    html_start = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>z3ncoding Video Library ({len(all_videos)})</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #050505;
            --bg-surface: #121212;
            --bg-surface-hover: #1e1e1e;
            --text-primary: #f0f0f0;
            --text-secondary: #a0a0a0;
            --accent-primary: #e50914; /* Cinematic Red */
            --accent-hover: #ff0f1a;
            --border-color: #2a2a2a;
            
            --cat-public: #2ecc71;
            --cat-least: #95a5a6;
            --cat-avg: #3498db;
            --cat-most: #f39c12;
            
            --sidebar-width: 250px;
        }}

        * {{ box-sizing: border-box; }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            margin: 0;
            padding: 0;
            display: flex;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        /* --- Sidebar Navigation --- */
        .sidebar {{
            width: var(--sidebar-width);
            background-color: var(--bg-surface);
            border-right: 1px solid var(--border-color);
            position: fixed;
            height: 100vh;
            display: flex;
            flex-direction: column;
            z-index: 100;
        }}

        .sidebar-header {{
            padding: 24px 20px;
            border-bottom: 1px solid var(--border-color);
        }}

        .sidebar-header h1 {{
            margin: 0;
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }}
        .sidebar-header span {{
            color: var(--accent-primary);
        }}

        .nav-links {{
            flex: 1;
            padding: 20px 10px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .nav-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            text-align: left;
            padding: 12px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
        }}

        .nav-btn:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
        }}

        .nav-btn.active {{
            background-color: rgba(229, 9, 20, 0.1);
            color: var(--accent-primary);
            font-weight: 600;
        }}
        .nav-btn.active::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 10%;
            height: 80%;
            width: 4px;
            background-color: var(--accent-primary);
            border-radius: 0 4px 4px 0;
        }}

        .sidebar-footer {{
            padding: 20px;
            border-top: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .action-btn {{
            background: #222;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }}
        .action-btn:hover {{ background: #333; color: white; }}
        .btn-export:hover {{ border-color: #2ecc71; color: #2ecc71; }}
        .btn-blacklist:hover {{ border-color: #e74c3c; color: #e74c3c; }}
        .btn-connect:hover {{ border-color: #3498db; color: #3498db; }}
        .btn-connect.connected {{ border-color: #2ecc71; color: #2ecc71; background: rgba(46, 204, 113, 0.1); }}

        .sync-status {{
            font-size: 0.75rem;
            padding: 6px 10px;
            border-radius: 6px;
            text-align: center;
            transition: all 0.3s;
        }}
        .sync-status.disconnected {{
            background: rgba(231, 76, 60, 0.1);
            color: #e74c3c;
        }}
        .sync-status.connected {{
            background: rgba(46, 204, 113, 0.1);
            color: #2ecc71;
        }}
        .sync-status.saving {{
            background: rgba(52, 152, 219, 0.1);
            color: #3498db;
        }}

        /* --- Main Content Area --- */
        .main-wrapper {{
            flex: 1;
            margin-left: var(--sidebar-width);
            display: flex;
            flex-direction: column;
            min-width: 0; /* Important for flex child truncating */
        }}

        /* Top Bar */
        .top-bar {{
            position: sticky;
            top: 0;
            background-color: rgba(5, 5, 5, 0.85);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            z-index: 90;
            padding: 16px 32px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
        }}

        .search-container {{
            flex: 1;
            max-width: 600px;
            position: relative;
        }}

        #search-input {{
            width: 100%;
            padding: 12px 20px;
            background-color: rgba(255, 255, 255, 0.08);
            border: 1px solid transparent;
            border-radius: 30px;
            color: white;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.2s;
        }}
        #search-input:focus {{
            background-color: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.2);
            box-shadow: 0 0 0 3px rgba(229, 9, 20, 0.1);
        }}
        #search-input::placeholder {{ color: #777; }}

        .top-controls {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        select#sort-select {{
            padding: 10px 16px;
            background-color: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.9rem;
            cursor: pointer;
            outline: none;
        }}

        .stats {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            white-space: nowrap;
        }}

        /* Grid */
        .content-area {{
            padding: 32px;
            flex: 1;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 24px;
        }}

        /* Video Card */
        .video-card {{
            background-color: var(--bg-surface);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            text-decoration: none;
            color: inherit;
            position: relative;
            transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 1px solid transparent;
        }}

        .video-card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 15px 30px rgba(0,0,0,0.6);
            border-color: rgba(255,255,255,0.1);
            z-index: 10;
        }}

        .thumbnail-wrapper {{
            position: relative;
            width: 100%;
            padding-top: 56.25%; /* 16:9 Aspect Ratio */
            background-color: #000;
            overflow: hidden;
        }}

        .thumbnail {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            object-fit: cover;
            transition: opacity 0.3s ease;
        }}

        .preview-img {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            object-fit: cover;
            opacity: 0;
            pointer-events: none;
            z-index: 5;
            transition: opacity 0.2s;
        }}

        .thumbnail-wrapper:hover .preview-img {{ opacity: 1; }}
        .thumbnail-wrapper:hover .thumbnail {{ opacity: 0.3; }}

        .duration {{
            position: absolute;
            bottom: 8px; right: 8px;
            background-color: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            z-index: 6;
        }}

        .video-info {{
            padding: 16px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            position: relative;
        }}

        .video-title {{
            font-size: 0.95rem;
            font-weight: 600;
            margin-bottom: 12px;
            line-height: 1.4;
            height: 2.8em;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            color: var(--text-primary);
        }}

        .video-meta {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* Categorization Overlay */
        .category-actions {{
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            background: rgba(18, 18, 18, 0.95);
            backdrop-filter: blur(4px);
            padding: 12px;
            display: flex;
            gap: 6px;
            transform: translateY(100%);
            transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
            border-top: 1px solid rgba(255,255,255,0.05);
            z-index: 20;
        }}

        .video-card:hover .category-actions {{
            transform: translateY(0);
        }}

        .cat-btn {{
            flex: 1;
            padding: 6px 0;
            border: none;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            color: white;
            transition: filter 0.2s, transform 0.1s;
        }}
        .cat-btn:hover {{ filter: brightness(1.2); transform: scale(1.05); }}
        .cat-btn:active {{ transform: scale(0.95); }}
        
        .btn-public {{ background: var(--cat-public); }}
        .btn-least {{ background: var(--cat-least); }}
        .btn-avg {{ background: var(--cat-avg); }}
        .btn-most {{ background: var(--cat-most); }}
        .btn-reset {{ background: #444; }}
        .btn-delete {{ background: #c0392b; }}

        /* Status Indicator */
        .status-badge {{
            position: absolute;
            top: 8px;
            left: 8px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            z-index: 6;
            box-shadow: 0 0 4px rgba(0,0,0,0.5);
        }}

        /* Modals */
        .modal {{
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%) scale(0.95);
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            padding: 24px; z-index: 2000; width: 90%; max-width: 600px;
            border-radius: 12px;
            opacity: 0; pointer-events: none;
            transition: all 0.2s;
            box-shadow: 0 20px 40px rgba(0,0,0,0.8);
        }}
        .modal.visible {{ opacity: 1; pointer-events: auto; transform: translate(-50%, -50%) scale(1); }}
        .modal h2 {{ margin-top: 0; margin-bottom: 16px; font-size: 1.2rem; }}
        
        .modal-overlay {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); backdrop-filter: blur(4px);
            z-index: 1999; opacity: 0; pointer-events: none;
            transition: opacity 0.2s;
        }}
        .modal-overlay.visible {{ opacity: 1; pointer-events: auto; }}
        
        textarea {{
            background: #0a0a0a; color: #fff; border: 1px solid #333;
            padding: 12px; border-radius: 8px; font-family: monospace;
            resize: vertical;
        }}

        #back-to-top {{
            position: fixed; bottom: 30px; right: 30px;
            background-color: var(--accent-primary); color: white;
            width: 50px; height: 50px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            opacity: 0; transition: opacity 0.3s, transform 0.2s; z-index: 100;
            text-decoration: none; font-size: 1.2rem; font-weight: bold;
            box-shadow: 0 4px 12px rgba(229, 9, 20, 0.4);
        }}
        #back-to-top.visible {{ opacity: 1; }}
        #back-to-top:hover {{ transform: scale(1.1); background-color: var(--accent-hover); }}

        #sentinel {{ height: 50px; width: 100%; }}

        /* Responsive */
        @media (max-width: 900px) {{
            :root {{ --sidebar-width: 0px; }}
            .sidebar {{ transform: translateX(-100%); transition: transform 0.3s; }}
            .sidebar.mobile-open {{ transform: translateX(0); }}
            .main-wrapper {{ margin-left: 0; }}
            .mobile-menu-btn {{ display: block !important; }}
            .top-bar {{ padding: 12px 16px; flex-wrap: wrap; }}
            .search-container {{ order: 3; min-width: 100%; margin-top: 10px; }}
        }}
        
        .mobile-menu-btn {{
            display: none;
            background: none; border: none; color: white;
            font-size: 1.5rem; cursor: pointer; padding: 0 10px 0 0;
        }}
    </style>
</head>
<body>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h1>z3ncoding <span>Library</span></h1>
        </div>
        <div class="nav-links">
            <button class="nav-btn active" onclick="setTab('none')">Main Collection</button>
            <button class="nav-btn" onclick="setTab('public')">Public & Exhibition</button>
            <button class="nav-btn" onclick="setTab('least')">Least Liked</button>
            <button class="nav-btn" onclick="setTab('average')">Averagely Liked</button>
            <button class="nav-btn" onclick="setTab('most')">Most Liked</button>
        </div>
        <div class="sidebar-footer">
            <button class="action-btn btn-connect" id="connect-folder-btn" onclick="connectFolder()">📁 Connect Folder</button>
            <div class="sync-status disconnected" id="sync-status">⚠ Not connected — changes only in browser</div>
            <button class="action-btn btn-export" onclick="toggleModal('export-modal')">Export Categories</button>
            <button class="action-btn btn-blacklist" onclick="toggleModal('blacklist-modal')">Manage Blacklist</button>
            <button class="action-btn" onclick="resetLocalStorage()" style="border-color:#555; font-size:0.78rem;">🔄 Reset Browser Data</button>
        </div>
    </aside>

    <div class="modal-overlay" id="modal-overlay" onclick="closeModals()"></div>
    <div class="modal" id="blacklist-modal">
        <h2>Local Blacklist</h2>
        <textarea id="blacklist-textarea" style="width:100%;height:200px;" readonly></textarea>
        <div style="margin-top: 15px; display: flex; gap: 10px; justify-content: flex-end;">
            <button class="action-btn" onclick="closeModals()">Close</button>
            <button class="action-btn" onclick="clearBlacklist()" style="background: #e74c3c; border-color: #e74c3c; color: white;">Clear All</button>
        </div>
    </div>
    <div class="modal" id="export-modal">
        <h2>Export Categories JSON</h2>
        <textarea id="export-textarea" style="width:100%;height:200px;" readonly></textarea>
        <div style="margin-top: 15px; display: flex; justify-content: flex-end;">
            <button class="action-btn" onclick="closeModals()">Close</button>
        </div>
    </div>

    <main class="main-wrapper">
        <div class="top-bar">
            <button class="mobile-menu-btn" onclick="document.getElementById('sidebar').classList.toggle('mobile-open')">☰</button>
            <div class="search-container">
                <input type="text" id="search-input" placeholder="Search titles, tags..." autocomplete="off">
            </div>
            <div class="top-controls">
                <select id="sort-select">
                    <option value="newest">Recently Scraped</option>
                    <option value="title-az">Title (A-Z)</option>
                    <option value="views-desc">Most Viewed</option>
                    <option value="duration-desc">Longest Duration</option>
                </select>
                <div class="stats"><span id="visible-count">0</span> / {len(all_videos)}</div>
            </div>
        </div>

        <div class="content-area">
            <div class="grid" id="video-grid"></div>
            <div id="sentinel"></div>
        </div>
    </main>

    <a href="#" id="back-to-top">↑</a>

    <script>
        const ALL_VIDEOS = {json.dumps(json_videos)};
        
        const searchInput = document.getElementById('search-input');
        const sortSelect = document.getElementById('sort-select');
        const videoGrid = document.getElementById('video-grid');
        const visibleCount = document.getElementById('visible-count');
        const backToTop = document.getElementById('back-to-top');
        
        let currentTab = 'none';
        let categories = JSON.parse(localStorage.getItem('z3ncoding_categories') || '{{}}');
        let deleted = new Set(JSON.parse(localStorage.getItem('z3ncoding_deleted') || '[]'));
        
        let filteredVideos = [];
        let currentIndex = 0;
        const BATCH_SIZE = 40;

        function getCategoryColor(cat) {{
            if (cat === 'public') return 'var(--cat-public)';
            if (cat === 'least') return 'var(--cat-least)';
            if (cat === 'average') return 'var(--cat-avg)';
            if (cat === 'most') return 'var(--cat-most)';
            return 'transparent';
        }}

        function createVideoCard(vid) {{
            const card = document.createElement('div');
            card.className = 'video-card';
            const safeTitle = vid[1].replace(/"/g, '&quot;');
            const viewkey = vid[8];
            const currentCat = getVideoCategory(vid);
            const badgeColor = getCategoryColor(currentCat);
            
            card.innerHTML = `
                <a href="${{vid[2]}}" target="_blank" style="text-decoration:none; color:inherit; display:flex; flex-direction:column; height:100%;">
                    <div class="thumbnail-wrapper" data-preview="${{vid[11]}}">
                        ${{badgeColor !== 'transparent' ? `<div class="status-badge" style="background:${{badgeColor}};"></div>` : ''}}
                        <img class="thumbnail" src="${{vid[3]}}" alt="Thumbnail" loading="lazy" onerror="this.style.display='none'">
                        ${{vid[4] ? `<span class="duration">${{vid[4]}}</span>` : ''}}
                    </div>
                    <div class="video-info">
                        <div class="video-title" title="${{safeTitle}}">${{vid[1]}}</div>
                        <div class="video-meta">
                            <span>${{vid[6]}} views</span>
                            <span style="font-family:monospace; font-size:0.7rem; opacity:0.4;">${{viewkey}}</span>
                        </div>
                    </div>
                </a>
                <div class="category-actions" onclick="event.preventDefault();">
                    <button class="cat-btn btn-public" onclick="categorize('${{viewkey}}', 'public')" title="Public">PUB</button>
                    <button class="cat-btn btn-least" onclick="categorize('${{viewkey}}', 'least')" title="Least">MIN</button>
                    <button class="cat-btn btn-avg" onclick="categorize('${{viewkey}}', 'average')" title="Avg">AVG</button>
                    <button class="cat-btn btn-most" onclick="categorize('${{viewkey}}', 'most')" title="Most">MAX</button>
                    <button class="cat-btn btn-reset" onclick="categorize('${{viewkey}}', 'none')" title="Reset">↺</button>
                    <button class="cat-btn btn-delete" onclick="deleteVideo('${{viewkey}}')" title="Delete">✕</button>
                </div>
            `;
            return card;
        }}

        function renderNextBatch() {{
            const end = Math.min(currentIndex + BATCH_SIZE, filteredVideos.length);
            for (let i = currentIndex; i < end; i++) {{
                videoGrid.appendChild(createVideoCard(filteredVideos[i]));
            }}
            currentIndex = end;
        }}

        function getVideoCategory(vid) {{
            // localStorage takes precedence; treat empty string same as missing
            const localCat = categories[vid[8]];
            if (localCat && localCat !== '') return localCat;
            // Fall back to baked category
            const bakedCat = vid[9];
            if (bakedCat && bakedCat !== '') return bakedCat;
            return 'none';
        }}

        function filterAndSort() {{
            const query = searchInput.value.toLowerCase().trim();
            const sortMode = sortSelect.value;
            
            filteredVideos = ALL_VIDEOS.filter(vid => {{
                const cat = getVideoCategory(vid);
                const isDeleted = deleted.has(vid[8]);
                const matchesTab = (cat === currentTab);
                const matchesQuery = query === '' || vid[10].includes(query);
                return !isDeleted && matchesTab && matchesQuery;
            }});

            filteredVideos.sort((a, b) => {{
                if (sortMode === 'title-az') return a[1].localeCompare(b[1]);
                if (sortMode === 'views-desc') return b[7] - a[7];
                if (sortMode === 'duration-desc') return b[5] - a[5];
                return a[0] - b[0]; // Recently Scraped
            }});

            videoGrid.innerHTML = '';
            currentIndex = 0;
            visibleCount.textContent = filteredVideos.length;
            renderNextBatch();
        }}

        // Infinite scroll observer
        const observer = new IntersectionObserver((entries) => {{
            if (entries[0].isIntersecting && currentIndex < filteredVideos.length) {{
                renderNextBatch();
            }}
        }}, {{ rootMargin: '400px' }});
        
        observer.observe(document.getElementById('sentinel'));

        // Preview Rotation logic — uses event delegation with mouseenter/mouseleave
        let activePreviewWrapper = null;
        let previewInterval = null;
        let previewFrame = 1;

        function startPreview(wrapper) {{
            const originalSrc = wrapper.getAttribute('data-preview');
            if (!originalSrc || originalSrc === 'undefined' || originalSrc === 'null' || originalSrc === '') return;

            activePreviewWrapper = wrapper;

            let previewImg = wrapper.querySelector('.preview-img');
            if (!previewImg) {{
                previewImg = document.createElement('img');
                previewImg.className = 'preview-img';
                previewImg.setAttribute('loading', 'eager');
                wrapper.appendChild(previewImg);
            }}

            // Reset inline opacity so the CSS :hover rule takes effect again
            previewImg.style.opacity = '';

            // Determine URL pattern
            // Pattern 1: numbered jpg — e.g. .../thumbs_10/(...)16.jpg → cycle 1–16
            const numberedMatch = originalSrc.match(/^(.+?)(\\d+)(\\.jpg)$/i);
            // Pattern 2: vts parameter — e.g. /vts:1624 → increment by 20 per frame
            const vtsMatch = originalSrc.match(/vts:(\\d+)/);

            previewFrame = 1;
            let errorCount = 0;

            // On image load error, skip to next frame (don't show broken image)
            previewImg.onerror = function() {{
                errorCount++;
                if (errorCount > 4) {{
                    // Too many errors — this URL pattern doesn't support cycling
                    clearInterval(previewInterval);
                    previewInterval = null;
                    // Fall back to just showing the static thumbnail as preview
                    previewImg.src = originalSrc;
                    previewImg.onerror = function() {{ previewImg.style.opacity = '0'; }};
                    return;
                }}
                previewFrame = (previewFrame % 16) + 1;
            }};

            clearInterval(previewInterval);

            if (numberedMatch) {{
                // Cycle through frame numbers 1–16
                const base = numberedMatch[1];
                const ext = numberedMatch[3];
                previewImg.src = `${{base}}${{previewFrame}}${{ext}}`;
                previewInterval = setInterval(() => {{
                    previewFrame = (previewFrame % 16) + 1;
                    previewImg.src = `${{base}}${{previewFrame}}${{ext}}`;
                }}, 500);
            }} else if (vtsMatch) {{
                // Increment vts timestamp
                const baseVts = parseInt(vtsMatch[1]);
                previewImg.src = originalSrc.replace(/vts:\\d+/, `vts:${{baseVts + previewFrame * 20}}`);
                previewInterval = setInterval(() => {{
                    previewFrame = (previewFrame % 16) + 1;
                    previewImg.src = originalSrc.replace(/vts:\\d+/, `vts:${{baseVts + previewFrame * 20}}`);
                }}, 500);
            }} else {{
                // Static image — no frame cycling, just show as preview
                previewImg.src = originalSrc;
                previewImg.onerror = function() {{ previewImg.style.opacity = '0'; }};
            }}
        }}

        function stopPreview(wrapper) {{
            clearInterval(previewInterval);
            previewInterval = null;
            activePreviewWrapper = null;
            const previewImg = wrapper.querySelector('.preview-img');
            if (previewImg) {{
                previewImg.style.opacity = '0';
                previewImg.onerror = null;
                // Clear src after fade-out transition
                setTimeout(() => {{
                    if (previewImg.style.opacity === '0') {{
                        previewImg.removeAttribute('src');
                    }}
                }}, 250);
            }}
        }}

        // Delegate mouseenter/mouseleave on the grid (works for dynamically added cards)
        videoGrid.addEventListener('mouseenter', e => {{
            const wrapper = e.target.closest('.thumbnail-wrapper');
            if (wrapper && wrapper !== activePreviewWrapper) {{
                startPreview(wrapper);
            }}
        }}, true);

        videoGrid.addEventListener('mouseleave', e => {{
            const wrapper = e.target.closest('.thumbnail-wrapper');
            if (wrapper) {{
                stopPreview(wrapper);
            }}
        }}, true);

        function setTab(tab) {{
            currentTab = tab;
            
            // Update sidebar active state
            document.querySelectorAll('.nav-btn').forEach(btn => {{
                const text = btn.innerText.toLowerCase();
                const isMain = tab === 'none' && text.includes('main');
                const isMatch = text.includes(tab) && tab !== 'none';
                btn.classList.toggle('active', isMain || isMatch);
            }});
            
            // Close mobile menu if open
            document.getElementById('sidebar').classList.remove('mobile-open');
            
            videoGrid.innerHTML = '';
            setTimeout(filterAndSort, 0);
            window.scrollTo(0, 0);
        }}

        function categorize(vk, cat) {{
            if (cat === 'none') delete categories[vk];
            else categories[vk] = cat;
            localStorage.setItem('z3ncoding_categories', JSON.stringify(categories));
            saveToFiles();
            filterAndSort();
        }}

        function deleteVideo(vk) {{
            if (confirm('Move to blacklist and hide from view?')) {{
                deleted.add(vk);
                localStorage.setItem('z3ncoding_deleted', JSON.stringify([...deleted]));
                saveToFiles();
                filterAndSort();
            }}
        }}

        function toggleModal(id) {{
            if (id === 'export-modal') document.getElementById('export-textarea').value = JSON.stringify(categories, null, 2);
            if (id === 'blacklist-modal') document.getElementById('blacklist-textarea').value = [...deleted].join('\\n');
            document.getElementById(id).classList.add('visible');
            document.getElementById('modal-overlay').classList.add('visible');
        }}

        function closeModals() {{
            document.querySelectorAll('.modal').forEach(m => m.classList.remove('visible'));
            document.getElementById('modal-overlay').classList.remove('visible');
        }}

        function clearBlacklist() {{
            if (confirm('Clear entire blacklist? This cannot be undone.')) {{
                deleted.clear(); localStorage.setItem('z3ncoding_deleted', '[]'); filterAndSort(); closeModals();
            }}
        }}

        function resetLocalStorage() {{
            if (confirm('Reset all browser-saved categories and blacklist?\\nThe baked-in data from categories.json will be used instead.\\n\\nThis cannot be undone.')) {{
                categories = {{}};
                deleted = new Set();
                localStorage.removeItem('z3ncoding_categories');
                localStorage.removeItem('z3ncoding_deleted');
                filterAndSort();
            }}
        }}

        searchInput.addEventListener('input', () => {{
            clearTimeout(window.searchTimeout);
            window.searchTimeout = setTimeout(() => {{
                videoGrid.innerHTML = '';
                setTimeout(filterAndSort, 0);
            }}, 300);
        }});
        
        sortSelect.addEventListener('change', () => {{
            videoGrid.innerHTML = '';
            setTimeout(filterAndSort, 0);
        }});
        
        window.addEventListener('scroll', () => {{
            backToTop.classList.toggle('visible', window.scrollY > 500);
        }});

        // ===== File System Access API — Auto-save categories & blacklist to disk =====
        const DB_NAME = 'z3ncoding_fsapi';
        const DB_STORE = 'handles';
        const DB_KEY = 'projectDir';
        let dirHandle = null;

        function openDB() {{
            return new Promise((resolve, reject) => {{
                const req = indexedDB.open(DB_NAME, 1);
                req.onupgradeneeded = () => {{ req.result.createObjectStore(DB_STORE); }};
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            }});
        }}

        async function saveDirHandle(handle) {{
            const db = await openDB();
            const tx = db.transaction(DB_STORE, 'readwrite');
            tx.objectStore(DB_STORE).put(handle, DB_KEY);
            return new Promise((resolve, reject) => {{
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
            }});
        }}

        async function loadDirHandle() {{
            const db = await openDB();
            const tx = db.transaction(DB_STORE, 'readonly');
            const req = tx.objectStore(DB_STORE).get(DB_KEY);
            return new Promise((resolve, reject) => {{
                req.onsuccess = () => resolve(req.result || null);
                req.onerror = () => reject(req.error);
            }});
        }}

        function updateSyncUI(state, msg) {{
            const el = document.getElementById('sync-status');
            const btn = document.getElementById('connect-folder-btn');
            el.className = 'sync-status ' + state;
            el.textContent = msg;
            if (state === 'connected') {{
                btn.classList.add('connected');
                btn.textContent = '✅ Folder Connected';
            }} else if (state === 'disconnected') {{
                btn.classList.remove('connected');
                btn.textContent = '📁 Connect Folder';
            }}
        }}

        async function connectFolder() {{
            try {{
                // File System Access API is blocked on file:// URLs
                if (location.protocol === 'file:') {{
                    alert(
                        'Cannot connect folders when opened via file://\\n\\n' +
                        'The File System Access API requires an HTTP server.\\n\\n' +
                        'Run this command in your project folder:\\n' +
                        '   python serve.py\\n\\n' +
                        'It will auto-open this page in Chrome at http://localhost:8888'
                    );
                    updateSyncUI('disconnected', '⚠ Run "python serve.py" to enable');
                    return;
                }}
                if (!window.showDirectoryPicker) {{
                    alert('Your browser does not support the File System Access API. Please use Chrome or Edge.');
                    return;
                }}
                dirHandle = await window.showDirectoryPicker({{ mode: 'readwrite' }});
                await saveDirHandle(dirHandle);
                updateSyncUI('connected', '✓ Connected — auto-saving to disk');
                // Immediately save current state
                await saveToFiles();
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    console.error('Connect folder error:', err);
                    updateSyncUI('disconnected', '\u26a0 Connection failed: ' + err.message);
                    alert('Connect folder failed:\\n' + err.name + ': ' + err.message);
                }}
            }}
        }}

        async function writeFile(handle, name, content) {{
            try {{
                const fileHandle = await handle.getFileHandle(name, {{ create: true }});
                const writable = await fileHandle.createWritable();
                await writable.write(content);
                await writable.close();
                return true;
            }} catch (err) {{
                console.error(`Error writing ${{name}}:`, err);
                return false;
            }}
        }}

        async function readFile(handle, name) {{
            try {{
                const fileHandle = await handle.getFileHandle(name);
                const file = await fileHandle.getFile();
                return await file.text();
            }} catch (err) {{
                // File doesn't exist yet — that's OK
                return null;
            }}
        }}

        let saveTimeout = null;
        function saveToFiles() {{
            // Debounce saves to avoid hammering disk on rapid clicks
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(async () => {{
                if (!dirHandle) return;

                // Verify we still have permission
                try {{
                    const perm = await dirHandle.queryPermission({{ mode: 'readwrite' }});
                    if (perm !== 'granted') {{
                        const req = await dirHandle.requestPermission({{ mode: 'readwrite' }});
                        if (req !== 'granted') {{
                            updateSyncUI('disconnected', '⚠ Permission denied — click to reconnect');
                            dirHandle = null;
                            return;
                        }}
                    }}
                }} catch(err) {{
                    updateSyncUI('disconnected', '⚠ Permission lost — click to reconnect');
                    dirHandle = null;
                    return;
                }}

                updateSyncUI('saving', '💾 Saving...');

                // Build merged categories: start with embedded defaults, overlay localStorage
                const mergedCategories = {{}};
                for (const vid of ALL_VIDEOS) {{
                    if (vid[9] && vid[9] !== 'none') mergedCategories[vid[8]] = vid[9];
                }}
                Object.assign(mergedCategories, categories);
                // Remove 'none' entries
                for (const k of Object.keys(mergedCategories)) {{
                    if (mergedCategories[k] === 'none') delete mergedCategories[k];
                }}

                const catOk = await writeFile(dirHandle, 'categories.json', JSON.stringify(mergedCategories, null, 2));
                const blOk = await writeFile(dirHandle, 'blacklist.txt', [...deleted].join('\\n') + '\\n');

                if (catOk && blOk) {{
                    updateSyncUI('connected', '✓ Saved — ' + new Date().toLocaleTimeString());
                }} else {{
                    updateSyncUI('disconnected', '⚠ Write failed — click to reconnect');
                }}
            }}, 300);
        }}

        async function loadFromDisk() {{
            if (!dirHandle) return;

            try {{
                const perm = await dirHandle.queryPermission({{ mode: 'readwrite' }});
                if (perm !== 'granted') {{
                    // Can't auto-grant — need user gesture. Show UI hint.
                    updateSyncUI('disconnected', '🔄 Click "Connect Folder" to re-authorize');
                    return;
                }}
            }} catch(err) {{
                return;
            }}

            // Read categories from disk and merge
            const catText = await readFile(dirHandle, 'categories.json');
            if (catText) {{
                try {{
                    const diskCats = JSON.parse(catText);
                    // Disk categories are the baseline; localStorage overrides on top
                    const localCats = JSON.parse(localStorage.getItem('z3ncoding_categories') || '{{}}');
                    // Merge: disk first, then local overrides
                    const merged = Object.assign({{}}, diskCats, localCats);
                    categories = merged;
                    localStorage.setItem('z3ncoding_categories', JSON.stringify(categories));
                }} catch(e) {{
                    console.error('Error parsing disk categories:', e);
                }}
            }}

            // Read blacklist from disk and merge
            const blText = await readFile(dirHandle, 'blacklist.txt');
            if (blText) {{
                const diskDeleted = blText.split('\\n').map(s => s.trim()).filter(Boolean);
                const localDeleted = JSON.parse(localStorage.getItem('z3ncoding_deleted') || '[]');
                deleted = new Set([...diskDeleted, ...localDeleted]);
                localStorage.setItem('z3ncoding_deleted', JSON.stringify([...deleted]));
            }}

            updateSyncUI('connected', '✓ Connected — loaded from disk');
        }}

        // On page load: try to restore saved directory handle
        async function initFileSystem() {{
            if (location.protocol === 'file:') {{
                updateSyncUI('disconnected', '⚠ Use "python serve.py" for auto-save');
                return;
            }}
            try {{
                const saved = await loadDirHandle();
                if (saved) {{
                    dirHandle = saved;
                    await loadFromDisk();
                    // Re-render with merged data
                    filterAndSort();
                }}
            }} catch(err) {{
                console.log('No saved directory handle found:', err);
            }}
        }}

        // Initialize
        filterAndSort();
        initFileSystem();
    </script>
</body>
</html>"""
    
    with open(filename, "w", encoding="UTF-8") as f:
        f.write(html_start)
def main():
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

    output_file = "z3ncoding_videos_grid.html"
    write_html_grid(all_videos, output_file, saved_categories)
    
    print(f"\nSUCCESS! Generated {output_file}")
    print(f"Total unique videos processed: {len(all_videos)}")

if __name__ == "__main__":
    main()
