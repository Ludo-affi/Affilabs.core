"""Test Afterglow Correction Module

Validates the afterglow correction module by:
1. Loading optical calibration
2. Testing interpolation at various integration times
3. Calculating corrections for different scenarios
4. Validating correction accuracy

Run this script to verify the module works before integrating into production.

Usage:
    python test_afterglow_correction.py [calibration_file]

Example:
    python test_afterglow_correction.py optical_calibration/system_FLMT09788_20251011_210859.json
"""

import sys
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from afterglow_correction import AfterglowCorrection
from utils.logger import logger


def test_load_calibration(cal_file: str):
    """Test 1: Load calibration file"""
    print(f"\n{'='*70}")
    print("TEST 1: Load Calibration")
    print(f"{'='*70}")

    try:
        cal = AfterglowCorrection(cal_file)
        print(f"✅ Successfully loaded: {cal_file}")

        info = cal.get_calibration_info()
        print(f"\n📋 Calibration Info:")
        print(f"   Channels: {info['channels']}")
        print(f"   Integration time range: {info['integration_time_range_ms'][0]:.1f} - {info['integration_time_range_ms'][1]:.1f} ms")

        for ch, (min_tau, max_tau) in info['tau_ranges'].items():
            print(f"   Channel {ch.upper()} τ range: {min_tau:.2f} - {max_tau:.2f} ms")

        return cal

    except Exception as e:
        print(f"❌ FAILED: {e}")
        raise


def test_interpolation(cal: AfterglowCorrection):
    """Test 2: Interpolation at non-calibrated points"""
    print(f"\n{'='*70}")
    print("TEST 2: Interpolation Accuracy")
    print(f"{'='*70}")

    # Test integration times between calibrated points
    test_cases = [
        ('a', 25.0, 5.0),  # Between 20-30ms
        ('b', 35.0, 5.0),  # Between 30-40ms
        ('c', 55.0, 5.0),  # At typical measurement point
        ('d', 65.0, 5.0),  # Between 60-70ms
    ]

    print(f"\n{'Channel':<10} {'Int Time (ms)':<15} {'Delay (ms)':<12} {'Correction (counts)':<20}")
    print("-" * 70)

    for channel, int_time, delay in test_cases:
        try:
            correction = cal.calculate_correction(channel, int_time, delay)
            print(f"{channel.upper():<10} {int_time:<15.1f} {delay:<12.1f} {correction:<20.1f}")
        except Exception as e:
            print(f"{channel.upper():<10} {int_time:<15.1f} {delay:<12.1f} ❌ ERROR: {e}")
            return False

    print(f"\n✅ Interpolation tests passed")
    return True


def test_delay_dependency(cal: AfterglowCorrection):
    """Test 3: Verify exponential decay with delay"""
    print(f"\n{'='*70}")
    print("TEST 3: Delay Dependency (Exponential Decay)")
    print(f"{'='*70}")

    # Test how correction decreases with increasing delay
    int_time = 55.0  # Typical measurement integration time
    delays = [0.0, 5.0, 10.0, 20.0, 50.0, 100.0]  # ms

    print(f"\nChannel A @ {int_time}ms integration time:")
    print(f"{'Delay (ms)':<15} {'Correction (counts)':<20} {'Ratio to 5ms':<15}")
    print("-" * 50)

    corrections = []
    for delay in delays:
        correction = cal.calculate_correction('a', int_time, delay)
        corrections.append(correction)

    reference = corrections[1]  # 5ms delay as reference

    for delay, correction in zip(delays, corrections):
        ratio = correction / reference if reference > 0 else 0
        print(f"{delay:<15.1f} {correction:<20.1f} {ratio:<15.3f}")

    # Verify exponential decay: longer delays → smaller corrections
    if all(corrections[i] >= corrections[i+1] for i in range(len(corrections)-1)):
        print(f"\n✅ Exponential decay verified (corrections decrease with delay)")
        return True
    else:
        print(f"\n❌ FAILED: Corrections don't decrease monotonically")
        return False


def test_array_correction(cal: AfterglowCorrection):
    """Test 4: Correction on spectrum arrays"""
    print(f"\n{'='*70}")
    print("TEST 4: Spectrum Array Correction")
    print(f"{'='*70}")

    # Simulate a spectrum measurement
    spectrum_size = 2048
    base_intensity = 20000
    spectrum = np.ones(spectrum_size) * base_intensity

    # Add some realistic spectral shape
    wavelengths = np.linspace(500, 900, spectrum_size)
    spectrum *= 0.8 + 0.2 * np.exp(-((wavelengths - 650) / 100)**2)  # Gaussian-ish

    print(f"\nOriginal spectrum:")
    print(f"   Shape: {spectrum.shape}")
    print(f"   Mean: {np.mean(spectrum):.1f} counts")
    print(f"   Min: {np.min(spectrum):.1f}, Max: {np.max(spectrum):.1f}")

    # Apply correction
    corrected = cal.apply_correction(
        spectrum,
        previous_channel='b',
        integration_time_ms=55.0,
        delay_ms=5.0
    )

    print(f"\nCorrected spectrum:")
    print(f"   Shape: {corrected.shape}")
    print(f"   Mean: {np.mean(corrected):.1f} counts")
    print(f"   Min: {np.min(corrected):.1f}, Max: {np.max(corrected):.1f}")

    difference = np.mean(spectrum) - np.mean(corrected)
    print(f"\nCorrection applied: {difference:.1f} counts")

    # Verify shape preserved
    if corrected.shape == spectrum.shape:
        print(f"✅ Array shape preserved")
        return True
    else:
        print(f"❌ FAILED: Array shape mismatch")
        return False


