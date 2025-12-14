"""Create a fixed firmware version with detailed debug output
This directly patches the pico-p4spr-firmware source"""

import re
from pathlib import Path

FIRMWARE_PATH = Path(r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\affinite_p4spr.c")

print("="*70)
print("DIRECT FIRMWARE PATCH - Adding Debug Output")
print("="*70)

if not FIRMWARE_PATH.exists():
    print(f"\n❌ Firmware not found at {FIRMWARE_PATH}")
    exit(1)

# Read current firmware
with open(FIRMWARE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"\n✅ Read firmware ({len(content)} chars)")

# Find the atoi conversions section
pattern = r'(\s+uint16_t num_cycles = atoi\(str_cycles\);)'

if re.search(pattern, content):
    print("\n📝 Found parsing section, adding debug output...")

    # Add debug AFTER the atoi calls
    replacement = r'''\1

                    // DEBUG: Print parsed values before clamping
                    if (debug){
                        printf("DEBUG: str_a='%s' str_b='%s' str_c='%s' str_d='%s'\\n",
                               str_int_a, str_int_b, str_int_c, str_int_d);
                        printf("DEBUG: str_settle='%s' str_dark='%s' str_cycles='%s'\\n",
                               str_settling, str_dark, str_cycles);
                        printf("PARSED: A=%d B=%d C=%d D=%d settle=%d dark=%d cycles=%d\\n",
                               int_a, int_b, int_c, int_d, settling_ms, dark_ms, num_cycles);
                    }'''

    content = re.sub(pattern, replacement, content)

    # Write modified firmware
    with open(FIRMWARE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Added debug output")
    print(f"✅ Saved to {FIRMWARE_PATH}")
    print("\n" + "="*70)
    print("Next steps:")
    print("  1. cd C:\\Users\\lucia\\OneDrive\\Desktop\\ezControl 2.0\\Affilabs.core\\pico-p4spr-firmware\\build")
    print("  2. make -j4")
    print("  3. Convert BIN to UF2")
    print("  4. Flash to device")
else:
    print("\n❌ Could not find parsing section in firmware")
    print("    The firmware may not have rankbatch command")
