#!/usr/bin/env python3
"""
Local server for the video grid.
- Serves static files (HTML, thumbs, etc.)
- /api/streams?url=... → uses yt-dlp to extract direct video URLs at all qualities
"""
import http.server
import socketserver
import webbrowser
import os
import sys
import glob
import threading
import time
import json
import gzip
import subprocess
import urllib.parse
from curl_cffi import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

PORT = 8888
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
FILE = "z3ncoding_videos_grid.html"

# Constructed on first use of /api/categorize, not at import time, so the
# server still starts if ANTHROPIC_API_KEY/auth isn't configured.
_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic()
    return _anthropic_client

# Data files that can be read/written via API
DATA_FILES = {
    "categories": {"path": "categories.json", "type": "json", "default": {}},
    "categoriesSchema": {"path": "categories-schema.json", "type": "json", "default": []},
    "blacklist": {"path": "blacklist.txt", "type": "text", "default": []},
    "videos": {"path": "videos.json", "type": "json", "default": []},
    "playlists": {"path": "playlists.json", "type": "json", "default": {}},
    "tags": {"path": "tags.json", "type": "json", "default": {}},
    "history": {"path": "history.json", "type": "json", "default": []},
}

os.chdir(DIRECTORY)

# The React SPA (frontend/) is the primary UI and is served from "/".
# Vite builds it with base "./", so its assets resolve relative to wherever
# index.html is served from -- no rebuild needed to move it to the root.
FRONTEND_DIST = os.path.join(DIRECTORY, "frontend", "dist")

# URL prefixes that must always resolve against the project root rather than
# the SPA bundle. Thumbnails live at <root>/thumbs/ and the cards reference
# them relatively, so from "/" they must not be looked up inside dist/.
ROOT_OWNED_PREFIXES = ("thumbs/",)

# Responses smaller than this aren't worth the CPU to compress.
GZIP_MIN_BYTES = 1024

# Cache of serialized API payloads, keyed by absolute file path.
# Value: (stamp, raw_bytes, gzipped_bytes) where stamp is (st_mtime_ns, st_size),
# so any write to the underlying file invalidates the entry automatically.
_payload_cache = {}
_payload_cache_lock = threading.Lock()


def _invalidate_payload(path):
    """Drop a cached payload after its file is rewritten."""
    with _payload_cache_lock:
        _payload_cache.pop(os.path.abspath(path), None)


