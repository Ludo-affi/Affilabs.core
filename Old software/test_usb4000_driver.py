"""Test USB4000 driver configuration."""

import sys

print("=" * 60)
print("USB4000 Driver Test")
print("=" * 60)

# Test 1: Check SeaBreeze installation
print("\n1. Checking SeaBreeze installation...")
try:
    import seabreeze
    print(f"   ✓ SeaBreeze version: {seabreeze.__version__}")
    seabreeze.use('cseabreeze')
    print("   ✓ Using cseabreeze backend")
except ImportError as e:
    print(f"   ✗ SeaBreeze not installed: {e}")
    sys.exit(1)

# Test 2: List devices
print("\n2. Scanning for devices...")
try:
    from seabreeze.spectrometers import list_devices
    devices = list_devices()
    print(f"   Found {len(devices)} device(s)")
    for i, dev in enumerate(devices):
        print(f"   Device {i}: {dev.model} (Serial: {dev.serial_number})")
except Exception as e:
    print(f"   ✗ Error listing devices: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check USB devices in Windows
print("\n3. Checking Windows USB devices...")
try:
    import subprocess
    result = subprocess.run(
        ['powershell', '-Command',
         "Get-PnpDevice | Where-Object { $_.FriendlyName -like '*USB4000*' -or $_.FriendlyName -like '*Ocean*' } | Select-Object FriendlyName, Status, InstanceId | Format-List"],
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        print(result.stdout)
    else:
        print("   No USB4000 devices found in Device Manager")
except Exception as e:
    print(f"   ✗ Error checking devices: {e}")

# Test 4: Check libusb
print("\n4. Checking libusb backend...")
try:
    import usb.core
    devices = usb.core.find(find_all=True, idVendor=0x2457)  # Ocean Optics vendor ID
    device_list = list(devices)
    print(f"   Found {len(device_list)} Ocean Optics USB device(s) via libusb")
    for dev in device_list:
        print(f"   - VID: 0x{dev.idVendor:04x}, PID: 0x{dev.idProduct:04x}")
except ImportError:
    print("   ✗ pyusb not installed (optional)")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSIS:")
print("=" * 60)
if len(devices) == 0:
    print("""
The USB4000 is NOT detected by SeaBreeze.

Possible causes:
1. Wrong driver installed (needs WinUSB driver)
2. Driver not properly installed
3. USB device not recognized

Solutions:
A. Install WinUSB driver using Zadig:
   - Download Zadig from https://zadig.akeo.ie/
   - Run Zadig as Administrator
   - Options → List All Devices
   - Select "USB4000" from dropdown
   - Select "WinUSB" as target driver
   - Click "Replace Driver" or "Install Driver"
   - Reconnect USB4000

B. Check Device Manager:
   - Look for "USB4000" or "Ocean Optics" device
   - If it has a yellow warning icon, update/reinstall driver
   - Right-click → Update Driver → Browse → Let me pick
   - Select "WinUSB" or "libusb" driver
""")
else:
    print("\n✓ USB4000 detected successfully!")

print("=" * 60)
