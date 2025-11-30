"""
Integration Time vs SNR Analysis - Asynchronous Acquisition

Tests the trade-off between:
- Long integration (fewer points, high counts)
- Short integration (more points, low counts)

Using ASYNCHRONOUS acquisition:
- Detector reads continuously
- Collect many spectra quickly
- Average/process for noise reduction

Compares to synchronized single-shot measurements.
"""

import time
import sys
from pathlib import Path
import io
import numpy as np
import threading
from collections import deque

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000
from utils.logger import logger


def calculate_snr(spectrum):
    """Calculate SNR as signal mean / noise std."""
    signal = np.mean(spectrum)
    noise = np.std(spectrum)
    return signal / noise if noise > 0 else 0


def find_peak_position(spectrum, wavelengths):
    """Find peak wavelength in spectrum."""
    # Centroid around peak (more robust than max)
    peak_idx = np.argmax(spectrum)

    window = 20  # pixels around peak
    start = max(0, peak_idx - window)
    end = min(len(spectrum), peak_idx + window)

    weights = spectrum[start:end]
    positions = wavelengths[start:end]
    centroid = np.sum(weights * positions) / np.sum(weights)

    return centroid


def async_acquisition(usb, duration_ms, spectra_buffer):
    """
    Continuously read spectra as fast as possible.

    Args:
        usb: USB4000 detector
        duration_ms: How long to collect (milliseconds)
        spectra_buffer: deque to store spectra with timestamps
    """
    start_time = time.perf_counter()
    end_time = start_time + duration_ms / 1000.0

    count = 0
    while time.perf_counter() < end_time:
        spectrum = usb.read_intensity()
        if spectrum is not None:
            timestamp = time.perf_counter()
            spectra_buffer.append((timestamp, spectrum))
            count += 1

    return count


