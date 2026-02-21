#!/usr/bin/env python
"""Reinstall libusb driver for Ocean Optics FLAME-T spectrometer."""

import subprocess
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s"
)
logger = logging.getLogger(__name__)

print("=" * 80)
print("USB DRIVER REINSTALLATION TOOL")
print("=" * 80)
print("\nThis tool will delete phantom device entries and reinstall the libusbK driver")
print("for your Ocean Optics FLAME-T spectrometer.")
print("\n⚠️  IMPORTANT: Unplug your detector from USB BEFORE PROCEEDING\n")

input("Press Enter once detector is unplugged... ")

logger.info("Removing all Ocean Optics device entries from Device Manager...")

ps_script = """
# Get all Ocean Optics device entries
$devices = @(Get-PnpDevice -FriendlyName '*FLAME-T*' -ErrorAction SilentlyContinue)

Write-Host "Found $($devices.Count) FLAME-T device entries"

# Remove each one
foreach ($device in $devices) {
    Write-Host "Removing: $($device.FriendlyName) [Status: $($device.Status)]"
    try {
        Remove-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -Force -ErrorAction Stop
        Write-Host "  [OK] Removed"
    } catch {
        Write-Host "  [INFO] Already removed or failed: $_"
    }
}

# Also clear any libusb-win32 entries
Write-Host ""
Write-Host "Checking for libusb-win32 entries..."
$libusb32 = @(Get-PnpDevice -FriendlyName '*FLAME*' -ErrorAction SilentlyContinue | Where-Object {$_.Class -eq 'libusb32'})
foreach ($device in $libusb32) {
    Write-Host "Removing (libusb32): $($device.FriendlyName)"
    try {
        Remove-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -Force
    } catch {
        Write-Host "  [INFO] $_"
    }
}

Write-Host ""
Write-Host "Device cleanup complete. Waiting 2 seconds..."
Start-Sleep -Seconds 2
"""

try:
    result = subprocess.run(
        [sys.executable, "-c", """
import subprocess
ps_code = r'''{}'''
subprocess.run(['powershell', '-NoProfile', '-Command', ps_code], timeout=15)
""".format(ps_script)],
        capture_output=False,
        timeout=20
    )
except Exception as e:
    logger.warning(f"Could not run cleanup: {e}")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("\n1. Download and run Zadig from: https://zadig.akeo.ie/")
print("\n2. In Zadig:")
print("   a) Options → List All Devices (checkbox)")
print("   b) PLUG IN your detector NOW")
print("   c) Look for: 'Ocean Optics FLAME-T' in the device list")
print("   d) Select from dropdown: libusb-win32 or libusbK (recommend libusbK)")
print("   e) Click 'Replace Driver'")
print("   f) Wait for completion (may take 30 seconds)")
print("   g) Close Zadig")
print("\n3. Run this command to verify:")
print("   python detector_diagnostic_simple.py")
print("\n" + "=" * 80)

input("\nPress Enter when driver installation is complete... ")

logger.info("Running detector diagnostic...")
result = subprocess.run(
    [sys.executable, "detector_diagnostic_simple.py"],
    timeout=20
)
sys.exit(result.returncode)
