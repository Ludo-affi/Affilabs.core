"""Fix all references to the old status bar."""

import re

with open("Old software/main/main.py", encoding="utf-8") as f:
    content = f.read()

# Replace ui.status references
content = re.sub(
    r"self\.main_window\.ui\.status\.setText\([^)]+\)",
    'logger.info("Status updated")',
    content,
)
content = re.sub(
    r"self\.main_window\.ui\.status\.repaint\(\)",
    "# Status bar removed",
    content,
)
content = re.sub(r"self\.main_window\.ui\.status\.text\(\)", '"Connected"', content)
content = re.sub(
    r"self\.main_window\.ui\.device\.setText\([^)]+\)",
    "# Device display removed",
    content,
)
content = re.sub(r"self\.main_window\.ui\.adv_btn", "self.main_window.adv_btn", content)

with open("Old software/main/main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ Fixed all ui.status references!")
