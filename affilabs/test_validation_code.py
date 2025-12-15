#!/usr/bin/env python3
"""Verify validation code is up to date"""

# Read the file directly
with open("utils/led_calibration.py", encoding="utf-8") as f:
    content = f.read()

# Check for our new debug markers
markers = [
    "READ_INTENSITY_FAILED",
    "FLAT_SPECTRUM",
    "ORIENTATION_INVERTED",
    "SATURATED_AFTER_REDUCTION",
]

print("Checking for validation debug markers:")
for marker in markers:
    if marker in content:
        print(f"  [OK] {marker} found")
    else:
        print(f"  [ERROR] {marker} NOT FOUND")

# Check for old UNKNOWN prints
if "FAILED: UNKNOWN" in content:
    print("\n[WARN]  WARNING: Old 'UNKNOWN' debug prints still present!")
    # Count them
    count = content.count("FAILED: UNKNOWN")
    print(f"     Found {count} instances")
else:
    print("\n[OK] No old 'UNKNOWN' prints found")

print("\n" + "=" * 60)
print("File verification complete")
