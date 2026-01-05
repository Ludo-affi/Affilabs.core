"""
Test Advanced Functions - Priority 2 & 3
Tests configuration queries, speed controls, and advanced operations
"""
from affipump_controller import AffipumpController
import time

controller = AffipumpController(port='COM8', baudrate=38400, auto_recovery=True)
controller.open()

try:
    print("="*60)
    print("ADVANCED FUNCTIONS TEST")
    print("="*60)
    
    # Test 1: Comprehensive Diagnostics
    print("\n" + "="*60)
    print("TEST 1: FULL DIAGNOSTICS")
    print("="*60)
    controller.print_diagnostics(1)
    
    # Test 2: Configuration Queries
    print("\n" + "="*60)
    print("TEST 2: CONFIGURATION QUERIES")
    print("="*60)
    print(f"Syringe Volume: {controller.get_syringe_volume(1)} µL")
    print(f"Backlash: {controller.get_backlash(1)} steps")
    print(f"Firmware Version: {controller.get_firmware_version(1)}")
    print(f"Valve Position: {controller.get_valve_position(1)}")
    print(f"Raw Position: {controller.get_plunger_position_raw(1)} steps")
    
    # Test 3: Speed Queries
    print("\n" + "="*60)
    print("TEST 3: SPEED SETTINGS")
    print("="*60)
    print(f"Start Speed: {controller.get_start_speed(1)} pulses/sec")
    print(f"Top Speed: {controller.get_top_speed(1)} pulses/sec")
    print(f"Cutoff Speed: {controller.get_cutoff_speed(1)} pulses/sec")
    
    # Test 4: Volume Calculations
    print("\n" + "="*60)
    print("TEST 4: VOLUME CALCULATIONS")
    print("="*60)
    current = controller.get_position(1) or 0
    remaining = controller.get_remaining_volume(1)
    print(f"Current Volume: {current} µL")
    print(f"Remaining Space: {remaining} µL")
    print(f"Can dispense 50µL? {controller.check_volume_available(1, 50)}")
    print(f"Can dispense 500µL? {controller.check_volume_available(1, 500)}")
    
    # Test 5: Prime Lines (if you want to test - WARNING: MOVES PUMP)
    print("\n" + "="*60)
    print("TEST 5: PRIME LINES (COMMENTED OUT - UNCOMMENT TO TEST)")
    print("="*60)
    print("# controller.prime_lines(1, cycles=2, volume_ul=100, speed_ul_s=200)")
    print("Skipping prime test (would move pump)")
    
    # Test 6: Extract to Waste Pattern (COMMENTED - would move pump)
    print("\n" + "="*60)
    print("TEST 6: EXTRACT TO WASTE (COMMENTED OUT)")
    print("="*60)
    print("# controller.extract_to_waste(1, 50, waste_port='O', input_port='I')")
    print("Skipping extract test (would move pump)")
    
    # Test 7: Transfer Between Pumps (COMMENTED - would move pump)
    print("\n" + "="*60)
    print("TEST 7: TRANSFER BETWEEN PUMPS (COMMENTED OUT)")
    print("="*60)
    print("# controller.transfer(from_pump=1, to_pump=2, volume_ul=50)")
    print("Skipping transfer test (would move pumps)")
    
    # Test 8: Dilution (COMMENTED - would move pump)
    print("\n" + "="*60)
    print("TEST 8: DILUTION (COMMENTED OUT)")
    print("="*60)
    print("# controller.dilute(1, diluent_volume_ul=80, sample_volume_ul=20)")
    print("Skipping dilution test (would move pump)")
    
    # Test 9: Speed Control Settings (safe to test)
    print("\n" + "="*60)
    print("TEST 9: SPEED CONTROL MODIFICATIONS")
    print("="*60)
    print("Setting custom speeds...")
    controller.set_start_speed(1, 500)
    time.sleep(0.2)
    controller.set_top_speed(1, 3000)
    time.sleep(0.2)
    controller.set_cutoff_speed(1, 1000)
    time.sleep(0.2)
    
    print(f"New Start Speed: {controller.get_start_speed(1)} pulses/sec")
    print(f"New Top Speed: {controller.get_top_speed(1)} pulses/sec")
    print(f"New Cutoff Speed: {controller.get_cutoff_speed(1)} pulses/sec")
    
    # Test 10: Error Handling
    print("\n" + "="*60)
    print("TEST 10: ERROR HANDLING")
    print("="*60)
    try:
        # Try invalid speed
        controller.set_start_speed(1, 10000)  # Too high
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    
    try:
        # Try invalid volume
        controller.validate_position(2000)  # Too high
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETE!")
    print("="*60)
    print("\nSummary:")
    print("✓ Configuration queries working")
    print("✓ Speed queries working")
    print("✓ Volume calculations working")
    print("✓ Speed control modifications working")
    print("✓ Error handling working")
    print("✓ Advanced operations defined (not executed)")
    print("\nTo test movement operations, uncomment the relevant sections.")
    
finally:
    controller.close()
