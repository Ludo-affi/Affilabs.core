"""Diagnose firmware parsing of rankbatch command"""
import serial
import time

print("="*70)
print("FIRMWARE PARSING DIAGNOSTIC")
print("="*70)
print("\nThis will send various rankbatch commands to see what the firmware")
print("actually parses and executes.")
print("="*70)

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)

# Enable debug mode first
print("\n🔧 Enabling debug mode...")
ser.reset_input_buffer()
ser.write(b"d\n")
time.sleep(0.5)
while ser.in_waiting > 0:
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        print(f"  {line}")

# Test 1: Simple single digit cycle count
print("\n" + "="*70)
print("TEST 1: Single digit cycle count (5)")
print("="*70)
ser.reset_input_buffer()
command = "rankbatch:50,50,50,50,250,50,5\n"
print(f"Command: {command.strip()}")
ser.write(command.encode())

cycles_seen = []
start = time.time()
while time.time() - start < 15:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"  {line}")
            if line.startswith("CYCLE:"):
                cycles_seen.append(line)
            elif line.endswith("READ"):
                ser.write(b"ack\n")
            elif line == "BATCH_END":
                break

print(f"\nResult: {len(cycles_seen)} cycles executed (expected 5)")
time.sleep(1)

# Test 2: Double digit cycle count
print("\n" + "="*70)
print("TEST 2: Double digit cycle count (10)")
print("="*70)
ser.reset_input_buffer()
command = "rankbatch:50,50,50,50,250,50,10\n"
print(f"Command: {command.strip()}")
ser.write(command.encode())

cycles_seen = []
start = time.time()
while time.time() - start < 30:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"  {line}")
            if line.startswith("CYCLE:"):
                cycles_seen.append(line)
            elif line.endswith("READ"):
                ser.write(b"ack\n")
            elif line == "BATCH_END":
                break

print(f"\nResult: {len(cycles_seen)} cycles executed (expected 10)")
time.sleep(1)

# Test 3: Triple digit cycle count
print("\n" + "="*70)
print("TEST 3: Triple digit cycle count (100)")
print("="*70)
print("(Sending command but won't wait for completion)")
ser.reset_input_buffer()
command = "rankbatch:50,50,50,50,250,50,100\n"
print(f"Command: {command.strip()}")
ser.write(command.encode())

# Just check first few cycles
cycles_seen = []
start = time.time()
sample_time = 5  # Only sample for 5 seconds
while time.time() - start < sample_time:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            if line.startswith("CYCLE:"):
                cycles_seen.append(line)
                print(f"  {line}")
            elif line.endswith("READ"):
                ser.write(b"ack\n")

print(f"\nSample result: {len(cycles_seen)} cycles seen in {sample_time}s")
print("(Not waiting for completion)")

# Send abort
ser.close()
time.sleep(1)
ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)
print("\nIf all tests show only 1 cycle, the parsing logic is likely")
print("defaulting num_cycles to 1 or there's a bug in the loop.")
print("\nPossible causes:")
print("1. Firmware on device is not V2.1")
print("2. atoi() failing to parse the cycle count")
print("3. num_cycles variable not being properly used in loop")
print("4. Early exit from the loop")

ser.close()
print("\n📡 Disconnected")
