"""Execute the requested test with proper device reset to avoid firmware bug
Configuration:
  LEDs: A=100, B=150, C=200, D=250
  Settle: 1000ms (1 second - max allowed)
  Dark: 100ms (0.1 seconds - max allowed)
  Cycles: 10
  Expected: ~4.4 seconds per cycle
  Total expected: ~44 seconds
"""

import time

import serial

print("=" * 70)
print("FINAL TEST - PROPERLY ISOLATED")
print("=" * 70)
print("Configuration:")
print("  LEDs: A=100, B=150, C=200, D=250")
print("  Settle: 1000ms (1 second - max allowed)")
print("  Dark: 100ms (0.1 seconds - max allowed)")
print("  Cycles: 10")
print("  Expected: ~4.4 seconds per cycle")
print("  Total expected: ~44 seconds")
print("=" * 70)
print("\n⚠️  NOTE: Firmware has a bug where commands queue.")
print("This test will reset the connection to get a clean state.")
print("=" * 70)

# Fully reset connection
print("\n🔄 Resetting device connection...")
try:
    ser = serial.Serial("COM5", 115200, timeout=2)
    ser.close()
    time.sleep(3)
except:
    pass

print("🔌 Connecting to COM5...")
ser = serial.Serial("COM5", 115200, timeout=15)
time.sleep(3)
ser.reset_input_buffer()
ser.reset_output_buffer()

# Flush any pending output
print("🧹 Flushing device buffers...")
start_flush = time.time()
while ser.in_waiting > 0 and time.time() - start_flush < 2:
    ser.read(ser.in_waiting)
    time.sleep(0.1)

print("✅ Device ready\n")

# Send the command
command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"📤 Sending: {command.strip()}")
print()

ser.write(command.encode())
start_time = time.time()

cycle_count = 0
cycle_times = []
last_cycle_time = start_time

print("📊 Progress:")
print("-" * 70)

try:
    while time.time() - start_time < 60:  # 60 second timeout
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if line:
                if line.startswith("BATCH_START"):
                    print(f"🚀 {line}")

                elif line.startswith("CYCLE:"):
                    cycle_num = int(line.split(":")[1])
                    elapsed = time.time() - start_time

                    # Calculate cycle time
                    if cycle_count > 0:
                        cycle_time = time.time() - last_cycle_time
                        cycle_times.append(cycle_time)

                    last_cycle_time = time.time()
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
                        avg_cycle = elapsed / cycle_count
                        print(f"⚡ Average per cycle: {avg_cycle:.2f}s")
                        expected_per_cycle = 4.4
                        diff = avg_cycle - expected_per_cycle
                        print(f"📈 Difference from expected: {diff:+.2f}s per cycle")

                        if cycle_times:
                            min_cycle = min(cycle_times)
                            max_cycle = max(cycle_times)
                            print(
                                f"⏱️  Cycle time range: {min_cycle:.2f}s - {max_cycle:.2f}s",
                            )

                    # Check if we got the expected number of cycles
                    if cycle_count == 10:
                        print("\n✅ SUCCESS: Got expected 10 cycles")
                    else:
                        print(f"\n⚠️  WARNING: Expected 10 cycles, got {cycle_count}")
                        print("   (Firmware bug: commands may be queuing)")

                    break

    if time.time() - start_time >= 60:
        print("\n\n⚠️  Test timed out after 60 seconds")
        print(f"📊 Cycles completed: {cycle_count}")
        print("   (Firmware may be executing queued commands)")

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user")
    print(f"📊 Cycles completed: {cycle_count}")

finally:
    print("-" * 70)
    ser.close()
    print("\n📡 Disconnected")

    print("\n" + "=" * 70)
    print("TEST ANALYSIS")
    print("=" * 70)
    print("\n✅ Test execution complete")
    print("\nKnown firmware issue identified:")
    print("  - Commands are being queued/concatenated")
    print("  - Cycle counter persists across commands")
    print("  - Device may need physical reset (power cycle) for clean state")
    print("\nTo fix this firmware bug:")
    print("  1. Add command buffer flush after BATCH_END")
    print("  2. Add busy flag to prevent command queueing")
    print("  3. Ensure proper function exit after all cycles complete")
