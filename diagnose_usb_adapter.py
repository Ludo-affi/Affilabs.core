"""
USB Adapter Diagnostic Tool

Helps diagnose why hardware isn't detected through USB-C adapters.
"""

import sys

print("="*70)
print("  USB ADAPTER DIAGNOSTIC TOOL")
print("="*70)

# 1. Check serial ports
print("\n1. SERIAL PORT SCAN:")
print("-"*70)
try:
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    print(f"Total COM ports found: {len(ports)}")
    
    if ports:
        for p in ports:
            print(f"\n  Port: {p.device}")
            print(f"    VID: {hex(p.vid) if p.vid else 'None'}")
            print(f"    PID: {hex(p.pid) if p.pid else 'None'}")
            print(f"    Manufacturer: {p.manufacturer or 'Unknown'}")
            print(f"    Description: {p.description or 'Unknown'}")
            print(f"    Serial Number: {p.serial_number or 'Unknown'}")
    else:
        print("\n  ❌ NO COM PORTS DETECTED")
        print("  This usually means:")
        print("    - USB adapter driver not installed")
        print("    - Device not recognized by Windows")
        print("    - USB-C adapter incompatible")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 2. Check USB devices (pyusb)
print("\n\n2. USB DEVICE SCAN (via pyusb):")
print("-"*70)
try:
    import usb.core
    devices = list(usb.core.find(find_all=True))
    print(f"Total USB devices found: {len(devices)}")
    
    if devices:
        # Look for Pico (0x2e8a) and Ocean Optics (0x2457)
        pico_devices = [d for d in devices if d.idVendor == 0x2e8a]
        ocean_devices = [d for d in devices if d.idVendor == 0x2457]
        
        if pico_devices:
            print(f"\n  ✓ Found {len(pico_devices)} Raspberry Pi Pico device(s):")
            for d in pico_devices:
                print(f"    VID:PID = {hex(d.idVendor)}:{hex(d.idProduct)}")
                try:
                    print(f"    Manufacturer: {usb.util.get_string(d, d.iManufacturer)}")
                    print(f"    Product: {usb.util.get_string(d, d.iProduct)}")
                except:
                    pass
        
        if ocean_devices:
            print(f"\n  ✓ Found {len(ocean_devices)} Ocean Optics device(s):")
            for d in ocean_devices:
                print(f"    VID:PID = {hex(d.idVendor)}:{hex(d.idProduct)}")
                try:
                    print(f"    Manufacturer: {usb.util.get_string(d, d.iManufacturer)}")
                    print(f"    Product: {usb.util.get_string(d, d.iProduct)}")
                    if hasattr(d, 'serial_number'):
                        print(f"    Serial: {d.serial_number}")
                except:
                    pass
        
        if not pico_devices and not ocean_devices:
            print("\n  ⚠️  No Pico or Ocean Optics devices found")
            print(f"  Found {len(devices)} other USB devices")
            print("\n  All devices:")
            for d in devices:
                print(f"    VID:PID = {hex(d.idVendor)}:{hex(d.idProduct)}")
    else:
        print("  ❌ NO USB DEVICES DETECTED")
        print("  This usually means:")
        print("    - libusb backend not working")
        print("    - USB devices not enumerated")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# 3. Check FTDI devices
print("\n\n3. FTDI DEVICE SCAN (for AffiPump):")
print("-"*70)
try:
    import ftd2xx
    num_devices = ftd2xx.createDeviceInfoList()
    print(f"Total FTDI devices found: {num_devices}")
    
    if num_devices > 0:
        for i in range(num_devices):
            info = ftd2xx.getDeviceInfoDetail(i)
            print(f"\n  Device {i}:")
            print(f"    Serial: {info['serial'].decode() if isinstance(info['serial'], bytes) else info['serial']}")
            print(f"    Description: {info['description'].decode() if isinstance(info['description'], bytes) else info['description']}")
            print(f"    Type: {info['type']}")
    else:
        print("  ℹ️  No FTDI devices (AffiPump not connected - this is optional)")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 4. Recommendations
print("\n\n" + "="*70)
print("RECOMMENDATIONS:")
print("="*70)

if ports or devices:
    print("✓ Hardware detected! Try these steps:")
    print("  1. Close this diagnostic")
    print("  2. Restart the main application")
    print("  3. Click 'Scan Hardware' button")
    print("  4. If still fails, try unplugging and replugging USB adapter")
else:
    print("❌ NO HARDWARE DETECTED - Try these steps:")
    print("\n1. Check Device Manager (Windows):")
    print("   - Press Win+X → Device Manager")
    print("   - Look for devices with yellow exclamation marks")
    print("   - Check 'Ports (COM & LPT)' section")
    print("   - Check 'Universal Serial Bus devices' section")
    
    print("\n2. Install USB drivers:")
    print("   - Pico: Windows should auto-detect")
    print("   - Ocean Optics: Install OmniDriver or OceanView")
    print("   - Try different USB-C adapter (some don't pass through properly)")
    
    print("\n3. Test with different USB ports:")
    print("   - Try USB-A ports directly (bypass adapter)")
    print("   - Try different USB-C ports on your computer")
    print("   - Some USB-C adapters only support charging, not data")
    
    print("\n4. Verify USB-C adapter specifications:")
    print("   - Must support DATA transfer (not just power)")
    print("   - Should be USB 3.0 or higher")
    print("   - Some cheap adapters don't enumerate USB devices")

print("\n" + "="*70)
print("If still having issues, run this with admin privileges:")
print("  Right-click PowerShell → Run as Administrator")
print("  Then run: python diagnose_usb_adapter.py")
print("="*70)
