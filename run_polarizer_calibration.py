"""
Run actual polarizer calibration.
This script performs a real polarizer calibration with the connected hardware.
"""

import sys
import os
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Force UTF-8 for console
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("POLARIZER CALIBRATION - LIVE RUN")
logger.info("=" * 80)

# Import required modules
logger.info("\nImporting modules...")
try:
    from utils.servo_calibration import auto_calibrate_polarizer
    from utils.detector_factory import create_detector
    from utils.controller import PicoP4SPR
    logger.info("[OK] All modules imported successfully")
except Exception as e:
    logger.error(f"[FAIL] Import error: {e}")
    sys.exit(1)

# Connect to hardware
logger.info("\nConnecting to hardware...")
try:
    # Connect spectrometer
    config = {"detector_type": "USB4000"}
    usb = create_detector(None, config)
    if not usb:
        logger.error("[FAIL] Could not connect to spectrometer")
        sys.exit(1)
    logger.info(f"[OK] Spectrometer connected: {usb.serial_number if hasattr(usb, 'serial_number') else 'Unknown'}")

    # Connect controller
    ctrl = PicoP4SPR()
    if not ctrl.open():
        logger.error("[FAIL] Could not connect to controller")
        sys.exit(1)
    logger.info(f"[OK] Controller connected: {ctrl.version}")

except Exception as e:
    logger.error(f"[FAIL] Hardware connection error: {e}")
    sys.exit(1)

# Run calibration
logger.info("\n" + "=" * 80)
logger.info("STARTING POLARIZER CALIBRATION")
logger.info("=" * 80)
logger.info("\nThis will take approximately 1-2 minutes...")
logger.info("Please ensure water/buffer is on the sensor!\n")

try:
    # Try with channel B (often brighter and more stable)
    logger.info("\nUsing LED channel B for calibration...")

    result = auto_calibrate_polarizer(
        usb=usb,
        ctrl=ctrl,
        require_water=True,
        polarizer_type='circular'
    )

    if result and result.get('success'):
        logger.info("\n" + "=" * 80)
        logger.info("CALIBRATION SUCCESSFUL!")
        logger.info("=" * 80)
        logger.info(f"\nResults:")
        logger.info(f"  Polarizer Type: {result.get('polarizer_type', 'unknown').upper()}")
        logger.info(f"  S Position: {result.get('s_pos')} degrees")
        logger.info(f"  P Position: {result.get('p_pos')} degrees")
        logger.info(f"  S/P Ratio: {result.get('sp_ratio', 0):.2f}x")
        logger.info(f"  SPR Dip Depth: {result.get('dip_depth_percent', 0):.1f}%")
        if 'resonance_wavelength' in result:
            logger.info(f"  Resonance Wavelength: {result.get('resonance_wavelength'):.1f} nm")

        # Show validation checks
        if 'validation_checks' in result:
            logger.info(f"\nValidation Checks:")
            for check_name, passed, detail in result['validation_checks']:
                status = "[PASS]" if passed else "[FAIL]"
                logger.info(f"  {status} {check_name}: {detail}")

        # Ask if user wants to save
        logger.info("\n" + "=" * 80)
        logger.info("To save these positions to device config:")
        logger.info("  1. Open the main application")
        logger.info("  2. Go to Device Configuration")
        logger.info("  3. Set S position and P position manually")
        logger.info(f"     S = {result.get('s_pos')}")
        logger.info(f"     P = {result.get('p_pos')}")
        logger.info("=" * 80)

    else:
        logger.error("\n" + "=" * 80)
        logger.error("CALIBRATION FAILED")
        logger.error("=" * 80)
        if result:
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
        else:
            logger.error("No result returned from calibration")
        sys.exit(1)

except KeyboardInterrupt:
    logger.warning("\n\nCalibration interrupted by user")
    sys.exit(1)
except Exception as e:
    logger.exception(f"\n\nCalibration error: {e}")
    sys.exit(1)
finally:
    # Cleanup
    logger.info("\nCleaning up...")
    try:
        if usb:
            usb.close()
        if ctrl:
            ctrl.close()
    except:
        pass
    logger.info("Done.")
