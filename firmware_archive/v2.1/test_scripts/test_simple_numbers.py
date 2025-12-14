"""Test with simpler numbers"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

# Try with all 100s to simplify
command = "rankbatch:100,100,100,100,250,250,10\n"
print(f"Testing: {command.strip()}\n")

ser.write(command.encode())

cycles = []
start = time.time()

while time.time() - start < 25:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(line)
            if line.startswith("CYCLE:"):
                cycles.append(line)
            elif "READ" in line:
                ser.write(b"ack\n")
            elif "BATCH_END" in line:
                break

ser.close()
print(f"\n✅ Cycles executed: {len(cycles)}")
if cycles:
    print(f"   First: {cycles[0]}")
    print(f"   Last: {cycles[-1]}")
