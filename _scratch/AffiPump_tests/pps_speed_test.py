"""Measure real pump speed in *pulses/second* using raw step counts.

This bypasses any steps<->µL assumptions so we can validate whether the pump
is actually reaching high speed (e.g., ~6000 pulses/sec).

Run:
  py -3.12 -u pps_speed_test.py

Safe-ish defaults:
- Uses a moderate step move
- Cancels residual motion before/after
"""

import time

from affipump_controller import AffipumpController

PORT = "COM8"
BAUD = 38400
PUMP_NUM = 1

# Raw step moves for measurement (pulses). Use multiple distances so we can
# see the steady-state speed after acceleration.
TEST_STEPS_LIST = [60000, 120000, 180000]

# Speed config targets (per controller docstrings)
START_PPS = 1000
TOP_PPS = 6000
CUTOFF_PPS = 2700
SLOPE = 20


def _now() -> float:
    return time.perf_counter()


def _safe_cancel(ctrl: AffipumpController) -> None:
    try:
        ctrl.terminate_move(PUMP_NUM)
    except Exception:
        pass
    time.sleep(0.2)


def _wait_idle(ctrl: AffipumpController, timeout_s: float = 30.0) -> None:
    t0 = _now()
    while _now() - t0 < timeout_s:
        st = ctrl.get_status(PUMP_NUM)
        if st and st.get("idle"):
            return
        time.sleep(0.1)
    raise TimeoutError("Pump did not go idle")


def main() -> None:
    ctrl = AffipumpController(port=PORT, baudrate=BAUD, auto_recovery=True)
    ctrl.open()

    try:
        print("Cancelling residual motion...", flush=True)
        _safe_cancel(ctrl)

        print("Reading pump configuration...", flush=True)
        fw = ctrl.get_firmware_version(PUMP_NUM)
        syringe_cfg = ctrl.get_syringe_volume(PUMP_NUM)

        raw_q1 = ctrl.send_command(f"/{PUMP_NUM}?1")
        raw_q2 = ctrl.send_command(f"/{PUMP_NUM}?2")
        raw_q3 = ctrl.send_command(f"/{PUMP_NUM}?3")

        start_cfg = ctrl.get_start_speed(PUMP_NUM)
        top_cfg = ctrl.get_top_speed(PUMP_NUM)
        cutoff_cfg = ctrl.get_cutoff_speed(PUMP_NUM)

        print(f"Firmware:       {fw}")
        print(f"Syringe (?17):  {syringe_cfg}")
        print(f"Raw ?1:         {raw_q1!r}")
        print(f"Raw ?2:         {raw_q2!r}")
        print(f"Raw ?3:         {raw_q3!r}")
        print(f"Start (?1):     {start_cfg}")
        print(f"Top (?2):       {top_cfg}")
        print(f"Cutoff (?3):    {cutoff_cfg}")

        print("\nInitializing pump...", flush=True)
        ctrl.initialize_pump(PUMP_NUM)
        _wait_idle(ctrl, timeout_s=30.0)

        print("\nSetting speed profile (v/V/c/L)...", flush=True)
        try:
            ctrl.set_slope(PUMP_NUM, SLOPE)
            ctrl.set_start_speed(PUMP_NUM, START_PPS)
            ctrl.set_cutoff_speed(PUMP_NUM, CUTOFF_PPS)
            ctrl.set_top_speed(PUMP_NUM, TOP_PPS)
        except Exception as e:
            print(f"Speed profile set raised: {e}")
        time.sleep(0.2)

        raw_q1b = ctrl.send_command(f"/{PUMP_NUM}?1")
        raw_q2b = ctrl.send_command(f"/{PUMP_NUM}?2")
        raw_q3b = ctrl.send_command(f"/{PUMP_NUM}?3")
        start_cfg2 = ctrl.get_start_speed(PUMP_NUM)
        top_cfg2 = ctrl.get_top_speed(PUMP_NUM)
        cutoff_cfg2 = ctrl.get_cutoff_speed(PUMP_NUM)
        print(f"Raw ?1 (after): {raw_q1b!r}")
        print(f"Raw ?2 (after): {raw_q2b!r}")
        print(f"Raw ?3 (after): {raw_q3b!r}")
        print(f"Start now:      {start_cfg2}")
        print(f"Top now:        {top_cfg2}")
        print(f"Cutoff now:     {cutoff_cfg2}")

        print("\nMeasuring raw pulses/sec (multiple distances)...", flush=True)
        ctrl.set_valve_input(PUMP_NUM)
        time.sleep(0.2)

        if not syringe_cfg:
            syringe_cfg = 1000

        steps_per_ul = ctrl.full_stroke_steps / float(syringe_cfg)
        print(f"Assumed steps/µL: {steps_per_ul:.4f} (from ?17={syringe_cfg})")
        print(
            "For reference, 60,000 µL/min with a 1 mL syringe would require "
            f"~{(60000/60.0)*steps_per_ul:.0f} pulses/sec."
        )

        for test_steps in TEST_STEPS_LIST:
            _safe_cancel(ctrl)
            pos0 = ctrl.get_plunger_position_raw(PUMP_NUM)
            t0 = _now()
            ctrl.send_command(f"/{PUMP_NUM}P{test_steps}R")
            _wait_idle(ctrl, timeout_s=120.0)
            t1 = _now()
            pos1 = ctrl.get_plunger_position_raw(PUMP_NUM)

            if pos0 is None or pos1 is None:
                raise RuntimeError("Could not read raw positions")

            moved = pos1 - pos0
            dt = max(1e-3, t1 - t0)
            pps = abs(moved) / dt
            ul_min = (pps / steps_per_ul) * 60.0

            print("-" * 60)
            print(f"Move: {test_steps} steps")
            print(f"Raw pos: {pos0} -> {pos1} (Δ={moved})")
            print(f"Time: {dt:.3f}s")
            print(f"Effective: {pps:.1f} pulses/sec")
            print(f"Equivalent: {ul_min:.0f} µL/min (if 1 mL syringe scaling)")

    finally:
        try:
            _safe_cancel(ctrl)
        except Exception:
            pass
        ctrl.close()


if __name__ == "__main__":
    main()
