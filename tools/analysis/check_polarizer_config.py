from utils.device_configuration import DeviceConfiguration

cfg = DeviceConfiguration()
d = cfg.to_dict()

print("Device config polarizer positions:")
baseline = d.get("baseline", {})
print(f'S position: {baseline.get("oem_polarizer_s_position")}')
print(f'P position: {baseline.get("oem_polarizer_p_position")}')

print("\nCurrent servo positions:")
from utils.controller import PicoP4SPR

ctrl = PicoP4SPR()
ctrl.open()
pos = ctrl.servo_get()
print(f'S servo: {pos.get("s")}')
print(f'P servo: {pos.get("p")}')
