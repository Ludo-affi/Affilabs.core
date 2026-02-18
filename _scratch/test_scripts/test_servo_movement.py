"""Test basic servo movement - move to specific positions."""

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger
import time

print("=" * 80)
print("SERVO MOVEMENT TEST")
print("=" * 80)

# Initialize hardware manager
logger.info("Initializing hardware manager...")
hm = HardwareManager()

# Scan and connect
logger.info("Scanning for devices...")
hm.scan_and_connect(auto_connect=True)

# Wait for connection
logger.info("Waiting for hardware connection...")
for i in range(30):
    if hm.ctrl and hm.usb:
        logger.info(f"✓ Hardware connected after {i * 0.5:.1f}s")
        break
    time.sleep(0.5)
else:
    logger.error("✗ Hardware connection timeout!")
    exit(1)

logger.info(f"Controller: {type(hm.ctrl).__name__}")

# Test servo movements
test_positions = [1, 50, 100, 150, 200, 255, 128, 64, 192, 1]

print("\n" + "=" * 80)
print("Testing servo movement to various positions")
print("=" * 80)
print("Watch the servo - it should move to each position")
print()

for i, pwm in enumerate(test_positions, 1):
    print(f"\nMove {i}/{len(test_positions)}: Moving to PWM {pwm}...")

    # Use the raw controller method
    success = hm.ctrl.servo_move_raw_pwm(pwm)

    if success:
        print("  ✅ Command sent successfully")
    else:
        print("  ❌ Command FAILED")

    # Wait for movement to complete
    time.sleep(0.7)

    # Ask user for confirmation
    response = input(f"  Did servo move to position {pwm}? (y/n/q to quit): ").strip().lower()
    if response == 'q':
        print("\nTest aborted by user")
        break
    elif response != 'y':
        print(f"  ⚠️  USER REPORTED: Servo did NOT move to PWM {pwm}")
    else:
        print(f"  ✅ USER CONFIRMED: Servo moved to PWM {pwm}")

print("\n" + "=" * 80)
print("SERVO MOVEMENT TEST COMPLETE")
print("=" * 80)
