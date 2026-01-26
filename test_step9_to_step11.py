"""Test transition between Step 9 (30µL spike @ 250 µL/min) and Step 11 (slow dispense @ 100 µL/min)."""

import time
from affipump.affipump_controller import AffipumpController

def print_positions(pump):
    """Print current pump positions."""
    pos1 = pump.get_plunger_position(1) or 0.0
    pos2 = pump.get_plunger_position(2) or 0.0
    print(f"  P1: {pos1:.1f} uL | P2: {pos2:.1f} uL")

def test_step9_to_step11_transition():
    """Test the transition from spike dispense to slow assay flow rate dispense."""
    
    # Initialize pump
    print("Initializing pump...")
    pump = AffipumpController()
    
    try:
        pump.open()
        print("✓ Pump connected\n")
    except Exception as e:
        print(f"ERROR: Failed to connect to pump: {e}")
        return
    
    # Home pumps
    print("Homing pumps...")
    pump.send_command("/1IR")
    time.sleep(0.1)
    pump.send_command("/2IR")
    time.sleep(1.0)
    pump.send_command("/1ZR")
    time.sleep(0.1)
    pump.send_command("/2ZR")
    time.sleep(0.5)
    pump.wait_until_both_ready(60.0)
    print("✓ Pumps homed")
    print_positions(pump)
    
    # Setup: Aspirate to P975 (simulating end of Step 6)
    print("\n[SETUP] Aspirating to P975...")
    pump.aspirate_both_to_position(975, 400)  # Fast aspirate
    pump.wait_until_both_ready(30.0)
    print("✓ At P975 (ready for Step 9)")
    print_positions(pump)
    
    input("\n=== Ready to test Step 9 → Step 11 transition. Press ENTER ===\n")
    
    # STEP 9: Dispense 30µL spike at 250 µL/min
    print("\n" + "="*60)
    print("STEP 9: Dispense 30µL spike at 250 µL/min")
    print("="*60)
    print("Using: dispense_both(30, 250/60)")
    input("Press ENTER to start Step 9...")
    
    start_time = time.time()
    pump.dispense_both(30.0, 250/60.0, switch_valve=True)
    pump.wait_until_both_ready(30.0)
    step9_duration = time.time() - start_time
    
    print(f"\n✓ Step 9 complete in {step9_duration:.1f}s")
    print_positions(pump)
    
    # Brief pause (simulating Step 10 - closing 3-way valves)
    print("\n[Simulating Step 10] Pausing 1 second...")
    time.sleep(1.0)
    
    # Check pump status before Step 11
    print("\n[Checking pump status before Step 11]")
    status1 = pump.get_status(1)
    status2 = pump.get_status(2)
    print(f"  Pump 1 busy: {status1.get('busy', 'unknown') if status1 else 'N/A'}")
    print(f"  Pump 2 busy: {status2.get('busy', 'unknown') if status2 else 'N/A'}")
    
    input("\nPress ENTER to start Step 11...")
    
    # STEP 11: Dispense remaining 945µL at 100 µL/min (assay flow rate)
    print("\n" + "="*60)
    print("STEP 11: Dispense to P0 at 100 µL/min - Debug approaches")
    print("="*60)
    
    assay_flow_rate_ul_s = 100.0 / 60.0  # 1.667 µL/s
    
    # Debug: Check current state
    print("\n[DEBUG] Checking pump state...")
    status1 = pump.get_status(1)
    status2 = pump.get_status(2)
    print(f"  Pump 1: {status1}")
    print(f"  Pump 2: {status2}")
    
    # Test Approach 1: Individual pump commands (not broadcast)
    print("\n--- Approach 1: Individual pump commands (P1 then P2) ---")
    input("Press ENTER to try individual commands...")
    
    # Pump 1
    pump.send_command("/1OR")  # Set valve to OUTPUT
    time.sleep(0.1)
    pump.send_command(f"/1V{assay_flow_rate_ul_s:.3f}R")  # Set velocity for pump 1
    time.sleep(0.1)
    pump.send_command("/1A0R")  # Move pump 1 to position 0
    time.sleep(0.5)
    
    # Pump 2
    pump.send_command("/2OR")  # Set valve to OUTPUT
    time.sleep(0.1)
    pump.send_command(f"/2V{assay_flow_rate_ul_s:.3f}R")  # Set velocity for pump 2
    time.sleep(0.1)
    pump.send_command("/2A0R")  # Move pump 2 to position 0
    
    print(f"\n✓ Step 11 started: dispensing to P0 at {assay_flow_rate_ul_s:.3f} uL/s")
    print("\nMonitoring positions for 30 seconds...")
    
    # Monitor positions during dispense
    start_monitor = time.time()
    last_check = 0
    
    for i in range(30):
        time.sleep(1)
        elapsed = time.time() - start_monitor
        
        pos1 = pump.get_plunger_position(1) or 0.0
        pos2 = pump.get_plunger_position(2) or 0.0
        avg_pos = (pos1 + pos2) / 2.0
        
        # Calculate expected position (should be decreasing)
        # Expected: P945 - (elapsed * 1.667 µL/s)
        expected_pos = 945 - (elapsed * assay_flow_rate_ul_s)
        
        print(f"  [{i+1:2d}s] P1={pos1:6.1f} uL | P2={pos2:6.1f} uL | Expected={expected_pos:6.1f} uL")
        
        # Check if pumps have stopped moving
        if i > 0 and abs(avg_pos - last_check) < 0.5:
            print(f"\n⚠ Pumps appear to have stopped moving!")
            break
        
        last_check = avg_pos
    
    print("\n" + "="*60)
    print("Monitor complete - you can Ctrl+C to stop")
    print("="*60)
    
    # Final wait
    input("\nPress ENTER to wait for full completion (or Ctrl+C to stop)...")
    pump.wait_until_both_ready(600.0)
    
    print("\n✓ Dispense to P0 complete")
    print_positions(pump)

if __name__ == "__main__":
    try:
        test_step9_to_step11_transition()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
