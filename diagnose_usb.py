"""Diagnose USB/Serial port detection issues."""
import serial.tools.list_ports

print("=" * 70)
print("USB/SERIAL PORT DIAGNOSTIC")
print("=" * 70)

# List ALL serial ports
print("\n1. Enumerating ALL serial ports...")
ports = list(serial.tools.list_ports.comports())
print(f"   Found {len(ports)} port(s)")

if len(ports) == 0:
    print("\n❌ NO SERIAL PORTS DETECTED!")
    print("\nPossible causes:")
    print("1. Device not connected to USB")
    print("2. USB cable is charge-only (no data lines)")
    print("3. USB drivers not installed")
    print("4. Device not powered on")
    print("5. USB port failure")
    print("\nTroubleshooting steps:")
    print("- Check Device Manager (Win+X → Device Manager)")
    print("- Look under 'Ports (COM & LPT)' for any devices")
    print("- Check for yellow warning icons")
    print("- Try different USB port")
    print("- Try different USB cable")
    print("- Unplug and replug device")
else:
    print("\n✓ Serial ports detected!")
    print("\nDetailed port information:")
    print("-" * 70)
    
    for i, port in enumerate(ports, 1):
        print(f"\nPort {i}: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   Manufacturer: {port.manufacturer}")
        print(f"   VID: {hex(port.vid) if port.vid else 'None'}")
        print(f"   PID: {hex(port.pid) if port.pid else 'None'}")
        print(f"   Serial Number: {port.serial_number}")
        print(f"   Location: {port.location}")
        
        # Check if this matches Pico
        if port.vid == 0x2e8a and port.pid == 0xa:
            print("   ⭐ MATCHES RASPBERRY PI PICO (P4PRO/P4PROPLUS)")
        elif port.vid == 0x2e8a:
            print(f"   ℹ️  Raspberry Pi device (PID={hex(port.pid)})")

print("\n" + "=" * 70)
print("\nExpected for P4PRO/P4PROPLUS:")
print("   VID: 0x2e8a (11914)")
print("   PID: 0xa (10)")
print("=" * 70)
