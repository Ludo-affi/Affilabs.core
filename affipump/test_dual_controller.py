#!/usr/bin/env python3
"""
Test dual pump operations with AffiPump controller
"""
from affipump_controller import AffipumpController

def main():
    print("="*60)
    print("Dual Pump Test - AffiPump Controller")
    print("="*60)

    controller = AffipumpController(port='COM8', baudrate=38400, syringe_volume_ul=1000)
    controller.open()

    try:
        # Initialize both pumps
        print("\n1. Initialize both pumps")
        controller.initialize_pumps()
        positions = controller.get_both_positions()
        print(f"   Pump 1: {positions['pump1']}µL")
        print(f"   Pump 2: {positions['pump2']}µL")

        # Individual operations
        print("\n2. Individual aspirate operations")
        print("   Pump 1: Aspirate 250µL")
        controller.aspirate(1, 250)
        print("   Pump 2: Aspirate 400µL")
        controller.aspirate(2, 400)

        positions = controller.get_both_positions()
        print(f"   Pump 1: {positions['pump1']}µL (should be 250)")
        print(f"   Pump 2: {positions['pump2']}µL (should be 400)")

        # Synchronized dispense
        print("\n3. Synchronized dispense (both pumps: 100µL)")
        controller.dispense_both(100)

        positions = controller.get_both_positions()
        print(f"   Pump 1: {positions['pump1']}µL (should be 150)")
        print(f"   Pump 2: {positions['pump2']}µL (should be 300)")

        # Synchronized aspirate
        print("\n4. Synchronized aspirate (both pumps: 200µL)")
        controller.aspirate_both(200)

        positions = controller.get_both_positions()
        print(f"   Pump 1: {positions['pump1']}µL (should be 350)")
        print(f"   Pump 2: {positions['pump2']}µL (should be 500)")

        # Return both to zero
        print("\n5. Return both pumps to zero")
        controller.move_to_position(1, 0)
        controller.move_to_position(2, 0)

        positions = controller.get_both_positions()
        print(f"   Pump 1: {positions['pump1']}µL")
        print(f"   Pump 2: {positions['pump2']}µL")

        print("\n" + "="*60)
        print("DUAL PUMP TEST COMPLETE!")
        print("="*60)

    finally:
        controller.close()

if __name__ == "__main__":
    main()
