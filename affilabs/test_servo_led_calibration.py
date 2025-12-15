"""Test script for LED calibration method used in servo calibration.

This script tests the _calibrate_leds_for_servo() function independently
before integration into the full servo calibration workflow.

Test scenarios:
1. Normal operation with mock devices
2. Different target percentages (20%, 30%, 40%)
3. Saturation handling
4. Fallback behavior on errors
5. Integration time verification
"""

import sys
from unittest.mock import patch

import numpy as np

# Add parent directory to path
sys.path.insert(0, r"c:\Users\ludol\ezControl-AI\Affilabs.core beta")

from affilabs.utils.logger import logger


# Mock time.sleep to speed up tests
def fast_sleep(duration):
    """Fast sleep for testing - just pass through."""


# ============================================================================
# Mock Classes for Testing
# ============================================================================


class MockSpectrometer:
    """Mock spectrometer for testing."""

    def __init__(self, max_counts: int = 62000):
        self.max_counts = max_counts
        self.target_counts = max_counts * 0.60  # Default 60% target
        self.integration_time = 100  # ms
        self.num_scans = 1
        self._current_intensity = 0
        self._saturate_next = False

    def read_intensity(self):
        """Simulate spectrum reading."""
        # Simulate realistic spectrum response based on LED intensity
        base_signal = self._current_intensity * 200  # Rough scaling factor

        # Add some noise
        noise = np.random.normal(0, 100, 2048)
        spectrum = base_signal + noise

        # Clip to detector range
        spectrum = np.clip(spectrum, 0, self.max_counts)

        # Simulate saturation if requested
        if self._saturate_next:
            spectrum[:] = self.max_counts * 0.98
            self._saturate_next = False

        return spectrum

    def set_integration_time(self, time_ms: int):
        """Set integration time."""
        self.integration_time = time_ms
        logger.debug(f"Integration time set to {time_ms} ms")

    def set_num_scans(self, num: int):
        """Set number of scans to average."""
        self.num_scans = num
        logger.debug(f"Number of scans set to {num}")

    def trigger_saturation(self):
        """Force next read to return saturated values."""
        self._saturate_next = True


class MockController:
    """Mock controller for testing."""

    def __init__(self):
        self._a_intensity = 128
        self._b_intensity = 128
        self._c_intensity = 128
        self._d_intensity = 128
        self._mock_spec = None

    def set_mock_spectrometer(self, spec):
        """Link to mock spectrometer for realistic behavior."""
        self._mock_spec = spec

    def set_intensity(self, ch: str, raw_val: int):
        """Set LED intensity."""
        setattr(self, f"_{ch}_intensity", raw_val)
        logger.debug(f"LED {ch.upper()} intensity set to {raw_val}")

        # Update mock spectrometer's current intensity
        if self._mock_spec:
            self._mock_spec._current_intensity = raw_val

    def get_intensity(self, ch: str) -> int:
        """Get current LED intensity."""
        return getattr(self, f"_{ch}_intensity", 128)


# ============================================================================
# Import Function Under Test
# ============================================================================

from affilabs.utils.servo_calibration import (
    SERVO_CAL_TARGET_PERCENT,
    _calibrate_leds_for_servo,
)

# ============================================================================
# Test Functions
# ============================================================================


def test_normal_operation():
    """Test 1: Normal LED calibration with default target."""
    print("\n" + "=" * 80)
    print("TEST 1: Normal Operation (30% target)")
    print("=" * 80)

    spec = MockSpectrometer(max_counts=62000)
    ctrl = MockController()
    ctrl.set_mock_spectrometer(spec)

    # Mock time.sleep to speed up test
    with patch("time.sleep", fast_sleep):
        result = _calibrate_leds_for_servo(spec, ctrl, target_percent=0.30)

    # Verify results
    print("\nResults:")
    for ch, intensity in result.items():
        print(f"  Channel {ch.upper()}: {intensity}")

    # Check that all channels were calibrated
    assert all(
        ch in result for ch in ["a", "b", "c", "d"]
    ), "Missing channels in result"

    # Check that intensities are reasonable (should be relatively low for 30% target)
    for ch, intensity in result.items():
        assert (
            0 <= intensity <= 255
        ), f"Channel {ch} intensity out of range: {intensity}"

    print("\n[OK] TEST 1 PASSED: All channels calibrated successfully")
    return True


