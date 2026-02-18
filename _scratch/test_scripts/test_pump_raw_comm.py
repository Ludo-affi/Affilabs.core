"""Test raw pump communication"""
import time
import serial
import serial.tools.list_ports

def test_raw_pump_comm():
    """Test raw serial communication with pump"""

    # Try both ports
    for test_port in ['COM3', 'COM8']:
        print(f"\n{'='*60}")
        print(f"Testing {test_port}")
        print('='*60)

        try:
            ser = serial.Serial(
                port=test_port,
                baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            time.sleep(0.5)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            print(f"[OK] Connected to {test_port}")

            # Test commands
            test_commands = [
                ("/1?", "Pump 1 status"),
                ("/2?", "Pump 2 status"),
                ("/A?", "Broadcast status"),
            ]

            for cmd, desc in test_commands:
                print(f"\n--- Testing: {desc} ({cmd}) ---")
                ser.reset_input_buffer()
                cmd_bytes = (cmd + '\r').encode()
                ser.write(cmd_bytes)
                print(f"Sent: {repr(cmd_bytes)}")

                time.sleep(0.2)

                response = ser.read(256)
                print(f"Raw Response ({len(response)} bytes): {repr(response)}")

                if response:
                    # Try to decode
                    try:
                        decoded = response.decode('ascii', errors='replace')
                        print(f"Decoded: {repr(decoded)}")
                    except:
                        print("Could not decode")
                else:
                    print("[WARN] No response received!")

            ser.close()
            print(f"\n[OK] Closed {test_port}")

        except Exception as e:
            print(f"[ERROR] Failed on {test_port}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_raw_pump_comm()
