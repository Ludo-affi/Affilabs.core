#!/usr/bin/env python3
"""Test the sequential LED batch control on P4PRO controller."""

import sys
import time
from affilabs.utils.controller import PicoP4PRO

def main():
    print("=" * 60)
    print("P4PRO Sequential LED Batch Test")
    print("=" * 60)
    
    # Initialize controller
    ctrl = PicoP4PRO()
    
    if not ctrl.open():
        print("❌ Failed to open P4PRO controller")
        return 1
    
    print(f"✓ Connected to P4PRO")
    print()
    
    # TEST 1: All LEDs at same intensity (51 = 20%)
    print("TEST 1: All LEDs at intensity 51 (20%)")
    print("-" * 40)
    result = ctrl.set_batch_intensities(51, 51, 51, 51)
    print(f"Command result: {'✓ SUCCESS' if result else '❌ FAILED'}")
    print("All 4 LEDs should be ON at ~20% brightness")
    input("Press Enter to continue...")
    print()
    
    # TEST 2: Turn off
    print("TEST 2: Turn off all LEDs")
    print("-" * 40)
    result = ctrl.turn_off_channels()
    print(f"Command result: {'✓ SUCCESS' if result else '❌ FAILED'}")
    print("All LEDs should be OFF")
    input("Press Enter to continue...")
    print()
    
    # TEST 3: Different intensities (the critical test!)
    print("TEST 3: Different intensities per LED")
    print("-" * 40)
    print("A=200 (78%), B=150 (59%), C=100 (39%), D=50 (20%)")
    result = ctrl.set_batch_intensities(200, 150, 100, 50)
    print(f"Command result: {'✓ SUCCESS' if result else '❌ FAILED'}")
    print("All 4 LEDs should be ON at DIFFERENT brightness levels:")
    print("  LED A: Brightest (78%)")
    print("  LED B: Bright (59%)")
    print("  LED C: Medium (39%)")
    print("  LED D: Dimmest (20%)")
    print()
    print("⚠️  CRITICAL: All LEDs should have VISIBLY DIFFERENT brightness!")
    input("Press Enter to continue...")
    print()
    
    # TEST 4: Turn off
    print("TEST 4: Turn off all LEDs")
    print("-" * 40)
    result = ctrl.turn_off_channels()
    print(f"Command result: {'✓ SUCCESS' if result else '❌ FAILED'}")
    print("All LEDs should be OFF")
    print()
    
    # TEST 5: Only some LEDs (verify atomicity)
    print("TEST 5: Only LED A and C (atomicity test)")
    print("-" * 40)
    print("A=255 (100%), B=0 (OFF), C=128 (50%), D=0 (OFF)")
    result = ctrl.set_batch_intensities(255, 0, 128, 0)
    print(f"Command result: {'✓ SUCCESS' if result else '❌ FAILED'}")
    print("Only LED A and C should be ON")
    print("  LED A: Maximum brightness (100%)")
    print("  LED C: Medium brightness (50%)")
    input("Press Enter to continue...")
    print()
    
    # Final cleanup
    print("Cleanup: Turning off all LEDs")
    ctrl.turn_off_channels()
    
    ctrl.close()
    print()
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("VERIFICATION CHECKLIST:")
    print("✓ TEST 1: All 4 LEDs on at same brightness? (Yes/No)")
    print("✓ TEST 3: All 4 LEDs on at DIFFERENT brightness? (Yes/No)")
    print("✓ TEST 5: Only A and C on, with different brightness? (Yes/No)")
    print()
    print("If TEST 3 shows DIFFERENT brightness levels, the atomic")
    print("leds: command is working correctly! 🎉")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
