"""Test all possible servo commands for V2.4 firmware.

Tries different command formats to find what works.
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

def test_command(ser, cmd, description):
    """Test a command and show response."""
    print(f"\n   Testing: {description}")
    print(f"   Command: {cmd if isinstance(cmd, str) else cmd.decode()}")
    
    ser.reset_input_buffer()
    if isinstance(cmd, str):
        ser.write(cmd.encode())
    else:
        ser.write(cmd)
    time.sleep(0.1)
    
    response = ser.read(20)
    print(f"   Response: {response!r}")
    
    time.sleep(2.0)  # Wait to observe movement
    
    # Ask user if servo moved
    user_input = input("   >>> Did the servo MOVE? (y/n): ").strip().lower()
    moved = user_input == 'y'
    
    return response, moved

def test_all_formats():
    """Test all possible servo command formats."""
    
    print("=" * 70)
    print("TESTING ALL V2.4 SERVO COMMAND FORMATS")
    print("=" * 70)
    
    # Find COM port
    port = find_p4spr_port()
    if not port:
        print("❌ PicoP4SPR not found")
        return
    
    print(f"\n✅ Found PicoP4SPR on {port}")
    
    # Open serial
    ser = serial.Serial(port, baudrate=115200, timeout=1)
    time.sleep(0.5)
    
    # Test position: 90 degrees (middle)
    test_angle = 90
    
    print(f"\n" + "=" * 70)
    print(f"TARGET: Move servo to {test_angle}°")
    print("=" * 70)
    
    results = []
    
    # Enable servo power first
    print(f"\n[0] Enabling servo power...")
    resp, moved = test_command(ser, b"sp1\n", "Enable servo power")
    
    # Test Format 1: servo:ANGLE,DURATION (current format)
    print(f"\n[1] Format: servo:ANGLE,DURATION")
    resp, moved = test_command(ser, f"servo:{test_angle},1000\n", f"Move to {test_angle}° in 1000ms")
    results.append(("Format 1: servo:ANGLE,DURATION", moved))
    
    # Test Format 2: sv command (old V1.9 format - set positions)
    print(f"\n[2] Format: sv + ss/sp (old V1.9)")
    resp, moved1 = test_command(ser, f"sv{test_angle:03d}{test_angle:03d}\n", f"Set S={test_angle}°, P={test_angle}°")
    resp, moved2 = test_command(ser, b"ss\n", "Move to S position")
    results.append(("Format 2: sv + ss", moved1 or moved2))
    
    # Test Format 3: Direct PWM format (if supported)
    print(f"\n[3] Format: Direct PWM")
    pwm = int((test_angle - 5) * 255 / 170)
    resp, moved = test_command(ser, f"sp{pwm:03d}\n", f"Set PWM {pwm}")
    results.append(("Format 3: sp PWM", moved))
    
    # Test Format 4: Servo enable + move
    print(f"\n[4] Format: se + servo command")
    resp, moved1 = test_command(ser, b"se\n", "Enable servo")
    resp, moved2 = test_command(ser, f"servo:{test_angle},1000\n", f"Move to {test_angle}°")
    results.append(("Format 4: se + servo", moved1 or moved2))
    
    ser.close()
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    working_formats = []
    for format_name, moved in results:
        status = "✅ MOVED" if moved else "❌ NO MOVEMENT"
        print(f"   {format_name}: {status}")
        if moved:
            working_formats.append(format_name)
    
    print("\n" + "=" * 70)
    if working_formats:
        print(f"✅ Working format(s): {', '.join(working_formats)}")
        print("We'll use this format in the calibration code.")
    else:
        print("❌ No servo movement detected in any format!")
        print("Check:")
        print("  - Servo power cable connected")
        print("  - Servo mechanically free to move")
        print("  - Correct firmware version")
    print("=" * 70)

if __name__ == "__main__":
    try:
        test_all_formats()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
