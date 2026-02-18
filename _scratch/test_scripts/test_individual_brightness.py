import serial
import time

ser = serial.Serial('COM3', 115200, timeout=2)
time.sleep(2)

# Clear
ser.write(b'lx\n')
time.sleep(0.5)

# Test LED A at different levels
print("Testing LED A at brightness 255...")
ser.write(b'bA255\n')
time.sleep(0.1)
ser.write(b'la:255\n')
time.sleep(0.1)
input("LED A at 255 - Note brightness. Press Enter...")

ser.write(b'lx\n')
time.sleep(0.5)

print("Testing LED A at brightness 50...")
ser.write(b'bA050\n')
time.sleep(0.1)
ser.write(b'la:50\n')
time.sleep(0.1)
input("LED A at 50 - Dimmer than before? Press Enter...")

ser.write(b'lx\n')
time.sleep(0.5)

print("Testing LED A at brightness 10...")
ser.write(b'bA010\n')
time.sleep(0.1)
ser.write(b'la:10\n')
time.sleep(0.1)
input("LED A at 10 - Very dim? Press Enter...")

ser.close()
