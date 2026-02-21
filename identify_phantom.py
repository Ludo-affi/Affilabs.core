#!/usr/bin/env python
"""Identify and remove the phantom device blocking the real detector."""

import usb.core

print("=" * 80)
print("IDENTIFYING PHANTOM VS REAL DEVICE")
print("=" * 80)

OCEAN_OPTICS_VID = 0x2457

try:
    from affilabs.utils.libusb_init import get_libusb_backend
    backend = get_libusb_backend()
except:
    backend = None

devices = list(usb.core.find(find_all=True, idVendor=OCEAN_OPTICS_VID, backend=backend))

print(f"\nFound {len(devices)} devices\n")

phantom_indices = []
real_indices = []

for i, dev in enumerate(devices):
    print(f"Testing Device [{i}] - Bus {dev.bus}, Address {dev.address}...")

    try:
        # Try to reset and open
        dev.reset()

        # Try to read descriptor
        try:
            product = usb.util.get_string(dev, dev.iProduct)
            manufacturer = usb.util.get_string(dev, dev.iManufacturer)
            print(f"  [REAL] Successfully opened")
            print(f"         Product: {product}")
            print(f"         Manufacturer: {manufacturer}")
            real_indices.append(i)
        except:
            print(f"  [PHANTOM] Opened but can't read descriptors")
            phantom_indices.append(i)
    except Exception as e:
        print(f"  [PHANTOM] Failed to open: {e}")
        phantom_indices.append(i)

    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nWorking devices: {real_indices}")
print(f"Phantom devices (to remove): {phantom_indices}\n")

if not phantom_indices:
    print("[SUCCESS] No phantom devices to remove!")
    exit(0)

print("=" * 80)
print("REGISTRY PATH TO REMOVE")
print("=" * 80 + "\n")

for i in phantom_indices:
    dev = devices[i]
    print(f"Device [{i}]:")
    print(f"  Bus: {dev.bus}")
    print(f"  Address: {dev.address}")
    print(f"  VID: 0x{dev.idVendor:04x}")
    print(f"  PID: {dev.idProduct:04x}\n")

# Now get the instance IDs from Device Manager
import subprocess

ps_cmd = """
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*'} |
Select-Object FriendlyName, Status, InstanceId |
ForEach-Object {
    $status = if ($_.Status -eq 'OK') { 'OK  ' } else { 'FAIL' }
    Write-Host "$status | $($_.InstanceId)"
}
"""

print("Mapping to Device Manager (run as Administrator):")
print("=" * 80)
print("\nCurrent device entries in Device Manager:\n")

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    print(result.stdout)
except:
    pass

print("=" * 80)
print("\nINSTRUCTIONS TO REMOVE PHANTOM:")
print("=" * 80)
print("""
Option 1 - GUI (easiest):
1. Open Device Manager (Win+R, devmgmt.msc)
2. View > Show hidden devices
3. Expand "Universal Serial Bus controllers"
4. Find "Ocean Optics FLAME-T" entries with warning/error icons
5. Right-click each phantom > Uninstall device
6. Check "Delete the driver software"
7. Click Uninstall

Option 2 - PowerShell (as Administrator):
1. Right-click PowerShell, select "Run as Administrator"
2. Run this command:

Remove-Item "HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_2457&PID_1022\\*" `
    -Force -Recurse -Exclude "*1*" -ErrorAction SilentlyContinue

Note: This keeps only one device (the *1* entry)

Option 3 - Delete all and rescan:
1. Run: Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*'} |
         Foreach {$_ | Remove-Item -Force -Recurse}
2. Unplug detector USB
3. Plug back in
4. Windows will re-detect the real device

After removal:
1. Unplug detector USB cable
2. Wait 5 seconds
3. Plug back in
4. Run: python detector_diagnostic_simple.py
""")
