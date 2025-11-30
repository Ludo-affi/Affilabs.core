"""Test LED command sequence during calibration Steps 1-2.

This script validates that:
1. LEDs can be turned off properly
2. LED state can be verified (V1.1+)
3. No unintended LED activation occurs during calibration
"""

import time
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR, ArduinoController
from utils.logger import logger

# Test configuration
TEST_CONTROLLER_TYPE = "pico"  # "pico" or "arduino"


def test_led_off_verification(ctrl):
    """Test Step 1: LED off verification."""
    print("\n" + "="*80)
    print("TEST 1: LED OFF VERIFICATION (Step 1 of Calibration)")
    print("="*80)

    # Turn off all LEDs
    print("\n1. Turning off all LEDs...")
    success = ctrl.turn_off_channels()
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    time.sleep(0.2)

    # Verify LEDs are off (V1.1+ firmware)
    has_led_query = hasattr(ctrl, 'get_all_led_intensities')
    print(f"\n2. LED query available: {has_led_query}")

    if has_led_query:
        print("\n3. Verifying LED state (V1.1+ firmware)...")
        max_retries = 5

        for attempt in range(max_retries):
            time.sleep(0.01)  # Wait for command to process

            # Query LED state
            led_state = ctrl.get_all_led_intensities()

            if led_state is None:
                print(f"   ❌ LED query failed (attempt {attempt+1}/{max_retries})")
                continue

            # Check if all LEDs are off
            all_off = all(intensity == 0 for intensity in led_state.values())
            print(f"   Attempt {attempt+1}/{max_retries}: {led_state}")

            if all_off:
                print(f"   ✅ All LEDs confirmed OFF")
                return True
            else:
                print(f"   ⚠️  LEDs still on - retrying turn_off_channels()")
                ctrl.turn_off_channels()
                time.sleep(0.05)

        print(f"   ❌ Failed to verify LEDs off after {max_retries} attempts")
        return False
    else:
        print("   ⚠️  V1.0 firmware - using timing-based approach")
        time.sleep(0.05)
        print("   ✅ Assumed LEDs are off (timing-based)")
        return True


def test_led_command_sequence(ctrl):
    """Test typical LED command sequence that might cause issues."""
    print("\n" + "="*80)
    print("TEST 2: LED COMMAND SEQUENCE")
    print("="*80)

    # Start with all LEDs off
    print("\n1. Initial state: All LEDs OFF")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   Verified state: {state}")

    # Test: What happens if we query LED state without turning anything on?
    print("\n2. Testing LED state query without turning on...")
    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

        if state is None:
            print("   ⚠️  LED query failed - firmware may not support queries")
        elif any(intensity > 0 for intensity in state.values()):
            print("   ⚠️  WARNING: Some LEDs showing non-zero intensity!")
        else:
            print("   ✅ All LEDs remain at 0 intensity")

    # Test: Turn on one channel and verify only that channel is on
    print("\n3. Testing single channel activation (Channel A)...")
    print("   Turning on channel A only...")
    ctrl.turn_on_channel('a')
    time.sleep(0.1)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

        if state is None:
            print("   ⚠️  LED query failed")
        elif state.get('a', 0) > 0 and all(state.get(ch, 0) == 0 for ch in ['b', 'c', 'd']):
            print("   ✅ Only channel A is enabled")
        else:
            print("   ⚠️  WARNING: Unexpected LED state!")

    # Clean up
    print("\n4. Cleanup: Turning off all channels...")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   Final state: {state}")


