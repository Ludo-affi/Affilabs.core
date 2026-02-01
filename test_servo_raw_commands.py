"""Test servo movement using RAW serial commands (same as stage 3).

This sends the exact servo:ANGLE,DURATION commands that stage 3 uses.
"""

import time
import serial.tools.list_ports

def find_p4spr_port():
    """Find PicoP4SPR COM port."""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if port.vid == 0x2E8A and port.pid == 0x000A:
            return port.device
    return None

def send_servo_command(ser, angle_degrees, duration_ms=2000):
    """Send servo:ANGLE,DURATION command.
    
    This is the V2.4 firmware command format.
    """
    # Clamp angle to firmware range (5-175 degrees)
    angle = max(5, min(175, angle_degrees))

    # Build command
    cmd = f"servo:{angle},{duration_ms}\n"

    print(f"   Sending: {cmd.strip()}")

    # Clear input buffer
    ser.reset_input_buffer()

    # Send command
    ser.write(cmd.encode())
    time.sleep(0.05)

    # Read response
    response = ser.read(10)
    print(f"   Response: {response!r}")

    # V2.4 responds with '1', older firmware with '6'
    if response in (b"1", b"6"):
        print(f"   ✅ Command accepted - waiting {duration_ms}ms for movement...")
        # Wait for movement with extra margin
        time.sleep(duration_ms / 1000.0 + 0.5)
        return True
    else:
        print("   ❌ Unexpected response")
        return False

def pwm_to_degrees(pwm):
    """Convert PWM (0-255) to degrees (5-175)."""
    # Linear mapping
    MIN_ANGLE = 5
    MAX_ANGLE = 175
    degrees = int(MIN_ANGLE + (pwm / 255.0) * (MAX_ANGLE - MIN_ANGLE))
    return max(MIN_ANGLE, min(MAX_ANGLE, degrees))

def test_raw_servo():
    """Test servo using raw serial commands."""

    print("=" * 70)
    print("RAW SERVO COMMAND TEST (V2.4 firmware)")
    print("=" * 70)

    # Find COM port
    port = find_p4spr_port()
    if not port:
        print("❌ PicoP4SPR not found")
        return

    print(f"\n✅ Found PicoP4SPR on {port}")

    # Open serial connection
    ser = serial.Serial(port, baudrate=115200, timeout=1)
    time.sleep(0.5)  # Let connection stabilize

    print("✅ Serial connection opened")

    # Get calibrated positions (use same as test)
    s_pwm = 210  # S position
    p_pwm = 86   # P position

    s_deg = pwm_to_degrees(s_pwm)
    p_deg = pwm_to_degrees(p_pwm)

    print("\nCalibrated positions:")
    print(f"   S: PWM {s_pwm} = {s_deg}°")
    print(f"   P: PWM {p_pwm} = {p_deg}°")

    # Enable servo power (CRITICAL for V2.4!)
    print("\n[1] Enabling servo power...")
    ser.write(b"sp1\n")
    time.sleep(0.05)
    resp = ser.read(10)
    print(f"   Response: {resp!r}")
    time.sleep(0.2)

    # Test movements
    print(f"\n[2] Moving to S position ({s_deg}°)...")
    send_servo_command(ser, s_deg, 2000)  # 2 second movement

    print(f"\n[3] Moving to P position ({p_deg}°)...")
    send_servo_command(ser, p_deg, 2000)  # 2 second movement

    print(f"\n[4] Returning to S position ({s_deg}°)...")
    send_servo_command(ser, s_deg, 2000)  # 2 second movement

    # Close connection
    ser.close()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nDid you hear/see the servo move?")
    print("If NO:")
    print("  - Check servo power cable")
    print("  - Check servo is mechanically free to move")
    print("  - Verify firmware version with 'vi' command")

if __name__ == "__main__":
    try:
        test_raw_servo()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
