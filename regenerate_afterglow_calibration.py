"""Regenerate optical_calibration.json with all 4 channels.

This script re-runs afterglow calibration to fix missing channel 'd' data.
The afterglow correction requires ALL 4 channels due to cross-channel correction:
- Channel A corrected by D afterglow
- Channel B corrected by A afterglow
- Channel C corrected by B afterglow
- Channel D corrected by C afterglow

Usage:
    python regenerate_afterglow_calibration.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from utils.device_manager import get_device_manager


def main():
    """Run afterglow calibration to regenerate optical_calibration.json."""

    logger.info("=" * 80)
    logger.info("REGENERATING AFTERGLOW CALIBRATION")
    logger.info("=" * 80)

    # Get device manager
    device_manager = get_device_manager()

    # Check if device is set
    if device_manager.current_device_serial is None:
        logger.error("❌ No device selected!")
        logger.error("   Please select a device first.")
        return 1

    logger.info(f"Current device: {device_manager.current_device_serial}")

    # Check if optical calibration file exists
    optical_cal_file = device_manager.current_device_dir / "optical_calibration.json"
    if optical_cal_file.exists():
        logger.warning(f"⚠️  Existing optical calibration file will be replaced:")
        logger.warning(f"   {optical_cal_file}")

        # Show which channels are in current file
        import json
        try:
            with open(optical_cal_file, 'r') as f:
                data = json.load(f)
                channels = list(data.get('channel_data', {}).keys())
                logger.warning(f"   Current channels: {channels}")

                if len(channels) == 4:
                    logger.info("✅ File already has all 4 channels. Re-running anyway to ensure quality.")
                else:
                    logger.error(f"❌ File missing channels! Has {len(channels)}/4: {channels}")
                    missing = [ch for ch in ['a', 'b', 'c', 'd'] if ch not in channels]
                    logger.error(f"   Missing: {missing}")
        except Exception as e:
            logger.warning(f"   Could not parse existing file: {e}")

    # Import calibrator
    try:
        from utils.spr_calibrator import SPRCalibrator
    except ImportError as e:
        logger.error(f"❌ Failed to import SPRCalibrator: {e}")
        return 1

    # You'll need to initialize the calibrator with your hardware instances
    # This typically requires:
    # - ctrl (PicoP4SPRHAL instance)
    # - usb (Spectrometer instance)
    # - main_window (for UI callbacks)

    logger.error("=" * 80)
    logger.error("⚠️  MANUAL STEPS REQUIRED")
    logger.error("=" * 80)
    logger.error("")
    logger.error("This script needs to be integrated into your application workflow.")
    logger.error("To re-run afterglow calibration, you need to:")
    logger.error("")
    logger.error("1. From the GUI: Look for calibration menu → Run Optical Calibration")
    logger.error("")
    logger.error("2. Or programmatically call:")
    logger.error("   calibrator._run_optical_calibration()")
    logger.error("")
    logger.error("3. The calibration will:")
    logger.error("   - Test all 4 channels: a, b, c, d")
    logger.error("   - Test multiple integration times: [10, 25, 40, 55, 70, 85] ms")
    logger.error("   - Use LED intensities from your device_config.json")
    logger.error("   - Take approximately 5-10 minutes")
    logger.error("   - Save results to:")
    logger.error(f"     {optical_cal_file}")
    logger.error("")
    logger.error("4. After completion, verify all channels present:")
    logger.error("   python -c \"import json; print(list(json.load(open(r'" + str(optical_cal_file) + "'))['channel_data'].keys()))\"")
    logger.error("")
    logger.error("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
