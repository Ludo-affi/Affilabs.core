"""Test different approaches for Step 6: Dispense 25µL from P1000 to P975."""

import time
from affipump.affipump_controller import AffipumpController

def print_positions(pump):
    """Print current pump positions."""
    pos1 = pump.get_plunger_position(1) or 0.0
    pos2 = pump.get_plunger_position(2) or 0.0
    print(f"  P1: {pos1:.1f} uL | P2: {pos2:.1f} uL")

def test_step6_approaches():
    """Test different commands to dispense 25µL from P1000 to P975."""

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

    # Aspirate to P1000 (setup for Step 6)
    print("\n[SETUP] Aspirating to P1000...")
    pump.aspirate_both_to_position(1000, 400)  # Fast aspirate
    pump.wait_until_both_ready(30.0)
    print("✓ At P1000")
    print_positions(pump)

    input("\n=== Ready to test Step 6 approaches. Press ENTER to continue ===\n")

    # APPROACH 1: Using dispense_both_to_position
    print("\n" + "="*60)
    print("APPROACH 1: dispense_both_to_position(975)")
    print("="*60)
    print("This should:")
    print("  1. Switch valves to OUTPUT")
    print("  2. Set velocity to 250 µL/min")
    print("  3. Move to absolute position P975")
    input("Press ENTER to try...")

    pump.dispense_both_to_position(975, 250/60.0, switch_valve=True)
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P1000
    print("\n[RESET] Going back to P1000...")
    pump.aspirate_both_to_position(1000, 400)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 2...")

    # APPROACH 2: Manual /AP command with OUTPUT valve
    print("\n" + "="*60)
    print("APPROACH 2: Manual /AP command (OUTPUT valve)")
    print("="*60)
    print("Commands:")
    print("  /1OR - Set pump 1 valve to OUTPUT")
    print("  /2OR - Set pump 2 valve to OUTPUT")
    print("  /AV4.167,1R - Set velocity to 250 µL/min")
    print("  /AP176956R - Move to P975 (176956 steps)")
    input("Press ENTER to try...")

    pump.send_command("/1OR")
    time.sleep(0.3)
    pump.send_command("/2OR")
    time.sleep(0.3)
    pump.send_command("/AV4.167,1R")
    time.sleep(0.1)
    target_steps = int(975 * pump.ul_to_steps)
    pump.send_command(f"/AP{target_steps}R")
    print(f"  Sent: /AP{target_steps}R")
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P1000
    print("\n[RESET] Going back to P1000...")
    pump.aspirate_both_to_position(1000, 400)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 3...")

    # APPROACH 3: Relative dispense (25 µL)
    print("\n" + "="*60)
    print("APPROACH 3: Relative dispense (25 µL)")
    print("="*60)
    print("Commands:")
    print("  /1OR, /2OR - Set valves to OUTPUT")
    print("  /AV4.167,1R - Set velocity")
    print("  /AD25.000,1R - Dispense 25 µL (relative)")
    input("Press ENTER to try...")

    pump.send_command("/1OR")
    time.sleep(0.3)
    pump.send_command("/2OR")
    time.sleep(0.3)
    pump.send_command("/AV4.167,1R")
    time.sleep(0.1)
    pump.send_command("/AD25.000,1R")
    print("  Sent: /AD25.000,1R")
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    # Reset to P1000
    print("\n[RESET] Going back to P1000...")
    pump.aspirate_both_to_position(1000, 400)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("\nPress ENTER for Approach 4...")

    # APPROACH 4: Using dispense_both (existing function)
    print("\n" + "="*60)
    print("APPROACH 4: dispense_both(25, 4.167, switch_valve=True)")
    print("="*60)
    print("This uses the existing dispense_both method")
    input("Press ENTER to try...")

    pump.dispense_both(25.0, 250/60.0, switch_valve=True)
    pump.wait_until_both_ready(30.0)
    print("Result:")
    print_positions(pump)

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("Which approach worked best?")

if __name__ == "__main__":
    try:
        test_step6_approaches()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
