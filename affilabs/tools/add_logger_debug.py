#!/usr/bin/env python3
"""Add print after 'Entering try block...'"""

with open("utils/led_calibration.py", encoding="utf-8") as f:
    lines = f.readlines()

# Find "Entering try block" line
for i, line in enumerate(lines):
    if "Entering try block" in line:
        print(f"Found at line {i+1}")
        # Add print statement after it
        lines.insert(i + 1, '        print("🔥 About to call logger.info...")\\n')
        break

# Write back
with open("utils/led_calibration.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("[OK] Print added!")
