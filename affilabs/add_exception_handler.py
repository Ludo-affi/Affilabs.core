#!/usr/bin/env python3
"""Add print to except block"""

with open("utils/led_calibration.py", encoding="utf-8") as f:
    lines = f.readlines()

# Find the except block (line 3232)
target = 3231  # 0-indexed
print(f"Line 3232: {lines[target]!r}")

# Insert print statements after "except Exception as e:"
insert_lines = [
    '        print("\\n" + "="*80)\n',
    '        print("[ERROR][ERROR][ERROR] EXCEPTION IN perform_alternative_calibration()")\n',
    '        print("="*80)\n',
    '        print(f"Exception: {e}")\n',
    "        import traceback\n",
    "        traceback.print_exc()\n",
    '        print("="*80 + "\\n")\n',
]

lines[target + 1 : target + 1] = insert_lines

# Write back
with open("utils/led_calibration.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("[OK] Exception handler updated!")
