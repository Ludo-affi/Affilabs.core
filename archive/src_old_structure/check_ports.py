"""Quick script to check what serial ports are visible."""

import serial.tools.list_ports

ports = list(serial.tools.list_ports.comports())
print(f"Found {len(ports)} port(s):")
for p in ports:
    vid = f"0x{p.vid:04X}" if p.vid else "None"
    pid = f"0x{p.pid:04X}" if p.pid else "None"
    print(f"  {p.device}: VID={vid} PID={pid} - {p.description}")
