"""
Test: Fixed integration time with variable LED intensity
Compare against variable integration with fixed LED=255

Goal: Determine best approach for 50k counts target
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
    """Find maximum counts in spectrum"""
    return np.max(spectrum)

def optimize_led_for_fixed_integration(detector, ctrl, channel, target_counts=50000, integration_time=30.0):
    """Find LED intensity that gives target counts at fixed integration time.

    Args:
        detector: USB4000 detector instance
        ctrl: PicoP4SPR controller instance
        channel: Channel letter ('a', 'b', 'c', 'd')
        target_counts: Target peak counts (default 50000)
        integration_time: Fixed integration time in ms

    Returns:
        Optimal LED intensity (0-255), or None if failed
    """
    print(f"  Optimizing Ch {channel} at fixed {integration_time}ms integration...")

    # Set integration time (fixed)
    detector.set_integration(integration_time)
    time.sleep(0.01)

    # Start at maximum intensity
    intensity = 255
    led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    led_values[channel] = intensity
    ctrl.set_batch_intensities(**led_values)
    time.sleep(0.02)

    # Read initial signal
    spectrum = detector.read_intensity()
    if spectrum is None:
        print(f"    ❌ Failed to acquire spectrum")
        return None

    peak_counts = find_peak_counts(spectrum)
    print(f"    Initial: LED=255 → {peak_counts:.0f} counts")

    # Check if saturated
    if peak_counts >= 65535:
        print(f"    ⚠️ Saturated - need shorter integration time")
        return None

    # Check if too dim even at max
    if peak_counts < target_counts * 0.5:
        print(f"    ⚠️ Too dim at LED=255 - need longer integration time")
        return None

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
    print(f"    ✅ Final: LED={intensity} → {peak_counts:.0f} counts ({error_pct:+.1f}%)")

    # Turn OFF LED
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.01)

    return intensity

def measure_speed_and_noise(detector, ctrl, channels_config, num_cycles=20):
    """Measure cycle time and noise with optimized settings"""
    print(f"\n  Running {num_cycles} complete cycles (A→B→C→D)...\n")

    channels = ['a', 'b', 'c', 'd']
    data = {ch: [] for ch in channels}
    cycle_times = []
    acquisition_times = {ch: [] for ch in channels}

    for cycle in range(num_cycles):
        cycle_start = time.perf_counter()
        print(f"  Cycle {cycle+1}/{num_cycles}: ", end='', flush=True)

        for ch in channels:
            if channels_config[ch] is None:
                continue

            # Set integration time for this channel
            integration_time = channels_config[ch]['integration_time']
            detector.set_integration(integration_time)
            time.sleep(0.005)

            # Turn on LED with optimized intensity
            led_intensity = channels_config[ch]['led_intensity']
            led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
            led_values[ch] = led_intensity
            ctrl.set_batch_intensities(**led_values)
            time.sleep(0.012)  # PRE delay

            # Acquire
            acq_start = time.perf_counter()
            spectrum = detector.read_intensity()
            acq_time = (time.perf_counter() - acq_start) * 1000
            acquisition_times[ch].append(acq_time)

            if spectrum is not None:
                peak = find_peak_counts(spectrum)
                data[ch].append(peak)
                print(f"{ch.upper()}:{peak:.0f} ", end='', flush=True)

            # Turn off LED
            ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            time.sleep(0.040)  # POST delay

        cycle_time = (time.perf_counter() - cycle_start) * 1000
        cycle_times.append(cycle_time)
        print(f"[{cycle_time:.0f}ms]")

    return data, cycle_times, acquisition_times

def main():
    print("=" * 80)
    print("TEST: FIXED INTEGRATION vs VARIABLE LED")
    print("=" * 80)
    print(f"Goal: Compare fixed integration (30ms) + variable LED")
    print(f"      vs variable integration + fixed LED (255)")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Initializing controller...")
    ctrl = PicoP4SPR()
    if not ctrl.open():
        print("❌ Failed to connect to controller")
        return
    print("✅ Connected to controller")

    print("Initializing detector...")
    detector = USB4000()
    if not detector.open():
        print("❌ Failed to connect to detector")
        ctrl.close()
        return
    print("✅ Connected to detector")
    print()

    # Test different fixed integration times
    test_integrations = [25, 30, 35, 40]

    for fixed_int in test_integrations:
        print("=" * 80)
        print(f"TESTING: Fixed Integration = {fixed_int}ms, Variable LED")
        print("=" * 80)
        print()

        channels = ['a', 'b', 'c', 'd']
        results = {}

        # Step 1: Optimize LED for each channel
        all_success = True
        for ch in channels:
            print(f"Channel {ch.upper()}:")
            optimal_led = optimize_led_for_fixed_integration(
                detector, ctrl, ch,
                target_counts=50000,
                integration_time=fixed_int
            )

            if optimal_led is None:
                print(f"  ❌ Failed to optimize Ch {ch}")
                results[ch] = None
                all_success = False
            else:
                results[ch] = {
                    'led_intensity': optimal_led,
                    'integration_time': fixed_int
                }
            print()

        if not all_success:
            print(f"⚠️ Skipping speed test - optimization failed\n")
            continue

        # Step 2: Measure speed and noise
        print("=" * 80)
        print("STEP 2: MEASURE SPEED AND NOISE (20 CYCLES)")
        print("=" * 80)

        data, cycle_times, acq_times = measure_speed_and_noise(detector, ctrl, results, num_cycles=20)

        # Step 3: Analyze results
        print("\n" + "=" * 80)
        print(f"RESULTS: Integration={fixed_int}ms Fixed")
        print("=" * 80)
        print()

        for ch in channels:
            if results[ch] is None:
                continue

            r = results[ch]
            ch_data = np.array(data[ch])
            mean_counts = np.mean(ch_data)
            std_counts = np.std(ch_data)
            noise_pct = (std_counts / mean_counts) * 100
            mean_acq = np.mean(acq_times[ch])

            print(f"Channel {ch.upper()}:")
            print(f"  LED intensity: {r['led_intensity']}")
            print(f"  Integration: {r['integration_time']:.2f} ms")
            print(f"  Peak counts: {mean_counts:.0f} ± {std_counts:.1f}")
            print(f"  Noise: {noise_pct:.2f}%")
            print(f"  Acquisition time: {mean_acq:.1f} ms")
            print()

        mean_cycle = np.mean(cycle_times)
        std_cycle = np.std(cycle_times)
        throughput = 1000 / mean_cycle

        print("=" * 80)
        print("THROUGHPUT ANALYSIS")
        print("=" * 80)
        print(f"Mean cycle time: {mean_cycle:.1f} ± {std_cycle:.1f} ms")
        print(f"Throughput: {throughput:.2f} Hz")
        print()
        if throughput > 1.0:
            print(f"✅ FASTER THAN 1 Hz: {throughput:.2f}x faster!")
        else:
            print(f"⚠️ SLOWER THAN 1 Hz: {throughput:.2f}x")
        print()

    # Cleanup
    print("Hardware disconnected")
    detector.close()
    ctrl.close()

if __name__ == '__main__':
    main()
