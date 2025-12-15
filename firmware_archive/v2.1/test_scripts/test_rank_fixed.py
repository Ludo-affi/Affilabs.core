"""Test the fixed rank command with START/END protocol."""

import time

import serial

port = serial.Serial("COM5", 115200, timeout=2)
time.sleep(0.1)

print("Testing firmware version...")
port.write(b"fv\n")
time.sleep(0.2)
response = port.read_all().decode()
print(f"Firmware: {response}")

print("\nTesting rank command...")
port.write(b"rank:128,35,5\n")
time.sleep(0.05)

# Read START signal
line = port.readline().decode().strip()
print(f"Received: {line}")

if line == "START":
    print("✓ START signal received!")

    # Read until END
    while True:
        line = port.readline().decode().strip()
        print(f"Received: {line}")
        if line == "END":
            print("✓ END signal received!")
            break
        if not line:
            print("✗ Timeout waiting for END")
            break
else:
    print(f"✗ Expected START, got: {line}")

port.close()
print("\n✓ Test complete")
