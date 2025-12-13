#!/usr/bin/env python
"""Add debug print statements to perform_alternative_calibration()"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert print statements after line 2847 (index 2847 in 0-indexed array)
insert_after_2847 = '''
    print("\\n" + "="*80)
    print("🔥🔥🔥 perform_alternative_calibration() ENTERED")
    print("="*80 + "\\n")

'''

# Insert after "try:" line (around line 2849, now will be 2852 after first insert)
insert_after_try = '''        print("🔥 Entering try block...")
'''

# Insert the first block after result = LEDCalibrationResult()
lines.insert(2848, insert_after_2847)

# Insert the second block after try: line (account for previous insertion)
lines.insert(2853, insert_after_try)

# Write back
with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("[OK] Debug prints added successfully!")
print(f"   Total lines now: {len(lines)}")
