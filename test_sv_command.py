"""Test if sv command works for servo movement."""

import time
from affilabs.core.hardware_manager import HardwareManager

print("=" * 80)
print("TESTING SV COMMAND FOR SERVO MOVEMENT")
print("=" * 80)

# Initialize hardware
hm = HardwareManager()
hm.scan_and_connect(auto_connect=True)

# Wait for connection
for i in range(30):
    if hm.ctrl and hm.usb:
        print(f"✓ Hardware connected after {i * 0.5:.1f}s")
        break
    time.sleep(0.5)
else:
    print("✗ Hardware connection timeout!")
    exit(1)

ctrl = hm.ctrl

# Get the actual controller object (unwrap from adapter)
if hasattr(ctrl, '_ctrl'):
    raw_ctrl = ctrl._ctrl
else:
    raw_ctrl = ctrl

print("\n" + "=" * 80)
print("TEST 1: Move servo using sv command")
print("=" * 80)

# Test positions (PWM 0-255)
test_positions = [
    (10, 100),   # S=10, P=100
    (50, 150),   # S=50, P=150
    (100, 200),  # S=100, P=200
    (120, 30),   # S=120, P=30 (from your calibration log)
]

for s_pwm, p_pwm in test_positions:
    print(f"\nTesting S={s_pwm}, P={p_pwm}")

    # Format: svSSSppp\n (zero-padded to 3 digits each)
    cmd = f"sv{s_pwm:03d}{p_pwm:03d}\n"
    print(f"  Command: {cmd.strip()}")

    try:
        if raw_ctrl._ser is None:
            print("  ❌ Serial port not open")
            continue

        with raw_ctrl._lock:
            # Clear buffer
            raw_ctrl._ser.reset_input_buffer()

            # Send command
            raw_ctrl._ser.write(cmd.encode())
            print(f"  📤 Sent: {cmd.strip()}")

            # Wait for response
            time.sleep(0.1)

            # Read response
            response = raw_ctrl._ser.read(10)
            print(f"  📥 Response: {response!r}")

            if response == b"6" or b"6" in response:
                print("  ✅ SUCCESS - Servo moved!")

                # Wait for physical movement
                time.sleep(0.8)

                # Test ss command to confirm it moves to S position
                print("  Testing 'ss' command to verify S position...")
                raw_ctrl._ser.reset_input_buffer()
                raw_ctrl._ser.write(b"ss\n")
                time.sleep(0.3)
                ss_response = raw_ctrl._ser.read(10)
                print(f"  📥 ss response: {ss_response!r}")

            else:
                print(f"  ❌ FAILED - Expected b'6', got {response!r}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Wait between tests
    time.sleep(1.0)

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nIf sv command works:")
print("  - You should see b'6' responses")
print("  - Servo should physically move")
print("  - 'ss' command should move to the S position from sv command")
