import json
import re
import os

input_file = '/home/z3ncoding123/.antigravity/projects/porn-project/categories.json'

print("Reading original categories.json...")
with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines read: {len(lines)}")

pattern = re.compile(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"')

processed_entries = [] # list of (original_line_num, key, value)

for idx, line in enumerate(lines):
    line_num = idx + 1
    match = pattern.search(line)
    if match:
        key = match.group(1)
        val = match.group(2)
        processed_entries.append((line_num, key, val))

print(f"Parsed {len(processed_entries)} key-value entries.")

final_categories = {}
removed_least_avg_count = 0
removed_most_count = 0
moved_to_pending_count = 0
kept_count = 0

for line_num, key, val in processed_entries:
    # 1. Reset/uncategorize average and least liked videos.
    # "every instance that is categorized inside of both least liked and average categories"
    if val in ("least", "average"):
        removed_least_avg_count += 1
        continue
    
    # 2. Clear/uncategorize lines 674-1474 sending them back to "Main category"
    # (only for videos in "Most Liked" category)
    if 674 <= line_num <= 1474 and val == "most":
        removed_most_count += 1
        continue
        
    # 3. Move lines 201-673 to the new "Pending" category
    # (only for videos in "Most Liked" category)
    if 201 <= line_num <= 673 and val == "most":
        final_categories[key] = "pending"
        moved_to_pending_count += 1
        continue
        
    # Keep others
    final_categories[key] = val
    kept_count += 1

print("\n--- Summary of Changes ---")
print(f"Removed (least/average): {removed_least_avg_count}")
print(f"Removed (most in 674-1474): {removed_most_count}")
print(f"Moved to Pending (most in 201-673): {moved_to_pending_count}")
print(f"Kept entries: {kept_count}")
print(f"Total entries in output: {len(final_categories)}")

# Save to categories.json
print("\nSaving new categories.json...")
with open(input_file, 'w', encoding='utf-8') as f:
    json.dump(final_categories, f, indent=2)

print("Saved successfully!")
