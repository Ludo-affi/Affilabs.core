"""Test different approaches for Step 4: Aspirate 50µL from P950 to P1000."""

import time
from affipump.affipump_controller import AffipumpController

def print_positions(pump):
    """Print current pump positions."""
    pos1 = pump.get_plunger_position(1) or 0.0
    pos2 = pump.get_plunger_position(2) or 0.0
    print(f"  P1: {pos1:.1f} uL | P2: {pos2:.1f} uL")

def test_step4_approaches():
    """Test different commands to aspirate 50µL from P950 to P1000."""

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

    # Aspirate to P950 (setup for Step 4)
    print("\n[SETUP] Aspirating to P950...")
    pump.aspirate_both_to_position(950, 400)  # Fast aspirate
    pump.wait_until_both_ready(30.0)
    print("✓ At P950")
    print_positions(pump)

    input("\n=== Ready to test Step 4 approaches. Press ENTER to continue ===\n")

    # APPROACH 1: Using aspirate_both_to_position (current approach)
    print("\n" + "="*60)
    print("APPROACH 1: aspirate_both_to_position(1000)")
    print("="*60)
    print("This should:")
    print("  1. Switch valves to INPUT")
    print("  2. Set velocity to 900 µL/min")
    print("  3. Move to absolute position P1000")
    input("Press ENTER to try...")

    pump.aspirate_both_to_position(1000, 900/60.0)
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P950
    print("\n[RESET] Dispensing back to P950...")
    pump.send_command("/1OR")
    time.sleep(0.1)
    pump.send_command("/2OR")
    time.sleep(1.0)
    pump.dispense_both(50.0, 15.0, switch_valve=False)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 2...")

    # APPROACH 2: Manual /AP command with INPUT valve
    print("\n" + "="*60)
    print("APPROACH 2: Manual /AP command (INPUT valve)")
    print("="*60)
    print("Commands:")
    print("  /1IR - Set pump 1 valve to INPUT")
    print("  /2IR - Set pump 2 valve to INPUT")
    print("  /AV15.000,1R - Set velocity to 900 µL/min")
    print("  /AP181490R - Move to P1000 (181490 steps)")
    input("Press ENTER to try...")

    pump.send_command("/1IR")
    time.sleep(0.3)
    pump.send_command("/2IR")
    time.sleep(0.3)
    pump.send_command("/AV15.000,1R")
    time.sleep(0.1)
    target_steps = int(1000 * pump.ul_to_steps)
    pump.send_command(f"/AP{target_steps}R")
    print(f"  Sent: /AP{target_steps}R")
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P950
    print("\n[RESET] Dispensing back to P950...")
    pump.send_command("/1OR")
    time.sleep(0.1)
    pump.send_command("/2OR")
    time.sleep(1.0)
    pump.dispense_both(50.0, 15.0, switch_valve=False)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 3...")

    # APPROACH 3: Relative aspirate (50 µL)
    print("\n" + "="*60)
    print("APPROACH 3: Relative aspirate (50 µL)")
    print("="*60)
    print("Commands:")
    print("  /1IR, /2IR - Set valves to INPUT")
    print("  /AV15.000,1R - Set velocity")
    print("  /AA50.000,1R - Aspirate 50 µL (relative)")
    input("Press ENTER to try...")

    pump.send_command("/1IR")
    time.sleep(0.3)
    pump.send_command("/2IR")
    time.sleep(0.3)
    pump.send_command("/AV15.000,1R")
    time.sleep(0.1)
    pump.send_command("/AA50.000,1R")
    print("  Sent: /AA50.000,1R")
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P950
    print("\n[RESET] Dispensing back to P950...")
    pump.send_command("/1OR")
    time.sleep(0.1)
    pump.send_command("/2OR")
    time.sleep(1.0)
    pump.dispense_both(50.0, 15.0, switch_valve=False)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 4...")

    # APPROACH 4: Using aspirate_both (if it exists)
    print("\n" + "="*60)
    print("APPROACH 4: Check for aspirate_both method")
    print("="*60)
    if hasattr(pump, 'aspirate_both'):
        print("aspirate_both method exists!")
        print("Trying: aspirate_both(50, 15.0)")
        input("Press ENTER to try...")
        pump.aspirate_both(50.0, 900/60.0)
        pump.wait_until_both_ready(30.0)
        print("Result:")
        print_positions(pump)
    else:
        print("aspirate_both method does NOT exist")
        print("Only aspirate_both_to_position is available")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("Which approach worked best?")

if __name__ == "__main__":
    try:
        test_step4_approaches()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
