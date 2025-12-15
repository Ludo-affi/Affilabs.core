"""Alternate between LED A and C - fun test!"""

import time

import serial

print("=" * 70)
print("ALTERNATING LED A ↔ C TEST")
print("=" * 70)

ser = serial.Serial("COM5", 115200, timeout=1)
time.sleep(0.5)

# Turn off all LEDs first
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(100)

print("\n>>> Watch LEDs A and C alternate 10 times...")
print("    A ON → A OFF → C ON → C OFF → repeat\n")
time.sleep(1)

for i in range(10):
    # Turn on LED A
    ser.write(b"ba128\n")  # Set brightness
    time.sleep(0.02)
    ser.read(100)
    ser.write(b"la\n")  # Turn on A
    time.sleep(0.02)
    ack = ser.read(100)
    print(f"Cycle {i+1:2d}: LED A ON ", end="", flush=True)
    time.sleep(0.3)

    # Turn off A
    ser.write(b"lx\n")
    time.sleep(0.02)
    ser.read(100)
    print("→ OFF | ", end="", flush=True)
    time.sleep(0.1)

    # Turn on LED C
    ser.write(b"bc128\n")  # Set brightness
    time.sleep(0.02)
    ser.read(100)
    ser.write(b"lc\n")  # Turn on C
    time.sleep(0.02)
    ser.read(100)
    print("LED C ON ", end="", flush=True)
    time.sleep(0.3)

    # Turn off C
    ser.write(b"lx\n")
    time.sleep(0.02)
    ser.read(100)
    print("→ OFF")
    time.sleep(0.1)

# Final turn off
ser.write(b"lx\n")
ser.close()

print("\n" + "=" * 70)
print("Did you see A and C alternating cleanly?")
print("=" * 70)
