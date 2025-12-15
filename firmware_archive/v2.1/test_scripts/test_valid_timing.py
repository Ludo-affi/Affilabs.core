"""Test with valid timing ranges (settle max 1000ms, dark max 100ms)"""

import time

import serial

print("=" * 60)
print("VALID TIMING TEST")
print("=" * 60)
print("Configuration:")
print("  LEDs: A=100, B=150, C=200, D=250")
print("  Settle: 1000ms (1 second - max allowed)")
print("  Dark: 100ms (0.1 seconds - max allowed)")
print("  Cycles: 10")
print("  Expected: ~4.4 seconds per cycle")
print("  Total expected: ~44 seconds")
print("=" * 60)
print()

ser = serial.Serial("COM5", 115200, timeout=10)
time.sleep(2)
ser.reset_input_buffer()

command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"📤 Sending: {command.strip()}")
print()

ser.write(command.encode())
start_time = time.time()

cycle_count = 0

print("📊 Progress:")
print("-" * 60)

while time.time() - start_time < 120:  # 2 minute timeout
    if ser.in_waiting > 0:
        line = ser.readline().decode("utf-8", errors="ignore").strip()

        if line:
            if line.startswith("BATCH_START"):
                print(f"🚀 {line}")

            elif line.startswith("CYCLE:"):
                cycle_num = int(line.split(":")[1])
                elapsed = time.time() - start_time
                cycle_count = cycle_num
                print(f"\n⏱️  CYCLE {cycle_num}/10 (elapsed: {elapsed:.1f}s)")
                print("   ", end="", flush=True)

            elif line.endswith("READY"):
                channel = line.split(":")[0].upper()
                print(f"{channel}:", end=" ", flush=True)

            elif line.endswith("READ"):
                ser.write(b"ack\n")
                print("📸", end=" ", flush=True)

            elif line.endswith("DONE"):
                print("✓", end=" ", flush=True)

            elif line.startswith("CYCLE_END"):
                print()

            elif line == "BATCH_END":
                elapsed = time.time() - start_time
                print("\n\n✅ BATCH_END")
                print(f"⏱️  Total time: {elapsed:.1f}s")
                print(f"📊 Cycles completed: {cycle_count}")
                if cycle_count > 0:
                    print(f"⚡ Average per cycle: {elapsed/cycle_count:.1f}s")
                break

print("-" * 60)
ser.close()
print("\n📡 Disconnected")
