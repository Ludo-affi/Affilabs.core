"""Test ALL possible P4PRO batch LED command variations."""
import serial
import time

port = 'COM3'
baud = 115200

print("="*70)
print("P4PRO BATCH LED COMMAND DISCOVERY")
print("="*70)

ser = serial.Serial(port, baud, timeout=1)
time.sleep(0.5)
ser.read(1000)

# First enable LEDs
print("\n1. Enable all LEDs with lm:ABCD")
ser.write(b"lm:ABCD\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"   Response: {resp!r}")

time.sleep(0.5)

# Test batch command variations
tests = [
    "batch:51,51,51,51",     # P4SPR style (we know this fails)
    "lb:51,51,51,51",        # Batch with lb prefix
    "li:51,51,51,51",        # Batch with li prefix  
    "lset:51,51,51,51",      # Set all
    "lall:51",               # Set all to same value
    "l:51,51,51,51",         # Just l: prefix
    "la:51\nlb:51\nlc:51\nld:51",  # All in one string (newlines)
]

print("\n2. Testing batch command variations (intensity=51 for all):")
print("-" * 70)

for i, cmd_base in enumerate(tests, 1):
    # Turn off first
    ser.write(b"lx\n")
    time.sleep(0.1)
    ser.read(10)
    time.sleep(0.2)
    
    # Enable again
    ser.write(b"lm:ABCD\n")
    time.sleep(0.1)
    ser.read(10)
    time.sleep(0.2)
    
    # Test command
    cmd = cmd_base + "\n"
    print(f"\n{i}. Testing: {cmd_base!r}")
    ser.write(cmd.encode())
    time.sleep(0.15)
    resp = ser.read(100)
    print(f"   Response: {resp!r} {'✓' if resp == b'1' else '✗'}")
    
    reading = input(f"   Detector reading (or Enter to skip): ")
    if reading.strip():
        print(f"   Counts: {reading}")
        if reading.isdigit() and int(reading) > 5000:
            print(f"   ✅ THIS WORKS! Command: {cmd_base!r}")

print("\n3. Current method (individual commands in sequence):")
print("-" * 70)
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(10)

ser.write(b"lm:ABCD\n")
time.sleep(0.1)
ser.read(10)
time.sleep(0.2)

for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:51\n"
    print(f"   Sending {cmd.strip()}")
    ser.write(cmd.encode())
    time.sleep(0.05)
    resp = ser.read(10)
    print(f"   Response: {resp!r}")

reading = input("\n   Final detector reading with sequential commands: ")
print(f"   Counts: {reading}")

# Cleanup
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(10)

ser.close()
print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
