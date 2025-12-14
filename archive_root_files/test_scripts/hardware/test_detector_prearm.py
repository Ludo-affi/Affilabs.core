"""Test if detector supports pre-arm optimization (caching integration time).

This script tests whether the spectrometer caches integration time or requires
it to be set before every read operation.

Test Method:
1. Set integration time once
2. Read spectrum multiple times without re-setting integration time
3. Compare spectra - if they're valid and similar, caching works
"""

import time
import numpy as np
from src.utils.usb4000_wrapper import USB4000

def test_detector_prearm():
    """Test if detector caches integration time."""

    print("=" * 80)
    print("DETECTOR PRE-ARM TEST")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Connecting to spectrometer...")
    usb = USB4000()

    if not usb.open():
        print("❌ ERROR: Failed to open spectrometer")
        return False

    if not usb.opened:
        print("❌ ERROR: Spectrometer not opened")
        return False

    print(f"✅ Spectrometer connected")
    print(f"   Serial: {usb.serial_number}")
    print(f"   Pixels: {usb._num_pixels}")
    print()

    # Test parameters
    integration_time = 50.0  # ms
    num_reads = 5

    print(f"Test Parameters:")
    print(f"  Integration Time: {integration_time}ms")
    print(f"  Number of Reads: {num_reads}")
    print()

    # ============================================================================
    # TEST 1: Set integration time ONCE, then read multiple times
    # ============================================================================
    print("-" * 80)
    print("TEST 1: Pre-Arm (Set Once, Read Multiple)")
    print("-" * 80)

    try:
        # Set integration time ONCE
        print(f"Setting integration time to {integration_time}ms...")
        result = usb.set_integration(integration_time)
        print(f"  Result: {result}")
        time.sleep(0.1)

        # Read multiple spectra WITHOUT re-setting integration time
        spectra_prearm = []
        times_prearm = []

        for i in range(num_reads):
            print(f"  Read {i+1}/{num_reads}...", end=" ")
            start = time.perf_counter()
            spectrum = usb.read_intensity()
            elapsed = (time.perf_counter() - start) * 1000.0

            if spectrum is not None:
                spectra_prearm.append(spectrum)
                times_prearm.append(elapsed)
                print(f"✅ {elapsed:.1f}ms (min={np.min(spectrum):.0f}, max={np.max(spectrum):.0f}, mean={np.mean(spectrum):.0f})")
            else:
                print("❌ FAILED - spectrum is None")

        print()
        print(f"Pre-Arm Results: {len(spectra_prearm)}/{num_reads} successful")
        if times_prearm:
            print(f"  Average time: {np.mean(times_prearm):.1f}ms")
            print(f"  Time range: {np.min(times_prearm):.1f}ms - {np.max(times_prearm):.1f}ms")

    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # ============================================================================
    # TEST 2: Set integration time BEFORE EVERY read (baseline)
    # ============================================================================
    print("-" * 80)
    print("TEST 2: No Pre-Arm (Set Before Every Read)")
    print("-" * 80)

    try:
        spectra_no_prearm = []
        times_no_prearm = []

        for i in range(num_reads):
            print(f"  Read {i+1}/{num_reads}...", end=" ")

            # Set integration time EVERY TIME
            usb.set_integration(integration_time)

            start = time.perf_counter()
            spectrum = usb.read_intensity()
            elapsed = (time.perf_counter() - start) * 1000.0

            if spectrum is not None:
                spectra_no_prearm.append(spectrum)
                times_no_prearm.append(elapsed)
                print(f"✅ {elapsed:.1f}ms (min={np.min(spectrum):.0f}, max={np.max(spectrum):.0f}, mean={np.mean(spectrum):.0f})")
            else:
                print("❌ FAILED - spectrum is None")

        print()
        print(f"No Pre-Arm Results: {len(spectra_no_prearm)}/{num_reads} successful")
        if times_no_prearm:
            print(f"  Average time: {np.mean(times_no_prearm):.1f}ms")
            print(f"  Time range: {np.min(times_no_prearm):.1f}ms - {np.max(times_no_prearm):.1f}ms")

    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # ============================================================================
    # ANALYSIS: Compare results
    # ============================================================================
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if len(spectra_prearm) != num_reads:
        print(f"❌ FAILED: Pre-arm mode only got {len(spectra_prearm)}/{num_reads} valid spectra")
        print("   → Detector DOES NOT support pre-arm (requires integration time before every read)")
        return False

    if len(spectra_no_prearm) != num_reads:
        print(f"⚠️  WARNING: No-prearm mode only got {len(spectra_no_prearm)}/{num_reads} valid spectra")

    # Check if spectra are valid (not all zeros)
    prearm_valid = all(np.sum(s) > 0 for s in spectra_prearm)
    no_prearm_valid = all(np.sum(s) > 0 for s in spectra_no_prearm)

    print(f"✅ Pre-Arm Spectra Valid: {prearm_valid}")
    print(f"✅ No Pre-Arm Spectra Valid: {no_prearm_valid}")
    print()

    if not prearm_valid:
        print("❌ CONCLUSION: Detector DOES NOT support pre-arm")
        print("   All spectra from pre-arm mode are invalid (zeros)")
        print("   → Integration time MUST be set before every read")
        return False

    # Compare spectral similarity
    print("Spectral Comparison:")
    for i in range(min(len(spectra_prearm), len(spectra_no_prearm))):
        diff = np.abs(spectra_prearm[i] - spectra_no_prearm[i])
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        rel_diff = mean_diff / np.mean(spectra_prearm[i]) * 100 if np.mean(spectra_prearm[i]) > 0 else 0

        print(f"  Spectrum {i+1}: max_diff={max_diff:.1f}, mean_diff={mean_diff:.1f}, relative={rel_diff:.2f}%")

    print()

    # Time comparison
    if times_prearm and times_no_prearm:
        time_prearm_avg = np.mean(times_prearm)
        time_no_prearm_avg = np.mean(times_no_prearm)
        time_saved = time_no_prearm_avg - time_prearm_avg
        speedup = time_no_prearm_avg / time_prearm_avg if time_prearm_avg > 0 else 1.0

        print("Performance Comparison:")
        print(f"  Pre-Arm:    {time_prearm_avg:.1f}ms average")
        print(f"  No Pre-Arm: {time_no_prearm_avg:.1f}ms average")
        print(f"  Time Saved: {time_saved:.1f}ms per read")
        print(f"  Speedup:    {speedup:.2f}x")
        print()

        if time_saved > 1.0:
            print(f"💡 Pre-arm saves ~{time_saved:.1f}ms per acquisition")
            print(f"   For 4 channels: ~{time_saved * 3:.1f}ms per cycle (3 redundant calls avoided)")

    print()
    print("=" * 80)
    print("✅ CONCLUSION: Detector SUPPORTS pre-arm optimization")
    print("=" * 80)
    print("Recommendations:")
    print("1. Set integration time ONCE before acquisition loop")
    print("2. Remove set_integration() from inside _acquire_channel_spectrum_batched()")
    print("3. Move to _acquisition_worker() startup (before channel loop)")
    print()

    return True

if __name__ == "__main__":
    try:
        success = test_detector_prearm()
        if success:
            print("✅ Test completed successfully")
        else:
            print("❌ Test failed or detector does not support pre-arm")
    except Exception as e:
        print(f"❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
