"""
Direct P4PRO servo command test - bypasses all abstractions.

Tests servo:ANGLE,DURATION command directly on COM port to verify if
P4PRO firmware v2.0 actually supports this command format.
"""

import serial
import time
import sys

def find_p4pro_port():
    """Scan COM ports to find P4PRO controller."""
    import serial.tools.list_ports
    
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x2E8A and port.pid == 0x000A:  # Pico VID:PID
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(0.1)
                
                # Check if it's P4PRO
                ser.write(b"id\n")
                time.sleep(0.1)
                response = ser.read(100).decode('utf-8', errors='ignore')
                
                if "P4PRO" in response:
                    print(f"✅ Found P4PRO on {port.device}")
                    print(f"   Firmware ID: {response.strip()}")
                    return ser
                else:
                    ser.close()
            except Exception as e:
                print(f"   Error checking {port.device}: {e}")
    
    return None

def test_servo_commands(ser):
    """Test different servo command formats."""
    
    print("\n" + "="*60)
    print("TESTING P4PRO SERVO COMMANDS")
    print("="*60)
    
    # Test 1: servo:ANGLE,DURATION format (from PicoEZSPR)
    print("\n[TEST 1] servo:ANGLE,DURATION format (from old PicoEZSPR)")
    print("-" * 60)
    
    angles = [7, 87, 45, 87, 7]  # S, P, mid, P, S
    for angle in angles:
        cmd = f"servo:{angle},150\n"
        print(f"\n  Sending: {cmd.strip()}")
        ser.reset_input_buffer()
        ser.write(cmd.encode())
        time.sleep(0.2)
        response = ser.read(100)
        print(f"  Response: {response!r}")
        
        # Wait for servo to move
        time.sleep(1.0)
        input(f"  >>> Did servo move to {angle}°? (Press Enter to continue)")
    
    # Test 2: sv + ss command (flash write + move)
    print("\n[TEST 2] sv{s}{p} + ss format (flash write)")
    print("-" * 60)
    
    cmd = "sv007087\n"  # Program S=7, P=87
    print(f"\n  Sending: {cmd.strip()} (programs flash)")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.2)
    response = ser.read(100)
    print(f"  Response: {response!r}")
    
    # Move to S position
    cmd = "ss\n"
    print(f"\n  Sending: {cmd.strip()} (move to S)")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.2)
    response = ser.read(100)
    print(f"  Response: {response!r}")
    time.sleep(1.0)
    input("  >>> Did servo move to S position (7°)? (Press Enter to continue)")
    
    # Move to P position
    cmd = "sp\n"
    print(f"\n  Sending: {cmd.strip()} (move to P)")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.2)
    response = ser.read(100)
    print(f"  Response: {response!r}")
    time.sleep(1.0)
    input("  >>> Did servo move to P position (87°)? (Press Enter to continue)")
    
    # Test 3: Try m{deg} command (probably doesn't exist)
    print("\n[TEST 3] m{deg} format (might not exist)")
    print("-" * 60)
    
    cmd = "m045\n"
    print(f"\n  Sending: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.2)
    response = ser.read(100)
    print(f"  Response: {response!r}")
    time.sleep(1.0)
    input("  >>> Did servo move to 45°? (Press Enter to continue)")
    
    # Test 4: Query firmware version
    print("\n[TEST 4] Firmware version query")
    print("-" * 60)
    
    cmd = "iv\n"
    print(f"\n  Sending: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.2)
    response = ser.read(100)
    print(f"  Firmware version: {response!r}")
    
    print("\n" + "="*60)
    print("SERVO COMMAND TEST COMPLETE")
    print("="*60)
    print("\nBased on which commands worked, we can fix the calibration code.")

def main():
    print("P4PRO Servo Command Direct Test")
    print("=" * 60)
    print("This script tests servo commands directly on the serial port")
    print("to determine which format P4PRO firmware v2.0 supports.")
    print("=" * 60)
    
    # Find P4PRO
    ser = find_p4pro_port()
    if not ser:
        print("\n❌ ERROR: P4PRO controller not found!")
        print("   Check:")
        print("   - USB cable connected")
        print("   - Controller powered on")
        print("   - No other programs using the port")
        sys.exit(1)
    
    try:
        test_servo_commands(ser)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ser.close()
        print("\n✅ Serial port closed")

if __name__ == "__main__":
    main()
