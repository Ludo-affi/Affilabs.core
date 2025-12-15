"""Test 2 cycles to debug"""

import time

import serial

ser = serial.Serial("COM5", 115200, timeout=10)
time.sleep(2)
ser.reset_input_buffer()

command = "rankbatch:100,150,200,250,1000,100,2\n"
print(f"Testing: {command.strip()}")

ser.write(command.encode())
start = time.time()

lines = []
while time.time() - start < 30:
    if ser.in_waiting > 0:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            lines.append(line)
            print(line)
            if "READ" in line:
                ser.write(b"ack\n")
            if "BATCH_END" in line:
                break

ser.close()

print(f"\n✅ Total lines: {len(lines)}")
cycles = [l for l in lines if "CYCLE:" in l]
print(f"📊 Cycles: {cycles}")
