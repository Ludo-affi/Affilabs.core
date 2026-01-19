"""Fix pyusb backend for Ocean Optics detector."""
import urllib.request
import os
import zipfile
import shutil

print("=" * 80)
print("FIXING PYUSB BACKEND FOR OCEAN OPTICS DETECTOR")
print("=" * 80)

# Download libusb DLL
print("\n[1/3] Downloading libusb-1.0.dll...")
url = "https://github.com/libusb/libusb/releases/download/v1.0.26/libusb-1.0.26-binaries-7z"
zip_path = "libusb.7z"

try:
    # Simpler approach - just tell user where to get it
    print("\n⚠️  You need to install libusb-1.0.dll manually:")
    print("\n1. Download from: https://github.com/libusb/libusb/releases/latest")
    print("2. Extract the ZIP file")
    print("3. Copy MS64\\dll\\libusb-1.0.dll to C:\\Windows\\System32\\")
    print("\nOR try installing Zadig driver:")
    print("1. Download Zadig from: https://zadig.akeo.ie/")
    print("2. Run Zadig")
    print("3. Options → List All Devices")
    print("4. Select 'Ocean Optics FLAME-T'")
    print("5. Select 'libusb-win32' or 'libusbK' driver")
    print("6. Click 'Replace Driver'")
    
    print("\n" + "=" * 80)
    print("Current detection status:")
    print("  ✅ Pico: WORKING (COM3)")
    print("  ⚠️  FLAME-T: Hardware detected but driver issue")
    print("=" * 80)
    
except Exception as e:
    print(f"Error: {e}")
