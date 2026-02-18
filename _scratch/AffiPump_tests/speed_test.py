"""Speed test for AffiPump.

Purpose:
- Cancel any residual motion
- Run a small aspirate/dispense at requested speeds
- Measure actual motion time from position readings

This avoids run_buffer and isolates speed/velocity behavior.

Run:
  py -3.12 -u speed_test.py
"""

import time

from affipump_controller import AffipumpController

PORT = "COM8"
BAUD = 38400
PUMP_NUM = 1

# Test parameters
TEST_VOLUME_UL = 200
PREFILL_UL = 800

ASPIRATE_UL_MIN = 15000
ASPIRATE_UL_S = ASPIRATE_UL_MIN / 60.0  # 250 µL/s

DISPENSE_UL_MIN = 500
DISPENSE_UL_S = DISPENSE_UL_MIN / 60.0  # 8.333.. µL/s

SAMPLE_PERIOD_S = 0.5
POS_EPS_UL = 2.0


def _now() -> float:
    return time.perf_counter()


def _safe_cancel(controller: AffipumpController) -> None:
    try:
        controller.terminate_move(PUMP_NUM)
    except Exception:
        pass
    try:
        st = controller.get_status(PUMP_NUM)
        if st and st.get('error'):
            controller.clear_errors(PUMP_NUM)
    except Exception:
        pass
    time.sleep(0.2)


def _read_pos(controller: AffipumpController):
    try:
        return controller.get_position(PUMP_NUM)
    except Exception:
        return None


def _wait_until_target(controller: AffipumpController, target_pos, timeout_s: float):
    start_t = _now()
    next_print = start_t
    last_pos = _read_pos(controller)

    while _now() - start_t < timeout_s:
        time.sleep(SAMPLE_PERIOD_S)
        pos = _read_pos(controller)
        if pos is not None:
            last_pos = pos

        now = _now()
        if now >= next_print:
            try:
                st = controller.get_status(PUMP_NUM)
            except Exception:
                st = None
            print(f"  t={now-start_t:5.1f}s pos={last_pos} target={target_pos} status={st and st.get('status_char')}", flush=True)
            next_print = now + 5.0

        if last_pos is not None and target_pos is not None:
            if abs(last_pos - target_pos) <= POS_EPS_UL:
                return last_pos

    return last_pos


def _run_one(controller: AffipumpController, label: str, move_fn, speed_ul_s: float, expected_time_s: float, target_pos):
    code, res = controller._velocity_to_code(speed_ul_s)
    print("\n" + "-" * 60, flush=True)
    print(f"{label}", flush=True)
    print(f"Requested speed: {speed_ul_s:.4f} µL/s ({speed_ul_s*60:.1f} µL/min)", flush=True)
    print(f"Velocity command: V{code},{res}", flush=True)
    print(f"Expected time (ideal): ~{expected_time_s:.1f}s", flush=True)

    _safe_cancel(controller)

    pos0 = _read_pos(controller)
    print(f"Position before: {pos0} µL", flush=True)
    try:
        print(f"Status before:   {controller.get_status(PUMP_NUM)}", flush=True)
        print(f"Error before:    {controller.get_error_code(PUMP_NUM)}", flush=True)
    except Exception:
        pass

    t0 = _now()
    move_fn(TEST_VOLUME_UL, speed_ul_s)

    pos_end = _wait_until_target(controller, target_pos, timeout_s=max(120.0, expected_time_s * 6.0))
    t1 = _now()

    print(f"Position after:  {pos_end} µL", flush=True)
    try:
        print(f"Status after:    {controller.get_status(PUMP_NUM)}", flush=True)
        print(f"Error after:     {controller.get_error_code(PUMP_NUM)}", flush=True)
    except Exception:
        pass

    if pos0 is not None and pos_end is not None:
        moved_ul = abs(pos_end - pos0)
        dt = max(0.001, t1 - t0)
        eff_ul_s = moved_ul / dt
        eff_ul_min = eff_ul_s * 60.0
        print(f"Measured move:  {moved_ul:.1f} µL in {dt:.1f}s => {eff_ul_min:.1f} µL/min", flush=True)
    else:
        print("Measured move:  (position unavailable)", flush=True)


def main():
    controller = AffipumpController(port=PORT, baudrate=BAUD, auto_recovery=True)
    controller.open()

    try:
        print("\nCancelling any residual motion...", flush=True)
        _safe_cancel(controller)

        print("Initializing pump (home + zero)...", flush=True)
        controller.initialize_pump(PUMP_NUM)

        # Prefill syringe so dispense has real volume to move.
        controller.set_valve_input(PUMP_NUM)
        time.sleep(0.2)
        print(f"Prefilling to ~{PREFILL_UL} µL...", flush=True)
        controller.aspirate(PUMP_NUM, PREFILL_UL, 50.0)
        time.sleep((PREFILL_UL / 50.0) + 2.0)
        pos_prefill = _read_pos(controller)
        print(f"Position after prefill: {pos_prefill} µL", flush=True)

        # Confirm whether terminate_move changes the reported position.
        try:
            st_before = controller.get_status(PUMP_NUM)
        except Exception:
            st_before = None
        print(f"Status after prefill: {st_before}", flush=True)

        print("Sending terminate_move (TR) to cancel residual action...", flush=True)
        try:
            controller.terminate_move(PUMP_NUM)
        except Exception as e:
            print(f"terminate_move error: {e}", flush=True)
        time.sleep(0.5)
        print(f"Position after TR: {_read_pos(controller)} µL", flush=True)

        # DISPENSE speed test
        controller.set_valve_output(PUMP_NUM)
        time.sleep(0.2)
        pos0 = _read_pos(controller)
        target = None if pos0 is None else max(0.0, pos0 - TEST_VOLUME_UL)
        _run_one(
            controller,
            label=f"DISPENSE {TEST_VOLUME_UL} µL @ {DISPENSE_UL_MIN} µL/min",
            move_fn=lambda vol, sp: controller.dispense(PUMP_NUM, vol, sp),
            speed_ul_s=DISPENSE_UL_S,
            expected_time_s=TEST_VOLUME_UL / DISPENSE_UL_S,
            target_pos=target,
        )

        # ASPIRATE speed test
        # Dispense back down a bit first so we have room to aspirate.
        controller.set_valve_output(PUMP_NUM)
        time.sleep(0.2)
        controller.dispense(PUMP_NUM, TEST_VOLUME_UL, 50.0)
        time.sleep((TEST_VOLUME_UL / 50.0) + 2.0)

        controller.set_valve_input(PUMP_NUM)
        time.sleep(0.2)
        pos0 = _read_pos(controller)
        target = None if pos0 is None else min(1000.0, pos0 + TEST_VOLUME_UL)
        _run_one(
            controller,
            label=f"ASPIRATE {TEST_VOLUME_UL} µL @ {ASPIRATE_UL_MIN} µL/min",
            move_fn=lambda vol, sp: controller.aspirate(PUMP_NUM, vol, sp),
            speed_ul_s=ASPIRATE_UL_S,
            expected_time_s=TEST_VOLUME_UL / ASPIRATE_UL_S,
            target_pos=target,
        )

        print("\nDone.", flush=True)

    except KeyboardInterrupt:
        print("\nInterrupted. Sending cancel...", flush=True)
        _safe_cancel(controller)
        raise
    finally:
        try:
            _safe_cancel(controller)
        except Exception:
            pass
        controller.close()


if __name__ == "__main__":
    main()
