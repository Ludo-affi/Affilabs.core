"""\
Test P4SPR servo using the SAME serial connection as HardwareManager/HAL.

This bypasses `servo_move_raw_pwm` and sends raw `servo:ANGLE,DURATION` commands
on the controller's existing serial port, so we can see if the issue is in
HAL logic vs. firmware/connection.
"""

import time

from affilabs.core.hardware_manager import HardwareManager


def get_underlying_serial(hm):
    """Return the pyserial Serial object used by the controller, plus a label."""
    ctrl = hm.ctrl
    label = f"hm.ctrl type = {type(ctrl).__name__}"

    # If this is a HAL adapter, unwrap the underlying controller
    low_ctrl = getattr(ctrl, "_ctrl", ctrl)
    ser = getattr(low_ctrl, "_ser", None)

    return ser, label, low_ctrl


def send_servo_command(ser, angle: int, duration_ms: int = 500) -> bytes:
    """Send one servo:ANGLE,DURATION command and return raw response bytes.

    Uses 3-digit zero-padded fields to match strict parsers:
        servo:AAA,DDD
    e.g. angle=5, duration=500 → "servo:005,500".
    """
    cmd = f"servo:{angle:03d},{duration_ms:03d}\n"
    print(f"\n{'='*70}")
    print(f"Sending raw command on existing serial: {cmd.strip()}")
    print(f"Angle = {angle}°, Duration = {duration_ms} ms")

    # Clear input buffer and send
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.05)

    response = ser.read(100)
    print(f"Response bytes: {response!r}")
    try:
        print(f"Response text : {response.decode('utf-8', errors='ignore').strip()}")
    except Exception:
        pass

    # Give time for servo to move
    time.sleep(0.7)  # 500 ms pulse + margin

    return response


def main() -> None:
    print("=" * 70)
    print("P4SPR SERVO TEST VIA CONTROLLER SERIAL (RAW COMMANDS)")
    print("=" * 70)

    print("\nConnecting hardware via HardwareManager (same as calibrate_polarizer)...")
    hm = HardwareManager()
    hm.scan_and_connect(auto_connect=True)

    # Wait up to 15s for controller + detector, mirroring calibrate_polarizer.main()
    t0 = time.time()
    while time.time() - t0 < 15.0:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)

    if not hm.ctrl or not hm.usb:
        print("\n❌ Hardware not connected (ctrl or usb is None)")
        return

    ser, label, low_ctrl = get_underlying_serial(hm)
    print(f"  {label}")
    print(f"  low_ctrl type = {type(low_ctrl).__name__}")

    if ser is None:
        print("\n❌ Could not get underlying serial port from controller.")
        return

    print(f"  Serial port: {ser.port}, is_open={ser.is_open}")

    # Try a few angles spanning the full range
    test_angles = [5, 45, 90, 135, 175]

    print("\nWe will now send raw servo commands on this serial connection.")
    print("For each angle, watch the polarizer servo and answer the prompt.")

    for angle in test_angles:
        resp = send_servo_command(ser, angle, duration_ms=500)

        if b"1" in resp or b"6" in resp:
            print("  ✅ Firmware ACK (1/6) detected")
        elif resp == b"":
            print("  ⚠️ No bytes returned (timeout)")
        else:
            print("  ⚠️ Unexpected response pattern")

        input(f"  >>> Did the servo visibly move to about {angle}°? Press Enter to continue...")

    print("\n" + "=" * 70)
    print("Test finished. Please report which angles moved / did not move.")
    print("=" * 70)


if __name__ == "__main__":
    main()
