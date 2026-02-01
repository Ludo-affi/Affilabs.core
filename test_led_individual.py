"""Test individual LED commands (la:X, lb:X, lc:X, ld:X)

Tests if individual LED intensity commands work with P4PRO+ firmware.
This is critical for OEM model training which sets one LED at a time.
"""
import time
from affilabs.core.hardware_manager import HardwareManager
import numpy as np

print("=" * 70)
print("INDIVIDUAL LED COMMAND TEST")
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
print("[OK] Detector: Connected")

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

# Test individual LED commands (like OEM training does)
print("\n" + "=" * 70)
print("TEST: Individual LED intensity commands")
print("=" * 70)
print("Pattern: Turn on LED A only at intensity 50")
print("Commands: la:50, lb:0, lc:0, ld:0")

# Turn on LED A only
print("\nSetting LED A=50...")
ctrl.set_intensity(ch='a', raw_val=50)
time.sleep(0.01)
print("Setting LED B=0...")
ctrl.set_intensity(ch='b', raw_val=0)
time.sleep(0.01)
print("Setting LED C=0...")
ctrl.set_intensity(ch='c', raw_val=0)
time.sleep(0.01)
print("Setting LED D=0...")
ctrl.set_intensity(ch='d', raw_val=0)
time.sleep(0.5)

# Measure signal
scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_a = float(spectrum.max())
print(f"\nSignal with LED A ON (50): {signal_a:.0f} counts")

# Turn off all LEDs
print("\n" + "=" * 70)
print("Turning off all LEDs...")
ctrl.set_intensity(ch='a', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='b', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='c', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='d', raw_val=0)
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_off = float(spectrum.max())
print(f"Signal with all LEDs OFF: {signal_off:.0f} counts")

# Test LED D (since it worked in your OEM training)
print("\n" + "=" * 70)
print("Testing LED D (this one worked in OEM training)")
print("=" * 70)
print("Setting LED D=50, others=0")

ctrl.set_intensity(ch='a', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='b', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='c', raw_val=0)
time.sleep(0.01)
ctrl.set_intensity(ch='d', raw_val=50)
time.sleep(0.5)

scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_d = float(spectrum.max())
print(f"Signal with LED D ON (50): {signal_d:.0f} counts")

# Summary
print("\n" + "=" * 70)
print("TEST RESULTS")
print("=" * 70)
print(f"LED A (individual cmd): {signal_a:>8.0f} counts")
print(f"LED D (individual cmd): {signal_d:>8.0f} counts")
print(f"All OFF:                {signal_off:>8.0f} counts")

if signal_a > 10000:
    print("\n[OK] LED A works with individual commands")
else:
    print("\n[X] FAIL: LED A did NOT turn on with individual commands")
    print("    This explains why OEM training shows ~30 counts for A/B/C")

if signal_d > 10000:
    print("[OK] LED D works with individual commands")
else:
    print("[X] FAIL: LED D did NOT turn on")

# Cleanup
hw.disconnect_all()
print("\n[OK] Test complete, hardware disconnected")
