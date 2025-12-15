"""Quick polarizer calibration test with channel B only.
Skips water validation to find positions regardless of signal quality.
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
logger.info("QUICK POLARIZER POSITION FINDER (Channel B)")
logger.info("=" * 80)

# Import required modules
import time

from utils.controller import PicoP4SPR
from utils.detector_factory import create_detector

# Connect hardware
logger.info("\nConnecting to hardware...")
config = {"detector_type": "USB4000"}
usb = create_detector(None, config)
ctrl = PicoP4SPR()

if not ctrl.open():
    logger.error("[FAIL] Controller connection failed!")
    logger.error("Make sure the main application is closed!")
    sys.exit(1)

logger.info(f"[OK] Spectrometer: {usb.serial_number}")
logger.info(f"[OK] Controller: {ctrl.version}")
logger.info(f"[OK] Serial port: {ctrl._ser.port if ctrl._ser else 'None'}")

# Setup - use only channel B with low intensity
logger.info("\nSetup: Using channel B with intensity 64")

# Use controller methods
ctrl.set_intensity("b", 64)
time.sleep(0.2)

usb.set_integration(50)  # 50ms integration
time.sleep(0.1)

logger.info("\nScanning servo positions (5-point search)...")
positions = [10, 50, 90, 130, 170]
measurements = {}

for angle in positions:
    # CRITICAL: Must flash position to EEPROM and use mode commands to move servo!
    # Step 1: Set position in EEPROM (both S and P to same value)
    ctrl.servo_set(s=angle, p=angle)
    time.sleep(0.1)

    # Step 2: Flash to EEPROM
    ctrl.flash()
    time.sleep(0.1)

    # Step 3: Move to position using mode command (use 's' mode)
    ctrl.set_mode("s")
    time.sleep(0.5)  # Wait for servo to physically move

    spectrum = usb.read_intensity()
    if spectrum is not None:
        max_signal = float(spectrum.max())
        measurements[angle] = max_signal
        logger.info(f"  {angle:3d}°: {max_signal:6.0f} counts")
    else:
        logger.warning(f"  {angle:3d}°: No data")

# Find P position (minimum)
p_pos = min(measurements, key=measurements.get)
p_signal = measurements[p_pos]

# Find S position (maximum - should be 90° from P)
s_pos = max(measurements, key=measurements.get)
s_signal = measurements[s_pos]

# Calculate 90° relationship
theoretical_s = (p_pos + 90) % 180
separation = abs(s_pos - p_pos)

logger.info("\n" + "=" * 80)
logger.info("RESULTS")
logger.info("=" * 80)
logger.info(f"P Position (minimum): {p_pos}° ({p_signal:.0f} counts)")
logger.info(f"S Position (maximum): {s_pos}° ({s_signal:.0f} counts)")
logger.info(f"Separation: {separation}°")
logger.info(f"S/P Ratio: {s_signal/p_signal:.2f}x")

if abs(separation - 90) < 20:
    logger.info("\n[OK] Positions are approximately 90° apart")
    logger.info("\nRecommended positions:")
    logger.info(f"  S = {s_pos}°")
    logger.info(f"  P = {p_pos}°")
else:
    logger.warning(f"\n[WARNING] Separation is {separation}°, expected ~90°")
    logger.info("\nUsing theoretical 90° relationship:")
    logger.info(f"  P = {p_pos}°")
    logger.info(f"  S = {theoretical_s}° (P + 90°)")

logger.info("\n" + "=" * 80)
logger.info("To save: Update device_config.json with these values")
logger.info("=" * 80)

# Cleanup
usb.close()
ctrl.close()
logger.info("\nDone.")
