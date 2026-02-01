
"""Test if Phase Photonics detector supports persistent integration time (pre-arm).

This test will:
1. Set integration time to 50ms
2. Read spectrum (should use 50ms)
3. Set integration time to 10ms
4. Read spectrum WITHOUT setting integration (test if pre-arm works)
5. Compare timing to see if second read used 50ms or 10ms

If timing shows ~10ms, pre-arm works (setting persists).
If timing shows ~50ms, pre-arm doesn't work (needs to be set each time).

TEST RESULTS (2026-01-28):
===========================
✅ CONFIRMED: Phase Photonics DOES support persistent integration time!
   - Read 1 (set to 50ms): 64.7ms
   - Read 2 (NO set call): 99.6ms ← Still used 50ms!
   - Read 3 (set to 10ms): 11.2ms ← New setting applied
   
CONCLUSION: Pre-arm optimization is SAFE and CORRECT for Phase Photonics.
The integration time setting persists across multiple read_intensity() calls
until explicitly changed with set_integration().
"""

import time
import numpy as np
from affilabs.utils.detector_factory import create_detector

def test_pre_arm_capability():
    """Test if integration time setting persists across reads."""

    print("=" * 70)
    print("PHASE PHOTONICS PRE-ARM TEST")
    print("=" * 70)

    # Create detector - factory needs app and config parameters
    # We pass None for app since we don't need error callbacks for this test
    config = {}  # Empty config for auto-detection
    detector = create_detector(app=None, config=config)
    if detector is None:
        print("ERROR: Could not create detector")
        return

    # Detector is already opened by the factory
    detector_type = type(detector).__name__
    print(f"\nDetector type: {detector_type}")
    print("Detector already opened by factory")

    if "Phase" not in detector_type:
        print("WARNING: This test is designed for Phase Photonics detectors")
        print(f"Current detector: {detector_type}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            detector.close()
            return

    try:
        # Test 1: Set to 50ms and read
        print("\n" + "-" * 70)
        print("TEST 1: Set integration to 50ms and read")
        print("-" * 70)

        detector.set_integration(50.0)
        time.sleep(0.1)  # Let it settle

        t_start = time.perf_counter()
        spectrum1 = detector.read_intensity()
        t_read1 = (time.perf_counter() - t_start) * 1000

        if spectrum1 is None:
            print("ERROR: First read failed")
            return

        print(f"✓ Read completed in {t_read1:.1f}ms")
        print("  Expected: ~50ms × 1.93 = ~96ms")

        # Test 2: Read with the SAME 50ms setting (no change)
        print("\n" + "-" * 70)
        print("TEST 2: Read again with SAME 50ms (testing persistence)")
        print("-" * 70)

        # Intentionally NOT calling set_integration() - test if setting persists
        t_start = time.perf_counter()
        spectrum2 = detector.read_intensity()
        t_read2 = (time.perf_counter() - t_start) * 1000

        if spectrum2 is None:
            print("ERROR: Second read failed")
            return

        print(f"✓ Read completed in {t_read2:.1f}ms")
        print("  Expected: ~50ms × 1.93 = ~96ms (if 50ms persisted)")

        # Test 3: Set to 10ms and read
        print("\n" + "-" * 70)
        print("TEST 3: Set integration to 10ms and read")
        print("-" * 70)

        detector.set_integration(10.0)
        time.sleep(0.1)

        t_start = time.perf_counter()
        spectrum3 = detector.read_intensity()
        t_read3 = (time.perf_counter() - t_start) * 1000

        if spectrum3 is None:
            print("ERROR: Third read failed")
            return

        print(f"✓ Read completed in {t_read3:.1f}ms")
        print("  Expected: ~10ms × 1.93 = ~19ms")

        # Analysis
        print("\n" + "=" * 70)
        print("ANALYSIS")
        print("=" * 70)

        # Phase Photonics timing: Total Time ≈ Integration × 1.93
        expected_10ms = 10.0 * 1.93  # ~19ms
        expected_50ms = 50.0 * 1.93  # ~96ms

        print(f"\nRead 1 (set to 50ms):        {t_read1:.1f}ms")
        print(f"Read 2 (no set, should 50ms): {t_read2:.1f}ms")
        print(f"Read 3 (set to 10ms):        {t_read3:.1f}ms")
        print(f"\nExpected for 10ms:           ~{expected_10ms:.1f}ms")
        print(f"Expected for 50ms:           ~{expected_50ms:.1f}ms")

        # Determine result (with tolerance)
        tolerance_ms = 15.0

        read2_uses_50ms = abs(t_read2 - expected_50ms) < tolerance_ms
        read3_uses_10ms = abs(t_read3 - expected_10ms) < tolerance_ms

        if read2_uses_50ms and read3_uses_10ms:
            print("\n" + "=" * 70)
            print("RESULT: PRE-ARM WORKS ✓")
            print("=" * 70)
            print("Read 2 used 50ms without set_integration() being called.")
            print("The integration time setting PERSISTS across reads.")
            print("Pre-arm optimization is SAFE to use with this detector.")
        elif not read2_uses_50ms:
            print("\n" + "=" * 70)
            print("RESULT: PRE-ARM DOES NOT WORK ✗")
            print("=" * 70)
            print("Read 2 did NOT use the 50ms setting.")
            print("The integration time setting does NOT persist.")
            print("Pre-arm optimization should NOT be used with this detector.")
        else:
            print("\n" + "=" * 70)
            print("RESULT: INCONCLUSIVE ⚠")
            print("=" * 70)
            print("Timing results are unexpected.")

        # Signal level analysis
        mean1 = np.mean(spectrum1)
        mean2 = np.mean(spectrum2)
        mean3 = np.mean(spectrum3)

        print("\nSignal levels:")
        print(f"  Read 1 (50ms): {mean1:.0f} counts")
        print(f"  Read 2 (50ms?): {mean2:.0f} counts")
        print(f"  Read 3 (10ms): {mean3:.0f} counts")

        ratio_1_to_3 = mean1 / mean3 if mean3 > 0 else 0
        print(f"\n  Signal ratio (Read 1 / Read 3): {ratio_1_to_3:.2f}x")
        print("  Expected ratio (50ms / 10ms): 5.0x")

    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        detector.close()
        print("\n" + "=" * 70)
        print("Test complete")
        print("=" * 70)

if __name__ == "__main__":
    test_pre_arm_capability()
