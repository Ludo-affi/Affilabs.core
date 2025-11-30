import serial.tools.list_ports

print("\n" + "="*60)
print("COM PORT SCAN")
print("="*60)

ports = list(serial.tools.list_ports.comports())

if not ports:
    print("No COM ports detected")
else:
    print(f"Found {len(ports)} COM port(s):\n")
    for p in ports:
        print(f"  Port: {p.device}")
        print(f"  Description: {p.description}")
        if p.vid and p.pid:
            print(f"  VID:PID: {hex(p.vid)}:{hex(p.pid)}")
        print()
