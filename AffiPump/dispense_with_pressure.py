#!/usr/bin/env python3
"""
Incremental dispense with pressure monitoring
Move in small steps, checking pressure between each step
"""
from affipump_controller import AffipumpController
import time

def dispense_with_pressure_monitoring(controller, pump_num, total_volume_ul, 
                                     step_size_ul=10, speed_ul_s=50, 
                                     max_pressure=None):
    """
    Dispense volume in small increments, monitoring pressure after each step
    
    Args:
        controller: AffipumpController instance
        pump_num: Pump number (1 or 2)
        total_volume_ul: Total volume to dispense
        step_size_ul: Volume per increment (smaller = more pressure readings)
        speed_ul_s: Dispense speed
        max_pressure: Stop if pressure exceeds this value (None = no limit)
    
    Returns:
        dict with pressure_history, volume_dispensed, stopped_early
    """
    steps_ul_to_steps = controller.ul_to_steps
    pressure_history = []
    volume_dispensed = 0
    stopped_early = False
    
    print(f"\nStarting incremental dispense: {total_volume_ul}µL in {step_size_ul}µL steps")
    print(f"Target: {total_volume_ul}µL, Step size: {step_size_ul}µL, Speed: {speed_ul_s}µL/s")
    print(f"Max pressure: {max_pressure if max_pressure else 'None (monitoring only)'}\n")
    
    # Set valve to output
    controller.send_command(f"/{pump_num}OR", wait_time=0.3)
    controller.send_command(f"/{pump_num}V{speed_ul_s},1R", wait_time=0.2)
    
    # Calculate number of steps
    num_increments = int(total_volume_ul / step_size_ul)
    remaining = total_volume_ul % step_size_ul
    
    print(f"Step | Volume (µL) | Pressure | Position (µL) | Status")
    print("-" * 65)
    
    for i in range(num_increments):
        # Dispense one increment
        increment_steps = int(step_size_ul * steps_ul_to_steps)
        controller.send_command(f"/{pump_num}D{increment_steps}R", 
                              wait_time=(step_size_ul / speed_ul_s) + 0.5)
        
        # Wait a moment for movement to complete
        time.sleep(0.3)
        
        # Read pressure
        pressure = controller.get_pressure(pump_num)
        position = controller.get_position(pump_num)
        volume_dispensed += step_size_ul
        
        pressure_history.append({
            'step': i + 1,
            'volume_dispensed': volume_dispensed,
            'pressure': pressure,
            'position': position
        })
        
        status = "OK"
        if max_pressure and pressure and pressure > max_pressure:
            status = "PRESSURE LIMIT!"
            stopped_early = True
        
        print(f"{i+1:4d} | {volume_dispensed:11.1f} | {pressure:8d} | {position:13.1f} | {status}")
        
        if stopped_early:
            print(f"\n*** STOPPED: Pressure {pressure} exceeded limit {max_pressure} ***")
            break
    
    # Dispense remaining volume if any
    if remaining > 0 and not stopped_early:
        remaining_steps = int(remaining * steps_ul_to_steps)
        controller.send_command(f"/{pump_num}D{remaining_steps}R", 
                              wait_time=(remaining / speed_ul_s) + 0.5)
        time.sleep(0.3)
        
        pressure = controller.get_pressure(pump_num)
        position = controller.get_position(pump_num)
        volume_dispensed += remaining
        
        pressure_history.append({
            'step': num_increments + 1,
            'volume_dispensed': volume_dispensed,
            'pressure': pressure,
            'position': position
        })
        
        print(f"{num_increments+1:4d} | {volume_dispensed:11.1f} | {pressure:8d} | {position:13.1f} | OK (final)")
    
    print("-" * 65)
    
    return {
        'pressure_history': pressure_history,
        'volume_dispensed': volume_dispensed,
        'stopped_early': stopped_early
    }


def main():
    print("="*70)
    print("Incremental Dispense with Pressure Monitoring")
    print("="*70)
    
    controller = AffipumpController()
    controller.open()
    
    try:
        # Initialize and aspirate
        print("\n1. Initialize pump 1...")
        controller.initialize_pump(1)
        
        print("\n2. Aspirate 600µL...")
        controller.aspirate(1, 600)
        pos = controller.get_position(1)
        print(f"   Position: {pos}µL")
        
        input("\n>>> BLOCK THE OUTLET (or leave open), then press ENTER to start...\n")
        
        # Check initial pressure
        pressure_init = controller.get_pressure(1)
        limit = controller.get_pressure_limit(1)
        print(f"\nInitial pressure: {pressure_init}")
        print(f"Pressure limit: {limit}")
        
        # Dispense with pressure monitoring
        # Using 20µL steps = 30 measurements for 600µL
        result = dispense_with_pressure_monitoring(
            controller=controller,
            pump_num=1,
            total_volume_ul=400,
            step_size_ul=20,  # 20µL per step
            speed_ul_s=50,    # Moderate speed
            max_pressure=800  # Stop if pressure > 800 (below limit of 900)
        )
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Total volume dispensed: {result['volume_dispensed']:.1f}µL")
        print(f"Stopped early: {result['stopped_early']}")
        print(f"Pressure readings: {len(result['pressure_history'])} measurements")
        
        # Show pressure trend
        print("\nPressure trend:")
        for reading in result['pressure_history']:
            print(f"  {reading['volume_dispensed']:6.1f}µL -> Pressure: {reading['pressure']:4d}")
        
        # Check if pressure changed
        pressures = [r['pressure'] for r in result['pressure_history'] if r['pressure'] is not None]
        if pressures and max(pressures) > min(pressures):
            print(f"\n✓ Pressure sensor ACTIVE - Range: {min(pressures)} to {max(pressures)}")
        elif pressures and all(p == 0 for p in pressures):
            print(f"\n✗ Pressure sensor reads 0 throughout - likely no sensor installed")
        
        print("\n" + "="*70)
        
    finally:
        controller.close()


if __name__ == "__main__":
    main()
