"""Bug Reporter Service — Generate Email Drafts

Creates formatted email drafts for bug reports that users can copy and send manually.
No SMTP credentials or email sending required.

Each report includes:
  - User's description
  - Screenshot (saved separately, user attaches manually)
  - Last 100 lines from the most recent log file
  - System info (OS, software version, hardware serial)
"""

import logging
import platform
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_TAIL_LINES = 100
SUPPORT_EMAIL = "info@affiniteinstruments.com"


def _find_latest_log() -> Path | None:
    """Return path to the most recently modified .log file under logs/."""
    log_dir = Path("logs")
    if not log_dir.exists():
        # Fallback: root directory
        candidates = list(Path(".").glob("*.log"))
    else:
        candidates = list(log_dir.glob("*.log"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_log_tail(log_path: Path, n: int = LOG_TAIL_LINES) -> str:
    """Read last n lines from a log file safely."""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"[Could not read log: {e}]"


def _system_info() -> str:
    """Build a short system info block."""
    try:
        from version import __version__
        version = __version__
    except Exception:
        version = "unknown"

    lines = [
        f"Version : {version}",
        f"OS      : {platform.platform()}",
        f"Python  : {sys.version.split()[0]}",
        f"Machine : {platform.machine()}",
        f"Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    # Hardware serial if available
    try:
        from affilabs.utils.settings_helpers import get_setting
        serial = get_setting("device_serial", None)
        if serial:
            lines.append(f"Serial  : {serial}")
    except Exception:
        pass

    return "\n".join(lines)


def _take_screenshot() -> tuple[bytes | None, str]:
    """Capture the main application window as PNG bytes.
    
    Returns:
        (png_bytes, filename) tuple where png_bytes is None on failure.
    """
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QBuffer, QIODevice
        
        app = QApplication.instance()
        if app is None:
            return None, ""
        
        windows = [w for w in app.topLevelWidgets() if w.isVisible()]
        if not windows:
            return None, ""
        
        target = max(windows, key=lambda w: w.width() * w.height())
        pixmap = target.grab()
        
        buf = QBuffer()
        buf.open(QIODevice.OpenMode.WriteOnly)
        pixmap.save(buf, "PNG")
        
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        return bytes(buf.data()), filename
    except Exception as e:
        logger.warning(f"Screenshot failed: {e}")
        return None, ""


def is_configured() -> bool:
    """Check if bug reporter is configured (always True now — no config needed)."""
    return True


def save_screenshot(output_dir: Path | None = None) -> Path | None:
    """Save a screenshot to disk and return its path.
    
    Args:
        output_dir: Directory to save screenshot. Defaults to _data directory.
    
    Returns:
        Path to saved screenshot, or None on failure.
    """
    png_bytes, filename = _take_screenshot()
    if not png_bytes or not filename:
        return None
    
    if output_dir is None:
        output_dir = Path("_data")
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / filename
    try:
        filepath.write_bytes(png_bytes)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")
        return None


def generate_bug_report_draft(
    description: str,
    user_name: str = "",
) -> str:
    """Generate an email draft for a bug report.
    
    Args:
        description: User's bug description.
        user_name: Display name of the reporter (optional).
    
    Returns:
        Formatted email text ready to copy and send.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[Affilabs Bug] {timestamp} — {user_name or 'beta user'}"
    
    sys_info = _system_info()
    log_path = _find_latest_log()
    log_tail = _read_log_tail(log_path) if log_path else "[No log file found]"
    log_filename = log_path.name if log_path else "no_log.txt"
    
    # ── Build email body ──────────────────────────────────────────────────
    body = f"""Subject: {subject}
To: {SUPPORT_EMAIL}

════════════════════════════════════════════════════════════════════════════════
BUG REPORT — Affilabs.core
════════════════════════════════════════════════════════════════════════════════

Reporter : {user_name or "anonymous"}
Submitted: {timestamp}

DESCRIPTION
───────────────────────────────────────────────────────────────────────────────
{description}

SYSTEM INFO
───────────────────────────────────────────────────────────────────────────────
{sys_info}

LOG TAIL ({LOG_TAIL_LINES} lines from {log_filename})
───────────────────────────────────────────────────────────────────────────────
{log_tail}

════════════════════════════════════════════════════════════════════════════════
INSTRUCTIONS FOR SENDER:

1. Copy all text above (Ctrl+A, then Ctrl+C)
2. Open your email client
3. Compose a new email
4. Paste the text (Ctrl+V)
5. Review the information
6. Attach a screenshot (if you saved one) to the email
7. Send to: {SUPPORT_EMAIL}

DO NOT include passwords, personal data, or experiment results.
════════════════════════════════════════════════════════════════════════════════
"""
    
    logger.info(f"Generated bug report draft: {subject}")
    return body


def send_bug_report(
    description: str,
    user_name: str = "",
    include_screenshot: bool = True,
    additional_images: list[str] = None,
) -> tuple[bool, str]:
    """Generate a bug report draft and optionally save a screenshot.

    Args:
        description: User's bug description.
        user_name: Display name of the reporter (optional).
        include_screenshot: Whether to save a screenshot.
        additional_images: List of image file paths (saved alongside draft).

    Returns:
        (True, draft_text) tuple. Draft text is ready for user to copy and email.
    """
    draft = generate_bug_report_draft(description, user_name)

    results = [draft]

    # Optionally save screenshot
    if include_screenshot:
        screenshot_path = save_screenshot()
        if screenshot_path:
            results.append(f"\n✅ Screenshot saved: {screenshot_path.relative_to(Path.cwd())}")
        else:
            results.append("\n⚠️ Screenshot could not be captured.")

    # Save any additional images
    if additional_images:
        results.append("\nAdditional images provided by user:")
        for i, img_path in enumerate(additional_images, 1):
            img_path_obj = Path(img_path)
            if img_path_obj.exists():
                results.append(f"  {i}. {img_path_obj.name}")
            else:
                results.append(f"  {i}. {img_path} (not found)")

    full_output = "\n".join(results)
    return (True, full_output)


def send_bug_report_auto(
    description: str,
    user_name: str = "",
    screenshot_bytes: bytes | None = None,
    additional_images: list[str] = None,
    report_type: str = "bug",
) -> tuple[bool, str, str]:
    """Try to auto-submit bug report via Sparq Coach backend; fall back to draft on failure.

    Args:
        description: User's bug description.
        user_name: Display name of the reporter (optional).
        screenshot_bytes: Pre-captured screenshot PNG bytes (must be taken on main thread).
            If None, attempts to capture here (only safe when called from main thread).
        additional_images: List of extra image file paths to attach.
        report_type: 'bug' (default) or 'support_request' for Sparq unanswered questions.

    Returns:
        (auto_submitted, mode, result)
        - auto_submitted=True,  mode='auto',  result=ticket_id    → cloud submit OK
        - auto_submitted=False, mode='draft', result=draft_text   → fallback copy-paste
        - auto_submitted=False, mode='limit', result=message      → rate limited
    """
    # Use caller-provided screenshot; only capture here if not provided
    if screenshot_bytes is None:
        screenshot_bytes, _ = _take_screenshot()

    # Try cloud submission first
    try:
        from affilabs.services.sparq_coach_service import SparqCoachService
        svc = SparqCoachService()
        if svc.is_available():
            ok, result = svc.submit_bug_report(
                description,
                user_name=user_name,
                screenshot_bytes=screenshot_bytes,
                additional_images=additional_images,
                report_type=report_type,
            )
            if ok:
                return True, "auto", result
            if result == "report_limit_reached":
                return False, "limit", (
                    "You've reached today's bug report limit (10/day). "
                    "Email info@affiniteinstruments.com directly."
                )
            if result == "auth_failed":
                return False, "draft", generate_bug_report_draft(description, user_name)
            # Any other failure (offline, timeout, server error) → fall through to draft
    except Exception as e:
        logger.warning(f"send_bug_report_auto: service call failed: {e}")

    # Fallback: generate a copy-paste draft and also save screenshot to disk
    draft = generate_bug_report_draft(description, user_name)
    if screenshot_bytes:
        save_screenshot()   # saves to _data/ for user to attach manually
    return False, "draft", draft
