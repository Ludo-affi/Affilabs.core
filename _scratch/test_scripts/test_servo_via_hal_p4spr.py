"""\
Test P4SPR servo movement via HAL (same path as calibration).

- Uses HardwareManager and hm.ctrl.servo_move_raw_pwm(pwm)
- Prints mapped angle for each PWM
- Pauses for you to confirm whether the servo moved
"""

import time

from affilabs.core.hardware_manager import HardwareManager


def pwm_to_angle(pwm: int) -> int:
    """Map PWM 0-255 to firmware angle 5-175° (same as HAL)."""
    if pwm < 0:
        pwm = 0
    if pwm > 255:
        pwm = 255
    min_angle = 5
    max_angle = 175
    angle = int(min_angle + (pwm / 255.0) * (max_angle - min_angle))
    if angle < min_angle:
        angle = min_angle
    if angle > max_angle:
        angle = max_angle
    return angle


def main() -> None:
    print("=" * 70)
    print("P4SPR SERVO TEST VIA HAL (hm.ctrl.servo_move_raw_pwm)")
    print("=" * 70)

    print("\nConnecting hardware via HardwareManager (same as calibrate_polarizer)...")
    hm = HardwareManager()

    # Use the same connection sequence as calibrate_polarizer.main()
    hm.scan_and_connect(auto_connect=True)

    t0 = time.time()
    while time.time() - t0 < 15.0:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)

    if not hm.ctrl or not hm.usb:
        print("\n❌ Hardware not connected (ctrl or usb is None)")
        return

    ctrl = hm.ctrl
    ctrl_type = getattr(ctrl, "get_device_type", lambda: type(ctrl).__name__)()
    print(f"  Controller type: {ctrl_type}")

    if not hasattr(ctrl, "servo_move_raw_pwm"):
        print("\n❌ This controller object does not expose servo_move_raw_pwm().")
        return

    # Same PWM positions used by Stage 1 of calibration
    test_pwms = [1, 65, 128, 191, 255]

    print("\nTest PWM positions:")
    for pwm in test_pwms:
        angle = pwm_to_angle(pwm)
        print(f"  PWM {pwm:3d} → angle ≈ {angle:3d}°")

    print("\nFor each step, watch the servo and answer the prompt.")

    for pwm in test_pwms:
        angle = pwm_to_angle(pwm)
        print("\n" + "-" * 70)
        print(f"Moving via HAL: PWM {pwm} → angle ≈ {angle}°")

        try:
            ok = ctrl.servo_move_raw_pwm(pwm)
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ Exception from servo_move_raw_pwm({pwm}): {e}")
            continue

        if not ok:
            print(f"  ❌ servo_move_raw_pwm({pwm}) returned False")
        else:
            print(f"  ✅ servo_move_raw_pwm({pwm}) returned True")

        # Give the servo time to move and settle (HAL already waits ~0.6s)
        time.sleep(0.3)

        input(f"  >>> Did the servo visibly move to about {angle}°? Press Enter to continue...")

    print("\n" + "=" * 70)
    print("Test complete. Please report which PWM steps did/did not move.")
    print("=" * 70)


if __name__ == "__main__":
    main()
