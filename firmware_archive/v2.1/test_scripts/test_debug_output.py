"""
Check what's happening during execution
"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(0.1)
ser.reset_input_buffer()

command = "rankbatch:100,150,200,250,1000,100,10\n"
ser.write(command.encode())

print("First 30 lines of output:")
for i in range(30):
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        print(f"{i+1}: {line}")
    time.sleep(0.1)

ser.close()
