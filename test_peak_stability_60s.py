"""
Test peak position stability over 60 seconds.

Measures peak-to-peak position variation for each channel to validate
timing optimization doesn't introduce spectral drift or jitter.

Target: Peak position stability <0.1nm (< 1 pixel drift)
"""

import sys
import time
import json
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000
from settings import (
    PRE_LED_DELAY_MS,
    POST_LED_DELAY_MS,
    LED_OVERLAP_MS,
)


def find_peak_wavelength(spectrum, wavelengths):
    """Find peak wavelength in spectrum.

    Args:
        spectrum: Intensity array
        wavelengths: Wavelength array

    Returns:
        Peak wavelength in nm
    """
    if spectrum is None or len(spectrum) == 0:
        return None

    # Find peak pixel
    peak_idx = np.argmax(spectrum)

    # Use 3-point parabolic interpolation for sub-pixel precision
    if peak_idx > 0 and peak_idx < len(spectrum) - 1:
        y0 = spectrum[peak_idx - 1]
        y1 = spectrum[peak_idx]
        y2 = spectrum[peak_idx + 1]

        # Parabolic interpolation
        denom = 2 * (2*y1 - y0 - y2)
        if abs(denom) > 1e-10:
            offset = (y2 - y0) / denom
            peak_idx_interp = peak_idx + offset
        else:
            peak_idx_interp = peak_idx
    else:
        peak_idx_interp = peak_idx

    # Convert to wavelength
    peak_wavelength = wavelengths[int(peak_idx)]

    return peak_wavelength


def test_peak_stability():
    """Test peak position stability over 60 seconds."""

    print("=" * 80)
    print("PEAK POSITION STABILITY TEST - 60 Second Monitoring")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  PRE delay: {PRE_LED_DELAY_MS}ms")
    print(f"  POST delay: {POST_LED_DELAY_MS}ms")
    print(f"  LED overlap: {LED_OVERLAP_MS}ms")
    print(f"  Duration: 60 seconds")
    print(f"  Target: Peak position drift <0.1nm")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Initializing controller...")
    ctrl = PicoP4SPR()

    try:
        ctrl.open()
        print(f"✅ Connected to controller")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False

    print("Initializing detector...")
    detector = USB4000(parent=None)
    try:
        detector.open()
        print(f"✅ Connected to detector")
    except Exception as e:
        print(f"❌ Failed to connect to detector: {e}")
        ctrl.close()
        return False

    print()

    # Get wavelength array
    wavelengths = detector.get_wavelengths()
    if wavelengths is None:
        print("❌ Failed to get wavelength calibration")
        detector.close()
        ctrl.close()
        return False

    print(f"Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
    print()

    # Storage for peak positions
    channels = ['a', 'b', 'c', 'd']
    peak_data = {ch: [] for ch in channels}
    timestamps = []

    # Run for 60 seconds
    print("Starting 60-second acquisition...")
    print("=" * 80)
    print()

    start_time = time.time()
    cycle_count = 0

    while time.time() - start_time < 60:
        cycle_start = time.time()
        cycle_count += 1
        elapsed = cycle_start - start_time

        print(f"Cycle {cycle_count} ({elapsed:.1f}s elapsed)")

        # Acquire all channels
        for idx, ch in enumerate(channels):
            try:
                # Turn ON LED
                led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                led_values[ch] = 255
                ctrl.set_batch_intensities(**led_values)

                # PRE delay (skip for overlap channels)
                if idx > 0:
                    pass  # LED already ON from overlap
                else:
                    time.sleep(PRE_LED_DELAY_MS / 1000.0)

                # Acquire spectrum
                spectrum = detector.read_intensity()

                # Turn OFF LED
                ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

                # Find peak
                if spectrum is not None and len(spectrum) > 0:
                    peak_wl = find_peak_wavelength(spectrum, wavelengths)
                    peak_data[ch].append(peak_wl)
                    print(f"  Ch {ch}: Peak at {peak_wl:.3f} nm")
                else:
                    print(f"  ❌ Ch {ch}: No spectrum")

                # POST delay with overlap
                if idx < len(channels) - 1:
                    # Overlap period
                    time.sleep(LED_OVERLAP_MS / 1000.0)
                    # Turn ON next LED
                    next_ch = channels[idx + 1]
                    next_led = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                    next_led[next_ch] = 255
                    ctrl.set_batch_intensities(**next_led)
                    # Remaining POST
                    remaining = POST_LED_DELAY_MS - LED_OVERLAP_MS
                    time.sleep(remaining / 1000.0)
                else:
                    time.sleep(POST_LED_DELAY_MS / 1000.0)

            except Exception as e:
                print(f"  ❌ Ch {ch}: {e}")

        timestamps.append(time.time() - start_time)
        print()

    print("=" * 80)
    print("STABILITY ANALYSIS")
    print("=" * 80)
    print()

    # Analyze each channel
    all_passed = True

    for ch in channels:
        if len(peak_data[ch]) < 2:
            print(f"Channel {ch.upper()}: ❌ Insufficient data")
            all_passed = False
            continue

        peaks = np.array(peak_data[ch])

        # Statistics
        mean_peak = np.mean(peaks)
        std_peak = np.std(peaks)
        min_peak = np.min(peaks)
        max_peak = np.max(peaks)
        peak_to_peak = max_peak - min_peak

        print(f"Channel {ch.upper()}:")
        print(f"  Measurements: {len(peaks)}")
        print(f"  Mean peak: {mean_peak:.3f} nm")
        print(f"  Std dev: {std_peak:.4f} nm")
        print(f"  Min peak: {min_peak:.3f} nm")
        print(f"  Max peak: {max_peak:.3f} nm")
        print(f"  Peak-to-peak drift: {peak_to_peak:.4f} nm")

        # Pass/fail
        if peak_to_peak < 0.1:
            print(f"  ✅ PASS: Drift {peak_to_peak:.4f}nm < 0.1nm target")
        else:
            print(f"  ❌ FAIL: Drift {peak_to_peak:.4f}nm > 0.1nm target")
            all_passed = False

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cycles: {cycle_count}")
    print(f"Test duration: {timestamps[-1]:.1f}s")
    print(f"Average cycle time: {timestamps[-1]/cycle_count:.1f}s")
    print()

    if all_passed:
        print("✅ ALL CHANNELS PASSED: Peak stability <0.1nm")
    else:
        print("❌ SOME CHANNELS FAILED: Peak drift >0.1nm")

    print()

    # Cleanup
    detector.close()
    ctrl.close()
    print("Hardware disconnected")

    return all_passed


if __name__ == "__main__":
    try:
        success = test_peak_stability()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
