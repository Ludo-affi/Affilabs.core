"""Get Phase Photonics Detector Information

Retrieves all available information about the connected detector:
- Serial number
- Firmware version
- Wavelength range
- Pixel count
- ADC resolution
- Any other identifiable information
"""

from affilabs.utils.phase_photonics_wrapper import PhasePhotonics
from affilabs.utils.phase_photonics_api import (
    SENSOR_DATA_LEN,
    ADC_RESOLUTION,
    MAX_COUNT,
    WAVELENGTH_MIN,
    WAVELENGTH_MAX,
    FIRMWARE_VERSION,
)
from affilabs.utils.logger import logger


def get_detector_info():
    """Retrieve and display all detector information."""
    print("\n" + "="*80)
    print("PHASE PHOTONICS DETECTOR INFORMATION")
    print("="*80)
    
    try:
        # Connect
        detector = PhasePhotonics()
        detector.get_device_list()
        
        if not detector.devs:
            print("\n❌ No PhasePhotonics detector found")
            print("\nSearching for devices with 'ST' serial prefix...")
            return
        
        print(f"\n✓ Found {len(detector.devs)} device(s)")
        for i, dev in enumerate(detector.devs):
            print(f"  Device {i+1}: {dev}")
        
        if not detector.open():
            print("❌ Failed to connect to detector")
            return
        
        # Basic info
        print("\n" + "="*80)
        print("DEVICE IDENTIFICATION")
        print("="*80)
        print(f"Serial Number: {detector.serial_number}")
        print(f"Manufacturer: Phase Photonics")
        print(f"Expected Firmware: {FIRMWARE_VERSION}")
        
        # Try to read actual firmware version from detector
        try:
            # Read a frame to get state info
            api = detector.api
            handle = detector.spec
            
            # Allocate frame structure
            from affilabs.utils.phase_photonics_api import SENSOR_FRAME_T
            frame = SENSOR_FRAME_T()
            
            # Read from detector
            ret = api.usb_read_image_v2(handle, frame)
            
            if ret == 0:
                state = frame.state
                print(f"\nFirmware Version (from detector):")
                print(f"  Major: {state.major_version}")
                print(f"  Minor: {state.minor_version}")
                print(f"  Full: {state.major_version}.{state.minor_version}")
                
                print(f"\nDetector State:")
                print(f"  SOF marker: 0x{state.sof:08X}")
                print(f"  Integration time: {state.integration} μs ({state.integration/1000:.1f} ms)")
                print(f"  Offset value: {state.offset}")
                print(f"  Averaging setting: {state.averaging}")
                print(f"  Trigger mode: {state.trig_mode} (0=Internal, 1=ExtNeg, 2=ExtPos)")
                print(f"  Trigger timeout: {state.trig_tmo} ms")
                print(f"  Shutter state: {state.shutter_state}")
                print(f"  Lamp state: {state.lamp_state}")
                print(f"  GPIO: 0x{state.gpio:08X}")
            else:
                print(f"\n⚠ Could not read detector state (error code: {ret})")
        except Exception as e:
            print(f"\n⚠ Could not read firmware version: {e}")
        
        # Specifications
        print("\n" + "="*80)
        print("DETECTOR SPECIFICATIONS")
        print("="*80)
        print(f"Pixel Count: {SENSOR_DATA_LEN} pixels")
        print(f"ADC Resolution: {ADC_RESOLUTION} bits")
        print(f"Maximum Counts: {MAX_COUNT}")
        print(f"Wavelength Range: {WAVELENGTH_MIN} - {WAVELENGTH_MAX} nm")
        
        # Read wavelength calibration
        print("\n" + "="*80)
        print("WAVELENGTH CALIBRATION")
        print("="*80)
        
        wavelengths = detector.read_wavelength()
        if wavelengths is not None:
            print(f"Calibration loaded: {len(wavelengths)} points")
            print(f"  Min wavelength: {wavelengths.min():.2f} nm")
            print(f"  Max wavelength: {wavelengths.max():.2f} nm")
            print(f"  Range: {wavelengths.max() - wavelengths.min():.2f} nm")
            print(f"  First pixel: {wavelengths[0]:.2f} nm")
            print(f"  Last pixel: {wavelengths[-1]:.2f} nm")
            
            # Check for valid calibration
            if wavelengths[0] < 400 or wavelengths[-1] > 1000:
                print("\n⚠ WARNING: Wavelength calibration seems incorrect!")
        else:
            print("⚠ Could not read wavelength calibration")
        
        # Performance specs
        print("\n" + "="*80)
        print("PERFORMANCE CHARACTERISTICS")
        print("="*80)
        print(f"Min Integration Time: 0.1 ms (100 μs)")
        print(f"Max Integration Time: 5000 ms (5 seconds)")
        print(f"Typical Read Time: ~44 ms (22 ms integration + 22 ms USB)")
        print(f"Max Averaging: {255} scans (not working in current firmware)")
        
        # USB/Communication
        print("\n" + "="*80)
        print("COMMUNICATION")
        print("="*80)
        print(f"Interface: USB (FTDI chip)")
        print(f"DLL: Sensor64bit.dll (OEM recommended)")
        print(f"Driver: D2XX (FTDI direct driver)")
        
        # Test connection
        ping_result = api.usb_ping(handle)
        print(f"Connection test (ping): {'✅ OK' if ping_result == 0 else f'❌ Failed (code {ping_result})'}")
        
        print("\n" + "="*80)
        print("OEM INFORMATION")
        print("="*80)
        print("Manufacturer: Phase Photonics B.V.")
        print("Location: Enschede, Netherlands")
        print("Technology: Integrated photonics spectrometer")
        print("Website: phasephotonics.com")
        print("\nProduct Line: Compact spectrometer module")
        print("Serial Prefix: ST (Spectrometer Technology)")
        
        print("\n" + "="*80 + "\n")
        
        detector.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.exception("Failed to get detector info")
        raise


if __name__ == "__main__":
    get_detector_info()
