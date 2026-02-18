"""Test servo movement for PicoP4SPR using calibrated positions.

This script tests servo movement using the same commands as the calibration.
"""

import time
from affilabs.core.hardware_manager import HardwareManager

def test_servo_movement():
    """Test servo movement between S and P positions."""

    print("=" * 70)
    print("SERVO MOVEMENT TEST - PicoP4SPR V2.4")
    print("=" * 70)

    # Initialize hardware manager
    hm = HardwareManager()

    print("\n[1] Connecting to hardware...")
    hm.scan_and_connect(auto_connect=True)

    # Wait for connection
    timeout = 15
    start = time.time()
    while time.time() - start < timeout:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)

    if not hm.ctrl or not hm.usb:
        print("❌ ERROR: Hardware not connected")
        return False

    ctrl_type = hm.ctrl.get_device_type() if hasattr(hm.ctrl, 'get_device_type') else 'Unknown'
    print(f"✅ Connected: {ctrl_type}")
    print(f"   Serial: {hm.usb.serial_number}")

    # Get calibrated positions from device config
    device_config = hm.device_config
    if device_config:
        s_pos = device_config.get_servo_s_position()
        p_pos = device_config.get_servo_p_position()
        print("\n[2] Using calibrated positions:")
        print(f"   S position: PWM {s_pos} ({(s_pos/255.0)*180:.1f}°)")
        print(f"   P position: PWM {p_pos} ({(p_pos/255.0)*180:.1f}°)")
    else:
        print("\n⚠️ No device config found - using default positions")
        s_pos = 210
        p_pos = 86
        print(f"   S position: PWM {s_pos} ({(s_pos/255.0)*180:.1f}°)")
        print(f"   P position: PWM {p_pos} ({(p_pos/255.0)*180:.1f}°)")

    # Test servo movement
    print("\n[3] Testing servo movement...")
    print("-" * 70)

    # Move to S position
    print(f"\n🔧 Moving to S position (PWM {s_pos})...")
    if hasattr(hm.ctrl, 'servo_move_raw_pwm'):
        success = hm.ctrl.servo_move_raw_pwm(s_pos)
        if success:
            print("   ✅ Command succeeded")
        else:
            print("   ❌ Command failed")
    else:
        print("   ❌ Controller does not support servo_move_raw_pwm()")
        return False

    time.sleep(2)  # Wait for servo to settle
    print("   Servo should now be at S position")

    # Move to P position
    print(f"\n🔧 Moving to P position (PWM {p_pos})...")
    success = hm.ctrl.servo_move_raw_pwm(p_pos)
    if success:
        print("   ✅ Command succeeded")
    else:
        print("   ❌ Command failed")

    time.sleep(2)  # Wait for servo to settle
    print("   Servo should now be at P position")

    # Return to S position
    print(f"\n🔧 Returning to S position (PWM {s_pos})...")
    success = hm.ctrl.servo_move_raw_pwm(s_pos)
    if success:
        print("   ✅ Command succeeded")
    else:
        print("   ❌ Command failed")

    time.sleep(2)  # Wait for servo to settle
    print("   Servo should now be back at S position")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nYou should have heard the servo move 3 times:")
    print("  1. S position → P position (large movement)")
    print("  2. P position → S position (large movement back)")
    print("\nIf you didn't hear movement, check:")
    print("  - Servo power cable connected")
    print("  - Firmware version (should be V2.4)")
    print("  - Serial communication working")

    return True


if __name__ == "__main__":
    try:
        test_servo_movement()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
