"""Diagnose servo communication - show raw firmware responses."""

from affilabs.core.hardware_manager import HardwareManager
import time

print("=" * 80)
print("SERVO DIAGNOSTIC - RAW FIRMWARE RESPONSES")
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
print(f"Serial port: {hm.ctrl._ctrl._ser.port if hasattr(hm.ctrl._ctrl, '_ser') else 'Unknown'}")

# Get direct access to the raw controller
raw_ctrl = hm.ctrl._ctrl

print("\n" + "=" * 80)
print("Testing servo commands with raw responses")
print("=" * 80)

test_positions = [1, 50, 100, 150, 200]

for pwm in test_positions:
    print(f"\nSending servo command for PWM {pwm}...")

    # Calculate degrees (same as servo_move_raw_pwm does)
    degrees = int(5 + (pwm * 170 / 255))
    degrees = max(5, min(175, degrees))
    duration_ms = 500

    cmd = f"servo:{degrees},{duration_ms}\n"
    print(f"  Command: {cmd.strip()}")

    try:
        with raw_ctrl._serial_lock:
            raw_ctrl._ser.reset_input_buffer()
            raw_ctrl._ser.write(cmd.encode())
            print("  Command sent, waiting 0.6s for response...")
            time.sleep(0.6)

            response = raw_ctrl._ser.read(10)
            print(f"  Response bytes: {response!r}")
            print(f"  Response length: {len(response)}")

            has_x01 = b'\x01' in response
            has_1 = b'1' in response

            if len(response) > 0:
                print(f"  Contains \\x01: {has_x01}")
                print(f"  Contains '1': {has_1}")
                if has_x01 or has_1:
                    print("  ✅ Valid response")
                else:
                    print("  ❌ Invalid response - servo should not move")
            else:
                print("  ❌ NO RESPONSE from firmware!")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

    time.sleep(0.5)

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print("\nAnalysis:")
print("- If responses are empty (b'') → Serial communication issue")
print("- If responses are b'11\\r\\n' or contain \\x01 → Firmware responding correctly")
print("- If servo not moving despite valid responses → Mechanical/power issue")
