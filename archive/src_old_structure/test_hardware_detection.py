"""Quick hardware detection test."""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("HARDWARE DETECTION TEST")
print("=" * 60)

# Test 1: Check for serial ports
print("\n1. SERIAL PORTS (Controllers):")
try:
    import serial.tools.list_ports

    ports = list(serial.tools.list_ports.comports())
    if ports:
        for port in ports:
            print(f"   - {port.device}: {port.description}")
    else:
        print("   NO serial ports found")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 2: Check for Ocean Optics devices (USB4000 via SeaBreeze)
print("\n2. OCEAN OPTICS SPECTROMETERS:")
try:
    from utils.usb4000_wrapper import USB4000

    usb = USB4000()
    ok = usb.open()
    if ok:
        print("   Connected: YES")
        print(f"   Serial: {getattr(usb, 'serial_number', 'Unknown')}")
    else:
        print("   Connected: NO")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 3: Try connecting to controller (PicoP4SPR → PicoEZSPR → Arduino)
print("\n3. SPR CONTROLLERS:")
try:
    from utils.controller import ArduinoController, PicoEZSPR, PicoP4SPR

    ctrl = None
    for cls in (PicoP4SPR, PicoEZSPR, ArduinoController):
        try:
            c = cls()
            if c.open():
                ctrl = c
                break
        except Exception:
            pass
    if ctrl:
        name = getattr(ctrl, "name", ctrl.__class__.__name__)
        port = getattr(getattr(ctrl, "_ser", None), "port", "Unknown")
        print(f"   Found: {name}")
        print(f"   Port: {port}")
    else:
        print("   NO controller found")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
