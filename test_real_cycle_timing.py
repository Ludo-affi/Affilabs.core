"""Empirical test: Measure ACTUAL detector cycle timing with hardware averaging"""

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

# Timing parameters
LED_ON_TIME_MS = root_settings.LED_ON_TIME_MS
DETECTOR_WAIT_MS = root_settings.DETECTOR_WAIT_MS
SAFETY_BUFFER_MS = root_settings.SAFETY_BUFFER_MS
DETECTOR_WINDOW_MS = LED_ON_TIME_MS - DETECTOR_WAIT_MS - SAFETY_BUFFER_MS

print("="*80)
print("EMPIRICAL DETECTOR CYCLE TIMING TEST")
print("="*80)
print()
print(f"Device: ST00014")
print(f"Integration time: {integration_ms:.3f}ms (from device config)")
print(f"Detector window:  {DETECTOR_WINDOW_MS}ms")
print()

# Connect to detector
detector = PhasePhotonics()
if not detector.open():
    print("ERROR: Failed to connect")
    sys.exit(1)

print(f"Connected: {detector.serial_number}")
print()

# Set the actual integration time
detector.set_integration(integration_ms / 1000.0)  # API expects seconds
print(f"Integration time set to: {detector._integration_time * 1000:.3f}ms")
print()

# Test 5, 10, 15 scans
test_scans = [5, 10, 15]

print("EMPIRICAL MEASUREMENTS (10 iterations each):")
print(f"{'Scans':<8} {'Mean Time':<12} {'Std Dev':<12} {'Min':<10} {'Max':<10} {'Fits?':<8}")
print("-"*70)

results = []
for num_scans in test_scans:
    # Set hardware averaging
    detector.set_averaging(num_scans)
    time.sleep(0.1)  # Let setting stabilize
    
    # Warm-up read
    detector.read_intensity()
    
    # Measure 10 times
    times_ms = []
    for _ in range(10):
        start = time.perf_counter()
        spectrum = detector.read_intensity()
        elapsed_ms = (time.perf_counter() - start) * 1000
        times_ms.append(elapsed_ms)
    
    # Statistics
    mean_ms = np.mean(times_ms)
    std_ms = np.std(times_ms)
    min_ms = np.min(times_ms)
    max_ms = np.max(times_ms)
    fits = "YES" if mean_ms <= DETECTOR_WINDOW_MS else "NO"
    
    print(f"{num_scans:<8} {mean_ms:>8.2f}ms    {std_ms:>8.2f}ms    {min_ms:>6.2f}ms   {max_ms:>6.2f}ms   {fits:<8}")
    
    results.append({
        'scans': num_scans,
        'mean': mean_ms,
        'std': std_ms,
        'min': min_ms,
        'max': max_ms
    })

# Reset
detector.set_averaging(1)
detector.close()

print()
print("="*80)
print("ANALYSIS")
print("="*80)
print()

for r in results:
    margin_ms = DETECTOR_WINDOW_MS - r['mean']
    margin_pct = (margin_ms / DETECTOR_WINDOW_MS) * 100
    snr_gain = np.sqrt(r['scans'])
    
    print(f"{r['scans']} scans:")
    print(f"  Actual time:    {r['mean']:.2f}ms +/- {r['std']:.2f}ms")
    print(f"  Window budget:  {DETECTOR_WINDOW_MS}ms")
    print(f"  Margin:         {margin_ms:.2f}ms ({margin_pct:.1f}%)")
    print(f"  SNR gain:       {snr_gain:.2f}x")
    print()

# Verify hardware averaging efficiency
print("HARDWARE AVERAGING EFFICIENCY:")
single_scan_time = results[0]['mean'] / results[0]['scans']  # Estimate
for r in results:
    software_time = single_scan_time * r['scans']
    hardware_time = r['mean']
    speedup = software_time / hardware_time
    print(f"{r['scans']} scans: {hardware_time:.1f}ms (vs {software_time:.1f}ms software) = {speedup:.2f}x faster")

print()
print("="*80)
