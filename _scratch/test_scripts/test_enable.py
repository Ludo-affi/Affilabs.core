"""Test if le (enable) command is needed"""
import time
from affilabs.utils.controller import PicoP4PRO
from affilabs.utils.usb4000_wrapper import USB4000

ctrl = PicoP4PRO()
ctrl.open()
usb = USB4000()
usb.open()
usb.set_integration(5.0)
time.sleep(0.5)

print("Before enable:")
spec = usb.intensities()
print(f"  Max: {max(spec):.0f}")

print("\nSending le:A,B,C,D (enable channels)...")
ctrl._ser.write(b"le:A,B,C,D\n")
time.sleep(0.2)
resp = ctrl._ser.read(10)
print(f"  Response: {resp!r}")

print("\nAfter le (enable):")
spec = usb.intensities()
print(f"  Max: {max(spec):.0f}")

print("\nSetting all to 10...")
for ch in ["a", "b", "c", "d"]:
    ctrl._ser.write(f"l{ch}10\n".encode())
    time.sleep(0.02)
    ctrl._ser.read(10)

time.sleep(0.5)
print("\nAfter setting to 10:")
spec = usb.intensities()
print(f"  Max: {max(spec):.0f}")

ctrl._ser.write(b"lx\n")
ctrl.close()
usb.close()
