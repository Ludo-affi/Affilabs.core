# -*- coding: utf-8 -*-
"""
Find step-to-uL conversion factor for 1000uL syringe
"""
import sys
sys.path.insert(0, r'C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\AffiPump')
from affipump_v2 import AffipumpController
import time

pump = AffipumpController(port='COM8', baudrate=38400)

try:
    pump.open()
    
    print("Finding step-to-uL conversion factor")
    print("="*60)
    
    # Initialize to zero
    print("\n1. Initialize (should go to zero)")
    pump.send_command("/1ZR", wait_time=5)
    time.sleep(3)
    zero_steps = pump.get_position(1)
    print(f"   Zero position: {zero_steps} steps")
    
    # Move to 500uL
    print("\n2. Move to 500uL")
    pump.send_command("/1V200,1R", wait_time=0.5)
    pump.send_command("/1A500R", wait_time=3)
    time.sleep(3)
    pos_500 = pump.get_position(1)
    print(f"   Position after A500: {pos_500} steps")
    
    # Move to 1000uL
    print("\n3. Move to 1000uL (full syringe)")
    pump.send_command("/1A1000R", wait_time=3)
    time.sleep(3)
    pos_1000 = pump.get_position(1)
    print(f"   Position after A1000: {pos_1000} steps")
    
    # Calculate conversion
    print("\n" + "="*60)
    print("CONVERSION FACTORS:")
    if pos_500 != zero_steps:
        factor_500 = 500 / (pos_500 - zero_steps)
        print(f"  500uL move: {pos_500 - zero_steps} steps = {factor_500:.4f} uL/step")
    
    if pos_1000 != zero_steps:
        factor_1000 = 1000 / (pos_1000 - zero_steps)
        print(f"  1000uL move: {pos_1000 - zero_steps} steps = {factor_1000:.4f} uL/step")
    
    # Move back to zero
    print("\n4. Move back to 0uL")
    pump.send_command("/1A0R", wait_time=3)
    time.sleep(3)
    back_to_zero = pump.get_position(1)
    print(f"   Position after A0: {back_to_zero} steps")
    
    print("\n" + "="*60)
    print("CONCLUSION:")
    print(f"  The '?' query returns STEPS, not uL")
    print(f"  Commands use uL directly (A500 = 500uL)")
    print(f"  Responses need conversion to uL")
    print("="*60)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    pump.close()
