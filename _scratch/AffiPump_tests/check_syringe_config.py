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
            print(f"Data: {data}")
    print()

# Query syringe volume (?17 command)
print("=== Query Syringe Volume (?17) ===")
send_cmd("/1?17")

# Query plunger position
print("=== Query Position (?) ===")
send_cmd("/1?")

print("\nNOTE: If SyringeVol = 181490, then 1 step = 1µL (our current mode)")
print("If SyringeVol = 1000, we'd need to use ,1 parameter for µL commands")

ser.close()
