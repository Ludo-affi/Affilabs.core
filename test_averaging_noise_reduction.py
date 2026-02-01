"""Verify Phase Photonics Hardware Averaging Actually Averages

This test checks if hardware averaging actually reduces noise (proving it's 
averaging multiple scans) or if it's just returning a single scan faster.

If it's truly averaging, we should see:
- Noise (std dev) reduced by sqrt(8) = 2.83x
- Signal remains the same
"""

import time
import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger


def test_noise_reduction():
    """Test if hardware averaging reduces noise as expected."""
    print("\n" + "="*80)
    print("HARDWARE AVERAGING NOISE REDUCTION TEST")
    print("="*80)
    print("If averaging works correctly, noise should reduce by √8 = 2.83x\n")

    try:
        # Connect
        detector = PhasePhotonics()
        detector.get_device_list()

        if not detector.devs or not detector.open():
            print("❌ Failed to connect to detector")
            return

        print(f"✓ Connected: {detector.serial_number}\n")

        # Set integration time
        detector.set_integration(22.0)

        # Test 1: Single scans (no averaging) - collect noise baseline
        print("="*80)
        print("TEST 1: Single Scans (num_scans=1) - Noise Baseline")
        print("="*80)

        detector.set_averaging(1)
        time.sleep(0.1)

        single_scans = []
        print("  Collecting 20 single scans...")
        for i in range(20):
            single_scans.append(detector.read_intensity())

        single_scans = np.array(single_scans)

        # Calculate noise (std dev across scans at each pixel)
        single_noise = np.std(single_scans, axis=0)
        single_signal = np.mean(single_scans, axis=0)
        single_snr = single_signal / (single_noise + 1e-10)

        # Use middle pixels for analysis (avoid edges)
        pixel_range = slice(500, 1500)

        avg_single_noise = np.mean(single_noise[pixel_range])
        avg_single_signal = np.mean(single_signal[pixel_range])
        avg_single_snr = np.mean(single_snr[pixel_range])

        print(f"  Signal (mean): {avg_single_signal:.1f} counts")
        print(f"  Noise (std dev): {avg_single_noise:.2f} counts")
        print(f"  SNR: {avg_single_snr:.1f}\n")

        # Test 2: Hardware averaged scans (8 scans)
        print("="*80)
        print("TEST 2: Hardware Averaged Scans (num_scans=8)")
        print("="*80)
        print("  Expected noise reduction: 2.83x (if averaging works)")
        print("  Expected noise: ~{:.2f} counts\n".format(avg_single_noise / 2.83))

        detector.set_averaging(8)
        time.sleep(0.1)

        averaged_scans = []
        print("  Collecting 20 hardware-averaged spectra...")
        for i in range(20):
            averaged_scans.append(detector.read_intensity())

        averaged_scans = np.array(averaged_scans)

        # Calculate noise for averaged scans
        averaged_noise = np.std(averaged_scans, axis=0)
        averaged_signal = np.mean(averaged_scans, axis=0)
        averaged_snr = averaged_signal / (averaged_noise + 1e-10)

        avg_averaged_noise = np.mean(averaged_noise[pixel_range])
        avg_averaged_signal = np.mean(averaged_signal[pixel_range])
        avg_averaged_snr = np.mean(averaged_snr[pixel_range])

        print(f"  Signal (mean): {avg_averaged_signal:.1f} counts")
        print(f"  Noise (std dev): {avg_averaged_noise:.2f} counts")
        print(f"  SNR: {avg_averaged_snr:.1f}\n")

        # Analysis
        print("="*80)
        print("ANALYSIS")
        print("="*80)

        noise_reduction = avg_single_noise / avg_averaged_noise
        snr_improvement = avg_averaged_snr / avg_single_snr

        expected_reduction = np.sqrt(8)  # 2.83

        print(f"  Single scan noise: {avg_single_noise:.2f} counts")
        print(f"  Hardware avg noise: {avg_averaged_noise:.2f} counts")
        print(f"  Noise reduction: {noise_reduction:.2f}x")
        print(f"  Expected reduction: {expected_reduction:.2f}x (√8)")
        print(f"  SNR improvement: {snr_improvement:.2f}x\n")

        # Verdict
        print("="*80)
        print("VERDICT")
        print("="*80)

        if noise_reduction >= 2.0:
            print("\n  ✅ HARDWARE AVERAGING IS WORKING!")
            print(f"  • Noise reduced by {noise_reduction:.2f}x (expected {expected_reduction:.2f}x)")
            print(f"  • SNR improved by {snr_improvement:.2f}x")
            print("  • The detector IS averaging multiple scans internally")
            print(f"  • Achievement: {noise_reduction/expected_reduction*100:.0f}% of theoretical performance")
        elif noise_reduction >= 1.3:
            print("\n  ⚠ PARTIAL AVERAGING")
            print(f"  • Noise reduced by {noise_reduction:.2f}x (expected {expected_reduction:.2f}x)")
            print("  • Some averaging is happening but not full 8 scans")
            print("  • Check detector firmware and DLL version")
        else:
            print("\n  ❌ AVERAGING NOT WORKING")
            print(f"  • Noise reduced by only {noise_reduction:.2f}x (expected {expected_reduction:.2f}x)")
            print("  • The detector is NOT averaging - just returning single scans")
            print("  • Hardware averaging feature may not be enabled in this firmware")

        # Timing comparison
        print("\n" + "="*80)
        print("TIMING SUMMARY")
        print("="*80)

        # Quick timing test
        detector.set_averaging(1)
        time.sleep(0.05)

        start = time.perf_counter()
        for _ in range(5):
            detector.read_intensity()
        single_time = (time.perf_counter() - start) / 5 * 1000

        detector.set_averaging(8)
        time.sleep(0.05)

        start = time.perf_counter()
        for _ in range(5):
            detector.read_intensity()
        avg_time = (time.perf_counter() - start) / 5 * 1000

        print(f"  Single scan: {single_time:.1f} ms")
        print(f"  8-scan average: {avg_time:.1f} ms")
        print(f"  Time ratio: {avg_time/single_time:.2f}x")
        print("  Expected ratio: ~4.5x if hardware averaging works")

        if avg_time / single_time > 3.0:
            print("  ✓ Timing suggests hardware averaging is active")
        else:
            print("  ⚠ Timing suggests averaging may not be working")

        print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("Noise reduction test failed")
        raise


if __name__ == "__main__":
    test_noise_reduction()
