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
            ul = (steps - 1600) / 181.49
            print(f"Position: {steps} steps = {ul:.2f}µL")
    print()

print("="*60)
print("Testing Individual Pump Control")
print("="*60)

# Initialize both pumps using broadcast
print("=== Initialize BOTH pumps (address A) ===")
send_cmd("/AZR", 5)

# Check pump 1 position
print("=== Check Pump 1 position ===")
send_cmd("/1?")

# Check pump 2 position
print("=== Check Pump 2 position ===")
send_cmd("/2?")

print("\n" + "="*60)
print("Testing Individual Operations")
print("="*60)

# Aspirate with pump 1
print("=== Pump 1: Aspirate 200µL ===")
steps_200 = int(200 * 181.49)
send_cmd("/1IR")
send_cmd("/1V200,1R")
send_cmd(f"/1P{steps_200}R", 2)
send_cmd("/1?")

# Aspirate with pump 2
print("=== Pump 2: Aspirate 300µL ===")
steps_300 = int(300 * 181.49)
send_cmd("/2IR")
send_cmd("/2V200,1R")
send_cmd(f"/2P{steps_300}R", 3)
send_cmd("/2?")

print("\n" + "="*60)
print("Testing Synchronized Operations (Broadcast)")
print("="*60)

# Dispense 100µL from BOTH pumps simultaneously
print("=== BOTH pumps: Dispense 100µL (address A) ===")
steps_100 = int(100 * 181.49)
send_cmd("/AOR")
send_cmd("/AV50,1R")
send_cmd(f"/AD{steps_100}R", 3)

print("=== Check Pump 1 position (should be ~100µL) ===")
send_cmd("/1?")

print("=== Check Pump 2 position (should be ~200µL) ===")
send_cmd("/2?")

# Move both to zero
print("\n=== BOTH pumps: Move to 0µL ===")
send_cmd("/1?")  # Get pump 1 position
time.sleep(0.3)
send_cmd("/2?")  # Get pump 2 position
time.sleep(0.3)

# For simplicity, just dispense all
send_cmd("/AOR")
send_cmd("/AV200,1R")
# Move to home (A0 is absolute 0 in increments, but it's relative!)
# Better: use position query to calculate, but for demo, send a large D command
send_cmd("/AD100000R", 5)  # Dispense max, will stop at 0

print("=== Final positions ===")
send_cmd("/1?")
send_cmd("/2?")

ser.close()

print("\n" + "="*60)
print("SUMMARY:")
print("- /1 = Control pump 1 only")
print("- /2 = Control pump 2 only")
print("- /A = Control BOTH pumps simultaneously (broadcast)")
print("="*60)
