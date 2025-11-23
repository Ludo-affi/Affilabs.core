"""Check LED values used in live data acquisition.

This script reads the calibration state and shows what LED values
will be used during P-pol live measurements.
"""

import sys
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from utils.logger import logger
from settings.settings import CH_LIST


def check_device_config():
    """Check device_config.json for saved LED calibration."""
    config_file = ROOT_DIR / "config" / "device_config.json"

    if not config_file.exists():
        logger.warning(f"❌ Device config not found: {config_file}")
        return None

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        led_cal = config.get('calibration', {}).get('led_calibration', {})
        if not led_cal:
            logger.warning("❌ No LED calibration found in device_config.json")
            return None

        s_mode = led_cal.get('s_mode_intensities', {})
        p_mode = led_cal.get('p_mode_intensities', {})
        integration = led_cal.get('integration_time_ms', 0)

        logger.info("=" * 80)
        logger.info("📋 DEVICE CONFIG LED CALIBRATION")
        logger.info("=" * 80)
        logger.info(f"Integration Time: {integration} ms")
        logger.info("")
        logger.info("S-mode LED intensities:")
        for ch in CH_LIST:
            val = s_mode.get(ch, 'N/A')
            logger.info(f"   {ch.upper()}: {val}")

        logger.info("")
        logger.info("P-mode LED intensities:")
        for ch in CH_LIST:
            val = p_mode.get(ch, 'N/A')
            logger.info(f"   {ch.upper()}: {val}")

        logger.info("=" * 80)

        return {
            's_mode': s_mode,
            'p_mode': p_mode,
            'integration_ms': integration
        }

    except Exception as e:
        logger.error(f"❌ Error reading device config: {e}")
        return None


def check_calib_state():
    """Check shared calibration state."""
    try:
        from utils.spr_calibrator import CalibrationState

        # Try to load from device config
        state = CalibrationState()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📋 CALIBRATION STATE")
        logger.info("=" * 80)

        if hasattr(state, 'ref_intensity') and state.ref_intensity:
            logger.info("ref_intensity:")
            for ch in CH_LIST:
                val = state.ref_intensity.get(ch, 'N/A')
                logger.info(f"   {ch.upper()}: {val}")
        else:
            logger.warning("⚠️ ref_intensity not populated")

        logger.info("")
        if hasattr(state, 'leds_calibrated') and state.leds_calibrated:
            logger.info("leds_calibrated:")
            for ch in CH_LIST:
                val = state.leds_calibrated.get(ch, 'N/A')
                logger.info(f"   {ch.upper()}: {val}")
        else:
            logger.warning("⚠️ leds_calibrated not populated")

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error checking calibration state: {e}")


def simulate_get_led_for_live():
    """Simulate what get_led_for_live() will return."""
    try:
        from utils.spr_calibrator import CalibrationState

        state = CalibrationState()

        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 SIMULATING get_led_for_live() FOR EACH CHANNEL")
        logger.info("=" * 80)

        for ch in CH_LIST:
            # Simulate the logic from get_led_for_live()
            led_val = None
            source = None

            # Check leds_calibrated first
            if hasattr(state, 'leds_calibrated') and ch in getattr(state, 'leds_calibrated', {}):
                val = state.leds_calibrated.get(ch, 0)
                if val > 0:
                    led_val = val
                    source = "leds_calibrated"

            # Fall back to ref_intensity
            if led_val is None:
                if hasattr(state, 'ref_intensity') and ch in getattr(state, 'ref_intensity', {}):
                    val = state.ref_intensity.get(ch, 0)
                    if val > 0:
                        led_val = val
                        source = "ref_intensity"

            # Final fallback
            if led_val is None:
                led_val = 255
                source = "default (255)"

            logger.info(f"Channel {ch.upper()}: LED = {led_val:3d}  (from {source})")

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error simulating get_led_for_live: {e}")


if __name__ == "__main__":
    logger.info("🔍 Checking LED values for live P-pol acquisition...")
    logger.info("")

    # Check device config
    device_leds = check_device_config()

    # Check calibration state
    check_calib_state()

    # Simulate what live acquisition will see
    simulate_get_led_for_live()

    logger.info("")
    logger.info("✅ Check complete")
