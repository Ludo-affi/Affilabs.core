"""
Test version command
"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(0.1)

# Clear buffer
ser.reset_input_buffer()

# Test version command
print("Testing version command:")
print("Sending: 'iv' (version)")
ser.write(b"iv\n")
time.sleep(0.2)
response = ser.read_all().decode('utf-8', errors='ignore')
print(f"Response: '{response}'")
print()

# Test device info command
print("Sending: 'id' (device info)")
ser.write(b"id\n")
time.sleep(0.2)
response = ser.read_all().decode('utf-8', errors='ignore')
print(f"Response: '{response}'")

ser.close()
