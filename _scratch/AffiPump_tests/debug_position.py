import serial
import time

port = 'COM8'
baudrate = 38400

ser = serial.Serial(port, baudrate, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()
ser.reset_output_buffer()

def send_cmd(cmd):
    cmd_bytes = f"{cmd}\r".encode('ascii')
    print(f"Send: {cmd}")
    ser.write(cmd_bytes)
    time.sleep(0.5)
    response = ser.read(ser.in_waiting or 1024)
    print(f"Response: {response}")
    print(f"Hex: {response.hex(' ')}")
    print()

# Initialize
print("=== Initialize ===")
send_cmd("/1ZR")
time.sleep(5)

# Query position after init
print("=== Position after init ===")
send_cmd("/1?")

# Move to 300 steps
print("=== Move to A1900 (300µL in steps) ===")
send_cmd("/1A1900R")
time.sleep(3)

# Query position
print("=== Position after A1900 ===")
send_cmd("/1?")

# Query again
print("=== Position query again ===")
send_cmd("/1?")

ser.close()
