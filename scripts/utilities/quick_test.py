import time

import serial

s = serial.Serial("COM5", 115200, timeout=0.05)
time.sleep(1)

print("Sending rankbatch command...")
s.write(b"rankbatch:128,128,128,128,245,5,2\n")

start = time.time()
lines = []

while time.time() - start < 4:
    if s.in_waiting:
        line = s.readline().decode().strip()
        if line:
            lines.append(f"{time.time()-start:.2f}s: {line}")
            print(f"{time.time()-start:.2f}s: {line}")
        if "COMPLETE" in line:
            break

print(f"\nTotal lines received: {len(lines)}")
s.close()
