"""Display raw detector data from Phase Photonics ST00012.

Shows:
- EEPROM calibration coefficients
- Wavelength array (actual values from EEPROM)
- Raw spectrum (intensity counts)
- Basic statistics
"""

import numpy as np
from numpy import frombuffer
from numpy.polynomial import Polynomial
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

print("=" * 80)
print("PHASE PHOTONICS RAW DETECTOR DATA")
print("=" * 80)

# Open detector
det = PhasePhotonics()
if not det.open():
    print("❌ Failed to open detector")
    exit(1)

try:
    # ========================================================================
    # 1. READ EEPROM CALIBRATION
    # ========================================================================
    print("\n📋 EEPROM CALIBRATION COEFFICIENTS:")
    print("-" * 80)

    bytes_read, config = det.api.usb_read_config(det.spec, 0)

    if bytes_read == det.CONFIG_SIZE:
        # Extract calibration coefficients
        coeffs = frombuffer(
            config.data,
            ">f8",  # Big-endian float64
            4,      # 4 coefficients (4th order polynomial)
            3072,   # Offset in EEPROM
        )

        print(f"  c0 (intercept):  {coeffs[0]:.6f}")
        print(f"  c1 (linear):     {coeffs[1]:.6f}")
        print(f"  c2 (quadratic):  {coeffs[2]:.6e}")
        print(f"  c3 (cubic):      {coeffs[3]:.6e}")

        # Calculate wavelength array
        cal_curve = Polynomial(coeffs)
        wavelengths = cal_curve(np.arange(1848))

        print(f"\n  Polynomial: λ(pixel) = {coeffs[0]:.4f} + {coeffs[1]:.4f}*x + {coeffs[2]:.6e}*x² + {coeffs[3]:.6e}*x³")
    else:
        print(f"  ❌ EEPROM read failed ({bytes_read} bytes)")
        wavelengths = None

    # ========================================================================
    # 2. WAVELENGTH ARRAY
    # ========================================================================
    if wavelengths is not None:
        print("\n🌈 WAVELENGTH ARRAY:")
        print("-" * 80)
        print(f"  Total pixels: {len(wavelengths)}")
        print(f"  Wavelength range: {wavelengths[0]:.3f} - {wavelengths[-1]:.3f} nm")
        print(f"  Spectral span: {wavelengths[-1] - wavelengths[0]:.3f} nm")
        print(f"  Average resolution: {(wavelengths[-1] - wavelengths[0]) / (len(wavelengths) - 1):.4f} nm/pixel")

        print("\n  First 10 wavelengths (nm):")
        for i in range(10):
            print(f"    Pixel {i:4d}: {wavelengths[i]:.3f} nm")

        print("\n  Last 10 wavelengths (nm):")
        for i in range(1838, 1848):
            print(f"    Pixel {i:4d}: {wavelengths[i]:.3f} nm")

    # ========================================================================
    # 3. ACQUIRE RAW SPECTRUM
    # ========================================================================
    print("\n📊 RAW SPECTRUM ACQUISITION:")
    print("-" * 80)

    # Set integration time
    integration_time = 100  # milliseconds
    det.integration_time(integration_time / 1000.0)  # Convert to seconds
    print(f"  Integration time: {integration_time} ms")

    # Acquire spectrum
    raw_spectrum = det.intensities()

    if raw_spectrum is not None:
        print(f"\n  Spectrum array length: {len(raw_spectrum)}")
        print("  ADC resolution: 12-bit (0-4095 counts)")
        print("\n  Intensity statistics:")
        print(f"    Min:    {raw_spectrum.min():.1f} counts")
        print(f"    Max:    {raw_spectrum.max():.1f} counts")
        print(f"    Mean:   {raw_spectrum.mean():.1f} counts")
        print(f"    Median: {np.median(raw_spectrum):.1f} counts")
        print(f"    Std:    {raw_spectrum.std():.1f} counts")

        # Check for saturation
        saturated = np.sum(raw_spectrum >= 4095)
        if saturated > 0:
            print(f"\n  ⚠️  WARNING: {saturated} pixels saturated (>= 4095 counts)")

        # Show intensity distribution
        print("\n  Intensity distribution:")
        bins = [0, 500, 1000, 2000, 3000, 4000, 4095]
        for i in range(len(bins) - 1):
            count = np.sum((raw_spectrum >= bins[i]) & (raw_spectrum < bins[i+1]))
            print(f"    {bins[i]:4d} - {bins[i+1]:4d} counts: {count:5d} pixels ({count/len(raw_spectrum)*100:.1f}%)")

        # ====================================================================
        # 4. WAVELENGTH-INTENSITY PAIRS (SAMPLE)
        # ====================================================================
        if wavelengths is not None:
            print("\n🔬 SAMPLE DATA (Wavelength, Intensity):")
            print("-" * 80)

            # Show every 200 pixels
            print("  Pixel  |  Wavelength (nm)  |  Intensity (counts)")
            print("  -------+-------------------+--------------------")
            for i in range(0, len(raw_spectrum), 200):
                print(f"  {i:5d}  |  {wavelengths[i]:15.3f}  |  {raw_spectrum[i]:18.1f}")

            # Show 570nm region (where valid SPR data starts)
            idx_570 = np.argmin(np.abs(wavelengths - 570.0))
            print("\n  570nm cutoff region (valid SPR data starts here):")
            print("  Pixel  |  Wavelength (nm)  |  Intensity (counts)")
            print("  -------+-------------------+--------------------")
            for i in range(max(0, idx_570-5), min(len(wavelengths), idx_570+6)):
                marker = " ← 570nm" if i == idx_570 else ""
                print(f"  {i:5d}  |  {wavelengths[i]:15.3f}  |  {raw_spectrum[i]:18.1f}{marker}")

        # ====================================================================
        # 5. SUMMARY
        # ====================================================================
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("✓ Detector: Phase Photonics ST00012")
        print(f"✓ Serial: {det.serial_number}")
        print(f"✓ Total pixels: {len(raw_spectrum)}")
        if wavelengths is not None:
            print(f"✓ Wavelength range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")
            print(f"✓ Valid SPR range: 570.0 - 720.0 nm (~{np.sum(wavelengths >= 570.0)} pixels)")
        print(f"✓ Intensity range: {raw_spectrum.min():.0f} - {raw_spectrum.max():.0f} counts")
        print(f"✓ Mean intensity: {raw_spectrum.mean():.0f} counts")

    else:
        print("  ❌ Failed to acquire spectrum")

finally:
    det.close()
    print("\n✓ Detector closed")
    print("=" * 80)
