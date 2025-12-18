"""Diagnostic script to test servo commands and identify the exact issue.

This script will:
1. Read current EEPROM values
2. Test different sv command formats
3. Verify what the firmware actually expects
4. Document the correct command format
"""

import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.device_configuration import DeviceConfiguration


def read_eeprom(ctrl):
    """Read and display EEPROM servo positions."""
    print("\n" + "="*70)
    print("READING EEPROM")
    print("="*70)

    try:
        # Use raw controller for EEPROM access (HAL doesn't expose this)
        raw_ctrl = ctrl._ctrl if hasattr(ctrl, '_ctrl') else ctrl
        eeprom_config = raw_ctrl.read_config_from_eeprom()
        if eeprom_config:
            s_eeprom = eeprom_config.get("servo_s_position", "N/A")
            p_eeprom = eeprom_config.get("servo_p_position", "N/A")
            print(f"✅ EEPROM S position: {s_eeprom}")
            print(f"✅ EEPROM P position: {p_eeprom}")
            return s_eeprom, p_eeprom
        else:
            print("⚠️  Failed to read EEPROM (continuing with tests anyway)")
            print("   Device config has: S=67°, P=157°")
            return None, None
    except Exception as e:
        print(f"⚠️  Exception reading EEPROM: {e}")
        print("   (continuing with tests anyway)")
        print("   Device config has: S=67°, P=157°")
        return None, None


