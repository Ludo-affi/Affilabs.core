import sys
sys.path.insert(0, r'c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\Affilabs-core')

from affilabs.core.hardware_manager import HardwareManager

# Check if there's a stale controller reference
print("Checking HardwareManager state...")
print()

# Create instance (this happens at startup)
hw = HardwareManager()

print(f"ctrl = {hw.ctrl}")
print(f"_ctrl_raw = {hw._ctrl_raw}")
print(f"_ctrl_type = {hw._ctrl_type}")
print(f"_ctrl_port = {hw._ctrl_port}")

if hw.ctrl is not None:
    print()
    print("⚠️ FOUND THE BUG!")
    print("⚠️ hw.ctrl is NOT None - scanning will be skipped!")
    print(f"⚠️ Stale controller object: {hw.ctrl}")
