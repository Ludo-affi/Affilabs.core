#!/usr/bin/env python3
"""
Test pressure sensor by creating back pressure
"""
from affipump_controller import AffipumpController
import time

def main():
    print("="*60)
    print("Pressure Sensor Test - Block Outlet")
    print("="*60)
    
    controller = AffipumpController()
    controller.open()
    
    try:
        # Initialize and aspirate some liquid
        print("\n1. Initializing pump 1...")
        controller.initialize_pump(1)
        
        print("\n2. Aspirating 500µL...")
        controller.aspirate(1, 500, speed_ul_s=200)
        pos = controller.get_position(1)
        print(f"   Position: {pos}µL")
        
        print("\n" + "="*60)
        print("READY FOR TEST")
        print("="*60)
        input("\n>>> BLOCK THE OUTLET NOW, then press ENTER to continue...")
        
        # Check pressure before dispense
        print("\n3. Pressure before dispense:")
        pressure = controller.get_pressure(1)
        print(f"   Pressure: {pressure}")
        
        # Try to dispense with blocked outlet (slow speed for safety)
        print("\n4. Attempting to dispense 100µL with blocked outlet...")
        print("   (Monitoring pressure every 0.2s)")
        
        # Switch to output valve
        controller.send_command("/1OR", wait_time=0.3)
        controller.send_command("/1V50,1R", wait_time=0.2)
        
        # Start dispense
        steps = int(100 * controller.ul_to_steps)
        controller.send_command(f"/1D{steps}R", wait_time=0.1)
        
        # Monitor pressure during operation
        for i in range(15):  # Monitor for 3 seconds
            time.sleep(0.2)
            pressure = controller.get_pressure(1)
            pos = controller.get_position(1)
            print(f"   t={i*0.2:.1f}s - Pressure: {pressure:4d}, Position: {pos:.1f}µL")
            
            if pressure and pressure > 100:  # If we see significant pressure
                print(f"\n   *** PRESSURE DETECTED: {pressure} ***")
        
        # Final readings
        time.sleep(1)
        print("\n5. Final readings:")
        pressure = controller.get_pressure(1)
        pos = controller.get_position(1)
        limit = controller.get_pressure_limit(1)
        print(f"   Pressure: {pressure}")
        print(f"   Position: {pos}µL")
        print(f"   Pressure limit: {limit}")
        
        # Stop pump
        controller.stop_pump(1)
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("If pressure stayed at 0, sensor may not be installed.")
        print("If pressure increased, sensor is working!")
        print("="*60)
        
    finally:
        controller.close()

if __name__ == "__main__":
    main()
