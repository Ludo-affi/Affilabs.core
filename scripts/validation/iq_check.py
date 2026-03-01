"""Installation Qualification (IQ) -- Affilabs.core v1.0

PURPOSE
-------
Verifies that Affilabs.core is correctly installed on a given machine.
Produces a timestamped JSON report suitable for academic/lab archiving.

USAGE (frozen exe -- customer)
    AffilabsCore.exe --iq-check
    AffilabsCore.exe --iq-check --operator "Jane Smith"

USAGE (dev / source)
    python scripts/validation/iq_check.py
    python scripts/validation/iq_check.py --operator "Jane Smith"

Report saved to:
    Frozen:  %APPDATA%\\Affilabs\\validation\\IQ_report_<SERIAL>_<DATE>.json
    Dev:     _data/validation/IQ_report_<SERIAL>_<DATE>.json

CHECKS (frozen mode)
    IQ-004  VERSION file present and parseable as semver
    IQ-005  Required config files present
    IQ-006  Detector profile JSON files contain required keys
    IQ-007  user_profiles.json has valid schema
    IQ-010  OS is Windows x86-64
    IQ-011  Data directory is writable

CHECKS (dev/source mode, additional)
    IQ-001  Python version >= 3.12, < 3.13
    IQ-003  Critical source modules importable
    IQ-008  No conflicting Qt bindings installed

DEFERRED (v2)
    IQ-002  Full dependency version pinning
    IQ-009  File integrity manifest (SHA-256)
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# -- Environment detection -----------------------------------------------------
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    # Running as PyInstaller exe.
    # sys.executable  = path to AffilabsCore.exe
    # sys._MEIPASS    = temp dir where bundled libs are extracted
    INSTALL_DIR = Path(sys.executable).parent
    BUNDLE_DIR  = Path(sys._MEIPASS)
else:
    # Running from source tree.
    _SCRIPT_DIR = Path(__file__).resolve().parent
    INSTALL_DIR = _SCRIPT_DIR.parent.parent   # workspace root
    BUNDLE_DIR  = INSTALL_DIR
    if str(INSTALL_DIR) not in sys.path:
        sys.path.insert(0, str(INSTALL_DIR))


# -- Serial auto-detection -----------------------------------------------------

def _normalize_serial(raw: str) -> str:
    """Normalize legacy FLMT/ST prefixes to AFFI for reports."""
    for prefix in ("FLMT", "ST"):
        if raw.upper().startswith(prefix):
            return "AFFI" + raw[len(prefix):]
    return raw


def _detect_serial() -> str:
    """Read instrument serial from config/devices/ folder name.

    Provisioning writes config/devices/<SERIAL>/device_config.json.
    The folder name IS the serial -- no hardware connection needed.
    Legacy FLMT/ST prefixes are normalized to AFFI in the report.
    """
    devices_dir = INSTALL_DIR / "config" / "devices"
    if not devices_dir.exists():
        return "UNKNOWN"
    for entry in sorted(devices_dir.iterdir()):
        if entry.is_dir() and (entry / "device_config.json").exists():
            return _normalize_serial(entry.name)
    return "UNKNOWN"


# -- Result helpers ------------------------------------------------------------

def _pass(check_id, description, detail=""):
    return {"id": check_id, "description": description, "result": "PASS", "detail": detail}

def _fail(check_id, description, detail=""):
    return {"id": check_id, "description": description, "result": "FAIL", "detail": detail}

def _skip(check_id, description, reason=""):
    return {"id": check_id, "description": description, "result": "SKIP", "detail": reason}


# -- Checks --------------------------------------------------------------------

def check_iq001():
    """IQ-001: Python version >= 3.12, < 3.13 (dev mode only)."""
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor == 12:
        return _pass("IQ-001", "Python version >= 3.12, < 3.13", detail)
    return _fail("IQ-001", "Python version >= 3.12, < 3.13",
                 f"{detail} -- expected 3.12.x")


def check_iq003():
    """IQ-003: Critical source modules importable (dev mode only)."""
    modules = ["affilabs.core", "affilabs.services", "affilabs.hardware", "AffiPump"]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")
    if not failed:
        return _pass("IQ-003", "Critical source modules importable", ", ".join(modules))
    return _fail("IQ-003", "Critical source modules importable", "; ".join(failed))


def check_iq004():
    """IQ-004: VERSION file present and parseable as semver."""
    for candidate in [INSTALL_DIR / "VERSION", BUNDLE_DIR / "VERSION"]:
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8").strip()
            if re.match(r"^\d+\.\d+\.\d+", content):
                return _pass("IQ-004", "VERSION file present and parseable", content)
            return _fail("IQ-004", "VERSION file present and parseable",
                         f"Not semver: {content!r}")
    return _fail("IQ-004", "VERSION file present and parseable", "File not found")


def check_iq005():
    """IQ-005: Required config files present."""
    required = [INSTALL_DIR / "user_profiles.json"]
    detector_dir = INSTALL_DIR / "detector_profiles"
    profiles = list(detector_dir.glob("*.json")) if detector_dir.exists() else []
    missing = [str(p) for p in required if not p.exists()]
    if not profiles:
        missing.append("detector_profiles/*.json (none found)")
    if not missing:
        return _pass("IQ-005", "Required config files present",
                     f"{len(profiles)} detector profile(s) found")
    return _fail("IQ-005", "Required config files present",
                 "Missing: " + "; ".join(missing))


def check_iq006():
    """IQ-006: Detector profile JSON files contain required keys."""
    detector_dir = INSTALL_DIR / "detector_profiles"
    profiles = list(detector_dir.glob("*.json")) if detector_dir.exists() else []
    if not profiles:
        return _fail("IQ-006", "Detector profile schema valid", "No profiles found")
    required_keys = {"hardware_specs", "acquisition_limits", "spr_settings"}
    errors = []
    for p in profiles:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{p.name}: invalid JSON -- {e}")
            continue
        missing = required_keys - data.keys()
        if missing:
            errors.append(f"{p.name}: missing {missing}")
    if not errors:
        return _pass("IQ-006", "Detector profile schema valid",
                     f"{len(profiles)} profile(s) OK")
    return _fail("IQ-006", "Detector profile schema valid", "; ".join(errors))


def check_iq007():
    """IQ-007: user_profiles.json has valid schema."""
    path = INSTALL_DIR / "user_profiles.json"
    if not path.exists():
        return _fail("IQ-007", "user_profiles.json schema valid", "File not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return _fail("IQ-007", "user_profiles.json schema valid", f"Invalid JSON: {e}")
    if "users" not in data:
        return _fail("IQ-007", "user_profiles.json schema valid", "Missing 'users' key")
    users = data["users"]
    if not isinstance(users, list) or len(users) == 0:
        return _fail("IQ-007", "user_profiles.json schema valid",
                     "'users' is empty or not a list")
    return _pass("IQ-007", "user_profiles.json schema valid",
                 f"{len(users)} user(s) found")


def check_iq008():
    """IQ-008: No conflicting Qt bindings (dev mode only)."""
    conflicts = []
    for binding in ("PyQt5", "PyQt6"):
        try:
            importlib.import_module(binding)
            conflicts.append(binding)
        except ImportError:
            pass
        except Exception as e:
            conflicts.append(f"{binding} ({e})")
    if not conflicts:
        return _pass("IQ-008", "No conflicting Qt bindings installed",
                     "PyQt5 and PyQt6 absent")
    return _fail("IQ-008", "No conflicting Qt bindings installed",
                 f"Found: {', '.join(conflicts)}")


def check_iq010():
    """IQ-010: OS is Windows x86-64."""
    os_name = platform.system()
    machine = platform.machine()
    detail = f"{os_name} / {machine}"
    if os_name == "Windows" and machine in ("AMD64", "x86_64"):
        return _pass("IQ-010", "OS is Windows x86-64", detail)
    return _fail("IQ-010", "OS is Windows x86-64", f"Got: {detail}")


def check_iq011():
    """IQ-011: Data directory is writable."""
    if IS_FROZEN:
        appdata = os.environ.get("APPDATA", "")
        test_dir = (Path(appdata) / "Affilabs" / "validation"
                    if appdata else INSTALL_DIR / "_data" / "validation")
    else:
        test_dir = INSTALL_DIR / "_data" / "validation"
    try:
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / ".iq_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return _pass("IQ-011", "Data directory is writable", str(test_dir))
    except Exception as e:
        return _fail("IQ-011", "Data directory is writable", f"{test_dir} -- {e}")


# -- Runner --------------------------------------------------------------------

def run_iq(operator: str, instrument_serial: str | None = None) -> dict:
    """Run all applicable IQ checks and return the full report dict."""
    if not instrument_serial:
        instrument_serial = _detect_serial()
    else:
        instrument_serial = _normalize_serial(instrument_serial)

    # Checks that always run (frozen + dev)
    always = [check_iq004, check_iq005, check_iq006,
               check_iq007, check_iq010, check_iq011]

    # Additional checks in dev/source mode only
    dev_only = [check_iq001, check_iq003, check_iq008]

    checks_to_run = (dev_only + always) if not IS_FROZEN else always

    results = []
    for fn in checks_to_run:
        try:
            results.append(fn())
        except Exception as e:
            results.append(_fail(fn.__name__, str(fn.__doc__ or ""), f"Exception: {e}"))

    # Deferred to v2
    results += [
        _skip("IQ-002", "All dependencies at pinned versions",
              "Requires locked requirements file -- deferred to v2"),
        _skip("IQ-009", "File integrity manifest (SHA-256)",
              "Requires build-time manifest -- deferred to v2"),
    ]

    sw_version = "UNKNOWN"
    for candidate in [INSTALL_DIR / "VERSION", BUNDLE_DIR / "VERSION"]:
        if candidate.exists():
            sw_version = candidate.read_text(encoding="utf-8").strip()
            break

    passed  = sum(1 for r in results if r["result"] == "PASS")
    failed  = sum(1 for r in results if r["result"] == "FAIL")
    skipped = sum(1 for r in results if r["result"] == "SKIP")

    return {
        "report_type": "IQ",
        "report_revision": "1.0",
        "software_version": sw_version,
        "instrument_serial": instrument_serial,
        "machine_hostname": platform.node(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "mode": "frozen" if IS_FROZEN else "source",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "overall": "PASS" if failed == 0 else "FAIL",
        "checks": results,
    }


def _report_dir() -> Path:
    if IS_FROZEN:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Affilabs" / "validation"
    return INSTALL_DIR / "_data" / "validation"


def save_report(report: dict, out_dir: Path | None = None) -> Path:
    target = out_dir or _report_dir()
    target.mkdir(parents=True, exist_ok=True)
    serial = report["instrument_serial"].replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = target / f"IQ_report_{serial}_{ts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def print_report(report: dict) -> None:
    sym = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}
    print()
    print("=" * 64)
    print("  Affilabs.core -- Installation Qualification (IQ)")
    print("=" * 64)
    print(f"  Software:   {report['software_version']}")
    print(f"  Serial:     {report['instrument_serial']}")
    print(f"  Operator:   {report['operator']}")
    print(f"  Machine:    {report['machine_hostname']}")
    print(f"  OS:         {report['os']}")
    print(f"  Timestamp:  {report['timestamp_utc']}")
    print("-" * 64)
    for check in report["checks"]:
        s = sym.get(check["result"], "[ ?? ]")
        print(f"  {s}  {check['id']:<10} {check['description']}")
        if check["result"] != "PASS" and check.get("detail"):
            print(f"            -> {check['detail']}")
    print("-" * 64)
    sm = report["summary"]
    print(f"  Passed: {sm['passed']}   Failed: {sm['failed']}   Skipped: {sm['skipped']}")
    print()
    if report["overall"] == "PASS":
        print("  OVERALL: PASS -- installation verified")
    else:
        print("  OVERALL: FAIL -- review items above before use")
    print("=" * 64)
    print()


# -- Entry point (standalone) -------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Affilabs.core Installation Qualification (IQ) check"
    )
    parser.add_argument("--operator", "-o",
                        default=os.environ.get("USERNAME", "Unknown"),
                        help="Name of the person running the IQ (default: OS username)")
    parser.add_argument("--serial", "-s", default=None,
                        help="Override instrument serial (default: auto-detected)")
    parser.add_argument("--out-dir", default=None,
                        help="Override report save directory")
    parser.add_argument("--no-save", action="store_true",
                        help="Print results but do not save report")
    args = parser.parse_args()

    report = run_iq(operator=args.operator, instrument_serial=args.serial)
    print_report(report)

    if not args.no_save:
        out_dir = Path(args.out_dir) if args.out_dir else None
        path = save_report(report, out_dir)
        print(f"  Report saved: {path}")
        print()

    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())