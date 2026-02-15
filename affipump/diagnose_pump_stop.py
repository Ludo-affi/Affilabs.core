#!/usr/bin/env python3
"""
Check pump status, errors, and why it stopped
"""
import serial
import time

port = 'COM8'
baudrate = 38400

ser = serial.Serial(port, baudrate, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()
ser.reset_output_buffer()

def decode_status(status_byte):
    """Decode Cavro status byte"""
    print(f"  Status byte: 0x{status_byte:02x} ({status_byte:08b})")
    print(f"  Bit 7 (Initialized): {'YES' if status_byte & 0x80 else 'NO'}")
    print(f"  Bit 6 (Moving/Busy): {'YES' if status_byte & 0x40 else 'NO'}")
    print(f"  Bit 5 (Idle/Ready):  {'YES' if status_byte & 0x20 else 'NO'}")
    print(f"  Bit 4 (Error):       {'YES' if status_byte & 0x10 else 'NO'}")
    print(f"  Bit 3 (Reserved):    {status_byte & 0x08}")
    
    if status_byte == 0x60:
        print("  > Status: Ready (Initialized + Idle)")
    elif status_byte == 0x40:
        print("  > Status: BUSY (Moving)")
    elif status_byte & 0x10:
        print("  > Status: ERROR DETECTED!")

print("="*70)
print("Pump Status and Error Check")
print("="*70)

# Position query (returns status + position)
print("\n1. Current status and position:")
ser.write(b'/1?\r')
time.sleep(0.3)
resp = ser.read(200)
print(f"Response: {resp}")
if b'/0' in resp:
    status_byte = resp[resp.find(b'/0')+2]
    decode_status(status_byte)

# Error code query
print("\n2. Error code query (?4):")
ser.write(b'/1?4\r')
time.sleep(0.3)
resp = ser.read(200)
print(f"Response: {resp}")
if b'`' in resp:
    start = resp.find(b'`') + 1
    end = resp.find(b'\x03')
    if end > start:
        error_code = resp[start:end].decode('ascii')
        print(f"  Last Error Code: {error_code}")
        
        # Common error codes
        errors = {
            '0': 'No error',
            '1': 'Initialization failure',
            '2': 'Invalid command',
            '3': 'Invalid operand',
            '6': 'EEPROM failure',
            '7': 'Device not initialized',
            '9': 'Plunger overload',
            '10': 'Valve overload',
            '11': 'Plunger move not allowed',
            '15': 'Command overflow'
        }
        if error_code in errors:
            print(f"  Meaning: {errors[error_code]}")

# Check if stalled
print("\n3. Checking various status queries:")
queries = {
    '?': 'Position',
    '?4': 'Last error code',
    '?22': 'Pressure threshold',
    '?24': 'Pressure sensor',
    '?25': 'Pressure limit'
}

for cmd, desc in queries.items():
    ser.write(f'/1{cmd}\r'.encode())
    time.sleep(0.2)
    resp = ser.read(200)
    
    if b'`' in resp:
        start = resp.find(b'`') + 1
        end = resp.find(b'\x03')
        data = resp[start:end].decode('ascii', errors='ignore') if end > start else 'N/A'
        print(f"  {desc:20s} ({cmd:4s}): {data}")

# Try to clear errors
print("\n4. Clear errors (W command):")
ser.write(b'/1WR\r')
time.sleep(0.3)
resp = ser.read(200)
print(f"Response: {resp}")

# Check status again
print("\n5. Status after clearing errors:")
ser.write(b'/1?\r')
time.sleep(0.3)
resp = ser.read(200)
if b'/0' in resp:
    status_byte = resp[resp.find(b'/0')+2]
    decode_status(status_byte)

ser.close()

print("\n" + "="*70)
print("If Error Code = 9 or 10: Overload (likely pressure)")
print("If pump won't move: May need to re-initialize")
print("="*70)
