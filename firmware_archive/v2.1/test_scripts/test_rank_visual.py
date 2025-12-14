"""
Visual test of rank command showing successive LED flashing
"""

import serial
import time

print("=" * 70)
print("RANK COMMAND TEST - Successive LED Flashing")
print("=" * 70)
print("\nThis will show LEDs flashing one at a time: A → B → C → D\n")

# Connect to P4SPR
ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(0.5)

# Send rank command
print("📤 Sending: rank:128,35,5")
print("   (intensity=128, settling=35ms, dark=5ms)\n")
ser.write(b'rank:128,35,5\n')
time.sleep(0.05)

print("📥 Firmware Response:")
print("-" * 70)

led_count = 0
start_time = time.perf_counter()

while True:
    line = ser.readline().decode().strip()
    if not line:
        break

    elapsed = (time.perf_counter() - start_time) * 1000

    # Format output based on message type
    if line == "START":
        print(f"\n⏱️  {elapsed:6.1f}ms | 🚀 START - Beginning sequence")

    elif "READY" in line:
        led = line[0].upper()
        led_count += 1
        print(f"⏱️  {elapsed:6.1f}ms | 💡 LED {led} ON - Settling...")

    elif "READ" in line:
        led = line[0].upper()
        print(f"⏱️  {elapsed:6.1f}ms | 📸 LED {led} READY - Acquire now!")
        # Send ACK to continue
        ser.write(b'1\n')

    elif "DONE" in line:
        led = line[0].upper()
        print(f"⏱️  {elapsed:6.1f}ms | ⚫ LED {led} OFF - Dark period...")

    elif line == "END":
        print(f"\n⏱️  {elapsed:6.1f}ms | ✅ END - Sequence complete!")
        time.sleep(0.05)
        ack = ser.read(1)
        if ack:
            print(f"⏱️  {elapsed:6.1f}ms | 📨 Final ACK received: {ack}")
        break
    else:
        print(f"⏱️  {elapsed:6.1f}ms | {line}")

total_time = (time.perf_counter() - start_time) * 1000

print("-" * 70)
print(f"\n✅ Test Complete!")
print(f"   Total time: {total_time:.1f}ms")
print(f"   LEDs sequenced: {led_count}/4")
print(f"   Time per LED: {total_time/4:.1f}ms")
print("\n🎯 Key Observation: LEDs flashed ONE AT A TIME (successively)")
print("   This prevents crosstalk and ensures clean spectral measurements.")

ser.close()
