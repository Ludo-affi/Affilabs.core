# -*- coding: utf-8 -*-
"""
Test AffiPump with proper zero positioning
"""
import sys
sys.path.insert(0, r'C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\AffiPump')
from affipump_v2 import AffipumpController
import time

print("="*60)
print("AffiPump Test - With Zero Reset")
print("="*60)

pump = AffipumpController(port='COM8', baudrate=38400, syringe_volume_ul=1000)

try:
    pump.open()
    
    # Initialize
    print("\n1. Initializing pumps...")
    pump.initialize_pumps()
    time.sleep(5)
    
    # Check position after init
    pos = pump.get_position(1)
    print(f"   Position after init: {pos}uL")
    
    # If position is weird or over capacity, manually move to zero
    if pos > 1000 or pos < 0:
        print(f"   Position {pos}uL is invalid, moving to 100uL safe position...")
        pump.set_speed(1, 200)
        time.sleep(0.5)
        pump.send_command("/1A100R", wait_time=2)
        time.sleep(2)
        pos = pump.get_position(1)
        print(f"   New position: {pos}uL")
    
    # Now test aspirate from current position
    print(f"\n2. Current position: {pos}uL")
    print("   Aspirating 200uL...")
    
    try:
        target = pump.aspirate(1, 200, speed_ul_s=100)
        time.sleep(3)
        final_pos = pump.get_position(1)
        print(f"   Target: {target}uL, Actual: {final_pos}uL")
        print(f"   SUCCESS! Moved {final_pos - pos}uL")
    except ValueError as e:
        print(f"   Validation error: {e}")
        print(f"   Skipping aspirate test")
    
    # Test dispense
    current_pos = pump.get_position(1)
    if current_pos > 0:
        print(f"\n3. Dispensing 100uL from {current_pos}uL...")
        target = pump.dispense(1, 100, speed_ul_s=50)
        time.sleep(3)
        final_pos = pump.get_position(1)
        print(f"   Target: {target}uL, Actual: {final_pos}uL")
        print(f"   SUCCESS! Moved {current_pos - final_pos}uL")
    
    # Test capacity validation
    print("\n4. Testing 1000uL capacity validation...")
    try:
        pump.validate_position(1200)
        print("   ERROR: Should have rejected 1200uL!")
    except ValueError as e:
        print(f"   PASS: {e}")
    
    try:
        pump.validate_position(500)
        print("   PASS: 500uL is valid")
    except ValueError as e:
        print(f"   ERROR: {e}")
    
    print("\n" + "="*60)
    print("PHASE 1 TEST COMPLETE!")
    print("="*60)
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
finally:
    pump.close()
