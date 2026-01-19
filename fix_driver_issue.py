"""
Windows Driver Repair Tool for Pico P4PRO/EZSPR

This script helps fix driver issues that can occur after:
- Failed firmware flash attempts
- Improper bootloader entry
- Windows driver corruption
"""

print("="*70)
print("  WINDOWS DRIVER REPAIR TOOL")
print("="*70)

print("\nDIAGNOSING DRIVER ISSUE FROM FAILED FIRMWARE FLASH...\n")

# Check if Pico is stuck in bootloader mode
import subprocess
import os

print("1. CHECKING FOR PICO IN BOOTLOADER MODE:")
print("-"*70)
print("Looking for RP2 USB Boot device (stuck in bootloader)...")

try:
    # Check for RPI-RP2 drive (bootloader mode)
    drives = [d for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{d}:\\')]
    rp2_found = False
    
    for drive in drives:
        drive_path = f"{drive}:\\"
        # Check if this is the RPI-RP2 drive
        if os.path.exists(os.path.join(drive_path, "INFO_UF2.TXT")):
            print(f"\n  ✓ FOUND: Pico in bootloader mode on drive {drive}:")
            rp2_found = True
            print(f"    The Pico is stuck in bootloader mode!")
            print(f"    This happens when firmware flash was interrupted.")
            break
    
    if not rp2_found:
        print("  ℹ️  Pico not in bootloader mode")
except Exception as e:
    print(f"  ⚠️  Could not check drives: {e}")

print("\n\n2. CHECKING DEVICE MANAGER FOR PROBLEM DEVICES:")
print("-"*70)

# PowerShell command to check for problem devices
ps_cmd = """
Get-PnpDevice | Where-Object {$_.Status -ne 'OK' -or $_.Problem -ne 0} | 
Select-Object FriendlyName, Status, Problem, InstanceId | 
Format-List
"""

try:
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.stdout.strip():
        print("  ⚠️  PROBLEM DEVICES FOUND:")
        print(result.stdout)
    else:
        print("  ✓ No problem devices found in Device Manager")
        
except Exception as e:
    print(f"  ⚠️  Could not check Device Manager: {e}")

print("\n\n3. CHECKING FOR PICO USB SERIAL DEVICES:")
print("-"*70)

# Check for Pico-related devices
ps_pico_cmd = """
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Pico*' -or 
                              $_.FriendlyName -like '*2e8a*' -or
                              $_.FriendlyName -like '*RP2*' -or
                              $_.HardwareID -like '*VID_2E8A*'} | 
Select-Object FriendlyName, Status, InstanceId | Format-List
"""

try:
    result = subprocess.run(
        ["powershell", "-Command", ps_pico_cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.stdout.strip():
        print("  PICO DEVICES FOUND:")
        print(result.stdout)
    else:
        print("  ❌ NO PICO DEVICES FOUND")
        print("  The Pico is not being recognized by Windows at all")
        
except Exception as e:
    print(f"  ⚠️  Could not check for Pico devices: {e}")

print("\n\n" + "="*70)
print("REPAIR STEPS:")
print("="*70)

print("\n🔧 STEP 1: RESET THE PICO HARDWARE")
print("-"*70)
print("1. UNPLUG the Pico from USB")
print("2. HOLD the BOOTSEL button on the Pico")
print("3. While holding BOOTSEL, PLUG IN the USB cable")
print("4. Release BOOTSEL - you should see RPI-RP2 drive appear")
print("5. Drag & drop the correct .uf2 firmware file onto RPI-RP2 drive")
print("6. Wait for Pico to reboot (drive will disappear)")

print("\n\n🔧 STEP 2: REMOVE CORRUPTED DRIVERS")
print("-"*70)
print("Run this PowerShell command AS ADMINISTRATOR:")
print()
print("# Remove all Pico-related drivers")
print("pnputil /enum-devices /class USB | Select-String '2E8A' | ")
print("ForEach-Object { pnputil /remove-device $_.Line.Split()[1] /force }")
print()
print("OR manually in Device Manager:")
print("1. Open Device Manager (Win + X → Device Manager)")
print("2. View → Show Hidden Devices")
print("3. Find any Raspberry Pi Pico devices")
print("4. Right-click → Uninstall device")
print("5. Check 'Delete the driver software' if prompted")
print("6. Repeat for all Pico-related entries")

print("\n\n🔧 STEP 3: LET WINDOWS REINSTALL DRIVERS")
print("-"*70)
print("1. Unplug ALL USB devices from adapter")
print("2. Restart Windows (important!)")
print("3. Plug in USB-C adapter first")
print("4. Plug Pico into adapter")
print("5. Wait 30 seconds for Windows to install drivers")
print("6. Check Device Manager for 'USB Serial Device' or 'Pico'")

print("\n\n🔧 STEP 4: VERIFY COM PORT ASSIGNMENT")
print("-"*70)
print("After driver reinstall, run this to check COM ports:")
print()
print("python -c \"import serial.tools.list_ports; \"")
print("[print(f'{p.device}: {p.description}') for p in serial.tools.list_ports.comports()]\"")

print("\n\n🔧 ALTERNATIVE: BYPASS USB-C ADAPTER")
print("-"*70)
print("If drivers still don't work:")
print("1. Try plugging Pico directly into USB-A port (no adapter)")
print("2. Try different USB-C adapter")
print("3. Try different USB port on computer")

print("\n\n" + "="*70)
print("COMMON ISSUES AFTER FAILED FIRMWARE FLASH:")
print("="*70)
print("❌ Pico stuck in bootloader - needs firmware reflash")
print("❌ Windows cached bad driver - needs driver removal")
print("❌ USB descriptor corrupted - needs hardware reset")
print("❌ COM port not assigned - needs Windows restart")
print("\n" + "="*70)
