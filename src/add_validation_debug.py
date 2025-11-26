#!/usr/bin/env python3
"""Add debug prints for validation failures"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all ch_error_list.append lines and add prints before them
changes = []
for i, line in enumerate(lines):
    if 'ch_error_list.append(ch)' in line:
        # Get context to understand which check failed
        context = ''.join(lines[max(0, i-5):i])
        if 'saturation' in context.lower():
            reason = "SATURATED"
        elif 'no water' in context.lower() or 'dip' in context.lower():
            reason = "NO_SPR_DIP"
        elif 'fwhm' in context.lower():
            reason = "FWHM_FAIL"
        elif 'invert' in context.lower() or 'orientation' in context.lower():
            reason = "ORIENTATION"
        else:
            reason = "UNKNOWN"

        indent = ' ' * (len(line) - len(line.lstrip()))
        print_line = f'{indent}print(f"❌ Ch {{ch.upper()}} FAILED: {reason}")\n'
        changes.append((i, print_line))

# Insert in reverse order to preserve line numbers
for i, print_line in reversed(changes):
    lines.insert(i, print_line)

with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"✅ Added {len(changes)} debug prints for validation failures!")
