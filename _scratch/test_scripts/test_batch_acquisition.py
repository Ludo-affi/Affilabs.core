"""Test optimized batch acquisition vs individual reads.

This test compares:
1. Multiple read_intensity() calls (current method)
2. read_intensity_batch() with tight loop (optimized method)

Goal: Minimize USB command overhead by reading scans in rapid succession
without extra delays between reads.
"""

import time
import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger


def test_batch_optimization():
    """Compare batch vs individual read performance."""
    print("\n" + "="*80)
    print("BATCH ACQUISITION OPTIMIZATION TEST")
    print("="*80)
    print("Goal: Reduce USB overhead by reading scans in tight loop\n")

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

        num_scans = 8
        num_iterations = 10

        # Test 1: Individual reads (current method)
        print("="*80)
        print("TEST 1: Individual read_intensity() calls")
        print("="*80)
        print(f"  Reading {num_scans} scans separately, {num_iterations} times...\n")

        individual_times = []

        for iteration in range(num_iterations):
            t_start = time.perf_counter()

            scans = []
            for i in range(num_scans):
                spectrum = detector.read_intensity()
                if spectrum is None:
                    print(f"  ❌ Read failed on iteration {iteration+1}")
                    break
                scans.append(spectrum)
            else:
                # Average
                averaged = np.mean(scans, axis=0)

                t_elapsed = (time.perf_counter() - t_start) * 1000
                individual_times.append(t_elapsed)

                if iteration < 3:
                    print(f"  Iteration {iteration+1}: {t_elapsed:.1f}ms ({t_elapsed/num_scans:.1f}ms per scan)")

        avg_individual = np.mean(individual_times)
        std_individual = np.std(individual_times)

        print(f"\n  Average: {avg_individual:.1f} ms ± {std_individual:.1f} ms")
        print(f"  Per scan: {avg_individual/num_scans:.1f} ms")

        # Test 2: Batch read (optimized)
        print("\n" + "="*80)
        print("TEST 2: read_intensity_batch() with tight loop")
        print("="*80)
        print(f"  Reading {num_scans} scans in batch, {num_iterations} times...\n")

        batch_times = []

        for iteration in range(num_iterations):
            t_start = time.perf_counter()

            averaged = detector.read_intensity_batch(num_scans)

            if averaged is None:
                print(f"  ❌ Batch read failed on iteration {iteration+1}")
                continue

            t_elapsed = (time.perf_counter() - t_start) * 1000
            batch_times.append(t_elapsed)

            if iteration < 3:
                print(f"  Iteration {iteration+1}: {t_elapsed:.1f}ms ({t_elapsed/num_scans:.1f}ms per scan)")

        avg_batch = np.mean(batch_times)
        std_batch = np.std(batch_times)

        print(f"\n  Average: {avg_batch:.1f} ms ± {std_batch:.1f} ms")
        print(f"  Per scan: {avg_batch/num_scans:.1f} ms")

        # Analysis
        print("\n" + "="*80)
        print("PERFORMANCE COMPARISON")
        print("="*80)

        speedup = avg_individual / avg_batch
        time_saved = avg_individual - avg_batch
        percent_faster = (time_saved / avg_individual) * 100

        print(f"\n  Individual reads: {avg_individual:.1f} ms")
        print(f"  Batch reads:      {avg_batch:.1f} ms")
        print(f"  Time saved:       {time_saved:.1f} ms ({percent_faster:.1f}% faster)")
        print(f"  Speedup:          {speedup:.2f}x")

        # Check if we meet 180ms target
        print("\n" + "="*80)
        print("TARGET ANALYSIS")
        print("="*80)

        target_ms = 180

        print(f"\n  Target: {num_scans} scans in {target_ms} ms")
        print(f"  Individual method: {avg_individual:.1f} ms → {'❌ TOO SLOW' if avg_individual > target_ms else '✅ MEETS TARGET'}")
        print(f"  Batch method:      {avg_batch:.1f} ms → {'❌ TOO SLOW' if avg_batch > target_ms else '✅ MEETS TARGET'}")

        if avg_batch <= target_ms:
            print(f"\n  🎉 SUCCESS! Batch method achieves {num_scans} scans in {avg_batch:.1f}ms")
            throughput = 1000 / avg_batch
            print(f"  Throughput: ~{throughput:.1f} averaged spectra/second")
        else:
            # Calculate how many scans we can do in 180ms
            max_scans = int(target_ms / (avg_batch / num_scans))
            print(f"\n  ⚠ Batch method still too slow for {num_scans} scans")
            print(f"  Can do {max_scans} scans in ~{target_ms}ms")
            print(f"  SNR improvement: √{max_scans} = {np.sqrt(max_scans):.2f}x")

        # Recommendations
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)

        if speedup > 1.1:
            print(f"\n  ✅ Batch method is {percent_faster:.0f}% faster - USE IT!")
            print("  • Replace individual read loops with read_intensity_batch()")
            print("  • Update acquisition manager to use batch method")
        else:
            print(f"\n  ⚠ Batch method only {percent_faster:.1f}% faster")
            print("  • USB overhead may not be the bottleneck")
            print("  • Consider reducing integration time or number of scans")

        print("\n" + "="*80 + "\n")

        detector.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("Batch optimization test failed")
        raise


if __name__ == "__main__":
    test_batch_optimization()