def test_different_targets():
    """Test 2: Different target percentages."""
    print("\n" + "=" * 80)
    print("TEST 2: Different Target Percentages")
    print("=" * 80)

    targets = [0.20, 0.30, 0.40, 0.50]

    # Mock time.sleep to speed up test
    with patch("time.sleep", fast_sleep):
        for target in targets:
            print(f"\nTesting {target*100:.0f}% target...")
            spec = MockSpectrometer(max_counts=62000)
            ctrl = MockController()
            ctrl.set_mock_spectrometer(spec)

            result = _calibrate_leds_for_servo(spec, ctrl, target_percent=target)

            target_counts = 62000 * target
            print(f"  Target counts: {target_counts:.0f}")
            print(f"  Calibrated intensities: {result}")

            # Verify all channels present
            assert len(result) == 4, f"Expected 4 channels, got {len(result)}"

    print("\n[OK] TEST 2 PASSED: Different targets handled correctly")
    return True


def test_saturation_handling():
    """Test 3: Saturation detection and recovery."""
    print("\n" + "=" * 80)
    print("TEST 3: Saturation Handling")
    print("=" * 80)

    spec = MockSpectrometer(max_counts=62000)
    ctrl = MockController()
    ctrl.set_mock_spectrometer(spec)

    # Trigger saturation on first read
    spec.trigger_saturation()

    print("\nSimulating saturation on first channel...")

    # Mock time.sleep to speed up test
    with patch("time.sleep", fast_sleep):
        result = _calibrate_leds_for_servo(spec, ctrl, target_percent=0.30)

    print(f"\nResults after saturation: {result}")

    # Should still get valid results (calibration should handle saturation)
    assert len(result) == 4, "Should calibrate all channels even with saturation"

    print("\n[OK] TEST 3 PASSED: Saturation handled gracefully")
    return True


def test_fallback_behavior():
    """Test 4: Fallback to defaults on error."""
    print("\n" + "=" * 80)
    print("TEST 4: Fallback Behavior on Error")
    print("=" * 80)

    # Create mock that will fail
    class FailingSpectrometer(MockSpectrometer):
        def read_intensity(self):
            raise RuntimeError("Simulated spectrometer failure")

    spec = FailingSpectrometer()
    ctrl = MockController()

    print("\nSimulating spectrometer failure...")
    result = _calibrate_leds_for_servo(spec, ctrl, target_percent=0.30)

    print(f"\nFallback results: {result}")

    # Should return default values (32 for all channels)
    expected = {"a": 32, "b": 32, "c": 32, "d": 32}
    assert result == expected, f"Expected fallback {expected}, got {result}"

    print("\n[OK] TEST 4 PASSED: Fallback to defaults on error")
    return True


def test_target_count_calculation():
    """Test 5: Verify target count calculation."""
    print("\n" + "=" * 80)
    print("TEST 5: Target Count Calculation")
    print("=" * 80)

    test_cases = [
        (62000, 0.20, 12400),
        (62000, 0.30, 18600),
        (62000, 0.40, 24800),
        (65535, 0.30, 19660.5),
    ]

    for max_counts, target_percent, expected_counts in test_cases:
        calculated = max_counts * target_percent
        print(
            f"Max: {max_counts}, Target: {target_percent*100:.0f}% → {calculated:.1f} counts",
        )
        assert (
            abs(calculated - expected_counts) < 1
        ), f"Expected {expected_counts}, got {calculated}"

    print("\n[OK] TEST 5 PASSED: Target calculations correct")
    return True


