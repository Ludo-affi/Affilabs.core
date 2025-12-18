#!/usr/bin/env python3
"""Headless Calibration CLI

Runs the 6-step calibration without the Qt UI.
Useful to reproduce crashes (e.g., during S↔P movements) and capture logs.

Usage (from repo root):
  python tools/calibration_cli.py --log

Options:
  --skip-afterglow   Skip afterglow parts if your workflow only needs LED calibration
  --iterations N     Override max iterations per convergence phase (if supported)
  --verbose          Extra console logging
  --log              Write detailed log to logs/calibration_cli_YYYYmmdd_HHMMSS.log
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime


def _setup_paths():
    # Ensure `src` is importable when running the script directly
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(repo_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    return repo_root


def _setup_logging(enable_file: bool, verbose: bool) -> logging.Logger:
    from utils.logger import logger as app_logger

    # Avoid duplicating handlers across multiple runs
    logger = app_logger
    logger.setLevel(logging.INFO)
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Add file handler if requested
    if enable_file:
        os.makedirs("logs", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join("logs", f"calibration_cli_{ts}.log")
        fh = logging.FileHandler(filepath, encoding="utf-8")
        fh.setLevel(logging.DEBUG if verbose else logging.INFO)
        fh.setFormatter(
            logging.Formatter("%(asctime)s :: %(levelname)s :: %(message)s"),
        )
        logger.addHandler(fh)
        logger.info(f"[CLI] File logging → {filepath}")
    return logger


def _connect_hardware(logger):
    # Use HardwareManager but invoke synchronous connect steps to avoid Qt threads
    from core.hardware_manager import HardwareManager

    hm = HardwareManager()

    try:
        logger.info("=== HARDWARE CONNECT (CLI) ===")
        hm._connect_controller()
        hm._connect_spectrometer()
        if not hm.ctrl or not hm.usb:
            raise RuntimeError("Controller and spectrometer must both be connected")
        logger.info("✅ Controller + spectrometer connected")
    except Exception:
        logger.exception("Hardware connection failed")
        raise

    return hm


def _flush_usb(usb, logger):
    try:
        logger.info("🔄 Flushing spectrometer buffer (3 dummy reads @ 10 ms)...")
        usb.set_integration(10)
        time.sleep(0.1)
        for i in range(3):
            arr = usb.read_intensity(timeout_seconds=2.0)
            if arr is None:
                logger.warning(f"   Dummy read {i+1}/3: timeout (continuing)")
            else:
                logger.info(f"   Dummy read {i+1}/3: {len(arr)} pixels")
            time.sleep(0.05)
        logger.info("✅ Spectrometer buffer flushed")
    except Exception as e:
        logger.warning(f"USB flush encountered issues: {e}")


def _progress(msg: str, pct: int = 0):
    # Simple console-friendly progress callback
    try:
        from utils.logger import logger

        logger.info(f"[CAL] {msg} ({pct}%)")
    except Exception:
        print(f"[CAL] {msg} ({pct}%)")


def main(argv=None):
    _ = _setup_paths()

    ap = argparse.ArgumentParser(description="Run LED calibration headlessly (no UI)")
    ap.add_argument(
        "--skip-afterglow",
        action="store_true",
        help="Skip afterglow steps if supported",
    )
    ap.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Override convergence max iterations (if supported)",
    )
    ap.add_argument("--verbose", action="store_true", help="Enable extra debug logs")
    ap.add_argument(
        "--log",
        action="store_true",
        help="Write detailed log to logs/ folder",
    )
    args = ap.parse_args(argv)

    logger = _setup_logging(enable_file=args.log, verbose=args.verbose)

    # Ensure Qt doesn’t interfere
    os.environ.setdefault("QT_LOGGING_RULES", "qt.*=false;*.debug=false")
    os.environ.setdefault("QT_FATAL_WARNINGS", "0")

    # Headless marker for any shared code paths
    os.environ["CALIBRATION_HEADLESS"] = "1"

    # Connect hardware
    hm = _connect_hardware(logger)
    usb, ctrl = hm.usb, hm.ctrl

    # Light device configuration
    from affilabs.utils.device_configuration import DeviceConfiguration

    device_serial = getattr(usb, "serial_number", None)
    device_config = DeviceConfiguration(device_serial=device_serial)
    # LED timing now built into hardware commands - no explicit delays needed
    logger.info("📊 LED timing: Built into hardware commands (no explicit delays)")

    # Flush spectrometer IO
    _flush_usb(usb, logger)

    # Run calibration core
    from affilabs.utils.startup_calibration import run_full_6step_calibration

    logger.info("🚀 Starting 6-step calibration (CLI)…")
    try:
        cal_result = run_full_6step_calibration(
            usb=usb,
            ctrl=ctrl,
            device_type=type(ctrl).__name__,
            device_config=device_config,
            detector_serial=device_serial,
            progress_callback=_progress,
        )
    except Exception:
        logger.exception("Calibration routine crashed")
        sys.exit(2)

    if not cal_result or not getattr(cal_result, "success", False):
        err = (
            getattr(cal_result, "error", None)
            or getattr(cal_result, "error_message", None)
            or "Calibration failed"
        )
        logger.error(f"❌ Calibration failed: {err}")
        sys.exit(1)

    try:
        if hasattr(cal_result, "validate") and not cal_result.validate():
            logger.error("❌ Calibration data validation failed")
            sys.exit(3)
    except Exception as e:
        logger.warning(f"Validation raised: {e}")

    # Minimal summary output
    chans = cal_result.get_channels() if hasattr(cal_result, "get_channels") else []
    logger.info("✅ Calibration SUCCESS")
    logger.info(f"   Channels: {chans}")
    if hasattr(cal_result, "shared_integration_ms"):
        logger.info(f"   Shared integration: {cal_result.shared_integration_ms} ms")
    if hasattr(cal_result, "leds_calibrated"):
        logger.info(f"   LED intensities: {cal_result.leds_calibrated}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
