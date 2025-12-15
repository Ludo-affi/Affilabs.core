"""Test controller connection directly."""

import sys

sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Affilabs.core beta")

from utils.controller import ArduinoController, PicoP4SPR

print("=" * 60)
print("TESTING CONTROLLER CONNECTION")
print("=" * 60)

# Try Pico
print("\n1. Testing PicoP4SPR...")
pico = PicoP4SPR()
if pico.open():
    print(f"✅ PicoP4SPR CONNECTED! Version: {pico.version}")
else:
    print("❌ PicoP4SPR NOT FOUND")

# Try Arduino
print("\n2. Testing Arduino...")
arduino = ArduinoController()
if arduino.open():
    print("✅ Arduino CONNECTED!")
else:
    print("❌ Arduino NOT FOUND")

print("\n" + "=" * 60)
