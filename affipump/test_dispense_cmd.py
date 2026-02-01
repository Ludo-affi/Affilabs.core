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
    time.sleep(0.8)
    response = ser.read(ser.in_waiting or 1024)
    print(f"Response: {response}")
    status_byte = response[response.find(b'/0')+2:response.find(b'/0')+3]
    print(f"Status: 0x{status_byte.hex()} = {int.from_bytes(status_byte, 'big'):08b}")
    if b'`' in response:
        start = response.find(b'`') + 1
        end = response.find(b'\x03')
        if end > start:
            data = response[start:end].decode('ascii')
            print(f"Position: {data} steps = {int(data) - 1600}uL")
    print()

# Initialize
send_cmd("/1ZR")
time.sleep(5)
send_cmd("/1?")

# Aspirate 500uL
send_cmd("/1IR")
send_cmd("/1V200,1R")
send_cmd("/1A500R")
time.sleep(3)
send_cmd("/1?")

# Try D command for dispense
print("=== Try D150R for dispense ===")
send_cmd("/1OR")
send_cmd("/1D150R")
time.sleep(2)
send_cmd("/1?")

ser.close()
