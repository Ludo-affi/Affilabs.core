"""Deep dive test of P4PRO LED batch command sequence."""
import serial
import time

port = 'COM3'
baud = 115200

print("="*70)
print("P4PRO LED BATCH COMMAND DEEP DIVE TEST")
print("="*70)

ser = serial.Serial(port, baud, timeout=1)
time.sleep(0.5)
ser.read(1000)

print("\nTEST 1: Turn OFF all LEDs first (baseline)")
print("-" * 70)
ser.write(b"lx\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"lx response: {resp!r}")
time.sleep(0.5)

print("\nTEST 2: Enable LEDs with lm:ABCD")
print("-" * 70)
ser.write(b"lm:ABCD\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"lm:ABCD response: {resp!r} {'✓' if resp == b'1' else '✗ FAIL'}")
time.sleep(0.2)

print("\nTEST 3: Set batch intensities (20% = 51/255)")
print("-" * 70)
print("Setting individual la:51, lb:51, lc:51, ld:51 commands...")

for i, ch in enumerate(['a', 'b', 'c', 'd'], 1):
    cmd = f"l{ch}:51\n"
    print(f"  {i}. Sending {cmd.strip()!r}...", end=" ")
    ser.write(cmd.encode())
    time.sleep(0.01)
    resp = ser.read(10)
    print(f"response: {resp!r} {'✓' if resp == b'1' else '✗'}")

print("\n** CHECK DETECTOR NOW - Should show signal (not ~3090) **")
input("Press Enter to continue...")

print("\nTEST 4: Increase intensity to 50% (127/255)")
print("-" * 70)
for i, ch in enumerate(['a', 'b', 'c', 'd'], 1):
    cmd = f"l{ch}:127\n"
    print(f"  {i}. Sending {cmd.strip()!r}...", end=" ")
    ser.write(cmd.encode())
    time.sleep(0.01)
    resp = ser.read(10)
    print(f"response: {resp!r}")

print("\n** CHECK DETECTOR - Should be BRIGHTER **")
input("Press Enter to continue...")

print("\nTEST 5: Try DIFFERENT sequence - intensity BEFORE enable")
print("-" * 70)
print("Turn off first...")
ser.write(b"lx\n")
time.sleep(0.1)
ser.read(10)

print("Set intensities FIRST (before enable)...")
for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:51\n"
    ser.write(cmd.encode())
    time.sleep(0.01)
    ser.read(10)

print("Now enable with lm:ABCD...")
ser.write(b"lm:ABCD\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"lm:ABCD response: {resp!r}")

print("\n** CHECK DETECTOR - Does this sequence work better? **")
input("Press Enter to continue...")

print("\nTEST 6: Try setting intensities to 100% (255)")
print("-" * 70)
for ch in ['a', 'b', 'c', 'd']:
    cmd = f"l{ch}:255\n"
    ser.write(cmd.encode())
    time.sleep(0.01)
    resp = ser.read(10)

print("\n** CHECK DETECTOR - Should be MAXIMUM brightness **")
input("Press Enter to finish...")

print("\nTEST 7: Turn off")
print("-" * 70)
ser.write(b"lx\n")
time.sleep(0.1)
resp = ser.read(10)
print(f"lx response: {resp!r}")

ser.close()
print("\n" + "="*70)
print("DEEP DIVE COMPLETE")
print("="*70)