class Handler(http.server.SimpleHTTPRequestHandler):
    # Set by send_response() so end_headers() can avoid marking errors cacheable.
    _status_code = 200

    def send_response(self, code, message=None):
        self._status_code = int(code)
        super().send_response(code, message)

    def end_headers(self):
        self.send_header("Cache-Control", self._cache_control())
        # Allow the page to use the stream URLs cross-origin (needed for <video> src)
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def _cache_control(self):
        """
        Cache policy by content lifetime, not blanket no-store.

        Thumbnails are named by viewkey and Vite asset filenames are
        content-hashed, so both are immutable once written. API payloads and
        HTML change constantly and must never be held.
        """
        path = urllib.parse.urlparse(self.path).path
        cacheable = self._status_code in (200, 206, 304)
        if cacheable and path.startswith(("/thumbs/", "/assets/")):
            return "public, max-age=31536000, immutable"
        if path.startswith("/api/"):
            return "no-store"
        # HTML entry points: allow a cached copy but always revalidate (enables 304).
        return "no-cache"

    def translate_path(self, path):
        """
        Resolve static requests against the SPA bundle first, then the project
        root. Lets "/" serve the React app while /thumbs/, the legacy grid HTML
        and the JSON data files keep working from the root.
        """
        # super() sanitizes "..", so the result is always inside DIRECTORY.
        fs_path = super().translate_path(path)
        rel = os.path.relpath(fs_path, DIRECTORY)
        rel_url = "" if rel == "." else rel.replace(os.sep, "/")

        if rel_url.startswith(ROOT_OWNED_PREFIXES):
            return fs_path
        if rel_url in ("", "index.html"):
            return os.path.join(FRONTEND_DIST, "index.html")
        dist_candidate = os.path.join(FRONTEND_DIST, rel)
        if os.path.exists(dist_candidate):
            return dist_candidate
        return fs_path

    def log_message(self, format, *args):
        pass  # Suppress request logs for cleanliness

    def do_GET(self):
        # ── /api/proxy?url=<url> ────────────────────────────────────────────
        if self.path.startswith("/api/proxy"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            target_url = params.get("url", [""])[0]

            if not target_url:
                self._json_response(400, {"error": "Missing url"})
                return

            headers_sent = False
            upstream_headers = self._referer_headers(target_url)
            try:
                if ".m3u8" in target_url or "application/vnd.apple.mpegurl" in target_url:
                    res = requests.get(target_url, impersonate="chrome", headers=upstream_headers)

                    if res.status_code != 200 or not res.text.lstrip().startswith("#EXTM3U"):
                        self._json_response(502, {
                            "error": "Upstream did not return a valid playlist",
                            "status": res.status_code,
                        })
                        return

                    base_url = target_url.rsplit("/", 1)[0] + "/"
                    new_lines = []
                    for line in res.text.split("\n"):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            new_lines.append(line)
                        else:
                            if not line.startswith("http"):
                                full_url = urllib.parse.urljoin(base_url, line)
                            else:
                                full_url = line
                            proxy_url = f"/api/proxy?url={urllib.parse.quote(full_url)}"
                            new_lines.append(proxy_url)
                    
                    content = "\n".join(new_lines).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    headers_sent = True
                    self.wfile.write(content)
                else:
                    res = requests.get(target_url, impersonate="chrome", stream=True, headers=upstream_headers)
                    self.send_response(res.status_code)
                    self.send_header("Content-Type", res.headers.get("Content-Type", "application/octet-stream"))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    if "Content-Length" in res.headers:
                        self.send_header("Content-Length", res.headers["Content-Length"])
                    self.end_headers()
                    headers_sent = True
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            self.wfile.write(chunk)
            except Exception as e:
                print(f"Proxy error: {e}")
                if not headers_sent:
                    try:
                        self._json_response(502, {"error": f"Proxy error: {e}"})
                    except Exception:
                        pass
            return

        # ── /api/refresh-thumbnail?viewkey=<viewkey> ────────────────────────
        # Hover-preview thumbnails that come from Pornhub's signed CDN URLs
        # expire ~24h after scraping. Called by the frontend when a preview
        # image fails to load, so it can self-heal instead of staying broken.
        if self.path.startswith("/api/refresh-thumbnail"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            viewkey = params.get("viewkey", [""])[0]

            if not viewkey:
                self._json_response(400, {"error": "Missing viewkey"})
                return

            try:
                result = self._refresh_thumbnail(viewkey)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        # ── /api/streams?url=<encoded_url> ──────────────────────────────────
        if self.path.startswith("/api/streams"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            url = params.get("url", [None])[0]

            if not url:
                self._json_response(400, {"error": "Missing url param"})
                return

            try:
                result = self._get_streams(url)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        # ── /api/<resource> → read data files ────────────────────────────────
        if self.path.startswith("/api/"):
            resource = self.path.split("/")[2].split("?")[0]
            if resource in DATA_FILES:
                cfg = DATA_FILES[resource]
                try:
                    raw, gz = self._cached_payload(cfg)
                    self._send_bytes(200, raw, gz)
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
                return
            self._json_response(404, {"error": f"Unknown resource: {resource}"})
            return

        # ── everything else → serve static files ─────────────────────────────
        super().do_GET()

    # ── POST handler for data persistence ────────────────────────────────
    def do_POST(self):
        if self.path.startswith("/api/categorize"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                items = json.loads(body)
                result = self._categorize_videos(items)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        if self.path.startswith("/api/"):
            resource = self.path.split("/")[2].split("?")[0]
            if resource not in DATA_FILES:
                self._json_response(404, {"error": f"Unknown resource: {resource}"})
                return

            cfg = DATA_FILES[resource]
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                if cfg["type"] == "json":
                    data = json.loads(body)
                    self._write_json_file(cfg["path"], data)
                else:
                    items = json.loads(body)
                    text = "\n".join(str(item) for item in items) + "\n"
                    self._write_text_file(cfg["path"], text)
                _invalidate_payload(cfg["path"])
                self._json_response(200, {"ok": True})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        self._json_response(404, {"error": "Not found"})

    # CDN hostname substring → Referer required by that CDN's hotlink protection
    REFERER_BY_CDN = {
        "phncdn.com": "https://www.pornhub.com/",
        "xhcdn.com": "https://xhamster.com/",
    }

    def _referer_headers(self, target_url):
        host = urllib.parse.urlparse(target_url).netloc
        for cdn_suffix, referer in self.REFERER_BY_CDN.items():
            if host.endswith(cdn_suffix):
                return {"Referer": referer}
        return {}

    def _accepts_gzip(self):
        return "gzip" in self.headers.get("Accept-Encoding", "").lower()

    def _send_bytes(self, code, raw, gz=None):
        """Send a JSON body, preferring the pre-gzipped copy when acceptable."""
        body, encoding = raw, None
        if gz is not None and len(raw) > GZIP_MIN_BYTES and self._accepts_gzip():
            body, encoding = gz, "gzip"
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if encoding:
            self.send_header("Content-Encoding", encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, code, data):
        raw = json.dumps(data).encode("utf-8")
        gz = gzip.compress(raw, 6) if len(raw) > GZIP_MIN_BYTES else None
        self._send_bytes(code, raw, gz)

    def _cached_payload(self, cfg):
        """
        Return (raw, gzipped) JSON bytes for a data file, reusing the cached
        copy while the file's (mtime, size) is unchanged. Without this, every
        /api/videos hit re-reads and re-parses ~6MB from disk.
        """
        path = cfg["path"]
        try:
            st = os.stat(path)
            stamp = (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            stamp = None

        key = os.path.abspath(path)
        with _payload_cache_lock:
            entry = _payload_cache.get(key)
            if entry is not None and entry[0] == stamp:
                return entry[1], entry[2]

        # Built outside the lock: a cold-cache race just does the work twice
        # rather than blocking every other request behind a 6MB parse.
        if cfg["type"] == "json":
            data = self._read_json_file(path, cfg["default"])
        else:
            text = self._read_text_file(path)
            # Return text files as JSON arrays (one entry per line)
            data = [line for line in text.split("\n") if line.strip()]

        raw = json.dumps(data).encode("utf-8")
        gz = gzip.compress(raw, 6)
        with _payload_cache_lock:
            _payload_cache[key] = (stamp, raw, gz)
        return raw, gz

    def _read_json_file(self, path, default=None):
        if not os.path.exists(path):
            return default if default is not None else {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_text_file(self, path):
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_json_file(self, path, data):
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _write_text_file(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _categorize_videos(self, items):
        """
        Ask Claude to assign each {viewkey, title} in `items` to one of the
        existing categories.json categories, by title alone.

        Returns {"suggestions": [{"viewkey": ..., "category_id": ...}, ...]}.
        Raises on any failure (missing key, empty schema, refusal) - the
        caller wraps this in a try/except and reports a 500 with the message.
        """
        if not items:
            return {"suggestions": []}

        schema = self._read_json_file("categories-schema.json", [])
        if not schema:
            raise ValueError("No categories defined in categories-schema.json")

        # Only leaf-ish, human-named categories are useful suggestions - skip
        # entries with no name. Build "id: name" so Claude can match on the
        # readable name while we get back a validated id.
        id_by_choice = {}
        choices = []
        for cat in schema:
            cid, name = cat.get("id"), cat.get("name")
            if not cid or not name:
                continue
            choices.append(f"{cid}: {name}")
            id_by_choice[cid] = name

        if not choices:
            raise ValueError("No usable categories in categories-schema.json")

        from pydantic import BaseModel
        from typing import Literal

        CategoryId = Literal[tuple(id_by_choice.keys())]

        class VideoCategorization(BaseModel):
            viewkey: str
            category_id: CategoryId

        class CategorizationResult(BaseModel):
            suggestions: list[VideoCategorization]

        video_list = "\n".join(f"- {it['viewkey']}: {it['title']}" for it in items)
        categories_list = "\n".join(choices)

        client = _get_anthropic_client()
        response = client.messages.parse(
            model="claude-opus-5",
            max_tokens=4096,
            output_config={"effort": "low"},
            system=(
                "You categorize adult video titles into an existing category "
                "tree for a personal video library. Pick the single best-fitting "
                "category id for each video from the provided list, based only "
                "on its title. If nothing fits well, prefer a general/miscellaneous "
                "category over guessing narrowly."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Available categories (id: name):\n{categories_list}\n\n"
                    f"Videos to categorize (viewkey: title):\n{video_list}\n\n"
                    "Return one suggestion per video, in the same order."
                ),
            }],
            output_format=CategorizationResult,
        )

        if response.stop_reason == "refusal":
            raise ValueError("Claude declined to categorize these videos")

        result = response.parsed_output
        return {
            "suggestions": [
                {"viewkey": s.viewkey, "category_id": s.category_id}
                for s in result.suggestions
            ]
        }

    def _get_streams(self, url):
        """
        Use yt-dlp to get all available video+audio format URLs.
        Returns a list of {quality, url, ext} dicts sorted best-first.
        """
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--dump-json",
            "--no-warnings",
            "--impersonate", "chrome",
            url,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=30)
        info = json.loads(out)

        formats = info.get("formats", [])
        streams = []
        seen_heights = set()

        # Prefer formats that have both video AND audio merged
        # yt-dlp often gives separate video/audio tracks; we want combined or best single-file
        for f in reversed(formats):  # reversed = best quality last → best first after reversing
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            height = f.get("height")
            stream_url = f.get("url")
            ext = f.get("ext", "mp4")
            fps = f.get("fps") or ""

            # Must have video and a direct URL
            if vcodec == "none" or not stream_url or not height:
                continue

            # Skip direct MP4s because they require strict User-Agent/IP matching
            proto = f.get("protocol", "")
            if "m3u8" not in proto:
                continue

            # Skip duplicate heights
            if height in seen_heights:
                continue

            # Build quality label
            label = f"{height}p"
            if fps and int(fps) > 30:
                label += f"@{int(fps)}fps"

            proxy_url = f"/api/proxy?url={urllib.parse.quote(stream_url)}"
            streams.append({
                "quality": label,
                "height": height,
                "url": proxy_url,
                "ext": ext,
                "has_audio": acodec != "none",
            })
            seen_heights.add(height)

        # Sort highest quality first
        streams.sort(key=lambda x: x["height"], reverse=True)

        return {
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration"),
            "streams": streams,
        }

    def _scrape_page_thumbnail(self, video_url):
        """Re-fetch the video page and read its og:image/image_src meta tags."""
        res = requests.get(video_url, impersonate="chrome", timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.content, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        link = soup.find("link", rel="image_src")
        if link and link.get("href"):
            return link["href"]
        return ""

    def _thumbnail_via_ytdlp(self, video_url):
        cmd = [
            "yt-dlp", "--no-playlist", "--dump-json", "--no-warnings",
            "--skip-download", "--impersonate", "chrome", video_url,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=20)
        return json.loads(out).get("thumbnail", "") or ""

    def _refresh_thumbnail(self, viewkey):
        """
        Re-scrape a fresh remoteThumbnail for one video and persist it back
        to videos.json, so a hover-preview that failed because its signed
        CDN URL expired self-heals for next time.
        """
        videos = self._read_json_file(DATA_FILES["videos"]["path"], [])
        record = next((v for v in videos if v.get("viewkey") == viewkey), None)
        if record is None:
            return {"error": "Unknown viewkey", "remoteThumbnail": ""}

        video_url = record.get("url", "")
        fresh = ""
        if video_url:
            try:
                fresh = self._scrape_page_thumbnail(video_url)
            except Exception:
                fresh = ""
            if not fresh:
                try:
                    fresh = self._thumbnail_via_ytdlp(video_url)
                except Exception:
                    fresh = ""

        if fresh and fresh != record.get("remoteThumbnail"):
            record["remoteThumbnail"] = fresh
            self._write_json_file(DATA_FILES["videos"]["path"], videos)
            _invalidate_payload(DATA_FILES["videos"]["path"])

        return {"remoteThumbnail": fresh}


socketserver.ThreadingTCPServer.allow_reuse_address = True

# Check for --no-browser flag
NO_BROWSER = "--no-browser" in sys.argv

# --legacy opens the old generated grid instead of the React app.
LEGACY_UI = "--legacy" in sys.argv
if not LEGACY_UI and not os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
    print("warning: frontend/dist not built -- falling back to the legacy grid.")
    print("         run 'npm run build' in frontend/ to use the React UI.")
    LEGACY_UI = True

BIND_HOST = os.environ.get("BIND_HOST", "100.116.128.90")  # Tailscale IP only; not LAN-exposed

with socketserver.ThreadingTCPServer((BIND_HOST, PORT), Handler) as httpd:
    # BIND_HOST is a Tailscale IP, so "localhost" would not reach this server.
    origin = f"http://{BIND_HOST}:{PORT}"
    url = f"{origin}/{FILE}?v={int(time.time())}" if LEGACY_UI else f"{origin}/"
    print(f"Serving {'legacy grid' if LEGACY_UI else 'React UI'} at {origin}")
    if not NO_BROWSER:
        print(f"Opening {url}")
    print("Press Ctrl+C to stop.\n")

    def open_browser():
        profile_dir = os.path.expanduser("~/.cache/porn-project-chrome-profile")
        os.makedirs(profile_dir, exist_ok=True)

        # Clean up stale Chrome lock files that cause transparent/blank windows
        for lock_file in glob.glob(os.path.join(profile_dir, "**", "*.lock"), recursive=True):
            try:
                os.remove(lock_file)
            except OSError:
                pass
        singleton = os.path.join(profile_dir, "SingletonLock")
        if os.path.exists(singleton):
            try:
                os.remove(singleton)
            except OSError:
                pass

        # Chrome flags:
        #   --autoplay-policy=no-user-gesture-required  → videos autoplay without click
        #   --ozone-platform=wayland                    → proper Wayland rendering (no transparency)
        #   --enable-features=UseOzonePlatform          → enable ozone
        #   --disable-gpu-sandbox                       → prevent GPU sandbox issues on Wayland
        #   --no-first-run --no-default-browser-check   → skip Chrome first-run prompts
        #   --test-type                                 → hides "unsupported command-line flag" warnings
        cmd_args = [
            "google-chrome-stable",
            "--autoplay-policy=no-user-gesture-required",
            "--ozone-platform=wayland",
            "--enable-features=UseOzonePlatform",
            "--disable-gpu-sandbox",
            "--test-type",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1920,1080",
            url
        ]

        start_time = time.time()
        success = False
        try:
            res = subprocess.run(cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # If it exited very quickly with a non-zero exit code, it probably crashed.
            if res.returncode != 0 and (time.time() - start_time) < 1.5:
                success = False
            else:
                success = True
        except FileNotFoundError:
            success = False

        if not success:
            # Fallback: try without GPU/Wayland flags
            cmd_fallback = [
                "google-chrome-stable",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-gpu",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                url
            ]
            start_time = time.time()
            try:
                res = subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode != 0 and (time.time() - start_time) < 1.5:
                    success = False
                else:
                    success = True
            except FileNotFoundError:
                success = False

        if not success:
            webbrowser.open(url)
            return

        print("Browser window closed. Shutting down server...")
        httpd.shutdown()

    if not NO_BROWSER:
        threading.Timer(0.5, open_browser).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
