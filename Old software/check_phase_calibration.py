"""Check Phase Photonics detector calibration."""
import sys
from pathlib import Path

# Add Phase Photonics path
sys.path.insert(0, str(Path(__file__).parent / "Phase Photonics Modifications"))

from utils.SpectrometerAPI import SpectrometerAPI, SENSOR_DATA_LEN
from ftd2xx import listDevices
from numpy import all, arange, frombuffer, isnan
from numpy.polynomial import Polynomial

def check_calibration():
    # List devices
    devices = [s.decode() for s in listDevices() if s.startswith(b"ST")]
    print(f"Found {len(devices)} Phase Photonics device(s):")
    for i, dev in enumerate(devices):
        print(f"  {i}: {dev}")

    if not devices:
        print("No Phase Photonics devices found!")
        return

    # Initialize API
    dll_path = Path(__file__).parent / "Phase Photonics Modifications" / "utils" / "SensorT_x64.dll"
    print(f"\nUsing DLL: {dll_path}")
    print(f"DLL exists: {dll_path.exists()}")

    api = SpectrometerAPI(dll_path)

    # Open device
    device_name = devices[0]
    print(f"\nOpening device: {device_name}")
    spec = api.usb_initialize(device_name)

    if spec is None:
        print("Failed to initialize spectrometer!")
        return

    print("Device opened successfully!")

    # Read calibration
    print(f"\nReading calibration data...")
    CONFIG_SIZE = 4096
    CALIBRATION_OFFSET = 3072
    CALIBRATION_DEGREE = 4

    try:
        bytes_read, config = api.usb_read_config(spec, 0)
        print(f"Bytes read: {bytes_read}/{CONFIG_SIZE}")

        if bytes_read == CONFIG_SIZE:
            coeffs = frombuffer(
                config.data,
                ">f8",  # Big-endian float64
                CALIBRATION_DEGREE,
                CALIBRATION_OFFSET,
            )

            print(f"\nCalibration coefficients ({len(coeffs)} values):")
            for i, coeff in enumerate(coeffs):
                print(f"  C{i}: {coeff}")

            if all(isnan(coeffs)):
                print("\n⚠️  WARNING: All coefficients are NaN - spectrometer NOT calibrated!")
            else:
                print("\n✓ Valid calibration found!")

                # Calculate wavelength array
                calibration_curve = Polynomial(coeffs)
                wavelengths = calibration_curve(arange(SENSOR_DATA_LEN))

                print(f"\nWavelength range:")
                print(f"  Pixels: {SENSOR_DATA_LEN}")
                print(f"  Min wavelength: {wavelengths[0]:.2f} nm")
                print(f"  Max wavelength: {wavelengths[-1]:.2f} nm")
                print(f"  Center wavelength: {wavelengths[SENSOR_DATA_LEN//2]:.2f} nm")
                print(f"  Average spacing: {(wavelengths[-1] - wavelengths[0]) / SENSOR_DATA_LEN:.3f} nm/pixel")
        else:
            print(f"⚠️  ERROR: Read {bytes_read} bytes, expected {CONFIG_SIZE}")

    except Exception as e:
        print(f"⚠️  ERROR reading calibration: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nClosing device...")
        # Note: Add proper close method if available in API

if __name__ == "__main__":
    check_calibration()
