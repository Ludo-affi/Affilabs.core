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
    if b'`' in response:
        start = response.find(b'`') + 1
        end = response.find(b'\x03')
        if end > start:
            steps = int(response[start:end].decode('ascii'))
            ul_proper = (steps - 1600) / 181.49
            print(f"Position: {steps} steps = {ul_proper:.2f}µL")
            return steps
    return None

# Initialize to zero
print("=== Initialize ===")
send_cmd("/1ZR", 5)
steps_zero = send_cmd("/1?")

# Move to absolute position for 500µL
# Formula: target_steps = 1600 + (500 * 181.49) = 1600 + 90745 = 92345
target_500ul = int(1600 + (500 * 181.49))
print(f"\n=== Move to {target_500ul} steps (should be 500µL absolute) ===")
send_cmd("/1V200,1R")
send_cmd(f"/1A{target_500ul}R", 4)
send_cmd("/1?")

# Move to absolute position 0µL
# Formula: target_steps = 1600 + (0 * 181.49) = 1600
print("\n=== Move to 1600 steps (should be 0µL absolute) ===")
send_cmd("/1A1600R", 4)
send_cmd("/1?")

ser.close()
