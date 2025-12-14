#!/usr/bin/env python3
"""Add debug prints for S-mode calibration"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the S-mode calibration loop (around line 2920)
for i, line in enumerate(lines):
    if 's_integration_times[ch], _ = calibrate_integration_per_channel(' in line:
        print(f"Found S-mode calibration at line {i+1}")
        # Add print before the call
        lines.insert(i, f'            print(f"🔧 Calibrating channel {{ch.upper()}} (S-mode)...")\n')
        break

# Find where S-mode LED intensities are stored (look for "result.ref_intensity[ch] = 255")
for i, line in enumerate(lines):
    if 'result.ref_intensity[ch] = 255' in line and i > 2900:
        print(f"Found S-mode intensity storage at line {i+1}")
        # Add print after
        lines.insert(i+1, f'            print(f"   ✅ Ch {{ch.upper()}}: LED=255, Integration={{s_integration_times[ch]}}ms")\n')
        break

# Write back
with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Debug prints added!")
