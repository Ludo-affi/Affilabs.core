"""Test controller connection directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("CONTROLLER CONNECTION TEST")
print("=" * 70)

# Test direct controller connection
from settings.settings import PICO_PID, PICO_VID
from utils.controller import PicoP4SPR

print(f"\n[1] Looking for PicoP4SPR (VID:PID = {hex(PICO_VID)}:{hex(PICO_PID)})...")
pico_p4spr = PicoP4SPR()
if pico_p4spr.open():
    print("✅ PicoP4SPR connected!")
    print(f"   Device: {pico_p4spr.port}")

    # Test basic command
    print("\n[2] Testing LED control...")
    result = pico_p4spr.set_intensity(ch="a", raw_val=200)
    print(f"   set_intensity('a', 200): {result}")

    pico_p4spr.close()
    print("\n✅ TEST PASSED")
else:
    print("❌ PicoP4SPR NOT found")

    # List available serial ports
    import serial.tools.list_ports

    ports = list(serial.tools.list_ports.comports())
    print(f"\nAvailable COM ports ({len(ports)}):")
    for port in ports:
        vid_str = f"0x{port.vid:04X}" if port.vid else "None"
        pid_str = f"0x{port.pid:04X}" if port.pid else "None"
        print(f"  • {port.device}: VID={vid_str} PID={pid_str}")
        print(f"    {port.description}")
