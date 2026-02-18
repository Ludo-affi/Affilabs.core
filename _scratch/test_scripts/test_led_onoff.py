"""Test LED on/off control for P4PRO controller

Validates that LEDs can be turned on and off properly before OEM calibration.
This tests the critical leds:A:X,B:X,C:X,D:X command.
"""
import time
from affilabs.core.hardware_manager import HardwareManager

print("=" * 70)
print("LED ON/OFF CONTROL TEST")
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

# Test 1: Turn ON all LEDs
print("\n" + "=" * 70)
print("TEST 1: TURN ON ALL LEDs (intensity=50)")
print("=" * 70)
print("Sending command: leds:A:50,B:50,C:50,D:50")

success = ctrl.set_batch_intensities(a=50, b=50, c=50, d=50)
print(f"Command returned: {success}")
time.sleep(0.5)

# Measure signal
scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
import numpy as np
spectrum = np.mean(scans, axis=0)
signal_on = float(spectrum.max())
print(f"Signal with LEDs ON: {signal_on:.0f} counts")

if signal_on < 1000:
    print("[X] FAIL: Signal too low - LEDs may not have turned on!")
    print("    Expected: >10,000 counts")
    print("    Got: {:.0f} counts".format(signal_on))
else:
    print("[OK] PASS: LEDs are ON")

# Test 2: Turn OFF all LEDs
print("\n" + "=" * 70)
print("TEST 2: TURN OFF ALL LEDs (intensity=0)")
print("=" * 70)
print("Sending command: leds:A:0,B:0,C:0,D:0")

success = ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
print(f"Command returned: {success}")
time.sleep(0.5)

# Measure signal
scans = []
for i in range(3):
    scans.append(detector.read_intensity())
    time.sleep(0.1)
spectrum = np.mean(scans, axis=0)
signal_off = float(spectrum.max())
print(f"Signal with LEDs OFF: {signal_off:.0f} counts")

if signal_off > 10000:
    print("[X] FAIL: Signal too high - LEDs are still ON!")
    print("    Expected: ~3000 counts (typical Ocean Optics dark signal)")
    print("    Got: {:.0f} counts".format(signal_off))
    print("\n    DIAGNOSIS: The leds:A:0,B:0,C:0,D:0 command did not work")
    print("    Firmware may not support this command")
elif signal_off > 6000:
    print("[WARNING] Signal higher than expected but LEDs may be off")
    print("    Expected: ~3000 counts (Ocean Optics dark)")
    print("    Got: {:.0f} counts".format(signal_off))
    print("    This may indicate residual LED light or background")
else:
    print("[OK] PASS: LEDs are OFF")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Signal ON:  {signal_on:>8.0f} counts")
print(f"Signal OFF: {signal_off:>8.0f} counts")
print(f"Ratio:      {signal_on/signal_off:>8.1f}x")
print("")

if signal_on > 10000 and signal_off < 10000:
    print("[OK] ALL TESTS PASSED")
    print("LED control is working correctly - OEM calibration can proceed")
elif signal_off > 10000:
    print("[X] TEST FAILED")
    print("LEDs cannot be turned off - OEM calibration will fail")
    print("\nPossible fixes:")
    print("  1. Check firmware version (need v2.1+)")
    print("  2. Try power cycling the controller")
    print("  3. Check if lx command works instead")
else:
    print("[WARNING] PARTIAL PASS")
    print("LEDs may not be working optimally")

print("=" * 70)

# Cleanup
hw.disconnect_all()
