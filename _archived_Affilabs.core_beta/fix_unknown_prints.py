#!/usr/bin/env python3
"""Replace UNKNOWN debug prints with specific error codes"""

with open('utils/led_calibration.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all three UNKNOWN prints with specific error codes
replacements = [
    ('print(f"❌ Ch {ch.upper()} FAILED: UNKNOWN")',
     'logger.error(f"❌ Ch {ch.upper()} FAILED: VALIDATION_ERROR")'),
]

count = 0
for old, new in replacements:
    old_count = content.count(old)
    content = content.replace(old, new)
    count += old_count

with open('utils/led_calibration.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Replaced {count} UNKNOWN prints with proper error codes")
