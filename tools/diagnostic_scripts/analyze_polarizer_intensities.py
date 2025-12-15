#!/usr/bin/env python3
"""Analyze polarizer intensity values in 600-630nm range for each servo position.

This script extracts the intensity measurements from the OEM calibration sweep
and shows the spectral characteristics in the SPR-relevant wavelength range.
"""

import json
from pathlib import Path

import numpy as np
from seabreeze.spectrometers import Spectrometer, list_devices


def get_wavelength_range_indices(spec, min_wl=600, max_wl=630):
    """Get pixel indices corresponding to wavelength range."""
    wavelengths = spec.wavelengths()
    min_idx = np.argmin(np.abs(wavelengths - min_wl))
    max_idx = np.argmin(np.abs(wavelengths - max_wl))
    return min_idx, max_idx, wavelengths[min_idx : max_idx + 1]


def analyze_sweep_data():
    """Analyze the polarizer sweep data."""
    print("=" * 80)
    print("POLARIZER INTENSITY ANALYSIS - 600-630nm Range")
    print("=" * 80)

    # Load the saved profile
    profile_path = Path("calibration_data/device_profiles/device_TEST001_20251019.json")

    if not profile_path.exists():
        print(f"❌ Profile not found: {profile_path}")
        return

    with profile_path.open("r") as f:
        data = json.load(f)

    polarizer = data["polarizer"]

    print("\n📊 Calibration Results:")
    print(
        f"   S Position (HIGH): {polarizer['s_position']} → {polarizer['s_intensity']:.1f} counts",
    )
    print(
        f"   P Position (LOW):  {polarizer['p_position']} → {polarizer['p_intensity']:.1f} counts",
    )
    print(f"   S/P Ratio: {polarizer['sp_ratio']:.2f}× (target >3.0×)")

    # Get the intensity curve
    if "intensity_curve" not in polarizer:
        print("\n❌ No intensity curve data found in profile")
        return

    curve = polarizer["intensity_curve"]
    angles = np.array(curve["angles"])
    intensities = np.array(curve["intensities"])

    print("\n📈 Sweep Data:")
    print(f"   Total positions measured: {len(angles)}")
    print(f"   Position range: {angles.min()}-{angles.max()}")

    # Initialize spectrometer to get wavelength mapping
    print("\n🔬 Connecting to spectrometer for wavelength mapping...")
    devices = list_devices()
    if not devices:
        print("❌ No spectrometer found!")
        print(
            "\nNote: Using full spectrum intensities (600-630nm indices depend on detector)",
        )
        print_intensity_table(angles, intensities, polarizer)
        return

    spec = Spectrometer(devices[0])
    print(f"✅ Connected: {spec.model}")

    # Get wavelength range
    min_idx, max_idx, wavelengths = get_wavelength_range_indices(spec, 600, 630)
    print("\n🌈 Wavelength Mapping:")
    print(
        f"   Full spectrum: {spec.wavelengths()[0]:.1f}-{spec.wavelengths()[-1]:.1f} nm",
    )
    print("   Target range: 600-630 nm")
    print(f"   Pixel indices: {min_idx}-{max_idx} ({max_idx-min_idx+1} pixels)")
    print(f"   Actual range: {wavelengths[0]:.2f}-{wavelengths[-1]:.2f} nm")

    # Close spectrometer
    spec.close()

    # Note: The saved intensities are max() values from full spectrum
    # For detailed wavelength-specific analysis, we'd need the full spectrum data
    print("\n📊 INTENSITY VALUES (Full Spectrum Max):")
    print_intensity_table(angles, intensities, polarizer)

    # Show top 10 positions
    print("\n🔝 TOP 10 POSITIONS BY INTENSITY:")
    sorted_idx = np.argsort(intensities)[::-1][:10]
    print(f"{'Rank':<6} {'Position':<10} {'Intensity':<12} {'Notes'}")
    print("-" * 60)
    for i, idx in enumerate(sorted_idx, 1):
        pos = int(angles[idx])
        intensity = intensities[idx]
        notes = ""
        if pos == polarizer["s_position"]:
            notes = "← S-mode (HIGH)"
        elif pos == polarizer["p_position"]:
            notes = "← P-mode (LOW)"
        print(f"{i:<6} {pos:<10} {intensity:<12.1f} {notes}")

    # Calculate statistics
    print("\n📈 INTENSITY STATISTICS:")
    print(
        f"   Maximum: {intensities.max():.1f} counts at position {int(angles[np.argmax(intensities)])}",
    )
    print(
        f"   Minimum: {intensities.min():.1f} counts at position {int(angles[np.argmin(intensities)])}",
    )
    print(f"   Mean: {intensities.mean():.1f} counts")
    print(f"   Std Dev: {intensities.std():.1f} counts")
    print(f"   Max/Min Ratio: {intensities.max() / intensities.min():.2f}×")

    print("\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nNote: Detailed 600-630nm spectral data requires full spectrum capture.")
    print("The values above show max intensity across full detector range.")
    print(
        "For wavelength-specific analysis, re-run calibration with full spectrum logging.",
    )


def print_intensity_table(angles, intensities, polarizer):
    """Print intensity table for all positions."""
    print(f"\n{'Position':<10} {'Intensity':<12} {'Notes'}")
    print("-" * 50)

    # Group by position (handling duplicates from coarse + fine sweep)
    unique_positions = sorted(set(angles))

    for pos in unique_positions:
        # Get all intensities for this position
        mask = angles == pos
        intensity = intensities[mask].max()  # Use max if multiple measurements

        notes = ""
        if pos == polarizer["s_position"]:
            notes = "← S-mode (HIGH transmission)"
        elif pos == polarizer["p_position"]:
            notes = "← P-mode (LOW transmission)"

        print(f"{int(pos):<10} {intensity:<12.1f} {notes}")


if __name__ == "__main__":
    try:
        analyze_sweep_data()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
