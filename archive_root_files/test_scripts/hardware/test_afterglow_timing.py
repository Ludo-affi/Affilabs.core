"""LED Afterglow Timing Analysis

This script measures LED afterglow decay to determine optimal POST-LED delay.

Test sequence:
1. Turn LED ON for 200ms (simulate measurement)
2. Turn LED OFF
3. Wait various delays (0-200ms)
4. Measure residual signal (afterglow)
5. Calculate optimal POST-LED delay before next channel

Goal: Minimize afterglow contamination while maximizing throughput
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


def test_afterglow_timing():
    """Test LED afterglow decay and determine optimal POST-LED delay."""
    print("=" * 80)
    print("LED AFTERGLOW TIMING ANALYSIS")
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

    # Test parameters
    test_channel = "a"
    led_intensity = 255  # Full brightness to maximize afterglow
    led_on_time_ms = 200  # Simulate measurement time
    integration_time_ms = 70

    # Test various POST-LED delays
    post_delays_ms = [0, 5, 10, 20, 30, 40, 50, 60, 80, 100, 150, 200]

    print("Test Configuration:")
    print(f"  Channel: {test_channel.upper()}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  LED ON Time: {led_on_time_ms}ms (simulated measurement)")
    print(f"  Integration Time: {integration_time_ms}ms")
    print(f"  Testing POST-LED delays: {post_delays_ms}")
    print()

    # Set integration time
    usb.set_integration(integration_time_ms)
    print(f"Integration time set to {integration_time_ms}ms")
    print()

    # STEP 1: Measure dark baseline (LED OFF)
    print("=" * 80)
    print("STEP 1: Measuring dark baseline (LED OFF)")
    print("=" * 80)
    print()

    ctrl.turn_off_channels()
    time.sleep(0.5)  # Wait for any residual light to decay

    dark_spectra = []
    for i in range(3):
        spectrum = usb.read_intensity()
        if spectrum is not None:
            dark_spectra.append(spectrum)

    if len(dark_spectra) == 0:
        print("ERROR: Failed to read dark baseline")
        return

    dark_baseline = np.mean(dark_spectra, axis=0)
    dark_mean = np.mean(dark_baseline)
    dark_max = np.max(dark_baseline)

    print(f"Dark baseline: mean={dark_mean:.1f}, max={dark_max:.1f}")
    print()

    # STEP 2: Measure afterglow at various delays
    print("=" * 80)
    print("STEP 2: Measuring afterglow decay")
    print("=" * 80)
    print()

    results = []

    for delay_ms in post_delays_ms:
        print(f"Testing POST-LED delay = {delay_ms}ms...")

        # Turn off all LEDs first
        ctrl.turn_off_channels()
        time.sleep(0.5)  # Wait for complete decay

        # Turn ON LED for measurement simulation
        ctrl.set_intensity(ch=test_channel, raw_val=led_intensity)
        time.sleep(led_on_time_ms / 1000.0)

        # Turn OFF LED
        ctrl.turn_off_channels()

        # Wait POST-LED delay
        time.sleep(delay_ms / 1000.0)

        # Measure residual signal (afterglow)
        spectrum = usb.read_intensity()

        if spectrum is not None:
            # Subtract dark baseline
            afterglow_spectrum = spectrum - dark_baseline

            afterglow_mean = np.mean(afterglow_spectrum)
            afterglow_max = np.max(afterglow_spectrum)
            afterglow_std = np.std(afterglow_spectrum)

            # Calculate percentage of dark noise
            afterglow_percent = (
                (afterglow_mean / dark_mean * 100) if dark_mean > 0 else 0
            )

            print(
                f"  Afterglow: mean={afterglow_mean:6.1f} ({afterglow_percent:+5.1f}% of dark), max={afterglow_max:6.1f}, std={afterglow_std:5.1f}",
            )

            results.append(
                {
                    "delay_ms": delay_ms,
                    "afterglow_mean": afterglow_mean,
                    "afterglow_max": afterglow_max,
                    "afterglow_std": afterglow_std,
                    "afterglow_percent": afterglow_percent,
                },
            )
        else:
            print("  ERROR: Failed to read spectrum")

        print()

    # STEP 3: Analysis and recommendations
    print("=" * 80)
    print("STEP 3: ANALYSIS & RECOMMENDATIONS")
    print("=" * 80)
    print()

    if len(results) == 0:
        print("ERROR: No successful measurements")
        return

    # Display decay curve
    print("Afterglow Decay Curve:")
    print()
    print("  Delay (ms) | Mean Afterglow | % of Dark | Max Afterglow | Status")
    print(
        "  -----------+----------------+-----------+---------------+-----------------",
    )

    # Define acceptable afterglow threshold (e.g., <5% of dark noise)
    threshold_percent = 5.0
    acceptable_delays = []

    for r in results:
        delay = r["delay_ms"]
        mean_ag = r["afterglow_mean"]
        percent = r["afterglow_percent"]
        max_ag = r["afterglow_max"]

        status = ""
        if abs(percent) < threshold_percent:
            status = "OK: Acceptable"
            acceptable_delays.append(delay)
        elif abs(percent) < threshold_percent * 2:
            status = "WARNING: High afterglow"
        else:
            status = "BAD: Very high afterglow"

        print(
            f"  {delay:4d}       | {mean_ag:14.1f} | {percent:+9.1f} | {max_ag:13.1f} | {status}",
        )

    print()
    print("Analysis:")
    print(f"  Dark baseline mean: {dark_mean:.1f} counts")
    print(
        f"  Acceptable threshold: <{threshold_percent:.1f}% of dark ({dark_mean * threshold_percent / 100:.1f} counts)",
    )
    print()

    if len(acceptable_delays) > 0:
        optimal_delay = min(acceptable_delays)
        print(f"  Optimal POST-LED delay: {optimal_delay}ms")
        print(f"    (Minimum delay where afterglow < {threshold_percent:.1f}% of dark)")
        print()

        # Calculate decay time constant (exponential fit)
        if len(results) >= 3:
            delays = np.array([r["delay_ms"] for r in results])
            afterglows = np.array([abs(r["afterglow_mean"]) for r in results])

            # Fit exponential decay: A * exp(-t/tau)
            # Use first 3 points to estimate tau
            if afterglows[0] > afterglows[1] > 0:
                tau = -delays[1] / np.log(afterglows[1] / afterglows[0])
                print(f"  Estimated decay constant: tau = {tau:.1f}ms")
                print("    (Time for afterglow to decay to 1/e = 37% of initial)")
                print()
    else:
        print(f"  WARNING: No delay achieves <{threshold_percent:.1f}% afterglow")
        print(f"  Recommend using longest tested delay: {max(post_delays_ms)}ms")
        print()

    # STEP 4: Throughput optimization
    print("=" * 80)
    print("STEP 4: THROUGHPUT OPTIMIZATION")
    print("=" * 80)
    print()

    pre_led_delay = 45  # ms (from previous test)

    print("Timing budget per channel:")
    print(f"  PRE-LED delay:  {pre_led_delay}ms (LED stabilization)")
    print(f"  Integration:    {integration_time_ms}ms (detector read)")
    print(
        f"  POST-LED delay: {optimal_delay if len(acceptable_delays) > 0 else max(post_delays_ms)}ms (afterglow decay)",
    )
    print()

    if len(acceptable_delays) > 0:
        total_time = pre_led_delay + integration_time_ms + optimal_delay
        print(f"  TOTAL per channel: {total_time}ms")
        print(f"  Throughput: {1000/total_time:.1f} channels/second")
        print()

        # Overlapping optimization
        print("Overlapping optimization:")
        print(
            "  POST-LED delay of previous channel can overlap with PRE-LED delay of next",
        )
        print(
            f"  Overlap: min({optimal_delay}ms, {pre_led_delay}ms) = {min(optimal_delay, pre_led_delay)}ms",
        )
        print()

        effective_time = total_time - min(optimal_delay, pre_led_delay)
        print(f"  Effective time per channel: {effective_time}ms")
        print(f"  Optimized throughput: {1000/effective_time:.1f} channels/second")
        print()

    # STEP 5: Verification test (use 100ms as practical compromise)
    print("=" * 80)
    print("STEP 5: VERIFICATION TEST (100ms POST-LED delay)")
    print("=" * 80)
    print()

    practical_post_delay = 100  # ms - afterglow stable by then

    print("Testing channel sequence with practical delays:")
    print(f"  PRE-LED:  {pre_led_delay}ms (LED stabilization)")
    print(f"  POST-LED: {practical_post_delay}ms (afterglow decay)")
    print()

    # Test 4-channel sequence
    channels = ["a", "b", "c", "d"]
    channel_signals = []

    for i, ch in enumerate(channels):
        print(f"Channel {ch.upper()}:", end=" ")

        # Turn off all LEDs
        ctrl.turn_off_channels()

        # POST-LED delay (from previous channel)
        if i > 0:
            time.sleep(practical_post_delay / 1000.0)
        else:
            time.sleep(0.2)  # Initial delay

        # PRE-LED delay (LED stabilization)
        ctrl.set_intensity(ch=ch, raw_val=led_intensity)
        time.sleep(pre_led_delay / 1000.0)

        # Read spectrum
        spectrum = usb.read_intensity()

        if spectrum is not None:
            signal = spectrum - dark_baseline
            signal_mean = np.mean(signal)
            signal_max = np.max(signal)

            print(f"mean={signal_mean:6.0f}, max={signal_max:6.0f}")
            channel_signals.append(signal_mean)
        else:
            print("ERROR: Failed to read")
            channel_signals.append(0)

    ctrl.turn_off_channels()
    print()

    # Check for channel crosstalk
    if len(channel_signals) == 4:
        avg_signal = np.mean(channel_signals)
        std_signal = np.std(channel_signals)
        cv = (std_signal / avg_signal * 100) if avg_signal > 0 else 0

        print("Channel consistency:")
        print(f"  Average signal: {avg_signal:.0f} counts")
        print(f"  Std deviation:  {std_signal:.0f} counts")
        print(f"  Coefficient of variation: {cv:.1f}%")
        print()

        if cv < 10:
            print("  OK: Low channel-to-channel variation (<10%)")
        elif cv < 20:
            print("  WARNING: Moderate variation (10-20%)")
        else:
            print("  BAD: High variation (>20%) - possible crosstalk")
        print()

        print("Timing summary per channel:")
        print(f"  PRE-LED:     {pre_led_delay}ms")
        print(f"  Integration: {integration_time_ms}ms")
        print(f"  POST-LED:    {practical_post_delay}ms")
        print(
            f"  TOTAL:       {pre_led_delay + integration_time_ms + practical_post_delay}ms",
        )
        print()
        print("Note: POST-LED delay can overlap with next channel's PRE-LED delay")
        print(
            f"  Effective time: {max(practical_post_delay, pre_led_delay) + integration_time_ms}ms per channel",
        )

    print()

    # STEP 6: Empirical afterglow correction
    print("=" * 80)
    print("STEP 6: EMPIRICAL AFTERGLOW CORRECTION")
    print("=" * 80)
    print()

    print("Building empirical afterglow model from decay curve...")
    print()

    # Extract decay curve data
    if len(results) >= 5:
        delays = np.array([r["delay_ms"] for r in results])
        afterglows = np.array([r["afterglow_mean"] for r in results])

        # Fit exponential decay: A * exp(-t/tau) + baseline
        # Use non-linear least squares
        from scipy.optimize import curve_fit

        def decay_model(t, A, tau, baseline):
            """Exponential decay with baseline offset"""
            return A * np.exp(-t / tau) + baseline

        try:
            # Initial guess: A=initial afterglow, tau=50ms, baseline=stable value
            p0 = [afterglows[0], 50, afterglows[-1]]
            popt, pcov = curve_fit(decay_model, delays, afterglows, p0=p0, maxfev=5000)

            A_fit, tau_fit, baseline_fit = popt

            print("Fitted decay model: A * exp(-t/tau) + baseline")
            print(f"  A (initial):     {A_fit:7.1f} counts")
            print(f"  tau (decay):     {tau_fit:7.1f} ms")
            print(f"  baseline (stable): {baseline_fit:7.1f} counts")
            print()

            # Calculate R-squared
            residuals = afterglows - decay_model(delays, *popt)
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((afterglows - np.mean(afterglows)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            print(f"Model fit quality: R² = {r_squared:.4f}")
            print()

            # Test correction on channel sequence
            print("Testing afterglow correction on 4-channel sequence...")
            print(f"Using {practical_post_delay}ms POST-LED delay with correction")
            print()

            channels = ["a", "b", "c", "d"]
            corrected_signals = []
            raw_signals = []

            for i, ch in enumerate(channels):
                # Turn off all LEDs
                ctrl.turn_off_channels()

                # POST-LED delay
                if i > 0:
                    time.sleep(practical_post_delay / 1000.0)
                else:
                    time.sleep(0.2)

                # Measure afterglow from previous channel (before turning on LED)
                pre_spectrum = usb.read_intensity()
                pre_signal = (
                    np.mean(pre_spectrum - dark_baseline)
                    if pre_spectrum is not None
                    else 0
                )

                # Predict afterglow using model
                predicted_afterglow = decay_model(
                    practical_post_delay,
                    A_fit,
                    tau_fit,
                    baseline_fit,
                )

                # Turn on LED and measure
                ctrl.set_intensity(ch=ch, raw_val=led_intensity)
                time.sleep(pre_led_delay / 1000.0)
                spectrum = usb.read_intensity()

                if spectrum is not None:
                    signal = spectrum - dark_baseline
                    signal_mean = np.mean(signal)

                    # Apply correction: subtract predicted afterglow
                    corrected_mean = signal_mean - predicted_afterglow

                    raw_signals.append(signal_mean)
                    corrected_signals.append(corrected_mean)

                    print(
                        f"Ch {ch.upper()}: raw={signal_mean:6.0f}, predicted_afterglow={predicted_afterglow:6.1f}, corrected={corrected_mean:6.0f}",
                    )
                else:
                    raw_signals.append(0)
                    corrected_signals.append(0)

            ctrl.turn_off_channels()
            print()

            # Compare raw vs corrected
            if len(corrected_signals) == 4:
                raw_avg = np.mean(raw_signals)
                raw_std = np.std(raw_signals)
                raw_cv = (raw_std / raw_avg * 100) if raw_avg > 0 else 0

                corr_avg = np.mean(corrected_signals)
                corr_std = np.std(corrected_signals)
                corr_cv = (corr_std / corr_avg * 100) if corr_avg > 0 else 0

                print("Raw signals:")
                print(f"  Mean: {raw_avg:.0f}, Std: {raw_std:.0f}, CV: {raw_cv:.1f}%")
                print()
                print("Corrected signals:")
                print(
                    f"  Mean: {corr_avg:.0f}, Std: {corr_std:.0f}, CV: {corr_cv:.1f}%",
                )
                print()

                improvement = ((raw_cv - corr_cv) / raw_cv * 100) if raw_cv > 0 else 0
                print(f"Improvement: {improvement:+.1f}% reduction in CV")
                print()

                if corr_cv < raw_cv * 0.8:
                    print(
                        "SUCCESS: Afterglow correction significantly improves consistency (>20%)",
                    )
                elif corr_cv < raw_cv:
                    print("MINOR: Afterglow correction provides modest improvement")
                else:
                    print("FAILED: Correction does not improve consistency")
                    print("  (Channel brightness differences dominate over afterglow)")

        except Exception as e:
            print(f"ERROR: Failed to fit decay model: {e}")
            print("Cannot perform afterglow correction test")
    else:
        print("ERROR: Not enough data points for decay model")

    print()

    # STEP 7: Batch command timing test
    print("=" * 80)
    print("STEP 7: BATCH COMMAND PERFORMANCE TEST")
    print("=" * 80)
    print()

    print("Testing set_batch_intensities() vs individual set_intensity()...")
    print()

    # Test batch command speed
    batch_times = []
    for i in range(10):
        t0 = time.perf_counter()
        ctrl.set_batch_intensities(a=128, b=64, c=192, d=255)
        t1 = time.perf_counter()
        batch_times.append((t1 - t0) * 1000)

    batch_avg = np.mean(batch_times)
    batch_std = np.std(batch_times)

    print("Batch command (4 LEDs simultaneously):")
    print(f"  Average: {batch_avg:.2f}ms")
    print(f"  Std dev: {batch_std:.2f}ms")
    print(f"  Min:     {min(batch_times):.2f}ms")
    print(f"  Max:     {max(batch_times):.2f}ms")
    print()

    # Test individual command speed (4 sequential calls)
    individual_times = []
    for i in range(10):
        ctrl.turn_off_channels()
        time.sleep(0.01)  # Small delay to clear state

        t0 = time.perf_counter()
        ctrl.set_intensity(ch="a", raw_val=128)
        ctrl.set_intensity(ch="b", raw_val=64)
        ctrl.set_intensity(ch="c", raw_val=192)
        ctrl.set_intensity(ch="d", raw_val=255)
        t1 = time.perf_counter()
        individual_times.append((t1 - t0) * 1000)

    indiv_avg = np.mean(individual_times)
    indiv_std = np.std(individual_times)

    print("Individual commands (4 LEDs sequentially):")
    print(f"  Average: {indiv_avg:.2f}ms")
    print(f"  Std dev: {indiv_std:.2f}ms")
    print(f"  Min:     {min(individual_times):.2f}ms")
    print(f"  Max:     {max(individual_times):.2f}ms")
    print()

    speedup = indiv_avg / batch_avg
    time_saved = indiv_avg - batch_avg

    print("Performance comparison:")
    print(f"  Batch command speedup: {speedup:.1f}x faster")
    print(f"  Time saved per 4-LED update: {time_saved:.1f}ms")
    print()

    if speedup > 2:
        print("RECOMMENDATION: Use batch commands for calibration")
        print(f"  Expected calibration speedup: ~{speedup:.1f}x")
    else:
        print("NOTE: Batch commands provide modest improvement")

    print()

    # Cleanup
    ctrl.turn_off_channels()
    usb.close()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_afterglow_timing()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback

        traceback.print_exc()
