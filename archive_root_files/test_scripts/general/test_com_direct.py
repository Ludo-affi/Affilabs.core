"""Quick COM port test - check if we can open and communicate with serial devices."""

import time

import serial
import serial.tools.list_ports

print("=" * 60)
print("COM PORT DIAGNOSTIC TEST")
print("=" * 60)

# List all ports
print("\n1. Available COM ports:")
ports = list(serial.tools.list_ports.comports())
for p in ports:
    vid = f"0x{p.vid:04X}" if p.vid else "None"
    pid = f"0x{p.pid:04X}" if p.pid else "None"
    print(f"  {p.device}: {p.description}")
    print(f"    VID:PID = {vid}:{pid}")
    print(f"    Manufacturer: {p.manufacturer}")

# Try to open each Pico device (VID=0x2E8A)
print("\n2. Testing Pico devices (VID=0x2E8A):")
pico_ports = [p for p in ports if p.vid == 0x2E8A and p.pid == 0x000A]

if not pico_ports:
    print("  ❌ No Pico devices found!")
    print("  Expected: VID=0x2E8A, PID=0x000A")
else:
    for p in pico_ports:
        print(f"\n  Testing {p.device}...")
        try:
            # Try to open with standard settings
            ser = serial.Serial(
                port=p.device,
                baudrate=115200,
                timeout=2,
                write_timeout=2,
            )
            print("    ✅ Port opened successfully")
            print(f"    Baudrate: {ser.baudrate}")
            print(f"    Timeout: {ser.timeout}s")

            # Try to send a test command
            ser.write(b"?\n")  # Query command
            time.sleep(0.1)

            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"    ✅ Device responded: {response[:50]}")
            else:
                print("    ⚠️  No response (device may need initialization)")

            ser.close()
            print("    ✅ Port closed")

        except serial.SerialException as e:
            print(f"    ❌ Serial error: {e}")
        except Exception as e:
            print(f"    ❌ Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
