"""FIXED: Empirical test with VERIFIED integration time setting"""

import time
import sys
import numpy as np
import json

sys.path.insert(0, r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\test\ezControl-AI")

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
import settings as root_settings

# Get actual device integration time from config
with open('affilabs/config/devices/ST00014/device_config.json', 'r') as f:
    config = json.load(f)
    integration_ms = config['calibration']['integration_time_ms']

DETECTOR_WINDOW_MS = root_settings.LED_ON_TIME_MS - root_settings.DETECTOR_WAIT_MS - root_settings.SAFETY_BUFFER_MS

print("="*80)
print("EMPIRICAL DETECTOR CYCLE TIMING TEST (FIXED)")
print("="*80)
print()
print(f"Target integration time: {integration_ms:.3f}ms")
print(f"Detector window:         {DETECTOR_WINDOW_MS}ms")
print()

detector = PhasePhotonics()
if not detector.open():
    print("ERROR: Failed to connect")
    sys.exit(1)

print(f"Connected: {detector.serial_number}")

# PROPERLY set integration time (API expects SECONDS)
integration_seconds = integration_ms / 1000.0
success = detector.set_integration(integration_seconds)
print(f"set_integration({integration_seconds:.6f}s) returned: {success}")

# VERIFY it was set correctly
actual_integration_ms = detector._integration_time * 1000
print(f"Verified integration time: {actual_integration_ms:.3f}ms")
print()

if abs(actual_integration_ms - integration_ms) > 0.1:
    print(f"WARNING: Integration time mismatch!")
    print(f"  Requested: {integration_ms:.3f}ms")
    print(f"  Actual:    {actual_integration_ms:.3f}ms")
    print()

test_scans = [5, 10, 15]

print("MEASUREMENTS:")
print(f"{'Scans':<8} {'Mean':<12} {'Std':<10} {'Expected':<12} {'Fits?':<8}")
print("-"*60)

for num_scans in test_scans:
    detector.set_averaging(num_scans)
    time.sleep(0.1)
    
    detector.read_intensity()  # Warm-up
    
    times_ms = []
    for _ in range(10):
        start = time.perf_counter()
        spectrum = detector.read_intensity()
        elapsed_ms = (time.perf_counter() - start) * 1000
        times_ms.append(elapsed_ms)
    
    mean_ms = np.mean(times_ms)
    std_ms = np.std(times_ms)
    
    # Expected: (num_scans × integration_time) + USB_overhead (~8ms)
    expected_ms = (num_scans * actual_integration_ms) + 8.0
    
    fits = "YES" if mean_ms <= DETECTOR_WINDOW_MS else "NO"
    
    print(f"{num_scans:<8} {mean_ms:>8.2f}ms   {std_ms:>6.2f}ms   {expected_ms:>8.2f}ms     {fits:<8}")

detector.set_averaging(1)
detector.close()
print()
