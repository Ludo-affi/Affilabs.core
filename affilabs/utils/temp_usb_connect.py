import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usb4000_wrapper import USB4000

try:
    device = USB4000()
    if device.connect():
        sys.exit(0)
    else:
        sys.exit(1)
except Exception:
    sys.exit(2)
