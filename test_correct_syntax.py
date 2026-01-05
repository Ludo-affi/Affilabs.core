"""Test CORRECT P4PRO syntax with colon"""
import time
from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

ctrl = PicoP4PRO()
ctrl.open()

# Turn off first
ctrl._ser.write(b"lx\n")
time.sleep(0.2)

usb = USB4000()
usb.open()
usb.set_integration(5.0)
time.sleep(0.5)

print("="*70)
print("Testing CORRECT P4PRO syntax: la:X (with colon)")
print("="*70)

for val in [0, 5, 20, 50, 100]:
    print(f"\nSetting all to {val} using la:{val} syntax...")
    for ch in ['a', 'b', 'c', 'd']:
        ctrl._ser.write(f"l{ch}:{val}\n".encode())
        time.sleep(0.02)
        resp = ctrl._ser.read(10)
        if resp:
            print(f"  l{ch}:{val} -> {resp!r}")
    
    time.sleep(0.5)
    spec = usb.intensities()
    max_signal = max(spec)
    print(f"  Max signal: {max_signal:.1f} counts")

print("\n" + "="*70)
print("Expected: 0 < 5 < 20 < 50 < 100")
print("="*70)

ctrl._ser.write(b"lx\n")
time.sleep(0.2)
spec = usb.intensities()
print(f"\nAfter lx: {max(spec):.1f} counts")

ctrl.close()
usb.close()
