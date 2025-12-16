import serial.tools.list_ports

ports = list(serial.tools.list_ports.comports())
print(f"\nFound {len(ports)} COM ports:\n")
for p in ports:
    vid = f"0x{p.vid:04X}" if p.vid else "None"
    pid = f"0x{p.pid:04X}" if p.pid else "None"
    print(f"  {p.device}")
    print(f"    VID: {vid}")
    print(f"    PID: {pid}")
    print(f"    Description: {p.description}")
    print(f"    Serial: {p.serial_number if p.serial_number else 'N/A'}")
    print()
