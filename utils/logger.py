import logging
import os
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler

from settings import ROOT_DIR

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
console_handler.setLevel(logging.DEBUG)

logger = logging.getLogger("LOG")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
