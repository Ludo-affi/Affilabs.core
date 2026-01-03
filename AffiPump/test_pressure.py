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
            data = response[start:end].decode('ascii', errors='ignore')
            print(f"Data: {data}")
    print()
    return response

print("="*60)
print("Testing Pressure Sensing Capabilities")
print("="*60)

# Initialize pump 1
print("\n=== Initialize Pump 1 ===")
send_cmd("/1ZR", 5)

# Try common pressure query commands
print("\n=== Query Commands ===")

# Standard position query (we know this works)
print("Position query (?)")
send_cmd("/1?")

# Try pressure-related queries
print("Pressure query (?F) - Force/Pressure")
send_cmd("/1?F")

print("Pressure query (?24) - Pressure sensor")
send_cmd("/1?24")

print("Pressure query (?25) - Pressure limit")
send_cmd("/1?25")

print("Status with pressure (?6) - Detailed status")
send_cmd("/1?6")

print("Error status (?E)")
send_cmd("/1?E")

# Try during operation
print("\n=== Aspirate 300µL and check for pressure data ===")
steps = int(300 * 181.49)
send_cmd("/1IR")
send_cmd(f"/1P{steps}R", 3)

print("Position query during/after move:")
send_cmd("/1?")

print("Pressure query during/after move:")
send_cmd("/1?F")

# Check configuration
print("\n=== Configuration Queries ===")
print("Firmware version (?23)")
send_cmd("/1?23")

print("Configuration (?27)")
send_cmd("/1?27")

print("All parameters (?0-30)")
for i in [0, 1, 2, 3, 10, 15, 20, 21, 22, 26, 28, 29, 30]:
    send_cmd(f"/1?{i}", 0.3)

ser.close()

print("\n" + "="*60)
print("ANALYSIS:")
print("If pressure data is available, it should appear above.")
print("No response or error = No pressure sensor capability")
print("="*60)