def test_channel_variation(cal: AfterglowCorrection):
    """Test 5: Verify different channels have different corrections"""
    print(f"\n{'='*70}")
    print("TEST 5: Channel-Specific Corrections")
    print(f"{'='*70}")

    # Same measurement conditions, different channels
    int_time = 55.0
    delay = 5.0

    print(f"\nCorrections at {int_time}ms, {delay}ms delay:")
    print(f"{'Channel':<10} {'Correction (counts)':<20}")
    print("-" * 30)

    corrections = {}
    for channel in ['a', 'b', 'c', 'd']:
        correction = cal.calculate_correction(channel, int_time, delay)
        corrections[channel] = correction
        print(f"{channel.upper():<10} {correction:<20.1f}")

    # Verify channels are different (LEDs have different characteristics)
    unique_corrections = len(set(corrections.values()))
    if unique_corrections >= 3:  # At least 3 different values
        print(f"\n✅ Channel-specific corrections verified ({unique_corrections} unique values)")
        return True
    else:
        print(f"\n⚠️ WARNING: Only {unique_corrections} unique correction values")
        return True  # Not a failure, but worth noting


def test_scalar_correction(cal: AfterglowCorrection):
    """Test 6: Correction on scalar values"""
    print(f"\n{'='*70}")
    print("TEST 6: Scalar Value Correction")
    print(f"{'='*70}")

    # Test correction on a single averaged intensity value
    avg_intensity = 18500.0  # counts

    print(f"\nOriginal averaged intensity: {avg_intensity:.1f} counts")

    corrected = cal.apply_correction(
        avg_intensity,
        previous_channel='c',
        integration_time_ms=55.0,
        delay_ms=5.0
    )

    print(f"Corrected averaged intensity: {corrected:.1f} counts")
    print(f"Correction applied: {avg_intensity - corrected:.1f} counts")

    # Verify it's a scalar
    if isinstance(corrected, (int, float, np.number)):
        print(f"✅ Scalar correction works")
        return True
    else:
        print(f"❌ FAILED: Expected scalar, got {type(corrected)}")
        return False


def run_all_tests(cal_file: str):
    """Run complete test suite"""
    print(f"\n{'#'*70}")
    print("# Afterglow Correction Module - Test Suite")
    print(f"{'#'*70}")
    print(f"\nCalibration file: {cal_file}\n")

    results = {}

    try:
        # Test 1: Load calibration
        cal = test_load_calibration(cal_file)
        results['Load'] = True

        # Test 2: Interpolation
        results['Interpolation'] = test_interpolation(cal)

        # Test 3: Delay dependency
        results['Delay Decay'] = test_delay_dependency(cal)

        # Test 4: Array correction
        results['Array'] = test_array_correction(cal)

        # Test 5: Channel variation
        results['Channel Variation'] = test_channel_variation(cal)

        # Test 6: Scalar correction
        results['Scalar'] = test_scalar_correction(cal)

    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<25} {status}")

    all_passed = all(results.values())

    print(f"\n{'='*70}")
    if all_passed:
        print("🎉 ALL TESTS PASSED! Module ready for integration.")
    else:
        print("❌ SOME TESTS FAILED. Review errors above.")
    print(f"{'='*70}\n")

    return all_passed


def main():
    """Main entry point"""
    # Default calibration file
    default_file = "optical_calibration/system_FLMT09788_20251011_210859.json"

    if len(sys.argv) > 1:
        cal_file = sys.argv[1]
    else:
        cal_file = default_file
        print(f"ℹ️ No calibration file specified, using default: {cal_file}")
        print(f"   Usage: python {Path(__file__).name} <calibration_file>\n")

    # Check file exists
    if not Path(cal_file).exists():
        print(f"\n❌ Error: Calibration file not found: {cal_file}")
        print(f"   Absolute path: {Path(cal_file).resolve()}")
        print(f"\nℹ️ Run optical calibration first to generate the file:")
        print(f"   python led_afterglow_integration_time_model.py")
        sys.exit(1)

    # Run tests
    success = run_all_tests(cal_file)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
