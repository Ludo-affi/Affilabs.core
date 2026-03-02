"""
Affilabs.core — Qualification Report Generator
Shared HTML + JSON report builder for IQ and OQ reports.

Usage (from oq_runner.py):
    from scripts.validation.report_generator import generate_html, generate_json
"""
from __future__ import annotations

import json
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CheckResult:
    """One row in a qualification report."""

    def __init__(
        self,
        req_id: str,
        description: str,
        result: str,  # "PASS" | "FAIL" | "SKIP" | "ERROR"
        detail: str = "",
        suite: str = "",
        duration_s: float = 0.0,
    ) -> None:
        self.req_id = req_id
        self.description = description
        self.result = result
        self.detail = detail
        self.suite = suite
        self.duration_s = duration_s

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.req_id,
            "suite": self.suite,
            "description": self.description,
            "result": self.result,
            "detail": self.detail,
            "duration_s": round(self.duration_s, 3),
        }


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def generate_json(
    checks: list[CheckResult],
    report_type: str,
    software_version: str,
    operator: str = "",
    instrument_serial: str = "Unknown",
) -> dict[str, Any]:
    """Build the qualification report dict (suitable for json.dumps)."""
    passed = sum(1 for c in checks if c.result == "PASS")
    failed = sum(1 for c in checks if c.result == "FAIL")
    skipped = sum(1 for c in checks if c.result in ("SKIP", "ERROR"))

    return {
        "report_type": report_type,
        "report_revision": "1.0",
        "software_version": software_version,
        "instrument_serial": instrument_serial,
        "machine_hostname": socket.gethostname(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "summary": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": len(checks),
        },
        "overall": "PASS" if failed == 0 and len(checks) > 0 else "FAIL",
        "checks": [c.as_dict() for c in checks],
    }


def save_json(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_RESULT_COLOR = {
    "PASS": "#2e7d32",
    "FAIL": "#c62828",
    "SKIP": "#757575",
    "ERROR": "#e65100",
}

_RESULT_BG = {
    "PASS": "#e8f5e9",
    "FAIL": "#ffebee",
    "SKIP": "#f5f5f5",
    "ERROR": "#fff3e0",
}


def generate_html(report: dict[str, Any]) -> str:
    """Convert a report dict (from generate_json) to a printable HTML string."""
    checks = report["checks"]
    summary = report["summary"]
    overall = report["overall"]
    overall_color = _RESULT_COLOR.get(overall, "#000")

    # Group by suite
    suites: dict[str, list[dict]] = {}
    for c in checks:
        suite = c.get("suite") or "General"
        suites.setdefault(suite, []).append(c)

    # Suite summary rows
    suite_rows = ""
    for suite_name, suite_checks in suites.items():
        p = sum(1 for c in suite_checks if c["result"] == "PASS")
        f = sum(1 for c in suite_checks if c["result"] == "FAIL")
        s = len(suite_checks) - p - f
        suite_rows += (
            f"<tr><td>{suite_name}</td><td style='color:{_RESULT_COLOR['PASS']}'>{p}</td>"
            f"<td style='color:{_RESULT_COLOR['FAIL']}'>{f}</td>"
            f"<td style='color:{_RESULT_COLOR['SKIP']}'>{s}</td></tr>\n"
        )

    # Detail rows
    detail_rows = ""
    for c in checks:
        res = c["result"]
        bg = _RESULT_BG.get(res, "#fff")
        color = _RESULT_COLOR.get(res, "#000")
        detail = c.get("detail", "").replace("<", "&lt;").replace(">", "&gt;")
        dur = f"{c.get('duration_s', 0.0):.3f}s"
        detail_rows += (
            f"<tr style='background:{bg}'>"
            f"<td><code>{c['id']}</code></td>"
            f"<td>{c.get('suite','')}</td>"
            f"<td>{c['description']}</td>"
            f"<td style='color:{color};font-weight:bold'>{res}</td>"
            f"<td>{dur}</td>"
            f"<td style='font-size:0.85em'>{detail}</td>"
            f"</tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Affilabs.core {report['report_type']} Report — {report['software_version']}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 14px; margin: 40px; color: #222; }}
  h1 {{ color: #1a237e; }}
  h2 {{ color: #283593; margin-top: 28px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
  th {{ background: #3949ab; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  .overall {{ font-size: 1.4em; font-weight: bold; color: {overall_color}; }}
  .meta td {{ width: 200px; font-weight: bold; }}
  code {{ background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
  .footer {{ margin-top: 40px; font-size: 0.8em; color: #888; }}
</style>
</head>
<body>
<h1>Affilabs.core — {report['report_type']} Report</h1>

<table class="meta">
  <tr><td>Software Version</td><td>{report['software_version']}</td></tr>
  <tr><td>Instrument Serial</td><td>{report['instrument_serial']}</td></tr>
  <tr><td>Hostname</td><td>{report['machine_hostname']}</td></tr>
  <tr><td>OS</td><td>{report['os']}</td></tr>
  <tr><td>Python</td><td>{report['python_version']}</td></tr>
  <tr><td>Timestamp (UTC)</td><td>{report['timestamp_utc']}</td></tr>
  <tr><td>Operator</td><td>{report.get('operator') or '—'}</td></tr>
  <tr><td>Overall Result</td><td class="overall">{overall}</td></tr>
</table>

<h2>Summary by Suite</h2>
<table>
  <tr><th>Suite</th><th>PASS</th><th>FAIL</th><th>SKIP/ERROR</th></tr>
  <tr><td><strong>TOTAL</strong></td>
      <td style='color:{_RESULT_COLOR["PASS"]}'><strong>{summary['passed']}</strong></td>
      <td style='color:{_RESULT_COLOR["FAIL"]}'><strong>{summary['failed']}</strong></td>
      <td style='color:{_RESULT_COLOR["SKIP"]}'><strong>{summary['skipped']}</strong></td></tr>
  {suite_rows}
</table>

<h2>Check Details</h2>
<table>
  <tr><th>ID</th><th>Suite</th><th>Description</th><th>Result</th><th>Duration</th><th>Detail</th></tr>
  {detail_rows}
</table>

<div class="footer">
  Generated by Affilabs.core validation framework · {report['timestamp_utc']}<br>
  &copy; Affilabs Inc. — Confidential
</div>
</body>
</html>"""
    return html


def save_html(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(generate_html(report), encoding="utf-8")
