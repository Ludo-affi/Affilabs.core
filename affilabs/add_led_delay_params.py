#!/usr/bin/env python3
"""Add pre_led_delay_ms and post_led_delay_ms parameters to perform_alternative_calibration()"""

with open("utils/led_calibration.py", encoding="utf-8") as f:
    lines = f.readlines()

# Find line 2793 (afterglow_correction line)
target_line = 2793 - 1  # 0-indexed

print(f"Line 2793: {lines[target_line]!r}")
print(f"Line 2794: {lines[target_line+1]!r}")

# Replace line 2793 to add comma at end
lines[target_line] = lines[target_line].rstrip() + ",\n"

# Insert new parameters after line 2793
new_params = [
    "    pre_led_delay_ms: float = 45.0,  # PRE LED delay: settling time after LED on (default 45ms)\n",
    "    post_led_delay_ms: float = 5.0,  # POST LED delay: dark time after LED off (default 5ms)\n",
]

lines[target_line + 1 : target_line + 1] = new_params

# Write back
with open("utils/led_calibration.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("[OK] Parameters added successfully!")
print(f"   Total lines: {len(lines)}")
