"""Write new wavelength calibration coefficients to PhasePhotonics ST00012 EEPROM.

WARNING: This will overwrite the detector's calibration data. Make sure you have
the correct coefficients before running this script.

New Calibration Coefficients:
  c0: 563.7917
  c1: 0.2089449
  c2: -2.302712e-06
  c3: -1.650914e-08
"""

import numpy as np
from affilabs.utils.logger import logger
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

# New calibration coefficients (from user)
NEW_COEFFICIENTS = [
    5.637917e2,      # c0
    2.089449e-1,     # c1
    -2.302712e-6,    # c2
    -1.650914e-8,    # c3
]

def write_calibration():
    """Write new calibration coefficients to detector EEPROM."""
    
    logger.info("="*70)
    logger.info("PhasePhotonics ST00012 Calibration Writer")
    logger.info("="*70)
    
    # Connect to detector
    det = PhasePhotonics()
    if not det.open():
        logger.error("Failed to connect to PhasePhotonics detector")
        return False
    
    try:
        # Read current calibration
        logger.info("Reading current calibration from EEPROM...")
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
        
        logger.info("Current calibration coefficients:")
        for i, coeff in enumerate(current_coeffs):
            logger.info(f"  c{i}: {coeff}")
        
        # Create new coefficient array
        new_coeffs = np.array(NEW_COEFFICIENTS, dtype='>f8')  # Big-endian float64
        
        logger.info("\nNew calibration coefficients:")
        for i, coeff in enumerate(new_coeffs):
            logger.info(f"  c{i}: {coeff}")
        
        # Verify wavelength range with new coefficients
        from numpy.polynomial import Polynomial
        calibration_curve = Polynomial(new_coeffs)
        wl_min = calibration_curve(0)
        wl_max = calibration_curve(1847)
        
        logger.info(f"\nNew wavelength range: {wl_min:.2f} - {wl_max:.2f} nm")
        
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
            
            # Check if they match
            if np.allclose(verify_coeffs, new_coeffs):
                logger.info("\n✓✓✓ Calibration verified successfully!")
                return True
            else:
                logger.error("\n✗✗✗ Verification failed - coefficients don't match!")
                return False
        else:
            logger.error(f"✗ Failed to write calibration (error code: {result})")
            return False
            
    except Exception as e:
        logger.error(f"Error during calibration write: {e}", exc_info=True)
        return False
    finally:
        det.close()
        logger.info("\nDetector disconnected")


if __name__ == "__main__":
    success = write_calibration()
    if success:
        print("\n" + "="*70)
        print("SUCCESS: New calibration written and verified!")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("FAILED: Calibration was not written")
        print("="*70)
