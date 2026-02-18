"""Test servo calibration only - no LED model training."""

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger
from servo_polarizer_calibration.calibrate_polarizer import run_calibration_with_hardware
import time

print("=" * 80)
print("SERVO CALIBRATION TEST - STANDALONE")
print("=" * 80)

# Initialize hardware manager
logger.info("Initializing hardware manager...")
hm = HardwareManager()

# Scan and connect
logger.info("Scanning for devices...")
hm.scan_and_connect(auto_connect=True)

# Wait for connection
logger.info("Waiting for hardware connection...")
for i in range(30):  # Wait up to 15 seconds
    if hm.ctrl and hm.usb:
        logger.info(f"✓ Hardware connected after {i * 0.5:.1f}s")
        break
    time.sleep(0.5)
else:
    logger.error("✗ Hardware connection timeout!")
    exit(1)

# Verify hardware
logger.info(f"Controller: {hm.ctrl.get_device_type() if hasattr(hm.ctrl, 'get_device_type') else type(hm.ctrl).__name__}")
logger.info(f"Spectrometer: {hm.usb.serial_number if hasattr(hm.usb, 'serial_number') else 'Unknown'}")

# Run servo calibration only
print("\n" + "=" * 80)
logger.info("STARTING SERVO POLARIZER CALIBRATION")
print("=" * 80)

try:
    success = run_calibration_with_hardware(hm)

    print("\n" + "=" * 80)
    if success:
        logger.info("✅ SERVO CALIBRATION COMPLETE")
        print("✅ SERVO CALIBRATION COMPLETE")
        print("Results saved to device profile and device_config.json")
    else:
        logger.error("❌ SERVO CALIBRATION FAILED")
        print("❌ SERVO CALIBRATION FAILED")
    print("=" * 80)
except Exception as e:
    logger.exception("Servo calibration crashed:")
    print(f"❌ ERROR: {e}")
