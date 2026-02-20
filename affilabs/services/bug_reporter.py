"""Bug Reporter Service

Sends beta user bug reports via email (SMTP).
Each report contains:
  - User's description
  - Screenshot of the app window (PNG attachment)
  - Last 100 lines of the most recent log file
  - System info (OS, software version, hardware serial)

Credentials are loaded from .env (never hardcoded).
.env lives next to main.py and is gitignored.
"""

import logging
import os
import platform
import smtplib
import sys
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Load credentials from .env ────────────────────────────────────────────────
def _load_env():
    """Read key=value pairs from .env next to main.py into os.environ (if not already set)."""
    env_path = Path(__file__).parents[2] / ".env"   # project root
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

SMTP_FROM     = os.environ.get("SMTP_FROM", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_TO       = os.environ.get("SMTP_TO", "info@affiniteinstruments.com")
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

LOG_TAIL_LINES = 100
# ─────────────────────────────────────────────────────────────────────────────


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


def _take_screenshot() -> bytes | None:
    """Capture the main application window as PNG bytes. Returns None on failure."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        app = QApplication.instance()
        if app is None:
            return None
        # Find the main (top-level) window
        windows = [w for w in app.topLevelWidgets() if w.isVisible()]
        if not windows:
            return None
        target = max(windows, key=lambda w: w.width() * w.height())
        pixmap = target.grab()
        # Encode to PNG in memory
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenMode.WriteOnly)
        pixmap.save(buf, "PNG")
        return bytes(buf.data())
    except Exception as e:
        logger.warning(f"Screenshot failed: {e}")
        return None


def send_bug_report(
    description: str,
    user_name: str = "",
    include_screenshot: bool = True,
    additional_images: list[str] = None,
) -> tuple[bool, str]:
    """Compose and send a bug report email.

    Args:
        description: Free-text description from the user.
        user_name: Display name of the beta user (optional).
        include_screenshot: Whether to attach a screenshot.
        additional_images: List of image file paths to attach.

    Returns:
        (success, message) tuple.
    """
    # Validate SMTP credentials before attempting to send
    if not SMTP_FROM or not SMTP_PASSWORD:
        error_msg = (
            "Bug reporter not configured. "
            "Copy .env.example to .env and add your SMTP credentials."
        )
        logger.error(error_msg)
        return (False, "Email not configured. Contact support at info@affiniteinstruments.com")

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"[Affilabs Bug] {timestamp} — {user_name or 'beta user'}"

        sys_info = _system_info()
        log_path = _find_latest_log()
        log_tail = _read_log_tail(log_path) if log_path else "[No log file found]"
        log_filename = log_path.name if log_path else "no_log.txt"

        # ── Build email body ──────────────────────────────────────────────────
        body = f"""Bug Report — Affilabs.core Beta
{"=" * 50}

Reporter : {user_name or "anonymous"}
Submitted: {timestamp}

DESCRIPTION
-----------
{description}

SYSTEM INFO
-----------
{sys_info}

LOG TAIL ({LOG_TAIL_LINES} lines from {log_filename})
-----------
{log_tail}
"""

        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = SMTP_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # ── Screenshot attachment ─────────────────────────────────────────────
        if include_screenshot:
            png_bytes = _take_screenshot()
            if png_bytes:
                part = MIMEBase("image", "png")
                part.set_payload(png_bytes)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"screenshot_{datetime.now().strftime('%H%M%S')}.png",
                )
                msg.attach(part)

        # ── Additional user images ────────────────────────────────────────────
        if additional_images:
            for i, img_path in enumerate(additional_images):
                try:
                    img_path_obj = Path(img_path)
                    if img_path_obj.exists():
                        with open(img_path_obj, "rb") as f:
                            img_data = f.read()
                        # Determine MIME subtype from extension
                        ext = img_path_obj.suffix.lower().lstrip('.')
                        if ext in ('jpg', 'jpeg'):
                            subtype = 'jpeg'
                        elif ext == 'png':
                            subtype = 'png'
                        elif ext == 'gif':
                            subtype = 'gif'
                        elif ext == 'bmp':
                            subtype = 'bmp'
                        else:
                            subtype = 'png'  # fallback
                        
                        part = MIMEBase("image", subtype)
                        part.set_payload(img_data)
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            "attachment",
                            filename=f"user_image_{i+1}_{img_path_obj.name}",
                        )
                        msg.attach(part)
                except Exception as e:
                    logger.warning(f"Failed to attach image {img_path}: {e}")

        # ── Send ─────────────────────────────────────────────────────────────
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_FROM, SMTP_PASSWORD)
            smtp.sendmail(SMTP_FROM, SMTP_TO, msg.as_bytes())

        logger.info(f"Bug report sent: {subject}")
        return (True, "Report sent — thank you!")

    except smtplib.SMTPAuthenticationError:
        error_msg = (
            "SMTP authentication failed. Check your credentials in .env:\n"
            "- For Gmail, use an App Password (not your regular password)\n"
            "- Generate at: https://myaccount.google.com/apppasswords\n"
            f"- Current SMTP_FROM: {SMTP_FROM}"
        )
        logger.error(error_msg)
        return (False, "Email authentication failed. Check .env credentials or contact support.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending bug report: {e}")
        return (False, f"Email error: {e}")
    except Exception as e:
        logger.error(f"Bug report failed: {e}", exc_info=True)
        return (False, f"Unexpected error: {e}")
