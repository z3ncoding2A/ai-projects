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

    # Optimized dynamic HTML template
    html_start = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>z3ncoding Video Library ({len(all_videos)})</title>
    <style>
        :root {{
            --bg-color: #0a0a0a;
            --card-bg: #161616;
            --text-color: #efefef;
            --accent-color: #ff9000;
            --secondary-text: #888;
            --border-color: #333;
            --hover-shadow: rgba(255, 144, 0, 0.25);
            --least-color: #555;
            --average-color: #3498db;
            --most-color: #e74c3c;
            --public-color: #2ecc71;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            line-height: 1.5;
        }}

        header {{
            position: sticky;
            top: 0;
            background-color: rgba(10, 10, 10, 0.95);
            backdrop-filter: blur(10px);
            z-index: 1000;
            padding: 8px 10px;
            border-bottom: 1px solid var(--border-color);
        }}
        .header-content {{
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
        }}
        h1 {{
            margin: 0;
            color: var(--accent-color);
            font-size: 1.2rem;
            letter-spacing: -0.5px;
        }}
        .category-tabs {{
            display: flex;
            gap: 8px;
            flex-wrap: nowrap;
            overflow-x: auto;
            width: 100%;
            justify-content: center;
            padding-bottom: 4px;
            scrollbar-width: none;
        }}
        .category-tabs::-webkit-scrollbar {{ display: none; }}

        .tab-btn {{
            padding: 4px 12px;
            background: #222;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            color: var(--secondary-text);
            cursor: pointer;
            font-size: 0.75rem;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .tab-btn:hover {{ background: #333; color: white; }}
        .tab-btn.active {{
            background: var(--accent-color);
            color: black;
            border-color: var(--accent-color);
            font-weight: bold;
        }}

        .toolbar {{
            display: flex;
            gap: 8px;
            width: 100%;
            max-width: 900px;
            align-items: center;
        }}

        #search-input {{
            flex-grow: 1;
            padding: 6px 12px;
            background-color: #222;
            border: 1px solid var(--border-color);
            border-radius: 25px;
            color: white;
            font-size: 0.8rem;
            outline: none;
            min-width: 0;
        }}
        #search-input:focus {{ border-color: var(--accent-color); box-shadow: 0 0 8px var(--hover-shadow); }}

        select#sort-select {{
            padding: 6px 10px;
            background-color: #222;
            border: 1px solid var(--border-color);
            border-radius: 25px;
            color: white;
            font-size: 0.8rem;
            cursor: pointer;
            appearance: none;
        }}

        .stats {{ font-size: 0.75rem; color: var(--secondary-text); }}

        .main-container {{ max-width: 1600px; margin: 0 auto; padding: 15px 10px; }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            min-height: 500px;
        }}

        .video-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            text-decoration: none;
            color: inherit;
            position: relative;
            content-visibility: auto;
            contain-intrinsic-size: 300px 400px;
        }}

        .video-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.5), 0 0 15px var(--hover-shadow);
            border-color: var(--accent-color);
        }}

        .thumbnail-wrapper {{
            position: relative;
            width: 100%;
            padding-top: 56.25%;
            background-color: #000;
        }}

        .thumbnail {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            object-fit: cover;
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

        .duration {{
            position: absolute;
            bottom: 8px; right: 8px;
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }}

        .video-info {{ padding: 15px; flex-grow: 1; display: flex; flex-direction: column; }}

        .video-title {{
            font-size: 0.95rem; font-weight: 600;
            margin-bottom: 10px; line-height: 1.4;
            height: 2.8em; overflow: hidden;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        }}

        .video-meta {{
            font-size: 0.8rem; color: var(--secondary-text);
            margin-top: auto; display: flex;
            justify-content: space-between; align-items: center;
        }}

        .category-actions {{
            display: flex; gap: 5px; padding: 10px 15px;
            background: rgba(0,0,0,0.3); border-top: 1px solid #222;
        }}

        .cat-btn {{
            flex: 1; padding: 5px; border: none; border-radius: 4px;
            font-size: 0.7rem; cursor: pointer; font-weight: bold;
            display: flex; align-items: center; justify-content: center;
        }}
        .btn-public {{ background: var(--public-color); color: white; }}
        .btn-least {{ background: var(--least-color); color: white; }}
        .btn-avg {{ background: var(--average-color); color: white; }}
        .btn-most {{ background: var(--most-color); color: white; }}
        .btn-reset {{ background: #333; color: #888; }}
        .btn-delete {{ background: #c0392b; color: white; }}

        .modal {{
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: #1a1a1a; border: 2px solid var(--accent-color);
            padding: 20px; z-index: 2000; width: 80%; max-width: 600px;
            border-radius: 12px; display: none;
        }}
        .modal.visible {{ display: block; }}
        .modal-overlay {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); z-index: 1999; display: none;
        }}
        .modal-overlay.visible {{ display: block; }}
        #back-to-top {{
            position: fixed; bottom: 30px; right: 30px;
            background-color: var(--accent-color); color: black;
            width: 50px; height: 50px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            opacity: 0; transition: opacity 0.3s; z-index: 100;
        }}
        #back-to-top.visible {{ opacity: 1; }}

        #sentinel {{ height: 50px; width: 100%; }}

        @media (max-width: 600px) {{
            .grid {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }}
            .category-tabs {{ justify-content: flex-start; }}
            .toolbar {{ flex-wrap: wrap; gap: 4px; }}
            #search-input {{ order: -1; flex-basis: 100%; }}
            .tab-btn {{ padding: 4px 8px; font-size: 0.7rem; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <h1>z3ncoding Video Library</h1>
            <div class="category-tabs">
                <button class="tab-btn active" onclick="setTab('none')">Main List</button>
                <button class="tab-btn" onclick="setTab('public')">Public</button>
                <button class="tab-btn" onclick="setTab('least')">Least Liked</button>
                <button class="tab-btn" onclick="setTab('average')">Averagely Liked</button>
                <button class="tab-btn" onclick="setTab('most')">Most Liked</button>
            </div>
            <div class="toolbar">
                <input type="text" id="search-input" placeholder="Search videos by title..." autocomplete="off">
                <select id="sort-select">
                    <option value="newest">Recently Scraped</option>
                    <option value="title-az">Title (A-Z)</option>
                    <option value="views-desc">Most Viewed</option>
                    <option value="duration-desc">Longest Duration</option>
                </select>
                <button class="tab-btn" onclick="toggleModal('export-modal')" style="border-color: #27ae60; color: #27ae60;">Export</button>
                <button class="tab-btn" onclick="toggleModal('blacklist-modal')" style="border-color: #c0392b; color: #c0392b;">Blacklist</button>
            </div>
            <div class="stats">Showing <span id="visible-count">0</span> / {len(all_videos)} videos</div>
        </div>
    </header>

    <div class="modal-overlay" id="modal-overlay" onclick="closeModals()"></div>
    <div class="modal" id="blacklist-modal">
        <h2>Local Blacklist</h2>
        <textarea id="blacklist-textarea" style="width:100%;height:200px;" readonly></textarea>
        <div style="margin-top: 15px; display: flex; gap: 10px;">
            <button class="tab-btn" onclick="closeModals()">Close</button>
            <button class="tab-btn" onclick="clearBlacklist()" style="background: #c0392b; color: white;">Clear All</button>
        </div>
    </div>
    <div class="modal" id="export-modal">
        <h2>Export Categories</h2>
        <textarea id="export-textarea" style="width:100%;height:200px;" readonly></textarea>
        <div style="margin-top: 15px; display: flex; gap: 10px;">
            <button class="tab-btn" onclick="closeModals()">Close</button>
        </div>
    </div>

    <main class="main-container">
        <div class="grid" id="video-grid"></div>
        <div id="sentinel"></div>
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

        function createVideoCard(vid) {{
            const card = document.createElement('div');
            card.className = 'video-card';
            const safeTitle = vid[1].replace(/"/g, '&quot;');
            
            card.innerHTML = `
                <a href="${{vid[2]}}" target="_blank" style="text-decoration:none; color:inherit;">
                    <div class="thumbnail-wrapper" data-preview="${{vid[11]}}">
                        <img class="thumbnail" src="${{vid[3]}}" alt="No Image" loading="lazy" onerror="this.style.display='none'">
                        ${{vid[4] ? `<span class="duration">${{vid[4]}}</span>` : ''}}
                    </div>
                    <div class="video-info">
                        <div class="video-title" title="${{safeTitle}}">${{vid[1]}}</div>
                        <div class="video-meta">
                            <span>${{vid[6]}}</span>
                            <span style="font-size:0.7rem; opacity:0.5;">${{vid[8]}}</span>
                        </div>
                    </div>
                </a>
                <div class="category-actions">
                    <button class="cat-btn btn-public" onclick="categorize('${{vid[8]}}', 'public')" title="Public">P</button>
                    <button class="cat-btn btn-least" onclick="categorize('${{vid[8]}}', 'least')" title="Least">L</button>
                    <button class="cat-btn btn-avg" onclick="categorize('${{vid[8]}}', 'average')" title="Avg">A</button>
                    <button class="cat-btn btn-most" onclick="categorize('${{vid[8]}}', 'most')" title="Most">M</button>
                    <button class="cat-btn btn-reset" onclick="categorize('${{vid[8]}}', 'none')" title="Reset">↺</button>
                    <button class="cat-btn btn-delete" onclick="deleteVideo('${{vid[8]}}')" title="Delete">🗑️</button>
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

        function filterAndSort() {{
            const query = searchInput.value.toLowerCase().trim();
            const sortMode = sortSelect.value;
            
            filteredVideos = ALL_VIDEOS.filter(vid => {{
                const cat = categories[vid[8]] || vid[9] || 'none';
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

        // Preview Rotation logic
        let previewInterval;
        document.addEventListener('mouseover', e => {{
            const wrapper = e.target.closest('.thumbnail-wrapper');
            if (!wrapper) return;
            
            const originalSrc = wrapper.getAttribute('data-preview');
            if (!originalSrc || originalSrc === 'undefined' || originalSrc === 'null' || originalSrc === '') return;

            let previewImg = wrapper.querySelector('.preview-img');
            if (!previewImg) {{
                previewImg = document.createElement('img');
                previewImg.className = 'preview-img';
                wrapper.appendChild(previewImg);
            }}
            
            const match = originalSrc.match(/(.+?)(\\d+)\\.jpg$/);
            const vtsMatch = originalSrc.match(/vts:(\\d+)/);
            let frame = 1;
            
            clearInterval(previewInterval);
            previewInterval = setInterval(() => {{
                if (match) previewImg.src = `${{match[1]}}${{frame}}.jpg`;
                else if (vtsMatch) previewImg.src = originalSrc.replace(/vts:\\d+/, `vts:${{parseInt(vtsMatch[1]) + frame * 20}}`);
                frame = (frame % 15) + 1;
            }}, 400);
        }});
        
        document.addEventListener('mouseout', e => {{
            const wrapper = e.target.closest('.thumbnail-wrapper');
            if (wrapper) {{
                clearInterval(previewInterval);
                const previewImg = wrapper.querySelector('.preview-img');
                if (previewImg) {{
                    previewImg.style.opacity = '0';
                    setTimeout(() => {{ if (previewImg.style.opacity === '0') previewImg.src = ''; }}, 200);
                }}
            }}
        }});

        function setTab(tab) {{
            currentTab = tab;
            document.querySelectorAll('.tab-btn').forEach(btn => {{
                const text = btn.innerText.toLowerCase();
                btn.classList.toggle('active', tab === 'none' ? text === 'main list' : text.includes(tab));
            }});
            videoGrid.innerHTML = '';
            setTimeout(filterAndSort, 0);
            window.scrollTo(0, 0);
        }}

        function categorize(vk, cat) {{
            if (cat === 'none') delete categories[vk];
            else categories[vk] = cat;
            localStorage.setItem('z3ncoding_categories', JSON.stringify(categories));
            filterAndSort();
        }}

        function deleteVideo(vk) {{
            if (confirm('Delete video?')) {{
                deleted.add(vk);
                localStorage.setItem('z3ncoding_deleted', JSON.stringify([...deleted]));
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
            if (confirm('Clear blacklist?')) {{
                deleted.clear(); localStorage.setItem('z3ncoding_deleted', '[]'); filterAndSort(); closeModals();
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

        filterAndSort();
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

    # --- Search for specific tags ---
    public_tags = ["public", "exhibition", "watched", "being watched"]
    print(f"\nScraping search results for tags: {public_tags}...")
    
    for tag in public_tags:
        for p in range(1, 4): # Scrape first 3 pages of each search
            search_videos = get_videos_from_search(tag, p)
            if not search_videos:
                break
                
            new_tag_count = 0
            for vid in search_videos:
                if vid['viewkey'] not in seen_viewkeys:
                    seen_viewkeys.add(vid['viewkey'])
                    all_videos.append(vid)
                    new_tag_count += 1
            
            print(f"Tag '{tag}' Page {p}: Found {len(search_videos)} videos, {new_tag_count} were new.")
            if new_tag_count == 0 and len(search_videos) > 0:
                break # Stop if we only see duplicates
            time.sleep(1)

    # --- Related Videos for "Most Liked" ---
    most_liked_keys = [k for k, v in saved_categories.items() if v == "most"]
    print(f"\nScraping related videos for {len(most_liked_keys)} 'Most Liked' videos...")
    
    for count, vk in enumerate(most_liked_keys, 1):
        related = get_related_videos(vk)
        if not related:
            continue
            
        new_rel_count = 0
        for vid in related[:10]:
            if vid['viewkey'] not in seen_viewkeys:
                seen_viewkeys.add(vid['viewkey'])
                all_videos.append(vid)
                new_rel_count += 1
        
        print(f"[{count}/{len(most_liked_keys)}] {vk}: Added {new_rel_count} new related videos.")
        time.sleep(1) # Small delay to avoid 429

    if not all_videos:
        print("No videos found. Check the profile URL or network connection.")
        return

    output_file = "z3ncoding_videos_grid.html"
    write_html_grid(all_videos, output_file, saved_categories)
    
    print(f"\nSUCCESS! Generated {output_file}")
    print(f"Total unique videos processed: {len(all_videos)}")

if __name__ == "__main__":
    main()
