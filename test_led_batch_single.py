"""Test batch command with single LED on (mimics OEM training pattern)

Tests if set_batch_intensities(a=50, b=0, c=0, d=0) properly turns on
only LED A and keeps others off. This is the pattern OEM training needs.
"""
import time
from affilabs.core.hardware_manager import HardwareManager
import numpy as np

print("=" * 70)
print("BATCH COMMAND - SINGLE LED TEST (OEM Training Pattern)")
print("=" * 70)

# Connect to hardware
print("\n1. Connecting to hardware...")
hw = HardwareManager()
hw._connect_controller()
hw._connect_spectrometer()

if not hw._ctrl_raw or not hw.usb:
    print("[X] Hardware not connected!")
    exit(1)

print(f"[OK] Controller: {hw._ctrl_raw.name}")
print(f"[OK] Detector: Connected")

# Get HAL controller
ctrl = hw.ctrl
detector = hw.usb

# Set integration time
print("\n2. Setting integration time to 20ms...")
detector.set_integration(20.0)
time.sleep(0.2)

# Enable LEDs first (required for P4PRO+)
print("\n3. Enabling LEDs with lm:ABCD command...")
success = ctrl.enable_multi_led(['a', 'b', 'c', 'd'])
print(f"Enable command returned: {success}")
time.sleep(0.1)

# Test batch command with LED A only
print("\n" + "=" * 70)
print("TEST 1: Batch command - LED A=50, others=0")
print("=" * 70)
print("Command: set_batch_intensities(a=50, b=0, c=0, d=0)")

success = ctrl.set_batch_intensities(a=50, b=0, c=0, d=0)
print(f"Command returned: {success}")
time.sleep(0.5)

# Measure signal
scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_a = float(spectrum.max())
print(f"Signal with LED A=50: {signal_a:.0f} counts")

# Test batch command with LED B only
print("\n" + "=" * 70)
print("TEST 2: Batch command - LED B=50, others=0")
print("=" * 70)
print("Command: set_batch_intensities(a=0, b=50, c=0, d=0)")

success = ctrl.set_batch_intensities(a=0, b=50, c=0, d=0)
print(f"Command returned: {success}")
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_b = float(spectrum.max())
print(f"Signal with LED B=50: {signal_b:.0f} counts")

# Test batch command with LED C only
print("\n" + "=" * 70)
print("TEST 3: Batch command - LED C=50, others=0")
print("=" * 70)
print("Command: set_batch_intensities(a=0, b=0, c=50, d=0)")

success = ctrl.set_batch_intensities(a=0, b=0, c=50, d=0)
print(f"Command returned: {success}")
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_c = float(spectrum.max())
print(f"Signal with LED C=50: {signal_c:.0f} counts")

# Test batch command with LED D only
print("\n" + "=" * 70)
print("TEST 4: Batch command - LED D=50, others=0")
print("=" * 70)
print("Command: set_batch_intensities(a=0, b=0, c=0, d=50)")

success = ctrl.set_batch_intensities(a=0, b=0, c=0, d=50)
print(f"Command returned: {success}")
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_d = float(spectrum.max())
print(f"Signal with LED D=50: {signal_d:.0f} counts")

# Turn off all LEDs
print("\n" + "=" * 70)
print("TEST 5: Turn off all LEDs")
print("=" * 70)
print("Command: set_batch_intensities(a=0, b=0, c=0, d=0)")

success = ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
print(f"Command returned: {success}")
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_off = float(spectrum.max())
print(f"Signal with all LEDs OFF: {signal_off:.0f} counts")

# Summary
print("\n" + "=" * 70)
print("TEST RESULTS")
print("=" * 70)
print(f"LED A only: {signal_a:>8.0f} counts")
print(f"LED B only: {signal_b:>8.0f} counts")
print(f"LED C only: {signal_c:>8.0f} counts")
print(f"LED D only: {signal_d:>8.0f} counts")
print(f"All OFF:    {signal_off:>8.0f} counts")

# Check if each LED works individually
all_pass = True
for name, signal in [('A', signal_a), ('B', signal_b), ('C', signal_c), ('D', signal_d)]:
    if signal > 10000:
        print(f"\n[OK] LED {name} works individually")
    else:
        print(f"\n[X] FAIL: LED {name} did NOT turn on (only {signal:.0f} counts)")
        all_pass = False

if signal_off < 10000:
    print("[OK] All LEDs turn off properly")
else:
    print(f"[X] FAIL: LEDs did not turn off ({signal_off:.0f} counts)")
    all_pass = False

if all_pass:
    print("\n" + "=" * 70)
    print("[OK] ALL TESTS PASSED - OEM training can use batch commands")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print("[X] SOME TESTS FAILED - Need to investigate LED control")
    print("=" * 70)

# Cleanup
hw.disconnect_all()
print("\n[OK] Test complete, hardware disconnected")
