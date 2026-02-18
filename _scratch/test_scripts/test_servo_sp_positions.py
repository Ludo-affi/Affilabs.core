"""Test servo using stored S/P positions from EEPROM."""

from affilabs.core.hardware_manager import HardwareManager
import time

print("=" * 80)
print("SERVO S/P POSITION TEST")
print("=" * 80)

# Initialize hardware manager
hm = HardwareManager()
hm.scan_and_connect(auto_connect=True)

# Wait for connection
for i in range(30):
    if hm.ctrl and hm.usb:
        break
    time.sleep(0.5)

print(f"\nController: {type(hm.ctrl).__name__}")

# Get direct access to the raw controller
raw_ctrl = hm.ctrl._ctrl

print("\n" + "=" * 80)
print("Testing EEPROM-stored servo positions")
print("=" * 80)
print("These use 'ss' and 'sp' commands that move to pre-calibrated positions")
print()

# Test S position
print("Test 1: Move to S position (ss command)")
cmd = "ss\n"
try:
    with raw_ctrl._serial_lock:
        raw_ctrl._ser.reset_input_buffer()
        raw_ctrl._ser.write(cmd.encode())
        print(f"  Command sent: {cmd.strip()}")
        time.sleep(0.6)
        response = raw_ctrl._ser.read(10)
        print(f"  Response: {response!r}")

    input("  Press Enter after checking if servo moved to S position...")
except Exception as e:
    print(f"  ERROR: {e}")

time.sleep(1)

# Test P position
print("\nTest 2: Move to P position (sp command)")
cmd = "sp\n"
try:
    with raw_ctrl._serial_lock:
        raw_ctrl._ser.reset_input_buffer()
        raw_ctrl._ser.write(cmd.encode())
        print(f"  Command sent: {cmd.strip()}")
        time.sleep(0.6)
        response = raw_ctrl._ser.read(10)
        print(f"  Response: {response!r}")

    input("  Press Enter after checking if servo moved to P position...")
except Exception as e:
    print(f"  ERROR: {e}")

time.sleep(1)

# Test raw servo command again
print("\nTest 3: Raw servo command to 90 degrees (servo:90,500)")
cmd = "servo:90,500\n"
try:
    with raw_ctrl._serial_lock:
        raw_ctrl._ser.reset_input_buffer()
        raw_ctrl._ser.write(cmd.encode())
        print(f"  Command sent: {cmd.strip()}")
        time.sleep(0.6)
        response = raw_ctrl._ser.read(10)
        print(f"  Response: {response!r}")

    input("  Press Enter after checking if servo moved to 90°...")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nIf none of these moved the servo:")
print("- Check servo is plugged into P4PRO board")
print("- Check servo power supply")
print("- Check for servo enable jumper/setting")
