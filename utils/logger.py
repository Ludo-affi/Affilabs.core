import logging
import os
import sys
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler

# ============================================================================
# PYTHON VERSION CHECK - Import early warning banner
# ============================================================================
try:
    from utils.python_version_check import check_python_version

    check_python_version()
except ImportError:
    # Fallback if check module not available
    if sys.version_info < (3, 12):
        print("\n" + "!" * 80)
        print(
            f"⚠️  WARNING: Python {sys.version_info.major}.{sys.version_info.minor} detected - Expected 3.12+",
        )
        print("!" * 80)
        print("   This may cause runtime errors with type hints and modern syntax!")
        print(f"   Python executable: {sys.executable}")
        print("!" * 80 + "\n")

from settings import CONSOLE_LOG_LEVEL, ROOT_DIR

log_fname = os.path.join(ROOT_DIR, "logfile.txt")
log_formatter = Formatter(fmt="%(asctime)s :: %(levelname)s :: %(message)s")
file_handler = RotatingFileHandler(
    filename=log_fname,
    mode="a",
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf8",
    delay=False,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(fmt=log_formatter)

console_handler = StreamHandler()
console_handler.setFormatter(fmt=log_formatter)
# ✨ PERFORMANCE: Configurable console logging level (reduced overhead)
# File still logs everything at DEBUG level for troubleshooting
# Console uses CONSOLE_LOG_LEVEL from settings (default: WARNING)
# This reduces console I/O overhead by ~1-2ms per cycle vs DEBUG
console_handler.setLevel(
    CONSOLE_LOG_LEVEL,
)  # Configurable: WARNING (prod) / INFO (dev) / DEBUG (troubleshoot)

logger = logging.getLogger("LOG")
logger.setLevel(logging.DEBUG)  # Root logger still at DEBUG (for file handler)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
