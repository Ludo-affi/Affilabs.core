from utils.controller import PicoP4SPR
import time

ctrl = PicoP4SPR()
ctrl.open()
print("Moving to S position...")
ctrl.set_mode('s')
time.sleep(1)
try:
    pos = ctrl.servo_get()
    print(f"S-mode position set: S={pos.get('s')}, P={pos.get('p')}")
except:
    print("S-mode command sent")
