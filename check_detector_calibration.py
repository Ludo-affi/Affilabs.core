"""Quick check to see which Phase Photonics detector is connected and verify calibration."""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger

print("=" * 80)
print("PHASE PHOTONICS DETECTOR CALIBRATION CHECK")
print("=" * 80)

# Connect to detector
detector = PhasePhotonics()

print("\n[1] Connecting to detector...")
if not detector.open():
    print("❌ Failed to connect to Phase Photonics detector")
    print("   - Make sure detector is plugged in")
    print("   - Check USB connection")
    print("   - Ensure no other program is using the detector")
    exit(1)

print(f"✓ Connected successfully")

# Get serial number
print(f"\n[2] Detector Serial Number: {detector.serial_number}")

# Check if override is configured
print(f"\n[3] Calibration Source:")
if detector.serial_number in detector.CALIBRATION_OVERRIDES:
    print(f"✓ Using EXTERNAL CALIBRATION OVERRIDE")
    coeffs = detector.CALIBRATION_OVERRIDES[detector.serial_number]
    print(f"  c0: {coeffs[0]:.6e}")
    print(f"  c1: {coeffs[1]:.6e}")
    print(f"  c2: {coeffs[2]:.6e}")
    print(f"  c3: {coeffs[3]:.6e}")
else:
    print(f"⚠ No override found - will use EEPROM calibration")
    print(f"  (This detector is not in CALIBRATION_OVERRIDES dictionary)")

# Read wavelength calibration
print(f"\n[4] Reading wavelength calibration...")
wavelengths = detector.read_wavelength()

if wavelengths is not None:
    print(f"✓ Wavelength calibration loaded successfully")
    print(f"  Range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")
    print(f"  Pixels: {len(wavelengths)}")
    print(f"  Resolution: {(wavelengths[-1] - wavelengths[0]) / len(wavelengths):.3f} nm/pixel")
else:
    print(f"❌ Failed to load wavelength calibration")

# Test reading intensity
print(f"\n[5] Testing detector readout...")
detector.set_integration(50)  # 50ms integration
intensity = detector.read_intensity()

if intensity is not None:
    print(f"✓ Detector readout successful")
    print(f"  Data points: {len(intensity)}")
    print(f"  Min: {intensity.min():.0f} counts")
    print(f"  Max: {intensity.max():.0f} counts")
    print(f"  Mean: {intensity.mean():.0f} counts")
    
    if intensity.max() > 7500:
        print(f"  ⚠ WARNING: Signal close to saturation (13-bit max: 8191)")
else:
    print(f"❌ Failed to read intensity")

# Close detector
detector.close()

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
print(f"\nConfigured detectors in CALIBRATION_OVERRIDES:")
for serial in sorted(detector.CALIBRATION_OVERRIDES.keys()):
    coeffs = detector.CALIBRATION_OVERRIDES[serial]
    print(f"  • {serial}: c0={coeffs[0]:.2f} nm")
