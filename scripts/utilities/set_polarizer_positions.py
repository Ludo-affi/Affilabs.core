from utils.controller import PicoP4SPR
import time

ctrl = PicoP4SPR()
ctrl.open()

print("Current position:")
pos = ctrl.servo_get()
print(f"  S={pos.get('s')}, P={pos.get('p')}")

print("\nSetting polarizer positions: S=50, P=138...")
# Set BOTH positions at once (this is how the main code does it)
ctrl.servo_set(s=50, p=138)
time.sleep(1.0)  # Wait for servo to move

print("Saving to EEPROM...")
ctrl.flash()
time.sleep(0.5)

pos = ctrl.servo_get()
print(f"\nNew position: S={pos.get('s')}, P={pos.get('p')}")
print("Positions saved to EEPROM!")
