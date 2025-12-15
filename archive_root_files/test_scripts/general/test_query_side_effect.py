"""Test if LED query commands (ia, ib, ic, id) have side effects.

This script validates whether querying LED intensity activates the LED channel.

CRITICAL TEST: Determines if firmware bug exists before updating firmware.

Expected Behavior (NO BUG):
- Turn off all LEDs → LEDs physically off
- Query LED intensity → LEDs stay off (read-only operation)

Buggy Behavior (BUG EXISTS):
- Turn off all LEDs → LEDs physically off
- Query LED intensity → LEDs turn on (side effect!)

OBSERVE THE PHYSICAL LEDs - Do they light up during query?
"""

import sys
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import ArduinoController, PicoP4SPR

# Test configuration
TEST_CONTROLLER_TYPE = "pico"  # "pico" or "arduino"
PAUSE_FOR_OBSERVATION = 2.0  # Seconds to pause and observe LEDs


def test_query_side_effect(ctrl):
    """Test if query commands activate LEDs as side effect."""
    print("\n" + "=" * 80)
    print("🔬 CRITICAL TEST: LED QUERY SIDE EFFECT VALIDATION")
    print("=" * 80)
    print("\nThis test determines if query commands (ia, ib, ic, id) activate LEDs.")
    print("WATCH THE PHYSICAL LEDs - Do they turn on during the query phase?\n")

    # Check if query method exists
    has_query = hasattr(ctrl, "get_led_intensity")
    print(f"Controller has get_led_intensity(): {has_query}")

    if not has_query:
        print("❌ Controller doesn't support LED queries - test cannot run")
        return False

    # Get firmware version
    fw_version = getattr(ctrl, "version", "Unknown")
    print(f"Firmware version: {fw_version}")
    print()

    # =========================================================================
    # PHASE 1: Turn off all LEDs and verify they're physically off
    # =========================================================================
    print("-" * 80)
    print("PHASE 1: BASELINE - Turn off all LEDs")
    print("-" * 80)

    print("\n1. Sending turn_off_channels() command...")
    success = ctrl.turn_off_channels()
    print(f"   Command result: {'✅ Success' if success else '❌ Failed'}")

    print(f"\n2. Waiting {PAUSE_FOR_OBSERVATION}s for LEDs to turn off...")
    print("   👀 OBSERVE: All LEDs should be OFF now")
    time.sleep(PAUSE_FOR_OBSERVATION)

    input("\n   Press ENTER to confirm all LEDs are physically OFF...")

    # =========================================================================
    # PHASE 2: Query LED A without turning it on - CHECK FOR SIDE EFFECT
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 2: QUERY TEST - Query LED A intensity (WITHOUT turn_on command)")
    print("-" * 80)

    print("\n3. Sending query command for LED A (ia\\n)...")
    print("   This should be a READ-ONLY operation")
    print("   👀 CRITICAL: Watch LED A - does it turn on?\n")

    # Direct serial command to isolate the query
    if ctrl._ser is not None:
        # Send ia command directly
        with ctrl._lock:
            ctrl._ser.reset_input_buffer()
            ctrl._ser.write(b"ia\n")
            time.sleep(0.05)
            response = ctrl._ser.readline().decode().strip()
            print(f"   Firmware response: '{response}'")

    print(f"\n4. Pausing {PAUSE_FOR_OBSERVATION}s for observation...")
    print("   👀 OBSERVE: Did LED A turn on after the query?")
    time.sleep(PAUSE_FOR_OBSERVATION)

    print("\n   📝 Record your observation:")
    led_a_on = (
        input("   Did LED A physically turn ON after query? (y/n): ").lower().strip()
    )

    # =========================================================================
    # PHASE 3: Query all LEDs - CHECK IF MULTIPLE LEDs ACTIVATE
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 3: FULL QUERY TEST - Query all 4 LEDs")
    print("-" * 80)

    # Turn off again to reset state
    print("\n5. Resetting: Turn off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(0.5)

    print("\n6. Querying all LED intensities (ia, ib, ic, id)...")
    print("   This mimics what calibration Step 1 does")
    print("   👀 CRITICAL: Watch all 4 LEDs - do any turn on?\n")

    # Use the actual method that calibration uses
    led_state = ctrl.get_all_led_intensities()
    print(f"   Firmware response: {led_state}")

    print(f"\n7. Pausing {PAUSE_FOR_OBSERVATION}s for observation...")
    print("   👀 OBSERVE: Did ANY LEDs turn on after querying all?")
    time.sleep(PAUSE_FOR_OBSERVATION)

    print("\n   📝 Record your observation:")
    any_leds_on = (
        input("   Did ANY LEDs physically turn ON after query? (y/n): ").lower().strip()
    )

    # =========================================================================
    # PHASE 4: Control test - Verify batch command works correctly
    # =========================================================================
    print("\n" + "-" * 80)
    print("PHASE 4: CONTROL TEST - Batch command (should turn on LEDs)")
    print("-" * 80)

    print("\n8. Sending batch command to turn on LED B at 50...")
    print("   This SHOULD turn on LED B (positive control)")

    if hasattr(ctrl, "set_batch_intensities"):
        ctrl.set_batch_intensities(a=0, b=50, c=0, d=0)
        print("   Command sent: batch:0,50,0,0")
    else:
        ctrl.set_intensity("b", 50)
        print("   Command sent: turn_on_channel(b) + set_intensity(b, 50)")

    print(f"\n9. Pausing {PAUSE_FOR_OBSERVATION}s for observation...")
    print("   👀 OBSERVE: LED B should be ON now (dimly lit)")
    time.sleep(PAUSE_FOR_OBSERVATION)

    input("\n   Press ENTER to confirm LED B is physically ON...")

    # Clean up
    print("\n10. Cleanup: Turning off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(0.5)

    # =========================================================================
    # RESULTS ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS")
    print("=" * 80)

    bug_exists = led_a_on == "y" or any_leds_on == "y"

    print(f"\nPhase 2 - Single query (ia): LED A turned on? {led_a_on.upper()}")
    print(f"Phase 3 - All queries (ia,ib,ic,id): Any LEDs on? {any_leds_on.upper()}")
    print("Phase 4 - Control test (batch): LED B turned on? YES (confirmed)")

    print("\n" + "-" * 80)
    if bug_exists:
        print("❌ BUG CONFIRMED: Query commands have side effects!")
        print("-" * 80)
        print("\n🔴 FIRMWARE BUG EXISTS:")
        print("   • LED query commands (ia, ib, ic, id) activate LED channels")
        print("   • This is NOT a read-only operation")
        print("   • Causes LEDs to turn on during calibration Step 1 verification")
        print("\n✅ WORKAROUND JUSTIFIED:")
        print("   • Disabling LED queries in calibration is CORRECT")
        print("   • Must use timing-based verification until firmware fixed")
        print("\n🔧 FIRMWARE FIX REQUIRED:")
        print("   • Query commands should NOT enable LED channels")
        print("   • Should only return intensity value (read-only)")
        print("   • Update firmware and re-test")
    else:
        print("✅ NO BUG DETECTED: Query commands are read-only")
        print("-" * 80)
        print("\n🟢 FIRMWARE WORKING CORRECTLY:")
        print("   • LED query commands (ia, ib, ic, id) do NOT activate LEDs")
        print("   • Read-only operation confirmed")
        print("   • Safe to re-enable LED queries in calibration")
        print("\n⚠️ INVESTIGATION NEEDED:")
        print("   • If LEDs turn on during calibration, cause is elsewhere")
        print("   • Check other firmware commands in Steps 1-3")
        print("   • Review calibration log for unexpected commands")

    print("\n" + "=" * 80)

    return not bug_exists


def test_alternative_hypothesis(ctrl):
    """Test if turn_on_channel() is being called unexpectedly."""
    print("\n" + "=" * 80)
    print("🔬 ALTERNATIVE HYPOTHESIS: turn_on_channel() side effect")
    print("=" * 80)
    print("\nTesting if turn_on_channel() is called when it shouldn't be.\n")

    # Phase 1: Turn off and verify
    print("1. Turning off all LEDs...")
    ctrl.turn_off_channels()
    time.sleep(1.0)
    print("   👀 OBSERVE: All LEDs should be OFF")
    input("\n   Press ENTER to confirm all LEDs are OFF...")

    # Phase 2: Call turn_on_channel() but don't set intensity
    print("\n2. Calling turn_on_channel('c') WITHOUT setting intensity...")
    print("   This enables the channel but doesn't set PWM duty cycle")
    ctrl.turn_on_channel("c")

    print(f"\n3. Pausing {PAUSE_FOR_OBSERVATION}s for observation...")
    print("   👀 OBSERVE: Does LED C turn on (even without set_intensity)?")
    time.sleep(PAUSE_FOR_OBSERVATION)

    led_c_on = input("\n   Did LED C physically turn ON? (y/n): ").lower().strip()

    # Clean up
    ctrl.turn_off_channels()
    time.sleep(0.5)

    print("\n" + "-" * 80)
    if led_c_on == "y":
        print("⚠️ PARTIAL BUG: turn_on_channel() activates LED without intensity")
        print("   • Enabling channel causes LED to turn on at last intensity")
        print("   • Or firmware defaults to non-zero intensity")
    else:
        print("✅ EXPECTED: turn_on_channel() alone doesn't activate LED")
        print("   • Channel enabled but LED stays off (requires set_intensity)")
    print("-" * 80)


def main():
    """Run LED query side effect validation tests."""
    print("=" * 80)
    print("LED QUERY SIDE EFFECT VALIDATION")
    print("Testing if ia/ib/ic/id commands activate LEDs")
    print("=" * 80)

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

    print("\n" + "=" * 80)
    print("⚠️  IMPORTANT INSTRUCTIONS:")
    print("=" * 80)
    print("1. WATCH THE PHYSICAL LEDs on the device")
    print("2. Note when each LED turns ON or OFF")
    print("3. Answer honestly about what you observe")
    print("4. This test determines if firmware needs updating")
    print("=" * 80)

    input("\nPress ENTER when ready to begin...")

    try:
        # Run main test
        no_bug = test_query_side_effect(ctrl)

        # Run alternative hypothesis test
        print("\n")
        input("Press ENTER to run alternative hypothesis test...")
        test_alternative_hypothesis(ctrl)

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 80)

        if not no_bug:
            print("\n🔴 ACTION REQUIRED:")
            print("   1. Firmware bug confirmed - query commands activate LEDs")
            print("   2. Keep LED query disabled in calibration (current workaround)")
            print("   3. Update firmware to fix query command side effect")
            print("   4. Re-run this test after firmware update to verify fix")
            return 1
        print("\n🟢 RESULT:")
        print("   • No firmware bug detected in query commands")
        print("   • Safe to re-enable LED queries if desired")
        print("   • Investigate other potential causes if LEDs activate unexpectedly")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        # Final cleanup
        print("\nFinal cleanup: Turning off all LEDs...")
        try:
            ctrl.turn_off_channels()
        except:
            pass
        time.sleep(0.5)
        ctrl.close()
        print("✅ Controller closed")


if __name__ == "__main__":
    sys.exit(main())
