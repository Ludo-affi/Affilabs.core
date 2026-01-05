"""
Manual test - send commands directly and check responses
"""
import time
import serial

# Open P4PRO directly
ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(0.1)

# Clear any startup messages
ser.read(1000)

print("=" * 60)
print("MANUAL BATCH COMMAND TEST")
print("=" * 60)
print()

# Test: Set different brightnesses then enable all
print("Step 1: Setting brightness levels (doesn't turn on)")
print("-" * 60)

commands = [
    "ba200",
    "bb150", 
    "bc100",
    "bd050"
]

for cmd in commands:
    full_cmd = cmd + "\n"
    print(f"Sending: {cmd}")
    ser.write(full_cmd.encode())
    time.sleep(0.02)
    resp = ser.read(10)
    print(f"  Response: {resp!r}")

print()
print("Step 2: Enable all 4 LEDs simultaneously")
print("-" * 60)
cmd = "lm:ABCD"
print(f"Sending: {cmd}")
ser.write((cmd + "\n").encode())
time.sleep(0.05)
resp = ser.read(10)
print(f"  Response: {resp!r}")
print()

print("=" * 60)
print("CHECK DETECTOR NOW")
print("=" * 60)
print("Are all 4 LEDs on?")
print("Do they have DIFFERENT brightnesses?")
print("  - LED A should be brightest (200/255 = 78%)")
print("  - LED B should be medium-bright (150/255 = 59%)")
print("  - LED C should be medium-dim (100/255 = 39%)")
print("  - LED D should be dimmest (50/255 = 20%)")
input("\nPress Enter to turn LEDs off...")

# Turn off
print("\nTurning off LEDs...")
ser.write(b"lx\n")
time.sleep(0.02)
resp = ser.read(10)
print(f"lx response: {resp!r}")

ser.close()
print("\nDone!")
