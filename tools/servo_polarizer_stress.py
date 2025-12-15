#!/usr/bin/env python3
"""Polarizer Stress Test (Headless)

Rapidly toggles the polarizer S↔P to reproduce crashes related to servo moves
while capturing spectrometer reads for basic health checks.

Usage:
  python tools/servo_polarizer_stress.py --cycles 20 --delay 0.4 --log
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime


def _setup_paths():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(repo_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    return repo_root


def _setup_logging(enable_file: bool, verbose: bool) -> logging.Logger:
    from utils.logger import logger as app_logger

    logger = app_logger
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if enable_file:
        os.makedirs("logs", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("logs", f"servo_stress_{ts}.log")
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(logging.DEBUG if verbose else logging.INFO)
        fh.setFormatter(
            logging.Formatter("%(asctime)s :: %(levelname)s :: %(message)s"),
        )
        logger.addHandler(fh)
        logger.info(f"[STRESS] File logging → {path}")
    return logger


def _connect_hardware(logger):
    from core.hardware_manager import HardwareManager

    hm = HardwareManager()
    logger.info("=== HARDWARE CONNECT (SERVO STRESS) ===")
    hm._connect_controller()
    hm._connect_spectrometer()
    if not hm.ctrl or not hm.usb:
        raise RuntimeError("Controller and spectrometer must both be connected")
    logger.info("✅ Controller + spectrometer connected")
    return hm


def _flush_usb(usb, logger):
    try:
        usb.set_integration(10)
        time.sleep(0.1)
        for i in range(2):
            arr = usb.read_intensity(timeout_seconds=2.0)
            logger.info(f"Dummy read {i+1}/2: {'OK' if arr is not None else 'TIMEOUT'}")
            time.sleep(0.05)
    except Exception as e:
        logger.warning(f"USB flush issue: {e}")


def main(argv=None):
    _ = _setup_paths()

    ap = argparse.ArgumentParser(
        description="Toggle polarizer S↔P in a loop and read spectra",
    )
    ap.add_argument("--cycles", type=int, default=20, help="Number of S→P→S cycles")
    ap.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Delay (s) after each move",
    )
    ap.add_argument(
        "--readouts",
        type=int,
        default=1,
        help="Spectra reads after each move",
    )
    ap.add_argument("--log", action="store_true", help="Write log file to logs/")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = ap.parse_args(argv)

    logger = _setup_logging(args.log, args.verbose)
    os.environ["CALIBRATION_HEADLESS"] = "1"

    hm = _connect_hardware(logger)
    usb, ctrl = hm.usb, hm.ctrl
    _flush_usb(usb, logger)

    # Determine S/P positions from device config (same method HardwareManager uses)
    try:
        from utils.common import get_config

        cfg = get_config()
        s_pos = cfg.get("hardware", {}).get("servo_s_position", 120)
        p_pos = cfg.get("hardware", {}).get("servo_p_position", 60)
    except Exception:
        s_pos, p_pos = 120, 60

    logger.info(
        f"Starting stress test: cycles={args.cycles}, delay={args.delay}s, reads={args.readouts}",
    )
    logger.info(f"Servo targets: S={s_pos}°, P={p_pos}°")

    # Ensure LEDs are off for safety during movements
    try:
        if hasattr(ctrl, "turn_off_channels"):
            ctrl.turn_off_channels()
    except Exception:
        pass

    for c in range(1, args.cycles + 1):
        logger.info(f"=== Cycle {c}/{args.cycles} : Move → S ===")
        try:
            if hasattr(ctrl, "servo_move_calibration_only"):
                ctrl.servo_move_calibration_only(s=s_pos, p=p_pos)
            elif hasattr(ctrl, "servo_set"):
                ctrl.servo_set(s=s_pos, p=p_pos)
            else:
                raise RuntimeError("Controller lacks servo methods")
            time.sleep(args.delay)
        except Exception:
            logger.exception("Move to S failed")
            return 2

        for r in range(args.readouts):
            try:
                arr = usb.read_intensity(timeout_seconds=2.0)
                if arr is None:
                    logger.warning("S-read: timeout")
                else:
                    logger.info(f"S-read: {len(arr)} pixels")
            except Exception:
                logger.exception("S-read crashed")
                return 3

        logger.info(f"=== Cycle {c}/{args.cycles} : Move → P ===")
        try:
            if hasattr(ctrl, "servo_move_calibration_only"):
                ctrl.servo_move_calibration_only(s=s_pos, p=p_pos)
            if hasattr(ctrl, "servo_set"):
                ctrl.servo_set(s=p_pos, p=s_pos)  # swap targets as a simple P-set
            time.sleep(args.delay)
        except Exception:
            logger.exception("Move to P failed")
            return 4

        for r in range(args.readouts):
            try:
                arr = usb.read_intensity(timeout_seconds=2.0)
                if arr is None:
                    logger.warning("P-read: timeout")
                else:
                    logger.info(f"P-read: {len(arr)} pixels")
            except Exception:
                logger.exception("P-read crashed")
                return 5

    logger.info("✅ Stress test completed without exceptions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
