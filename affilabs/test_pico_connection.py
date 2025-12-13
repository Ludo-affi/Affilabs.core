"""Test Pico P4SPR connection directly."""
import sys
import logging
sys.path.insert(0, r'c:\Users\ludol\ezControl-AI\Affilabs.core beta')

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s :: %(message)s')

from affilabs.utils.controller import PicoP4SPR

print("=" * 70)
print("TESTING Pico P4SPR CONNECTION")
print("=" * 70)

print("\nCreating PicoP4SPR instance...")
pico = PicoP4SPR()

print("Attempting to connect...")
result = pico.open()

print(f"\nConnection result: {result}")

if result:
    print("\n[OK] SUCCESS - Pico P4SPR connected!")
    print(f"Version: {pico.version}")
    print(f"Serial port: {pico._ser}")
else:
    print("\n[ERROR] FAILED - Could not connect to Pico P4SPR")
    print("\nPossible reasons:")
    print("  1. Pico not responding to 'id' command correctly")
    print("  2. Timeout too short")
    print("  3. Firmware not loaded or wrong firmware")
    print("  4. Serial communication issue")

print("\n" + "=" * 70)
