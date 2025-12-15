"""Test with valid timing ranges - Robust version with port handling"""

import sys
import time

import serial
import serial.tools.list_ports

print("=" * 60)
print("VALID TIMING TEST - ROBUST")
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

# Find available COM ports
ports = list(serial.tools.list_ports.comports())
print("Available COM ports:")
for port in ports:
    print(f"  {port.device}: {port.description}")
print()

if not ports:
    print("❌ No COM ports found!")
    sys.exit(1)

# Try to connect to the first available port
target_port = "COM5"
print(f"🔌 Attempting to connect to {target_port}...")

# Try to open the port with retry
max_retries = 3
for attempt in range(max_retries):
    try:
        ser = serial.Serial(target_port, 115200, timeout=10)
        print(f"✅ Connected to {target_port}")
        break
    except serial.SerialException as e:
        print(f"⚠️  Attempt {attempt + 1}/{max_retries} failed: {e}")
        if attempt < max_retries - 1:
            print("   Waiting 2 seconds before retry...")
            time.sleep(2)
        else:
            print(f"❌ Could not open {target_port} after {max_retries} attempts")
            print("\nTroubleshooting:")
            print("  1. Check if another program is using the port")
            print("  2. Try unplugging and replugging the USB cable")
            print("  3. Close any other serial monitors or applications")
            sys.exit(1)

time.sleep(2)
ser.reset_input_buffer()

command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"\n📤 Sending: {command.strip()}")
print()

ser.write(command.encode())
start_time = time.time()

cycle_count = 0

print("📊 Progress:")
print("-" * 60)

try:
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
                        expected_per_cycle = 4.4
                        diff = (elapsed / cycle_count) - expected_per_cycle
                        print(f"📈 Difference from expected: {diff:+.1f}s per cycle")
                    break

    if time.time() - start_time >= 120:
        print("\n\n⚠️  Test timed out after 2 minutes")
        print(f"📊 Cycles completed: {cycle_count}")

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user")
    print(f"📊 Cycles completed: {cycle_count}")

finally:
    print("-" * 60)
    ser.close()
    print("\n📡 Disconnected")
