"""Test WITHOUT le command"""
import time
from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

ctrl = PicoP4PRO()
ctrl.open()
usb = USB4000()
usb.open()
usb.set_integration(5.0)
time.sleep(0.5)

print("Test: Send laX commands WITHOUT le first")

for val in [0, 5, 20, 50, 100]:
    print(f"\nSetting all to {val}...")
    for ch in ['a', 'b', 'c', 'd']:
        ctrl._ser.write(f"l{ch}{val}\n".encode())
        time.sleep(0.01)
        ctrl._ser.read(10)
    
    time.sleep(0.5)
    spec = usb.intensities()
    print(f"  Signal: {max(spec):.1f} counts")

ctrl._ser.write(b"lx\n")
ctrl.close()
usb.close()
