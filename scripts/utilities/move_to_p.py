from utils.controller import PicoP4SPR
import time

ctrl = PicoP4SPR()
ctrl.open()

print("Moving to P position...")
ctrl.set_mode('p')
time.sleep(1.0)

pos = ctrl.servo_get()
print(f"Position: S={pos.get('s')}, P={pos.get('p')}")
print("Ready for P-pol acquisition!")
