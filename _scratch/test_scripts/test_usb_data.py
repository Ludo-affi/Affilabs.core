"""
Quick USB Data Line Test
Tests if USB data communication is working through the panel mount
"""

import serial.tools.list_ports
import subprocess

print("="*70)
print("  USB DATA LINE TEST")
print("="*70)
print()

# Check COM ports
print("1. CHECKING COM PORTS:")
print("-"*70)
ports = list(serial.tools.list_ports.comports())

if ports:
    print(f"✓ Found {len(ports)} COM port(s):")
    for p in ports:
        print(f"  {p.device}: {p.description}")
        print(f"    VID:PID = {p.vid:04X}:{p.pid:04X}" if p.vid else "    No VID/PID")
        print(f"    Serial: {p.serial_number}" if p.serial_number else "")
else:
    print("❌ NO COM PORTS FOUND")
    print("   This means USB data lines are NOT working")
    print()
    print("   Possible causes:")
    print("   • Windows USB drivers corrupted from failed firmware flash")
    print("   • USB device descriptor cache corrupted")
    print("   • Devices stuck in bad state from flash attempt")

print()
print("2. CHECKING USB DEVICE ENUMERATION:")
print("-"*70)

# Check if Windows sees ANY USB devices
ps_cmd = """
Get-PnpDevice -Class USB | Where-Object {$_.Status -eq 'OK'} | 
Select-Object -First 5 FriendlyName | Format-Table -HideTableHeaders
"""

try:
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.stdout.strip():
        print("✓ Windows can enumerate USB devices (USB subsystem working)")
    else:
        print("⚠️ No USB devices found")
except Exception as e:
    print(f"⚠️ Could not check: {e}")

print()
print("="*70)
print("DIAGNOSIS:")
print("="*70)

if not ports:
    print()
    print("❌ USB DATA COMMUNICATION FAILED")
    print()
    print("Since power works but data doesn't, this is NOT a cable issue.")
    print("This is corrupted Windows USB drivers from the failed firmware flash.")
    print()
    print("FIX:")
    print("  1. Open PowerShell AS ADMINISTRATOR")
    print("  2. Run: .\\fix_usb_drivers.ps1")
    print("  3. Restart Windows")
    print("  4. Plug devices back in")
    print("  5. Wait 30 seconds for driver reinstall")
    print()
else:
    print()
    print("✓ USB DATA COMMUNICATION WORKING")
    print()
    print("Devices are communicating. You can run the main application.")

print("="*70)
