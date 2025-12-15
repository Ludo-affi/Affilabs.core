"""LED Hardware Diagnostic - Check communication and power"""

import sys
import time

sys.path.insert(0, "src")

from utils.controller import PicoP4SPR

print("=" * 70)
print("LED HARDWARE DIAGNOSTIC")
print("=" * 70)

# Connect
print("\n1. Connecting to Pico...")
ctrl = PicoP4SPR()
if not ctrl.open():
    print("❌ ERROR: Cannot connect to Pico controller!")
    print("   - Check USB cable")
    print("   - Check COM port in Device Manager")
    sys.exit(1)
print("✅ Pico connected")

# Test firmware version
print("\n2. Checking firmware version...")
if hasattr(ctrl, "version") and ctrl.version:
    print(f"✅ Firmware: {ctrl.version}")
else:
    print("⚠️ Could not read firmware version")

# Test LED commands with responses
print("\n3. Testing LED command responses...")
print("   Sending: batch:255,0,0,0 (LED A ON)")

try:
    # Send raw command and check for response
    if ctrl._ser:
        ctrl._ser.write(b"batch:255,0,0,0\n")
        time.sleep(0.1)

        # Check if there's any response
        if ctrl._ser.in_waiting > 0:
            response = ctrl._ser.read(ctrl._ser.in_waiting)
            print(f"✅ Pico responded: {response}")
        else:
            print("⚠️ No response from Pico (this is normal for batch commands)")

        time.sleep(2)
        ctrl._ser.write(b"batch:0,0,0,0\n")
        time.sleep(0.1)
    else:
        print("❌ Serial port not open")
except Exception as e:
    print(f"❌ Error sending command: {e}")

# Check if commands are being received
print("\n4. Testing individual LED command (legacy method)...")
print("   Trying legacy 'la' command for LED A...")
try:
    if ctrl._ser:
        # Try legacy individual LED command
        ctrl._ser.write(b"la\n")
        time.sleep(0.1)

        if ctrl._ser.in_waiting > 0:
            response = ctrl._ser.read(ctrl._ser.in_waiting)
            print(f"✅ Response: {response}")

        # Set intensity using legacy command
        ctrl._ser.write(b"ia:255\n")
        time.sleep(0.1)

        if ctrl._ser.in_waiting > 0:
            response = ctrl._ser.read(ctrl._ser.in_waiting)
            print(f"✅ Intensity set response: {response}")

        print("   >>> LED A should be ON for 3 seconds <<<")
        time.sleep(3)

        # Turn off
        ctrl._ser.write(b"ia:0\n")
        time.sleep(0.1)
except Exception as e:
    print(f"❌ Legacy command error: {e}")

print("\n" + "=" * 70)
print("DIAGNOSTIC RESULTS")
print("=" * 70)
print("\n❓ Did you see ANY LEDs light up during this test?")
print("\n   YES → Software working, check:")
print("         • LED intensity settings too low")
print("         • Room too bright to see LEDs")
print("         • Looking at wrong part of hardware")
print("\n   NO → Hardware problem, check:")
print("         • LED PCB power supply (separate 12V/5V input?)")
print("         • LED PCB connected to Pico GPIO pins")
print("         • LED PCB model matches firmware (P4SPR = 4 channels)")
print("         • Damaged/burned out LEDs")
print("         • Wrong firmware loaded on Pico")
print("\n💡 Next steps:")
print("   1. Check LED PCB has external power connected")
print("   2. Check physical connections between Pico and LED PCB")
print("   3. Verify LED PCB model number")
print("   4. Test LEDs with multimeter if available")
print("=" * 70)