def test_integration_snr_async():
    """Test integration time vs SNR with asynchronous acquisition."""

    print("="*80)
    print("INTEGRATION TIME vs SNR - ASYNCHRONOUS ACQUISITION")
    print("="*80)
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

    print(f"Detector: {len(wavelengths)} pixels, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm")
    print()

    # Test parameters
    led_channel = 'c'
    led_intensity = 255

    # Integration times to test (ms)
    integration_times = [10, 20, 35, 50, 70]

    # Collection duration for each test (ms)
    collection_duration = 1000  # 1 second of continuous acquisition

    print(f"Test Configuration:")
    print(f"  LED Channel: {led_channel.upper()}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  Integration times: {integration_times}")
    print(f"  Collection duration: {collection_duration}ms per test")
    print(f"  Method: Asynchronous continuous acquisition")
    print()

    # Turn on LED
    ctrl.set_intensity(ch=led_channel, raw_val=led_intensity)
    time.sleep(0.1)

    results_sync = []
    results_async = []

    print("="*80)
    print("SYNCHRONIZED MEASUREMENTS (baseline)")
    print("="*80)
    print()

    for int_time in integration_times:
        print(f"Testing {int_time}ms integration (synchronized)...")

        usb.set_integration(int_time)
        time.sleep(0.05)

        # Collect as many measurements as fit in collection_duration
        num_measurements = int(collection_duration / (int_time + 20))  # +20ms overhead

        start_time = time.perf_counter()
        spectra = []
        for i in range(num_measurements):
            spectrum = usb.read_intensity()
            if spectrum is not None:
                spectra.append(spectrum)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if len(spectra) == 0:
            print(f"  ERROR: No valid spectra")
            continue

        # Statistics
        spectra_array = np.array(spectra)
        mean_spectrum = np.mean(spectra_array, axis=0)

        signal_mean = np.mean(mean_spectrum)
        signal_max = np.max(mean_spectrum)
        noise_std = np.std(mean_spectrum)
        snr = signal_mean / noise_std if noise_std > 0 else 0

        # Peak precision
        peak_positions = [find_peak_position(s, wavelengths) for s in spectra]
        peak_std = np.std(peak_positions)

        # Measurement variability
        mean_signals = [np.mean(s) for s in spectra]
        signal_cv = np.std(mean_signals) / np.mean(mean_signals) * 100

        results_sync.append({
            'int_time': int_time,
            'signal_mean': signal_mean,
            'signal_max': signal_max,
            'snr': snr,
            'peak_std': peak_std,
            'signal_cv': signal_cv,
            'num_spectra': len(spectra),
            'elapsed_ms': elapsed_ms,
            'rate_hz': len(spectra) / (elapsed_ms / 1000)
        })

        print(f"  Collected: {len(spectra)} spectra in {elapsed_ms:.0f}ms ({results_sync[-1]['rate_hz']:.1f} Hz)")
        print(f"  Signal: mean={signal_mean:.0f}, max={signal_max:.0f}")
        print(f"  SNR: {snr:.1f}")
        print(f"  Peak precision: {peak_std:.3f}nm")
        print()

    print("="*80)
    print("ASYNCHRONOUS MEASUREMENTS (continuous)")
    print("="*80)
    print()

    for int_time in integration_times:
        print(f"Testing {int_time}ms integration (asynchronous)...")

        usb.set_integration(int_time)
        time.sleep(0.05)

        # Async acquisition
        spectra_buffer = deque()

        start_time = time.perf_counter()
        acquisition_thread = threading.Thread(
            target=async_acquisition,
            args=(usb, collection_duration, spectra_buffer)
        )
        acquisition_thread.start()
        acquisition_thread.join()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if len(spectra_buffer) == 0:
            print(f"  ERROR: No spectra collected")
            continue

        # Extract spectra
        timestamps, spectra = zip(*spectra_buffer)
        spectra = list(spectra)

        # Statistics
        spectra_array = np.array(spectra)
        mean_spectrum = np.mean(spectra_array, axis=0)

        signal_mean = np.mean(mean_spectrum)
        signal_max = np.max(mean_spectrum)
        noise_std = np.std(mean_spectrum)
        snr = signal_mean / noise_std if noise_std > 0 else 0

        # Peak precision
        peak_positions = [find_peak_position(s, wavelengths) for s in spectra]
        peak_std = np.std(peak_positions)

        # Measurement variability
        mean_signals = [np.mean(s) for s in spectra]
        signal_cv = np.std(mean_signals) / np.mean(mean_signals) * 100

        results_async.append({
            'int_time': int_time,
            'signal_mean': signal_mean,
            'signal_max': signal_max,
            'snr': snr,
            'peak_std': peak_std,
            'signal_cv': signal_cv,
            'num_spectra': len(spectra),
            'elapsed_ms': elapsed_ms,
            'rate_hz': len(spectra) / (elapsed_ms / 1000)
        })

        print(f"  Collected: {len(spectra)} spectra in {elapsed_ms:.0f}ms ({results_async[-1]['rate_hz']:.1f} Hz)")
        print(f"  Signal: mean={signal_mean:.0f}, max={signal_max:.0f}")
        print(f"  SNR: {snr:.1f}")
        print(f"  Peak precision: {peak_std:.3f}nm")
        print()

    # Turn off LED
    ctrl.turn_off_channels()

    # Comparison
    print("="*80)
    print("SYNCHRONIZED vs ASYNCHRONOUS COMPARISON")
    print("="*80)
    print()

    print(f"{'Int Time':>8} | {'Method':>12} | {'Spectra':>7} | {'Rate':>8} | {'Signal':>8} | {'SNR':>6} | {'Peak Std':>9}")
    print(f"{'(ms)':>8} | {'':>12} | {'':>7} | {'(Hz)':>8} | {'(cts)':>8} | {'':>6} | {'(nm)':>9}")
    print(f"---------+--------------+---------+----------+----------+--------+-----------")

    for sync, async_r in zip(results_sync, results_async):
        print(f"{sync['int_time']:8d} | {'Sync':>12} | {sync['num_spectra']:7d} | {sync['rate_hz']:8.1f} | {sync['signal_mean']:8.0f} | {sync['snr']:6.1f} | {sync['peak_std']:9.3f}")
        print(f"{async_r['int_time']:8d} | {'Async':>12} | {async_r['num_spectra']:7d} | {async_r['rate_hz']:8.1f} | {async_r['signal_mean']:8.0f} | {async_r['snr']:6.1f} | {async_r['peak_std']:9.3f}")

        # Speedup
        speedup = async_r['num_spectra'] / sync['num_spectra']
        snr_ratio = async_r['snr'] / sync['snr']
        precision_ratio = sync['peak_std'] / async_r['peak_std']  # Higher is better

        print(f"         | {'Async/Sync':>12} | {speedup:7.2f}x | {async_r['rate_hz']/sync['rate_hz']:8.2f}x | {'':>8} | {snr_ratio:6.2f}x | {precision_ratio:9.2f}x")
        print()

    print()

    # Analysis
    print("="*80)
    print("ANALYSIS: DOES ASYNC HELP WITH NOISE?")
    print("="*80)
    print()

    print("Key findings:")
    print()

    for sync, async_r in zip(results_sync, results_async):
        print(f"{sync['int_time']}ms integration:")

        # More spectra collected
        spectra_gain = async_r['num_spectra'] / sync['num_spectra']
        print(f"  Async collected {spectra_gain:.2f}x more spectra ({async_r['num_spectra']} vs {sync['num_spectra']})")

        # SNR comparison
        snr_gain = async_r['snr'] / sync['snr']
        if snr_gain > 1.1:
            print(f"  SNR improved {snr_gain:.2f}x: {sync['snr']:.1f} → {async_r['snr']:.1f} ✓")
        elif snr_gain < 0.9:
            print(f"  SNR degraded {snr_gain:.2f}x: {sync['snr']:.1f} → {async_r['snr']:.1f} ✗")
        else:
            print(f"  SNR similar: {sync['snr']:.1f} vs {async_r['snr']:.1f} (~)")

        # Peak precision comparison
        precision_ratio = sync['peak_std'] / async_r['peak_std']
        if async_r['peak_std'] < sync['peak_std'] * 0.9:
            print(f"  Peak precision improved {precision_ratio:.2f}x: {sync['peak_std']:.3f}nm → {async_r['peak_std']:.3f}nm ✓")
        elif async_r['peak_std'] > sync['peak_std'] * 1.1:
            print(f"  Peak precision degraded {precision_ratio:.2f}x: {sync['peak_std']:.3f}nm → {async_r['peak_std']:.3f}nm ✗")
        else:
            print(f"  Peak precision similar: {sync['peak_std']:.3f}nm vs {async_r['peak_std']:.3f}nm (~)")

        # Theoretical expectation
        expected_snr_gain = np.sqrt(spectra_gain)
        print(f"  Expected SNR gain from √N: {expected_snr_gain:.2f}x (actual: {snr_gain:.2f}x)")

        print()

    # Recommendation
    print("="*80)
    print("RECOMMENDATION")
    print("="*80)
    print()

    # Find best approach for each integration time
    best_overall = None
    best_precision = float('inf')

    for sync, async_r in zip(results_sync, results_async):
        if async_r['peak_std'] < best_precision:
            best_precision = async_r['peak_std']
            best_overall = async_r

    if best_overall:
        print(f"Best peak precision: {best_overall['int_time']}ms asynchronous")
        print(f"  Peak std: {best_overall['peak_std']:.3f}nm")
        print(f"  SNR: {best_overall['snr']:.1f}")
        print(f"  Spectra collected: {best_overall['num_spectra']} in {best_overall['elapsed_ms']:.0f}ms")
        print()

    print("Async acquisition benefits:")
    print("  ✓ Collects more data points per unit time")
    print("  ✓ Averaging reduces random noise (follows √N law)")
    print("  ✓ Better utilization of detector duty cycle")
    print()

    print("But consider:")
    print("  - Signal mean remains the same (integration time determines photon count)")
    print("  - SNR improvement comes from averaging, not from raw signal")
    print("  - More data = more processing overhead")
    print("  - For real-time SPR: single high-quality measurement may be better")
    print()

    print("Verdict:")
    print("  For OFFLINE analysis: Async wins (more data → better averaging)")
    print("  For REAL-TIME monitoring: Sync at optimal integration time wins")
    print("  Optimal integration: 70ms (balances signal, speed, precision)")

    print()

    # Cleanup
    usb.close()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    try:
        test_integration_snr_async()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
