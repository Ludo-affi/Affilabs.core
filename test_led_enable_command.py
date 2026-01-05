"""Test P4PRO LED enable command directly."""
import serial
import time

port = 'COM3'
baud = 115200

print(f"Connecting to {port}...")
ser = serial.Serial(port, baud, timeout=1)
time.sleep(0.5)

# Clear buffer
ser.read(1000)

print("\n1. Testing lm:1,1,1,1 command (enable all LEDs)...")
cmd = "lm:1,1,1,1\n"
print(f"   Sending: {cmd!r}")
ser.write(cmd.encode())
time.sleep(0.1)
resp = ser.read(100)
print(f"   Response: {resp!r}")

time.sleep(0.5)

print("\n2. Setting LED intensity to 20% (51/255)...")
for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:51\n"
    print(f"   Sending: {cmd!r}")
    ser.write(cmd.encode())
    time.sleep(0.05)
    resp = ser.read(10)
    print(f"   Response: {resp!r}")

print("\n3. LEDs should now be ON at 20%")
print("   Check detector counts...")

time.sleep(2)

print("\n4. Turning OFF all LEDs (lx command)...")
cmd = "lx\n"
print(f"   Sending: {cmd!r}")
ser.write(cmd.encode())
time.sleep(0.1)
resp = ser.read(100)
print(f"   Response: {resp!r}")

ser.close()
print("\nTest complete!")
