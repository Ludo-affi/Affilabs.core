#!/usr/bin/env python3
"""Add entry/try prints"""

with open("utils/led_calibration.py", encoding="utf-8") as f:
    lines = f.readlines()

# Insert after line 2847 (result = LEDCalibrationResult())
lines.insert(2847, "\n")
lines.insert(2848, '    print("\\n" + "="*80)\n')
lines.insert(2849, '    print("🔥🔥🔥 perform_alternative_calibration() ENTERED")\n')
lines.insert(2850, '    print("="*80 + "\\n")\n')
lines.insert(2851, "\n")

# Find try: after the insertion (should be around 2852+5 = 2857)
for i in range(2852, 2865):
    if lines[i].strip() == "try:":
        print(f"Found try: at line {i+1}")
        lines.insert(i + 1, '        print("🔥 Entering try block...")\n')
        break

with open("utils/led_calibration.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("✅ Entry and try prints added!")
