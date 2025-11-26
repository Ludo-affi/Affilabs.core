#!/usr/bin/env python3
"""Fix indentation in led_calibration.py"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the incorrectly indented lines (2851-2855 approximately)
# Find the line with "print("🔥🔥🔥 perform_alternative_calibration() ENTERED")"
for i, line in enumerate(lines):
    if '🔥🔥🔥 perform_alternative_calibration() ENTERED' in line:
        print(f"Found at line {i+1}: {line.strip()}")
        # Check surrounding lines
        print(f"Line {i}: {repr(lines[i-1])}")
        print(f"Line {i+1}: {repr(lines[i])}")
        print(f"Line {i+2}: {repr(lines[i+1])}")
        print(f"Line {i+3}: {repr(lines[i+2])}")
        break

print("\nFile has", len(lines), "lines")
