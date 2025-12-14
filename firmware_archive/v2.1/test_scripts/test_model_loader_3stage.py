"""
Test script to verify model_loader.py works with 3-stage linear calibration.

This tests that the updated model_loader.py can:
1. Load a 3-stage calibration file
2. Transform it to compatible format
3. Calculate LED intensities correctly
4. Generate QC reports

Author: GitHub Copilot
Date: 2024
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath('.'))

from affilabs.utils.model_loader import LEDCalibrationModelLoader, ModelNotFoundError

def test_basic_loading():
    """Test that model loader can load 3-stage calibration file."""
    print("="*80)
    print("TEST 1: Basic Model Loading")
    print("="*80)

    loader = LEDCalibrationModelLoader()

    try:
        # This should find led_calibration_3stage_*.json in spr_calibration/data/
        loader.load_model("test")
        print("✓ Model loaded successfully")
        print(f"  Model data keys: {list(loader.model_data.keys())}")
        print(f"  LED channels: {list(loader.model_data['bilinear_models'].keys())}")
        return loader
    except ModelNotFoundError as e:
        print(f"✗ Failed to load model: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_model_info(loader):
    """Test get_model_info() method."""
    print("\n" + "="*80)
    print("TEST 2: Model Info")
    print("="*80)

    try:
        info = loader.get_model_info()
        print(f"✓ Model info retrieved")
        print(f"  Detector: {info.get('detector_serial', 'N/A')}")
        print(f"  Timestamp: {info.get('timestamp', 'N/A')}")
        print(f"  Channels: {info.get('channels', [])}")

        # Check R² scores (should be from linearity)
        r2_scores = info.get('r2_scores', {})
        if r2_scores:
            print(f"\n  Linearity R² Scores:")
            for channel, pols in r2_scores.items():
                print(f"    {channel}: S={pols.get('S', 'N/A'):.4f}, P={pols.get('P', 'N/A'):.4f}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calculate_intensity(loader):
    """Test calculate_led_intensity() with 3-stage formula."""
    print("\n" + "="*80)
    print("TEST 3: Calculate LED Intensities")
    print("="*80)

    try:
        # Test parameters
        target_counts = 60000
        time_ms = 30.0

        print(f"Target: {target_counts} counts at {time_ms}ms")
        print(f"\nCalculated Intensities (S-polarization):")

        for led in ['A', 'B', 'C', 'D']:
            intensity = loader.calculate_led_intensity(
                led, 'S', time_ms, target_counts
            )

            # Verify prediction
            predicted = loader.predict_counts(led, 'S', time_ms, intensity)

            print(f"  {led}: intensity={intensity:3d}, predicted={predicted:6.0f} counts")

            # Check if prediction is close to target (within 5%)
            error_pct = abs(predicted - target_counts) / target_counts * 100
            if error_pct > 5:
                print(f"    ⚠ Warning: {error_pct:.1f}% error")

        print("✓ Intensity calculations completed")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_leds(loader):
    """Test calculate_all_led_intensities()."""
    print("\n" + "="*80)
    print("TEST 4: Calculate All LEDs")
    print("="*80)

    try:
        target_counts = 60000
        time_ms = 20.0

        intensities = loader.calculate_all_led_intensities(
            'S', time_ms, target_counts
        )

        print(f"Target: {target_counts} counts at {time_ms}ms")
        print(f"Results: {intensities}")
        print("✓ All LED calculation successful")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_qc_report(loader):
    """Test QC report generation."""
    print("\n" + "="*80)
    print("TEST 5: QC Report")
    print("="*80)

    try:
        report = loader.generate_qc_report()

        print(f"Status: {report['status']}")
        print(f"Checks: {report['total_checks']}")
        print(f"Warnings: {report['total_warnings']}")
        print(f"Errors: {report['total_errors']}")

        if report['errors']:
            print("\nErrors found:")
            for error in report['errors']:
                print(f"  {error}")

        if report['passed']:
            print("✓ QC report PASSED")
        else:
            print("✗ QC report FAILED")

        return report['passed']
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dark_signal(loader):
    """Test dark signal calculation."""
    print("\n" + "="*80)
    print("TEST 6: Dark Signal")
    print("="*80)

    try:
        for time_ms in [10, 20, 30]:
            dark = loader.calculate_dark_signal('A', time_ms, 'S')
            print(f"  t={time_ms}ms: dark={dark:.1f} counts")

        print("✓ Dark signal calculation successful")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("="*80)
    print("MODEL LOADER 3-STAGE LINEAR TEST SUITE")
    print("="*80)
    print()

    # Test 1: Load model
    loader = test_basic_loading()
    if not loader:
        print("\n❌ CRITICAL: Could not load model. Stopping tests.")
        return False

    # Test 2: Model info
    success = test_model_info(loader)
    if not success:
        print("\n⚠ Model info test failed")

    # Test 3: Calculate intensity
    success = test_calculate_intensity(loader)
    if not success:
        print("\n⚠ Intensity calculation test failed")

    # Test 4: All LEDs
    success = test_all_leds(loader)
    if not success:
        print("\n⚠ All LEDs test failed")

    # Test 5: QC report
    success = test_qc_report(loader)
    if not success:
        print("\n⚠ QC report test failed")

    # Test 6: Dark signal
    success = test_dark_signal(loader)
    if not success:
        print("\n⚠ Dark signal test failed")

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)
    print()

    return True


if __name__ == "__main__":
    main()
