"""Test COM ports and Pico connection."""
import serial.tools.list_ports
import serial
import time

# Pico identifiers
PICO_VID = 0x2E8A
PICO_PID = 0x000A

print("=" * 60)
print("COM PORT DIAGNOSTIC")
print("=" * 60)

# List all COM ports
ports = serial.tools.list_ports.comports()
print(f"\nFound {len(ports)} COM port(s):")
for p in ports:
    vid_str = hex(p.vid) if p.vid else "None"
    pid_str = hex(p.pid) if p.pid else "None"
    print(f"\n  Port: {p.device}")
    print(f"    VID: {vid_str}")
    print(f"    PID: {pid_str}")
    print(f"    Description: {p.description}")
    print(f"    Manufacturer: {p.manufacturer}")
    print(f"    Serial: {p.serial_number}")

# Find Pico
print("\n" + "=" * 60)
print(f"LOOKING FOR PICO (VID={hex(PICO_VID)}, PID={hex(PICO_PID)})")
print("=" * 60)

pico_ports = [p for p in ports if p.vid == PICO_VID and p.pid == PICO_PID]

if not pico_ports:
    print("\n❌ PICO NOT FOUND!")
    print("   Check:")
    print("   - Is Pico plugged in via USB?")
    print("   - Is it recognized in Device Manager?")
else:
    pico_port = pico_ports[0]
    print(f"\n✅ Found Pico on: {pico_port.device}")

    # Try to open and test connection
    print("\nTesting connection...")
    try:
        ser = serial.Serial(port=pico_port.device, baudrate=115200, timeout=1)
        print(f"✅ Successfully opened {pico_port.device}")

        # Test ID command
        print("\nSending 'id' command...")
        ser.write(b"id\n")
        time.sleep(0.1)
        reply = ser.readline()
        print(f"   Raw reply: {reply}")
        print(f"   Decoded: {reply.decode('utf-8', errors='ignore').strip()}")

        # Test servo read command
        print("\nSending 'sr' command (servo read)...")
        ser.write(b"sr\n")
        time.sleep(0.1)
        reply = ser.readline()
        print(f"   Raw reply: {reply}")
        print(f"   Decoded: {reply.decode('utf-8', errors='ignore').strip()}")

        if len(reply) >= 7:
            s_pos = reply[0:3]
            p_pos = reply[4:7]
            print(f"   S position: {s_pos}")
            print(f"   P position: {p_pos}")
        else:
            print(f"   ⚠️  Reply too short (expected >=7 bytes, got {len(reply)})")

        ser.close()
        print("\n✅ Connection test passed!")

    except serial.SerialException as e:
        print(f"\n❌ Failed to open port: {e}")
        print("   Possible causes:")
        print("   - Another program has the port open")
        print("   - Permission denied")
        print("   - Driver issue")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
