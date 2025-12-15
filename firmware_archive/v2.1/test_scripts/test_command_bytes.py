"""Test what command the device actually receives"""

import time

import serial

ser = serial.Serial("COM5", 115200, timeout=2)
time.sleep(0.1)

# Clear buffer
ser.reset_input_buffer()

# Send the command byte by byte to see what's actually transmitted
command = b"rankbatch:100,150,200,250,1000,100,10\n"
print(f"Sending command ({len(command)} bytes):")
print(f"  Raw: {command}")
print(f"  Hex: {command.hex()}")
print(f"  ASCII: {command.decode()}")
print()

ser.write(command)
time.sleep(0.5)

response = ser.read_all().decode("utf-8", errors="ignore")
print("Response:")
print(response)

ser.close()
