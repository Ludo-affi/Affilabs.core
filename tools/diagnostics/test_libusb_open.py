#!/usr/bin/env python
"""Test if libusb device can be opened and configured."""

import usb.core
import usb.util
import usb.backend.libusb1
import sys

backend = usb.backend.libusb1.get_backend()
dev = usb.core.find(idVendor=0x2457, backend=backend)

if not dev:
    print("No device found")
    sys.exit(1)

print("Device found!")
print(f"Address: {dev.address}, Bus: {dev.bus}")

try:
    # Test 1: Try to set configuration (which attempts to open the device)
    print("\n[TEST 1] Attempting set_configuration()...")
    dev.set_configuration()
    print("  ✓ set_configuration() successful")

    # Test 2: Try to read string descriptor
    print("\n[TEST 2] Attempting to read manufacturer string...")
    try:
        mfr = usb.util.get_string(dev, dev.iManufacturer)
        print(f"  ✓ Manufacturer: {mfr}")
    except Exception as e:
        print(f"  ✗ Still can't read string after set_configuration: {e}")

except Exception as e:
    print(f"  ✗ set_configuration() failed: {e}")
    print(f"     Error type: {type(e).__name__}")

    if "Operation not supported" in str(e):
        print("\n" + "=" * 70)
        print("DIAGNOSIS: This is a Windows driver issue")
        print("=" * 70)
        print("\nThe device is enumerated but Windows won't let libusb open it.")
        print("\nSOLUTION: Try libusb-win32 driver instead of libusbK:")
        print("1. Download Zadig: https://zadig.akeo.ie/")
        print("2. Options → List All Devices")
        print("3. Select 'Ocean Optics FLAME-T'")
        print("4. Change driver dropdown from 'libusbK' to 'libusb-win32'")
        print("5. Click 'Replace Driver'")
        print("6. Unplug and replug detector")
        print("7. Run this script again")
        print("=" * 70)

sys.exit(0)
