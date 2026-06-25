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
import glob
import threading
import time
import json
import subprocess
import urllib.parse
from curl_cffi import requests

PORT = 8888
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
FILE = "z3ncoding_videos_grid.html"

os.chdir(DIRECTORY)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        # Allow the page to use the stream URLs cross-origin (needed for <video> src)
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

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

        # ── everything else → serve static files ────────────────────────────
        super().do_GET()

    def _json_response(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


socketserver.ThreadingTCPServer.allow_reuse_address = True

with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}/{FILE}?v={int(time.time())}"
    print(f"Serving at http://localhost:{PORT}")
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

    threading.Timer(0.5, open_browser).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
