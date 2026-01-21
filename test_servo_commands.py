"""Test servo commands to validate V2.4 firmware responses.

This script tests different servo command formats and logs responses.
"""

import time
import serial
import serial.tools.list_ports

# Pico USB identifiers
PICO_VID = 0x2E8A
PICO_PID = 0x000A  # USB CDC (serial)

def find_p4spr():
    """Find and connect to P4SPR controller."""
    print("\n🔍 Scanning for Pico devices...")
    found_any = False
    
    for dev in serial.tools.list_ports.comports():
        print(f"   Found: {dev.device} - VID:0x{dev.vid:04X} PID:0x{dev.pid:04X} - {dev.description}")
        
        if dev.pid == PICO_PID and dev.vid == PICO_VID:
            found_any = True
            try:
                print(f"   Attempting to connect to {dev.device}...")
                ser = serial.Serial(
                    port=dev.device,
                    baudrate=115200,
                    timeout=1,
                    write_timeout=3,
                )
                # Verify it's P4SPR
                ser.write(b"id\n")
                time.sleep(0.1)
                response = ser.read(100).decode('utf-8', errors='ignore')
                print(f"   ID response: {response.strip()}")
                if "P4SPR" in response:
                    print(f"✅ Found P4SPR on {dev.device}")
                    return ser
                else:
                    print(f"   Not P4SPR, closing...")
                    ser.close()
            except Exception as e:
                print(f"⚠️ Error checking {dev.device}: {e}")
    
    if not found_any:
        print("❌ No Pico devices found with VID:0x2E8A PID:0x0005")
        print("   Make sure the device is connected and not in use by another program")
    
    return None

def test_servo_command(ser, angle, duration=500):
    """Test a servo command and return response."""
    # V2.4 format: servo:ANGLE,DURATION
    cmd = f"servo:{angle},{duration}\n"
    
    print(f"\n{'='*60}")
    print(f"📤 Sending: {cmd.strip()}")
    
    # Clear input buffer
    ser.reset_input_buffer()
    
    # Send command
    ser.write(cmd.encode())
    time.sleep(0.05)
    
    # Read response
    response = ser.read(100)
    print(f"📥 Response (raw bytes): {response!r}")
    print(f"📥 Response (decoded): {response.decode('utf-8', errors='ignore').strip()}")
    print(f"📥 First byte: {response[0:1]!r}")
    
    # Wait for movement
    time.sleep(0.6)
    
    return response

def test_old_format(ser, angle):
    """Test old servo format for comparison."""
    # Old format: sv{angle:03d}{duration:03d}\n
    cmd = f"sv{angle:03d}500\n"
    
    print(f"\n{'='*60}")
    print(f"📤 Sending OLD format: {cmd.strip()}")
    
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.05)
    
    response = ser.read(100)
    print(f"📥 Response (raw bytes): {response!r}")
    print(f"📥 Response (decoded): {response.decode('utf-8', errors='ignore').strip()}")
    
    time.sleep(0.6)
    return response

def main():
    print("="*60)
    print("P4SPR Servo Command Test")
    print("="*60)
    
    # Find controller
    ser = find_p4spr()
    if not ser:
        print("❌ No P4SPR found!")
        return
    
    try:
        # Get firmware version
        print("\n📋 Checking firmware version...")
        ser.write(b"iv\n")
        time.sleep(0.1)
        version = ser.read(100).decode('utf-8', errors='ignore').strip()
        print(f"   Firmware version: {version}")
        
        # Test various angles with V2.4 format
        test_angles = [0, 45, 90, 135, 180]
        
        print("\n" + "="*60)
        print("Testing V2.4 servo:ANGLE,DURATION format")
        print("="*60)
        
        for angle in test_angles:
            response = test_servo_command(ser, angle, duration=500)
            
            # Analyze response
            if response == b'1':
                print("✅ Response: '1' - Command accepted (V2.4 firmware)")
            elif response == b'6':
                print("✅ Response: '6' - Command accepted (older firmware)")
            elif response == b'':
                print("❌ No response!")
            else:
                print(f"⚠️ Unexpected response: {response!r}")
            
            time.sleep(0.5)
        
        # Test old format for comparison
        print("\n" + "="*60)
        print("Testing OLD sv{angle}{duration} format (for comparison)")
        print("="*60)
        
        test_old_format(ser, 90)
        
        # Return to neutral position
        print("\n" + "="*60)
        print("Returning to neutral position (90°)")
        print("="*60)
        test_servo_command(ser, 90, 500)
        
        print("\n✅ Test complete!")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if ser:
            ser.close()
            print(f"\n🔌 Serial port closed")

if __name__ == "__main__":
    main()
