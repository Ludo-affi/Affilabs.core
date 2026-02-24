#!/usr/bin/env python
"""Use devcon.exe to remove phantom devices (requires admin)."""

import subprocess
import os
import shutil

print("=" * 80)
print("PHANTOM DEVICE REMOVAL (using devcon.exe)")
print("=" * 80)

# Check if running as admin
import ctypes

try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
except:
    is_admin = False

if not is_admin:
    print("\n[ERROR] This script must be run as Administrator!")
    print("\nRunning with elevated privileges...")
    print("You may see a UAC prompt. Click 'Yes' to continue.")

    # Try to re-run as admin using powershell
    ps_cmd = f"""
powershell -Command "Start-Process python -ArgumentList '{os.path.basename(__file__)}' -Verb RunAs"
"""
    os.system(ps_cmd)
    exit(1)

print("\n[OK] Running as Administrator")

# Check if devcon.exe is available
devcon_path = None

# Common locations
search_paths = [
    "C:\\Program Files (x86)\\Windows Kits\\10\\Tools\\x64\\devcon.exe",
    "C:\\Program Files (x86)\\Windows Kits\\8.1\\Tools\\x64\\devcon.exe",
    "C:\\Program Files\\Windows Kits\\10\\Tools\\x86\\devcon.exe",
]

print("\nSearching for devcon.exe...")
for path in search_paths:
    if os.path.exists(path):
        devcon_path = path
        print(f"[FOUND] {path}")
        break

if not devcon_path:
    print("[NOT FOUND] devcon.exe not in standard locations")
    print("\nTrying with 'where' command...")
    result = subprocess.run(
        ["where", "devcon.exe"],
        capture_output=True,
        text=True
    )
    if result.stdout.strip():
        devcon_path = result.stdout.strip().split('\n')[0]
        print(f"[FOUND] {devcon_path}")
    else:
        print("devcon.exe not found in PATH")
        devcon_path = None

if not devcon_path:
    print("\n" + "=" * 80)
    print("ALTERNATIVE: Using Registry to remove phantom devices")
    print("=" * 80)
    print("""
This requires more manual setup. Instead, please use Device Manager:

1. Open Device Manager (Win+R, type devmgmt.msc, press Enter)
2. View > Show hidden devices
3. Find "Ocean Optics FLAME-T" entries with warning icons
4. Right-click each one > Uninstall device
5. Check "Delete the driver software for this device"
6. Click Uninstall
7. Unplug USB cable, wait 5 seconds, replug
8. Windows will re-detect the device

Or download WinRAR and extract devcon.exe from Windows Kits:
https://docs.microsoft.com/en-us/windows-hardware/drivers/devtest/devcon
""")
    exit(1)

print("\n[READY] Using devcon.exe to remove phantom devices")
print("\nFinding Ocean Optics device IDs...")

# List all devices with Ocean Optics
result = subprocess.run(
    [devcon_path, "find", "*2457*"],
    capture_output=True,
    text=True
)

device_ids = []
for line in result.stdout.split('\n'):
    if 'USB\\VID_2457' in line:
        parts = line.split()
        if parts:
            device_ids.append(parts[0])

print(f"\nFound {len(device_ids)} Ocean Optics device(s):")
for device_id in device_ids:
    print(f"  {device_id}")

if not device_ids:
    print("\nNo Ocean Optics devices found!")
    exit(1)

print("\n" + "=" * 80)
print("Removing phantom device entries")
print("=" * 80 + "\n")

removed_count = 0
for device_id in device_ids:
    print(f"Removing {device_id}...")

    # Remove the device
    result = subprocess.run(
        [devcon_path, "remove", device_id],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"  [OK] Removed")
        removed_count += 1
    else:
        print(f"  [FAILED] {result.stderr}")

print(f"\nRemoved {removed_count} device(s)")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("""
1. Close this window
2. Unplug the Ocean Optics detector USB cable
3. Wait 5 seconds
4. Plug it back in
5. Wait for Windows to detect and install the driver
6. Run the diagnostic:
   python detector_diagnostic_simple.py
""")
