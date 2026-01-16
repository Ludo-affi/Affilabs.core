"""Diagnostic tool to check FTDI D2XX driver installation.

This script helps diagnose why PhasePhotonics detectors aren't being detected
by the ftd2xx library and provides step-by-step fix instructions.
"""

import sys
from pathlib import Path

print("=" * 80)
print("FTDI D2XX DRIVER DIAGNOSTIC TOOL")
print("=" * 80)

# Step 1: Check if ftd2xx library is installed
print("\n[1/5] Checking ftd2xx Python library...")
try:
    import ftd2xx
    print("✅ ftd2xx library is installed")
    version = getattr(ftd2xx, '__version__', 'unknown')
    print(f"    Version: {version}")
except ImportError as e:
    print(f"❌ ftd2xx library NOT installed: {e}")
    print("    Install with: pip install ftd2xx")
    sys.exit(1)

# Step 2: Check if D2XX drivers can enumerate devices
print("\n[2/5] Checking D2XX driver functionality...")
try:
    devices = ftd2xx.listDevices()
    if devices is None:
        print("❌ D2XX drivers NOT working (listDevices returned None)")
        print("    This means D2XX drivers are not installed or not functioning")
    elif len(devices) == 0:
        print("⚠️  D2XX drivers working, but NO devices found")
        print("    Check USB connections")
    else:
        print(f"✅ D2XX drivers working! Found {len(devices)} device(s):")
        for i, dev in enumerate(devices):
            serial = dev.decode() if isinstance(dev, bytes) else dev
            is_phase = serial.startswith("ST")
            marker = " 👉 PHASE PHOTONICS" if is_phase else ""
            print(f"    [{i}] {serial}{marker}")
except Exception as e:
    print(f"❌ Error checking D2XX drivers: {e}")
    devices = None

# Step 3: Check Windows Device Manager for FTDI devices
print("\n[3/5] Checking Windows Device Manager...")
try:
    import subprocess
    result = subprocess.run(
        [
            "powershell", "-Command",
            "Get-PnpDevice | Where-Object { $_.InstanceId -like '*FTDI*' -or $_.InstanceId -like '*0403*' -or $_.InstanceId -like '*ST0*' } | Select-Object FriendlyName, Status, InstanceId | Format-Table -AutoSize"
        ],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0 and result.stdout.strip():
        print("✅ Found FTDI devices in Windows:")
        print(result.stdout)
        
        # Check if devices are using VCP drivers (COM ports)
        if "COM" in result.stdout or "Serial" in result.stdout:
            print("⚠️  WARNING: Devices appear to be using VCP (COM port) drivers!")
            print("    D2XX drivers and VCP drivers are mutually exclusive.")
            print("    You need to switch to D2XX drivers for ftd2xx to work.")
    else:
        print("❌ No FTDI devices found in Device Manager")
        print("    Check physical USB connections")
except Exception as e:
    print(f"⚠️  Could not query Device Manager: {e}")

# Step 4: Check if Sensor64bit.dll exists
print("\n[4/5] Checking for PhasePhotonics DLL...")
dll_locations = [
    Path(__file__).parent / "affilabs" / "utils" / "Sensor64bit.dll",
    Path(__file__).parent / "Sensor64bit.dll",
]

dll_found = False
for dll_path in dll_locations:
    if dll_path.exists():
        print(f"✅ Found DLL: {dll_path}")
        print(f"    Size: {dll_path.stat().st_size:,} bytes")
        dll_found = True
        break

if not dll_found:
    print("❌ Sensor64bit.dll NOT FOUND")
    print("    Expected locations:")
    for loc in dll_locations:
        print(f"    - {loc}")

# Step 5: Provide instructions
print("\n" + "=" * 80)
print("DIAGNOSIS SUMMARY")
print("=" * 80)

if devices is None:
    print("\n❌ PROBLEM: D2XX drivers are NOT installed or not working\n")
    print("SOLUTION - Install FTDI D2XX Drivers:")
    print("─" * 80)
    print("1. Download FTDI D2XX drivers:")
    print("   https://ftdichip.com/drivers/d2xx-drivers/")
    print("   → Click 'Windows' → Download the setup executable")
    print()
    print("2. IMPORTANT: Uninstall VCP drivers first (if installed):")
    print("   a. Open Device Manager (Win+X → Device Manager)")
    print("   b. Find your PhasePhotonics devices (look for ST00011, ST00012)")
    print("   c. Right-click → Uninstall device")
    print("   d. Check 'Delete the driver software' if available")
    print("   e. Unplug and replug the USB devices")
    print()
    print("3. Install D2XX drivers:")
    print("   a. Run the D2XX driver installer you downloaded")
    print("   b. Follow the installation wizard")
    print("   c. Restart your computer")
    print()
    print("4. Verify installation:")
    print("   a. Reconnect PhasePhotonics devices")
    print("   b. Run this script again: python check_d2xx_drivers.py")
    print()
    print("ALTERNATIVE METHOD - Use FTClean utility:")
    print("─" * 80)
    print("1. Download FTClean from: https://ftdichip.com/utilities/#ftclean")
    print("2. Run FTClean to remove all FTDI drivers")
    print("3. Restart computer")
    print("4. Install D2XX drivers")
    print("5. Test again")
    
elif len(devices) == 0:
    print("\n⚠️  D2XX drivers are working, but no devices detected\n")
    print("TROUBLESHOOTING:")
    print("─" * 80)
    print("1. Check USB cable connections")
    print("2. Try a different USB port")
    print("3. Check if devices are powered on")
    print("4. Try unplugging and replugging the devices")
    print("5. Check Device Manager for any error icons")
    
else:
    phase_devices = [d for d in devices if (d.decode() if isinstance(d, bytes) else d).startswith("ST")]
    if phase_devices:
        print("\n✅ SUCCESS! PhasePhotonics detector(s) detected and ready!\n")
        print(f"Found {len(phase_devices)} PhasePhotonics device(s)")
        if dll_found:
            print("\nYou can now run your PhasePhotonics application.")
        else:
            print("\n⚠️  But Sensor64bit.dll is missing - add it to run the application")
    else:
        print("\n⚠️  D2XX working, but no PhasePhotonics devices found")
        print("    (PhasePhotonics devices have serials starting with 'ST')")

print("\n" + "=" * 80)
print("\nFor more help, visit: https://ftdichip.com/document/installation-guides/")
print("=" * 80)
