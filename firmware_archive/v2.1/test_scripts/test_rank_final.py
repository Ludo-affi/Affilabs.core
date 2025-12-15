#!/usr/bin/env python3
"""Test final rank command without debug output"""

import time

import serial

PORT = "COM5"
BAUD = 115200

print("Testing V2.0 rank command...")
ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)

# Clear buffer
ser.read(10000)

# Test rank command
print("Sending: rank:128,100,50")
ser.write(b"rank:128,100,50\n")
time.sleep(0.5)

response = ser.read(100)
print(f"Response: {response}")

if response == b"6":
    print("✅ SUCCESS - Rank command working!")
    print("LEDs should flash A→B→C→D in sequence")
else:
    print(f"❌ FAILED - Got {response} instead of ACK (6)")

ser.close()
