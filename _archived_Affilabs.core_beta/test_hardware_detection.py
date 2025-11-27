"""Quick hardware detection test."""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("="*60)
print("HARDWARE DETECTION TEST")
print("="*60)

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

# Test 2: Check for Ocean Optics devices
print("\n2. OCEAN OPTICS SPECTROMETERS:")
try:
    from utils.usb4000_wrapper import USB4000
    usb = USB4000()
    count = usb.get_device_count()
    print(f"   Found {count} device(s)")
    if count > 0:
        print(f"   Serial: {usb.serial_number if hasattr(usb, 'serial_number') else 'Unknown'}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 3: Try connecting to controller
print("\n3. SPR CONTROLLERS:")
try:
    from utils.controller import detect_and_connect_controller
    ctrl = detect_and_connect_controller()
    if ctrl:
        print(f"   Found: {ctrl.__class__.__name__}")
        print(f"   Port: {ctrl._port if hasattr(ctrl, '_port') else 'Unknown'}")
    else:
        print("   NO controller found")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
