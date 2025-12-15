"""Check for FTDI devices connected to the system."""

import serial.tools.list_ports

print("=" * 70)
print("FTDI DEVICE DETECTION")
print("=" * 70)

ports = list(serial.tools.list_ports.comports())

if not ports:
    print("\n❌ No COM ports found!")
else:
    print(f"\n✓ Found {len(ports)} COM port(s):\n")

    ftdi_found = False

    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device}")
        print(f"   Description:  {port.description}")
        print(f"   Manufacturer: {port.manufacturer}")

        if port.vid and port.pid:
            vid_hex = f"0x{port.vid:04X}"
            pid_hex = f"0x{port.pid:04X}"
            print(
                f"   VID:PID:      {vid_hex}:{pid_hex} (decimal: {port.vid}:{port.pid})",
            )
        else:
            print("   VID:PID:      None")

        print(f"   Serial:       {port.serial_number}")
        print(f"   HWID:         {port.hwid}")

        # Check if FTDI
        if port.vid == 0x0403:  # FTDI Vendor ID
            print("   ✓✓✓ THIS IS AN FTDI DEVICE! ✓✓✓")
            ftdi_found = True

        print()

    print("=" * 70)
    if ftdi_found:
        print("✓ FTDI device(s) detected and accessible!")
    else:
        print("❌ No FTDI devices found in COM port list")
        print("\nPossible issues:")
        print("  1. FTDI driver not installed (need VCP driver)")
        print("  2. Device in Device Manager but COM port not assigned")
        print("  3. Driver conflict or device disabled")

print("=" * 70)
