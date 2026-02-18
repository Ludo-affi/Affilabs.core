"""Ultra-simple detector test - just raw intensities, no wavelength calibration.

Bypasses all EEPROM reads to avoid hangs.
"""

import numpy as np
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

print("=" * 80)
print("PHASE PHOTONICS RAW INTENSITIES (NO WAVELENGTH CALIBRATION)")
print("=" * 80)

# Open detector
det = PhasePhotonics()
if not det.open():
    print("❌ Failed to open detector")
    exit(1)

try:
    print(f"✓ Detector: {det.serial_number}")
    print(f"✓ Pixels: {det.num_pixels}")

    # Set integration time
    integration_time = 100  # milliseconds
    print(f"\n⏱️  Setting integration time: {integration_time} ms")
    det.set_integration(integration_time)

    # Acquire raw spectrum (just intensities, no wavelength lookup)
    print("\n📊 Acquiring raw spectrum...")
    raw_spectrum = det.read_intensity()

    if raw_spectrum is not None:
        print(f"✓ Success! Got {len(raw_spectrum)} data points")

        print("\n📈 RAW INTENSITY DATA:")
        print("  ADC Resolution: 12-bit (0-4095 counts)")
        print(f"  Min:    {raw_spectrum.min():.0f} counts")
        print(f"  Max:    {raw_spectrum.max():.0f} counts")
        print(f"  Mean:   {raw_spectrum.mean():.1f} counts")
        print(f"  Median: {np.median(raw_spectrum):.1f} counts")
        print(f"  Std:    {raw_spectrum.std():.1f} counts")

        # Saturation
        saturated = np.sum(raw_spectrum >= 4095)
        print(f"\n  Saturated pixels: {saturated} / {len(raw_spectrum)}")

        # Distribution
        print("\n  Intensity distribution:")
        bins = [(0, 500), (500, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 4095)]
        for low, high in bins:
            count = np.sum((raw_spectrum >= low) & (raw_spectrum < high))
            pct = count / len(raw_spectrum) * 100
            print(f"    {low:4d} - {high:4d}: {count:5d} pixels ({pct:5.1f}%)")

        # Show raw pixel data (no wavelength - just pixel index)
        print("\n📋 SAMPLE RAW DATA (pixel index, intensity):")
        print("  Pixel Index  |  Intensity (counts)")
        print("  -------------+--------------------")

        # Every 200 pixels
        for i in range(0, len(raw_spectrum), 200):
            print(f"  {i:11d}  |  {raw_spectrum[i]:18.1f}")

        # First 10
        print("\n📋 FIRST 10 PIXELS:")
        for i in range(10):
            print(f"  {i:11d}  |  {raw_spectrum[i]:18.1f}")

        # Last 10
        print("\n📋 LAST 10 PIXELS:")
        for i in range(1838, 1848):
            print(f"  {i:11d}  |  {raw_spectrum[i]:18.1f}")

        # Around pixel 924 (middle)
        print("\n📋 MIDDLE REGION (pixels 920-930):")
        for i in range(920, 930):
            print(f"  {i:11d}  |  {raw_spectrum[i]:18.1f}")

        # Save to text file
        print("\n💾 Saving raw data to file...")
        np.savetxt('raw_detector_spectrum.txt', raw_spectrum, fmt='%.1f',
                   header=f'Phase Photonics ST00012 Raw Spectrum\nIntegration: {integration_time}ms\nPixels: {len(raw_spectrum)}')
        print("  ✓ Saved to: raw_detector_spectrum.txt")

    else:
        print("❌ Failed to acquire spectrum")

finally:
    det.close()
    print("\n✓ Detector closed")
    print("=" * 80)
