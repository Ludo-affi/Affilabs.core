import sys
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\Affilabs-core')

from affilabs.utils.controller import PicoP4PRO

print("Testing PicoP4PRO.open() method...")
print()

ctrl = PicoP4PRO()
result = ctrl.open()

print()
print(f"✅ Open result: {result}")
print(f"✅ Firmware ID: {ctrl.firmware_id}")
print(f"✅ Version: {ctrl.version}")
print(f"✅ Serial port: {ctrl._ser.port if ctrl._ser else 'None'}")
