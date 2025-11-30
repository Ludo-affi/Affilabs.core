"""
Test servo with EEPROM flash - positions might need to be saved to firmware first.
"""

import sys
import os
import logging
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s :: %(levelname)s :: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("SERVO FLASH TEST")
logger.info("=" * 80)

# Import required modules
from utils.controller import PicoP4SPR

# Connect controller
logger.info("\nConnecting to controller...")
ctrl = PicoP4SPR()

if not ctrl.open():
    logger.error("[FAIL] Controller connection failed!")
    sys.exit(1)

logger.info(f"[OK] Controller: {ctrl.version}")

# Test 1: Set positions and flash to EEPROM
logger.info("\n" + "=" * 80)
logger.info("TEST 1: Set positions to EEPROM")
logger.info("=" * 80)

# Set S=45°, P=135° (90° apart for clear visual difference)
logger.info("\nSetting servo positions: S=45°, P=135°")
result = ctrl.servo_set(s=45, p=135)
logger.info(f"  servo_set result: {result}")

time.sleep(0.2)

# Flash to EEPROM
logger.info("\nFlashing to EEPROM (sf command)...")
flash_result = ctrl.flash()
logger.info(f"  flash result: {flash_result}")

if not flash_result:
    logger.error("  ❌ EEPROM flash failed!")
else:
    logger.info("  ✅ EEPROM flash succeeded")

time.sleep(0.5)

# Test 2: Try using mode commands (ss/sp) which read from EEPROM
logger.info("\n" + "=" * 80)
logger.info("TEST 2: Use mode commands (ss/sp)")
logger.info("=" * 80)

logger.info("\nMoving to S mode (ss command)...")
result = ctrl.set_mode('s')
logger.info(f"  set_mode('s') result: {result}")
input("Press Enter after observing S position (should be 45°)...")

logger.info("\nMoving to P mode (sp command)...")
result = ctrl.set_mode('p')
logger.info(f"  set_mode('p') result: {result}")
input("Press Enter after observing P position (should be 135°)...")

logger.info("\nMoving to S mode again...")
result = ctrl.set_mode('s')
logger.info(f"  set_mode('s') result: {result}")
input("Press Enter after observing S position (should be 45°)...")

# Test 3: Read back positions
logger.info("\n" + "=" * 80)
logger.info("TEST 3: Read servo positions")
logger.info("=" * 80)

positions = ctrl.servo_get()
logger.info(f"  Current positions: S={positions['s'].decode()}, P={positions['p'].decode()}")

logger.info("\n" + "=" * 80)
logger.info("DIAGNOSIS")
logger.info("=" * 80)
logger.info("\nIf servo moved with ss/sp commands:")
logger.info("  → Servo works! Use set_mode() instead of servo_set()")
logger.info("  → Positions must be flashed to EEPROM first")
logger.info("\nIf servo still didn't move:")
logger.info("  → Hardware issue: check power, wiring, or servo itself")
logger.info("  → Firmware issue: verify 'ss'/'sp' commands are implemented")

# Cleanup
ctrl.close()
logger.info("\nDone.")
