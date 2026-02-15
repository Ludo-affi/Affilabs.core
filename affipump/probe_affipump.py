#!/usr/bin/env python3
"""
Probe Affipump controller to identify firmware
"""

import serial
import time

print("Connecting to COM8 (Affipump)...")
try:
    ser = serial.Serial('COM8', 115200, timeout=1)
    print("✅ Connected at 115200 baud\n")
    time.sleep(2)
    ser.read(ser.in_waiting)
    
    # Try common commands
    commands = [
        (b"iv\n", "Version command (P4 style)"),
        (b"?\n", "Help command"),
        (b"*IDN?\n", "SCPI identification"),
        (b"version\n", "Version command"),
        (b"info\n", "Info command"),
        (b"\n", "Empty line"),
    ]
    
    for cmd, desc in commands:
        print(f"Trying: {desc}")
        print(f"  Sending: {cmd}")
        ser.write(cmd)
        time.sleep(0.5)
        resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        if resp:
            print(f"  ✅ Response: {resp}")
        else:
            print(f"  No response")
        print()
    
    ser.close()
    
except Exception as e:
    print(f"❌ Error at 115200: {e}")
    
    # Try 9600 baud
    print("\nTrying 9600 baud...")
    try:
        ser = serial.Serial('COM8', 9600, timeout=1)
        print("✅ Connected at 9600 baud\n")
        time.sleep(2)
        ser.read(ser.in_waiting)
        
        ser.write(b"iv\n")
        time.sleep(0.5)
        resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        print(f"Response to 'iv': {resp}")
        
        ser.close()
    except Exception as e2:
        print(f"❌ Error at 9600: {e2}")
