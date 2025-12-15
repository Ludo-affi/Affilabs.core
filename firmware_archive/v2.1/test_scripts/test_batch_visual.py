#!/usr/bin/env python3
"""Test batch command with clear visual confirmation"""

import time

import serial

PORT = "COM5"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(10000)

print("\n" + "=" * 60)
print("BATCH COMMAND TEST")
print("=" * 60)

print("\n1. Turn off all LEDs first")
ser.write(b"lx\n")
time.sleep(0.2)
resp = ser.read(100)
print(f"   Response: {resp}")
input("   All LEDs should be OFF. Press Enter to continue...")

print("\n2. Set different brightness for each LED using BATCH")
print("   batch:50,100,150,200")
print("   LED A=50, B=100, C=150, D=200")
ser.write(b"batch:50,100,150,200\n")
time.sleep(0.5)
resp = ser.read(100)
print(f"   Response: {resp}")

print("\n   Now turning on LED A (should be dim - brightness 50)")
ser.write(b"la\n")
time.sleep(0.2)
ser.read(100)
time.sleep(2)
input("   Is LED A on and DIM? Press Enter...")

print("\n   Now turning on LED B (should be brighter - brightness 100)")
ser.write(b"lb\n")
time.sleep(0.2)
ser.read(100)
time.sleep(2)
input("   Is LED B on and BRIGHTER than A? Press Enter...")

print("\n   Now turning on LED C (should be even brighter - brightness 150)")
ser.write(b"lc\n")
time.sleep(0.2)
ser.read(100)
time.sleep(2)
input("   Is LED C on and BRIGHTER than B? Press Enter...")

print("\n   Now turning on LED D (should be brightest - brightness 200)")
ser.write(b"ld\n")
time.sleep(0.2)
ser.read(100)
time.sleep(2)
input("   Is LED D on and BRIGHTEST? Press Enter...")

print("\n3. Turn off all LEDs")
ser.write(b"lx\n")
time.sleep(0.2)
resp = ser.read(100)
print(f"   Response: {resp}")
time.sleep(1)

print("\n" + "=" * 60)
print("If you saw LEDs getting progressively brighter (A→B→C→D),")
print("then the BATCH command is working correctly!")
print("=" * 60)

ser.close()
