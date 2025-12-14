"""
Final test - verify 10 cycles execute correctly
"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(0.1)
ser.reset_input_buffer()

print("Testing: rankbatch:100,150,200,250,1000,100,10")
print("Expected: 10 cycles, ~44 seconds total\n")

command = "rankbatch:100,150,200,250,1000,100,10\n"
start_time = time.time()
ser.write(command.encode())

cycle_count = 0
batch_ended = False

while not batch_ended and time.time() - start_time < 60:
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if 'CYCLE:' in line:
            cycle_count += 1
            print(f"  Cycle {cycle_count}")
        elif 'BATCH_END' in line:
            batch_ended = True
            break

end_time = time.time()
elapsed = end_time - start_time

print(f"\n{'='*60}")
print(f"✅ Total time: {elapsed:.1f} seconds")
print(f"✅ Cycles executed: {cycle_count}")
print(f"✅ Average per cycle: {elapsed/cycle_count:.2f}s" if cycle_count > 0 else "")

if cycle_count == 10:
    print("🎉🎉🎉 SUCCESS! Firmware correctly executes 10 cycles! 🎉🎉🎉")
else:
    print(f"⚠️ Expected 10 cycles, got {cycle_count}")

ser.close()
