"""Optical Fiber & Servo Diagnostic Tool
========================================

Interactive tool to manually control LEDs and servo polarizer for
troubleshooting optical fiber alignment and servo movement.

Usage:
    .venv/Scripts/python.exe tools/diagnostics/fiber_servo_probe.py

Commands (at the prompt):
    led a|b|c|d|all|off  [intensity 0-255]   — turn on LED(s)
    servo <pwm>                               — move servo to PWM position (0-255)
    servo s                                   — move to saved S position
    servo p                                   — move to saved P position
    read                                      — read spectrum (max counts + top-20 avg)
    sweep                                     — sweep servo 0->255 in 16 steps, print counts at each
    status                                    — print current LED/servo state
    quit                                      — exit (LEDs off, servo to S)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np


# ── Hardware connect ──────────────────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class _HW:
    ctrl: object   # HAL-wrapped controller
    usb: object    # raw spectrometer (USB4000)


def connect_hardware() -> _HW:
    from affilabs.utils.controller import PicoP4SPR, PicoP4PRO, PicoEZSPR
    from affilabs.utils.hal.controller_hal import create_controller_hal
    from affilabs.utils.usb4000_wrapper import USB4000

    print("Connecting hardware...")

    # Controller
    ctrl_hal = None
    for name, CtrlClass in [("PicoP4SPR", PicoP4SPR), ("PicoP4PRO", PicoP4PRO), ("PicoEZSPR", PicoEZSPR)]:
        print(f"  Trying {name}...")
        try:
            ctrl = CtrlClass()
            if ctrl.open():
                ctrl_hal = create_controller_hal(ctrl, None)
                print(f"  ✓ Controller: {name}")
                break
        except Exception as e:
            print(f"    {name}: {e}")

    if not ctrl_hal:
        print("ERROR: No controller found. Check USB.")
        sys.exit(1)

    # Spectrometer
    print("  Trying detector...")
    try:
        usb = USB4000()
        if not usb.open():
            print("ERROR: Detector open() failed.")
            sys.exit(1)
        serial = getattr(usb, "serial_number", "?")
        print(f"  ✓ Spectrometer: {serial}")
    except Exception as e:
        print(f"ERROR: Detector connection failed: {e}")
        sys.exit(1)

    return _HW(ctrl=ctrl_hal, usb=usb)


# ── Low-level helpers ─────────────────────────────────────────────────────────

def raw_ctrl(hm):
    ctrl = hm.ctrl
    return ctrl._ctrl if hasattr(ctrl, "_ctrl") else ctrl


def leds_on(hm, channels: list[str], intensity: int):
    """Enable specified channels at given intensity, others off."""
    rc = raw_ctrl(hm)
    # Enable channel mode (P4SPR: comma-separated)
    ch_str = ",".join(c.upper() for c in channels)
    try:
        rc._ser.write(f"lm:{ch_str}\n".encode())
        time.sleep(0.05)
        rc._ser.read(20)
    except Exception as e:
        print(f"  [warn] lm: command failed: {e}")

    kwargs = {c: (intensity if c in channels else 0) for c in ["a", "b", "c", "d"]}
    hm.ctrl.set_batch_intensities(**kwargs)
    time.sleep(0.2)


def leds_off(hm):
    hm.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
    try:
        raw_ctrl(hm)._ser.write(b"lm:\n")
        time.sleep(0.05)
    except Exception:
        pass


def move_servo(hm, pwm: int):
    """Move servo to PWM position (0-255) using sv+sp command pair."""
    pwm = max(0, min(255, int(pwm)))
    degrees = int(5 + (pwm / 255.0) * 170.0)
    degrees = max(5, min(175, degrees))
    rc = raw_ctrl(hm)
    sv_cmd = f"sv{degrees:03d}{degrees:03d}\n"
    rc._ser.write(sv_cmd.encode())
    time.sleep(1.0)
    rc._ser.write(b"sp\n")
    time.sleep(1.0)
    print(f"  Servo -> PWM {pwm} ({degrees}°)")


def read_spectrum(hm) -> np.ndarray:
    hm.usb.set_integration(10.0)
    time.sleep(0.1)
    scans = []
    for _ in range(3):
        scans.append(hm.usb.read_intensity())
        time.sleep(0.05)
    return np.mean(scans, axis=0)


def print_spectrum_summary(spectrum: np.ndarray, label: str = ""):
    top20 = float(np.mean(np.sort(spectrum)[-20:]))
    peak = float(spectrum.max())
    prefix = f"[{label}] " if label else ""
    print(f"  {prefix}peak={peak:.0f}  top-20avg={top20:.0f}  pixels={len(spectrum)}")


def load_servo_positions(hm) -> dict | None:
    """Try to load saved S/P positions from device_config.json."""
    serial = getattr(hm.usb, "serial_number", None)
    if not serial:
        return None
    cfg_path = ROOT / "affilabs" / "config" / "devices" / serial / "device_config.json"
    if not cfg_path.exists():
        return None
    import json
    data = json.loads(cfg_path.read_text())
    s = data.get("servo_s_position") or data.get("s_position")
    p = data.get("servo_p_position") or data.get("p_position")
    if s and p:
        return {"s": int(s), "p": int(p)}
    return None


# ── Main REPL ─────────────────────────────────────────────────────────────────

def main():
    hm = connect_hardware()
    positions = load_servo_positions(hm)

    if positions:
        print(f"  Saved positions: S={positions['s']} PWM, P={positions['p']} PWM")
    else:
        print("  No saved servo positions found (run oem_calibrate first)")

    current_leds = []
    current_intensity = 100
    current_pwm = None

    print("\nReady. Type 'help' for commands.\n")

    while True:
        try:
            line = input("probe> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            line = "quit"

        if not line:
            continue

        parts = line.split()
        cmd = parts[0]

        # ── help ──
        if cmd == "help":
            print(__doc__)

        # ── quit ──
        elif cmd in ("quit", "exit", "q"):
            print("Turning LEDs off...")
            leds_off(hm)
            if positions:
                print(f"Moving servo to S position ({positions['s']} PWM)...")
                move_servo(hm, positions["s"])
            print("Done.")
            break

        # ── led ──
        elif cmd == "led":
            if len(parts) < 2:
                print("  Usage: led a|b|c|d|all|off [intensity]")
                continue
            channel_arg = parts[1]
            intensity = int(parts[2]) if len(parts) >= 3 else current_intensity

            if channel_arg == "off":
                leds_off(hm)
                current_leds = []
                print("  LEDs off")
            elif channel_arg == "all":
                channels = ["a", "b", "c", "d"]
                leds_on(hm, channels, intensity)
                current_leds = channels
                current_intensity = intensity
                print(f"  LEDs A B C D ON @ intensity {intensity}")
            elif channel_arg in ("a", "b", "c", "d"):
                channels = [channel_arg]
                leds_on(hm, channels, intensity)
                current_leds = channels
                current_intensity = intensity
                print(f"  LED {channel_arg.upper()} ON @ intensity {intensity}")
            else:
                print(f"  Unknown channel: {channel_arg}")

        # ── servo ──
        elif cmd == "servo":
            if len(parts) < 2:
                print("  Usage: servo <pwm 0-255> | servo s | servo p")
                continue
            arg = parts[1]
            if arg == "s":
                if positions:
                    move_servo(hm, positions["s"])
                    current_pwm = positions["s"]
                else:
                    print("  No saved S position. Use: servo <pwm>")
            elif arg == "p":
                if positions:
                    move_servo(hm, positions["p"])
                    current_pwm = positions["p"]
                else:
                    print("  No saved P position. Use: servo <pwm>")
            else:
                try:
                    pwm = int(arg)
                    move_servo(hm, pwm)
                    current_pwm = pwm
                except ValueError:
                    print(f"  Invalid PWM: {arg}")

        # ── read ──
        elif cmd == "read":
            spectrum = read_spectrum(hm)
            lbl = f"servo={current_pwm} PWM" if current_pwm is not None else "servo=?"
            print_spectrum_summary(spectrum, label=lbl)

        # ── sweep ──
        elif cmd == "sweep":
            print("  Sweeping servo 0 -> 255 (16 steps)...")
            print(f"  {'PWM':>4}  {'deg':>4}  {'peak':>8}  {'top-20':>8}")
            print("  " + "-" * 32)
            for pwm in range(0, 256, 16):
                move_servo(hm, pwm)
                spectrum = read_spectrum(hm)
                top20 = float(np.mean(np.sort(spectrum)[-20:]))
                peak = float(spectrum.max())
                degrees = int(5 + (pwm / 255.0) * 170.0)
                print(f"  {pwm:>4}  {degrees:>4}  {peak:>8.0f}  {top20:>8.0f}")
            current_pwm = 255
            print("  Sweep done.")

        # ── status ──
        elif cmd == "status":
            led_str = ", ".join(c.upper() for c in current_leds) if current_leds else "OFF"
            pwm_str = str(current_pwm) if current_pwm is not None else "unknown"
            print(f"  LEDs     : {led_str}  (intensity={current_intensity})")
            print(f"  Servo    : {pwm_str} PWM")
            if positions:
                print(f"  Saved S  : {positions['s']} PWM")
                print(f"  Saved P  : {positions['p']} PWM")

        else:
            print(f"  Unknown command: {cmd}. Type 'help' for commands.")


if __name__ == "__main__":
    main()
