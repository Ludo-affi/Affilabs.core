import contextlib
import io
import logging
import os
import sys
import threading
from logging import Formatter
from logging.handlers import RotatingFileHandler

from settings import ROOT_DIR

# Save logfile in generated-files directory
# ROOT_DIR already points to "generated-files", no need to append it again
os.makedirs(ROOT_DIR, exist_ok=True)
log_fname = os.path.join(ROOT_DIR, "logfile.txt")

# Runtime flags (can be overridden via environment variables)
# FORCE thread filtering ON by default to prevent Qt threading crashes from worker threads
ENABLE_THREAD_FILTERING = os.environ.get("AFFILABS_THREAD_FILTER", "1") not in (
    "0",
    "false",
    "False",
)
# Temporarily disable console emoji stripping/wrapping to avoid TypeError on Windows
ENABLE_EMOJI_STRIP = False

# Windows console fix: Replace stdout/stderr to prevent Unicode crashes
if ENABLE_EMOJI_STRIP:

    class SafeWriter(io.TextIOWrapper):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._closed = False

        def write(self, text):
            # Check if closed
            if self._closed:
                return None

            # Handle both str and bytes
            if isinstance(text, bytes):
                # Decode bytes first
                text = text.decode("utf-8", errors="replace")
            elif not isinstance(text, str):
                # Convert other types to string
                text = str(text)

            # Strip emoji/special characters for Windows console
            try:
                text = text.encode("cp1252", errors="ignore").decode("cp1252")
            except (AttributeError, TypeError):
                # If text is still somehow not a string, force convert
                text = str(text)

            # Final safety check - ensure text is definitely a string before calling parent
            if not isinstance(text, str):
                text = str(text)

            try:
                return super().write(text)
            except (ValueError, OSError, AttributeError):
                # Stream is closed during shutdown
                self._closed = True
            except TypeError:
                # Emergency fallback if we still get bytes somehow
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                    try:
                        return super().write(text)
                    except (ValueError, OSError, AttributeError):
                        self._closed = True
                else:
                    raise

        def flush(self):
            if self._closed:
                return None
            try:
                return super().flush()
            except (ValueError, OSError, AttributeError):
                self._closed = True

    sys.stdout = SafeWriter(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="ignore",
        line_buffering=True,
    )
    sys.stderr = SafeWriter(
        sys.stderr.buffer,
        encoding="utf-8",
        errors="ignore",
        line_buffering=True,
    )


def _resolve_record(record) -> None:
    """Resolve record.msg % record.args in-place, then clear args.

    Must be called before any format() call so that RotatingFileHandler.shouldRollover()
    (which calls format() internally) and the actual emit format() call both see a
    pre-resolved msg with no args — preventing double-format TypeError/ValueError.
    """
    if record.args:
        try:
            record.msg = str(record.msg) % record.args
        except Exception:
            # If formatting fails, stringify everything safely so the message
            # still appears in the log rather than silently vanishing.
            try:
                record.msg = f"{record.msg!r} % {record.args!r}"
            except Exception:
                record.msg = repr(record.msg)
        record.args = None


class SafeConsoleFormatter(Formatter):
    """Formatter that optionally removes emojis/special chars for Windows console compatibility."""

    def format(self, record):
        _resolve_record(record)
        msg = super().format(record)
        if ENABLE_EMOJI_STRIP:
            msg = msg.encode("cp1252", errors="ignore").decode("cp1252")
        return msg


class _SafeFormatter(Formatter):
    """Resolve msg % args once so double-format (RotatingFileHandler.shouldRollover) never raises."""

    def format(self, record):
        _resolve_record(record)
        return super().format(record)


log_formatter = _SafeFormatter(fmt="%(asctime)s :: %(levelname)s :: %(message)s")
safe_console_formatter = SafeConsoleFormatter(
    fmt="%(asctime)s :: %(levelname)s :: %(message)s",
)

# Use RotatingFileHandler to prevent log file from growing unbounded
# maxBytes=10MB: Rotate when log hits 10MB
# backupCount=5: Keep last 5 rotated files (logfile.txt.1 through logfile.txt.5)
# This caps total log disk usage at ~60MB across all files
file_handler = RotatingFileHandler(
    filename=log_fname,
    mode="a",
    encoding="utf8",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
)
file_handler.setLevel(logging.INFO)  # Reduce disk I/O overhead (was DEBUG)
file_handler.setFormatter(fmt=log_formatter)

_MAIN_THREAD_ID = threading.main_thread().ident


class ConditionalThreadFilterConsoleHandler(logging.StreamHandler):
    """Console handler that can optionally filter out non-main-thread logs.

    Controlled by ENABLE_THREAD_FILTERING flag (env AFFILABS_THREAD_FILTER=1 to enable).
    """

    def emit(self, record) -> None:
        if (
            ENABLE_THREAD_FILTERING
            and threading.current_thread().ident != _MAIN_THREAD_ID
        ):
            return
        try:
            super().emit(record)
        except Exception:
            # Catch all emit errors: UnicodeEncodeError on Windows console,
            # ValueError/OSError on stream close during shutdown, etc.
            with contextlib.suppress(Exception):
                self.flush()


console_handler = ConditionalThreadFilterConsoleHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Reduce console spam (DEBUG still goes to file)
console_handler.setFormatter(fmt=safe_console_formatter)

logger = logging.getLogger("LOG")
logger.setLevel(logging.DEBUG)

# Only add handlers if they haven't been added yet (prevent duplicates)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
logger.propagate = False


def enable_verbose_console() -> None:
    """Programmatically disable thread filtering and emoji stripping then raise console level."""
    global ENABLE_THREAD_FILTERING, ENABLE_EMOJI_STRIP
    ENABLE_THREAD_FILTERING = False
    ENABLE_EMOJI_STRIP = False
    console_handler.setLevel(logging.DEBUG)
