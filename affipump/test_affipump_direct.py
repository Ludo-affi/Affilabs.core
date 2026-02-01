#!/usr/bin/env python3
"""
Standalone Affipump test using Python 3.12
Works directly with pump_controller.py without additional dependencies
"""

import sys
import time

# Add affipump directory to path
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezcontrol-AI\affipump')

from pump_controller import PumpController

print("="*70)
print("AFFIPUMP DIRECT TEST (Python 3.12)")
print("="*70)

# Step 1: Connect
print("\n[1] Connecting to pump controller on COM8...")
controller = PumpController.from_first_available()

if not controller:
    print("❌ No FTDI pump controller found")
    print("\nTroubleshooting:")
    print("  - Check Affipump is powered on")
    print("  - Verify USB connection")
    print("  - Confirm COM8 in Device Manager")
    sys.exit(1)

print("✅ Connected to COM8")

# Step 2: Test basic communication
print("\n[2] Testing pump communication...")

# Initialize Pump 1
print("  Sending /1ZR (Initialize Pump 1)...")
response = controller.send_command(0x31, b"ZR")
print(f"  Response: {response}")

time.sleep(2)

# Initialize Pump 2
print("  Sending /2ZR (Initialize Pump 2)...")
response = controller.send_command(0x32, b"ZR")
print(f"  Response: {response}")

time.sleep(2)

# Query Pump 1 status
print("\n[3] Querying pump status...")
print("  Sending /1? (Query Pump 1)...")
response = controller.send_command(0x31, b"?")
print(f"  Response: {response}")

# Query Pump 2 status
print("  Sending /2? (Query Pump 2)...")
response = controller.send_command(0x32, b"?")
print(f"  Response: {response}")

# Set valve position
print("\n[4] Testing valve control...")
print("  Sending /1B3R (Set Pump 1 valve to port 3)...")
response = controller.send_command(0x31, b"B3R")
print(f"  Response: {response}")

time.sleep(1)

# Query valve position
print("  Sending /1? (Verify valve position)...")
response = controller.send_command(0x31, b"?")
print(f"  Response: {response}")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
print("\nIf you see responses with data bytes (not just echoes),")
print("the pumps are working correctly!")

controller.close()
print("\n✅ Connection closed")
