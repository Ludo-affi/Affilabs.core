"""Test script to run OEM model training workflow."""

from affilabs.core.hardware_manager import HardwareManager
from affilabs.core.oem_model_training import run_oem_model_training_workflow
import time

print("=" * 80)
print("OEM MODEL TRAINING TEST")
print("=" * 80)

# Initialize hardware manager
print("\nInitializing hardware...")
hm = HardwareManager()

# Scan and connect
print("Scanning for devices...")
hm.scan_and_connect(auto_connect=True)

# Wait for connection to complete
print("Waiting for hardware connection...")
for i in range(30):  # Wait up to 15 seconds
    if hm.ctrl and hm.usb:
        print(f"✓ Hardware connected after {i * 0.5:.1f}s")
        break
    time.sleep(0.5)
else:
    print("✗ Hardware connection timeout!")
    exit(1)

# Verify hardware
print(f"\nController: {hm.ctrl.get_device_type() if hasattr(hm.ctrl, 'get_device_type') else type(hm.ctrl).__name__}")
print(f"Spectrometer: {hm.usb.serial_number if hasattr(hm.usb, 'serial_number') else 'Unknown'}")

# Run OEM training
print("\n" + "=" * 80)
print("STARTING OEM MODEL TRAINING WORKFLOW")
print("=" * 80)
print("This will:")
print("  1. Run servo polarizer calibration (2-5 min)")
print("  2. Train LED calibration model (~2 min)")
print("=" * 80 + "\n")

success = run_oem_model_training_workflow(hardware_mgr=hm)

print("\n" + "=" * 80)
if success:
    print("✅ OEM MODEL TRAINING COMPLETE")
else:
    print("❌ OEM MODEL TRAINING FAILED")
print("=" * 80)