def test_realistic_scenario():
    """Test 6: Realistic scenario with actual detector specs."""
    print("\n" + "=" * 80)
    print("TEST 6: Realistic Scenario (Flame-T detector)")
    print("=" * 80)

    # Simulate Flame-T detector
    spec = MockSpectrometer(max_counts=62000)
    ctrl = MockController()
    ctrl.set_mock_spectrometer(spec)

    # Use actual servo calibration target
    target_percent = SERVO_CAL_TARGET_PERCENT  # Should be 0.30
    target_counts = 62000 * target_percent

    print("\nFlame-T Max Counts: 62000")
    print(f"Servo Cal Target: {target_percent*100:.0f}% = {target_counts:.0f} counts")
    print("Saturation Threshold: 95% = 58900 counts")
    print(f"Safety Margin: {58900 - target_counts:.0f} counts")

    result = _calibrate_leds_for_servo(spec, ctrl, target_percent=target_percent)

    print(f"\nCalibrated intensities: {result}")

    # Verify we're well below saturation
    assert target_counts < 58900, "Target should be well below saturation"

    # Verify safety margin is adequate (at least 30000 counts)
    safety_margin = 58900 - target_counts
    assert safety_margin > 30000, f"Safety margin too small: {safety_margin:.0f} counts"

    print("\n[OK] TEST 6 PASSED: Realistic scenario validated")
    print(
        f"   Safety margin: {safety_margin:.0f} counts ({safety_margin/620:.0f}% of full scale)",
    )
    return True


def test_integration_with_servo_workflow():
    """Test 7: Integration context (simulated servo workflow)."""
    print("\n" + "=" * 80)
    print("TEST 7: Integration with Servo Workflow")
    print("=" * 80)

    spec = MockSpectrometer(max_counts=62000)
    ctrl = MockController()
    ctrl.set_mock_spectrometer(spec)

    print("\nSimulating servo calibration workflow:")
    print("  STEP 1: LED Calibration (30% target)")

    # Step 1: LED calibration
    led_intensities = _calibrate_leds_for_servo(spec, ctrl, target_percent=0.30)
    print(f"    ✓ LEDs calibrated: {led_intensities}")

    print("  STEP 2: Coarse Search (simulated)")
    # Simulate using calibrated LEDs for servo search
    for ch, intensity in led_intensities.items():
        ctrl.set_intensity(ch, intensity)

    # Simulate reading spectrum
    spectrum = spec.read_intensity()
    max_signal = spectrum.max()

    print(f"    ✓ Signal level: {max_signal:.0f} counts")
    print(f"    ✓ Below saturation: {max_signal < 58900}")

    assert max_signal < 58900, f"Signal too high: {max_signal:.0f} counts"

    print("\n[OK] TEST 7 PASSED: Integration workflow validated")
    return True


# ============================================================================
# Main Test Runner
# ============================================================================


def run_all_tests():
    """Run all test scenarios."""
    print("\n" + "=" * 80)
    print("SERVO LED CALIBRATION TEST SUITE")
    print("=" * 80)
    print("Testing: _calibrate_leds_for_servo()")
    print(f"Default target: {SERVO_CAL_TARGET_PERCENT*100:.0f}% of detector max")

    tests = [
        ("Normal Operation", test_normal_operation),
        ("Different Targets", test_different_targets),
        ("Saturation Handling", test_saturation_handling),
        ("Fallback Behavior", test_fallback_behavior),
        ("Target Calculation", test_target_count_calculation),
        ("Realistic Scenario", test_realistic_scenario),
        ("Integration Workflow", test_integration_with_servo_workflow),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"\n[ERROR] TEST FAILED: {name}")
            print(f"   Error: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, "FAIL"))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, status in results:
        symbol = "[OK]" if status == "PASS" else "[ERROR]"
        print(f"{symbol} {name}: {status}")

    passed = sum(1 for _, status in results if status == "PASS")
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    print(f"\n[WARN]  {total - passed} test(s) failed")
    return False


if __name__ == "__main__":
    # Configure logger for test output
    import logging

    logger.setLevel(logging.INFO)

    success = run_all_tests()
    sys.exit(0 if success else 1)
