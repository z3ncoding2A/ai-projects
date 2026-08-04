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
import subprocess
import urllib.parse
from curl_cffi import requests

PORT = 8888
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
FILE = "index.html"
_FRONTEND_INDEX = os.path.join(DIRECTORY, "frontend", "dist", "index.html")
if not os.path.exists(_FRONTEND_INDEX):
    # The legacy z3ncoding_videos_grid.html fallback was removed (2026-08-03) —
    # the React frontend is the only supported UI now. See plans/improvements_audit.md.
    print(f"WARNING: {_FRONTEND_INDEX} not found.")
    print("Run `npm install && npm run build` inside frontend/ before starting serve.py.\n")

# Data files that can be read/written via API
DATA_FILES = {
    "categories": {"path": "categories.json", "type": "json", "default": {}},
    "blacklist": {"path": "blacklist.txt", "type": "text", "default": []},
    "videos": {"path": "videos.json", "type": "json", "default": []},
    "playlists": {"path": "playlists.json", "type": "json", "default": {}},
    "tags": {"path": "tags.json", "type": "json", "default": {}},
    # Object keyed by viewkey: {lastWatched, count, lastPosition}. Default was
    # previously [] (a leftover from the legacy template's flat watched-list
    # format); the React store has always expected an object.
    "history": {"path": "history.json", "type": "json", "default": {}},
    "first_seen": {"path": "first_seen.json", "type": "json", "default": {}},
    # Named saved searches: name -> {searchQuery, minViews, minDuration, regex}
    "filter_presets": {"path": "filter_presets.json", "type": "json", "default": {}},
}

# Hostname suffixes /api/proxy is allowed to fetch. The proxy exists to get around
# CORS for HLS/video segment CDNs — without an allowlist it's an open SSRF-capable
# proxy for anyone who can reach this server. Add suffixes here if new source sites
# are added to the scraper.
ALLOWED_PROXY_SUFFIXES = (
    ".phncdn.com",
    ".pornhub.com",
    "pornhub.com",
    ".xhcdn.com",
    ".xhamster.com",
    "xhamster.com",
)

# In-process cache for yt-dlp stream extraction, keyed by source video URL.
# Avoids re-spawning yt-dlp (2-5s) every time the same video is replayed.
_STREAMS_CACHE = {}
STREAMS_CACHE_TTL = 2 * 60 * 60  # 2 hours — stream URLs are signed and expire anyway

os.chdir(DIRECTORY)


def _is_allowed_proxy_target(url):
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return any(host == s.lstrip(".") or host.endswith(s) for s in ALLOWED_PROXY_SUFFIXES)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.startswith("/thumbs/"):
            # Thumbnails are content-addressed by viewkey and never change once
            # written — safe to cache aggressively. This was previously no-store,
            # forcing a re-fetch of the entire thumbs/ dir (650MB+) on every reload.
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            # Everything else (API responses, the HTML shell, JS/CSS bundle) must
            # stay fresh — categories/blacklist/etc. change constantly.
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        # Allow the page to use the stream URLs cross-origin (needed for <video> src)
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        # pass  # Suppress request logs for cleanliness
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        # ── /api/proxy?url=<url> ────────────────────────────────────────────
        if self.path.startswith("/api/proxy"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            target_url = params.get("url", [""])[0]

            if not target_url:
                self._json_response(400, {"error": "Missing url"})
                return

            if not _is_allowed_proxy_target(target_url):
                self._json_response(403, {"error": "Host not in proxy allowlist"})
                return

            try:
                if ".m3u8" in target_url or "application/vnd.apple.mpegurl" in target_url:
                    res = requests.get(target_url, impersonate="chrome")
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
                    self.wfile.write(content)
                else:
                    res = requests.get(target_url, impersonate="chrome", stream=True)
                    self.send_response(res.status_code)
                    self.send_header("Content-Type", res.headers.get("Content-Type", "application/octet-stream"))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    if "Content-Length" in res.headers:
                        self.send_header("Content-Length", res.headers["Content-Length"])
                    self.end_headers()
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            self.wfile.write(chunk)
            except Exception as e:
                print(f"Proxy error: {e}")
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
                    if cfg["type"] == "json":
                        data = self._read_json_file(cfg["path"], cfg["default"])
                    else:
                        raw = self._read_text_file(cfg["path"])
                        # Return text files as JSON arrays (one entry per line)
                        data = [line for line in raw.split("\n") if line.strip()]
                    self._json_response(200, data)
                except Exception as e:
                    self._json_response(500, {"error": str(e)})
                return
            self._json_response(404, {"error": f"Unknown resource: {resource}"})
            return

        # ── Root path → serve frontend/dist/index.html if available ─────────
        if self.path in ("/", "/index.html"):
            frontend_index = os.path.join(DIRECTORY, "frontend", "dist", "index.html")
            if os.path.exists(frontend_index):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                with open(frontend_index, "rb") as f:
                    content = f.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # ── /assets/* → serve built static assets from frontend/dist/assets ──
        if self.path.startswith("/assets/"):
            asset_path = os.path.join(DIRECTORY, "frontend", "dist", self.path.lstrip("/"))
            if os.path.exists(asset_path):
                self.send_response(200)
                if asset_path.endswith(".js"):
                    self.send_header("Content-Type", "application/javascript")
                elif asset_path.endswith(".css"):
                    self.send_header("Content-Type", "text/css")
                self.send_header("Access-Control-Allow-Origin", "*")
                with open(asset_path, "rb") as f:
                    content = f.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # ── everything else → serve static files ─────────────────────────────
        super().do_GET()

    # ── POST handler for data persistence ────────────────────────────────
    def do_POST(self):
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
                self._json_response(200, {"ok": True})
            except Exception as e:
                self._json_response(500, {"error": str(e)})
            return

        self._json_response(404, {"error": "Not found"})

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_text_file(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _get_streams(self, url):
        """
        Use yt-dlp to get all available video+audio format URLs.
        Returns a list of {quality, url, ext} dicts sorted best-first.
        Cached per-URL for STREAMS_CACHE_TTL to avoid re-spawning yt-dlp on replay.
        """
        cached = _STREAMS_CACHE.get(url)
        if cached and (time.time() - cached[0]) < STREAMS_CACHE_TTL:
            return cached[1]

        result = self._extract_streams(url)
        _STREAMS_CACHE[url] = (time.time(), result)
        return result

    def _extract_streams(self, url):
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


socketserver.ThreadingTCPServer.allow_reuse_address = True

# Check for --no-browser flag
NO_BROWSER = "--no-browser" in sys.argv

BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1")  # localhost-only by default.
# /api/proxy and /api/<resource> POST are unauthenticated; binding 0.0.0.0 exposes
# an open proxy + writable data files to anyone on the LAN. Set BIND_HOST=0.0.0.0
# explicitly if you deliberately want LAN access.

with socketserver.ThreadingTCPServer((BIND_HOST, PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}/{FILE}?v={int(time.time())}"
    print(f"Serving at http://localhost:{PORT}")
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
