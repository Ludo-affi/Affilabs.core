#!/usr/bin/env python
"""Check which driver is assigned to Ocean Optics devices."""

import subprocess
import sys

print("=" * 80)
print("CHECKING DEVICE DRIVERS IN DEVICE MANAGER")
print("=" * 80)

# Use Windows PowerShell to get device info
ps_script = """
Get-PnpDevice | Where-Object {$_.PNPClass -eq 'USBDevice' -or $_.FriendlyName -like '*Ocean*' -or $_.Description -like '*2457*'} |
Select-Object FriendlyName, Description, Status, ConfigManagerErrorCode, Manufacturer, DriverName |
Format-List
"""

try:
    print("\nQuerying device information via PowerShell...\n")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=10
    )

    output = result.stdout
    print(output)

    if result.stderr:
        print("\n[Warnings/Errors]")
        print(result.stderr)

except Exception as e:
    print(f"Error running PowerShell: {e}")

print("\n" + "=" * 80)
print("ALTERNATIVE: Using WMI to check USB devices")
print("=" * 80 + "\n")

ps_script2 = """
Get-WmiObject Win32_PnPSignedDriver | Where-Object {$_.DeviceName -like '*2457*' -or $_.DeviceName -like '*Ocean*' -or $_.DeviceName -like '*FLAME*'} |
Select-Object DeviceName, Manufacturer, DriverVersion, Inf |
Format-List
"""

try:
    result2 = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script2],
        capture_output=True,
        text=True,
        timeout=10
    )

    output2 = result2.stdout
    if output2.strip():
        print(output2)
    else:
        print("[No Ocean Optics drivers found via WMI]")

    if result2.stderr:
        print("\n[Warnings/Errors]")
        print(result2.stderr)

except Exception as e:
    print(f"Error running PowerShell: {e}")

print("\n" + "=" * 80)
print("MANUAL FIX INSTRUCTIONS")
print("=" * 80 + "\n")

print("If the device shows 'WinUSB' or 'usbser' driver instead of 'libusbK':")
print("\n1. Open Device Manager:")
print("   - Press Win+R, type 'devmgmt.msc', press Enter")
print("\n2. Find 'Ocean Optics' device under 'USB controllers' or 'Other devices'")
print("\n3. Right-click on it and select 'Update driver'")
print("\n4. Select 'Browse my computer for driver software'")
print("\n5. Click 'Let me pick from a list of available drivers on my computer'")
print("\n6. Look for 'libusbK' in the list")
print("\n7. If not listed, you may need to run Zadig again:")
print("    - Download: https://zadig.akeo.ie/")
print("    - Run Zadig")
print("    - Options > List All Devices")
print("    - Find: Ocean Optics FLAME-T")
print("    - Driver dropdown: libusbK")
print("    - Click 'Replace Driver'")
print("\n8. After driver change, unplug and replug the USB cable")
