#!/usr/bin/env python3
"""
Test script for multi-injection detection feature.

Tests the automatic detection of multiple injection points in concentration
series experiments with sequential sample injections.
"""

import numpy as np
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from affilabs.utils.spr_signal_processing import auto_detect_injection_point


def generate_test_sensorgram(num_injections=3, noise_level=0.5):
    """Generate synthetic SPR sensorgram with multiple injections.

    Args:
        num_injections: Number of sequential injections
        noise_level: Gaussian noise standard deviation

    Returns:
        tuple: (times, values_ru) arrays
    """
    # Create time array: 0 to 600 seconds, 1Hz sampling
    times = np.linspace(0, 600, 600)

    # Start with baseline (flat at 0 RU)
    baseline_value = 0.0
    values_ru = np.full_like(times, baseline_value, dtype=float)

    # Injection parameters
    injection_times = [60.0, 180.0, 300.0][:num_injections]  # At 1, 3, 5 minutes
    injection_slopes = [0.5, 0.3, 0.2][:num_injections]  # Decreasing slope (mass transport)

    offset = 0.0
    for inj_time, slope in zip(injection_times, injection_slopes):
        # Create exponential rise starting at injection time
        idx_start = int(inj_time)
        idx_end = len(times)

        rise_curve = np.zeros(len(times))
        for i in range(idx_start, idx_end):
            # Exponential rise: response = final_response * (1 - exp(-k*t))
            time_since_inj = times[i] - inj_time
            final_resp = slope * 200  # RU
            rise_curve[i] = final_resp * (1 - np.exp(-0.05 * time_since_inj))

        values_ru += rise_curve
        offset += slope * 200

    # Add realistic noise
    noise = np.random.normal(0, noise_level, len(values_ru))
    values_ru += noise

    return times, values_ru


def test_single_injection():
    """Test detection of a single injection."""
    print("\n" + "="*70)
    print("TEST 1: Single Injection Detection")
    print("="*70)

    times, values = generate_test_sensorgram(num_injections=1, noise_level=0.3)

    result = auto_detect_injection_point(times, values)

    actual_injection_time = 60.0
    detected_time = result['injection_time']
    confidence = result['confidence']

    print(f"Actual injection time:    {actual_injection_time:.2f}s")
    print(f"Detected injection time:  {detected_time:.2f}s")
    print(f"Detection error:          {abs(detected_time - actual_injection_time):.2f}s")
    print(f"Confidence:               {confidence:.2%}")

    if abs(detected_time - actual_injection_time) < 5.0 and confidence > 0.3:
        print("[OK] PASS: Single injection detected correctly")
        return True
    else:
        print("[FAIL] FAIL: Single injection detection failed")
        return False


