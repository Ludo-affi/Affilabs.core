"""
Debug test with readback - verify level_ptr values are actually set
"""
import time
import serial

# Open P4PRO directly
ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(0.1)

# Clear any startup messages
ser.read(1000)

print("=" * 60)
print("BRIGHTNESS COMMAND DEBUG TEST")
print("=" * 60)
print()

# First, turn all LEDs off
print("Turning all LEDs off...")
ser.write(b"lx\n")
time.sleep(0.02)
resp = ser.read(10)
print(f"Response: {resp!r}\n")

# Test: Set ONE LED at a time and check
test_brightnesses = [
    ('a', 200),
    ('b', 150),
    ('c', 100),
    ('d', 50),
]

print("Setting brightness for each LED (ONE AT A TIME)")
print("-" * 60)
for ch, val in test_brightnesses:
    cmd = f"b{ch}{val:03d}"
    print(f"\nSending: {cmd}")
    ser.write((cmd + "\n").encode())
    time.sleep(0.02)
    resp = ser.read(10)
    print(f"  Response: {resp!r}")

    # Check if LED turned on (firmware sets PWM immediately)
    print(f"  LED {ch.upper()} should be ON at {val}/255 = {val/255*100:.0f}%")
    input("  Press Enter to continue...")

print("\n" + "=" * 60)
print("Now turning off all LEDs and re-enabling with lm:ABCD")
print("=" * 60)

# Turn off
print("\nTurning off all LEDs...")
ser.write(b"lx\n")
time.sleep(0.02)
resp = ser.read(10)
print(f"Response: {resp!r}")

# Re-enable all at once
print("\nSending lm:ABCD to re-enable all LEDs...")
ser.write(b"lm:ABCD\n")
time.sleep(0.05)
resp = ser.read(10)
print(f"Response: {resp!r}\n")

print("=" * 60)
print("CHECK NOW - Do LEDs have DIFFERENT brightnesses?")
print("  - LED A should be brightest (200/255 = 78%)")
print("  - LED B should be medium-bright (150/255 = 59%)")
print("  - LED C should be medium-dim (100/255 = 39%)")
print("  - LED D should be dimmest (50/255 = 20%)")
print("=" * 60)
input("\nPress Enter to finish...")

# Turn off
ser.write(b"lx\n")
time.sleep(0.02)
ser.read(10)

ser.close()
print("\nDone!")
