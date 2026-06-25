import json
import sys
import os

sys.path.append("/home/z3ncoding123/.antigravity/projects/porn-project")
from generate_grid import write_html_grid, CATEGORIES_FILE

html_path = "z3ncoding_videos_grid.html"

print("Reading existing HTML file...")
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

print("Parsing ALL_VIDEOS from HTML...")
json_str = None
for line in content.splitlines():
    if "const ALL_VIDEOS = " in line:
        line = line.strip()
        # strip 'const ALL_VIDEOS = ' and the trailing ';'
        # Wait, if the line has been broken, it might be different, but in the old HTML it is a single line.
        if line.endswith(";"):
            json_str = line[len("const ALL_VIDEOS = "):-1]
        else:
            json_str = line[len("const ALL_VIDEOS = "):]
        break

if not json_str:
    print("ERROR: Could not find ALL_VIDEOS in HTML file!")
    sys.exit(1)

# Convert the array-of-arrays back to the dict format expected by the scraper
raw_data = json.loads(json_str)
print(f"Loaded {len(raw_data)} videos from cache.")

all_videos = []
for item in raw_data:
    # Item structure:
    # 0: idx
    # 1: title
    # 2: url
    # 3: thumbnail
    # 4: duration
    # 5: raw_duration
    # 6: views
    # 7: raw_views
    # 8: viewkey
    # 9: category
    # 10: lowercase_title
    # 11: remote_thumb
    all_videos.append({
        'title': item[1],
        'url': item[2],
        'thumbnail': item[3],
        'duration': item[4],
        'raw_duration': item[5],
        'views': item[6],
        'raw_views': item[7],
        'viewkey': item[8],
        'remote_thumbnail': item[11] if len(item) > 11 else ''
    })

# Load categories
saved_categories = {}
if os.path.exists(CATEGORIES_FILE):
    with open(CATEGORIES_FILE, "r") as f:
        saved_categories = json.load(f)

print("Calling write_html_grid with cached data...")
write_html_grid(all_videos, html_path, saved_categories)
print("Regeneration complete!")