def test_batch_command(ctrl):
    """Test batch LED command (V1.1+)."""
    print("\n" + "="*80)
    print("TEST 3: BATCH LED COMMAND (V1.1+ Only)")
    print("="*80)

    has_batch = hasattr(ctrl, 'set_batch_intensities')
    print(f"\nBatch command available: {has_batch}")

    if not has_batch:
        print("   ⚠️  Firmware doesn't support batch commands - skipping test")
        return

    # Test 1: Set all to 0 using batch
    print("\n1. Testing batch command with all LEDs at 0...")
    success = ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    time.sleep(0.1)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

        if state is None:
            print("   ⚠️  LED query failed")

    # Test 2: Set one LED using batch
    print("\n2. Testing batch command with only channel B at 50...")
    success = ctrl.set_batch_intensities(a=0, b=50, c=0, d=0)
    print(f"   Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    time.sleep(0.1)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

        if state is not None:
            expected = {'a': 0, 'b': 50, 'c': 0, 'd': 0}
            tolerance = 5
            match = all(abs(state.get(ch, -1) - expected[ch]) <= tolerance for ch in ['a', 'b', 'c', 'd'])
            if match:
                print("   ✅ LED state matches expected values")
            else:
                print("   ⚠️  LED state doesn't match expected values")
        else:
            print("   ⚠️  LED query failed")

    # Clean up
    print("\n3. Cleanup: Setting all LEDs to 0 via batch...")
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.2)


def test_set_intensity_zero(ctrl):
    """Test what happens when set_intensity(ch, 0) is called."""
    print("\n" + "="*80)
    print("TEST 4: SET_INTENSITY WITH 0 VALUE")
    print("="*80)

    # Start clean
    print("\n1. Initial cleanup...")
    ctrl.turn_off_channels()
    time.sleep(0.2)

    # Set channel A to 100
    print("\n2. Setting channel A to intensity 100...")
    ctrl.set_intensity('a', 100)
    time.sleep(0.1)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

    # Now set it to 0
    print("\n3. Setting channel A to intensity 0...")
    ctrl.set_intensity('a', 0)
    time.sleep(0.1)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state: {state}")

        if state is not None and state.get('a', -1) == 0:
            print("   ✅ Channel A properly disabled (intensity=0)")
        elif state is not None:
            print(f"   ⚠️  WARNING: Channel A shows intensity {state.get('a', -1)}")
        else:
            print("   ⚠️  LED query failed")

    # Clean up
    ctrl.turn_off_channels()


