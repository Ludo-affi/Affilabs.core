"""Simple test to verify LED commands work properly with firmware V1.2"""

import time
import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.logger import logger

def main():
    print("="*80)
    print("LED BRIGHTNESS TEST - Firmware V1.2 Command Verification")
    print("="*80)

    print("\nInitializing controller...")
    ctrl = PicoP4SPR()

    if not ctrl.open():
        print("❌ Failed to open controller")
        return 1

    print(f"✅ Controller connected: {ctrl.name}")
    print(f"   Firmware version: {getattr(ctrl, 'version', 'Unknown')}\n")

    try:
        # Test 1: Turn off all LEDs
        print("TEST 1: Turn off all LEDs")
        print("-" * 40)
        ctrl.turn_off_channels()
        time.sleep(0.5)
        print("   👀 ALL LEDs should be OFF")
        input("   Press ENTER to confirm...\n")

        # Test 2: Turn on Channel A at 20%
        print("TEST 2: Channel A at 20% (51/255)")
        print("-" * 40)
        print("   Sending: la (enable channel)")
        print("   Sending: ba051 (set intensity 51)")
        ctrl.set_intensity(ch='a', raw_val=51)
        time.sleep(0.5)
        print("   👀 Only LED A should be DIM (20%)")
        input("   Press ENTER to confirm...\n")

        # Test 3: Turn on Channel A at 100%
        print("TEST 3: Channel A at 100% (255/255)")
        print("-" * 40)
        print("   Sending: ba255 (set intensity 255)")
        ctrl.set_intensity(ch='a', raw_val=255)
        time.sleep(0.5)
        print("   👀 LED A should be BRIGHT (100%)")
        input("   Press ENTER to confirm...\n")

        # Test 4: Turn off, then turn on Channel B
        print("TEST 4: Turn off A, turn on B at 100%")
        print("-" * 40)
        print("   Sending: lx (turn off all)")
        ctrl.turn_off_channels()
        time.sleep(0.5)
        print("   👀 All LEDs should be OFF")
        time.sleep(1.0)

        print("   Sending: lb (enable B)")
        print("   Sending: bb255 (set intensity 255)")
        ctrl.set_intensity(ch='b', raw_val=255)
        time.sleep(0.5)
        print("   👀 Only LED B should be BRIGHT (100%)")
        input("   Press ENTER to confirm...\n")

        # Test 5: Use batch command
        print("TEST 5: Batch command - all LEDs at 50%")
        print("-" * 40)
        print("   Sending: batch:128,128,128,128")
        ctrl.set_batch_intensities(a=128, b=128, c=128, d=128)
        time.sleep(0.5)
        print("   👀 All 4 LEDs should be MEDIUM brightness (50%)")
        input("   Press ENTER to confirm...\n")

        # Test 6: Individual LEDs with batch
        print("TEST 6: Batch command - only C at 100%")
        print("-" * 40)
        print("   Sending: batch:0,0,255,0")
        ctrl.set_batch_intensities(a=0, b=0, c=255, d=0)
        time.sleep(0.5)
        print("   👀 Only LED C should be BRIGHT (100%)")
        input("   Press ENTER to confirm...\n")

        # Results
        print("="*80)
        print("TEST COMPLETE")
        print("="*80)
        print("\nPlease report your observations:")
        print("1. Did LEDs turn on/off as expected?")
        print("2. Was brightness changing properly (dim vs bright)?")
        print("3. Did only the specified LED light up each time?")
        print("4. Did 'lx' command turn off ALL LEDs including A?")
        print("\nIf any test failed, firmware V1.2 has LED control bugs.")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("\nCleanup: Turning off all LEDs...")
        try:
            ctrl.turn_off_channels()
            time.sleep(0.5)
        except:
            pass
        ctrl.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
