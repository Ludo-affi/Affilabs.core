"""Test the December 30th optimized LED control method."""

import time
import sys
import serial.tools.list_ports

# Initialize hardware
from affilabs.utils.controller import PicoP4SPR

print("Finding controller...")
ports = serial.tools.list_ports.comports()
pico_port = None
for port in ports:
    print(f"  Found: {port.device} - VID={hex(port.vid) if port.vid else 'None'}, PID={hex(port.pid) if port.pid else 'None'}")
    if port.vid in [0x2E8A, 0x10C4] and port.pid in [0x000A, 0xEA60]:  # Pico or CP210x
        pico_port = port.device
        print("  ✅ Using this port")
        break

if not pico_port:
    print("❌ No Pico controller found")
    sys.exit(1)

print(f"\nConnecting to {pico_port}...")
ctrl = PicoP4SPR()
ctrl.open()
print("✅ Connected")

# Test channels and intensities
channels = ['a', 'b', 'c', 'd']
led_intensities = {'a': 224, 'b': 87, 'c': 150, 'd': 200}

print("\n" + "="*60)
print("TESTING DECEMBER 30TH OPTIMIZED LED CONTROL")
print("="*60)

# ========================================================================
# OPTIMIZED LED CONTROL (Set Once + Turn On)
# ========================================================================
# Set all LED intensities ONCE at start via direct serial commands
# Then use turn_on_channel() to switch between LEDs
# ========================================================================

print("\nStep 1: Setting ALL LED intensities ONCE using direct serial commands")
current_intensities = {ch: led_intensities.get(ch, 128) for ch in channels}

for ch in channels:
    intensity = current_intensities[ch]
    cmd = f"b{ch}{int(intensity):03d}\n"
    print(f"  Sending: {cmd.strip()} (set LED {ch.upper()} intensity to {intensity})")
    ctrl._ctrl._ser.write(cmd.encode())
    time.sleep(0.005)  # 5ms between commands

print("\n✅ All LED intensities set!")

print("\nStep 2: Now switching between LEDs using turn_on_channel() only")
print("This should turn on ONE LED at a time with the pre-set intensity\n")

for i in range(2):  # Do 2 cycles
    print(f"\n--- Cycle {i+1} ---")
    for ch in channels:
        print(f"  Turning on LED {ch.upper()}...", end=" ", flush=True)
        ctrl.turn_on_channel(ch=ch)
        time.sleep(0.5)  # Wait 500ms to see it
        print("ON")

print("\n\nTurning off all LEDs...")
ctrl.turn_off_channels()

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
print("\nDid you observe:")
print("1. LEDs blinking sequentially (A→B→C→D)?")
print("2. Each LED at its pre-set brightness?")
print("3. Only ONE LED on at a time?")
