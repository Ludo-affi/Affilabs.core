"""Test pump commands for partial injection in isolation."""

import time
from affipump.affipump_controller import AffipumpController

def print_positions(pump):
    """Print current pump positions."""
    pos1 = pump.get_plunger_position(1) or 0.0
    pos2 = pump.get_plunger_position(2) or 0.0
    print(f"  P1: {pos1:.1f} uL | P2: {pos2:.1f} uL")

def test_partial_injection_steps():
    """Test each step of partial injection."""

    # Initialize pump
    print("Initializing pump...")
    pump = AffipumpController()

    # Try to open connection
    try:
        pump.open()
        print("✓ Pump connected\n")
    except Exception as e:
        print(f"ERROR: Failed to connect to pump: {e}")
        return

    # Home and initialize pumps
    print("Homing and initializing pumps...")
    print("  Setting valve to INPUT (IR)...")
    pump.send_command("/1IR")
    time.sleep(0.1)
    pump.send_command("/2IR")
    time.sleep(1.0)

    print("  Initializing plunger positions (homing)...")
    pump.send_command("/1ZR")
    time.sleep(0.1)
    pump.send_command("/2ZR")
    time.sleep(0.5)

    print("  Waiting for initialization to complete...")
    pump.wait_until_both_ready(60.0)
    print("✓ Pumps homed to P0")
    print_positions(pump)

    # Flow rates
    aspiration_flow_rate = 24000  # uL/min
    aspiration_flow_rate_ul_s = aspiration_flow_rate / 60.0
    output_aspirate_rate = 250  # uL/min
    output_aspirate_rate_ul_s = output_aspirate_rate / 60.0
    pulse_rate = 250  # uL/min
    pulse_rate_ul_s = pulse_rate / 60.0
    assay_flow_rate = 100  # uL/min
    assay_flow_rate_ul_s = assay_flow_rate / 60.0

    input("Press ENTER to start test...")

    # STEP 1: Move to P950
    print("\n[STEP 1] Aspirating to ABSOLUTE POSITION P950...")
    print(f"  Rate: {aspiration_flow_rate} uL/min")
    pump.aspirate_both_to_position(950, aspiration_flow_rate_ul_s)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("Press ENTER for Step 6...")

    # STEP 6: Aspirate to P975 (with OUTPUT valve - this is the issue!)
    print("\n[STEP 6] Aspirating to ABSOLUTE POSITION P975...")
    print(f"  Rate: {output_aspirate_rate} uL/min")
    print("  NOTE: Using dispense_both_to_position (may need to use aspirate instead!)")
    pump.dispense_both_to_position(975, output_aspirate_rate_ul_s, switch_valve=True)
    pump.wait_until_both_ready(10.0)
    print_positions(pump)

    input("Press ENTER for Step 9...")

    # STEP 9: Dispense to P945 (30uL spike)
    print("\n[STEP 9] Dispensing to ABSOLUTE POSITION P945...")
    print(f"  Rate: {pulse_rate} uL/min")
    pump.dispense_both_to_position(945, pulse_rate_ul_s, switch_valve=True)
    pump.wait_until_both_ready(30.0)
    print_positions(pump)

    input("Press ENTER for Step 11...")

    # STEP 11: Dispense to P0
    print("\n[STEP 11] Dispensing to ABSOLUTE POSITION P0...")
    print(f"  Rate: {assay_flow_rate} uL/min")

    # Manual command version (what the code does)
    pump.send_command("/1OR")
    time.sleep(0.3)
    pump.send_command("/2OR")
    time.sleep(0.3)
    pump.send_command(f"/AV{assay_flow_rate_ul_s:.3f},1R")
    time.sleep(0.1)
    target_steps = int(0 * pump.ul_to_steps)
    pump.send_command(f"/AP{target_steps}R")
    print(f"  Command sent: /AP{target_steps}R at {assay_flow_rate_ul_s:.3f} uL/s")

    # Monitor positions for 10 seconds
    print("\n  Monitoring positions for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        print(f"  [{i+1}s]", end=" ")
        print_positions(pump)

    # Wait for completion
    print("\n  Waiting for completion...")
    pump.wait_until_both_ready(600.0)
    print_positions(pump)

    print("\n✓ Test complete!")

if __name__ == "__main__":
    try:
        test_partial_injection_steps()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
