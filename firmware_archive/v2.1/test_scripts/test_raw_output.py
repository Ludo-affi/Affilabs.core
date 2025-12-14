"""Simple test to verify firmware response"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=5)
time.sleep(2)

# Enable debug
ser.reset_input_buffer()
ser.write(b"d\n")
time.sleep(0.3)
ser.read_all()

# Send command and capture ALL output
ser.reset_input_buffer()
print("Sending command...")
ser.write(b"rankbatch:100,150,200,250,1000,100,10\n")

print("\nAll output:")
print("-"*70)
time.sleep(0.5)

# Read initial response
initial = ser.read_all().decode('utf-8', errors='ignore')
print(initial, end="")

# Continue reading for 5 seconds
start = time.time()
while time.time() - start < 5:
    if ser.in_waiting > 0:
        data = ser.read_all().decode('utf-8', errors='ignore')
        print(data, end="")
        # Send acks
        if "READ" in data:
            ser.write(b"ack\n")
    time.sleep(0.1)

print("\n" + "-"*70)
ser.close()
