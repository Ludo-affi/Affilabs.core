#!/usr/bin/env python3
"""Test servo movement during calibration sweep - mimics servo calibration behavior."""

import time
from affilabs.utils.controller import PicoP4PRO

def test_calibration_sweep():
    """Test servo sweep with same PWM values used in calibration."""

    # Connect to P4PRO
    ctrl = PicoP4PRO()
    if not ctrl.open():
        print("❌ Failed to connect to P4PRO")
        return False

    print("✅ Connected to P4PRO")
    print(f"   Firmware: {ctrl.firmware_id}")
    print()

    # Test positions used in servo calibration (Stage 1)
    forward_positions = [1, 65, 128, 191, 255]

    print("=" * 70)
    print("TESTING SERVO CALIBRATION SWEEP")
    print("=" * 70)
    print("Testing PWM positions: 1, 65, 128, 191, 255")
    print("Watch for servo movement...")
    print()

    for pwm in forward_positions:
        print(f"Moving to PWM {pwm:3d}...", end=" ", flush=True)

        # Use the servo_move_raw_pwm method (same as servo_move_calibration_only calls)
        success = ctrl.servo_move_raw_pwm(target_pwm=pwm)

        if success:
            print("✅ ACK")
        else:
            print("❌ FAILED")
            return False

        # Small delay between moves
        time.sleep(0.2)

    print()
    print("=" * 70)
    print("✅ ALL POSITIONS TESTED SUCCESSFULLY")
    print("=" * 70)

    ctrl.close()
    return True

if __name__ == "__main__":
    test_calibration_sweep()
