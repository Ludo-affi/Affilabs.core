"""Find and test all connected Pico controllers"""
import serial.tools.list_ports

print("=" * 70)
print("SEARCHING FOR PICO CONTROLLERS")
print("=" * 70)

# Find all ports
ports = list(serial.tools.list_ports.comports())
print(f"\nFound {len(ports)} total serial ports:")

pico_ports = []
for port in ports:
    vid_str = f"0x{port.vid:04X}" if port.vid else "None"
    pid_str = f"0x{port.pid:04X}" if port.pid else "None"
    print(f"\n{port.device}:")
    print(f"  Description: {port.description}")
    print(f"  VID: {vid_str}")
    print(f"  PID: {pid_str}")
    print(f"  Serial#: {port.serial_number if port.serial_number else 'N/A'}")

    # Check if it's a Pico (VID=0x2E8A, PID=0x000A)
    if port.vid == 0x2E8A and port.pid == 0x000A:
        pico_ports.append(port.device)
        print("  ✅ THIS IS A PICO CONTROLLER!")

print("\n" + "=" * 70)
print(f"FOUND {len(pico_ports)} PICO CONTROLLER(S):")
for p in pico_ports:
    print(f"  - {p}")
print("=" * 70)

# Try to open each one
if pico_ports:
    print(f"\nTrying to connect to {pico_ports[0]}...")
    try:
        import serial
        ser = serial.Serial(pico_ports[0], 115200, timeout=1)
        print(f"✅ Successfully opened {pico_ports[0]}")

        # Try to send ID command
        ser.write(b"*IDN?\r\n")
        import time
        time.sleep(0.1)
        response = ser.read(100)
        print(f"ID Response: {response}")

        ser.close()
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("\n⚠️  No Pico controllers found with VID=0x2E8A, PID=0x000A")
