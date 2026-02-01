"""Set pump to MAXIMUM speed and measure actual performance.

No incremental moves, no polling during motion - just set max speed,
do one big move, and measure the result.
"""

import time
from affipump_controller import AffipumpController

PORT = "COM8"
BAUD = 38400
PUMP_NUM = 1

# Set MAXIMUM top speed
MAX_TOP_SPEED = 48000  # Try very high
START_SPEED = 1000
CUTOFF_SPEED = 2700
SLOPE = 20

# Big move to minimize accel/decel impact
BIG_MOVE_STEPS = 180000


def main():
    ctrl = AffipumpController(port=PORT, baudrate=BAUD)
    ctrl.open()

    try:
        print("Initializing...", flush=True)
        ctrl.terminate_move(PUMP_NUM)
        time.sleep(0.5)
        ctrl.initialize_pump(PUMP_NUM)
        time.sleep(10.0)

        print("\nSetting MAXIMUM speed profile:", flush=True)
        print(f"  Start:  {START_SPEED} pps")
        print(f"  Top:    {MAX_TOP_SPEED} pps")
        print(f"  Cutoff: {CUTOFF_SPEED} pps")
        print(f"  Slope:  {SLOPE}")

        ctrl.set_slope(PUMP_NUM, SLOPE)
        ctrl.set_start_speed(PUMP_NUM, START_SPEED)
        ctrl.set_cutoff_speed(PUMP_NUM, CUTOFF_SPEED)
        ctrl.set_top_speed(PUMP_NUM, MAX_TOP_SPEED)
        time.sleep(0.5)

        # Read back
        top_actual = ctrl.get_top_speed(PUMP_NUM)
        start_actual = ctrl.get_start_speed(PUMP_NUM)
        cutoff_actual = ctrl.get_cutoff_speed(PUMP_NUM)
        print("\nSpeed config read back:")
        print(f"  Start:  {start_actual}")
        print(f"  Top:    {top_actual}")
        print(f"  Cutoff: {cutoff_actual}")

        ctrl.set_valve_input(PUMP_NUM)
        time.sleep(0.3)

        pos0 = ctrl.get_plunger_position_raw(PUMP_NUM)
        print(f"\nStarting position: {pos0} steps")
        print(f"Commanding {BIG_MOVE_STEPS} step move...")
        print("(Not polling during move - waiting for completion)", flush=True)

        t0 = time.perf_counter()
        ctrl.send_command(f"/{PUMP_NUM}P{BIG_MOVE_STEPS}R")

        # Wait for idle WITHOUT polling every 0.1s (reduces overhead)
        time.sleep(2.0)  # Let it get going
        while True:
            st = ctrl.get_status(PUMP_NUM)
            if st and st.get('idle'):
                break
            time.sleep(1.0)  # Poll less frequently

        t1 = time.perf_counter()

        pos1 = ctrl.get_plunger_position_raw(PUMP_NUM)

        moved = pos1 - pos0
        elapsed = t1 - t0
        pps = abs(moved) / elapsed

        print("\nRESULTS:")
        print(f"  Moved:   {moved} steps")
        print(f"  Time:    {elapsed:.3f} s")
        print(f"  Speed:   {pps:.0f} pulses/sec")
        print("\n  For 1 mL syringe (181.49 steps/µL):")
        print(f"    {pps/181.49:.1f} µL/s = {pps/181.49*60:.0f} µL/min")

    finally:
        ctrl.terminate_move(PUMP_NUM)
        ctrl.close()


if __name__ == "__main__":
    main()
