"""Test if debug mode is actually working"""

import time

import serial

ser = serial.Serial("COM5", 115200, timeout=5)
time.sleep(2)

print("Testing debug mode...")
print("\n1. Enable debug:")
ser.write(b"d\n")
time.sleep(0.3)
response = ser.read_all().decode("utf-8", errors="ignore")
print(f"Response: '{response}'")

print("\n2. Send 'b' (batch command):")
ser.write(b"b:100,150,200,250\n")
time.sleep(0.3)
response = ser.read_all().decode("utf-8", errors="ignore")
print(f"Response: '{response}'")

print("\n3. Send 'v' (version):")
ser.write(b"v\n")
time.sleep(0.3)
response = ser.read_all().decode("utf-8", errors="ignore")
print(f"Response: '{response}'")

ser.close()
