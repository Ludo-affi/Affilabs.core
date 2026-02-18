"""Quick valve test with debug logging."""

import logging
logging.basicConfig(level=logging.DEBUG)

import serial
import serial.tools.list_ports

ser = None
for port in serial.tools.list_ports.comports():
    if port.vid == 0x2E8A and port.pid == 0x000A:
        try:
            ser = serial.Serial(port.device, 115200, timeout=1)
            ser.write(b"id\n")
            if b"P4PRO" in ser.readline():
                print(f"Found P4PRO on {port.device}")
                break
            ser.close()
            ser = None
        except:
            pass

if not ser:
    print("P4PRO not found")
    exit(1)

print("\nSending v6B1 command...")
ser.reset_input_buffer()
ser.write(b"v6B1\n")
print("Command sent")

import time
time.sleep(0.05)

response = ser.read(1)
print(f"Response: {response!r}")
print(f"Success: {response == b'1'}")
print("\nDid you hear a click? (y/n)")

ser.close()
