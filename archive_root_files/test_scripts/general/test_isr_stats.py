import time

import serial

s = serial.Serial("COM5", 115200, timeout=2)
time.sleep(0.5)
s.flushInput()  # Clear startup messages

print("Sending rankbatch command...")
s.write(b"rankbatch:128,128,128,128,245,5,2\n")
time.sleep(1.5)

print(f"Bytes waiting after rankbatch: {s.in_waiting}")
print("Reading all responses:")
for i in range(20):
    if s.in_waiting:
        line = s.readline().decode().strip()
        print(f"  [{i}] {line}")
    else:
        break

print("\nQuerying ISR stats with 'ix' command...")
s.write(b"ix\n")
time.sleep(0.3)

print(f"Bytes waiting after ix: {s.in_waiting}")
if s.in_waiting > 0:
    isr_resp = s.read(s.in_waiting).decode().strip()
    print(f"ISR Stats: {isr_resp}")
else:
    print("ISR Stats: NO RESPONSE")

print("\nTesting 'iv' command for comparison...")
s.write(b"iv\n")
time.sleep(0.2)
print(f"Bytes waiting after iv: {s.in_waiting}")
if s.in_waiting > 0:
    iv_resp = s.read(s.in_waiting).decode().strip()
    print(f"Version: {iv_resp}")
else:
    print("Version: NO RESPONSE")

s.close()
