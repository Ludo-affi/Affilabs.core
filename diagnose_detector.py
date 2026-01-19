"""Check for Ocean Optics USB detector (spectrometer)."""
import sys
import os

# Add affilabs to path
sys.path.insert(0, os.path.dirname(__file__))

# Initialize libusb paths BEFORE importing seabreeze
from affilabs.utils.libusb_init import init_libusb_paths, get_libusb_backend
init_libusb_paths()

try:
    import seabreeze
    seabreeze.use('pyseabreeze')
    from seabreeze.spectrometers import list_devices, Spectrometer
    
    print("=" * 70)
    print("OCEAN OPTICS DETECTOR DIAGNOSTIC")
    print("=" * 70)
    
    print("\n1. Checking for Ocean Optics USB spectrometers...")
    devices = list_devices()
    
    if len(devices) == 0:
        print("   ❌ NO DETECTORS FOUND")
        print("\nPossible causes:")
        print("1. Detector not connected to USB")
        print("2. USB cable issue (try different cable/port)")
        print("3. Detector not powered on")
        print("4. Driver issue")
    else:
        print(f"   ✅ Found {len(devices)} detector(s)!\n")
        
        for i, device in enumerate(devices, 1):
            print(f"Detector {i}:")
            print(f"   Model: {device.model}")
            print(f"   Serial: {device.serial_number}")
            
            try:
                spec = Spectrometer(device)
                print(f"   Status: ✅ Can open and communicate")
                
                # Get wavelengths
                wavelengths = spec.wavelengths()
                print(f"   Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
                print(f"   Pixels: {len(wavelengths)}")
                
                spec.close()
            except Exception as e:
                print(f"   Status: ⚠️ Device found but communication failed: {e}")
            
            print()
    
    print("=" * 70)
    
except ImportError as e:
    print("❌ seabreeze library not installed or not configured")
    print(f"   Error: {e}")
    print("\nMake sure seabreeze is installed in your Python environment")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
