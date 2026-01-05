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
    if b'`' in response:
        start = response.find(b'`') + 1
        end = response.find(b'\x03')
        if end > start:
            data = response[start:end].decode('ascii')
            print(f"Position: {data} steps")
    print()

# Initialize
print("=== Initialize ===")
send_cmd("/1ZR")
time.sleep(5)
send_cmd("/1?")

# Try moving to specific step counts
print("=== Move to 300 steps (A300) ===")
send_cmd("/1A300R")
time.sleep(2)
send_cmd("/1?")

print("=== Move to 0 steps (A0) ===")
send_cmd("/1A0R")
time.sleep(2)
send_cmd("/1?")

print("=== Move to 1600 steps (A1600) - should be zero ===")
send_cmd("/1A1600R")
time.sleep(2)
send_cmd("/1?")

ser.close()
