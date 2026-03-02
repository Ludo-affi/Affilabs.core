"""
Affilabs.core — OQ Runner
Operational Qualification runner: invokes all tests/oq/ suites via pytest,
collects results, and generates HTML + JSON qualification reports.

Usage:
    python scripts/validation/oq_runner.py
    python scripts/validation/oq_runner.py --operator "Lucia" --no-save
    python scripts/validation/oq_runner.py --out-dir /path/to/dir

Can also be triggered from:
    python main.py --oq-check [--operator NAME] [--no-save] [--out-dir PATH]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure repo root is on sys.path
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Pytest result collector plugin
# ---------------------------------------------------------------------------

class _OQResultCollector:
    """Minimal pytest plugin that captures test outcomes in memory."""

    def __init__(self) -> None:
        self.results: list[dict] = []
        self._start_times: dict[str, float] = {}

    def pytest_runtest_logstart(self, nodeid: str, location: tuple) -> None:
        self._start_times[nodeid] = time.monotonic()

    def pytest_runtest_logreport(self, report) -> None:
        if report.when != "call":
            # Only capture call phase (skip setup/teardown rows)
            # But capture setup failures too
            if report.when == "setup" and report.failed:
                pass
            else:
                return

        duration = time.monotonic() - self._start_times.get(report.nodeid, time.monotonic())

        # Extract req_id from @pytest.mark.req marker
        req_id = ""
        suite = ""
        # report.keywords is a dict of marker-name → marker object(s)
        keywords = getattr(report, "keywords", {})
        req_marker = keywords.get("req")
        if req_marker is not None:
            # Could be a MarkDecorator or a list; extract first arg
            try:
                args = getattr(req_marker, "args", None) or (req_marker[0].args if isinstance(req_marker, list) else ())
                if args:
                    req_id = args[0]
                    parts = req_id.rsplit("-", 1)
                    suite = parts[0] if len(parts) == 2 else req_id
            except (AttributeError, IndexError, TypeError):
                pass

        if not req_id:
            # Fall back to nodeid-derived name
            req_id = report.nodeid.split("::")[-1]
            suite = report.nodeid.split("/")[-1].replace("test_", "").replace(".py", "").upper().replace(".PY", "")

        if report.passed:
            result = "PASS"
            detail = ""
        elif report.failed:
            result = "FAIL"
            detail = str(report.longreprtext) if hasattr(report, "longreprtext") else str(report.longrepr)
            # Trim to first 300 chars for the report
            detail = detail.strip()[:300]
        else:
            result = "SKIP"
            detail = str(report.longrepr) if report.longrepr else ""

        # Extract description from test docstring via nodeid → function name
        description = req_id  # fallback
        node_name = report.nodeid.split("::")[-1]
        description = node_name.replace("_", " ").strip()

        self.results.append({
            "req_id": req_id,
            "suite": suite,
            "description": description,
            "result": result,
            "detail": detail,
            "duration_s": round(duration, 3),
        })


# ---------------------------------------------------------------------------
# Instrument serial detection (same logic as iq_check.py)
# ---------------------------------------------------------------------------

def _detect_serial() -> str:
    devices_dir = ROOT / "config" / "devices"
    if devices_dir.is_dir():
        subdirs = [d for d in devices_dir.iterdir() if d.is_dir()]
        if subdirs:
            subdirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            return subdirs[0].name
    return "Unknown"


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run_oq(
    operator: str = "",
    serial_override: str | None = None,
    no_save: bool = False,
    out_dir: Path | None = None,
) -> dict:
    """
    Run all OQ test suites and return the report dict.
    Also saves HTML + JSON reports to _data/validation/ unless no_save=True.
    """
    import pytest

    from scripts.validation.report_generator import (
        CheckResult,
        generate_json,
        save_html,
        save_json,
    )

    oq_dir = ROOT / "tests" / "oq"
    if not oq_dir.is_dir():
        print(f"[OQ] ERROR: tests/oq/ not found at {oq_dir}", file=sys.stderr)
        sys.exit(1)

    collector = _OQResultCollector()

    # Run pytest programmatically
    exit_code = pytest.main(
        [
            str(oq_dir),
            "-v",
            "--tb=short",
            "--no-header",
            "-p", "no:cacheprovider",
        ],
        plugins=[collector],
    )

    # Build CheckResult list from collector
    checks = [
        CheckResult(
            req_id=r["req_id"],
            description=r["description"],
            result=r["result"],
            detail=r["detail"],
            suite=r["suite"],
            duration_s=r["duration_s"],
        )
        for r in collector.results
    ]

    # Resolve version
    version_path = ROOT / "VERSION"
    software_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "Unknown"

    serial = serial_override or _detect_serial()

    report = generate_json(
        checks=checks,
        report_type="OQ",
        software_version=software_version,
        operator=operator,
        instrument_serial=serial,
    )

    # Console summary
    summary = report["summary"]
    overall = report["overall"]
    _print_summary(report, checks)

    if not no_save:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if out_dir is None:
            out_dir = ROOT / "_data" / "validation"
        out_dir = Path(out_dir)

        json_path = out_dir / f"OQ_report_{serial}_{ts}.json"
        html_path = out_dir / f"OQ_report_{serial}_{ts}.html"

        save_json(report, json_path)
        save_html(report, html_path)

        print(f"\n[OQ] Reports saved:")
        print(f"     JSON: {json_path}")
        print(f"     HTML: {html_path}")

    return report


# ---------------------------------------------------------------------------
# Console pretty-print
# ---------------------------------------------------------------------------

def _print_summary(report: dict, checks: list) -> None:
    summary = report["summary"]
    overall = report["overall"]

    width = 72
    print("\n" + "=" * width)
    print(f"  Affilabs.core OQ Report  —  v{report['software_version']}")
    print(f"  Instrument: {report['instrument_serial']}  |  {report['timestamp_utc'][:19]}Z")
    print("=" * width)

    if checks:
        suite_col_w = max(len(c.suite) for c in checks) + 2
        for c in checks:
            tick = "[+]" if c.result == "PASS" else ("[!]" if c.result == "FAIL" else "[ ]")
            suite_pad = c.suite.ljust(suite_col_w)
            print(f"  {tick}  {c.req_id:<16}  {suite_pad}  {c.description}")
            if c.result == "FAIL" and c.detail:
                # Indent failure detail
                for line in c.detail.splitlines()[:5]:
                    print(f"       | {line}")

    print("-" * width)
    print(f"  PASSED: {summary['passed']}   FAILED: {summary['failed']}   SKIPPED: {summary['skipped']}")
    print(f"  OVERALL: {overall}")
    print("=" * width)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Affilabs.core OQ Runner — Operational Qualification",
    )
    parser.add_argument("--operator", default="", help="Operator name for report")
    parser.add_argument("--serial", default=None, help="Override instrument serial")
    parser.add_argument("--no-save", action="store_true", help="Print only, do not save reports")
    parser.add_argument("--out-dir", default=None, help="Directory for report output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else None
    report = run_oq(
        operator=args.operator,
        serial_override=args.serial,
        no_save=args.no_save,
        out_dir=out_dir,
    )
    sys.exit(0 if report["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
