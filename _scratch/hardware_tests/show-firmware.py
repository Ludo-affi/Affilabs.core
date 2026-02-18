"""Show P4PRO firmware version and capabilities."""

import serial
import serial.tools.list_ports

def find_p4pro():
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x2E8A and port.pid == 0x000A:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                ser.write(b"id\n")
                response = ser.readline().decode().strip()
                if "P4PRO" in response:
                    return ser, port.device
                ser.close()
            except:
                pass
    return None, None

ser, port = find_p4pro()
if not ser:
    print("P4PRO not found")
    exit(1)

print(f"P4PRO on {port}")

# Get firmware ID
ser.write(b"id\n")
fw_id = ser.readline().decode().strip()
print(f"Firmware ID: {fw_id}")

# Get firmware version
ser.write(b"iv\n")
fw_ver = ser.readline().decode().strip()
print(f"Firmware Version: {fw_ver}")

# Test valve command
print("\nTesting valve command v6B1...")
ser.reset_input_buffer()
ser.write(b"v6B1\n")
import time
time.sleep(0.05)
response = ser.read(10)
print(f"Response: {response!r}")

ser.close()
