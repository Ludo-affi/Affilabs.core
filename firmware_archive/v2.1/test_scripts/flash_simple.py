"""
Simple firmware flasher - just copy to BOOTSEL drive
"""
import sys
import shutil
import os
import time

def wait_for_bootsel():
    """Wait for RPI-RP2 drive to appear"""
    print("\n⏳ Waiting for BOOTSEL drive (RPI-RP2)...")
    print("   Please:")
    print("   1. Unplug USB")
    print("   2. Hold BOOTSEL button")
    print("   3. Plug USB back in")
    print("   4. Release BOOTSEL\n")

    for i in range(60):
        for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
            path = f"{drive}:\\"
            try:
                if os.path.exists(path):
                    with open(os.path.join(path, "INFO_UF2.TXT"), 'r') as f:
                        if "RPI-RP2" in f.read():
                            return path
            except:
                pass
        time.sleep(1)
        print(f"   Still waiting... ({i+1}/60)", end='\r')

    return None

def flash_simple(firmware_path):
    """Flash firmware to Pico"""
    print("="*60)
    print("Simple Firmware Flasher")
    print("="*60)

    if not os.path.exists(firmware_path):
        print(f"\n❌ Firmware file not found: {firmware_path}")
        return False

    print(f"\n📁 Firmware: {firmware_path}")
    print(f"   Size: {os.path.getsize(firmware_path)} bytes")

    bootsel_drive = wait_for_bootsel()

    if not bootsel_drive:
        print("\n❌ BOOTSEL drive not found after 60 seconds")
        return False

    print(f"\n✓ Found BOOTSEL drive: {bootsel_drive}")

    dest = os.path.join(bootsel_drive, os.path.basename(firmware_path))
    print(f"\n📋 Copying firmware...")
    print(f"   {firmware_path}")
    print(f"   → {dest}")

    try:
        shutil.copy2(firmware_path, dest)
        print("\n✅ Firmware copied! Device will reboot automatically.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"\n❌ Copy failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python flash_simple.py <firmware.uf2>")
        sys.exit(1)

    success = flash_simple(sys.argv[1])
    sys.exit(0 if success else 1)
