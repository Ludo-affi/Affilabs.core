"""Test FIXED batch command for P4PRO"""
import time
from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

ctrl = PicoP4PRO()
ctrl.open()
usb = USB4000()
usb.open()
usb.set_integration(5.0)
time.sleep(0.5)

print("="*70)
print("Testing FIXED set_batch_intensities() for P4PRO")
print("="*70)

test_values = [(0,0,0,0), (5,5,5,5), (20,20,20,20), (50,50,50,50), (100,100,100,100)]

for a, b, c, d in test_values:
    print(f"\nSetting batch({a}, {b}, {c}, {d})...")
    ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)
    time.sleep(0.5)

    spec = usb.intensities()
    max_signal = max(spec)
    print(f"  Max signal: {max_signal:.1f} counts")

print("\n" + "="*70)
print("Expected: Signal should INCREASE with intensity")
print("If working: 0 < 5 < 20 < 50 < 100")
print("="*70)

# Cleanup
print("\nTurning off...")
ctrl.set_batch_intensities(0, 0, 0, 0)
time.sleep(0.2)
spec = usb.intensities()
print(f"After off: {max(spec):.1f} counts")

ctrl.close()
usb.close()
