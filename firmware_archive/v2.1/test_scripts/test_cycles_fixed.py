"""
Test if the firmware now correctly parses and executes the cycle count
"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(0.1)

# Clear buffer
ser.reset_input_buffer()

print("Configuration: LEDs: A=100, B=150, C=200, D=250")
print("               Settle=1000ms, Dark=100ms, Cycles=10")
print("               Expected: ~4.4s per cycle, ~44s total")
print()

# Send rankbatch command with 10 cycles
command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"Sending: {command.strip()}")
print()

start_time = time.time()
ser.write(command.encode())

# Read all output
output_lines = []
while True:
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            output_lines.append(line)
            print(f"  {line}")

    # Check if done (BATCH_END received)
    if any('BATCH_END' in line for line in output_lines):
        break

    # Safety timeout
    if time.time() - start_time > 60:
        print("\n⚠️ Timeout after 60 seconds")
        break

    time.sleep(0.05)

end_time = time.time()
elapsed = end_time - start_time

# Count cycles
cycle_count = sum(1 for line in output_lines if 'CYCLE:' in line)

print()
print("="*60)
print(f"✅ Total time: {elapsed:.1f} seconds")
print(f"✅ Cycles executed: {cycle_count}")
print(f"✅ Average per cycle: {elapsed/cycle_count:.2f}s" if cycle_count > 0 else "")

if cycle_count == 10:
    print("🎉 SUCCESS! Firmware now correctly executes 10 cycles!")
else:
    print(f"⚠️ Expected 10 cycles, got {cycle_count}")

ser.close()
