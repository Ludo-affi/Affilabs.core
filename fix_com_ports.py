"""Fix Windows driver for Pico COM ports

This script will attempt to trigger Windows to reinstall drivers for the COM ports.
"""
import subprocess
import sys

print("=" * 70)
print("WINDOWS USB SERIAL DRIVER FIX")
print("=" * 70)

print("\nYour Pico controllers are detected by Windows but the drivers aren't")
print("properly loaded. Here's how to fix it:\n")

print("OPTION 1: Automatic driver reinstall (requires admin)")
print("-" * 70)
print("Run these commands in an Administrator PowerShell:\n")
print("1. Disable and re-enable each COM port:")
print("   $devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like 'USB Serial Device*' -and $_.Status -eq 'Unknown'}")
print("   foreach ($dev in $devices) { Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false; Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false }")
print()

print("OPTION 2: Manual driver update (recommended)")
print("-" * 70)
print("1. Open Device Manager (devmgmt.msc)")
print("2. Look under 'Ports (COM & LPT)'")
print("3. For each 'USB Serial Device' with a yellow warning:")
print("   a. Right-click → Update driver")
print("   b. Choose 'Browse my computer for drivers'")
print("   c. Choose 'Let me pick from a list of available drivers'")
print("   d. Select 'USB Serial Device' or 'USB Serial Port'")
print("   e. Click Next")
print()

print("OPTION 3: Quick fix - unplug and replug")
print("-" * 70)
print("1. Unplug ALL your Pico controllers")
print("2. Wait 5 seconds")
print("3. Plug in ONE controller")
print("4. Wait for Windows to install drivers")
print("5. Repeat for each controller")
print()

print("OPTION 4: Install CH340 drivers (if using clone boards)")
print("-" * 70)
print("Some Pico clones use CH340 USB chips. Download driver from:")
print("https://www.wch-ic.com/downloads/CH341SER_EXE.html")
print()

print("=" * 70)
print("\nAfter trying one of these options, run: python test_direct_controller.py")
print("=" * 70)

# Try to list what's detected
print("\nCurrent Windows detection status:")
print("-" * 70)
try:
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Serial*' -and $_.Class -eq 'Ports'} | Select-Object Status, FriendlyName, InstanceId | Format-Table -AutoSize"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
except Exception as e:
    print(f"Could not query devices: {e}")
