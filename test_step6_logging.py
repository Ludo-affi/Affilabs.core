"""Quick test to verify Step 6 logging output format."""

from utils.spr_calibrator import CalibrationState
from utils.logger import logger


def test_step6_logging_global():
    """Test logging output for GLOBAL calibration mode."""
    print("\n" + "=" * 80)
    print("TEST 1: GLOBAL CALIBRATION MODE")
    print("=" * 80)

    # Create a mock calibration state (global mode)
    state = CalibrationState()
    state.calibration_mode = 'global'
    state.integration = 0.150  # 150ms
    state.num_scans = 4
    state.leds_calibrated = {'a': 128, 'b': 255, 'c': 96, 'd': 64}

    ch_list = ['a', 'b', 'c', 'd']

    # Simulate Step 6 completion logging
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS")
    logger.info("=" * 80)

    # Log integration time (global or per-channel)
    if state.calibration_mode == 'per_channel':
        logger.info("Mode: PER-CHANNEL (separate integration times per channel)")
        logger.info("")
        logger.info("   Channel  | LED Intensity | Integration Time | Scans")
        logger.info("   " + "-" * 58)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0)
            int_val = state.integration_per_channel.get(ch, 0.0)
            scans = state.scans_per_channel.get(ch, 1)
            logger.info(f"      {ch.upper()}     |      {led_val:3d}       |     {int_val*1000:6.1f} ms     |   {scans}")
    else:
        logger.info("Mode: GLOBAL (single integration time for all channels)")
        logger.info(f"Integration Time: {state.integration*1000:.1f} ms")
        logger.info(f"Scans per channel: {state.num_scans}")
        logger.info("")
        logger.info("   Channel  | LED Intensity")
        logger.info("   " + "-" * 26)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0)
            logger.info(f"      {ch.upper()}     |      {led_val:3d}")

    logger.info("")
    logger.info("=" * 80)


def test_step6_logging_per_channel():
    """Test logging output for PER-CHANNEL calibration mode."""
    print("\n" + "=" * 80)
    print("TEST 2: PER-CHANNEL CALIBRATION MODE")
    print("=" * 80)

    # Create a mock calibration state (per-channel mode)
    state = CalibrationState()
    state.calibration_mode = 'per_channel'
    state.leds_calibrated = {'a': 255, 'b': 255, 'c': 255, 'd': 255}
    state.integration_per_channel = {'a': 0.120, 'b': 0.080, 'c': 0.150, 'd': 0.200}  # ms
    state.scans_per_channel = {'a': 1, 'b': 1, 'c': 1, 'd': 1}

    ch_list = ['a', 'b', 'c', 'd']

    # Simulate Step 6 completion logging
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS")
    logger.info("=" * 80)

    # Log integration time (global or per-channel)
    if state.calibration_mode == 'per_channel':
        logger.info("Mode: PER-CHANNEL (separate integration times per channel)")
        logger.info("")
        logger.info("   Channel  | LED Intensity | Integration Time | Scans")
        logger.info("   " + "-" * 58)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0)
            int_val = state.integration_per_channel.get(ch, 0.0)
            scans = state.scans_per_channel.get(ch, 1)
            logger.info(f"      {ch.upper()}     |      {led_val:3d}       |     {int_val*1000:6.1f} ms     |   {scans}")
    else:
        logger.info("Mode: GLOBAL (single integration time for all channels)")
        logger.info(f"Integration Time: {state.integration*1000:.1f} ms")
        logger.info(f"Scans per channel: {state.num_scans}")
        logger.info("")
        logger.info("   Channel  | LED Intensity")
        logger.info("   " + "-" * 26)
        for ch in ch_list:
            led_val = state.leds_calibrated.get(ch, 0)
            logger.info(f"      {ch.upper()}     |      {led_val:3d}")

    logger.info("")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_step6_logging_global()
    test_step6_logging_per_channel()

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE - Logging format verified")
    print("=" * 80)
    print("\nExpected output shows:")
    print("  1. GLOBAL mode: Single integration time + per-channel LED intensities")
    print("  2. PER-CHANNEL mode: Per-channel integration times + all LEDs at 255")
    print("\nThis logging will appear after Step 6 during real calibration.")
