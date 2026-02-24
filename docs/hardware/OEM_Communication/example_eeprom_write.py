"""
Example Python code for PhasePhotonics detector EEPROM operations

This demonstrates:
1. Reading wavelength calibration from EEPROM
2. Writing wavelength calibration to EEPROM
3. The hardware averaging integration time bug

PURPOSE: Show to PhasePhotonics programmer to demonstrate:
- How we interact with the detector API
- The bug with usb_set_averaging() ignoring integration time
"""

import ctypes
import struct
import numpy as np
from numpy.polynomial import Polynomial
import time
import sys

# Add path for imports
sys.path.insert(0, r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\test\ezControl-AI")

# Import PhasePhotonics API
from affilabs.utils.phase_photonics_api import PhasePhotonicsAPI, config_contents
from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

# EEPROM structure constants
CONFIG_SIZE = 4096
CALIBRATION_OFFSET = 3072  # Wavelength calibration starts at byte 3072
CALIBRATION_DEGREE = 4      # 4 coefficients: c0, c1, c2, c3


def read_eeprom_calibration(detector):
    """Read wavelength calibration coefficients from EEPROM.

    Returns:
        numpy.ndarray: [c0, c1, c2, c3] calibration coefficients
    """
    print("\n" + "="*80)
    print("READING WAVELENGTH CALIBRATION FROM EEPROM")
    print("="*80)

    # Read EEPROM config area 0
    ret, cc = detector.api.usb_read_config(detector.spec, area_number=0)

    if ret != 0:
        print(f"ERROR: Failed to read EEPROM (error code: {ret})")
        return None

    print(f"Successfully read {len(cc.data)} bytes from EEPROM")

    # Extract wavelength calibration coefficients
    # Format: 4 double-precision floats (8 bytes each) starting at offset 3072
    coeffs = np.frombuffer(
        cc.data,
        dtype=">f8",  # Big-endian float64
        count=CALIBRATION_DEGREE,
        offset=CALIBRATION_OFFSET
    )

    print(f"\nWavelength calibration coefficients:")
    print(f"  c0 (offset):     {coeffs[0]:.6f} nm")
    print(f"  c1 (linear):     {coeffs[1]:.9e}")
    print(f"  c2 (quadratic):  {coeffs[2]:.9e}")
    print(f"  c3 (cubic):      {coeffs[3]:.9e}")

    # Compute wavelength range
    poly = Polynomial(coeffs)
    wl_min = poly(0)
    wl_max = poly(1847)  # 1848 pixels, 0-indexed

    print(f"\nWavelength range: {wl_min:.2f} - {wl_max:.2f} nm")

    return coeffs


def write_eeprom_calibration(detector, coefficients):
    """Write wavelength calibration coefficients to EEPROM.

    Args:
        coefficients: [c0, c1, c2, c3] array of calibration coefficients

    WARNING: This writes to EEPROM! Only use with valid calibration data!
    """
    print("\n" + "="*80)
    print("WRITING WAVELENGTH CALIBRATION TO EEPROM")
    print("="*80)
    print("\nWARNING: This will modify detector EEPROM!")
    print("Only proceed if you have valid calibration coefficients.\n")

    # Read current EEPROM contents first
    ret, cc = detector.api.usb_read_config(detector.spec, area_number=0)
    if ret != 0:
        print(f"ERROR: Failed to read EEPROM (error code: {ret})")
        return False

    print(f"Read {len(cc.data)} bytes from EEPROM")

    # Convert coefficients to big-endian float64 bytes
    coeff_bytes = struct.pack('>dddd', *coefficients)

    print(f"\nNew calibration coefficients:")
    print(f"  c0: {coefficients[0]:.6f}")
    print(f"  c1: {coefficients[1]:.9e}")
    print(f"  c2: {coefficients[2]:.9e}")
    print(f"  c3: {coefficients[3]:.9e}")

    # Modify EEPROM data structure
    # Replace bytes at CALIBRATION_OFFSET with new coefficients
    data_array = bytearray(cc.data)
    data_array[CALIBRATION_OFFSET:CALIBRATION_OFFSET+32] = coeff_bytes

    # Copy back to config_contents structure
    for i, byte in enumerate(data_array):
        cc.data[i] = byte

    # Write to EEPROM
    print(f"\nWriting to EEPROM...")
    ret = detector.api.usb_write_config(detector.spec, cc, area_number=0)

    if ret == 0:
        print("SUCCESS: Calibration written to EEPROM")
        return True
    else:
        print(f"ERROR: Failed to write EEPROM (error code: {ret})")
        return False


def demonstrate_hardware_averaging_bug(detector):
    """Demonstrate the bug where usb_set_averaging ignores integration time.

    BUG REPORT FOR PHASEPHOTONICS:
    When usb_set_averaging(num_scans) is called, the detector performs
    num_scans acquisitions but IGNORES the integration time set by
    usb_set_interval(). It uses a very short integration time (~1ms)
    instead of the configured value.
    """
    print("\n" + "="*80)
    print("DEMONSTRATING HARDWARE AVERAGING BUG")
    print("="*80)

    target_integration_ms = 10.0  # Target: 10ms integration time

    print(f"\n1. Setting integration time to {target_integration_ms}ms")
    detector.set_integration(target_integration_ms)
    print(f"   Integration time set: {detector._integration_time * 1000:.3f}ms")

    print(f"\n2. Testing single scan (no averaging)")
    detector.set_averaging(1)

    start = time.perf_counter()
    spectrum1 = detector.read_intensity()
    time1 = (time.perf_counter() - start) * 1000

    print(f"   Time for 1 scan: {time1:.2f}ms")
    print(f"   Expected: ~{target_integration_ms + 8:.1f}ms (integration + USB)")

    print(f"\n3. Testing 10 scans with hardware averaging")
    detector.set_averaging(10)

    start = time.perf_counter()
    spectrum10 = detector.read_intensity()
    time10 = (time.perf_counter() - start) * 1000

    print(f"   Time for 10 scans: {time10:.2f}ms")
    print(f"   Expected: ~{10 * target_integration_ms + 8:.1f}ms minimum")
    print(f"   (10 scans × {target_integration_ms}ms + USB overhead)")

    print(f"\n4. ANALYSIS:")
    expected_min = 10 * target_integration_ms

    if time10 < expected_min * 0.5:
        print(f"   BUG CONFIRMED!")
        print(f"   Hardware averaging took {time10:.1f}ms")
        print(f"   But 10 × {target_integration_ms}ms = {expected_min:.1f}ms minimum required!")
        print(f"   The detector is IGNORING the integration time setting!")
        print(f"   It is using ~{(time10 - 8) / 10:.1f}ms per scan instead of {target_integration_ms}ms")
    else:
        print(f"   Hardware averaging appears to be working correctly")

    detector.set_averaging(1)


def main():
    """Main demonstration."""
    print("="*80)
    print("PhasePhotonics EEPROM Operations Example")
    print("="*80)
    print("\nThis script demonstrates:")
    print("1. Reading wavelength calibration from EEPROM")
    print("2. Writing wavelength calibration to EEPROM (disabled by default)")
    print("3. Hardware averaging integration time bug")
    print()

    # Connect to detector
    detector = PhasePhotonics()
    if not detector.open():
        print("ERROR: Failed to connect to detector")
        return

    print(f"Connected to: {detector.serial_number}")

    # 1. Read current calibration
    coeffs = read_eeprom_calibration(detector)

    # 2. Write calibration (COMMENTED OUT - only enable with valid data!)
    # WARNING: Uncommenting this will modify EEPROM!
    #
    # new_coeffs = [
    #     555.928,      # c0: offset (nm)
    #     1.0284e-1,    # c1: linear term
    #     -1.234e-6,    # c2: quadratic term
    #     5.678e-10     # c3: cubic term
    # ]
    # write_eeprom_calibration(detector, new_coeffs)

    # 3. Demonstrate hardware averaging bug
    demonstrate_hardware_averaging_bug(detector)

    detector.close()

    print("\n" + "="*80)
    print("SUMMARY FOR PHASEPHOTONICS PROGRAMMER:")
    print("="*80)
    print("""
BUG REPORT: usb_set_averaging() ignores integration time

EXPECTED BEHAVIOR:
  - usb_set_interval(integration_us) sets integration time
  - usb_set_averaging(num_scans) tells detector to average N scans
  - Each scan should use the configured integration time
  - Total time = (num_scans × integration_time) + USB_overhead

ACTUAL BEHAVIOR:
  - usb_set_averaging(num_scans) performs N scans
  - BUT ignores integration time set by usb_set_interval()
  - Uses very short integration time (~1ms) instead
  - Total time is approximately constant (~16ms) regardless of num_scans or integration time

WORKAROUND:
  - We must use software averaging (Python loop with multiple reads)
  - This is slower: num_scans × (integration_time × 1.93) per channel

QUESTION FOR OEM:
  - Is this a bug or intended behavior?
  - Is there a different API call needed to set integration time with averaging?
  - Can this be fixed in firmware?
""")
    print("="*80)


if __name__ == "__main__":
    main()
