import time

import serial

s = serial.Serial("COM5", 115200, timeout=3)
time.sleep(0.5)

print("Sending rank command...")
s.write(b"rank:128,100,10\n")

start = time.time()
output = []

while time.time() - start < 2:
    s.timeout = 0.1
    line = s.readline()
    if line:
        msg = line.decode().strip()
        output.append(msg)
        print(f"Got: {msg}")
        if "END" in msg:
            # Send ACK for any READY/READ
            if ":" in msg:
                s.write(b"\n")
            break
    if "READ" in str(output):
        s.write(b"\n")

print(f"Total lines: {len(output)}")
print(f"Output: {output}")
s.close()
