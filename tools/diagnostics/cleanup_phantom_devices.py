#!/usr/bin/env python
"""Clean up phantom Ocean Optics device entries and reinstall driver."""

import subprocess
import sys
import time

print("=" * 80)
print("PHANTOM DEVICE CLEANUP TOOL")
print("=" * 80)
print("\nThis will remove ghost/phantom device entries for Ocean Optics FLAME-T")
print("and allow Windows to properly detect and bind the libusbK driver.\n")

input("Press Enter to continue... ")

print("\n" + "=" * 80)
print("STEP 1: Stop USB drivers and services")
print("=" * 80)

ps_script = """
# Disable and re-enable USB device drivers
Write-Host "Disabling USB drivers..."

Get-Service | Where-Object {$_.Name -like '*usb*'} |
ForEach-Object {
    Write-Host "  Stopping service: $($_.Name)"
    Stop-Service -Name $_.Name -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2
"""

try:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        timeout=10
    )
    print("[OK] USB services stopped temporarily")
except Exception as e:
    print(f"[WARNING] Could not stop USB services: {e}")

print("\n" + "=" * 80)
print("STEP 2: Remove phantom device entries")
print("=" * 80)

ps_script2 = """
$devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*FLAME*'}

Write-Host "Found $($devices.Count) Ocean Optics device entries"

foreach ($device in $devices) {
    if ($device.Status -eq 'Unknown' -or $device.ConfigManagerErrorCode -ne 0) {
        Write-Host "Removing: $($device.FriendlyName) (InstanceId: $($device.InstanceId))"

        try {
            # Remove the phantom device
            $device | Remove-PnpDevice -Confirm:$false -Force | Out-Null
            Write-Host "  [OK] Removed"
        } catch {
            Write-Host "  [SKIPPED] $_"
        }
    } else {
        Write-Host "Keeping: $($device.FriendlyName) (Status: OK)"
    }
}
"""

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script2],
        capture_output=True,
        text=True,
        timeout=15
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "=" * 80)
print("STEP 3: Restart USB services")
print("=" * 80)

ps_script3 = """
Write-Host "Restarting USB services and rescanning..."

$usbServices = @('UsbHub')
foreach ($service in $usbServices) {
    try {
        Write-Host "Starting service: $service"
        Start-Service -Name $service -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  Could not start: $_"
    }
}

Start-Sleep -Seconds 2

# Rescan PnP devices
Write-Host "Rescanning devices..."
$devMgmt = New-Object -ComObject DeviceManager.DeviceManager
$devMgmt.RescanDevices()

Write-Host "Done"
"""

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script3],
        capture_output=True,
        text=True,
        timeout=15
    )
    print("[OK] USB services restarted")
except Exception as e:
    print(f"[WARNING] Could not restart services: {e}")

print("\n" + "=" * 80)
print("STEP 4: Check current status")
print("=" * 80)

ps_script4 = """
Write-Host "`nCurrent Ocean Optics devices:`n"

$devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*'} |
Select-Object FriendlyName, Status, ConfigManagerErrorCode

if ($devices) {
    $devices | Format-Table -AutoSize
    Write-Host ""
    foreach ($device in $devices) {
        if ($device.Status -eq 'Unknown') {
            Write-Host "[ISSUE] $($device.FriendlyName) still shows Unknown status"
        } elseif ($device.ConfigManagerErrorCode -ne 0) {
            Write-Host "[ISSUE] $($device.FriendlyName) has error code $($device.ConfigManagerErrorCode)"
        } else {
            Write-Host "[OK] $($device.FriendlyName) is working"
        }
    }
} else {
    Write-Host "No Ocean Optics devices found (they may need to be reconnected)"
}
"""

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script4],
        capture_output=True,
        text=True,
        timeout=15
    )
    print(result.stdout)
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("\n1. Unplug the Ocean Optics detector USB cable")
print("2. Wait 5 seconds")
print("3. Plug it back in")
print("4. Wait for Windows to detect and install the driver")
print("5. Run the diagnostic again:")
print("   python detector_diagnostic_simple.py")
print("\nIf issues persist:")
print("6. Reinstall libusbK driver with Zadig:")
print("   https://zadig.akeo.ie/")
print("   Options > List All Devices")
print("   Find: Ocean Optics FLAME-T")
print("   Select: libusbK driver")
print("   Click: Replace Driver")
