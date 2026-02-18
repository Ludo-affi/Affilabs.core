"""Test P4PRO LED enable command - different syntax variations."""
import serial
import time

port = 'COM3'
baud = 115200

print(f"Connecting to {port}...")
ser = serial.Serial(port, baud, timeout=1)
time.sleep(0.5)
ser.read(1000)

tests = [
    "lm:1,1,1,1",    # With commas
    "lm:1111",       # Without commas
    "lm1111",        # No colon, no commas
    "lm:ABCD",       # Letter format
    "lmABCD",        # No colon, letters
]

for cmd_base in tests:
    cmd = cmd_base + "\n"
    print(f"\nTesting: {cmd!r}")
    ser.write(cmd.encode())
    time.sleep(0.1)
    resp = ser.read(100)
    print(f"Response: {resp!r} {'✓ SUCCESS' if resp == b'1' else '✗ FAIL'}")
    time.sleep(0.2)

ser.close()
print("\nTest complete!")
