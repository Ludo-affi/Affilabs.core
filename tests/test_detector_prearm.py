"""Test detector pre-arm integration time setting.

This diagnostic script validates why pre-arm is failing during live acquisition.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("DETECTOR PRE-ARM DIAGNOSTIC TEST")
print("=" * 80)

# Initialize detector
print("\n1. Connecting to USB4000 detector...")
from affilabs.utils.usb4000_wrapper import USB4000

detector = USB4000()
if not detector.open():
    print("❌ Failed to connect to detector!")
    sys.exit(1)

print(f"✅ Detector connected: {detector.serial_number}")
print(f"   Pixels: {detector.num_pixels}")
print(f"   Max integration: {detector.max_integration_time_ms}ms")
print(f"   Min integration: {detector.min_integration_time_ms}ms")

# Test set_integration with different values
test_times = [10.0, 30.0, 60.0, 63.5, 70.0, 100.0]

print("\n2. Testing set_integration() return values:")
print("-" * 80)

for time_ms in test_times:
    result = detector.set_integration(time_ms)
    print(f"   set_integration({time_ms:.1f}ms) → {result} (type: {type(result).__name__})")

    # Verify it was actually set
    time.sleep(0.05)

print("\n3. Testing actual spectrum acquisition:")
print("-" * 80)

for time_ms in [30.0, 60.0, 70.0]:
    result = detector.set_integration(time_ms)
    print(f"\n   Integration: {time_ms:.1f}ms, set_integration() returned: {result}")

    # Try to read spectrum
    time.sleep(0.1)
    try:
        spectrum = detector.read_spectrum()
        if spectrum is not None and len(spectrum) > 0:
            print(f"   ✅ Spectrum acquired: {len(spectrum)} pixels, max={spectrum.max():.0f}")
        else:
            print("   ❌ Empty spectrum returned")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

print("\n4. Testing HAL adapter (if used in acquisition):")
print("-" * 80)

from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

hal = OceanSpectrometerAdapter(detector)
print(f"   HAL adapter created: {hal}")

for time_ms in [30.0, 60.0]:
    result = hal.set_integration(time_ms)
    print(f"\n   HAL.set_integration({time_ms:.1f}ms) → {result} (type: {type(result).__name__})")

    time.sleep(0.1)
    try:
        spectrum = hal.read_spectrum()
        if spectrum is not None and len(spectrum) > 0:
            print(f"   ✅ HAL spectrum acquired: {len(spectrum)} pixels, max={spectrum.max():.0f}")
        else:
            print("   ❌ HAL returned empty spectrum")
    except Exception as e:
        print(f"   ❌ HAL exception: {e}")

print("\n5. Testing read_roi (used in batch acquisition):")
print("-" * 80)

wave_min_idx = 100
wave_max_idx = 2000

hal.set_integration(60.0)
time.sleep(0.1)

try:
    roi_spectrum = hal.read_roi(wave_min_idx, wave_max_idx, num_scans=3)
    if roi_spectrum is not None and len(roi_spectrum) > 0:
        print(f"   ✅ ROI acquired: {len(roi_spectrum)} pixels, max={roi_spectrum.max():.0f}")
    else:
        print(f"   ❌ ROI returned empty: {roi_spectrum}")
except Exception as e:
    print(f"   ❌ ROI exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC TEST COMPLETE")
print("=" * 80)

# Cleanup
detector.close()
