import serial
import time

port = 'COM8'
baudrate = 38400

ser = serial.Serial(port, baudrate, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()
ser.reset_output_buffer()

def send_cmd(cmd, wait_time=0.5):
    cmd_bytes = f"{cmd}\r".encode('ascii')
    print(f"Send: {cmd}")
    ser.write(cmd_bytes)
    time.sleep(wait_time)
    response = ser.read(ser.in_waiting or 1024)
    print(f"Response: {response}")
    if b'`' in response:
        start = response.find(b'`') + 1
        end = response.find(b'\x03')
        if end > start:
            steps = int(response[start:end].decode('ascii'))
            ul = steps - 1600
            print(f"Position: {steps} steps = {ul}uL")
    print()

# Initialize
print("=== Initialize ===")
send_cmd("/1ZR", 5)
send_cmd("/1?")

# Test P command with ,1 (relative pickup in µL)
print("=== Test P300,1 (pickup 300µL) ===")
send_cmd("/1IR")
send_cmd("/1V200,1R")
send_cmd("/1P300,1R", 3)
send_cmd("/1?")

# Test D command with ,1 (relative dispense in µL)
print("=== Test D150,1 (dispense 150µL) ===")
send_cmd("/1OR")
send_cmd("/1D150,1R", 2)
send_cmd("/1?")

# Test A command with ,1 (absolute position in µL)
print("=== Test A500,1 (absolute 500µL) ===")
send_cmd("/1A500,1R", 3)
send_cmd("/1?")

# Test A0,1 (absolute 0µL)
print("=== Test A0,1 (absolute 0µL) ===")
send_cmd("/1A0,1R", 3)
send_cmd("/1?")

ser.close()
