"""Run standalone OEM calibration (servo + LED model training)."""

from affilabs.core.hardware_manager import HardwareManager
from affilabs.core.oem_model_training import run_oem_model_training_workflow
from affilabs.utils.logger import logger
import time

print("=" * 80)
print("OEM CALIBRATION - STANDALONE")
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

# Run OEM training
print("\n" + "=" * 80)
logger.info("STARTING OEM MODEL TRAINING WORKFLOW")
print("=" * 80)
logger.info("This will:")
logger.info("  1. Run servo polarizer calibration (2-5 min)")
logger.info("  2. Train LED calibration model (~2 min)")
print("=" * 80 + "\n")

success = run_oem_model_training_workflow(hardware_mgr=hm)

print("\n" + "=" * 80)
if success:
    logger.info("✅ OEM CALIBRATION COMPLETE")
    print("✅ OEM CALIBRATION COMPLETE")
else:
    logger.error("❌ OEM CALIBRATION FAILED")
    print("❌ OEM CALIBRATION FAILED")
print("=" * 80)
