#!/usr/bin/env python
"""Remove phantom Ocean Optics devices using Windows WMI."""

import subprocess
import sys

print("=" * 80)
print("REMOVING PHANTOM DEVICES VIA WMI")
print("=" * 80)

# Check admin
import ctypes
try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
except:
    is_admin = False

if not is_admin:
    print("\n[ERROR] Must run as Administrator!")
    print("\nTo run as admin, right-click PowerShell and select 'Run as Administrator'")
    print("Then run: powershell -Command \"python remove_phantom_wmi.py\"")
    sys.exit(1)

print("\n[OK] Running as Administrator\n")

# PowerShell script to remove phantom devices
ps_script = r"""
[System.Reflection.Assembly]::LoadWithPartialName('System.Management')

# Get all Ocean Optics devices
$wmiDevices = Get-WmiObject Win32_PnPEntity | Where-Object {
    $_.Name -match 'Ocean Optics' -or $_.PNPDeviceID -match '2457'
}

Write-Host "Found $($wmiDevices.Count) device entry/entries`n"

if ($wmiDevices.Count -eq 0) {
    Write-Host "No Ocean Optics devices found"
    exit 0
}

# Get more detailed info
Get-PnpDevice | Where-Object { $_.FriendlyName -like '*Ocean Optics*' } |
Select-Object FriendlyName, Status, InstanceId |
ForEach-Object {
    Write-Host "$($_.FriendlyName) - Status: $($_.Status) - ID: $($_.InstanceId)"
}

Write-Host "`n[Note] Only ONE device should be OK. The rest are duplicates.`n"

# Try to identify which is the real working device
$workingDevices = @()
$phantomDevices = @()

$allDevices = Get-PnpDevice | Where-Object { $_.FriendlyName -like '*Ocean Optics*' }

foreach ($device in $allDevices) {
    if ($device.Status -eq 'OK' -and $device.ConfigManagerErrorCode -eq 0) {
        $workingDevices += $device
        Write-Host "[WORKING] $($device.InstanceId)"
    } else {
        $phantomDevices += $device
        Write-Host "[PHANTOM] $($device.InstanceId) - Status: $($device.Status), Error: $($device.ConfigManagerErrorCode)"
    }
}

if ($phantomDevices.Count -eq 0) {
    Write-Host "`n[OK] No phantom devices found!"
    exit 0
}

Write-Host "`nWill remove $($phantomDevices.Count) phantom device(s)"
Write-Host "Keeping $($workingDevices.Count) working device(s)`n"

# Remove phantom devices using SetupAPI
Write-Host "Attempting removal via SetupAPI..."
Write-Host ""

$removed = 0

foreach ($phantom in $phantomDevices) {
    Write-Host "Removing: $($phantom.InstanceId)"

    # Try using Remove-Item on the device's registry entry
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$($phantom.InstanceId)"

    if (Test-Path $regPath) {
        try {
            Remove-Item -Path $regPath -Force -Recurse -ErrorAction Stop
            Write-Host "  [OK] Removed from registry"
            $removed++
        } catch {
            Write-Host "  [ERROR] Registry removal failed: $_"
        }
    } else {
        Write-Host "  [WARNING] Registry path not found"
    }
}

Write-Host "`nRemoved $removed device(s) from registry"
Write-Host ""
Write-Host "Rescanning devices..."

# Rescan USB
$shell = New-Object -ComObject Wscript.Shell
$shell.SendKeys("{F5}")  # Refresh in Device Manager if open

Start-Sleep -Seconds 2

# Show final status
Write-Host ""
Write-Host "=" * 80
Write-Host "FINAL STATUS"
Write-Host "=" * 80
Write-Host ""

$finalDevices = Get-PnpDevice | Where-Object { $_.FriendlyName -like '*Ocean Optics*' }
Write-Host "Final device count: $($finalDevices.Count)`n"

foreach ($device in $finalDevices) {
    $status = if ($device.Status -eq 'OK') { 'OK' } else { 'ISSUE' }
    Write-Host "[$status] $($device.InstanceId) - Status: $($device.Status)"
}

Write-Host ""
"""

print("Running device removal script...\n")

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=30
    )

    print(result.stdout)

    if result.stderr:
        print("STDERR:", result.stderr)

except subprocess.TimeoutExpired:
    print("[ERROR] Command timed out")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("""
1. Close this window and Device Manager (if open)
2. Unplug the Ocean Optics detector USB cable
3. Wait 5 seconds
4. Plug it back in
5. Windows will automatically detect and reinstall the driver
6. Wait 10 seconds for the driver to initialize
7. Open a new PowerShell and run:
   python detector_diagnostic_simple.py
""")
