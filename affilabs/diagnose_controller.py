"""Diagnostic script to identify connected controller hardware."""

import serial.tools.list_ports
import usb.core

print("=" * 70)
print("CONTROLLER HARDWARE DIAGNOSTIC")
print("=" * 70)

# Expected VID/PID values from settings
ARDUINO_VID = 0x2341
ARDUINO_PID = 0x8036
PICO_VID = 0x2E8A
PICO_PID = 0x000A
CP210X_VID = 0x10C4
CP210X_PID = 0xEA60

print("\n1. Checking COM Ports (Serial Devices):")
print("-" * 70)
ports = list(serial.tools.list_ports.comports())
if ports:
    for p in ports:
        print(f"\n  Port: {p.device}")
        print(f"  Description: {p.description}")
        print(f"  Hardware ID: {p.hwid}")
        if p.vid and p.pid:
            print(f"  VID:PID = {hex(p.vid)}:{hex(p.pid)}")

            # Check against known controllers
            if p.vid == ARDUINO_VID:
                if p.pid == ARDUINO_PID:
                    print("  [OK] MATCH: Arduino P4SPR Controller")
                else:
                    print(
                        f"  [WARN] Arduino VID but different PID (expected {hex(ARDUINO_PID)})",
                    )
            elif p.vid == PICO_VID:
                if p.pid == PICO_PID:
                    print("  [OK] MATCH: Raspberry Pi Pico Controller")
                else:
                    print(
                        f"  [WARN] Pico VID but different PID (expected {hex(PICO_PID)})",
                    )
            elif p.vid == CP210X_VID:
                if p.pid == CP210X_PID:
                    print("  [OK] MATCH: CP2102 USB-Serial (used by some controllers)")
                else:
                    print(
                        f"  [WARN] CP210X VID but different PID (expected {hex(CP210X_PID)})",
                    )
        else:
            print("  [WARN] No VID/PID available")
else:
    print("  [ERROR] No COM ports found")

print("\n\n2. Checking All USB Devices:")
print("-" * 70)
try:
    devs = list(usb.core.find(find_all=True))
    print(f"Found {len(devs)} USB device(s)\n")

    for d in devs:
        vid = d.idVendor
        pid = d.idProduct
        print(f"  VID:PID = {hex(vid)}:{hex(pid)}")

        # Try to get manufacturer/product strings
        try:
            if d.iManufacturer:
                mfg = usb.util.get_string(d, d.iManufacturer)
                print(f"    Manufacturer: {mfg}")
        except:
            pass

        try:
            if d.iProduct:
                prod = usb.util.get_string(d, d.iProduct)
                print(f"    Product: {prod}")
        except:
            pass

        # Check against known controllers
        if vid == ARDUINO_VID:
            print("    [WARN] Arduino VID detected!")
            if pid == ARDUINO_PID:
                print("    [OK] MATCH: Arduino P4SPR Controller")
            else:
                print(f"    [WARN] Different PID (expected {hex(ARDUINO_PID)})")
        elif vid == PICO_VID:
            print("    [WARN] Pico VID detected!")
            if pid == PICO_PID:
                print("    [OK] MATCH: Raspberry Pi Pico Controller")
            else:
                print(f"    [WARN] Different PID (expected {hex(PICO_PID)})")

        print()

except Exception as e:
    print(f"  [ERROR] Error scanning USB devices: {e}")

print("\n3. Expected Controller Types:")
print("-" * 70)
print(f"  Arduino P4SPR:  VID={hex(ARDUINO_VID)}, PID={hex(ARDUINO_PID)}")
print(f"  Pico P4SPR:     VID={hex(PICO_VID)}, PID={hex(PICO_PID)}")
print(f"  CP2102 Serial:  VID={hex(CP210X_VID)}, PID={hex(CP210X_PID)}")

print("\n" + "=" * 70)
print("RECOMMENDATIONS:")
print("=" * 70)

if not ports:
    print("  • No COM ports detected - controller may not be connected")
    print("  • Check USB cable connection")
    print("  • Try a different USB port")
    print("  • Check Device Manager for unrecognized devices")
else:
    found_controller = False
    for p in ports:
        if p.vid in [ARDUINO_VID, PICO_VID, CP210X_VID]:
            found_controller = True
            break

    if not found_controller:
        print("  • COM ports found but no recognized controller VID/PID")
        print("  • Your controller may have a different VID/PID")
        print("  • Check which COM port device is listed above")
        print("  • You may need to update settings.py with correct VID/PID")

print("\n" + "=" * 70)
