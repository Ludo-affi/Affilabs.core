import serial
import time

port = 'COM3'
print(f"Testing P4PRO servo commands on {port}...")

ser = serial.Serial(port, 115200, timeout=1)

# Test 1
print("\nTEST 1: servo:45,150")
ser.reset_input_buffer()
ser.write(b"servo:45,150\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"Response: {resp!r}")

time.sleep(2)

# Test 2
print("\nTEST 2: sv090090")
ser.reset_input_buffer()
ser.write(b"sv090090\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"Response: {resp!r}")

time.sleep(2)

# Test 3
print("\nTEST 3: ss")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.5)
resp = ser.read(20)
print(f"Response: {resp!r}")

ser.close()
