"""Simple detector raw spectrum display - skips EEPROM read.

Shows raw intensity data directly from the detector.
"""

import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

print("=" * 80)
print("PHASE PHOTONICS RAW SPECTRUM")
print("=" * 80)

# Open detector
det = PhasePhotonics()
if not det.open():
    print("❌ Failed to open detector")
    exit(1)

try:
    print(f"✓ Detector connected: {det.serial_number}")
    print(f"✓ Total pixels: {det.num_pixels}")

    # Get wavelength array (uses cached or built-in calibration)
    print("\n🌈 Getting wavelength array...")
    wavelengths = det.wavelengths()

    if wavelengths is not None:
        print(f"  Wavelength range: {wavelengths[0]:.3f} - {wavelengths[-1]:.3f} nm")
        print(f"  Total pixels: {len(wavelengths)}")
        print(f"  Resolution: {(wavelengths[-1] - wavelengths[0]) / (len(wavelengths) - 1):.4f} nm/pixel")
    else:
        print("  ❌ Failed to get wavelengths")

    # Set integration time
    print("\n📊 Acquiring spectrum...")
    integration_time = 100  # milliseconds
    det.integration_time(integration_time / 1000.0)
    print(f"  Integration time: {integration_time} ms")

    # Acquire raw spectrum
    raw_spectrum = det.intensities()

    if raw_spectrum is not None:
        print("\n✓ Spectrum acquired!")
        print(f"  Total pixels: {len(raw_spectrum)}")
        print("  ADC: 12-bit (0-4095 counts)")

        print("\n📈 INTENSITY STATISTICS:")
        print(f"  Min:    {raw_spectrum.min():.1f} counts")
        print(f"  Max:    {raw_spectrum.max():.1f} counts")
        print(f"  Mean:   {raw_spectrum.mean():.1f} counts")
        print(f"  Median: {np.median(raw_spectrum):.1f} counts")
        print(f"  Std:    {raw_spectrum.std():.1f} counts")

        # Saturation check
        saturated = np.sum(raw_spectrum >= 4095)
        if saturated > 0:
            print(f"\n  ⚠️  {saturated} pixels saturated (>= 4095 counts)")
        else:
            print("\n  ✓ No saturation")

        # Show sample data
        if wavelengths is not None:
            print("\n🔬 SAMPLE DATA (every 200 pixels):")
            print("  Pixel  |  Wavelength (nm)  |  Intensity (counts)")
            print("  -------+-------------------+--------------------")
            for i in range(0, len(raw_spectrum), 200):
                print(f"  {i:5d}  |  {wavelengths[i]:15.3f}  |  {raw_spectrum[i]:18.1f}")

            # 570nm region
            idx_570 = np.argmin(np.abs(wavelengths - 570.0))
            print("\n  Around 570nm (SPR valid data starts):")
            print("  Pixel  |  Wavelength (nm)  |  Intensity (counts)")
            print("  -------+-------------------+--------------------")
            for i in range(max(0, idx_570-3), min(len(wavelengths), idx_570+4)):
                marker = " ← ~570nm" if abs(wavelengths[i] - 570.0) < 0.1 else ""
                print(f"  {i:5d}  |  {wavelengths[i]:15.3f}  |  {raw_spectrum[i]:18.1f}{marker}")

        # Show first/last 10 pixels
        print("\n📋 FIRST 10 PIXELS:")
        print("  Pixel  |  Intensity (counts)")
        print("  -------+--------------------")
        for i in range(10):
            wl_str = f"{wavelengths[i]:.3f} nm" if wavelengths is not None else "N/A"
            print(f"  {i:5d}  |  {raw_spectrum[i]:18.1f}  ({wl_str})")

        print("\n📋 LAST 10 PIXELS:")
        print("  Pixel  |  Intensity (counts)")
        print("  -------+--------------------")
        for i in range(1838, 1848):
            wl_str = f"{wavelengths[i]:.3f} nm" if wavelengths is not None else "N/A"
            print(f"  {i:5d}  |  {raw_spectrum[i]:18.1f}  ({wl_str})")

    else:
        print("  ❌ Failed to acquire spectrum")

finally:
    det.close()
    print("\n✓ Detector closed")
    print("=" * 80)
