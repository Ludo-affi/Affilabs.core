"""
Improved Pump Speed Test - Using Old Software Format

Based on findings from old working software:
- V{mL_per_min:.3f},1R - sets flow rate in mL/min
- V{pulses_per_sec}R - sets top speed limit
- Both commands used together for best results

Target: 15,000 µL/min aspirate, 500 µL/min dispense
"""
import time
from affipump_controller import AffipumpController

def main():
    print("="*70)
    print("IMPROVED SPEED TEST - Using Old Software Format")
    print("="*70)

    pump = AffipumpController(port='COM8', baudrate=38400)

    try:
        pump.open()

        # Cancel any pending moves
        print("\n[1/6] Clearing any pending commands...")
        pump.terminate_move(1)
        time.sleep(0.5)

        # Initialize pump
        print("\n[2/6] Initializing pump...")
        pump.initialize_pump(1)
        print("     Initialization complete")
        time.sleep(1)

        # Verify at zero
        pos = pump.get_position(1)
        print(f"\n[3/6] Current position: {pos} µL (should be 0)")

        # Test 1: ASPIRATE at 15,000 µL/min (250 µL/s)
        print("\n" + "="*70)
        print("[4/6] TEST 1: ASPIRATE 1000 µL @ 15,000 µL/min")
        print("="*70)

        aspirate_speed_ul_s = 15000 / 60  # 250 µL/s
        aspirate_ml_min = 15.0  # 15 mL/min
        expected_time = 1000 / aspirate_speed_ul_s

        print(f"     Target: 15,000 µL/min = {aspirate_speed_ul_s:.1f} µL/s = {aspirate_ml_min} mL/min")
        print(f"     Expected time: {expected_time:.1f} seconds")
        print(f"     Command format: V{aspirate_ml_min:.3f},1R + V9000R")

        start_time = time.time()

        # Use high top speed for aspirate
        pump.aspirate(1, 1000, speed_ul_s=aspirate_speed_ul_s, top_speed_pps=9000)

        # Wait for completion with periodic position checks
        print("\n     Progress:", end=" ", flush=True)
        last_pos = 0
        while True:
            time.sleep(0.5)
            pos = pump.get_position(1)
            if pos is None:
                continue

            # Show progress
            if pos != last_pos:
                print(f"{pos:.0f}µL", end=" ", flush=True)
                last_pos = pos

            # Check if complete (within 10 µL of target)
            if pos >= 990:
                break

            # Timeout after 30 seconds
            if time.time() - start_time > 30:
                print("\n     TIMEOUT!")
                break

        aspirate_time = time.time() - start_time
        final_pos = pump.get_position(1)
        actual_rate_ul_min = (final_pos / aspirate_time) * 60

        print("\n\n     RESULTS:")
        print(f"     Final position: {final_pos:.1f} µL")
        print(f"     Actual time: {aspirate_time:.2f} seconds")
        print(f"     Actual rate: {actual_rate_ul_min:.0f} µL/min")
        print("     Target rate: 15,000 µL/min")
        print(f"     Accuracy: {(actual_rate_ul_min/15000)*100:.1f}%")

        time.sleep(2)

        # Test 2: DISPENSE at 500 µL/min (8.33 µL/s) - 2 minute target
        print("\n" + "="*70)
        print("[5/6] TEST 2: DISPENSE 1000 µL @ 500 µL/min (2 minutes)")
        print("="*70)

        dispense_speed_ul_s = 500 / 60  # 8.33 µL/s
        dispense_ml_min = 0.5  # 0.5 mL/min
        expected_time = 1000 / dispense_speed_ul_s

        print(f"     Target: 500 µL/min = {dispense_speed_ul_s:.2f} µL/s = {dispense_ml_min} mL/min")
        print(f"     Expected time: {expected_time:.1f} seconds = {expected_time/60:.1f} minutes")
        print(f"     Command format: V{dispense_ml_min:.3f},1R + V9000R")

        start_time = time.time()

        # Use moderate top speed for dispense
        pump.dispense(1, 1000, speed_ul_s=dispense_speed_ul_s, top_speed_pps=6000)

        # Monitor with countdown
        print("\n     Dispensing (countdown):", end=" ", flush=True)
        last_report = 0
        while True:
            elapsed = time.time() - start_time
            remaining = expected_time - elapsed

            # Report every 10 seconds
            if int(elapsed) % 10 == 0 and int(elapsed) != last_report:
                pos = pump.get_position(1)
                if pos is not None:
                    print(f"\n     {remaining:.0f}s remaining, {pos:.0f}µL left", end=" ", flush=True)
                    last_report = int(elapsed)

            time.sleep(1)

            # Check position
            pos = pump.get_position(1)
            if pos is not None and pos <= 10:
                break

            # Timeout after 150 seconds (2.5 minutes)
            if elapsed > 150:
                print("\n     TIMEOUT!")
                break

        dispense_time = time.time() - start_time
        final_pos = pump.get_position(1)
        volume_dispensed = 1000 - final_pos
        actual_rate_ul_min = (volume_dispensed / dispense_time) * 60

        print("\n\n     RESULTS:")
        print(f"     Final position: {final_pos:.1f} µL")
        print(f"     Volume dispensed: {volume_dispensed:.1f} µL")
        print(f"     Actual time: {dispense_time:.2f} seconds = {dispense_time/60:.2f} minutes")
        print(f"     Actual rate: {actual_rate_ul_min:.0f} µL/min")
        print("     Target rate: 500 µL/min")
        print("     Target time: 120 seconds (2 minutes)")
        print(f"     Accuracy: {(actual_rate_ul_min/500)*100:.1f}%")

        # Summary
        print("\n" + "="*70)
        print("[6/6] TEST SUMMARY")
        print("="*70)
        print(f"Aspirate:  {actual_rate_ul_min:.0f} µL/min (target: 15,000 µL/min)")
        print(f"Dispense:  {actual_rate_ul_min:.0f} µL/min (target: 500 µL/min)")
        print("\nController improvements:")
        print("✓ Using V{mL/min},1R format (not code-based)")
        print("✓ Setting top speed with V{pps}R")
        print("✓ 0.1s delay between commands")
        print("✓ Separate valve, flow rate, and move commands")
        print("="*70)

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Stop pump
        try:
            pump.terminate_move(1)
        except:
            pass
        pump.close()
        print("\nPump closed")

if __name__ == "__main__":
    main()
