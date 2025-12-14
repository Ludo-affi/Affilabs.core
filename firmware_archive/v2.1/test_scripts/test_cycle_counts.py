"""Diagnostic test to see what cycle count firmware sees"""
import serial
import time

print("="*60)
print("CYCLE COUNT DIAGNOSTIC TEST")
print("="*60)

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

# Test different cycle counts
test_cases = [
    ("1 cycle", "rankbatch:100,100,100,100,250,50,1\n"),
    ("2 cycles", "rankbatch:100,100,100,100,250,50,2\n"),
    ("3 cycles", "rankbatch:100,100,100,100,250,50,3\n"),
    ("5 cycles", "rankbatch:100,100,100,100,250,50,5\n"),
    ("10 cycles", "rankbatch:100,100,100,100,250,50,10\n"),
]

for test_name, command in test_cases:
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"Command: {command.strip()}")
    print('-'*60)

    ser.reset_input_buffer()
    ser.write(command.encode())

    cycles_seen = 0
    start = time.time()

    while time.time() - start < 30:  # 30 second timeout per test
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if line:
                if line.startswith("CYCLE:"):
                    cycle_num = line.split(":")[1]
                    cycles_seen += 1
                    print(f"  Cycle {cycle_num}", end="", flush=True)

                elif line.endswith("READY"):
                    ch = line.split(":")[0]
                    print(f" {ch}", end="", flush=True)

                elif line.endswith("READ"):
                    ser.write(b"ack\n")
                    print("✓", end="", flush=True)

                elif line.startswith("CYCLE_END"):
                    print()  # New line after cycle complete

                elif line == "BATCH_END":
                    elapsed = time.time() - start
                    print(f"\n  BATCH_END - Time: {elapsed:.1f}s")
                    print(f"  ✅ Expected: {test_name}, Got: {cycles_seen} cycles")
                    if cycles_seen != int(test_name.split()[0]):
                        print(f"  ⚠️  MISMATCH!")
                    break

    # Small delay between tests
    time.sleep(1)

print(f"\n{'='*60}")
ser.close()
print("\n📡 Disconnected")
