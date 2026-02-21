#!/usr/bin/env python
"""Final phantom device removal - using registry directly."""

import subprocess
import sys
import os

print("=" * 80)
print("FINAL PHANTOM DEVICE CLEANUP")
print("=" * 80)

# Check admin
import ctypes
try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
except:
    is_admin = False

if not is_admin:
    print("\n[ERROR] Must run as Administrator!")
    print("\nRunning as admin...\n")

    # Re-run as admin
    script_path = os.path.abspath(__file__)
    os.system(f'powershell -Command "Start-Process python -ArgumentList \'{script_path}\' -Verb RunAs"')
    sys.exit(0)

print("\n[OK] Running as Administrator\n")

# The working device we want to keep
WORKING_DEVICE = "6&3B513BA8&5&4"

# List of phantom device identifiers to remove
PHANTOM_DEVICES = [
    "7&2980B0FF&0&2",
    "6&32429B9&1&1",
    "6&32429B9&1&2",
    "6&32429B9&1&3",
    "6&32429B9&1&4",
    "6&3B513BA8&5&1",
    "6&3B513BA8&5&2",
    "7&A26E785&0&2",
]

print("Devices to remove:")
for device in PHANTOM_DEVICES:
    print(f"  - USB\\VID_2457&PID_1022\\{device}")

print(f"\nDevice to KEEP:")
print(f"  + USB\\VID_2457&PID_1022\\{WORKING_DEVICE}")
print()

# Remove via PowerShell (works better with registry)
ps_cmd = """
$regBasePath = "HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_2457&PID_1022"

# List of phantom device IDs to remove
$phantomDevices = @(
    "7&2980B0FF&0&2",
    "6&32429B9&1&1",
    "6&32429B9&1&2",
    "6&32429B9&1&3",
    "6&32429B9&1&4",
    "6&3B513BA8&5&1",
    "6&3B513BA8&5&2",
    "7&A26E785&0&2"
)

$removed = 0
Write-Host "Removing phantom devices from registry...`n"

foreach ($device in $phantomDevices) {
    $regPath = "$regBasePath\\$device"

    if (Test-Path $regPath) {
        Write-Host "Removing: $device"
        try {
            Remove-Item -Path $regPath -Recurse -Force -ErrorAction Stop
            Write-Host "  [OK]`n"
            $removed++
        } catch {
            Write-Host "  [ERROR] $_`n"
        }
    } else {
        Write-Host "Removing: $device"
        Write-Host "  [SKIP - not found]`n"
    }
}

Write-Host "Removed $removed device(s)"
Write-Host ""
Write-Host "Verifying remaining devices...`n"

# Verify via PnP API
$devices = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Ocean*FLAME*'} |
    Select-Object InstanceId, Status

foreach ($device in $devices) {
    $icon = if ($device.Status -eq 'OK') { "[OK]" } else { "[!] " }
    Write-Host "$icon $($device.InstanceId)"
}

Write-Host ""
"""

try:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=30
    )

    print(result.stdout)

    if result.stderr:
        print("Messages:", result.stderr)

except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)

print("=" * 80)
print("FINAL STEPS")
print("=" * 80)
print("""
1. Unplug ALL USB cables from the detector (power + data)
2. Wait 10 seconds
3. Plug back in the USB data cable
4. Wait 10-15 seconds for Windows to detect
5. Open a new PowerShell and run:

   python detector_diagnostic_simple.py

You should see ALL tests PASS!
""")
