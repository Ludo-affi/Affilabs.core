"""
3-Cycle Test: 0-1000 µL @ 500 µL/min
With automatic completion detection
"""
import time
from affipump_controller import AffipumpController

def main():
    print("="*70)
    print("3-CYCLE TEST: 0→1000→0 µL @ 500 µL/min")
    print("Auto-detecting completion (no polling overhead)")
    print("="*70)

    pump = AffipumpController(port='COM8', baudrate=38400)
    pump.open()

    try:
        # Initialize
        print("\nInitializing...")
        pump.terminate_move(1)
        time.sleep(0.5)
        pump.initialize_pump(1)
        print(f"At home: {pump.is_at_home(1)}")
        print(f"Position: {pump.get_position(1)} µL\n")

        # Run 3 cycles
        for cycle in range(1, 4):
            print(f"\n{'='*70}")
            print(f"CYCLE {cycle}/3")
            print(f"{'='*70}")

            # ASPIRATE 1000 µL @ 500 µL/min
            print(f"\n[{cycle}.1] Aspirating 1000 µL @ 500 µL/min...")

            start = time.time()
            pump.aspirate(1, 1000, speed_ul_s=500/60, wait=True)
            elapsed = time.time() - start

            pos = pump.get_position(1)
            at_full = pump.is_at_full(1)
            actual_rate = (1000 / elapsed) * 60

            print(f"      ✓ Complete in {elapsed:.1f}s ({elapsed/60:.2f} min)")
            print(f"      Position: {pos} µL")
            print(f"      At full (1000µL): {at_full}")
            print(f"      Rate: {actual_rate:.0f} µL/min")

            # DISPENSE 1000 µL @ 500 µL/min
            print(f"\n[{cycle}.2] Dispensing 1000 µL @ 500 µL/min...")

            start = time.time()
            pump.dispense(1, 1000, speed_ul_s=500/60, wait=True)
            elapsed = time.time() - start

            pos = pump.get_position(1)
            at_home = pump.is_at_home(1)
            actual_rate = (1000 / elapsed) * 60

            print(f"      ✓ Complete in {elapsed:.1f}s ({elapsed/60:.2f} min)")
            print(f"      Position: {pos} µL")
            print(f"      At home: {at_home}")
            print(f"      Rate: {actual_rate:.0f} µL/min")

        print(f"\n{'='*70}")
        print("✓ ALL 3 CYCLES COMPLETE")
        print(f"{'='*70}")

    finally:
        pump.terminate_move(1)
        pump.close()
        print("\nDone")

if __name__ == "__main__":
    main()
