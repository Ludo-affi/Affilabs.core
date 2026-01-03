"""
Debug aspirate issue - test separate vs chained commands
"""
import serial
import time

ser = serial.Serial(port='COM8', baudrate=38400, timeout=2)
time.sleep(0.5)

def send_cmd(cmd):
    ser.write((cmd + '\r').encode())
    time.sleep(0.5)
    resp = ser.read(200)
    print(f"{cmd:30s} -> {resp}")
    return resp

print("="*60)
print("Testing Aspirate Commands")
print("="*60)

# Initialize
print("\n1. Initialize")
send_cmd("/1ZR")
time.sleep(3)

# Check position
print("\n2. Check initial position")
send_cmd("/1?")

# Method 1: Chained command (what we've been using)
print("\n3. Method 1: Chained command (valve + speed + position)")
send_cmd("/1IV200,1A500,1R")
time.sleep(3)
send_cmd("/1?")

# Method 2: Separate commands
print("\n4. Method 2: Separate commands")
print("  a. Set valve to INPUT")
send_cmd("/1IR")
time.sleep(0.5)

print("  b. Set speed to 200µL/s")
send_cmd("/1V200R")
time.sleep(0.5)

print("  c. Move to position 700µL")
send_cmd("/1A700R")
time.sleep(3)

print("  d. Check position")
send_cmd("/1?")

# Method 3: Try with ,1 suffix on speed only
print("\n5. Method 3: Speed with ,1 then position")
send_cmd("/1V150,1R")
time.sleep(0.5)
send_cmd("/1A900R")
time.sleep(2)
send_cmd("/1?")

# Method 4: All separate with R after each
print("\n6. Method 4: Individual commands with R")
send_cmd("/1IR")
send_cmd("/1V100,1R")
send_cmd("/1A1000R")
time.sleep(5)
send_cmd("/1?")

ser.close()
print("\n" + "="*60)
print("Check which method actually moved the pump!")
print("="*60)
