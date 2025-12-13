"""Test controller connection directly."""
import sys
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')

from affilabs.utils.controller import PicoP4SPR, ArduinoController
from affilabs.utils.logger import logger

print("="*60)
print("TESTING CONTROLLER CONNECTION")
print("="*60)

# Try Pico
print("\n1. Testing PicoP4SPR...")
pico = PicoP4SPR()
if pico.open():
    print(f"[OK] PicoP4SPR CONNECTED! Version: {pico.version}")
else:
    print("[ERROR] PicoP4SPR NOT FOUND")

# Try Arduino
print("\n2. Testing Arduino...")
arduino = ArduinoController()
if arduino.open():
    print("[OK] Arduino CONNECTED!")
else:
    print("[ERROR] Arduino NOT FOUND")

print("\n" + "="*60)
