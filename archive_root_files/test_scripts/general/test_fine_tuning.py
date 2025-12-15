"""Test the enhanced 3-stage refinement (±20°, ±5°, ±2°) for P position.
This will show how the algorithm converges to the exact minimum.
"""

import logging
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

if sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("FINE-TUNING TEST - 3-Stage P Position Refinement")
logger.info("=" * 80)

# Import required modules

from utils.controller import PicoP4SPR
from utils.detector_factory import create_detector
from utils.servo_calibration import perform_quadrant_search

# Connect hardware
logger.info("\nConnecting to hardware...")
config = {"detector_type": "USB4000"}
usb = create_detector(None, config)
ctrl = PicoP4SPR()

if not ctrl.open():
    logger.error("[FAIL] Controller connection failed!")
    sys.exit(1)

logger.info(f"[OK] Spectrometer: {usb.serial_number}")
logger.info(f"[OK] Controller: {ctrl.version}")

# Set integration time
usb.set_integration(50)

# Run quadrant search with multi-stage refinement
logger.info("\n" + "=" * 80)
logger.info("Running Quadrant Search with 3-Stage Refinement")
logger.info("=" * 80)
logger.info("")

result = perform_quadrant_search(usb, ctrl)

if result:
    s_pos_deg, p_pos_deg, extinction_ratio = result  # Degrees and extinction ratio
    # Convert back to servo units for display
    s_pos_servo = int(s_pos_deg * 255 / 180)
    p_pos_servo = int(p_pos_deg * 255 / 180)

    logger.info("\n" + "=" * 80)
    logger.info("FINAL RESULTS")
    logger.info("=" * 80)
    logger.info(f"S Position: servo {s_pos_servo} (maximum transmission)")
    logger.info(f"P Position: servo {p_pos_servo} (minimum, strongest SPR absorption)")
    logger.info(
        f"Separation: {abs(s_pos_servo - p_pos_servo)} servo units (circular polarizer)",
    )
    logger.info(
        f"Extinction Ratio: {extinction_ratio:.2f}% (sensor-specific reference)",
    )
    logger.info("\nRefinement stages:")
    logger.info("  Stage 1: Coarse search - 5 positions across 0-255 range")
    logger.info("  Stage 2: ±28 servo units in 14-unit steps")
    logger.info("  Stage 3: ±7 servo units in 7-unit steps")
    logger.info("  Stage 4: ±3 servo units in 3-unit steps")
    logger.info("\nThis converges to the exact maximum/minimum!")
else:
    logger.error("\n❌ Quadrant search failed")

# Cleanup
usb.close()
ctrl.close()
logger.info("\nDone.")
