"""Integration Time vs SNR Analysis

Tests the trade-off between:
- Long integration (fewer points, high counts)
- Short integration (more points, low counts)

For SPR peak detection, we measure:
1. Signal-to-noise ratio (SNR)
2. Peak position precision
3. Peak detection reliability
"""

import io
import sys
import time
from pathlib import Path

import numpy as np

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def calculate_snr(spectrum):
    """Calculate SNR as signal mean / noise std."""
    signal = np.mean(spectrum)
    noise = np.std(spectrum)
    return signal / noise if noise > 0 else 0


def find_peak_position(spectrum, wavelengths):
    """Find peak wavelength in spectrum."""
    # Simple method: find maximum
    peak_idx = np.argmax(spectrum)
    peak_wavelength = wavelengths[peak_idx]

    # Alternative: centroid around peak (more robust)
    window = 20  # pixels around peak
    start = max(0, peak_idx - window)
    end = min(len(spectrum), peak_idx + window)

    weights = spectrum[start:end]
    positions = wavelengths[start:end]
    centroid = np.sum(weights * positions) / np.sum(weights)

    return peak_wavelength, centroid


def test_integration_time_snr():
    """Test integration time vs SNR trade-off."""
    print("=" * 80)
    print("INTEGRATION TIME vs SNR ANALYSIS")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Initializing hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000()

    if not ctrl.open():
        print("ERROR: Controller not found")
        return

    if not usb.open():
        print("ERROR: Detector not found")
        return

    print("OK: Hardware connected")
    print()

    # Get wavelengths
    wavelengths = usb.wavelengths
    if wavelengths is None:
        print("ERROR: Failed to read wavelengths")
        return

    print(
        f"Detector: {len(wavelengths)} pixels, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm",
    )
    print()

    # Test parameters
    led_channel = "c"  # Use channel C (typically brightest)
    led_intensity = 255

    # Integration times to test (ms)
    integration_times = [10, 20, 35, 50, 70, 100, 150]

    # Number of measurements per integration time
    num_measurements = 10

    print("Test Configuration:")
    print(f"  LED Channel: {led_channel.upper()}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  Integration times: {integration_times}")
    print(f"  Measurements per setting: {num_measurements}")
    print()

    # Turn on LED
    ctrl.set_intensity(ch=led_channel, raw_val=led_intensity)
    time.sleep(0.1)  # Wait for LED to stabilize

    results = []

    print("=" * 80)
    print("MEASUREMENTS")
    print("=" * 80)
    print()

    for int_time in integration_times:
        print(f"Testing {int_time}ms integration time...")

        usb.set_integration(int_time)
        time.sleep(0.05)  # Wait for setting to apply

        # Collect measurements
        spectra = []
        for i in range(num_measurements):
            spectrum = usb.read_intensity()
            if spectrum is not None:
                spectra.append(spectrum)

        if len(spectra) == 0:
            print("  ERROR: No valid spectra")
            continue

        # Calculate statistics
        spectra_array = np.array(spectra)
        mean_spectrum = np.mean(spectra_array, axis=0)

        # SNR calculation
        signal_mean = np.mean(mean_spectrum)
        signal_max = np.max(mean_spectrum)
        noise_std = np.std(mean_spectrum)
        snr = signal_mean / noise_std if noise_std > 0 else 0

        # Peak detection
        peak_positions = []
        peak_centroids = []
        for spectrum in spectra:
            peak_wl, centroid_wl = find_peak_position(spectrum, wavelengths)
            peak_positions.append(peak_wl)
            peak_centroids.append(centroid_wl)

        peak_std = np.std(peak_positions)
        centroid_std = np.std(peak_centroids)

        # Measurement-to-measurement variability
        mean_signals = [np.mean(s) for s in spectra]
        signal_cv = np.std(mean_signals) / np.mean(mean_signals) * 100

        results.append(
            {
                "int_time": int_time,
                "signal_mean": signal_mean,
                "signal_max": signal_max,
                "noise_std": noise_std,
                "snr": snr,
                "peak_std": peak_std,
                "centroid_std": centroid_std,
                "signal_cv": signal_cv,
                "num_spectra": len(spectra),
            },
        )

        print(f"  Signal: mean={signal_mean:.0f}, max={signal_max:.0f}")
        print(f"  SNR: {snr:.1f}")
        print(
            f"  Peak precision: {peak_std:.3f}nm (max), {centroid_std:.3f}nm (centroid)",
        )
        print(f"  Signal variability: {signal_cv:.2f}%")
        print()

    # Turn off LED
    ctrl.turn_off_channels()

    # Analysis
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()

    print(
        f"{'Int Time':>8} | {'Signal':>8} | {'SNR':>6} | {'Peak Std':>9} | {'Centroid Std':>12} | {'Signal CV':>9}",
    )
    print(
        f"{'(ms)':>8} | {'(counts)':>8} | {'':>6} | {'(nm)':>9} | {'(nm)':>12} | {'(%)':>9}",
    )
    print("---------+----------+--------+-----------+--------------+-----------")

    for r in results:
        print(
            f"{r['int_time']:8d} | {r['signal_mean']:8.0f} | {r['snr']:6.1f} | {r['peak_std']:9.3f} | {r['centroid_std']:12.3f} | {r['signal_cv']:9.2f}",
        )

    print()

    # Theory validation
    print("Theory validation (√Signal law):")
    print()

    if len(results) >= 2:
        baseline = results[0]

        for r in results[1:]:
            # Expected SNR improvement
            signal_ratio = r["signal_mean"] / baseline["signal_mean"]
            expected_snr_ratio = np.sqrt(signal_ratio)
            actual_snr_ratio = r["snr"] / baseline["snr"]

            print(
                f"  {r['int_time']:3d}ms vs {baseline['int_time']:3d}ms: signal {signal_ratio:.2f}x → SNR expected {expected_snr_ratio:.2f}x, actual {actual_snr_ratio:.2f}x",
            )

    print()

    # Optimal strategy
    print("=" * 80)
    print("OPTIMAL STRATEGY FOR PEAK DETECTION")
    print("=" * 80)
    print()

    # Find best integration time for peak precision
    best_centroid = min(results, key=lambda x: x["centroid_std"])
    best_snr = max(results, key=lambda x: x["snr"])

    print(
        f"Best peak precision: {best_centroid['int_time']}ms (centroid std = {best_centroid['centroid_std']:.3f}nm)",
    )
    print(f"Best SNR: {best_snr['int_time']}ms (SNR = {best_snr['snr']:.1f})")
    print()

    # Averaging strategy
    print("Averaging strategy comparison:")
    print()

    # Compare: 1× long integration vs N× short integrations
    reference = results[-1]  # Longest integration

    for r in results[:-1]:
        # How many short integrations equal one long integration time?
        time_ratio = reference["int_time"] / r["int_time"]
        num_averages = int(time_ratio)

        # Expected SNR after averaging
        snr_single = r["snr"]
        snr_averaged = snr_single * np.sqrt(num_averages)

        # Compare to reference
        snr_improvement = snr_averaged / reference["snr"]

        print(
            f"  {num_averages}× {r['int_time']}ms = {num_averages * r['int_time']}ms total",
        )
        print(f"    Single: SNR = {snr_single:.1f}")
        print(f"    Averaged: SNR = {snr_averaged:.1f}")
        print(
            f"    vs {reference['int_time']}ms: SNR = {reference['snr']:.1f} ({snr_improvement:.2f}x)",
        )
        print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    print("For SPR peak detection:")
    print()

    # Find sweet spot (good SNR, reasonable time)
    sweet_spot = None
    for r in results:
        if (
            r["centroid_std"] < 0.1 and r["int_time"] <= 70
        ):  # Good precision, reasonable time
            sweet_spot = r
            break

    if sweet_spot:
        print(f"  Optimal integration time: {sweet_spot['int_time']}ms")
        print(f"    SNR: {sweet_spot['snr']:.1f}")
        print(f"    Peak precision: {sweet_spot['centroid_std']:.3f}nm")
        print(f"    Signal: {sweet_spot['signal_mean']:.0f} counts")
        print()
        print("  This provides:")
        print("    - Good signal-to-noise ratio")
        print("    - Sub-0.1nm peak precision")
        print("    - Fast measurement cycle")
    else:
        print("  Use maximum safe integration time: 70ms")
        print("    - Maximizes SNR")
        print("    - Best peak precision")
        print("    - Standard for SPR measurements")

    print()
    print("Key insights:")
    print("  1. SNR improves with sqrt(integration_time)")
    print(
        "  2. Averaging multiple short integrations = single long integration (theoretically)",
    )
    print("  3. In practice: single long integration is simpler and more reliable")
    print("  4. For real-time monitoring: shorter integration allows faster updates")
    print("  5. For precision: longer integration reduces measurement overhead")

    print()

    # Cleanup
    usb.close()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_integration_time_snr()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback

        traceback.print_exc()
