"""
Visual LED test - Keep LEDs on for 2 seconds each to verify hardware.
"""
import time
import sys
sys.path.insert(0, 'src')

from utils.controller import PicoP4SPR
import serial.tools.list_ports

# Find Pico controller
print("Searching for Pico controller...")
ports = list(serial.tools.list_ports.comports())
pico_port = None
for port in ports:
    if 'USB Serial Device' in port.description or 'Pico' in port.description:
        pico_port = port.device
        print(f"Found Pico on {pico_port}")
        break

if not pico_port:
    print("ERROR: No Pico controller found!")
    sys.exit(1)

# Connect to controller
print(f"Connecting...")
ctrl = PicoP4SPR()
if not ctrl.open():
    print("ERROR: Failed to connect to Pico controller!")
    sys.exit(1)

print(f"✅ Connected to Pico controller")

print("\n" + "="*60)
print("LED VISUAL TEST - Watch your hardware!")
print("="*60)

# Test each channel individually
channels = [('a', 255), ('b', 255), ('c', 255), ('d', 255)]

for ch, intensity in channels:
    print(f"\n🔆 Turning ON LED {ch.upper()} at intensity {intensity}")
    print(f"   >>> LED {ch.upper()} should be LIT for 2 seconds <<<")

    # Turn on this LED only
    led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    led_values[ch] = intensity

    ctrl.set_batch_intensities(**led_values)

    # Wait 2 seconds so you can see it
    time.sleep(2.0)

    # Turn off
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    print(f"   LED {ch.upper()} turned OFF")
    time.sleep(0.5)

print("\n" + "="*60)
print("Test ALL LEDs ON simultaneously for 3 seconds")
print("="*60)
print("🔆 Turning ON all LEDs at full brightness")
ctrl.set_batch_intensities(a=255, b=255, c=255, d=255)
time.sleep(3.0)
ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
print("All LEDs OFF")

print("\n✅ Visual test complete!")
print("Did you see the LEDs light up?")
print("If NO LEDs lit up:")
print("  1. Check LED power supply")
print("  2. Check LED PCB connections")
print("  3. Verify correct COM port")
print("If SOME LEDs lit up but not all:")
print("  1. Check individual LED connections")
print("  2. Check LED health (burned out?)")
