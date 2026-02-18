"""Reset USB4000/Flame-T detector when stuck or timing out.

This script:
1. Closes any open connections to the spectrometer
2. Resets the USB device
3. Verifies the detector is accessible again

Use this when you see timeouts like: [Errno 10060] Operation timed out
"""

import sys
import os

# Add affilabs to path
sys.path.insert(0, os.path.dirname(__file__))

# Initialize libusb paths BEFORE importing seabreeze
from affilabs.utils.libusb_init import init_libusb_paths
init_libusb_paths()

import time
import seabreeze
seabreeze.use('pyseabreeze')
from seabreeze.spectrometers import list_devices, Spectrometer

print("=" * 70)
print("USB SPECTROMETER RESET TOOL")
print("=" * 70)

# Step 1: Find all devices
print("\n1. Scanning for Ocean Optics spectrometers...")
try:
    devices = list_devices()
    print(f"   Found {len(devices)} device(s)")
    
    if len(devices) == 0:
        print("   ❌ No devices found - cannot reset")
        print("\n   Troubleshooting:")
        print("   - Check USB cable connection")
        print("   - Try a different USB port")
        print("   - Replug the device")
        sys.exit(1)
    
    for i, dev in enumerate(devices, 1):
        print(f"\n   Device {i}:")
        print(f"     Model: {dev.model}")
        print(f"     Serial: {dev.serial_number}")
        
except Exception as e:
    print(f"   ❌ Error scanning: {e}")
    sys.exit(1)

# Step 2: Close any open connections
print("\n2. Closing any open connections...")
closed_count = 0
for dev in devices:
    try:
        spec = Spectrometer(dev)
        spec.close()
        closed_count += 1
        print(f"   ✓ Closed connection to {dev.serial_number}")
    except Exception as e:
        if "already" in str(e).lower():
            print(f"   ⚠️  {dev.serial_number} already open in another process")
        else:
            print(f"   ℹ️  {dev.serial_number}: {e}")

if closed_count > 0:
    print(f"\n   Closed {closed_count} connection(s)")
    print("   Waiting for device to reset...")
    time.sleep(1)
else:
    print("   No open connections found")

# Step 3: Try USB reset (low-level)
print("\n3. Attempting USB device reset...")
try:
    import usb.core
    import usb.util
    
    # Ocean Optics VID
    OCEAN_OPTICS_VID = 0x2457
    
    # Get backend
    try:
        from affilabs.utils.libusb_init import get_libusb_backend
        backend = get_libusb_backend()
    except:
        backend = None
    
    # Find all Ocean Optics devices
    usb_devices = list(usb.core.find(
        find_all=True,
        idVendor=OCEAN_OPTICS_VID,
        backend=backend
    ))
    
    if usb_devices:
        for usb_dev in usb_devices:
            try:
                print(f"   Resetting USB device VID=0x{usb_dev.idVendor:04x} PID=0x{usb_dev.idProduct:04x}...")
                usb_dev.reset()
                print("   ✓ USB reset successful")
                time.sleep(0.5)
            except Exception as e:
                print(f"   ⚠️  USB reset failed: {e}")
    else:
        print("   ℹ️  No USB devices found for low-level reset")
        
except Exception as e:
    print(f"   ⚠️  USB reset not available: {e}")

# Step 4: Wait for device to re-enumerate
print("\n4. Waiting for device to re-enumerate...")
time.sleep(2)

# Step 5: Verify device is accessible
print("\n5. Verifying device accessibility...")
try:
    devices = list_devices()
    
    if len(devices) == 0:
        print("   ❌ No devices found after reset!")
        print("\n   Try:")
        print("   - Physically unplug and replug the USB cable")
        print("   - Check Device Manager for driver issues")
        sys.exit(1)
    
    # Try to open and communicate
    success = False
    for dev in devices:
        try:
            spec = Spectrometer(dev)
            
            # Try a read
            wavelengths = spec.wavelengths()
            intensities = spec.intensities()
            
            print(f"\n   ✅ Device {dev.serial_number} is fully functional!")
            print(f"      Model: {dev.model}")
            print(f"      Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
            print(f"      Read {len(intensities)} intensity values")
            
            spec.close()
            success = True
            
        except Exception as e:
            print(f"\n   ❌ Device {dev.serial_number} still has issues: {e}")
    
    if success:
        print("\n" + "=" * 70)
        print("✅ RESET SUCCESSFUL - Device ready to use!")
        print("=" * 70)
        print("\nYou can now:")
        print("  - Run your calibration again")
        print("  - Start the main application")
    else:
        print("\n" + "=" * 70)
        print("⚠️  RESET INCOMPLETE - Manual intervention needed")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Close ANY programs using the spectrometer")
        print("  2. Physically unplug the USB cable")
        print("  3. Wait 5 seconds")
        print("  4. Plug it back in")
        print("  5. Run this script again")
        
except Exception as e:
    print(f"   ❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
