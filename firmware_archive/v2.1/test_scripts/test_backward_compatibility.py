#!/usr/bin/env python3
"""Test backward compatibility with V1.9 commands"""

import time

import serial

PORT = "COM5"
BAUD = 115200


def test_command(ser, cmd, desc):
    """Send command and check response"""
    print(f"\n{desc}")
    print(f"  Sending: {cmd}")
    ser.write(cmd.encode() + b"\n")
    time.sleep(0.2)
    resp = ser.read(100)
    if resp == b"6":
        print("  ✅ ACK")
        return True
    print(f"  ❌ Response: {resp}")
    return False


print("=" * 60)
print("V2.0 Backward Compatibility Test")
print("=" * 60)

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(10000)  # Clear buffer

print("\n1. SERVO COMMANDS")
print("-" * 40)

# Test servo commands
test_command(ser, "sv090090", "Set servo position (S=90, P=90)")
test_command(ser, "ss", "Move to S position")
test_command(ser, "sp", "Move to P position")
test_command(ser, "servo_speed:0100", "Set servo speed to 100ms")

print("\n2. LED COMMANDS")
print("-" * 40)

# Test individual LED commands
test_command(ser, "ba128", "Set LED A brightness to 128")
test_command(ser, "la", "Turn on LED A")
time.sleep(0.5)
test_command(ser, "lx", "Turn off all LEDs")

print("\n3. BATCH LED COMMAND")
print("-" * 40)

# Test batch command
test_command(ser, "batch:100,150,200,255", "Set all 4 LEDs (batch)")
time.sleep(0.5)
test_command(ser, "lx", "Turn off all LEDs")

print("\n4. RANK LED COMMAND (V2.0)")
print("-" * 40)

# Test new rank command
test_command(ser, "rank:128,100,50", "Rank LED sequence")

print("\n" + "=" * 60)
print("✅ All backward compatibility tests complete!")
print("=" * 60)

ser.close()
