import urllib.parse
import json
import subprocess

url = "https://www.pornhub.com/view_video.php?viewkey=675954c9e5a48"
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

for f in reversed(formats):
    vcodec = f.get("vcodec")
    acodec = f.get("acodec")
    height = f.get("height")
    stream_url = f.get("url")
    ext = f.get("ext", "mp4")
    fps = f.get("fps") or ""

    if vcodec == "none" or not stream_url or not height:
        continue

    proto = f.get("protocol", "")
    if "m3u8" in proto:
        continue

    if height in seen_heights:
        continue

    label = f"{height}p"
    if fps and int(fps) > 30:
        label += f"@{int(fps)}fps"

    streams.append({
        "quality": label,
        "url": stream_url,
        "ext": ext,
        "has_audio": (acodec != "none" and acodec is not None),
    })
    seen_heights.add(height)

print(json.dumps({"streams": streams}, indent=2))
