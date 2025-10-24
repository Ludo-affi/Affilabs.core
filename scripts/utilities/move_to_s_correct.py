from utils.controller import PicoP4SPR
import time

ctrl = PicoP4SPR()
ctrl.open()

print("Current position:")
pos = ctrl.servo_get()
print(f"  S={pos.get('s')}, P={pos.get('p')}")

print("\nMoving to S position (50)...")
ctrl.servo_set(s=50)
time.sleep(2)

pos = ctrl.servo_get()
print(f"New position: S={pos.get('s')}, P={pos.get('p')}")
print("\nReady for S-pol acquisition!")