def test_mode_switch_side_effect(ctrl):
    """Test if set_mode() command activates LEDs (Hypothesis #2 & #3)."""
    print("\n" + "="*80)
    print("TEST 5: MODE SWITCH SIDE EFFECT (CALIBRATION STEP 3)")
    print("="*80)
    print("\nThis tests if switching servo mode activates LEDs.")
    print("This is what happens at the start of Step 3 in calibration.\n")

    # Phase 1: Turn off and verify
    print("1. Turning off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(1.0)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state after turn_off: {state}")

    print("   👀 OBSERVE: All LEDs should be OFF")
    input("\n   Press ENTER to confirm LEDs are OFF...")

    # Phase 2: Switch to S-mode (what Step 3 does)
    print("\n2. Switching to S-mode (servo movement)...")
    print("   This mimics: switch_mode_safely(ctrl, 's', turn_off_leds=True)")
    print("   Command: ss")

    if hasattr(ctrl, 'set_mode'):
        ctrl.set_mode('s')
        time.sleep(1.0)
        print("   Mode switch complete")
    else:
        print("   ⚠️  Controller doesn't support set_mode()")

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state after mode switch: {state}")

    print("\n   👀 CRITICAL: Did any LEDs turn on during/after mode switch?")
    time.sleep(1.0)
    result = input("   Did ANY LEDs turn ON after switching to S-mode? (y/n): ").lower().strip()

    # Phase 3: Test P-mode switch
    print("\n3. Switching to P-mode...")
    print("   Command: sp")

    if hasattr(ctrl, 'set_mode'):
        ctrl.set_mode('p')
        time.sleep(1.0)
        print("   Mode switch complete")

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state after P-mode: {state}")

    print("\n   👀 OBSERVE: Did LEDs turn on switching to P-mode?")
    time.sleep(1.0)
    result_p = input("   Did ANY LEDs turn ON after switching to P-mode? (y/n): ").lower().strip()

    # Phase 4: Test with previous LED state (Hypothesis #2)
    print("\n4. Testing firmware state restoration...")
    print("   Setting all LEDs to 150 (59% brightness)...")

    if hasattr(ctrl, 'set_batch_intensities'):
        ctrl.set_batch_intensities(a=150, b=150, c=150, d=150)
    else:
        for ch in ['a', 'b', 'c', 'd']:
            ctrl.set_intensity(ch, 150)

    time.sleep(1.0)
    print("   👀 OBSERVE: All LEDs should be ON at medium brightness")
    input("\n   Press ENTER to confirm LEDs are ON...")

    print("\n5. Turning off LEDs...")
    ctrl.turn_off_channels()
    time.sleep(1.0)
    print("   👀 OBSERVE: All LEDs should be OFF")
    input("\n   Press ENTER to confirm LEDs are OFF...")

    print("\n6. Switching mode (does firmware restore previous state?)...")
    if hasattr(ctrl, 'set_mode'):
        ctrl.set_mode('s')
        time.sleep(1.0)

    if hasattr(ctrl, 'get_all_led_intensities'):
        state = ctrl.get_all_led_intensities()
        print(f"   LED state after mode switch: {state}")

        if any(v > 10 for v in state.values()):
            print("   🔴 WARNING: LEDs restored to previous state!")
            print(f"   Intensity values: {state}")
        else:
            print("   ✅ LEDs remained off (state not restored)")

    print("\n   👀 CRITICAL: Did LEDs turn back ON at 150 intensity?")
    time.sleep(1.0)
    result_restore = input("   Did LEDs restore to previous state (150)? (y/n): ").lower().strip()

    # Clean up
    print("\n7. Cleanup: Turning off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(0.5)

    # Results
    print("\n" + "-" * 80)
    print("TEST RESULTS:")
    print("-" * 80)
    print(f"S-mode switch activated LEDs: {result.upper()}")
    print(f"P-mode switch activated LEDs: {result_p.upper()}")
    print(f"Mode switch restored LED state: {result_restore.upper()}")

    if result == 'y' or result_p == 'y':
        print("\n🔴 HYPOTHESIS CONFIRMED: Mode switch command activates LEDs")
        print("   This explains why LEDs turn on at start of Step 3")
        print("   Firmware bug: ss/sp commands should not enable LEDs")
    elif result_restore == 'y':
        print("\n🔴 HYPOTHESIS CONFIRMED: Firmware state machine restores LEDs")
        print("   Mode switch restores previous LED state")
        print("   Firmware bug: Should not restore LED state on mode switch")
    else:
        print("\n✅ NO BUG: Mode switch does not activate LEDs")
        print("   LEDs turning on must be from Step 3 ranking (expected)")
    print("-" * 80)
def main():
    """Run all LED command tests."""
    print("="*80)
    print("LED COMMAND TEST SUITE")
    print("Testing calibration Step 1-2 LED behavior")
    print("="*80)

    # Initialize controller
    if TEST_CONTROLLER_TYPE == "pico":
        print("\nInitializing PicoP4SPR controller...")
        ctrl = PicoP4SPR()
    else:
        print("\nInitializing ArduinoController controller...")
        ctrl = ArduinoController()

    if not ctrl.open():
        print("❌ Failed to open controller connection")
        print("   Please check:")
        print("   - Controller is connected via USB")
        print("   - No other software is using the controller")
        print("   - Correct controller type selected")
        return 1

    print(f"✅ Controller connected: {ctrl.name}")
    print(f"   Firmware version: {getattr(ctrl, 'version', 'Unknown')}")

    try:
        # Run tests
        test_led_off_verification(ctrl)
        test_led_command_sequence(ctrl)
        test_batch_command(ctrl)
        test_set_intensity_zero(ctrl)
        test_mode_switch_side_effect(ctrl)

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETE")
        print("="*80)
        print("\nPlease observe:")
        print("1. Did any LEDs turn on unexpectedly during testing?")
        print("2. Did the LED query commands work correctly?")
        print("3. Did the batch command (if available) work as expected?")
        print("\nIf any LEDs turned on when they shouldn't have, this indicates")
        print("a firmware or communication issue that needs investigation.")

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
        except:
            pass
        ctrl.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