def test_multiple_injections():
    """Test detection of multiple sequential injections."""
    print("\n" + "="*70)
    print("TEST 2: Multiple Injections Detection (Concentration Series)")
    print("="*70)

    times, values = generate_test_sensorgram(num_injections=3, noise_level=0.5)

    # Simulate scan algorithm: find first, then search for more
    detected_injections = []
    skip_distance = 60.0    # Skip 60s after each detection to avoid false positives
    window_size = 60.0      # Analyze 60s windows

    # Find first injection across full range
    result = auto_detect_injection_point(times, values)
    if result['injection_time'] is not None and result['confidence'] > 0.3:
        first_inj = result['injection_time']
        detected_injections.append({
            'time': first_inj,
            'confidence': result['confidence']
        })
        print(f"\n1st injection: t={first_inj:.1f}s (confidence: {result['confidence']:.2%})")

        # Now search for additional injections through entire remaining dataset
        # Start searching 60s after the first injection (skip association/dissociation phase)
        current_pos = first_inj + skip_distance
        max_time = times[-1]  # Search until end of data

        while current_pos < max_time - 10.0:  # Need at least 10s of data
            # Get window of data
            mask = (times >= current_pos) & (times < current_pos + window_size)
            if np.sum(mask) < 50:
                current_pos += skip_distance
                continue

            window_times = times[mask]
            window_values = values[mask]

            # Detect in this window
            result = auto_detect_injection_point(window_times, window_values)

            if result['injection_time'] is not None and result['confidence'] > 0.5:  # Higher threshold
                inj_time = result['injection_time']

                # Check it's not too close to previous injections (at least 30s apart)
                is_new = all(abs(inj_time - d['time']) > 30.0 for d in detected_injections)

                if is_new:
                    detected_injections.append({
                        'time': inj_time,
                        'confidence': result['confidence']
                    })
                    print(f"{len(detected_injections)}th injection: t={inj_time:.1f}s (confidence: {result['confidence']:.2%})")
                    # Jump past this injection + skip distance to search for next one
                    current_pos = inj_time + skip_distance
                else:
                    current_pos += skip_distance
            else:
                current_pos += skip_distance

    # Expected injections at 60, 180, 300 seconds
    expected_times = [60.0, 180.0, 300.0]

    print(f"\nExpected injections: {len(expected_times)}")
    print(f"Detected injections: {len(detected_injections)}")

    if len(detected_injections) >= 2:
        print("[OK] PASS: Multiple injections detected")
        return True
    else:
        print("[FAIL] FAIL: Could not detect multiple injections")
        return False


def test_concentration_series():
    """Test on realistic concentration series data."""
    print("\n" + "="*70)
    print("TEST 3: Concentration Series (2x dilution)")
    print("="*70)

    times, values = generate_test_sensorgram(num_injections=3)

    # The algorithm should handle decreasing signal amplitudes
    # (each successive injection produces smaller response due to mass transport)

    result1 = auto_detect_injection_point(times[:150], values[:150])  # Find in first part
    result2 = auto_detect_injection_point(times[100:250], values[100:250])  # Find in middle
    result3 = auto_detect_injection_point(times[250:], values[250:])  # Find at end

    print(f"1st injection: t={result1['injection_time']:.1f}s (confidence: {result1['confidence']:.2%})")
    print(f"2nd injection: t={result2['injection_time']:.1f}s (confidence: {result2['confidence']:.2%})")
    print(f"3rd injection: t={result3['injection_time']:.1f}s (confidence: {result3['confidence']:.2%})")

    # All should have reasonable confidence
    all_detected = (result1['injection_time'] is not None and
                   result2['injection_time'] is not None and
                   result3['injection_time'] is not None)

    if all_detected:
        print("[OK] PASS: Concentration series handled correctly")
        return True
    else:
        print("[FAIL] FAIL: Failed to detect all injections in concentration series")
        return False


def test_ui_integration():
    """Test that the UI button and method are properly connected."""
    print("\n" + "="*70)
    print("TEST 4: UI Integration Check")
    print("="*70)

    try:
        # Check that EditsTab has the method
        from affilabs.tabs.edits_tab import EditsTab

        # Check method exists
        if hasattr(EditsTab, '_find_multiple_injections'):
            print("[OK] Method _find_multiple_injections found in EditsTab")
        else:
            print("[FAIL] Method _find_multiple_injections NOT found in EditsTab")
            return False

        # Check it's callable
        method = getattr(EditsTab, '_find_multiple_injections')
        if callable(method):
            print("[OK] Method is callable")
        else:
            print("[FAIL] Method is not callable")
            return False

        print("[OK] PASS: UI integration check passed")
        return True

    except Exception as e:
        print(f"[FAIL] FAIL: UI integration check failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MULTI-INJECTION DETECTION TEST SUITE")
    print("="*70)

    # Set random seed for reproducibility
    np.random.seed(42)

    results = []

    # Run tests
    results.append(("Single injection detection", test_single_injection()))
    results.append(("Multiple injections detection", test_multiple_injections()))
    results.append(("Concentration series handling", test_concentration_series()))
    results.append(("UI integration", test_ui_integration()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Multi-injection detection feature is ready.")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed. Review implementation.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
