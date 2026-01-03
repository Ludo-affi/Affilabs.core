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
            ul_calc = steps - 1600  # Our current calculation
            ul_proper = (steps / 181490) * 1000  # Proper calculation
            print(f"Position: {steps} steps = {ul_calc}µL (our calc) vs {ul_proper:.2f}µL (proper)")
            return steps
    return None

# Initialize
print("=== Initialize ===")
send_cmd("/1ZR", 5)
steps = send_cmd("/1?")

# Test: Send P300 (300 increments)
print("\n=== Send P300 (300 increments, should be ~1.65µL) ===")
send_cmd("/1IR")
send_cmd("/1V200,1R")
send_cmd("/1P300R", 2)
steps = send_cmd("/1?")

# Test: Send P54447 (300µL in increments: 300 × 181.49)
print("\n=== Send P54447 (300µL in increments) ===")
send_cmd("/1P54447R", 4)
steps = send_cmd("/1?")

ser.close()

print("\n" + "="*60)
print("ANALYSIS:")
print("If P300 moved ~300µL, something is wrong with scaling")
print("If P54447 moved ~300µL, we need to fix our conversion!")
print("="*60)
