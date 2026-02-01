"""
Fix USB-A to USB-C connection issues for Pico and FTDI devices.

This script diagnoses and fixes common issues with USB-A to USB-C adapters/cables
that prevent proper enumeration of Raspberry Pi Pico and FTDI devices.
"""

import subprocess

print("=" * 80)
print("USB-A TO USB-C CONNECTION DIAGNOSTIC & FIX")
print("=" * 80)

# Step 1: Check what's currently in Device Manager
print("\n[1/6] Scanning Device Manager for problematic devices...")
try:
    result = subprocess.run([
        "powershell", "-Command",
        """
        Get-PnpDevice | Where-Object { 
            $_.Status -eq 'Unknown' -or $_.Status -eq 'Error' 
        } | Select-Object Status, Class, FriendlyName, InstanceId | Format-List
        """
    ], capture_output=True, text=True, timeout=15)

    if result.stdout.strip():
        print("\n⚠️  Found devices with problems:")
        print(result.stdout)
    else:
        print("✅ No devices showing Unknown/Error status")

except Exception as e:
    print(f"⚠️  Could not query Device Manager: {e}")

# Step 2: Look for FTDI devices specifically
print("\n[2/6] Checking FTDI devices (PhasePhotonics detectors)...")
try:
    result = subprocess.run([
        "powershell", "-Command",
        """
        Get-PnpDevice | Where-Object { 
            $_.InstanceId -like '*VID_0403*' 
        } | Select-Object Status, FriendlyName, InstanceId | Format-List
        """
    ], capture_output=True, text=True, timeout=15)

    if result.stdout.strip():
        print(result.stdout)
        if "Unknown" in result.stdout:
            print("⚠️  FTDI devices found but in Unknown state - driver issue!")
    else:
        print("❌ No FTDI devices found")

except Exception as e:
    print(f"⚠️  Could not query FTDI devices: {e}")

# Step 3: Look for Raspberry Pi Pico
print("\n[3/6] Checking Raspberry Pi Pico (VID 0x2e8a)...")
try:
    result = subprocess.run([
        "powershell", "-Command",
        """
        Get-PnpDevice | Where-Object { 
            $_.InstanceId -like '*VID_2E8A*' 
        } | Select-Object Status, FriendlyName, InstanceId | Format-List
        """
    ], capture_output=True, text=True, timeout=15)

    if result.stdout.strip():
        print("✅ Found Raspberry Pi Pico:")
        print(result.stdout)
    else:
        print("❌ Raspberry Pi Pico NOT found")
        print("   This is the main issue - Pico should enumerate with VID 0x2e8a")

except Exception as e:
    print(f"⚠️  Could not query for Pico: {e}")

# Step 4: Check for Unknown USB devices
print("\n[4/6] Checking for unknown USB devices...")
try:
    result = subprocess.run([
        "powershell", "-Command",
        """
        Get-PnpDevice | Where-Object { 
            $_.FriendlyName -like '*Unknown USB*' -or 
            ($_.Class -eq 'USB' -and $_.Status -eq 'Unknown')
        } | Select-Object Status, FriendlyName, InstanceId | Format-List
        """
    ], capture_output=True, text=True, timeout=15)

    if result.stdout.strip():
        print("⚠️  Found unknown USB devices:")
        print(result.stdout)
    else:
        print("✅ No completely unknown USB devices")

except Exception as e:
    print(f"⚠️  Could not query: {e}")

# Step 5: Provide manual fix instructions
print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE - ACTION REQUIRED")
print("=" * 80)

print("""
The USB-A to USB-C connection has issues. Here's what to do:

╔════════════════════════════════════════════════════════════════════════════╗
║  IMMEDIATE FIXES TO TRY (in order):                                       ║
╚════════════════════════════════════════════════════════════════════════════╝

1. CHECK YOUR CABLE:
   ─────────────────
   • USB-A to USB-C cables vary in quality
   • Some are "charge-only" (no data lines)
   • Try a DIFFERENT USB-A to USB-C cable first
   • Use a cable that came with a phone/tablet (these support data)

2. TRY DIRECT USB-C CONNECTION:
   ────────────────────────────
   • If your computer has USB-C ports, use those directly
   • This eliminates adapter/cable issues
   • Much more reliable for data transfer

3. RESET USB STACK:
   ────────────────
   a) Unplug ALL USB devices (Pico, PhasePhotonics detectors)
   b) Wait 10 seconds
   c) Plug in ONE device at a time
   d) Wait for Windows to enumerate each device before plugging next
   e) Listen for the "device connected" sound

4. FIX FTDI DRIVERS (for PhasePhotonics detectors):
   ─────────────────────────────────────────────────
   The FTDI devices are showing as "Unknown" - this is a driver conflict.
   
   Run this PowerShell command as Administrator:
   
""")

print('   Run-PowerShell-Script: .\\fix_usb_drivers_clean.ps1')

print("""

5. MANUAL DRIVER FIX (if script doesn't work):
   ───────────────────────────────────────────
   a) Open Device Manager (Win+X → Device Manager)
   b) Look under "Universal Serial Bus devices" for devices with "Unknown"
   c) Right-click each → "Update driver"
   d) Choose "Browse my computer for drivers"
   e) Choose "Let me pick from available drivers"
   f) Select the appropriate driver:
      - For Pico: "USB Serial Device" or "USB CDC"
      - For FTDI: "USB Serial Converter" from FTDI list

6. CHECK USB POWER:
   ────────────────
   • USB-A to USB-C adapters may not provide enough power
   • Try a powered USB hub if available
   • Check if devices have external power options

7. DISABLE USB SELECTIVE SUSPEND:
   ──────────────────────────────
   a) Control Panel → Power Options
   b) Change plan settings → Advanced power settings
   c) USB Settings → USB selective suspend → Disabled
   d) Apply and restart

8. WINDOWS USB TROUBLESHOOTER:
   ───────────────────────────
   • Settings → System → Troubleshoot → Other troubleshooters
   • Run "Hardware and Devices" troubleshooter

""")

print("=" * 80)
print("\nAfter trying fixes, run these to verify:")
print("  python diagnose_usb.py       # Check for Pico")
print("  python diagnose_detector.py  # Check for Ocean Optics detector")
print("  python check_d2xx_drivers.py # Check for PhasePhotonics detectors")
print("=" * 80)
