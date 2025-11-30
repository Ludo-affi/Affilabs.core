"""
Asynchronous Acquisition with Afterglow Correction

Tests whether correcting for LED afterglow contamination improves:
1. Signal stability (CV between measurements)
2. Peak position precision
3. Channel-to-channel consistency

Uses the exponential decay model from previous testing:
    afterglow(t) = A * exp(-t/tau) + baseline
    where A=13,985, tau=18.7ms, baseline=1,454
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


def afterglow_model(time_ms, A=13985, tau=18.7, baseline=1454):
    """
    Exponential decay model for LED afterglow.

    Args:
        time_ms: Time since LED turned off (milliseconds)
        A: Initial afterglow amplitude (counts)
        tau: Decay time constant (milliseconds)
        baseline: Persistent baseline offset (counts)

    Returns:
        Expected afterglow contribution (counts)
    """
    return A * np.exp(-time_ms / tau) + baseline


def find_peak_position(spectrum, wavelengths):
    """Find peak wavelength using centroid method."""
    peak_idx = np.argmax(spectrum)

    window = 20
    start = max(0, peak_idx - window)
    end = min(len(spectrum), peak_idx + window)

    weights = spectrum[start:end]
    positions = wavelengths[start:end]
    centroid = np.sum(weights * positions) / np.sum(weights)

    return centroid


def async_acquisition_multichannel(ctrl, usb, wavelengths, duration_ms=2000):
    """
    Acquire spectra while cycling through LED channels.

    Returns:
        List of (timestamp, led_state, spectrum) tuples
    """
    spectra_buffer = []

    # LED sequence
    channels = ['a', 'b', 'c', 'd']
    led_intensity = 255

    # Timing parameters
    integration_time = 70  # ms
    led_on_time = 100  # ms (give LED time to stabilize)
    led_off_time = 100  # ms (afterglow decay time)

    usb.set_integration(integration_time)
    time.sleep(0.05)

    start_time = time.perf_counter()
    end_time = start_time + duration_ms / 1000.0

    print(f"Starting acquisition for {duration_ms}ms...")
    print(f"  Integration: {integration_time}ms")
    print(f"  LED on time: {led_on_time}ms")
    print(f"  LED off time: {led_off_time}ms")
    print()

    cycle_count = 0

    while time.perf_counter() < end_time:
        for ch in channels:
            if time.perf_counter() >= end_time:
                break

            # Turn on LED
            ctrl.set_intensity(ch=ch, raw_val=led_intensity)
            led_on_timestamp = time.perf_counter()

            # Wait for LED to stabilize
            time.sleep(led_on_time / 1000.0)

            # Read spectrum
            spectrum = usb.read_intensity()
            measurement_timestamp = time.perf_counter()

            if spectrum is not None:
                spectra_buffer.append({
                    'timestamp': measurement_timestamp,
                    'led_on_time': led_on_timestamp,
                    'channel': ch,
                    'spectrum': spectrum,
                    'time_since_led_on': (measurement_timestamp - led_on_timestamp) * 1000
                })

            # Turn off LED
            ctrl.turn_off_channels()
            led_off_timestamp = time.perf_counter()

            # Wait for afterglow to decay
            time.sleep(led_off_time / 1000.0)

        cycle_count += 1
        print(f"  Cycle {cycle_count} complete ({len(spectra_buffer)} spectra collected)")

    ctrl.turn_off_channels()

    print(f"Acquisition complete: {len(spectra_buffer)} spectra in {cycle_count} cycles")
    print()

    return spectra_buffer


def apply_afterglow_correction(spectra_data, wavelengths):
    """
    Apply afterglow correction based on previous LED state.

    For each measurement, estimate and subtract the afterglow contribution
    from the previous LED that was turned off.
    """
    corrected_data = []

    for i, data in enumerate(spectra_data):
        spectrum = data['spectrum'].copy()

        # Find previous LED (if any)
        if i > 0:
            prev_data = spectra_data[i - 1]
            prev_channel = prev_data['channel']
            current_channel = data['channel']

            # Only correct if different channel (no self-contamination)
            if prev_channel != current_channel:
                # Calculate time since previous LED turned off
                # Assume previous LED turned off ~100ms after it turned on
                prev_led_off_time = prev_data['led_on_time'] + 0.1  # 100ms
                current_measurement_time = data['timestamp']
                time_since_prev_led_off = (current_measurement_time - prev_led_off_time) * 1000  # ms

                # Estimate afterglow contribution
                afterglow = afterglow_model(time_since_prev_led_off)

                # Subtract afterglow (apply to all pixels uniformly)
                spectrum = spectrum - afterglow

                data['afterglow_correction'] = afterglow
                data['time_since_prev_led_off'] = time_since_prev_led_off
            else:
                data['afterglow_correction'] = 0
                data['time_since_prev_led_off'] = 0
        else:
            data['afterglow_correction'] = 0
            data['time_since_prev_led_off'] = 0

        corrected_data.append({
            **data,
            'corrected_spectrum': spectrum
        })

    return corrected_data


def analyze_channel_consistency(spectra_data, wavelengths, corrected=False):
    """
    Analyze signal consistency within each channel.

    Returns:
        Dictionary with statistics for each channel
    """
    spectrum_key = 'corrected_spectrum' if corrected else 'spectrum'

    # Group by channel
    channels = {}
    for data in spectra_data:
        ch = data['channel']
        if ch not in channels:
            channels[ch] = []
        channels[ch].append(data[spectrum_key])

    results = {}

    for ch, spectra in channels.items():
        spectra_array = np.array(spectra)

        # Mean spectrum
        mean_spectrum = np.mean(spectra_array, axis=0)

        # Signal statistics
        mean_signals = [np.mean(s) for s in spectra]
        signal_mean = np.mean(mean_signals)
        signal_std = np.std(mean_signals)
        signal_cv = (signal_std / signal_mean * 100) if signal_mean > 0 else 0

        # Peak statistics
        peak_positions = [find_peak_position(s, wavelengths) for s in spectra]
        peak_mean = np.mean(peak_positions)
        peak_std = np.std(peak_positions)

        # SNR
        noise_std = np.std(mean_spectrum)
        snr = signal_mean / noise_std if noise_std > 0 else 0

        results[ch] = {
            'num_measurements': len(spectra),
            'signal_mean': signal_mean,
            'signal_std': signal_std,
            'signal_cv': signal_cv,
            'peak_mean': peak_mean,
            'peak_std': peak_std,
            'snr': snr
        }

    return results


def test_afterglow_correction():
    """Test whether afterglow correction improves signal stability."""

    print("="*80)
    print("AFTERGLOW CORRECTION TEST - ASYNCHRONOUS ACQUISITION")
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

    # Acquire data with LED cycling
    print("="*80)
    print("STEP 1: ACQUIRE DATA (LED CYCLING)")
    print("="*80)
    print()

    spectra_data = async_acquisition_multichannel(ctrl, usb, wavelengths, duration_ms=3000)

    if len(spectra_data) == 0:
        print("ERROR: No data collected")
        return

    print(f"Collected {len(spectra_data)} spectra total")

    # Count per channel
    channel_counts = {}
    for data in spectra_data:
        ch = data['channel']
        channel_counts[ch] = channel_counts.get(ch, 0) + 1

    print(f"Per channel: {channel_counts}")
    print()

    # Apply afterglow correction
    print("="*80)
    print("STEP 2: APPLY AFTERGLOW CORRECTION")
    print("="*80)
    print()

    corrected_data = apply_afterglow_correction(spectra_data, wavelengths)

    # Show correction statistics
    corrections = [d['afterglow_correction'] for d in corrected_data if d['afterglow_correction'] > 0]
    if len(corrections) > 0:
        print(f"Afterglow corrections applied: {len(corrections)}")
        print(f"  Mean correction: {np.mean(corrections):.0f} counts")
        print(f"  Std correction: {np.std(corrections):.0f} counts")
        print(f"  Range: {np.min(corrections):.0f} - {np.max(corrections):.0f} counts")
    else:
        print("WARNING: No corrections applied")

    print()

    # Analyze uncorrected data
    print("="*80)
    print("STEP 3: ANALYZE UNCORRECTED DATA")
    print("="*80)
    print()

    results_uncorrected = analyze_channel_consistency(spectra_data, wavelengths, corrected=False)

    print(f"{'Channel':>8} | {'N':>4} | {'Signal':>10} | {'Signal CV':>10} | {'Peak':>9} | {'Peak Std':>9} | {'SNR':>6}")
    print(f"{'':>8} | {'':>4} | {'(counts)':>10} | {'(%)':>10} | {'(nm)':>9} | {'(nm)':>9} | {'':>6}")
    print(f"---------+------+------------+------------+-----------+-----------+--------")

    for ch in ['a', 'b', 'c', 'd']:
        if ch in results_uncorrected:
            r = results_uncorrected[ch]
            print(f"{ch.upper():>8} | {r['num_measurements']:>4} | {r['signal_mean']:>10.0f} | {r['signal_cv']:>10.2f} | {r['peak_mean']:>9.2f} | {r['peak_std']:>9.3f} | {r['snr']:>6.1f}")

    print()

    # Calculate inter-channel variation (uncorrected)
    signals_uncorrected = [results_uncorrected[ch]['signal_mean'] for ch in ['a', 'b', 'c', 'd'] if ch in results_uncorrected]
    inter_channel_cv_uncorrected = (np.std(signals_uncorrected) / np.mean(signals_uncorrected) * 100)

    print(f"Inter-channel CV (uncorrected): {inter_channel_cv_uncorrected:.2f}%")
    print()

    # Analyze corrected data
    print("="*80)
    print("STEP 4: ANALYZE CORRECTED DATA")
    print("="*80)
    print()

    results_corrected = analyze_channel_consistency(corrected_data, wavelengths, corrected=True)

    print(f"{'Channel':>8} | {'N':>4} | {'Signal':>10} | {'Signal CV':>10} | {'Peak':>9} | {'Peak Std':>9} | {'SNR':>6}")
    print(f"{'':>8} | {'':>4} | {'(counts)':>10} | {'(%)':>10} | {'(nm)':>9} | {'(nm)':>9} | {'':>6}")
    print(f"---------+------+------------+------------+-----------+-----------+--------")

    for ch in ['a', 'b', 'c', 'd']:
        if ch in results_corrected:
            r = results_corrected[ch]
            print(f"{ch.upper():>8} | {r['num_measurements']:>4} | {r['signal_mean']:>10.0f} | {r['signal_cv']:>10.2f} | {r['peak_mean']:>9.2f} | {r['peak_std']:>9.3f} | {r['snr']:>6.1f}")

    print()

    # Calculate inter-channel variation (corrected)
    signals_corrected = [results_corrected[ch]['signal_mean'] for ch in ['a', 'b', 'c', 'd'] if ch in results_corrected]
    inter_channel_cv_corrected = (np.std(signals_corrected) / np.mean(signals_corrected) * 100)

    print(f"Inter-channel CV (corrected): {inter_channel_cv_corrected:.2f}%")
    print()

    # Comparison
    print("="*80)
    print("STEP 5: CORRECTION IMPACT")
    print("="*80)
    print()

    print(f"{'Metric':>30} | {'Uncorrected':>12} | {'Corrected':>12} | {'Change':>12}")
    print(f"---------------------------------+--------------+--------------+--------------")

    # Inter-channel CV
    cv_change = ((inter_channel_cv_corrected - inter_channel_cv_uncorrected) / inter_channel_cv_uncorrected * 100)
    print(f"{'Inter-channel CV':>30} | {inter_channel_cv_uncorrected:>11.2f}% | {inter_channel_cv_corrected:>11.2f}% | {cv_change:>11.1f}%")

    print()

    # Per-channel improvements
    for ch in ['a', 'b', 'c', 'd']:
        if ch in results_uncorrected and ch in results_corrected:
            print(f"Channel {ch.upper()}:")

            r_u = results_uncorrected[ch]
            r_c = results_corrected[ch]

            # Signal CV change
            signal_cv_change = ((r_c['signal_cv'] - r_u['signal_cv']) / r_u['signal_cv'] * 100) if r_u['signal_cv'] > 0 else 0
            print(f"  Signal CV: {r_u['signal_cv']:.2f}% → {r_c['signal_cv']:.2f}% ({signal_cv_change:+.1f}%)")

            # Peak precision change
            if r_u['peak_std'] > 0:
                peak_std_change = ((r_c['peak_std'] - r_u['peak_std']) / r_u['peak_std'] * 100)
                print(f"  Peak std: {r_u['peak_std']:.3f}nm → {r_c['peak_std']:.3f}nm ({peak_std_change:+.1f}%)")
            else:
                print(f"  Peak std: {r_u['peak_std']:.3f}nm → {r_c['peak_std']:.3f}nm")

            # SNR change
            snr_change = ((r_c['snr'] - r_u['snr']) / r_u['snr'] * 100) if r_u['snr'] > 0 else 0
            print(f"  SNR: {r_u['snr']:.1f} → {r_c['snr']:.1f} ({snr_change:+.1f}%)")
            print()

    # Conclusion
    print("="*80)
    print("CONCLUSION")
    print("="*80)
    print()

    if inter_channel_cv_corrected < inter_channel_cv_uncorrected * 0.9:
        improvement = ((inter_channel_cv_uncorrected - inter_channel_cv_corrected) / inter_channel_cv_uncorrected * 100)
        print(f"✓ Afterglow correction IMPROVED inter-channel consistency by {improvement:.1f}%")
        print(f"  {inter_channel_cv_uncorrected:.2f}% → {inter_channel_cv_corrected:.2f}%")
        print()
        print("Recommendation: Apply afterglow correction in production")
    elif inter_channel_cv_corrected > inter_channel_cv_uncorrected * 1.1:
        degradation = ((inter_channel_cv_corrected - inter_channel_cv_uncorrected) / inter_channel_cv_uncorrected * 100)
        print(f"✗ Afterglow correction DEGRADED inter-channel consistency by {degradation:.1f}%")
        print(f"  {inter_channel_cv_uncorrected:.2f}% → {inter_channel_cv_corrected:.2f}%")
        print()
        print("Reason: Channel brightness differences dominate over afterglow")
        print("Recommendation: Do NOT apply afterglow correction")
    else:
        print(f"~ Afterglow correction had MINIMAL impact")
        print(f"  {inter_channel_cv_uncorrected:.2f}% → {inter_channel_cv_corrected:.2f}%")
        print()
        print("Reason: Channel variation is hardware characteristic, not afterglow")
        print("Recommendation: Afterglow correction not necessary")

    print()

    # Cleanup
    usb.close()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    try:
        test_afterglow_correction()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
