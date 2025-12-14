"""Simple test for mode switch LED activation.

Tests ONLY the mode switch behavior without overwhelming the serial port.
"""

import time
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.logger import logger

def main():
    print("="*80)
    print("MODE SWITCH LED ACTIVATION TEST")
    print("="*80)
    print("\nThis test checks if switching servo mode activates LEDs.")
    print("This is what happens at the start of calibration Step 3.\n")

    # Initialize controller
    print("Initializing PicoP4SPR controller...")
    ctrl = PicoP4SPR()

    if not ctrl.open():
        print("❌ Failed to open controller")
        return 1

    print(f"✅ Controller connected: {ctrl.name}")
    print(f"   Firmware version: {getattr(ctrl, 'version', 'Unknown')}")

    try:
        # Test 1: Turn off LEDs
        print("\n" + "="*80)
        print("TEST 1: INITIAL STATE")
        print("="*80)
        print("\n1. Turning off all LEDs...")
        ctrl.turn_off_channels()
        time.sleep(1.0)

        print("\n   👀 OBSERVE: Are all LEDs OFF?")
        input("   Press ENTER when you've confirmed all LEDs are OFF...\n")

        # Test 2: Switch to S-mode
        print("\n" + "="*80)
        print("TEST 2: SWITCH TO S-MODE")
        print("="*80)
        print("\n2. Switching servo to S-mode...")
        print("   This is what calibration Step 3 does before LED ranking.")
        print("   Command being sent: 'ss\\n'")

        if hasattr(ctrl, 'set_mode'):
            ctrl.set_mode('s')
            time.sleep(1.5)  # Give servo time to move
            print("   ✅ Mode switch command sent")
        else:
            print("   ❌ Controller doesn't support set_mode()")
            return 1

        print("\n   👀 CRITICAL OBSERVATION:")
        print("   Did ANY LEDs turn ON after the mode switch?")
        print("   Look at all 4 LED channels (A, B, C, D)")
        time.sleep(1.0)

        result_s = input("\n   Did LEDs turn ON? (y/n): ").lower().strip()

        # Test 3: Turn off again and switch to P-mode
        print("\n" + "="*80)
        print("TEST 3: SWITCH TO P-MODE")
        print("="*80)
        print("\n3. Turning off LEDs again...")
        ctrl.turn_off_channels()
        time.sleep(1.0)

        print("   👀 OBSERVE: LEDs should be OFF again")
        input("   Press ENTER when confirmed...\n")

        print("\n4. Switching servo to P-mode...")
        print("   Command being sent: 'sp\\n'")
        ctrl.set_mode('p')
        time.sleep(1.5)

        print("\n   👀 CRITICAL OBSERVATION:")
        print("   Did ANY LEDs turn ON after switching to P-mode?")
        time.sleep(1.0)

        result_p = input("\n   Did LEDs turn ON? (y/n): ").lower().strip()

        # Test 4: State restoration test
        print("\n" + "="*80)
        print("TEST 4: STATE RESTORATION")
        print("="*80)
        print("\n5. Setting all LEDs to medium brightness (150)...")

        if hasattr(ctrl, 'set_batch_intensities'):
            ctrl.set_batch_intensities(a=150, b=150, c=150, d=150)
        else:
            for ch in ['a', 'b', 'c', 'd']:
                ctrl.set_intensity(ch, 150)
                time.sleep(0.1)

        time.sleep(1.0)
        print("   👀 OBSERVE: All 4 LEDs should be ON at medium brightness")
        input("   Press ENTER when confirmed...\n")

        print("\n6. Turning OFF all LEDs...")
        ctrl.turn_off_channels()
        time.sleep(1.0)
        print("   👀 OBSERVE: All LEDs should be OFF")
        input("   Press ENTER when confirmed...\n")

        print("\n7. Switching mode (does firmware restore previous LED state?)...")
        print("   If firmware has a bug, LEDs will turn back on at 150")
        ctrl.set_mode('s')
        time.sleep(1.5)

        print("\n   👀 CRITICAL OBSERVATION:")
        print("   Did LEDs turn back ON at medium brightness (150)?")
        time.sleep(1.0)

        result_restore = input("\n   Did LEDs restore to previous state? (y/n): ").lower().strip()

        # Results
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)
        print(f"\n1. S-mode switch activated LEDs: {result_s.upper()}")
        print(f"2. P-mode switch activated LEDs: {result_p.upper()}")
        print(f"3. Mode switch restored LED state: {result_restore.upper()}")

        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)

        if result_s == 'y' or result_p == 'y':
            print("\n🔴 BUG CONFIRMED: Mode switch command enables LEDs")
            print("   The servo movement command (ss/sp) is activating LEDs as a side effect.")
            print("   This is a FIRMWARE BUG that needs to be fixed.")
            print("\n   Impact: LEDs turn on at start of Step 3 before LED ranking begins.")
            print("   This is what you're observing during calibration.")
        elif result_restore == 'y':
            print("\n🔴 BUG CONFIRMED: Firmware restores previous LED state")
            print("   Mode switch triggers the firmware to restore LEDs to previous intensity.")
            print("   This is a FIRMWARE STATE MACHINE BUG.")
            print("\n   Impact: LEDs turn on at start of Step 3 if they were on previously.")
        else:
            print("\n✅ NO BUG DETECTED: Mode switch does not activate LEDs")
            print("   The servo movement (ss/sp) does NOT cause LED activation.")
            print("\n   Conclusion: LEDs turning on during calibration is likely from:")
            print("   - Step 3 LED ranking (EXPECTED behavior around 10-15 seconds)")
            print("   - User observing Step 3 where LEDs intentionally flash")

        print("="*80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up
        print("\nFinal cleanup: Turning off all LEDs...")
        try:
            ctrl.turn_off_channels()
            time.sleep(0.5)
        except:
            pass
        ctrl.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
