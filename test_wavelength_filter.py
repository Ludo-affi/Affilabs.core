"""Test wavelength filtering for Phase Photonics detector.

Verifies that data below 570nm is correctly filtered out.
"""

import numpy as np
from affilabs.utils.detector_config import (
    filter_valid_wavelength_data,
    get_detector_characteristics,
)


def test_phase_photonics_filtering():
    """Test that Phase Photonics filters data below 570nm."""
    print("\n=== Testing Phase Photonics Wavelength Filtering ===\n")

    # Create test data with wavelengths from 560nm to 580nm
    wavelengths = np.array([560, 565, 570, 575, 580, 585, 590])
    data = np.array([100, 110, 120, 130, 140, 150, 160])

    print("Original data:")
    print(f"  Wavelengths: {wavelengths}")
    print(f"  Data: {data}")
    print(f"  Data points: {len(wavelengths)}")

    # Filter using Phase Photonics detector (ST serial)
    filtered_wl, filtered_data = filter_valid_wavelength_data(
        wavelengths, data, detector_serial="ST00012"
    )

    print("\nFiltered data (Phase Photonics ST00012):")
    print(f"  Wavelengths: {filtered_wl}")
    print(f"  Data: {filtered_data}")
    print(f"  Data points: {len(filtered_wl)}")
    print(f"  Min wavelength: {filtered_wl[0] if len(filtered_wl) > 0 else 'N/A'} nm")

    # Verify filtering is correct
    assert len(filtered_wl) == 5, f"Expected 5 points (>=570nm), got {len(filtered_wl)}"
    assert filtered_wl[0] == 570, f"Expected min wavelength 570nm, got {filtered_wl[0]}"
    assert np.all(filtered_wl >= 570), "Some wavelengths below 570nm were not filtered!"

    print("\n✅ Phase Photonics filtering PASSED - data below 570nm correctly removed")


def test_usb4000_filtering():
    """Test that USB4000 filters data below 560nm."""
    print("\n=== Testing USB4000 Wavelength Filtering ===\n")

    # Create test data with wavelengths from 550nm to 570nm
    wavelengths = np.array([550, 555, 560, 565, 570, 575, 580])
    data = np.array([100, 110, 120, 130, 140, 150, 160])

    print("Original data:")
    print(f"  Wavelengths: {wavelengths}")
    print(f"  Data: {data}")
    print(f"  Data points: {len(wavelengths)}")

    # Filter using USB4000 detector
    filtered_wl, filtered_data = filter_valid_wavelength_data(
        wavelengths, data, detector_serial="USB4H14526"
    )

    print("\nFiltered data (USB4000):")
    print(f"  Wavelengths: {filtered_wl}")
    print(f"  Data: {filtered_data}")
    print(f"  Data points: {len(filtered_wl)}")
    print(f"  Min wavelength: {filtered_wl[0] if len(filtered_wl) > 0 else 'N/A'} nm")

    # Verify filtering is correct
    assert len(filtered_wl) == 5, f"Expected 5 points (>=560nm), got {len(filtered_wl)}"
    assert filtered_wl[0] == 560, f"Expected min wavelength 560nm, got {filtered_wl[0]}"
    assert np.all(filtered_wl >= 560), "Some wavelengths below 560nm were not filtered!"

    print("\n✅ USB4000 filtering PASSED - data below 560nm correctly removed")


def test_detector_characteristics():
    """Test detector characteristics lookup."""
    print("\n=== Testing Detector Characteristics ===\n")

    # Test Phase Photonics
    phase = get_detector_characteristics(serial_number="ST00012")
    print("Phase Photonics ST00012:")
    print(f"  Name: {phase.name}")
    print(f"  Valid range: {phase.wavelength_min}-{phase.wavelength_max} nm")
    print(f"  SPR range: {phase.spr_wavelength_min}-{phase.spr_wavelength_max} nm")
    print(f"  Max counts: {phase.max_counts}")
    print(f"  Pixels: {phase.pixels}")

    assert phase.wavelength_min == 570.0, "Phase Photonics should have min 570nm"
    assert phase.max_counts == 4095, "Phase Photonics should have 12-bit ADC (4095)"

    # Test USB4000
    usb4000 = get_detector_characteristics(serial_number="USB4H14526")
    print("\nUSB4000:")
    print(f"  Name: {usb4000.name}")
    print(f"  Valid range: {usb4000.wavelength_min}-{usb4000.wavelength_max} nm")
    print(f"  SPR range: {usb4000.spr_wavelength_min}-{usb4000.spr_wavelength_max} nm")
    print(f"  Max counts: {usb4000.max_counts}")
    print(f"  Pixels: {usb4000.pixels}")

    assert usb4000.wavelength_min == 560.0, "USB4000 should have min 560nm"
    assert usb4000.max_counts == 65535, "USB4000 should have 16-bit ADC (65535)"

    print("\n✅ Detector characteristics PASSED")


if __name__ == "__main__":
    try:
        test_detector_characteristics()
        test_phase_photonics_filtering()
        test_usb4000_filtering()
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED - Wavelength filtering working correctly!")
        print("="*60 + "\n")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise
