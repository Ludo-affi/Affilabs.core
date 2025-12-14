"""Test with proper reset between commands"""
import serial
import time

print("="*70)
print("COMMAND ISOLATION TEST")
print("="*70)

def run_isolated_test(ser, cycles_requested):
    """Run a single test with proper isolation"""
    print(f"\n{'='*70}")
    print(f"Testing {cycles_requested} cycles (ISOLATED)")
    print(f"{'='*70}")

    # Close and reopen connection to fully reset
    ser.close()
    time.sleep(2)
    ser = serial.Serial('COM5', 115200, timeout=10)
    time.sleep(2)
    ser.reset_input_buffer()

    command = f"rankbatch:100,100,100,100,250,50,{cycles_requested}\n"
    print(f"Command: {command.strip()}")

    ser.write(command.encode())

    cycles_seen = 0
    start = time.time()
    timeout = cycles_requested * 2 + 10  # 2 seconds per cycle plus buffer

    while time.time() - start < timeout:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if line:
                if line.startswith("BATCH_START"):
                    print(f"  🚀 START")
                elif line.startswith("CYCLE:"):
                    cycle_num = int(line.split(":")[1])
                    cycles_seen = cycle_num
                    print(f"  Cycle {cycle_num}/{cycles_requested}", end="", flush=True)
                elif line.endswith("READ"):
                    ser.write(b"ack\n")
                    print(".", end="", flush=True)
                elif line.startswith("CYCLE_END"):
                    print(" ✓")
                elif line == "BATCH_END":
                    elapsed = time.time() - start
                    print(f"  ✅ END - Time: {elapsed:.1f}s")
                    print(f"  Result: {cycles_seen} cycles (expected {cycles_requested})")
                    if cycles_seen == cycles_requested:
                        print(f"  ✅ PASS")
                    else:
                        print(f"  ❌ FAIL - Mismatch!")
                    return ser, cycles_seen

    print(f"\n  ⚠️ Timeout after {timeout}s")
    print(f"  Result: {cycles_seen} cycles seen (expected {cycles_requested})")
    return ser, cycles_seen

# Open connection
ser = serial.Serial('COM5', 115200, timeout=10)
time.sleep(2)

# Test sequence with isolation
test_cases = [1, 2, 5, 10]

results = []
for cycles in test_cases:
    ser, actual = run_isolated_test(ser, cycles)
    results.append((cycles, actual))
    time.sleep(2)  # Brief pause between tests

# Summary
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print(f"{'Requested':<12} {'Actual':<12} {'Status'}")
print("-" * 40)
for requested, actual in results:
    status = "✅ PASS" if requested == actual else "❌ FAIL"
    print(f"{requested:<12} {actual:<12} {status}")

ser.close()
print("\n📡 Disconnected")
