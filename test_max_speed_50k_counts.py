"""
Maximum Speed Test - 50k Counts Target

Optimize integration time for each channel to hit 50,000 counts at peak.
ALL LEDs at 255 intensity, measure actual speed and noise.

Goal: Find minimum integration time needed for 50k counts, measure throughput.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def find_peak_counts(spectrum):
    """Find peak intensity in spectrum."""
    if spectrum is None or len(spectrum) == 0:
        return 0
    return np.max(spectrum)


def optimize_led_intensity(detector, ctrl, channel, target_counts=50000, max_integration=300):
    """Find LED intensity AND integration time that gives target peak counts.

    Uses same algorithm as calibration_6step.py calibrate_led_channel()
    First tries to optimize LED at short integration, if can't reach target,
    increases integration time.

    Args:
        detector: USB4000 detector instance
        ctrl: PicoP4SPR controller instance
        channel: Channel letter ('a', 'b', 'c', 'd')
        target_counts: Target peak counts (default 50000)
        max_integration: Maximum integration time to try (ms)

    Returns:
        Tuple of (optimal_led_intensity, optimal_integration_time), or (None, None) if failed
    """
    print(f"  Optimizing Ch {channel} for {target_counts} counts...")

    # Start with short integration time
    integration_time = 10.0

    # Try to hit target with LED intensity at minimum integration first
    for attempt in range(5):
        detector.set_integration(integration_time)
        time.sleep(0.01)

        # Start at maximum intensity
        intensity = 255
        led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        led_values[channel] = intensity
        ctrl.set_batch_intensities(**led_values)
        time.sleep(0.02)  # LED settling

        # Read initial signal
        spectrum = detector.read_intensity()
        if spectrum is None:
            print(f"    ❌ Failed to acquire spectrum")
            return None, None

        peak_counts = find_peak_counts(spectrum)
        print(f"    Try {attempt+1}: Integration={integration_time:.1f}ms, LED={intensity} → {peak_counts:.0f} counts")

        # Check if we can reach target at this integration time
        if peak_counts >= target_counts * 0.9:
            # Close enough, optimize LED intensity
            print(f"    Can reach target at {integration_time:.1f}ms, optimizing LED...")
            break

        # Check if saturated
        if peak_counts >= 65535:
            print(f"    Saturated, reducing LED...")
            # Reduce LED instead of increasing integration
            target_signal = target_counts * 0.85
            reduction_factor = target_signal / peak_counts
            intensity = max(10, int(intensity * reduction_factor))

            led_values[channel] = intensity
            ctrl.set_batch_intensities(**led_values)
            time.sleep(0.02)

            spectrum = detector.read_intensity()
            if spectrum:
                peak_counts = find_peak_counts(spectrum)
                print(f"    Reduced: LED={intensity} → {peak_counts:.0f} counts")
            break

        # Need more signal, increase integration time
        if integration_time >= max_integration:
            print(f"    ⚠️ Max integration reached, using what we have")
            break

        # Calculate needed integration time
        needed_ratio = target_counts / peak_counts
        integration_time = min(integration_time * needed_ratio * 1.1, max_integration)  # 10% margin
        print(f"    Need {needed_ratio:.2f}x more signal, increasing integration to {integration_time:.1f}ms")

    # Now optimize LED intensity at chosen integration time
    detector.set_integration(integration_time)
    time.sleep(0.01)

    # Coarse adjustment (step size 20)
    coarse_step = 20
    while peak_counts > target_counts and intensity > coarse_step:
        intensity -= coarse_step
        led_values[channel] = intensity
        ctrl.set_batch_intensities(**led_values)
        time.sleep(0.015)

        spectrum = detector.read_intensity()
        if spectrum is None:
            break
        peak_counts = find_peak_counts(spectrum)

    # Medium adjustment (step size 5)
    medium_step = 5
    while peak_counts < target_counts and intensity < 255:
        intensity += medium_step
        led_values[channel] = intensity
        ctrl.set_batch_intensities(**led_values)
        time.sleep(0.015)

        spectrum = detector.read_intensity()
        if spectrum is None:
            break
        peak_counts = find_peak_counts(spectrum)

    # Fine adjustment (step size 1)
    fine_step = 1
    iterations = 0
    while abs(peak_counts - target_counts) > target_counts * 0.05 and iterations < 20:
        if peak_counts < target_counts and intensity < 255:
            intensity += fine_step
        elif peak_counts > target_counts and intensity > 1:
            intensity -= fine_step
        else:
            break

        led_values[channel] = intensity
        ctrl.set_batch_intensities(**led_values)
        time.sleep(0.015)

        spectrum = detector.read_intensity()
        if spectrum is None:
            break
        peak_counts = find_peak_counts(spectrum)
        iterations += 1

    error_pct = ((peak_counts - target_counts) / target_counts) * 100
    print(f"    ✅ Final: Integration={integration_time:.1f}ms, LED={intensity} → {peak_counts:.0f} counts ({error_pct:+.1f}%)")

    # Turn OFF LED
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.01)

    return intensity, integration_time


def measure_speed_and_noise(detector, ctrl, channels_config, num_cycles=20):
    """Measure acquisition speed and noise over multiple full cycles.

    Args:
        detector: USB4000 detector instance
        ctrl: PicoP4SPR controller instance
        channels_config: Dict with channel configs {ch: {'integration_time': ms}}
        num_cycles: Number of complete 4-channel cycles

    Returns:
        dict with per-channel speed and noise metrics
    """
    print(f"  Running {num_cycles} complete cycles (A→B→C→D)...")
    print()

    # Storage for all measurements
    all_data = {ch: {'counts': [], 'acq_times': []} for ch in channels_config.keys()}
    cycle_times = []

    for cycle in range(num_cycles):
        cycle_start = time.perf_counter()
        print(f"  Cycle {cycle+1}/{num_cycles}: ", end='', flush=True)

        for ch in ['a', 'b', 'c', 'd']:
            if ch not in channels_config:
                continue

            # Set integration time for this channel
            detector.set_integration(channels_config[ch]['integration_time'])
            time.sleep(0.005)

            # Turn ON LED at optimized intensity
            led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
            led_values[ch] = channels_config[ch]['led_intensity']
            ctrl.set_batch_intensities(**led_values)
            time.sleep(0.01)  # LED settling

            # Acquire spectrum
            acq_start = time.perf_counter()
            spectrum = detector.read_intensity()
            acq_time = (time.perf_counter() - acq_start) * 1000.0  # ms

            # Turn OFF LED
            ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            time.sleep(0.005)

            if spectrum is not None:
                peak = find_peak_counts(spectrum)
                all_data[ch]['counts'].append(peak)
                all_data[ch]['acq_times'].append(acq_time)
                print(f"{ch.upper()}:{peak:.0f} ", end='', flush=True)

        cycle_time = (time.perf_counter() - cycle_start) * 1000.0
        cycle_times.append(cycle_time)
        print(f"[{cycle_time:.0f}ms]")

    print()

    # Calculate statistics per channel
    results = {}
    for ch in channels_config.keys():
        if len(all_data[ch]['counts']) == 0:
            results[ch] = None
            continue

        counts = np.array(all_data[ch]['counts'])
        acq_times = np.array(all_data[ch]['acq_times'])

        results[ch] = {
            'mean_counts': np.mean(counts),
            'std_counts': np.std(counts),
            'noise_percent': (np.std(counts) / np.mean(counts)) * 100,
            'mean_acq_time': np.mean(acq_times),
            'std_acq_time': np.std(acq_times),
        }

    results['cycle_times'] = cycle_times
    results['mean_cycle_time'] = np.mean(cycle_times)
    results['std_cycle_time'] = np.std(cycle_times)

    return results


def test_max_speed():
    """Main test function."""

    print("=" * 80)
    print("MAXIMUM SPEED TEST - 50k Counts Target")
    print("=" * 80)
    print("Configuration:")
    print("  Target counts: 50,000 (optimal SNR)")
    print("  Optimize BOTH integration time AND LED intensity per channel")
    print("  Goal: Hit 50k counts with maximum LED efficiency")
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

    # Test each channel
    channels = ['a', 'b', 'c', 'd']
    results = {}

    print("=" * 80)
    print("STEP 1: OPTIMIZE INTEGRATION TIME AND LED INTENSITY")
    print("=" * 80)
    print(f"Target counts: 50,000 (optimal SNR)")
    print(f"Max integration: 300ms")
    print()

    for ch in channels:
        print(f"Channel {ch.upper()}:")
        optimal_led, optimal_int = optimize_led_intensity(detector, ctrl, ch, target_counts=50000, max_integration=300)

        if optimal_led is None or optimal_int is None:
            print(f"  ❌ Failed to optimize Ch {ch}")
            results[ch] = None
        else:
            results[ch] = {
                'led_intensity': optimal_led,
                'integration_time': optimal_int
            }

        print()

    # Measure speed and noise over 20 cycles
    print("=" * 80)
    print("STEP 2: MEASURE SPEED AND NOISE (20 CYCLES)")
    print("=" * 80)
    print()

    # Filter successful channels
    valid_channels = {ch: results[ch] for ch in channels if results[ch] is not None}

    if len(valid_channels) == 0:
        print("❌ No valid channels to test")
        detector.close()
        ctrl.close()
        return False

    metrics = measure_speed_and_noise(detector, ctrl, valid_channels, num_cycles=20)

    # Update results with metrics
    for ch in valid_channels.keys():
        if metrics[ch]:
            results[ch].update(metrics[ch])

    results['cycle_stats'] = {
        'mean_cycle_time': metrics['mean_cycle_time'],
        'std_cycle_time': metrics['std_cycle_time'],
    }

    print()

    # Summary
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    total_time = 0
    all_valid = True

    for ch in channels:
        if results[ch] is None:
            print(f"Channel {ch.upper()}: ❌ FAILED")
            all_valid = False
            continue

        r = results[ch]
        print(f"Channel {ch.upper()}:")
        print(f"  LED intensity: {r['led_intensity']}")
        print(f"  Integration time: {r['integration_time']:.2f} ms")
        print(f"  Peak counts: {r['mean_counts']:.0f} ± {r['std_counts']:.1f}")
        print(f"  Noise: {r['noise_percent']:.2f}%")
        print(f"  Acquisition time: {r['mean_acq_time']:.1f} ms")
        print()

        total_time += r['mean_acq_time']

    # Calculate throughput
    print("=" * 80)
    print("THROUGHPUT ANALYSIS")
    print("=" * 80)

    if all_valid and 'cycle_stats' in results:
        mean_cycle = results['cycle_stats']['mean_cycle_time']
        std_cycle = results['cycle_stats']['std_cycle_time']

        print(f"Mean cycle time: {mean_cycle:.1f} ± {std_cycle:.1f} ms")
        print(f"Throughput: {1000.0/mean_cycle:.2f} Hz")
        print()

        if mean_cycle < 1000:
            speedup = 1000.0 / mean_cycle
            print(f"✅ FASTER THAN 1 Hz: {speedup:.2f}x faster!")
        else:
            print(f"⚠️ Slower than 1 Hz: {mean_cycle/1000.0:.2f}s per cycle")
    else:
        print("❌ Cannot calculate throughput - some channels failed")

    print()

    # Cleanup
    detector.close()
    ctrl.close()
    print("Hardware disconnected")

    return all_valid


if __name__ == "__main__":
    try:
        success = test_max_speed()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
