"""
Test optimized set_batch_intensities() - removed redundant lm:ABCD
Should use only 4 serial writes (la:X, lb:X, lc:X, ld:X)
"""
import time
from affilabs.utils.controller import PicoP4PRO

print("=" * 60)
print("OPTIMIZED BATCH LED TEST (4 commands instead of 5)")
print("=" * 60)

# Initialize controller
ctrl = PicoP4PRO()
if not ctrl.open():
    print("ERROR: Cannot open P4PRO controller")
    exit(1)

print("Connected to P4PRO")
print()

# Test 1: Set all LEDs to 51 (20%)
print("TEST 1: Set all 4 LEDs to 51 (20% intensity)")
print("-" * 60)
result = ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)
print(f"Command result: {result}")
print()
print("PLEASE CHECK DETECTOR:")
print("  - Are all 4 LEDs on?")
print("  - What is the detector reading?")
input("Press Enter when ready to continue...")
print()

# Test 2: Turn off LEDs
print("TEST 2: Turn off all LEDs")
print("-" * 60)
ctrl.turn_off_channels()
time.sleep(0.5)
print("LEDs should be OFF")
input("Press Enter when ready to continue...")
print()

# Test 3: Different intensities
print("TEST 3: Different intensities (A=200, B=150, C=100, D=50)")
print("-" * 60)
result = ctrl.set_batch_intensities(a=200, b=150, c=100, d=50)
print(f"Command result: {result}")
print()
print("PLEASE CHECK DETECTOR:")
print("  - Are all 4 LEDs on?")
print("  - What is the detector reading?")
print("  - LEDs should have DIFFERENT brightnesses (A brightest, D dimmest)")
input("Press Enter when ready to continue...")
print()

# Test 4: Turn off LEDs
print("TEST 4: Turn off all LEDs")
print("-" * 60)
ctrl.turn_off_channels()
time.sleep(0.5)
print("LEDs should be OFF")
print()

# Close
ctrl.close()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print()
print("VERIFICATION:")
print("✓ LEDs turned on correctly?")
print("✓ All 4 LEDs visible on detector?")
print("✓ No lm:ABCD command in logs (only la:, lb:, lc:, ld:)?")
