import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usb4000_wrapper import USB4000

try:
    device = USB4000()
    if device.connect():
        print(f"SUCCESS:{device._serial_number}")
        sys.exit(0)
    else:
        print("FAIL:No devices found")
        sys.exit(1)
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(2)
