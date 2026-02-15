#!/usr/bin/env python3
"""
Test simultaneous pump operation and pressure monitoring
"""
import serial
import time

port = 'COM8'
baudrate = 38400

ser = serial.Serial(port, baudrate, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()
ser.reset_output_buffer()

def send_cmd(cmd, wait_time=0.1):
    cmd_bytes = f"{cmd}\r".encode('ascii')
    ser.write(cmd_bytes)
    time.sleep(wait_time)
    response = ser.read(ser.in_waiting or 1024)
    return response

def get_pressure():
    resp = send_cmd("/1?24", 0.05)
    if b'`' in resp:
        start = resp.find(b'`') + 1
        end = resp.find(b'\x03')
        if end > start:
            return int(resp[start:end].decode('ascii'))
    return None

def get_position():
    resp = send_cmd("/1?", 0.05)
    if b'`' in resp:
        start = resp.find(b'`') + 1
        end = resp.find(b'\x03')
        if end > start:
            steps = int(resp[start:end].decode('ascii'))
            return (steps - 1600) / 181.49
    return None

print("="*70)
print("Testing Real-Time Pressure Monitoring During Pump Operation")
print("="*70)

# Initialize
print("\n1. Initialize pump 1...")
send_cmd("/1ZR", 5)
print(f"   Position: {get_position():.1f}µL")

# Aspirate some volume
print("\n2. Aspirate 500µL...")
steps = int(500 * 181.49)
send_cmd("/1IR", 0.3)
send_cmd("/1V200,1R", 0.2)
send_cmd(f"/1P{steps}R", 0.1)  # Don't wait for completion
time.sleep(3)  # Wait for move to complete
print(f"   Position: {get_position():.1f}µL")

input("\n>>> BLOCK THE OUTLET NOW, then press ENTER to start test...\n")

# Start a SLOW dispense to give us time to monitor
print("\n3. Starting SLOW dispense (300µL at 30µL/s)...")
print("   Monitoring pressure and position in real-time:\n")
print("   Time (s) | Pressure | Position (µL) | Status")
print("   " + "-"*60)

steps_300 = int(300 * 181.49)
send_cmd("/1OR", 0.3)
send_cmd("/1V30,1R", 0.2)  # Very slow: 30µL/s
send_cmd(f"/1D{steps_300}R", 0.05)  # Start dispense, don't wait

start_time = time.time()

# Monitor for 12 seconds (300µL at 30µL/s = 10 seconds expected)
for i in range(60):  # 60 iterations x 0.2s = 12 seconds
    elapsed = time.time() - start_time
    
    # Query pressure
    pressure = get_pressure()
    pressure_str = f"{pressure:8d}" if pressure is not None else "    N/A "
    
    # Query position
    position = get_position()
    position_str = f"{position:13.1f}" if position is not None else "         N/A "
    
    # Query status
    status_resp = send_cmd("/1?", 0.05)
    if b'@' in status_resp:
        status = "BUSY"
    elif b'`' in status_resp:
        status = "IDLE"
    else:
        status = "UNKNOWN"
    
    print(f"   {elapsed:7.1f}  | {pressure_str} | {position_str} | {status}")
    
    time.sleep(0.2)
    
    # Stop if pump is idle
    if status == "IDLE":
        break

print("\n" + "-"*70)
print("\n4. Final readings:")
print(f"   Pressure: {get_pressure()}")
print(f"   Position: {get_position():.1f}µL")

ser.close()

print("\n" + "="*70)
print("ANALYSIS:")
print("- If pressure values changed during dispense: Sensor is working!")
print("- If pump stopped early: Pressure limit may have triggered")
print("- If pressure stayed at 0: No sensor or not connected")
print("="*70)
