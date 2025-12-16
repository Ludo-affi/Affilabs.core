"""Quick test to see if PicoP4SPR can connect."""
import sys
sys.path.insert(0, ".")

from affilabs.utils.controller import PicoP4SPR

print("\n" + "="*60)
print("Testing PicoP4SPR connection...")
print("="*60 + "\n")

controller = PicoP4SPR()
print(f"Controller created: {controller}")
print(f"Controller name: {controller.name}")

print("\nAttempting to open...")
result = controller.open()

print(f"\nResult: {result}")

if result:
    print("✅ Controller connected successfully!")
    print(f"Device type: {controller.get_device_type()}")
    controller.close()
    print("Controller closed.")
else:
    print("❌ Controller failed to connect")
    print("Check:")
    print("  1. Is the controller powered on?")
    print("  2. Is the USB cable connected?")
    print("  3. Is COM5 in use by another program?")
