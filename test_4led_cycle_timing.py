"""Test 4-LED SPR Measurement Cycle Timing

Simulates a complete SPR measurement with 4 LEDs, using:
- 22ms integration time
- 4 scans per LED (for SNR improvement)

Each LED measurement:
  4 scans × ~44ms = ~175ms per LED

Full 4-LED cycle:
  4 LEDs × 175ms = ~700ms (0.7 seconds)

This test measures actual timing to see real-world performance.
"""

import time
import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger


def test_4led_cycle():
    """Measure timing for complete 4-LED SPR cycle."""
    print("\n" + "="*80)
    print("4-LED SPR MEASUREMENT CYCLE TIMING TEST")
    print("="*80)
    print("Configuration:")
    print("  • Integration time: 22 ms")
    print("  • Scans per LED: 4 (averaged)")
    print("  • Number of LEDs: 4")
    print("  • Total scans per cycle: 16\n")

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

        # Test parameters
        num_leds = 4
        scans_per_led = 4
        num_cycles = 5  # Test multiple cycles for average

        print("="*80)
        print("RUNNING 4-LED CYCLES")
        print("="*80)

        cycle_times = []
        led_times = []

        for cycle in range(num_cycles):
            print(f"\nCycle {cycle + 1}/{num_cycles}:")

            cycle_start = time.perf_counter()
            led_spectra = []

            for led in range(num_leds):
                led_start = time.perf_counter()

                # Read 4 scans and average (simulating one LED measurement)
                scans = []
                for scan in range(scans_per_led):
                    spectrum = detector.read_intensity()
                    if spectrum is None:
                        print(f"  ❌ Read failed on LED {led+1}, scan {scan+1}")
                        break
                    scans.append(spectrum)

                # Average the scans for this LED
                led_spectrum = np.mean(scans, axis=0)
                led_spectra.append(led_spectrum)

                led_elapsed = (time.perf_counter() - led_start) * 1000
                led_times.append(led_elapsed)

                print(f"  LED {led + 1}: {led_elapsed:.1f} ms ({scans_per_led} scans)")

            cycle_elapsed = (time.perf_counter() - cycle_start) * 1000
            cycle_times.append(cycle_elapsed)

            print(f"  → Total cycle time: {cycle_elapsed:.1f} ms ({cycle_elapsed/1000:.2f} seconds)")

        # Analysis
        print("\n" + "="*80)
        print("TIMING ANALYSIS")
        print("="*80)

        avg_led_time = np.mean(led_times)
        std_led_time = np.std(led_times)
        avg_cycle_time = np.mean(cycle_times)
        std_cycle_time = np.std(cycle_times)

        print(f"\nPer-LED timing ({scans_per_led} scans averaged):")
        print(f"  Average: {avg_led_time:.1f} ms ± {std_led_time:.1f} ms")
        print(f"  Per scan: {avg_led_time/scans_per_led:.1f} ms")

        print("\nFull 4-LED cycle:")
        print(f"  Average: {avg_cycle_time:.1f} ms ({avg_cycle_time/1000:.2f} seconds)")
        print(f"  Std dev: ± {std_cycle_time:.1f} ms")

        # Calculate acquisition rate
        cycles_per_second = 1000 / avg_cycle_time
        cycles_per_minute = cycles_per_second * 60

        print("\nAcquisition rate:")
        print(f"  {cycles_per_second:.2f} complete cycles/second")
        print(f"  {cycles_per_minute:.1f} complete cycles/minute")

        # Time budget breakdown
        print("\n" + "="*80)
        print("TIME BUDGET BREAKDOWN")
        print("="*80)

        total_scans = num_leds * scans_per_led
        integration_time_total = total_scans * 22  # ms
        overhead_total = avg_cycle_time - integration_time_total
        overhead_per_scan = overhead_total / total_scans

        print(f"\nTotal time: {avg_cycle_time:.1f} ms")
        print(f"  Integration time: {integration_time_total} ms ({total_scans} scans × 22 ms)")
        print(f"  USB/readout overhead: {overhead_total:.1f} ms")
        print(f"  Overhead per scan: {overhead_per_scan:.1f} ms")
        print(f"  Overhead percentage: {(overhead_total/avg_cycle_time)*100:.1f}%")

        # Comparison with targets
        print("\n" + "="*80)
        print("PERFORMANCE TARGETS")
        print("="*80)

        print("\nOriginal goal: 8 scans per LED in 180ms")
        print(f"  Actual (4 scans): {avg_led_time:.1f} ms per LED → {'❌ MISSED' if avg_led_time > 180 else '✅ MET'}")
        print(f"  Gap: {avg_led_time - 180:.1f} ms {'too slow' if avg_led_time > 180 else 'under budget'}")

        # Alternative scenarios
        print("\n" + "="*80)
        print("ALTERNATIVE SCENARIOS")
        print("="*80)

        # Scenario 1: 8 scans per LED
        scans_8 = 8
        time_8_scans = (avg_led_time / scans_per_led) * scans_8
        cycle_8_scans = time_8_scans * num_leds

        print("\nScenario 1: 8 scans per LED (√8 = 2.83x SNR)")
        print(f"  Per LED: ~{time_8_scans:.1f} ms → {'✅ MEETS 180ms' if time_8_scans <= 180 else '❌ TOO SLOW'}")
        print(f"  Full cycle: ~{cycle_8_scans:.1f} ms ({cycle_8_scans/1000:.2f} seconds)")
        print(f"  Acquisition rate: {1000/cycle_8_scans:.2f} cycles/second")

        # Scenario 2: Reduce to 3 scans
        scans_3 = 3
        time_3_scans = (avg_led_time / scans_per_led) * scans_3
        cycle_3_scans = time_3_scans * num_leds

        print("\nScenario 2: 3 scans per LED (√3 = 1.73x SNR)")
        print(f"  Per LED: ~{time_3_scans:.1f} ms → {'✅ MEETS 180ms' if time_3_scans <= 180 else '❌ TOO SLOW'}")
        print(f"  Full cycle: ~{cycle_3_scans:.1f} ms ({cycle_3_scans/1000:.2f} seconds)")
        print(f"  Acquisition rate: {1000/cycle_3_scans:.2f} cycles/second")

        # Scenario 2: Reduce integration to 15ms
        int_15ms = 15
        time_15ms = ((int_15ms + overhead_per_scan) * scans_per_led)
        cycle_15ms = time_15ms * num_leds

        print("\nScenario 3: 15ms integration, 4 scans per LED (√4 = 2.0x SNR)")
        print(f"  Per LED: ~{time_15ms:.1f} ms → {'✅ MEETS 180ms' if time_15ms <= 180 else '❌ TOO SLOW'}")
        print(f"  Full cycle: ~{cycle_15ms:.1f} ms ({cycle_15ms/1000:.2f} seconds)")
        print(f"  Acquisition rate: {1000/cycle_15ms:.2f} cycles/second")
        print(f"  ⚠ Signal will be {22/15:.1f}x weaker")

        # Scenario 3: Compromise - 5 scans
        scans_5 = 5
        time_5_scans = (avg_led_time / scans_per_led) * scans_5
        cycle_5_scans = time_5_scans * num_leds

        print("\nScenario 4: 5 scans per LED (√5 = 2.24x SNR)")
        print(f"  Per LED: ~{time_5_scans:.1f} ms → {'✅ MEETS 180ms' if time_5_scans <= 180 else '❌ TOO SLOW'}")
        print(f"  Full cycle: ~{cycle_5_scans:.1f} ms ({cycle_5_scans/1000:.2f} seconds)")
        print(f"  Acquisition rate: {1000/cycle_5_scans:.2f} cycles/second")

        # Recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)

        print("\nCurrent configuration (4 scans, 22ms):")
        print(f"  • Cycle time: {avg_cycle_time/1000:.2f} seconds")
        print(f"  • Rate: {cycles_per_second:.2f} cycles/second")
        print("  • SNR: √4 = 2.0x improvement")

        if avg_led_time <= 180:
            print("\n✅ SUCCESS: 4 scans per LED meets 180ms target!")
            print(f"  • Per LED: {avg_led_time:.1f}ms")
            print(f"  • Cycle time: {avg_cycle_time/1000:.2f} seconds")
            print(f"  • Rate: {cycles_per_second:.2f} cycles/second")
            print("  • SNR: √4 = 2.0x improvement (good for SPR)")
        else:
            print(f"\n⚠ 4 scans takes {avg_led_time:.1f}ms (target: 180ms)")
            print("  • Consider reducing to 3 scans")
            print("  • Or accept slightly longer cycle time")

        print("\n" + "="*80 + "\n")

        detector.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("4-LED cycle test failed")
        raise


if __name__ == "__main__":
    test_4led_cycle()
