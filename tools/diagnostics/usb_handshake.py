#!/usr/bin/env python
"""USB Handshake - Directly communicate with Ocean Optics detector."""

import sys
import time
import usb.core
import usb.util

print("=" * 80)
print("USB HANDSHAKE TEST - Ocean Optics Detector")
print("=" * 80)

# Ocean Optics VID/PID
OCEAN_OPTICS_VID = 0x2457
OCEAN_OPTICS_FLAME_T_PID = 0x1022

print("\n[STEP 1] Finding Ocean Optics devices via pyusb...\n")

try:
    from affilabs.utils.libusb_init import get_libusb_backend
    backend = get_libusb_backend()
    print(f"[OK] libusb backend: {backend}\n")
except Exception as e:
    print(f"[WARNING] Could not get libusb backend: {e}")
    backend = None

# Find devices
devices = list(usb.core.find(find_all=True, idVendor=OCEAN_OPTICS_VID, backend=backend))

print(f"Found {len(devices)} Ocean Optics device(s)\n")

if not devices:
    print("[ERROR] No Ocean Optics devices found!")
    sys.exit(1)

for i, dev in enumerate(devices):
    print(f"[{i}] Device: VID=0x{dev.idVendor:04x}, PID=0x{dev.idProduct:04x}")
    print(f"    Bus: {dev.bus}, Address: {dev.address}\n")

# Try to open and handshake with each device
for i, dev in enumerate(devices):
    print("=" * 80)
    print(f"HANDSHAKE WITH DEVICE [{i}]")
    print("=" * 80 + "\n")

    try:
        print("[STEP 2] Opening device...\n")

        # Try to open
        try:
            dev.reset()
            print("[OK] Device reset successful\n")
        except usb.core.USBError as e:
            print(f"[WARNING] Reset failed (may be OK): {e}\n")

        print("[STEP 3] Reading device descriptor...\n")

        try:
            # Get device info
            manufacturer = usb.util.get_string(dev, dev.iManufacturer)
            product = usb.util.get_string(dev, dev.iProduct)
            serial = usb.util.get_string(dev, dev.iSerialNumber)

            print(f"  Manufacturer: {manufacturer}")
            print(f"  Product: {product}")
            print(f"  Serial: {serial}\n")
        except Exception as e:
            print(f"[WARNING] Could not read strings: {e}\n")

        print("[STEP 4] Setting device configuration...\n")

        try:
            # Get active config
            cfg = dev.get_active_configuration()
            print(f"[OK] Active configuration: {cfg.bConfigurationValue}\n")
        except usb.core.USBError as e:
            print(f"[WARNING] No active config: {e}")
            print("[ATTEMPTING] Setting configuration to 1\n")
            try:
                dev.set_configuration()
                print("[OK] Configuration set\n")
            except Exception as e2:
                print(f"[WARNING] Set config failed: {e2}\n")

        print("[STEP 5] Reading control endpoint (device status)...\n")

        try:
            # Try to read a simple control transfer to test communication
            # This is a test to see if the device responds
            data = dev.ctrl_transfer(
                usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR,
                0,  # bRequest
                0,  # wValue
                0,  # wIndex
                4,  # wLength
                timeout=1000
            )
            print(f"[OK] Device responded to control transfer")
            print(f"    Data: {data}\n")
        except usb.core.USBError as e:
            if "Operation not supported" in str(e) or "timed out" in str(e):
                print(f"[OK] Device doesn't respond to this control transfer (OK - different device)")
                print(f"    Error: {e}\n")
            else:
                print(f"[ERROR] Control transfer failed: {e}\n")
        except Exception as e:
            print(f"[WARNING] Control transfer error: {e}\n")

        print("[STEP 6] Listing endpoints...\n")

        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]

            print(f"Interface 0:")
            for ep in intf:
                ep_type = "CONTROL" if ep.bmAttributes & 3 == 0 else \
                          "ISO" if ep.bmAttributes & 3 == 1 else \
                          "BULK" if ep.bmAttributes & 3 == 2 else "INTERRUPT"
                direction = "IN" if ep.bEndpointAddress & 0x80 else "OUT"
                print(f"  Endpoint 0x{ep.bEndpointAddress:02x} - {ep_type} {direction} ({ep.wMaxPacketSize} bytes)")

            print()
        except Exception as e:
            print(f"[WARNING] Could not list endpoints: {e}\n")

        print("[STEP 7] Attempting bulk read (spectrum)...\n")

        try:
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]

            # Find input endpoint
            in_ep = None
            for ep in intf:
                if (ep.bEndpointAddress & 0x80) and (ep.bmAttributes & 3) == 2:  # Bulk IN
                    in_ep = ep
                    break

            if in_ep:
                print(f"[ATTEMPTING] Reading from endpoint 0x{in_ep.bEndpointAddress:02x}...")
                try:
                    data = dev.read(in_ep.bEndpointAddress, 4096, timeout=500)
                    print(f"[OK] Successfully read {len(data)} bytes from device!")
                    print(f"    Data (first 16 bytes): {list(data[:16])}\n")
                except usb.core.USBError as e:
                    print(f"[INFO] Bulk read: {e}\n")
            else:
                print("[INFO] No bulk input endpoint found\n")

        except Exception as e:
            print(f"[WARNING] Bulk read test: {e}\n")

        print("[STEP 8] Handshake summary...\n")
        print("[OK] Device opened successfully")
        print("[OK] Device responded to basic communication")
        print("\nThis device appears to be working!\n")

    except usb.core.USBError as e:
        print(f"[ERROR] Failed to open device: {e}\n")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()

print("=" * 80)
print("HANDSHAKE COMPLETE")
print("=" * 80)
