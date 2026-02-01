#!/usr/bin/env python3
"""
Affipump extended response test - read ALL data after commands
"""

import sys
import time
import serial

print("="*70)
print("AFFIPUMP EXTENDED RESPONSE TEST")
print("="*70)

# Open COM8 directly
print("\n[1] Opening COM8 at 9600 baud...")
try:
    ser = serial.Serial('COM8', 9600, timeout=2)
    print("✅ COM8 opened")
except Exception as e:
    print(f"❌ Failed to open COM8: {e}")
    sys.exit(1)

time.sleep(1)
ser.read(ser.in_waiting)  # Clear buffer

def send_and_read_all(command_str, description):
    """Send command and read ALL available data"""
    print(f"\n{description}")
    print(f"  Sending: {command_str}")

    # Send command
    ser.write(command_str.encode() + b'\r')
    time.sleep(0.5)  # Wait for response

    # Read everything available
    data = ser.read(ser.in_waiting)

    print(f"  Raw bytes: {data}")
    print(f"  As hex: {data.hex()}")
    print(f"  As ASCII: {data.decode('latin-1', errors='replace')}")
    print(f"  Length: {len(data)} bytes")

    return data

# Test initialization
print("\n" + "="*70)
print("TEST 1: INITIALIZATION")
print("="*70)

send_and_read_all("/1ZR", "Initialize Pump 1")
time.sleep(2)  # Pumps may take time to initialize

send_and_read_all("/2ZR", "Initialize Pump 2")
time.sleep(2)

# Test status query
print("\n" + "="*70)
print("TEST 2: STATUS QUERY")
print("="*70)

response1 = send_and_read_all("/1?", "Query Pump 1 Status")
response2 = send_and_read_all("/2?", "Query Pump 2 Status")

# Test valve control
print("\n" + "="*70)
print("TEST 3: VALVE CONTROL")
print("="*70)

send_and_read_all("/1B3R", "Set Pump 1 valve to port 3")
time.sleep(1)

send_and_read_all("/1?", "Verify Pump 1 valve position")

# Test absolute position query
print("\n" + "="*70)
print("TEST 4: POSITION QUERY")
print("="*70)

send_and_read_all("/1?6", "Query Pump 1 absolute position")
send_and_read_all("/2?6", "Query Pump 2 absolute position")

# Test error status
print("\n" + "="*70)
print("TEST 5: ERROR STATUS")
print("="*70)

send_and_read_all("/1Q", "Query Pump 1 busy/error status")
send_and_read_all("/2Q", "Query Pump 2 busy/error status")

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

print("\nExpected Cavro response format:")
print("  1. Command echo: /1ZR")
print("  2. Status byte: One byte indicating pump state")
print("     - 0x00 = Busy")
print("     - 0x01-0x0F = Error codes")
print("     - 0x60 (`) = Ready/OK")
print("  3. Null terminator: 0x00")
print("\nIf you only see echoes (like '/1ZR\\x00'), pumps may need:")
print("  - Front panel mode switch to 'Remote'")
print("  - Power cycle")
print("  - Different initialization sequence")

ser.close()
print("\n✅ Test complete, COM8 closed")
