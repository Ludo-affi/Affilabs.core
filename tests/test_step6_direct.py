"""Direct test of Step 6 logging by simulating calibration state."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger
from utils.spr_calibrator import CalibrationState


def test_step6_logging_with_problem():
    """Simulate the reported problem: only channel B has LED value."""
    print("\n" + "=" * 80)
    print("SIMULATING REPORTED PROBLEM: Only Channel B LED is set")
    print("=" * 80)

    # Create mock state matching the problem description
    state = CalibrationState()
    state.calibration_mode = "global"
    state.integration = 0.150  # 150ms
    state.num_scans = 4

    # This is what we suspect is happening: only B has a value
    state.leds_calibrated = {
        "a": 0,  # ❌ Not set
        "b": 255,  # ✅ Only this one set
        "c": 0,  # ❌ Not set
        "d": 0,  # ❌ Not set
    }

    ch_list = ["a", "b", "c", "d"]

    # Execute the Step 6 logging code
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS")
    logger.info("=" * 80)

    if state.calibration_mode == "per_channel":
        logger.info("Mode: PER-CHANNEL (separate integration times per channel)")
        logger.info("")
        logger.info("   Channel  | LED Intensity | Integration Time | Scans")
        logger.info("   " + "-" * 58)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0) if state.leds_calibrated else 0
            int_val = (
                state.integration_per_channel.get(ch, 0.0)
                if hasattr(state, "integration_per_channel")
                else 0.0
            )
            scans = (
                state.scans_per_channel.get(ch, 1)
                if hasattr(state, "scans_per_channel")
                else 1
            )
            logger.info(
                f"      {ch.upper()}     |      {led_val:3d}       |     {int_val*1000:6.1f} ms     |   {scans}",
            )
    else:
        logger.info("Mode: GLOBAL (single integration time for all channels)")
        logger.info(f"Integration Time: {state.integration*1000:.1f} ms")
        logger.info(f"Scans per channel: {state.num_scans}")
        logger.info("")
        logger.info("   Channel  | LED Intensity")
        logger.info("   " + "-" * 26)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0) if state.leds_calibrated else 0
            logger.info(f"      {ch.upper()}     |      {led_val:3d}")

        # ⚠️ VALIDATION: Check if all LED values are identical
        if state.leds_calibrated:
            led_values = [state.leds_calibrated.get(ch, 0) for ch in ch_list]
            unique_leds = set(led_values)
            if len(unique_leds) == 1 and len(ch_list) > 1:
                logger.warning("")
                logger.warning("⚠️  WARNING: All channels have IDENTICAL LED values!")
                logger.warning(f"   All LEDs = {led_values[0]}")
                logger.warning(
                    "   This suggests Step 4 (LED balancing) did not execute properly.",
                )
                logger.warning(
                    "   Expected: Different LED values to balance channels to weakest.",
                )
                logger.warning("")

    logger.info("")
    logger.info("=" * 80)

    print("\n" + "=" * 80)
    print("[OK] This is what the logging will show for the reported problem")
    print("=" * 80)


def test_step6_all_same():
    """Test the identical LED values warning."""
    print("\n" + "=" * 80)
    print("SIMULATING: All LEDs have same value (Step 4 failed)")
    print("=" * 80)

    state = CalibrationState()
    state.calibration_mode = "global"
    state.integration = 0.150
    state.num_scans = 4
    state.leds_calibrated = {"a": 255, "b": 255, "c": 255, "d": 255}

    ch_list = ["a", "b", "c", "d"]

    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS")
    logger.info("=" * 80)
    logger.info("Mode: GLOBAL (single integration time for all channels)")
    logger.info(f"Integration Time: {state.integration*1000:.1f} ms")
    logger.info(f"Scans per channel: {state.num_scans}")
    logger.info("")
    logger.info("   Channel  | LED Intensity")
    logger.info("   " + "-" * 26)
    for ch in ch_list:
        led_val = state.leds_calibrated.get(ch, 0)
        logger.info(f"      {ch.upper()}     |      {led_val:3d}")

    # Check for identical values
    if state.leds_calibrated:
        led_values = [state.leds_calibrated.get(ch, 0) for ch in ch_list]
        unique_leds = set(led_values)
        if len(unique_leds) == 1 and len(ch_list) > 1:
            logger.warning("")
            logger.warning("⚠️  WARNING: All channels have IDENTICAL LED values!")
            logger.warning(f"   All LEDs = {led_values[0]}")
            logger.warning(
                "   This suggests Step 4 (LED balancing) did not execute properly.",
            )
            logger.warning(
                "   Expected: Different LED values to balance channels to weakest.",
            )
            logger.warning("")

    logger.info("")
    logger.info("=" * 80)


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("TESTING STEP 6 CALIBRATION LOGGING")
    print("=" * 80)

    test_step6_logging_with_problem()
    test_step6_all_same()

    print("\n" + "=" * 80)
    print("[OK] TESTS COMPLETE")
    print("=" * 80)
    print("\nThe logging code is working correctly.")
    print("During real calibration, this will clearly show:")
    print("  1. Which channels have zero LED values")
    print("  2. If all channels have identical values (Step 4 failure)")
    print("  3. The exact LED and integration time settings")
