"""Test the EXACT path used by OEM calibration: hardware_mgr → HAL → controller."""
import sys
import time

# Import hardware manager setup
from affilabs.core.hardware_manager import HardwareManager
from affilabs.config.device_config import DeviceConfiguration

print("="*70)
print("TESTING EXACT OEM CALIBRATION PATH")
print("="*70)

# Create device config
device_config = DeviceConfiguration()

# Create hardware manager
print("\n1. Creating hardware manager...")
hardware_mgr = HardwareManager(device_config=device_config)

# Initialize hardware
print("2. Initializing hardware (COM3 P4PRO + USB detector)...")
success = hardware_mgr.initialize()
if not success:
    print("❌ Hardware initialization failed!")
    sys.exit(1)

print(f"   Controller type: {type(hardware_mgr.ctrl).__name__}")
print(f"   Detector: {hardware_mgr.usb.serial_number if hardware_mgr.usb else 'None'}")

# Get ctrl (HAL adapter) - same as calibration code
ctrl = hardware_mgr.ctrl
usb = hardware_mgr.usb

if not ctrl or not usb:
    print("❌ Hardware not connected!")
    sys.exit(1)

print("\n3. Testing LED enable path...")
print("-" * 70)

# Turn off first
print("Turning OFF LEDs (baseline)...")
ctrl.turn_off_channels()
time.sleep(0.1)

input("Check detector (should be ~3090). Press Enter...")

# Test enable_multi_led() - SAME AS CALIBRATION
print("\n4. Calling ctrl.enable_multi_led() (through HAL)...")
if hasattr(ctrl, 'enable_multi_led'):
    result = ctrl.enable_multi_led(a=True, b=True, c=True, d=True)
    print(f"   enable_multi_led() returned: {result}")
else:
    print(f"   ❌ NO enable_multi_led() method on {type(ctrl).__name__}!")

time.sleep(0.2)

# Test set_batch_intensities() - SAME AS CALIBRATION
print("\n5. Calling ctrl.set_batch_intensities(51, 51, 51, 51) (through HAL)...")
led_intensity = 51  # 20%
result = ctrl.set_batch_intensities(a=led_intensity, b=led_intensity, c=led_intensity, d=led_intensity)
print(f"   set_batch_intensities() returned: {result}")

time.sleep(0.2)

print("\n6. Setting integration time to 5ms...")
usb.set_integration(5.0)
time.sleep(0.5)

print("\n7. Reading detector signal...")
for i in range(5):
    spectrum = usb.read_intensity()
    signal = float(spectrum.mean())
    max_signal = float(spectrum.max())
    print(f"   Reading {i+1}: mean={signal:.1f}, max={max_signal:.1f}")
    time.sleep(0.2)

print("\n" + "="*70)
print("EXPECTED: Signal should be >5000 counts if LEDs are ON")
print("If signal is ~3090, LEDs are NOT turning on despite commands succeeding")
print("="*70)

# Cleanup
print("\n8. Cleanup - turning off LEDs...")
ctrl.turn_off_channels()
time.sleep(0.1)

print("\nTest complete!")
