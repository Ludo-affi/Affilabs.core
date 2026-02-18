"""Pump test: 1 mL aspirate then 1 mL dispense.

Requirements:
- Aspirate 1000 µL @ 15000 µL/min
- Dispense 1000 µL @ 500 µL/min (should take 2 minutes)
"""

import time
from affipump_controller import AffipumpController

PORT = "COM8"
BAUD = 38400
PUMP_NUM = 1

VOLUME_UL = 1000

ASPIRATE_UL_MIN = 15000
ASPIRATE_UL_S = ASPIRATE_UL_MIN / 60.0  # 250 µL/s

DISPENSE_UL_MIN = 500
DISPENSE_UL_S = DISPENSE_UL_MIN / 60.0  # 8.333.. µL/s

PRE_DISPENSE_UL_S = 50.0


def _sleep_with_progress(controller: AffipumpController, seconds: float, label: str) -> None:
    start = time.time()
    next_print = start
    while True:
        now = time.time()
        elapsed = now - start
        if elapsed >= seconds:
            break
        if now >= next_print:
            remaining = seconds - elapsed
            print(f"{label}: {elapsed:5.1f}s elapsed, {remaining:5.1f}s remaining", flush=True)
            next_print = now + 10.0
        time.sleep(0.2)


def main() -> None:
    controller = AffipumpController(port=PORT, baudrate=BAUD, auto_recovery=True)
    controller.open()

    try:
        try:
            controller.terminate_move(PUMP_NUM)
        except Exception:
            pass
        try:
            controller.clear_errors(PUMP_NUM)
        except Exception:
            pass

        print("\n" + "=" * 60)
        print("PUMP TEST: ASPIRATE 1 mL THEN DISPENSE 1 mL")
        print("=" * 60)
        print(f"Port: {PORT}  Pump: {PUMP_NUM}")
        print(f"Aspirate: {VOLUME_UL} µL @ {ASPIRATE_UL_MIN} µL/min ({ASPIRATE_UL_S:.1f} µL/s)")
        print(f"Dispense: {VOLUME_UL} µL @ {DISPENSE_UL_MIN} µL/min ({DISPENSE_UL_S:.2f} µL/s) => 120s")

        print("\nInitializing...", flush=True)
        controller.initialize_pump(PUMP_NUM)
        print(f"Position after init: {controller.get_position(PUMP_NUM)} µL", flush=True)

        print("\nPre-step: emptying syringe to waste (fast)...", flush=True)
        controller.set_valve_output(PUMP_NUM)
        time.sleep(0.3)
        controller.dispense(PUMP_NUM, VOLUME_UL, PRE_DISPENSE_UL_S)
        _sleep_with_progress(controller, (VOLUME_UL / PRE_DISPENSE_UL_S) + 2.0, "PRE-DISPENSE")
        print(f"Position after pre-dispense: {controller.get_position(PUMP_NUM)} µL", flush=True)

        print("\nSetting valve to reservoir (I) and aspirating 1 mL (fast)...", flush=True)
        controller.set_valve_input(PUMP_NUM)
        time.sleep(0.3)
        controller.aspirate(PUMP_NUM, VOLUME_UL, ASPIRATE_UL_S)
        aspirate_time_s = (VOLUME_UL / ASPIRATE_UL_S) + 1.0
        _sleep_with_progress(controller, aspirate_time_s, "ASPIRATE")
        print(f"Position after aspirate: {controller.get_position(PUMP_NUM)} µL", flush=True)

        print("\nSetting valve to output (O) and dispensing 1 mL (2 minutes)...", flush=True)
        controller.set_valve_output(PUMP_NUM)
        time.sleep(0.3)
        controller.dispense(PUMP_NUM, VOLUME_UL, DISPENSE_UL_S)
        dispense_time_s = (VOLUME_UL / DISPENSE_UL_S) + 1.0
        _sleep_with_progress(controller, dispense_time_s, "DISPENSE")
        print(f"Position after dispense: {controller.get_position(PUMP_NUM)} µL", flush=True)

        print("\n" + "=" * 60)
        print("DONE")
        print("=" * 60)
        final_pos = controller.get_position(PUMP_NUM)
        print(f"Final position: {final_pos} µL", flush=True)

    except KeyboardInterrupt:
        print("\nInterrupted. Aborting motion...", flush=True)
        try:
            controller.terminate_move(PUMP_NUM)
        except Exception:
            pass
        raise
    finally:
        controller.close()
        print("Pump disconnected", flush=True)


if __name__ == "__main__":
    main()
