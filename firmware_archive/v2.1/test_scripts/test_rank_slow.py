"""
Test rank command with clear visual indication
"""

import serial
import time

print("=" * 70)
print("RANK COMMAND VISUAL TEST")
print("=" * 70)

ser = serial.Serial('COM5', 115200, timeout=1)
time.sleep(0.5)

print("\n>>> WATCH THE LEDs - Starting rank sequence in 2 seconds...")
print("    You should see: A flash → B flash → C flash → D flash")
time.sleep(2)

print("\n📤 Sending rank command: rank:128,100,10")
print("   (intensity=128, settling=100ms, dark=10ms)")
print()

ser.write(b'rank:128,100,10\n')
time.sleep(0.05)

# Read and display responses with timing
responses = []
start = time.perf_counter()

while True:
    line = ser.readline().decode().strip()
    if not line:
        break

    elapsed_ms = (time.perf_counter() - start) * 1000
    responses.append((elapsed_ms, line))

    if "START" in line:
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line} - Beginning sequence")
    elif "READY" in line:
        led = line[0].upper()
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line} - ✨ LED {led} ON (watch it!)")
    elif "READ" in line:
        led = line[0].upper()
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line} - 📸 Acquiring LED {led}")
        ser.write(b'1\n')  # Send ACK
    elif "DONE" in line:
        led = line[0].upper()
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line} - 💡 LED {led} OFF")
    elif "END" in line:
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line} - ✅ Sequence complete!")
        time.sleep(0.05)
        ack = ser.read(1)
        break
    else:
        print(f"⏱️  {elapsed_ms:6.1f}ms | {line}")

ser.close()

total = (time.perf_counter() - start) * 1000
print()
print("=" * 70)
print(f"Total time: {total:.1f}ms for 4 LEDs")
print()
print("Did you see each LED flash one at a time?")
print("  A (0-110ms) → B (110-220ms) → C (220-330ms) → D (330-440ms)")
print("=" * 70)