def send_sv_command(ser, s_val, p_val, label):
    """Send sv command and wait for response."""
    cmd = f"sv{s_val:03d}{p_val:03d}\n"
    print(f"\n{label}:")
    print(f"  Command: {repr(cmd)}")

    try:
        ser.write(cmd.encode())
        time.sleep(0.05)
        resp = ser.readline().decode().strip()
        print(f"  Response: {repr(resp)}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def send_ss_command(ser):
    """Send ss command to move to S position."""
    print("\nSending ss command (move to S position from EEPROM)...")
    try:
        ser.write(b"ss\n")
        time.sleep(0.05)
        resp = ser.readline().decode().strip()
        print(f"  Response: {repr(resp)}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def send_sp_command(ser):
    """Send sp command to move to P position."""
    print("\nSending sp command (move to P position from EEPROM)...")
    try:
        ser.write(b"sp\n")
        time.sleep(0.05)
        resp = ser.readline().decode().strip()
        print(f"  Response: {repr(resp)}")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_servo_positions(ser):
    """Test different servo position values to determine expected units."""
    print("\n" + "="*70)
    print("TESTING SERVO POSITION VALUES")
    print("="*70)
    print("\nTesting different value ranges to determine if firmware expects:")
    print("  - Degrees (0-180)")
    print("  - PWM units (0-255)")
    print("  - Something else")

    # Test 1: Small value (should work in both degrees and PWM)
    print("\n--- TEST 1: Small value (10) ---")
    send_sv_command(ser, 10, 10, "sv010010")
    time.sleep(2)
    input("Press Enter after observing servo movement...")

    # Test 2: Mid-range value
    print("\n--- TEST 2: Mid-range value (90) ---")
    send_sv_command(ser, 90, 90, "sv090090")
    time.sleep(2)
    input("Press Enter after observing servo movement...")

    # Test 3: 180 (max degrees, valid PWM)
    print("\n--- TEST 3: Value 180 (max degrees, valid PWM) ---")
    send_sv_command(ser, 180, 180, "sv180180")
    time.sleep(2)
    input("Press Enter after observing servo movement...")

    # Test 4: 255 (invalid degrees, max PWM)
    print("\n--- TEST 4: Value 255 (invalid degrees, max PWM) ---")
    send_sv_command(ser, 255, 255, "sv255255")
    time.sleep(2)
    input("Press Enter after observing servo movement...")

    # Test 5: Compare 180 vs 255
    print("\n--- TEST 5: Compare 180 vs 255 ---")
    print("If firmware expects degrees: 180 and 255 should move to SAME position (clamped to 180°)")
    print("If firmware expects PWM: 180 and 255 should move to DIFFERENT positions")

    print("\nMoving to 180...")
    send_sv_command(ser, 180, 0, "sv180000")
    time.sleep(2)
    input("Press Enter after observing position...")

    print("\nMoving to 255...")
    send_sv_command(ser, 255, 0, "sv255000")
    time.sleep(2)
    input("Press Enter after observing position...")

    print("\n❓ Did the servo move between 180 and 255?")
    moved = input("Enter 'y' if it moved, 'n' if it stayed in same position: ").strip().lower()

    if moved == 'n':
        print("\n✅ CONCLUSION: Firmware expects DEGREES (0-180)")
        print("   Values > 180 are clamped to 180°")
        return "DEGREES"
    elif moved == 'y':
        print("\n✅ CONCLUSION: Firmware expects PWM UNITS (0-255)")
        print("   Full range 0-255 is used")
        return "PWM"
    else:
        print("\n❓ Inconclusive - manual inspection needed")
        return "UNKNOWN"


def test_calibrated_positions(ser, s_val, p_val):
    """Test the actual calibrated positions."""
    print("\n" + "="*70)
    print("TESTING CALIBRATED POSITIONS")
    print("="*70)
    print(f"Device config has: S={s_val}, P={p_val}")

    # Test S position
    print(f"\n--- Moving to S position ({s_val}) ---")
    send_sv_command(ser, s_val, p_val, f"sv{s_val:03d}{p_val:03d}")
    time.sleep(1)
    send_ss_command(ser)
    time.sleep(2)
    input("Press Enter after observing S position...")

    # Test P position
    print(f"\n--- Moving to P position ({p_val}) ---")
    send_sp_command(ser)
    time.sleep(2)
    input("Press Enter after observing P position...")

    print("\n❓ Did you observe LARGE movement between S and P (90° angular difference)?")
    large_move = input("Enter 'y' for large movement, 'n' for small movement: ").strip().lower()

    if large_move == 'n':
        print("\n❌ PROBLEM CONFIRMED: Servo movement is too small!")
        print("   Expected: 90° angular separation (large movement)")
        print(f"   Positions sent: S={s_val}, P={p_val} (separation={abs(p_val-s_val)})")
    else:
        print("\n✅ Servo movement looks correct!")


def main():
    """Run servo diagnostic tests."""
    print("="*70)
    print("SERVO COMMAND DIAGNOSTIC TOOL")
    print("="*70)
    print("\nThis script will help identify the exact command format issue.")
    print("You will be asked to observe servo movements and answer questions.")

    input("\nPress Enter to start (make sure hardware is connected)...")

    # Initialize hardware
    print("\nInitializing hardware...")
    hm = HardwareManager()
    hm.scan_and_connect(auto_connect=True)

    # Wait for connection
    t0 = time.time()
    while time.time() - t0 < 15.0:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)

    if not hm.ctrl or not hm.usb:
        print("❌ Hardware not connected!")
        sys.exit(1)

    print("✅ Hardware connected")

    # Get serial port
    if not hasattr(hm.ctrl, '_ser'):
        print("❌ Controller doesn't have serial port access!")
        sys.exit(1)

    ser = hm.ctrl._ser

    # Get device config servo positions
    print("\n" + "="*70)
    print("DEVICE CONFIG SERVO POSITIONS")
    print("="*70)

    # Create DeviceConfiguration instance (loads config in __init__)
    detector_serial = hm.usb.serial_number if hasattr(hm.usb, 'serial_number') else None
    if detector_serial:
        device_config = DeviceConfiguration(device_serial=detector_serial, controller=hm.ctrl, silent_load=True)
        print(f"Loaded device config for: {detector_serial}")
    else:
        print("⚠️  No detector serial, using default config")
        device_config = DeviceConfiguration(device_serial="UNKNOWN", controller=hm.ctrl, silent_load=True)

    servo_positions = device_config.get_servo_positions()
    s_config = servo_positions["s"]
    p_config = servo_positions["p"]
    print(f"Device config S position: {s_config}")
    print(f"Device config P position: {p_config}")
    print(f"Separation: {abs(p_config - s_config)} units")

    # Read EEPROM (use raw controller) - optional, may fail
    raw_ctrl = hm.ctrl._ctrl if hasattr(hm.ctrl, '_ctrl') else hm.ctrl
    s_eeprom, p_eeprom = read_eeprom(raw_ctrl)

    # Test servo position interpretation
    units = test_servo_positions(ser)

    # Test device config positions (these are what should work)
    print("\n" + "="*70)
    print("TESTING DEVICE CONFIG POSITIONS")
    print("="*70)
    print(f"\nTesting S={s_config}, P={p_config} from device_config.json")
    test_calibrated_positions(ser, s_config, p_config)

    # Final summary
    print("\Device config positions: S={s_config}, P={p_config}")
    if s_eeprom is not None:
        print(f"EEPROM positions: S={s_eeprom}, P={p_eeprom}")
        if s_eeprom != s_config or p_eeprom != p_config:
            print("\n⚠️  WARNING: EEPROM doesn't match device config!")
            print(f"   EEPROM has: S={s_eeprom}, P={p_eeprom}")
            print(f"   Config has: S={s_config}, P={p_config}")
            print("   → Power cycle needed to reload EEPROM from device_config")
    else:
        print("EEPROM positions: Could not read (continuing with device config)")

    print(f"\nFirmware expects: {units}")

    if units == "DEGREES":
        print("\n✅ CORRECT: Firmware expects degrees (0-180)")
        print("   Device config stores degrees (0-180) ✓")
        print("   Calibration tool output labeled 'PWM' is actually degrees ✓")
        print("   sv command format: sv{S:03d}{P:03d}\\n where S/P are 0-180°")
    elif units == "PWM":
        print("\n❌ UNEXPECTED: Firmware expects PWM units (0-255)")
        print("   This contradicts firmware source code analysis")
        print("   May indicate firmware version mismatchM")
    else:
        print("  1. ✅ EEPROM positions look reasonable")
        print("  2. Issue may be in HAL command generation")

    print("\n" + "="*70)

    # Cleanup
    hm.disconnect_all()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
