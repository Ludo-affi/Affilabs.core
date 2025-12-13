"""Quick test for Sensor IQ classification system."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from affilabs.utils.sensor_iq import classify_spr_quality, SensorIQLevel


def test_sensor_iq():
    """Test sensor IQ classification with various scenarios."""

    print("="*80)
    print("SENSOR IQ CLASSIFICATION SYSTEM - TEST")
    print("="*80)
    print()

    test_cases = [
        # (wavelength, fwhm, expected_level, description)
        (640.0, 25.0, SensorIQLevel.EXCELLENT, "Excellent: Good zone + sharp peak"),
        (645.0, 45.0, SensorIQLevel.GOOD, "Good: Good zone + normal FWHM"),
        (655.0, 70.0, SensorIQLevel.QUESTIONABLE, "Questionable: Good zone + high FWHM"),
        (650.0, 90.0, SensorIQLevel.POOR, "Poor: Good zone + critical FWHM"),
        (575.0, 35.0, SensorIQLevel.QUESTIONABLE, "Questionable: Low edge zone"),
        (705.0, 40.0, SensorIQLevel.QUESTIONABLE, "Questionable: High edge zone"),
        (550.0, 30.0, SensorIQLevel.CRITICAL, "Critical: Out of bounds low"),
        (730.0, 50.0, SensorIQLevel.CRITICAL, "Critical: Out of bounds high"),
        (640.0, None, SensorIQLevel.GOOD, "Good: No FWHM data (unknown quality)"),
    ]

    print("Testing classification scenarios:\n")

    passed = 0
    failed = 0

    for i, (wavelength, fwhm, expected, description) in enumerate(test_cases, 1):
        iq = classify_spr_quality(wavelength, fwhm, channel='test')

        status = "[OK] PASS" if iq.iq_level == expected else "[ERROR] FAIL"
        if iq.iq_level == expected:
            passed += 1
        else:
            failed += 1

        print(f"Test {i}: {status}")
        print(f"  Scenario: {description}")
        print(f"  Input: λ={wavelength:.1f}nm, FWHM={fwhm if fwhm else 'N/A'}")
        print(f"  Expected: {expected.value}")
        print(f"  Got: {iq.iq_level.value}")
        print(f"  Zone: {iq.zone.value}")
        print(f"  Quality Score: {iq.quality_score:.2f}")

        if iq.warning_message:
            print(f"  Warning: {iq.warning_message}")
        if iq.recommendation:
            print(f"  Recommendation: {iq.recommendation}")

        print()

    print("="*80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("="*80)
    print()

    # Test zone boundaries
    print("Testing zone boundary precision:\n")

    boundary_tests = [
        (559.9, "OUT_OF_BOUNDS_LOW"),
        (560.0, "QUESTIONABLE_LOW"),
        (589.9, "QUESTIONABLE_LOW"),
        (590.0, "GOOD"),
        (689.9, "GOOD"),
        (690.0, "QUESTIONABLE_HIGH"),
        (719.9, "QUESTIONABLE_HIGH"),
        (720.0, "OUT_OF_BOUNDS_HIGH"),
    ]

    for wavelength, expected_zone in boundary_tests:
        iq = classify_spr_quality(wavelength, 40.0)
        actual_zone = iq.zone.name
        status = "[OK]" if actual_zone == expected_zone else "[ERROR]"
        print(f"{status} λ={wavelength:.1f}nm → {actual_zone} (expected: {expected_zone})")

    print()

    # Test FWHM thresholds
    print("Testing FWHM quality thresholds:\n")

    fwhm_tests = [
        (25.0, "excellent"),
        (30.0, "good"),
        (45.0, "good"),
        (60.0, "poor"),
        (75.0, "poor"),
        (85.0, "critical"),
    ]

    for fwhm, expected_category in fwhm_tests:
        iq = classify_spr_quality(640.0, fwhm)  # Good wavelength zone
        # Extract FWHM category from IQ level
        if iq.iq_level == SensorIQLevel.EXCELLENT:
            actual_category = "excellent"
        elif iq.iq_level == SensorIQLevel.GOOD:
            actual_category = "good"
        elif iq.iq_level == SensorIQLevel.QUESTIONABLE:
            actual_category = "poor"
        else:
            actual_category = "critical"

        status = "[OK]" if actual_category == expected_category else "[ERROR]"
        print(f"{status} FWHM={fwhm:.1f}nm → {actual_category} (expected: {expected_category})")

    print()
    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    test_sensor_iq()
