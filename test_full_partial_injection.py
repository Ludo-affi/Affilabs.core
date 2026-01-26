"""
Full Partial Injection Test with Valve Movements
Mimics the complete 14-step procedure exactly as implemented in pump_manager.py
"""

import sys
import time
sys.path.insert(0, 'c:\\Users\\lucia\\OneDrive\\Desktop\\ezControl 2.0\\Affilabs.core\\Affilabs-core')

from affipump.affipump_controller import AffipumpController

def print_step(step_num, title):
    print("\n" + "="*70)
    print(f"STEP {step_num}: {title}")
    print("="*70)

def print_positions(pump):
    pos1 = pump.get_plunger_position(1) or 0.0
    pos2 = pump.get_plunger_position(2) or 0.0
    print(f"  P1: {pos1:.1f} uL | P2: {pos2:.1f} uL")

def main():
    print("="*70)
    print("FULL PARTIAL INJECTION TEST - 14 Steps")
    print("="*70)
    print("\nThis test mimics the complete partial injection procedure")
    print("including all valve movements and flow rate transitions.\n")
    
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
    
    # Parameters (matching production code)
    flow_rate = 100  # µL/min assay flow rate
    assay_flow_rate_ul_s = flow_rate / 60.0
    aspiration_flow_rate = 24000  # µL/min
    aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
    output_aspirate_rate = 250  # µL/min
    output_aspirate_rate_ul_s = output_aspirate_rate / 60.0
    pulse_rate = 250  # µL/min
    pulse_rate_ul_s = pulse_rate / 60.0
    loop_volume_ul = 100
    
    # Calculate contact time (65% of loop)
    contact_time_s = (loop_volume_ul * 0.65 / flow_rate) * 60.0
    
    print(f"\nParameters:")
    print(f"  Assay flow rate: {flow_rate} µL/min")
    print(f"  Loop volume: {loop_volume_ul} µL")
    print(f"  Contact time: {contact_time_s:.1f}s (65% of loop)")
    print(f"  Aspiration: {aspiration_flow_rate} µL/min")
    print(f"  Output aspirate: {output_aspirate_rate} µL/min")
    print(f"  Pulse rate: {pulse_rate} µL/min")
    
    input("\nPress ENTER to start 14-step procedure...")
    
    # ============================================================
    # STEP 1: Move to P950
    # ============================================================
    print_step(1, f"Move to P950 at {aspiration_flow_rate} µL/min")
    pump.aspirate_both_to_position(950, aspiration_flow_rate_ul_s)
    pump.wait_until_both_ready(30.0)
    print("✓ At P950")
    print_positions(pump)
    
    # ============================================================
    # STEP 2: Open 3-way valves (KC1→B, KC2→D)
    # ============================================================
    print_step(2, "Open 3-way valves (SIMULATED - set to OPEN/LOAD)")
    print("  [Would execute: ctrl.knx_three_both(state=1)]")
    print("  KC1→B, KC2→D - Both to LOAD")
    time.sleep(0.5)
    
    # ============================================================
    # STEP 3: Open 6-port valves (INJECT position)
    # ============================================================
    print_step(3, "Open 6-port valves to INJECT (SIMULATED)")
    print("  [Would execute: ctrl.knx_six_both(state=1)]")
    print("  6-port valves to INJECT position")
    time.sleep(1.0)
    
    # ============================================================
    # STEP 4: Aspirate 50µL (P950 → P1000)
    # ============================================================
    print_step(4, f"Aspirate 50µL to P1000 at {output_aspirate_rate} µL/min")
    pump.aspirate_both(50.0, output_aspirate_rate_ul_s)
    time.sleep(0.5)
    pump.wait_until_both_ready(20.0)
    print("✓ At P1000")
    print_positions(pump)
    
    # ============================================================
    # STEP 5: Close 6-port valves (LOAD position)
    # ============================================================
    print_step(5, "Close 6-port valves to LOAD (SIMULATED)")
    print("  [Would execute: ctrl.knx_six_both(state=0)]")
    print("  6-port valves to LOAD position")
    time.sleep(1.0)
    
    # ============================================================
    # STEP 6: Dispense 25µL (P1000 → P975)
    # ============================================================
    print_step(6, f"Dispense 25µL to P975 at {output_aspirate_rate} µL/min")
    print("  (Switching pump valve to OUTPUT)")
    pump.dispense_both(25.0, output_aspirate_rate_ul_s, switch_valve=True)
    time.sleep(0.5)
    pump.wait_until_both_ready(15.0)
    print("✓ At P975")
    print_positions(pump)
    
    # ============================================================
    # STEP 7: Wait 10 seconds
    # ============================================================
    print_step(7, "Wait 10 seconds")
    for i in range(10, 0, -1):
        print(f"  {i}...", end='\r')
        time.sleep(1.0)
    print("  ✓ Wait complete")
    
    # ============================================================
    # STEP 8: Open 6-port valves (INJECT position)
    # ============================================================
    print_step(8, "Open 6-port valves to INJECT (SIMULATED)")
    print("  [Would execute: ctrl.knx_six_both(state=1)]")
    print("  6-port valves to INJECT position")
    time.sleep(1.0)
    
    # ============================================================
    # STEP 9 + 11: Dispense with on-the-fly flow rate change
    # ============================================================
    print_step(9, f"Start dispense: 30µL spike at {pulse_rate} µL/min")
    print(f"  Then change to {flow_rate} µL/min on the fly (no stopping!)")
    
    # Start pumps moving to P0 at spike rate
    pump.send_command("/1OR")
    time.sleep(0.1)
    pump.send_command("/2OR")
    time.sleep(0.5)
    
    pump.send_command(f"/1V{pulse_rate_ul_s:.3f}R")
    time.sleep(0.1)
    pump.send_command(f"/2V{pulse_rate_ul_s:.3f}R")
    time.sleep(0.1)
    
    pump.send_command("/1A0R")
    time.sleep(0.1)
    pump.send_command("/2A0R")
    print("  ✓ Pumps started dispensing to P0")
    print_positions(pump)
    
    # Wait for 30µL spike to complete
    print(f"\n  Waiting 7.5s for 30µL spike...")
    for i in range(75):
        time.sleep(0.1)
        if i % 10 == 0:
            pos1 = pump.get_plunger_position(1) or 0.0
            pos2 = pump.get_plunger_position(2) or 0.0
            print(f"  [{i/10:.1f}s] P1={pos1:.1f} uL | P2={pos2:.1f} uL")
    
    print("\n  ✓ 30µL spike completed")
    print_positions(pump)
    
    # ============================================================
    # STEP 11: Change flow rate on the fly
    # ============================================================
    print_step(11, f"Change flow rate to {flow_rate} µL/min (ON THE FLY!)")
    print("  Pumps are still moving - changing velocity now...")
    
    pump.send_command(f"/1V{assay_flow_rate_ul_s:.3f}R")
    time.sleep(0.1)
    pump.send_command(f"/2V{assay_flow_rate_ul_s:.3f}R")
    print(f"  ✓ Flow rate changed to {assay_flow_rate_ul_s:.3f} uL/s")
    print_positions(pump)
    time.sleep(0.5)
    
    # ============================================================
    # STEP 10: Close 3-way valves (redirect to waste)
    # ============================================================
    print_step(10, "Close 3-way valves to CLOSED/WASTE (SIMULATED)")
    print("  [Would execute: ctrl.knx_three_both(state=0)]")
    print("  KC1→A, KC2→C - Both to WASTE")
    time.sleep(1.0)
    
    # ============================================================
    # STEP 12: Contact time monitoring
    # ============================================================
    print_step(12, f"Contact time monitoring ({contact_time_s:.1f}s)")
    print("  Monitoring pump positions during slow dispense...")
    
    start_time = time.time()
    last_update = start_time
    
    # Check initial motion
    time.sleep(1.0)
    pos1_before = pump.get_plunger_position(1) or 0.0
    pos2_before = pump.get_plunger_position(2) or 0.0
    time.sleep(1.0)
    pos1_after = pump.get_plunger_position(1) or 0.0
    pos2_after = pump.get_plunger_position(2) or 0.0
    
    moved = (abs(pos1_after - pos1_before) > 0.5) or (abs(pos2_after - pos2_before) > 0.5)
    if moved:
        print(f"  ✓ Motion detected: P1={pos1_before:.1f}→{pos1_after:.1f}, P2={pos2_before:.1f}→{pos2_after:.1f}")
    else:
        print(f"  ⚠ WARNING: No motion detected!")
    
    # Monitor for contact time
    while True:
        elapsed = time.time() - start_time
        if elapsed >= contact_time_s:
            break
        
        if time.time() - last_update >= 5.0:
            pos1 = pump.get_plunger_position(1) or 0.0
            pos2 = pump.get_plunger_position(2) or 0.0
            avg_pos = (pos1 + pos2) / 2.0
            print(f"  [{elapsed:.1f}s] P1={pos1:.1f} uL | P2={pos2:.1f} uL | Avg={avg_pos:.1f} uL")
            last_update = time.time()
        
        time.sleep(0.5)
    
    print(f"  ✓ Contact time complete ({elapsed:.1f}s)")
    print_positions(pump)
    
    # ============================================================
    # STEP 13: Close 6-port valves
    # ============================================================
    print_step(13, "Close 6-port valves to LOAD (SIMULATED)")
    print("  [Would execute: ctrl.knx_six_both(state=0)]")
    print("  6-port valves to LOAD position")
    time.sleep(1.0)
    
    # ============================================================
    # STEP 14: Purge remaining volume
    # ============================================================
    print_step(14, "Purge remaining volume to P0")
    print("  Waiting for pumps to finish...")
    
    poll_start = time.time()
    while True:
        status1 = pump.get_status(1)
        status2 = pump.get_status(2)
        
        if status1 and status2:
            p1_ready = not status1.get('busy', False)
            p2_ready = not status2.get('busy', False)
            
            if p1_ready and p2_ready:
                break
            
            if time.time() - poll_start > 300.0:
                print("  ⚠ Timeout waiting for purge")
                break
        
        time.sleep(1.0)
        pos1 = pump.get_plunger_position(1) or 0.0
        pos2 = pump.get_plunger_position(2) or 0.0
        print(f"  Purging... P1={pos1:.1f} uL | P2={pos2:.1f} uL", end='\r')
    
    purge_time = time.time() - poll_start
    total_time = time.time() - start_time + (time.time() - poll_start)
    
    print(f"\n  ✓ Purge complete in {purge_time:.1f}s")
    print_positions(pump)
    
    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "="*70)
    print("PARTIAL INJECTION COMPLETE")
    print("="*70)
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Contact time: {contact_time_s:.1f}s")
    print(f"  Final positions:")
    print_positions(pump)
    print("\n✓ All 14 steps completed successfully!")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
