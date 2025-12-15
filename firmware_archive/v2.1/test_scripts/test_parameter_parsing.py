"""Test to verify what the firmware is actually parsing"""

import time

import serial

print("=" * 70)
print("PARAMETER PARSING VERIFICATION TEST")
print("=" * 70)

ser = serial.Serial("COM5", 115200, timeout=5)
time.sleep(2)
ser.reset_input_buffer()

# Enable debug mode to see detailed output
print("\n🔧 Enabling debug mode...")
ser.write(b"d\n")
time.sleep(0.5)
while ser.in_waiting > 0:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if line:
        print(f"  {line}")

# Test with explicit values that are easy to identify
test_cases = [
    ("Test 1: Simple single digits", "rankbatch:1,2,3,4,500,50,2\n", 2),
    ("Test 2: Mixed values", "rankbatch:100,150,200,250,500,50,3\n", 3),
    ("Test 3: Target config", "rankbatch:100,150,200,250,1000,100,10\n", 10),
]

for test_name, command, expected_cycles in test_cases:
    print(f"\n{'='*70}")
    print(f"{test_name}")
    print(f"Command: {command.strip()}")
    print(f"Expected cycles: {expected_cycles}")
    print("-" * 70)

    ser.reset_input_buffer()
    ser.write(command.encode())

    cycles_seen = 0
    got_batch_start = False
    got_batch_end = False
    start = time.time()
    timeout = expected_cycles * 2 + 5

    while time.time() - start < timeout:
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if line:
                if line.startswith("BATCH_START"):
                    got_batch_start = True
                    print("  ✅ BATCH_START received")
                elif line.startswith("CYCLE:"):
                    cycle_num = int(line.split(":")[1])
                    cycles_seen = max(cycles_seen, cycle_num)
                    print(f"  Cycle {cycle_num}", end="", flush=True)
                elif line.endswith("READ"):
                    ser.write(b"ack\n")
                    print(".", end="", flush=True)
                elif line.startswith("CYCLE_END"):
                    print(" ✓")
                elif line == "BATCH_END":
                    got_batch_end = True
                    elapsed = time.time() - start
                    print(f"  ✅ BATCH_END received (time: {elapsed:.1f}s)")
                    break
                elif "rankbatch ok" in line or "rankbatch er" in line:
                    print(f"  Debug: {line}")

    # Analysis
    print(f"\n  Result: {cycles_seen} cycles executed")
    if cycles_seen == expected_cycles:
        print("  ✅ PASS")
    else:
        print(f"  ❌ FAIL - Expected {expected_cycles}, got {cycles_seen}")
        if cycles_seen == 1:
            print("  ⚠️  Parsing likely failed, defaulted to 1 cycle")

    if not got_batch_start:
        print("  ⚠️  No BATCH_START received")
    if not got_batch_end:
        print("  ⚠️  No BATCH_END received")

    time.sleep(1)

print(f"\n{'='*70}")
print("CONCLUSION")
print("=" * 70)
print("\nIf all tests show 1 cycle when expecting more:")
print("  → The 7th parameter (CYCLES) is not being parsed correctly")
print("  → Check: Buffer overflow, off-by-one error, or field counting bug")
print("\nIf specific tests fail:")
print("  → May be related to parameter length or specific values")

ser.close()
print("\n📡 Disconnected")
