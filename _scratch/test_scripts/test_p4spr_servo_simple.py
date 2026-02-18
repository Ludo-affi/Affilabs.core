"""
Simple P4SPR Servo Test - Uses servo:ANGLE,DURATION command like P4PRO
Tests the V2.4 firmware servo command with angles 5-175°
"""

import serial
import time
import serial.tools.list_ports

def find_controller():
    """Find P4SPR/P4PRO controller."""
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x2E8A and port.pid == 0x000A:  # Pico VID:PID
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(0.1)

                # Check firmware ID
                ser.write(b"id\n")
                time.sleep(0.1)
                response = ser.read(100).decode('utf-8', errors='ignore')

                print(f"✅ Found controller on {port.device}")
                print(f"   Firmware ID: {response.strip()}")
                return ser
            except Exception as e:
                print(f"   Error checking {port.device}: {e}")

    return None

def test_servo_movement():
    """Test servo movement with servo:ANGLE,DURATION command."""

    ser = find_controller()
    if not ser:
        print("\n❌ Controller not found!")
        return

    print("\n" + "="*70)
    print("P4SPR V2.4 SERVO TEST - servo:ANGLE,DURATION format")
    print("="*70)
    print("\nFirmware angle range: 5-175° (MIN_DEG to MAX_DEG)")
    print("This maps to 2.5%-12.5% duty cycle for SG90 servo")
    print("="*70)

    # Test angles within firmware range
    test_positions = [
        (5, "Minimum angle (2.5% duty)"),
        (90, "Middle angle (7.25% duty)"),
        (175, "Maximum angle (12.5% duty)"),
        (45, "Quarter position"),
        (135, "Three-quarter position"),
        (90, "Back to middle"),
    ]

    for angle, description in test_positions:
        print(f"\n{'='*70}")
        print(f"Testing: {description}")
        print(f"Angle: {angle}° | Duration: 500ms")
        print(f"{'='*70}")

        # Enable servo power first (V2.4 requirement)
        print("  1. Enabling servo power...")
        ser.reset_input_buffer()
        ser.write(b"sp1\n")
        time.sleep(0.05)
        enable_resp = ser.read(10)
        print(f"     Response: {enable_resp!r}")

        # Send servo command
        cmd = f"servo:{angle},500\n"
        print(f"  2. Sending command: {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        time.sleep(0.05)
        response = ser.read(10)
        print(f"     Response: {response!r}")

        if b"1" in response or b"6" in response:
            print("  ✅ Command accepted!")
        else:
            print("  ⚠️  Unexpected response!")

        # Wait for movement to complete
        print("  3. Waiting for servo movement (500ms + settle)...")
        time.sleep(0.7)  # 500ms movement + 200ms settle

        input(f"\n  >>> Did servo move to {angle}°? Press Enter to continue...")

    # Turn off servo power
    print(f"\n{'='*70}")
    print("Disabling servo power...")
    ser.write(b"sp0\n")
    time.sleep(0.05)

    ser.close()
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_servo_movement()
