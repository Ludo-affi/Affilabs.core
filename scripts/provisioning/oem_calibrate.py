# -*- coding: utf-8 -*-
"""Standalone OEM Calibration Script
====================================

Run this script before shipping or setting up any new device.
Does NOT require the main UI to be open — runs entirely from the command line.

Full workflow (both phases run automatically):
  Phase 1 — OEM Model Training:
    1a. Servo polarizer auto-calibration (sweep + detect S/P window positions)
    1b. LED response model training (10–60ms sweep → fits 3-stage linear model)

  Phase 2 — Startup Calibration:
    2a. Wavelength ROI definition (560–720 nm)
    2b. LED brightness + model load
    2c. S-mode LED convergence + reference capture
    2d. P-mode LED convergence + reference capture + dark
    2e. QC validation & result packaging

Outputs (saved automatically):
  calibrations/active/{SERIAL}/led_model.json       ← LED response model
  calibrations/active/{SERIAL}/device_profile.json  ← Servo positions + metadata
  calibrations/active/{SERIAL}/startup_config.json  ← Final LED intensities
  _data/calibration_data/device_{SERIAL}_{DATE}.json ← Calibration record

Usage:
  python scripts/provisioning/oem_calibrate.py
  python scripts/provisioning/oem_calibrate.py --skip-oem-model    # if led_model.json already exists
  python scripts/provisioning/oem_calibrate.py --skip-phase2        # Phase 1 only
  python scripts/provisioning/oem_calibrate.py --serial FLMT09788   # override serial

Requirements:
  - Controller (PicoP4SPR / PicoP4PRO / PicoEZSPR) connected via USB
  - Detector connected via USB
  - Sensor chip / flow cell installed and buffer flowing (or air is fine for OEM)
  - .venv activated: .venv\\Scripts\\activate (Windows)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ── Project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Logging (rich stdout before any other imports) ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("oem_calibrate")

# Suppress seabreeze USBTransportHandle.__del__ NotImplementedError on Windows WinUSB
def _suppress_seabreeze_del(unraisable):
    if unraisable.exc_type is NotImplementedError and "USBTransportHandle" in str(unraisable.object or ""):
        return
    sys.__unraisablehook__(unraisable)
sys.unraisablehook = _suppress_seabreeze_del


# =============================================================================
# HARDWARE CONNECTION
# =============================================================================

@dataclass
class MinimalHardwareMgr:
    """Minimal shim required by run_oem_model_training_workflow()."""
    ctrl: object     # HAL-wrapped controller
    usb: object      # HAL-wrapped spectrometer
    device_config: dict | None = None


def connect_controller():
    """Scan for and connect the first available controller. Returns (ctrl_raw, ctrl_hal, ctrl_type)."""
    from affilabs.utils.controller import PicoP4SPR, PicoP4PRO, PicoEZSPR
    from affilabs.utils.hal.controller_hal import create_controller_hal

    candidates = [
        ("PicoP4SPR", PicoP4SPR),
        ("PicoP4PRO", PicoP4PRO),
        ("PicoEZSPR", PicoEZSPR),
    ]

    for ctrl_type, CtrlClass in candidates:
        log.info(f"  Trying {ctrl_type}...")
        try:
            ctrl = CtrlClass()
            if ctrl.open():
                log.info(f"  ✓ Connected: {ctrl_type}")
                hal = create_controller_hal(ctrl, None)
                return ctrl, hal, ctrl_type
        except Exception as e:
            log.debug(f"  {ctrl_type}: {e}")

    return None, None, None


def connect_spectrometer():
    """Connect to the first available spectrometer. Returns (usb_raw, usb_hal, serial)."""
    from affilabs.utils.usb4000_wrapper import USB4000
    from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

    log.info("  Trying detector...")
    try:
        usb = USB4000()
        if usb.open():
            serial = getattr(usb, "serial_number", "UNKNOWN")
            log.info(f"  ✓ Connected: detector {serial}")
            hal = OceanSpectrometerAdapter(usb)
            return usb, hal, serial
        else:
            log.error("  Detector open() failed — device not responding")
    except Exception as e:
        log.error(f"  Detector connection failed: {e}")

    return None, None, None


# =============================================================================
# PHASE 1 — OEM MODEL TRAINING  (servo cal + LED model)
# =============================================================================

def run_phase1_oem_model(hw_mgr: MinimalHardwareMgr) -> bool:
    """Run servo calibration + LED model training."""
    log.info("")
    log.info("=" * 70)
    log.info("  PHASE 1: OEM Model Training (servo + LED model)")
    log.info("=" * 70)

    from affilabs.core.oem_model_training import run_oem_model_training_workflow

    def progress(msg, pct):
        log.info(f"  [{pct:3d}%] {msg}")

    success = run_oem_model_training_workflow(
        hardware_mgr=hw_mgr,
        progress_callback=progress,
    )

    if success:
        log.info("  ✓ Phase 1 complete — model saved")
    else:
        log.error("  ✗ Phase 1 FAILED — check logs above")

    return success


# =============================================================================
# PHASE 2 — STARTUP CALIBRATION  (LED convergence + reference capture)
# =============================================================================

def load_device_config(detector_serial: str):
    """Return a DeviceConfiguration object for the given serial.

    run_startup_calibration() requires a DeviceConfiguration object (not a plain dict)
    because it calls device_config.get_servo_positions(), sync_to_eeprom(), etc.

    DeviceConfiguration automatically reads from:
      affilabs/config/devices/{SERIAL}/device_config.json
    which is exactly where the servo polarizer calibration writes S/P positions.
    """
    from affilabs.utils.device_configuration import DeviceConfiguration

    config_path = ROOT / "affilabs" / "config" / "devices" / detector_serial / "device_config.json"

    if config_path.exists():
        log.info(f"  Loading device config: {config_path.relative_to(ROOT)}")
        return DeviceConfiguration(config_path=str(config_path))

    # No file yet (brand new device — servo cal hasn't run yet).
    # DeviceConfiguration will create a blank config; servo positions will be None
    # and get_servo_positions() will return None → orchestrator triggers servo cal.
    log.warning(f"  No device_config.json for {detector_serial} — will create new one at:")
    log.warning(f"    {config_path}")
    return DeviceConfiguration(device_serial=detector_serial)


def run_phase2_startup_calibration(
    hw_mgr: MinimalHardwareMgr,
    detector_serial: str,
    ctrl_type: str,
    device_config,  # DeviceConfiguration object
) -> object | None:
    """Run full startup calibration (LED convergence + reference capture + QC)."""
    log.info("")
    log.info("=" * 70)
    log.info("  PHASE 2: Startup Calibration (LED convergence + references)")
    log.info("=" * 70)

    from affilabs.core.calibration_orchestrator import run_startup_calibration

    def progress(msg, pct):
        log.info(f"  [{pct:3d}%] {msg}")

    import threading
    stop_flag = threading.Event()

    result = run_startup_calibration(
        usb=hw_mgr.usb,
        ctrl=hw_mgr.ctrl,
        device_type=ctrl_type,
        device_config=device_config,
        detector_serial=detector_serial,
        progress_callback=progress,
        single_mode=False,
        stop_flag=stop_flag,
        use_convergence_engine=True,
        force_oem_retrain=False,
    )

    if result and result.success:
        log.info("  ✓ Phase 2 complete — calibration successful")
    else:
        log.error("  ✗ Phase 2 FAILED — device NOT calibrated")

    return result


# =============================================================================
# SAVE CALIBRATION RECORD
# =============================================================================

def save_calibration_record(
    detector_serial: str,
    ctrl_type: str,
    result,
) -> None:
    """Save calibration record to _data/calibration_data/device_SERIAL_DATE.json."""
    date_str = datetime.now().strftime("%Y%m%d")
    out_dir = ROOT / "_data" / "calibration_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"device_{detector_serial}_{date_str}.json"

    # Load existing device_profile to grab polarizer positions
    profile_path = ROOT / "calibrations" / "active" / detector_serial / "device_profile.json"
    polarizer_data = {}
    if profile_path.exists():
        try:
            with open(profile_path) as f:
                profile = json.load(f)
            polarizer_data = profile.get("polarizer", {})
        except Exception:
            pass

    record = {
        "device_serial": detector_serial,
        "device_type": ctrl_type,
        "calibration_date": datetime.now().isoformat(),
        "calibration_success": bool(result and result.success),
        "polarizer": polarizer_data,
        "oem_calibration_version": "2.0",
        "afterglow": {},
    }

    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)

    log.info(f"  Saved: {out_path.relative_to(ROOT)}")


def update_device_registry(
    detector_serial: str,
    ctrl_type: str,
) -> None:
    """Add device to device_registry.json if not already present."""
    registry_path = ROOT / "_data" / "calibration_data" / "device_registry.json"
    if not registry_path.exists():
        log.warning("  device_registry.json not found — skipping registry update")
        return

    with open(registry_path) as f:
        registry = json.load(f)

    devices = registry.setdefault("devices", {})

    if detector_serial not in devices:
        # Find all calibration files for this serial
        cal_files = sorted(
            [p.name for p in (ROOT / "_data" / "calibration_data").glob(f"device_{detector_serial}_*.json")]
        )
        devices[detector_serial] = {
            "serial": detector_serial,
            "device_type": ctrl_type,
            "detector_model": "Unknown",
            "status": "in-house",
            "shipped_date": None,
            "customer": None,
            "order": None,
            "calibration_files": cal_files,
            "latest_calibration": cal_files[-1] if cal_files else None,
            "ml_training_include": True,
            "notes": "Added by oem_calibrate.py",
        }
        log.info(f"  Added {detector_serial} to device_registry.json")
    else:
        # Update calibration file list
        date_str = datetime.now().strftime("%Y%m%d")
        fname = f"device_{detector_serial}_{date_str}.json"
        files = devices[detector_serial].setdefault("calibration_files", [])
        if fname not in files:
            files.append(fname)
        devices[detector_serial]["latest_calibration"] = files[-1]
        log.info(f"  Updated {detector_serial} in device_registry.json")

    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)


def record_to_device_history_db(detector_serial: str, result) -> None:
    """Record calibration metrics to tools/ml_training/device_history.db."""
    try:
        from tools.ml_training.device_history import DeviceHistoryDatabase, CalibrationRecord

        # Extract numeric portion of serial for DB key (e.g. FLMT09788 → 9788)
        serial_int = int("".join(c for c in detector_serial if c.isdigit()) or "0")

        record = CalibrationRecord(
            timestamp=datetime.now().isoformat(),
            detector_serial=serial_int,
            success=bool(result and result.success),
            s_mode_iterations=getattr(result, "s_mode_iterations", 0) or 0,
            p_mode_iterations=getattr(result, "p_mode_iterations", 0) or 0,
            total_iterations=(
                (getattr(result, "s_mode_iterations", 0) or 0)
                + (getattr(result, "p_mode_iterations", 0) or 0)
            ),
            s_mode_converged=bool(getattr(result, "s_converged", False)),
            p_mode_converged=bool(getattr(result, "p_converged", False)),
            final_fwhm_avg=getattr(result, "fwhm_avg", None),
            final_fwhm_std=getattr(result, "fwhm_std", None),
            final_snr_avg=getattr(result, "snr_avg", None),
        )

        db = DeviceHistoryDatabase()
        db.add_record(record)
        log.info(f"  Logged calibration run to device_history.db (serial_int={serial_int})")

    except Exception as e:
        log.warning(f"  Could not write to device_history.db: {e}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Affilabs.core — Standalone OEM Calibration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skip-oem-model",
        action="store_true",
        help="Skip Phase 1 (OEM model training). Use if led_model.json already exists.",
    )
    parser.add_argument(
        "--skip-phase2",
        action="store_true",
        help="Skip Phase 2 (startup calibration). Run Phase 1 only.",
    )
    parser.add_argument(
        "--serial",
        type=str,
        default=None,
        help="Override detector serial (auto-detected by default).",
    )
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  AFFILABS.CORE — OEM DEVICE CALIBRATION")
    print("  Run before shipping or after hardware replacement")
    print("=" * 70)
    print()

    # ── 1. Connect hardware ───────────────────────────────────────────────────
    log.info("Connecting hardware...")
    ctrl_raw, ctrl_hal, ctrl_type = connect_controller()
    usb_raw, usb_hal, detector_serial = connect_spectrometer()

    if ctrl_hal is None:
        log.error("Controller not found. Check USB connection and drivers.")
        sys.exit(1)
    if usb_hal is None:
        log.error("Detector not found. Check USB connection and USB drivers.")
        sys.exit(1)

    if args.serial:
        detector_serial = args.serial
        log.info(f"  Serial overridden: {detector_serial}")

    log.info(f"  Controller : {ctrl_type}")
    log.info(f"  Spectrometer: {detector_serial}")

    hw_mgr = MinimalHardwareMgr(ctrl=ctrl_hal, usb=usb_hal)

    # ── 2. Phase 1: OEM model training ───────────────────────────────────────
    if not args.skip_oem_model:
        ok = run_phase1_oem_model(hw_mgr)
        if not ok:
            log.error("Phase 1 failed — cannot proceed to Phase 2 without a valid LED model.")
            log.error("Fix the issue above and re-run, or use --skip-oem-model if the model already exists.")
            sys.exit(2)
        time.sleep(1.0)  # Let hardware settle after servo sweep

    # ── 3. Load DeviceConfiguration object (written by Phase 1 servo cal) ──────
    # IMPORTANT: must be a DeviceConfiguration object, not a plain dict.
    # The orchestrator calls device_config.get_servo_positions() to get S/P positions
    # which were written to affilabs/config/devices/{SERIAL}/device_config.json
    # by the servo calibration step in Phase 1.
    device_config = load_device_config(detector_serial)
    hw_mgr.device_config = device_config

    if device_config.get_servo_positions() is None:
        log.warning("  Servo positions not found in device_config.")
        if args.skip_oem_model:
            log.error("  --skip-oem-model was used but servo positions are missing.")
            log.error("  Run without --skip-oem-model to run servo calibration first.")
            sys.exit(4)

    # ── 4. Phase 2: Startup calibration ──────────────────────────────────────
    result = None
    if not args.skip_phase2:
        result = run_phase2_startup_calibration(
            hw_mgr=hw_mgr,
            detector_serial=detector_serial,
            ctrl_type=ctrl_type,
            device_config=device_config,
        )

    # ── 5. Save records ───────────────────────────────────────────────────────
    log.info("")
    log.info("=" * 70)
    log.info("  Saving calibration records...")
    log.info("=" * 70)
    save_calibration_record(detector_serial, ctrl_type, result)
    update_device_registry(detector_serial, ctrl_type)
    if result is not None:
        record_to_device_history_db(detector_serial, result)

    # ── 6. Summary ────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    phase1_status = "SKIPPED" if args.skip_oem_model else ("OK" if not args.skip_oem_model else "N/A")
    phase2_status = "SKIPPED" if args.skip_phase2 else ("OK" if (result and result.success) else "FAILED")
    print(f"  Phase 1 (OEM model) : {phase1_status}")
    print(f"  Phase 2 (Startup cal): {phase2_status}")
    print(f"  Device serial       : {detector_serial}")
    print(f"  Calibration folder  : calibrations/active/{detector_serial}/")
    print("=" * 70)
    print()

    if phase2_status == "FAILED":
        log.error("Calibration failed. Device is NOT ready for use.")
        sys.exit(3)

    log.info("Device is calibrated and ready.")
    log.info("Next step: open the main app and click Start Acquisition.")


if __name__ == "__main__":
    main()
