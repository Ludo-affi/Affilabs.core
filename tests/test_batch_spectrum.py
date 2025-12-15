"""Test if USB4000 supports batch spectrum acquisition."""

import seabreeze

seabreeze.use("cseabreeze")

import time

import numpy as np
from seabreeze.spectrometers import Spectrometer, list_devices

# Connect to spectrometer
devices = list_devices()
if not devices:
    print("No spectrometer found!")
    exit(1)

spec = Spectrometer(devices[0])
print(f"Connected to: {spec.model} ({spec.serial_number})")

# Check available features
print("\n=== Available Features ===")
for name, feature in spec.features.items():
    print(f"  {name}: {type(feature).__name__}")

# Check for buffering or batch capabilities
print("\n=== Checking for Batch/Buffer Features ===")
feature_names = list(spec.features.keys())
batch_related = [
    f
    for f in feature_names
    if any(
        keyword in f.lower()
        for keyword in ["buffer", "batch", "acquisition", "continuous", "fast"]
    )
]
if batch_related:
    print("Found potentially relevant features:")
    for f in batch_related:
        print(f"  - {f}")
else:
    print("No obvious batch/buffer features found in standard API")

# Test: Can we trigger multiple integrations without reading?
print("\n=== Testing Sequential Reads ===")
spec.integration_time_micros(1000)  # 1ms
time.sleep(0.1)

# Method 1: Read spectra one at a time (current approach)
print("\nMethod 1: Individual reads (current)")
times = []
for i in range(5):
    t_start = time.perf_counter()
    data = spec.intensities()
    t_end = time.perf_counter()
    times.append((t_end - t_start) * 1000)
    print(f"  Read {i+1}: {times[-1]:.2f}ms")

print(
    f"Average: {np.mean(times):.2f}ms, Overhead per read: ~{np.mean(times) - 1:.2f}ms",
)

# Check if there's a spectrum acquisition mode
print("\n=== Checking Acquisition Modes ===")
if hasattr(spec, "trigger_mode"):
    print(f"Trigger mode available: {spec.trigger_mode}")
    # Try to access trigger mode values
    try:
        print(f"Available trigger modes: {dir(spec.trigger_mode)}")
    except Exception as e:
        print(f"Could not enumerate trigger modes: {e}")
else:
    print("No trigger_mode attribute")

# Check low-level features
print("\n=== Low-Level Feature Access ===")
if "spectrum_processing" in spec.features:
    print("Spectrum processing feature available")
    sp_feature = spec.features["spectrum_processing"]
    print(f"  Methods: {[m for m in dir(sp_feature) if not m.startswith('_')]}")

if "acquisition_delay" in spec.features:
    print("Acquisition delay feature available")

# Close connection
spec.close()
print("\n=== Test Complete ===")
