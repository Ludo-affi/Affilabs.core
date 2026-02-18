"""Check EEPROM calibration data in PhasePhotonics ST00012 detector."""

from numpy import frombuffer
from numpy.polynomial import Polynomial
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.logger import logger

det = PhasePhotonics()
if not det.open():
    logger.error("Failed to open detector")
    exit(1)

try:
    logger.info("="*70)
    logger.info("Reading EEPROM Calibration Data")
    logger.info("="*70)

    # Direct EEPROM read
    bytes_read, config = det.api.usb_read_config(det.spec, 0)

    logger.info(f"EEPROM read result: {bytes_read} bytes (expected {det.CONFIG_SIZE})")

    if bytes_read == det.CONFIG_SIZE:
        # Extract calibration coefficients
        eeprom_coeffs = frombuffer(
            config.data,
            ">f8",  # Big-endian float64
            4,      # 4 coefficients
            3072,   # Offset
        )

        logger.info("\nEEPROM Stored Calibration:")
        for i, coeff in enumerate(eeprom_coeffs):
            logger.info(f"  c{i}: {coeff}")

        # Calculate wavelength range
        cal_curve = Polynomial(eeprom_coeffs)
        wl_min = cal_curve(0)
        wl_max = cal_curve(1847)
        logger.info(f"\nEEPROM Wavelength Range: {wl_min:.2f} - {wl_max:.2f} nm")

        # Compare with expected
        expected_coeffs = [563.7917, 0.2089449, -2.302712e-6, -1.650914e-8]
        logger.info("\nExpected (User-Provided) Calibration:")
        for i, coeff in enumerate(expected_coeffs):
            logger.info(f"  c{i}: {coeff}")

        expected_curve = Polynomial(expected_coeffs)
        expected_min = expected_curve(0)
        expected_max = expected_curve(1847)
        logger.info(f"\nExpected Wavelength Range: {expected_min:.2f} - {expected_max:.2f} nm")

        # Check if they match
        import numpy as np
        if np.allclose(eeprom_coeffs, expected_coeffs):
            logger.info("\n✅ EEPROM matches expected calibration!")
        else:
            logger.warning("\n⚠️  EEPROM does NOT match expected calibration")
            logger.warning("    Using software OVERRIDE_CALIBRATION instead")
    else:
        logger.error(f"\n❌ EEPROM read failed (returned {bytes_read} bytes)")
        logger.error("   EEPROM may be uninitialized, corrupted, or read-protected")
        logger.info("\n✓ Using software OVERRIDE_CALIBRATION as fallback")

finally:
    det.close()
    logger.info("\nDetector disconnected")
