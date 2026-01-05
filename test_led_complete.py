"""Test complete LED enable + intensity sequence."""
import serial
import time

port = 'COM3'
baud = 115200

print(f"Connecting to {port}...")
ser = serial.Serial(port, baud, timeout=1)
time.sleep(0.5)
ser.read(1000)

print("\n1. Enable all LEDs with lm:ABCD command...")
cmd = "lm:ABCD\n"
print(f"   Sending: {cmd!r}")
ser.write(cmd.encode())
time.sleep(0.1)
resp = ser.read(100)
print(f"   Response: {resp!r} {'✓ SUCCESS' if resp == b'1' else '✗ FAIL'}")

if resp != b'1':
    print("\n   ERROR: lm command failed! LEDs will not turn on.")
    ser.close()
    exit(1)

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
print("   ** CHECK DETECTOR - should show ~4000-8000 counts **")
print("   (Currently showing ~3090 when OFF)")

input("\n   Press Enter when ready to continue...")

print("\n4. Increasing to 50% (127/255)...")
for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:127\n"
    ser.write(cmd.encode())
    time.sleep(0.05)
    resp = ser.read(10)

print("   ** CHECK DETECTOR - should be brighter now **")

input("\n   Press Enter when ready to turn OFF...")

print("\n5. Turning OFF all LEDs (lx command)...")
cmd = "lx\n"
print(f"   Sending: {cmd!r}")
ser.write(cmd.encode())
time.sleep(0.1)
resp = ser.read(100)
print(f"   Response: {resp!r}")

print("\n   ** CHECK DETECTOR - should return to ~3090 counts **")

ser.close()
print("\nTest complete!")
