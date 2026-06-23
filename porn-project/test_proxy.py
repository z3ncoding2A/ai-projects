import urllib.parse
from curl_cffi import requests

target_url = "https://ev-h.phncdn.com/hls/videos/202412/11/461710405/1080P_4000K_461710405.mp4/index-v1-a1.m3u8?validfrom=1781717557&validto=1781724757&ipa=1&hdl=-1&hash=Q5Jv67vEwP6qEwFmR9qM9qM9qM%3D" 
# Use a fresh URL from yt-dlp to be sure
import subprocess, json
url = "https://www.pornhub.com/view_video.php?viewkey=675954c9e5a48"
cmd = ["yt-dlp", "--dump-json", "--impersonate", "chrome", url]
out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
info = json.loads(out)
stream = next((f for f in reversed(info["formats"]) if f.get("ext")=="mp4" and "m3u8" in f.get("protocol","")), None)
target_url = stream["url"]

res = requests.get(target_url, impersonate="chrome")
text = res.text
new_lines = []
base_url = target_url.rsplit("/", 1)[0] + "/"
for line in text.split("\n"):
    if not line or line.startswith("#"):
        new_lines.append(line)
    else:
        if not line.startswith("http"):
            full_url = urllib.parse.urljoin(base_url, line)
        else:
            full_url = line
        proxy_url = f"/api/proxy?url={urllib.parse.quote(full_url)}"
        new_lines.append(proxy_url)

print("\n".join(new_lines)[:500])
