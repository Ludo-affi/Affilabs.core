"""Flash the fixed V2.1 firmware to the device"""

import shutil
import time
from pathlib import Path

print("=" * 70)
print("FIRMWARE V2.1 FIXED - FLASH SCRIPT")
print("=" * 70)
print("\nThis firmware includes debug output for parsing verification.")
print("=" * 70)

firmware_file = Path("firmware_v2.1/affinite_p4spr_v2.1_FIXED.uf2")

if not firmware_file.exists():
    print(f"\n❌ ERROR: Firmware file not found at {firmware_file}")
    print("   Run build_v2_1_firmware.py first")
    exit(1)

print(f"\n✅ Found firmware: {firmware_file}")
print(f"   Size: {firmware_file.stat().st_size} bytes")

print("\n" + "=" * 70)
print("FLASHING INSTRUCTIONS")
print("=" * 70)
print("\n1. Unplug the Pico from USB")
print("2. Hold down the BOOTSEL button (white button on the board)")
print("3. While holding BOOTSEL, plug in the USB cable")
print("4. Release BOOTSEL - a drive named 'RPI-RP2' should appear")
print("5. Press ENTER to continue...")

input()

# Look for BOOTSEL drive
print("\n🔍 Looking for BOOTSEL drive...")
bootsel_drive = None

# Check common drive letters
for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
    drive = Path(f"{letter}:/")
    if drive.exists():
        # Check if it's the RPI-RP2 drive
        info_file = drive / "INFO_UF2.TXT"
        if info_file.exists():
            print(f"✅ Found BOOTSEL drive at {letter}:")
            bootsel_drive = drive
            break

if not bootsel_drive:
    print("\n⚠️  BOOTSEL drive not found automatically.")
    print("Please enter the drive letter (e.g., E): ", end="")
    letter = input().strip().upper()
    bootsel_drive = Path(f"{letter}:/")

    if not bootsel_drive.exists():
        print(f"\n❌ Drive {letter}: not found")
        exit(1)

print("\n📋 BOOTSEL drive info:")
info_file = bootsel_drive / "INFO_UF2.TXT"
if info_file.exists():
    with open(info_file) as f:
        for line in f:
            print(f"   {line.strip()}")

print(f"\n📤 Copying firmware to {bootsel_drive}...")
dest = bootsel_drive / firmware_file.name

try:
    shutil.copy(firmware_file, dest)
    print(f"✅ Copied to {dest}")
    print("\n⏳ Waiting for device to reboot...")
    time.sleep(3)

    print("\n✅ Firmware flash complete!")
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    print("\nThe device should now have:")
    print("  - V2.1 firmware with rankbatch command")
    print("  - Debug output for parameter parsing")
    print("\nTo test:")
    print("  1. Wait 5 seconds for device to fully boot")
    print("  2. Run: python test_single_after_power_cycle.py")
    print("  3. Enable debug mode: send 'd' command")
    print("  4. Check for 'Parsed: A=X B=X...' output")

except Exception as e:
    print(f"\n❌ Error copying firmware: {e}")
    print("\nManual steps:")
    print(f"  1. Copy {firmware_file}")
    print(f"  2. To {bootsel_drive}")
    exit(1)
