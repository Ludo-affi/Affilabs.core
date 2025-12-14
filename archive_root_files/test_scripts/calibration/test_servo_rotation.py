"""
Test if polarizer servo is physically rotating.
This will slowly step through positions with visual confirmation pauses.
"""

import sys
import os
import logging
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("SERVO ROTATION TEST")
logger.info("=" * 80)

# Import required modules
from utils.controller import PicoP4SPR

# Connect controller
logger.info("\nConnecting to controller...")
ctrl = PicoP4SPR()

if not ctrl.open():
    logger.error("[FAIL] Controller connection failed!")
    logger.error("Make sure the main application is closed!")
    sys.exit(1)

logger.info(f"[OK] Controller: {ctrl.version}")
logger.info(f"[OK] Serial port: {ctrl._ser.port if ctrl._ser else 'None'}")

# Test servo movement with visible positions
test_positions = [0, 45, 90, 135, 180, 90, 0]

logger.info("\n" + "=" * 80)
logger.info("SERVO MOVEMENT TEST")
logger.info("=" * 80)
logger.info("\nWatch the polarizer servo for physical movement.")
logger.info("If it doesn't move, there may be a hardware or wiring issue.\n")

for i, angle in enumerate(test_positions):
    logger.info(f"\nStep {i+1}/{len(test_positions)}: Moving to {angle}°...")

    # Send command (both S and P to same value for visual test)
    result = ctrl.servo_set(s=angle, p=angle)

    if result:
        logger.info(f"  ✓ Command sent successfully (servo_set returned True)")
    else:
        logger.warning(f"  ✗ Command failed (servo_set returned False)")

    # Read back the command that was sent
    logger.info(f"  Command format: sv{angle:03d}{angle:03d}")

    # Wait for servo to move and give user time to observe
    time.sleep(2.0)

    input(f"Press Enter after observing position {angle}° (or Ctrl+C to abort)...")

logger.info("\n" + "=" * 80)
logger.info("TEST COMPLETE")
logger.info("=" * 80)
logger.info("\nIf you saw the servo moving between positions:")
logger.info("  → Servo is working correctly, signal variation issue may be optical")
logger.info("\nIf the servo did NOT move:")
logger.info("  → Check servo power supply")
logger.info("  → Check servo signal wire connection")
logger.info("  → Check if servo is mechanically jammed")
logger.info("  → Try moving servo manually to verify it's not stuck")

# Cleanup
ctrl.close()
logger.info("\nDone.")
