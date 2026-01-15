"""
Test LED cycle speed for P4PRO batch mode.
Target: 250ms per LED × 4 channels = 1000ms per cycle
"""

import time
import sys
from affilabs.utils.controller import PicoP4PRO

def test_led_cycle_speed():
    print("Testing P4PRO LED cycle speed...")
    print("Target: 250ms per LED, 1000ms per 4-channel cycle\n")

    # Connect to P4PRO
    ctrl = PicoP4PRO()
    if not ctrl.open():
        print("ERROR: Failed to connect to P4PRO")
        return False

    print(f"Connected to P4PRO")
    print(f"Firmware: {ctrl.version}\n")

    # Test parameters
    channels = ['a', 'b', 'c', 'd']
    num_cycles = 5
    detector_wait_ms = 45  # Reduced to compensate for ~15ms turn_on overhead
    led_on_time_ms = 240   # Target LED on time (reduced from 250ms)

    print(f"Running {num_cycles} cycles with {len(channels)} channels each...")
    print(f"LED ON time target: {led_on_time_ms}ms")
    print(f"Detector wait: {detector_wait_ms}ms\n")

    # Set all LED intensities once using batch command (like production code)
    print("Setting LED intensities using set_batch_intensities()...")
    setup_start = time.perf_counter()
    ctrl.set_batch_intensities(a=200, b=200, c=200, d=200)
    setup_time = (time.perf_counter() - setup_start) * 1000
    print(f"Batch intensity setup took: {setup_time:.1f}ms\n")

    cycle_times = []

    for cycle in range(num_cycles):
        cycle_start = time.perf_counter()

        for ch in channels:
            led_on_start = time.perf_counter()

            # Turn on LED
            turn_on_start = time.perf_counter()
            success = ctrl.turn_on_channel(ch=ch)
            turn_on_time = (time.perf_counter() - turn_on_start) * 1000

            if not success:
                print(f"WARNING: turn_on_channel({ch}) failed")

            # Wait for detector
            time.sleep(detector_wait_ms / 1000.0)

            # Simulate detector read time (typical: ~180ms for 8 scans)
            time.sleep(0.180)

            # Enforce LED on time
            elapsed_since_led_on = (time.perf_counter() - led_on_start) * 1000
            remaining_time_ms = max(0, led_on_time_ms - elapsed_since_led_on)
            if remaining_time_ms > 0:
                time.sleep(remaining_time_ms / 1000.0)

            actual_led_time = (time.perf_counter() - led_on_start) * 1000

            # Log first cycle details
            if cycle == 0:
                print(f"  Ch {ch.upper()}: turn_on={turn_on_time:.1f}ms, total={actual_led_time:.1f}ms (target={led_on_time_ms}ms)")

        cycle_time = (time.perf_counter() - cycle_start) * 1000
        cycle_times.append(cycle_time)
        print(f"Cycle {cycle + 1}: {cycle_time:.1f}ms")

    # Statistics
    avg_cycle_time = sum(cycle_times) / len(cycle_times)
    min_cycle_time = min(cycle_times)
    max_cycle_time = max(cycle_times)

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Target cycle time: 1000ms (250ms × 4 LEDs)")
    print(f"  Average cycle time: {avg_cycle_time:.1f}ms")
    print(f"  Min cycle time: {min_cycle_time:.1f}ms")
    print(f"  Max cycle time: {max_cycle_time:.1f}ms")
    print(f"  Variance: {max_cycle_time - min_cycle_time:.1f}ms")

    # Check if within acceptable range (±10%)
    target = 1000.0
    tolerance = 0.10  # 10%
    lower_bound = target * (1 - tolerance)
    upper_bound = target * (1 + tolerance)

    if lower_bound <= avg_cycle_time <= upper_bound:
        print(f"\n✓ PASS: Cycle time within ±{tolerance*100:.0f}% of target")
        print(f"  ({lower_bound:.0f}ms - {upper_bound:.0f}ms)")
        result = True
    else:
        print(f"\n✗ FAIL: Cycle time outside acceptable range")
        print(f"  Expected: {lower_bound:.0f}ms - {upper_bound:.0f}ms")
        print(f"  Got: {avg_cycle_time:.1f}ms")
        result = False

    ctrl.close()
    return result

if __name__ == "__main__":
    try:
        success = test_led_cycle_speed()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
