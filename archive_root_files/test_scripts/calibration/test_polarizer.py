"""
Test script for polarizer calibration functionality.
This script tests the servo calibration import and basic functionality.
"""

import sys
import os
import logging
import warnings

# Suppress USB cleanup warnings (harmless errors during device disconnection)
warnings.filterwarnings('ignore', category=Warning)
logging.getLogger('seabreeze').setLevel(logging.ERROR)

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s :: %(levelname)s :: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Force UTF-8 encoding for console output to handle unicode characters
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("POLARIZER CALIBRATION TEST")
logger.info("=" * 80)

# Test 1: Import check
logger.info("\nTest 1: Checking imports...")
try:
    from utils.servo_calibration import auto_calibrate_polarizer
    logger.info("✅ auto_calibrate_polarizer imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import auto_calibrate_polarizer: {e}")
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)

# Test 2: Check for hardware connection utilities
logger.info("\nTest 2: Checking hardware utilities...")
try:
    from utils.detector_factory import create_detector
    from utils.controller import PicoP4SPR
    logger.info("✅ Hardware wrapper classes imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import hardware wrappers: {e}")
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)

# Test 3: Scan for hardware
logger.info("\nTest 3: Scanning for hardware...")
try:
    import serial.tools.list_ports

    # Find spectrometer
    logger.info("Looking for spectrometer...")
    config = {"detector_type": "USB4000"}
    usb = create_detector(None, config)
    if usb:
        logger.info(f"✅ Spectrometer found: {usb.serial_number if hasattr(usb, 'serial_number') else 'Unknown'}")
    else:
        logger.warning("⚠️ No spectrometer connected")
        usb = None

    # Find controller
    logger.info("Looking for controller...")
    ports = serial.tools.list_ports.comports()
    pico_port = None
    for port in ports:
        if 'USB Serial Device' in port.description or '2E8A:000A' in port.hwid:
            pico_port = port.device
            break

    if pico_port:
        logger.info(f"✅ Controller port found: {pico_port}")
        ctrl = PicoP4SPR()
        if ctrl.open():
            logger.info(f"✅ Controller connected: {ctrl.firmware_version if hasattr(ctrl, 'firmware_version') else ctrl.version}")
        else:
            logger.warning("⚠️ Controller found but failed to connect")
            ctrl = None
    else:
        logger.warning("⚠️ No controller found")
        ctrl = None

except Exception as e:
    logger.error(f"❌ Hardware scan failed: {e}")
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)

# Test 4: Check servo calibration function signature
logger.info("\nTest 4: Checking function signature...")
try:
    import inspect
    sig = inspect.signature(auto_calibrate_polarizer)
    logger.info(f"✅ Function signature: {sig}")
    logger.info(f"   Parameters: {list(sig.parameters.keys())}")
except Exception as e:
    logger.error(f"❌ Failed to inspect function: {e}")

# Test 5: Check for required helper functions
logger.info("\nTest 5: Checking helper functions...")
try:
    from utils.servo_calibration import (
        check_water_presence,
        perform_quadrant_search,
        validate_positions_with_transmission,
        perform_barrel_window_search
    )
    logger.info("✅ All helper functions imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import helper functions: {e}")
    import traceback
    logger.error(traceback.format_exc())

# Test 6: Dry run test (if hardware is connected)
if usb and ctrl:
    logger.info("\nTest 6: Hardware is connected - ready for calibration")
    logger.info("   To run actual calibration, call:")
    logger.info("   result = auto_calibrate_polarizer(usb, ctrl, require_water=True, polarizer_type='circular')")
    logger.info("\n⚠️ NOT running actual calibration in test mode")
else:
    logger.info("\nTest 6: Skipping (hardware not connected)")
    if not usb:
        logger.info("   ⚠️ Connect spectrometer")
    if not ctrl:
        logger.info("   ⚠️ Connect controller")

logger.info("\n" + "=" * 80)
logger.info("TEST COMPLETE")
logger.info("=" * 80)
