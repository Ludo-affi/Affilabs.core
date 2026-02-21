#!/usr/bin/env python
"""Direct PyUSB test - bypasses seabreeze to test raw libusb access."""

import usb.core
import usb.util
import sys
import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

print("=" * 80)
print("DIRECT PyUSB DEVICE TEST (No SeaBreeze)")
print("=" * 80)

# Find all Ocean Optics devices
devices = list(usb.core.find(find_all=True, idVendor=0x2457))
print(f"\nFound {len(devices)} Ocean Optics device(s)")

if not devices:
    print("❌ NO DEVICES FOUND AT libusb LEVEL")
    sys.exit(1)

for idx, dev in enumerate(devices):
    print(f"\n--- Device [{idx}] ---")
    print(f"Bus: {dev.bus}, Address: {dev.address}")
    print(f"VID/PID: {hex(dev.idVendor)}/{hex(dev.idProduct)}")

    # Try to read descriptors without opening
    try:
        mfr = usb.util.get_string(dev, dev.iManufacturer)
        print(f"✓ Manufacturer (from descriptor): {mfr}")
    except Exception as e:
        print(f"✗ Can't read manufacturer: {e}")
        print(f"  → Device is PHANTOM/UNRESPONSIVE")
        continue

    # Try to get config without opening
    try:
        config = dev.get_active_configuration()
        print(f"✓ Active config: {config.bConfigurationValue}")
    except Exception as e:
        print(f"✗ Can't get active config: {e}")

    # Try to actually open the device
    try:
        logger.debug(f"Attempting to open Device [{idx}]...")
        dev.set_configuration()
        print(f"✓ Device opened successfully")

        # Try to access endpoint
        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]
            print(f"✓ Interface 0: {intf.bInterfaceNumber}")

            # List endpoints
            for ep in intf:
                print(f"  - Endpoint {hex(ep.bEndpointAddress)}: {ep.bmAttributes}")
        except Exception as e:
            print(f"  (Could not enumerate endpoints: {e})")

    except Exception as e:
        print(f"✗ CANNOT OPEN Device [{idx}]: {e}")
        print(f"  → This is the root cause of application failure")
        print(f"  → Driver binding issue or permission problem")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("\nIf you see '✗ CANNOT OPEN Device', the issue is:")
print("1. Driver not properly bound (use Zadig to reinstall)")
print("2. Permission issue (run as Administrator)")
print("3. Device in use by another application")
print("\nTo fix:")
print("  1. Download Zadig: https://zadig.akeo.ie/")
print("  2. Unplug detector")
print("  3. Run Zadig → Options → List All Devices")
print("  4. Plug in detector")
print("  5. Select FLAME-T, choose libusb driver")
print("  6. Click 'Replace Driver'")
print("=" * 80)
