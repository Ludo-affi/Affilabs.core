#!/usr/bin/env python3
"""Add debug prints to perform_alternative_calibration()"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line "result = LEDCalibrationResult()" inside perform_alternative_calibration
# This should be around line 2847
target_line = -1
for i, line in enumerate(lines):
    if i > 2840 and i < 2860 and 'result = LEDCalibrationResult()' in line:
        target_line = i
        print(f"Found 'result = LEDCalibrationResult()' at line {i+1}")
        break

if target_line == -1:
    print("ERROR: Could not find target line")
    exit(1)

# Insert print statements AFTER the result = line
insert_lines = [
    '\n',
    '    print("\\n" + "="*80)\n',
    '    print("🔥🔥🔥 perform_alternative_calibration() ENTERED")\n',
    '    print("="*80 + "\\n")\n',
    '\n',
]

# Insert after target_line
lines[target_line+1:target_line+1] = insert_lines

# Now find the "try:" line after the inserts
try_line = -1
for i in range(target_line + len(insert_lines), min(target_line + len(insert_lines) + 10, len(lines))):
    if lines[i].strip() == 'try:':
        try_line = i
        print(f"Found 'try:' at line {i+1}")
        break

if try_line == -1:
    print("ERROR: Could not find 'try:' line")
    exit(1)

# Insert print after try:
lines[try_line+1:try_line+1] = ['        print("🔥 Entering try block...")\n']

# Write back
with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"[OK] Debug prints added successfully!")
print(f"   Total lines: {len(lines)}")
