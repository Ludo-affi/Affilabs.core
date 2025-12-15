"""Check available COM ports and their VID/PID."""

import serial.tools.list_ports

print("=" * 80)
print("AVAILABLE COM PORTS")
print("=" * 80)

ports = serial.tools.list_ports.comports()

if not ports:
    print("\nNo COM ports found!")
else:
    print(f"\nFound {len(ports)} COM port(s):\n")

    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device}")
        print(f"   Description: {port.description}")
        print(f"   Manufacturer: {port.manufacturer}")
        print(
            f"   VID: 0x{port.vid:04X} (decimal: {port.vid})"
            if port.vid
            else "   VID: None",
        )
        print(
            f"   PID: 0x{port.pid:04X} (decimal: {port.pid})"
            if port.pid
            else "   PID: None",
        )
        print(f"   Serial: {port.serial_number}")
        print()

print("=" * 80)
print("Expected for PicoP4SPR:")
print("   VID: 0x2E8A (Raspberry Pi)")
print("   PID: 0x000A")
print("=" * 80)
