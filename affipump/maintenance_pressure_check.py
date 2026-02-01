#!/usr/bin/env python3
"""
Example: System pressure check for maintenance
"""
from affipump_controller import AffipumpController

def pressure_callback(step, volume, pressure, position):
    """Called after each increment"""
    print(f"  Step {step:3d}: {volume:6.1f}µL dispensed, Pressure: {pressure:4d}, Position: {position:6.1f}µL")

def main():
    print("="*70)
    print("System Pressure Check - Maintenance Mode")
    print("="*70)

    controller = AffipumpController()
    controller.open()

    try:
        # Initialize
        controller.initialize_pump(1)

        # Aspirate test volume
        print("\n1. Loading 500µL...")
        controller.aspirate(1, 500)

        print("\n2. Connect system and press ENTER to test pressure...")
        input()

        # Dispense with pressure monitoring
        print("\n3. Dispensing with pressure monitoring:")
        print("   (20µL steps, monitoring pressure between each step)")
        print()

        result = controller.dispense_with_pressure_monitoring(
            pump_num=1,
            volume_ul=300,
            step_size_ul=20,    # 20µL increments
            speed_ul_s=30,      # Slow speed
            max_pressure=850,   # Stop if pressure > 850
            callback=pressure_callback
        )

        # Analysis
        print("\n" + "="*70)
        print("RESULTS:")
        print(f"  Volume dispensed: {result['volume_dispensed']}µL")
        print(f"  Max pressure: {result['max_pressure_reached']}")
        print(f"  Stopped early: {result['stopped_early']}")

        if result['stopped_early']:
            print("\n  ⚠ WARNING: Pressure limit exceeded - check for blockage!")
        elif result['max_pressure_reached'] == 0:
            print("\n  ℹ INFO: No pressure sensor detected")
        else:
            print(f"\n  ✓ System pressure normal (max: {result['max_pressure_reached']})")

        print("="*70)

    finally:
        controller.close()

if __name__ == "__main__":
    main()
