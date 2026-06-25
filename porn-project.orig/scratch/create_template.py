import re
import os

html_path = "/home/z3ncoding123/.antigravity/projects/porn-project/z3ncoding_videos_grid.html"
template_path = "/home/z3ncoding123/.antigravity/projects/porn-project/z3ncoding_videos_grid.template.html"
gen_path = "/home/z3ncoding123/.antigravity/projects/porn-project/generate_grid.py"

print("Reading HTML file...")
with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

print("Cleaning up Javascript syntax errors (multiline strings caused by \\n)...")
# Fix split('\n')
html_content = html_content.replace("blText.split('\n')", "blText.split('\\n')")
# In case it is on multiple lines due to literal newline:
html_content = re.sub(r"blText\.split\('\s*\n\s*'\)", "blText.split('\\\\n')", html_content)
# Let's do a direct replacement for the specific split pattern we saw:
html_content = html_content.replace("blText.split('\n').map", "blText.split('\\n').map")
# Wait, let's look at the exact pattern in the file:
# line 1244: const dDel = blText.split('
# line 1245: ').map(s=>s.trim()).filter(Boolean);
html_content = re.sub(r"blText\.split\('\n'\)", "blText.split('\\\\n')", html_content)
html_content = html_content.replace("blText.split('\n')", "blText.split('\\n')")
html_content = html_content.replace("blText.split('\r\n')", "blText.split('\\n')")

# Fix join('\n')
# line 1091: if (id === 'blacklist-modal') document.getElementById('blacklist-textarea').value = [...deleted].join('
# line 1092: ');
html_content = re.sub(r"\.join\('\n'\)", ".join('\\\\n')", html_content)
html_content = html_content.replace(".join('\n')", ".join('\\n')")
html_content = html_content.replace(".join('\r\n')", ".join('\\n')")

# Let's perform a very robust regex substitution to clean up split/join multilines
html_content = re.sub(r"split\(\'\n\'\)", "split('\\\\n')", html_content)
html_content = re.sub(r"join\(\'\n\'\)", "join('\\\\n')", html_content)

# Replace the title tag with placeholder
title_pattern = r"<title>z3ncoding Library \(\d+\)</title>"
html_content = re.sub(title_pattern, "<title>z3ncoding Library (__TOTAL_VIDEOS_COUNT__)</title>", html_content)

# Replace the count label with placeholder
count_pattern = r"/ \d+ videos"
html_content = re.sub(count_pattern, "/ __TOTAL_VIDEOS_COUNT__ videos", html_content)

# Find and replace the ALL_VIDEOS line
lines = html_content.splitlines()
found_json = False
for idx, line in enumerate(lines):
    if "const ALL_VIDEOS = [" in line:
        lines[idx] = "    const ALL_VIDEOS = __VIDEOS_JSON_DATA__;"
        print(f"Replaced ALL_VIDEOS line successfully at line {idx+1}.")
        found_json = True
        break

if not found_json:
    print("WARNING: const ALL_VIDEOS line not found!")

# Join the lines back up
html_template = "\n".join(lines)

# Write out the template file
with open(template_path, "w", encoding="utf-8") as f:
    f.write(html_template)
print(f"Template successfully written to {template_path}")

# Now, read generate_grid.py and modify the write_html_grid function to read and replace this template
with open(gen_path, "r", encoding="utf-8") as f:
    gen_content = f.read()

# Let's find def write_html_grid
start_idx = gen_content.find("def write_html_grid(all_videos, filename, saved_categories):")
end_idx = gen_content.find("def main():")

new_write_fn = """def write_html_grid(all_videos, filename, saved_categories):
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

    # Read template from file
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "z3ncoding_videos_grid.template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    # Replace placeholders
    html_content = html_template.replace("__TOTAL_VIDEOS_COUNT__", str(len(all_videos)))
    html_content = html_content.replace("__VIDEOS_JSON_DATA__", json.dumps(json_videos, ensure_ascii=False))

    with open(filename, "w", encoding="UTF-8") as f:
        f.write(html_content)
"""

if start_idx != -1 and end_idx != -1:
    updated_gen_content = gen_content[:start_idx] + new_write_fn + "\n" + gen_content[end_idx:]
    with open(gen_path, "w", encoding="utf-8") as f:
        f.write(updated_gen_content)
    print("Successfully updated generate_grid.py to load from template file.")
else:
    print("ERROR: Could not find function boundaries in generate_grid.py")
