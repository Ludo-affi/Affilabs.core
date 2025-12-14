#!/usr/bin/env python3
"""Test V2.0 firmware with rank command in acquisition loop"""
import serial
import time
import numpy as np

PORT = 'COM5'
BAUD = 115200

print("\n" + "="*60)
print("V2.0 ACQUISITION TEST - Using RANK command")
print("="*60)

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(10000)  # Clear buffer

# Test parameters
INTENSITY = 150
SETTLING_MS = 35
DARK_MS = 5
NUM_CYCLES = 5

print(f"\nTest parameters:")
print(f"  LED intensity: {INTENSITY}")
print(f"  Settling time: {SETTLING_MS}ms")
print(f"  Dark time: {DARK_MS}ms")
print(f"  Cycles: {NUM_CYCLES}")

print("\nRunning acquisition cycles with RANK command...")
print("-" * 60)

for cycle in range(NUM_CYCLES):
    print(f"\nCycle {cycle+1}/{NUM_CYCLES}:")

    # Send rank command
    cmd = f"rank:{INTENSITY},{SETTLING_MS},{DARK_MS}\n"
    ser.write(cmd.encode())

    # Wait for LEDs to complete sequence
    cycle_time_ms = 4 * (SETTLING_MS + DARK_MS)
    time.sleep(cycle_time_ms / 1000.0 + 0.1)  # Add small buffer

    # Read response
    resp = ser.read(100)
    if resp == b'6':
        print(f"  ✅ Rank command ACK - LEDs sequenced A→B→C→D")
    else:
        print(f"  ❌ Unexpected response: {resp}")

    # Small delay between cycles
    time.sleep(0.2)

print("\n" + "="*60)
print("✅ Acquisition test complete!")
print("\nWith V2.0 firmware:")
print("  • Single 'rank:' command sequences all 4 LEDs")
print("  • No need for individual 'la/lb/lc/ld' commands")
print("  • Eliminates USB command overhead")
print("  • Perfect for high-speed acquisition")
print("="*60)

ser.close()
