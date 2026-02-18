"""Run LED model training only - no servo calibration.

This will train the LED optical model using existing servo positions.
The servo positions must already be configured in device_config.json.
"""

import sys
from affilabs.core.hardware_manager import HardwareManager
from affilabs.core.oem_model_training import run_oem_model_training_workflow
from affilabs.utils.logger import logger

print("=" * 80)
print("LED MODEL TRAINING ONLY")
print("=" * 80)
print()
print("This will train the LED optical model WITHOUT running servo calibration.")
print("Make sure servo positions are already configured in device_config.json")
print()

# Initialize hardware
logger.info("Initializing hardware manager...")
hm = HardwareManager()

# Connect to controller
logger.info("Connecting to controller...")
hm._connect_controller()

if not hm._ctrl_raw:
    print("❌ Failed to connect to controller")
    sys.exit(1)

print(f"✓ Controller connected: {hm._ctrl_raw.name}")

# Connect to detector
logger.info("Connecting to detector...")
from affilabs.utils.detector_factory import create_detector
detector = create_detector(app=None, config={})

if detector is None:
    print("❌ Failed to connect to detector")
    sys.exit(1)

detector_type = type(detector).__name__
print(f"✓ Detector connected: {detector_type}")
if hasattr(detector, 'serial_number'):
    print(f"  Serial: {detector.serial_number}")

# Assign detector to hardware manager
hm.usb = detector

print()
print("=" * 80)
print("STARTING LED MODEL TRAINING")
print("=" * 80)
print()

# Run LED model training workflow
try:
    success = run_oem_model_training_workflow(hardware_mgr=hm)

    if success:
        print()
        print("=" * 80)
        print("✅ LED MODEL TRAINING COMPLETE")
        print("=" * 80)
    else:
        print()
        print("=" * 80)
        print("❌ LED MODEL TRAINING FAILED")
        print("=" * 80)
        sys.exit(1)

except Exception as e:
    print()
    print("=" * 80)
    print(f"❌ ERROR: {e}")
    print("=" * 80)
    logger.error(f"LED model training error: {e}", exc_info=True)
    sys.exit(1)
finally:
    # Cleanup
    print()
    print("Cleaning up...")
    if hm.ctrl:
        hm.ctrl.set_batch_intensities(0, 0, 0, 0)
    print("✓ LEDs turned off")
