import os
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler
from logging import Formatter

from settings import ROOT_DIR

log_fname = os.path.join(ROOT_DIR, "logfile.txt")

# Runtime flags (can be overridden via environment variables)
# FORCE thread filtering ON by default to prevent Qt threading crashes from worker threads
ENABLE_THREAD_FILTERING = os.environ.get("AFFILABS_THREAD_FILTER", "1") not in ("0", "false", "False")
ENABLE_EMOJI_STRIP = sys.platform == 'win32' and os.environ.get("AFFILABS_EMOJI_STRIP", "1") not in ("0","false","False")

class SafeConsoleFormatter(Formatter):
    """Formatter that optionally removes emojis/special chars for Windows console compatibility."""
    def format(self, record):
        msg = super().format(record)
        if ENABLE_EMOJI_STRIP:
            msg = msg.encode('cp1252', errors='ignore').decode('cp1252')
        return msg

log_formatter = Formatter(fmt="%(asctime)s :: %(levelname)s :: %(message)s")
safe_console_formatter = SafeConsoleFormatter(fmt="%(asctime)s :: %(levelname)s :: %(message)s")

file_handler = RotatingFileHandler(
    filename=log_fname,
    mode='a',
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding='utf8',
    delay=False
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(fmt=log_formatter)

_MAIN_THREAD_ID = threading.main_thread().ident

class ConditionalThreadFilterConsoleHandler(logging.StreamHandler):
    """Console handler that can optionally filter out non-main-thread logs.

    Controlled by ENABLE_THREAD_FILTERING flag (env AFFILABS_THREAD_FILTER=1 to enable).
    """
    def emit(self, record):
        if ENABLE_THREAD_FILTERING and threading.current_thread().ident != _MAIN_THREAD_ID:
            return
        super().emit(record)

console_handler = ConditionalThreadFilterConsoleHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # Show DEBUG again
console_handler.setFormatter(fmt=safe_console_formatter)

logger = logging.getLogger('LOG')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

def enable_verbose_console():
    """Programmatically disable thread filtering and emoji stripping then raise console level."""
    global ENABLE_THREAD_FILTERING, ENABLE_EMOJI_STRIP
    ENABLE_THREAD_FILTERING = False
    ENABLE_EMOJI_STRIP = False
    console_handler.setLevel(logging.DEBUG)

