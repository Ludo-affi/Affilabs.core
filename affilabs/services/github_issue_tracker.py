"""GitHub Issue Tracker — OEM internal bug/issue management.

Creates and lists GitHub Issues via the REST API.
Credentials are loaded from .env (same file as bug_reporter):
  GITHUB_TOKEN   — Personal access token (repo scope)
  GITHUB_REPO    — owner/repo  e.g. "affinityinstruments/affilabs-core"

Labels are auto-created on first use via ensure_labels().
"""

import json
import logging
import os
import platform
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Load credentials from .env ────────────────────────────────────────────────
def _load_env() -> None:
    env_path = Path(__file__).parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

_load_env()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")   # owner/repo

API_BASE = "https://api.github.com"

# Label definitions: (name, color_hex, description)
SEVERITY_LABELS = [
    ("severity:critical", "d73a4a", "Crashes or data loss"),
    ("severity:high",     "e4606d", "Major feature broken"),
    ("severity:medium",   "fbca04", "Degraded functionality"),
    ("severity:low",      "0075ca", "Minor / cosmetic"),
]
COMPONENT_LABELS = [
    ("comp:spark",       "7057ff", "Spark AI assistant"),
    ("comp:pump",        "008672", "Pump control & fluidics"),
    ("comp:calibration", "e4e669", "Calibration system"),
    ("comp:ui",          "d876e3", "UI / widgets / dialogs"),
    ("comp:hardware",    "0052cc", "Hardware comms / HAL"),
    ("comp:acquisition", "1d76db", "Data acquisition / spectrometer"),
    ("comp:recording",   "5319e7", "Recording & export"),
    ("comp:other",       "cfd3d7", "Uncategorised"),
]
ALL_LABELS = SEVERITY_LABELS + COMPONENT_LABELS

LOG_TAIL_LINES = 80
# ─────────────────────────────────────────────────────────────────────────────


def _is_configured() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "Affilabs-Core-IssueTracker/1.0",
    }


def _api(method: str, path: str, body: dict | None = None) -> object:
    """Make a GitHub API request. Returns parsed JSON or raises on error."""
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Public API ────────────────────────────────────────────────────────────────

def ensure_configured() -> tuple[bool, str]:
    """Return (ok, error_message)."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN not set in .env"
    if not GITHUB_REPO:
        return False, "GITHUB_REPO not set in .env (expected: owner/repo)"
    return True, ""


def ensure_labels() -> None:
    """Create any missing labels in the repo. Safe to call repeatedly."""
    ok, err = ensure_configured()
    if not ok:
        logger.warning(f"Label sync skipped: {err}")
        return
    try:
        existing_raw = _api("GET", f"/repos/{GITHUB_REPO}/labels?per_page=100")
        assert isinstance(existing_raw, list)
        existing = {lbl["name"] for lbl in existing_raw}
        for name, color, description in ALL_LABELS:
            if name not in existing:
                _api("POST", f"/repos/{GITHUB_REPO}/labels", {
                    "name": name,
                    "color": color,
                    "description": description,
                })
                logger.info(f"Created label: {name}")
    except Exception as e:
        logger.warning(f"ensure_labels() failed (non-fatal): {e}")


def list_issues(state: str = "open") -> list[dict]:
    """Return list of issues. Each dict has: number, title, state, labels, html_url, created_at, body."""
    ok, err = ensure_configured()
    if not ok:
        raise RuntimeError(err)
    raw = _api("GET", f"/repos/{GITHUB_REPO}/issues?state={state}&per_page=50&sort=created&direction=desc")
    assert isinstance(raw, list)
    # Filter out pull requests (GitHub returns PRs in issues endpoint)
    return [i for i in raw if "pull_request" not in i]


def create_issue(
    title: str,
    description: str,
    severity: str,
    component: str,
    include_log: bool = True,
    screenshot_path: str | None = None,
) -> tuple[int, str]:
    """Create a GitHub issue. Returns (issue_number, html_url)."""
    ok, err = ensure_configured()
    if not ok:
        raise RuntimeError(err)

    # ── Build body ─────────────────────────────────────────────────────────
    from version import __version__
    lines = [
        f"## Description\n{description}\n",
        f"## Environment",
        f"| Field | Value |",
        f"| --- | --- |",
        f"| Version | `{__version__}` |",
        f"| OS | `{platform.platform()}` |",
        f"| Python | `{platform.python_version()}` |",
        f"| Reported | `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` |",
        "",
    ]

    if screenshot_path:
        lines += [
            f"## Screenshot",
            f"*Local path:* `{screenshot_path}`",
            "",
        ]

    if include_log:
        log_tail = _read_log_tail()
        if log_tail:
            lines += [
                "<details>",
                "<summary>Log tail (last 80 lines)</summary>\n",
                "```",
                log_tail,
                "```",
                "</details>",
                "",
            ]

    body = "\n".join(lines)

    # ── Labels ─────────────────────────────────────────────────────────────
    labels = []
    if severity:
        labels.append(f"severity:{severity}")
    if component:
        labels.append(f"comp:{component}")

    result = _api("POST", f"/repos/{GITHUB_REPO}/issues", {
        "title": title,
        "body": body,
        "labels": labels,
    })
    assert isinstance(result, dict)
    return int(result["number"]), str(result["html_url"])


def close_issue(number: int) -> None:
    """Close an issue by number."""
    ok, err = ensure_configured()
    if not ok:
        raise RuntimeError(err)
    _api("PATCH", f"/repos/{GITHUB_REPO}/issues/{number}", {"state": "closed"})


def reopen_issue(number: int) -> None:
    """Reopen a closed issue."""
    ok, err = ensure_configured()
    if not ok:
        raise RuntimeError(err)
    _api("PATCH", f"/repos/{GITHUB_REPO}/issues/{number}", {"state": "open"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_log_tail(n: int = LOG_TAIL_LINES) -> str:
    """Return last n lines of the most recent log file."""
    try:
        log_dir = Path("logs")
        candidates = list(Path(".").glob("*.log")) + list(log_dir.glob("*.log")) if log_dir.exists() else list(Path(".").glob("*.log"))
        if not candidates:
            # Also try logfile.txt
            lt = Path("logfile.txt")
            if lt.exists():
                candidates = [lt]
        if not candidates:
            return ""
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        lines = latest.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        logger.debug(f"Log tail read failed: {e}")
        return ""


def take_screenshot_to_file() -> str | None:
    """Capture the app window, save to _data/issue_screenshots/, return path or None."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return None

        # Find the main window
        main_win = None
        for w in app.topLevelWidgets():
            if w.isVisible() and w.width() > 400:
                main_win = w
                break
        if not main_win:
            return None

        screen = main_win.screen()
        pixmap = screen.grabWindow(main_win.winId())

        out_dir = Path("_data") / "issue_screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"issue_{ts}.png"
        pixmap.save(str(path), "PNG")
        return str(path)
    except Exception as e:
        logger.debug(f"Screenshot failed: {e}")
        return None
