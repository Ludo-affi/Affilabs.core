"""
Query syringe volume and calculate step-to-µL conversion
"""
import serial
import time

ser = serial.Serial(port='COM8', baudrate=38400, timeout=2)
time.sleep(0.3)

def query(cmd):
    ser.write((cmd + '\r').encode())
    time.sleep(0.3)
    resp = ser.read(200)
    print(f"{cmd:15s} -> {resp}")
    return resp

print("Querying pump configuration...")
print("="*60)

# Query syringe volume
query("/1?21000")  # Syringe volume query

# Query current position in steps
query("/1?4")

# Try to get valve position with different command
query("/1?")  # General status

# Try explicit position command
query("/1?1")  # Start velocity
query("/1?2")  # Top velocity
query("/1?3")  # Cutoff velocity

ser.close()
