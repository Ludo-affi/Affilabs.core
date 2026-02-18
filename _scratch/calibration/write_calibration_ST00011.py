"""Write wavelength calibration coefficients to PhasePhotonics ST00011 EEPROM.

WARNING: This will overwrite the detector's calibration data. Make sure you have
the correct coefficients before running this script.

New Calibration Coefficients for ST00011:
  c0: 530.3916
  c1: 0.2204814
  c2: -4.007498e-06
  c3: -9.861940e-09
"""

import numpy as np
from affilabs.utils.logger import logger
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

# New calibration coefficients for ST00011 (from manufacturer)
NEW_COEFFICIENTS = [
    5.303916e2,      # c0 = 530.3916
    2.204814e-1,     # c1 = 0.2204814
    -4.007498e-6,    # c2 = -4.007498e-06
    -9.861940e-9,    # c3 = -9.861940e-09
]

def write_calibration():
    """Write new calibration coefficients to detector EEPROM."""

    logger.info("="*70)
    logger.info("PhasePhotonics ST00011 Calibration Writer")
    logger.info("="*70)

    # Connect to detector
    det = PhasePhotonics()
    if not det.open():
        logger.error("Failed to connect to PhasePhotonics detector")
        logger.error("Make sure ST00011 is plugged in and no other program is using it")
        return False

    try:
        # Verify we're connected to ST00011
        serial = det.get_serial()
        if serial != "ST00011":
            logger.error(f"Wrong detector! Connected to {serial}, expected ST00011")
            logger.error("Please plug in ST00011 and try again")
            return False

        logger.info(f"✓ Connected to detector: {serial}")

        # Read current calibration
        logger.info("\nReading current calibration from EEPROM...")
        bytes_read, config = det.api.usb_read_config(det.spec, 0)

        if bytes_read != det.CONFIG_SIZE:
            logger.error(f"Failed to read config: expected {det.CONFIG_SIZE} bytes, got {bytes_read}")
            return False

        # Extract current coefficients
        current_coeffs = np.frombuffer(
            config.data,
            ">f8",  # Big-endian float64
            det.CALIBRATION_DEGREE,
            det.CALIBRATION_OFFSET,
        )

        logger.info("\nCurrent calibration coefficients:")
        for i, coeff in enumerate(current_coeffs):
            logger.info(f"  c{i}: {coeff}")

        # Check current wavelength range
        if not all(np.isnan(current_coeffs)):
            from numpy.polynomial import Polynomial
            current_curve = Polynomial(current_coeffs)
            wl_min_current = current_curve(0)
            wl_max_current = current_curve(1847)
            logger.info(f"  Current wavelength range: {wl_min_current:.2f} - {wl_max_current:.2f} nm")
        else:
            logger.info("  Detector is not currently calibrated (all NaN)")

        # Create new coefficient array
        new_coeffs = np.array(NEW_COEFFICIENTS, dtype='>f8')  # Big-endian float64

        logger.info("\n" + "="*70)
        logger.info("NEW calibration coefficients:")
        for i, coeff in enumerate(new_coeffs):
            logger.info(f"  c{i}: {coeff}")

        # Verify wavelength range with new coefficients
        from numpy.polynomial import Polynomial
        calibration_curve = Polynomial(new_coeffs)
        wl_min = calibration_curve(0)
        wl_max = calibration_curve(1847)

        logger.info(f"  New wavelength range: {wl_min:.2f} - {wl_max:.2f} nm")
        logger.info("="*70)

        # Confirm before writing
        logger.warning("\n" + "!"*70)
        logger.warning("WARNING: This will permanently modify the detector's EEPROM!")
        logger.warning("!"*70)
        response = input("\nType 'YES' to proceed with writing new calibration: ")

        if response != "YES":
            logger.info("Calibration write cancelled by user")
            return False

        # Write new coefficients to config data
        logger.info("\nWriting new calibration to EEPROM...")

        # Copy existing config data
        new_config_data = bytearray(config.data)

        # Replace calibration coefficients at offset 3072
        new_config_data[det.CALIBRATION_OFFSET:det.CALIBRATION_OFFSET + 32] = new_coeffs.tobytes()

        # Create new config structure
        from affilabs.utils.phase_photonics_api import config_contents
        new_config = config_contents()
        for i, byte in enumerate(new_config_data):
            new_config.data[i] = byte

        # Write to EEPROM
        result = det.api.usb_write_config(det.spec, new_config, 0)

        if result == 0:
            logger.info("✓ Calibration written successfully!")

            # Verify by reading back
            logger.info("\nVerifying written calibration...")
            bytes_read, verify_config = det.api.usb_read_config(det.spec, 0)
            verify_coeffs = np.frombuffer(
                verify_config.data,
                ">f8",
                det.CALIBRATION_DEGREE,
                det.CALIBRATION_OFFSET,
            )

            logger.info("Verified calibration coefficients:")
            for i, coeff in enumerate(verify_coeffs):
                logger.info(f"  c{i}: {coeff}")

            # Verify wavelength range
            verify_curve = Polynomial(verify_coeffs)
            verify_wl_min = verify_curve(0)
            verify_wl_max = verify_curve(1847)
            logger.info(f"  Verified wavelength range: {verify_wl_min:.2f} - {verify_wl_max:.2f} nm")

            # Check if they match
            if np.allclose(verify_coeffs, new_coeffs):
                logger.info("\n" + "✓"*70)
                logger.info("✓✓✓ CALIBRATION VERIFIED SUCCESSFULLY! ✓✓✓")
                logger.info("✓"*70)
                logger.info("\nST00011 is now calibrated and ready to use!")
                return True
            else:
                logger.error("\n✗✗✗ Verification failed - coefficients don't match!")
                return False
        else:
            logger.error(f"✗ Failed to write calibration (error code: {result})")
            return False

    except Exception as e:
        logger.error(f"Error during calibration write: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        det.close()
        logger.info("\nDetector connection closed")

if __name__ == "__main__":
    success = write_calibration()
    if success:
        print("\n🎉 Success! ST00011 calibration has been written to EEPROM")
    else:
        print("\n❌ Failed to write calibration. Check the log above for details.")
