with open("main/main.py", encoding="utf-8") as f:
    lines = f.readlines()

matches = [
    (i + 1, line.strip())
    for i, line in enumerate(lines)
    if "main_window.spectroscopy" in line and "sidebar_spectroscopy" not in line
]
print(f"Found {len(matches)} references to main_window.spectroscopy:")
for num, text in matches:
    print(f"  Line {num}: {text}")
