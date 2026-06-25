import re

template_path = "z3ncoding_videos_grid.template.html"

print("Reading template file...")
with open(template_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix resetLocalStorage confirm dialog multiline string
old_confirm_pattern = r"if\s*\(confirm\('Reset all browser-saved categories and blacklist\?\n\s*The baked-in data from categories\.json will be used instead\.\n\n\s*This cannot be undone\.'\)\)\s*\{"

# Let's perform a direct replace for safety
old_confirm = """        if (confirm('Reset all browser-saved categories and blacklist?
The baked-in data from categories.json will be used instead.

This cannot be undone.')) {"""

new_confirm = """        if (confirm('Reset all browser-saved categories and blacklist?\\nThe baked-in data from categories.json will be used instead.\\n\\nThis cannot be undone.')) {"""

if old_confirm in content:
    content = content.replace(old_confirm, new_confirm)
    print("Fixed resetLocalStorage confirm dialog multiline string.")
else:
    # Try with different line ending formatting in case of \r\n
    old_confirm_rn = old_confirm.replace("\n", "\r\n")
    if old_confirm_rn in content:
        content = content.replace(old_confirm_rn, new_confirm)
        print("Fixed resetLocalStorage confirm dialog multiline string (CRLF).")
    else:
        print("WARNING: could not find old_confirm string directly. Trying regex replacement...")
        # Use regex to find it
        regex_pattern = r"confirm\('Reset all browser-saved categories and blacklist\?[\s\S]*?This cannot be undone\.'"
        content, count = re.subn(regex_pattern, "confirm('Reset all browser-saved categories and blacklist?\\\\nThe baked-in data from categories.json will be used instead.\\\\n\\\\nThis cannot be undone.'", content)
        print(f"Regex replacements made: {count}")

# 2. Fix the split and join in writeFile
old_write = """            const blOk  = await writeFile(dirHandle,'blacklist.txt', [...deleted].join('\\n')+'
');"""
new_write = """            const blOk  = await writeFile(dirHandle,'blacklist.txt', [...deleted].join('\\n')+'\\n');"""

if old_write in content:
    content = content.replace(old_write, new_write)
    print("Fixed blOk join multiline string.")
else:
    old_write_rn = old_write.replace("\n", "\r\n")
    if old_write_rn in content:
        content = content.replace(old_write_rn, new_write)
        print("Fixed blOk join multiline string (CRLF).")
    else:
        print("WARNING: could not find old_write string directly. Trying regex replacement...")
        regex_pattern2 = r"join\(\'\\n\'\)\s*\+\s*\'\s*\n\s*\'"
        content, count = re.subn(regex_pattern2, "join('\\\\n') + '\\\\n'", content)
        print(f"Regex replacements made for join: {count}")

# Write the cleaned template back
with open(template_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Template cleanup complete.")
