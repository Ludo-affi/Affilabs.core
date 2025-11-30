"""
Test LED Control - Verify batch and individual LED commands
"""
import serial
import time
import sys

def flush_serial(ser):
    """Flush serial buffers."""
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except:
        pass

def send_command(ser, cmd, description):
    """Send command and read response safely."""
    try:
        print(f"\n{description}")
        print(f"  Command: {cmd.decode().strip()}")

        # Flush buffers before sending
        flush_serial(ser)

        # Send command
        ser.write(cmd)
        time.sleep(0.15)  # Increased wait time

        # Read response
        response = ser.read_all()
        if response:
            print(f"  Response: {response}")
        else:
            print(f"  Response: (no data)")

        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_led_control():
    """Test LED on/off using batch and individual commands."""

    print("\n" + "="*60)
    print("🔬 LED CONTROL TEST")
    print("="*60)

    # Connect to device
    try:
        ser = serial.Serial("COM4", 115200, timeout=2)
        print("✅ Connected to COM4")
        time.sleep(0.5)
        flush_serial(ser)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False

    try:
        # Test 1: Turn off all LEDs (emergency command)
        send_command(ser, b"lx\n", "[Test 1] Turning off all LEDs...")
        time.sleep(1)

        # Test 2: Batch command - Turn on channel A
        send_command(ser, b"batch:255,0,0,0\n", "[Test 2] Batch command - Channel A at full brightness")
        time.sleep(2)

        # Test 3: Batch command - Turn on channel B
        send_command(ser, b"batch:0,255,0,0\n", "[Test 3] Batch command - Channel B at full brightness")
        time.sleep(2)

        # Test 4: Batch command - Turn on channel C
        send_command(ser, b"batch:0,0,255,0\n", "[Test 4] Batch command - Channel C at full brightness")
        time.sleep(2)

        # Test 5: Batch command - Turn on channel D
        send_command(ser, b"batch:0,0,0,255\n", "[Test 5] Batch command - Channel D at full brightness")
        time.sleep(2)

        # Test 6: Batch command - All channels at half brightness
        send_command(ser, b"batch:128,128,128,128\n", "[Test 6] Batch command - All channels at 50% (128)")
        time.sleep(2)

        # Test 7: Turn off all LEDs
        send_command(ser, b"batch:0,0,0,0\n", "[Test 7] Batch command - All LEDs off")
        time.sleep(1)

        # Test 8: Individual command - Set intensity and turn on
        send_command(ser, b"ba200\n", "[Test 8a] Individual commands - Set channel A intensity=200")
        time.sleep(0.2)
        send_command(ser, b"la\n", "[Test 8b] Individual commands - Turn on channel A")
        time.sleep(2)

        # Test 9: Turn off all (emergency command)
        send_command(ser, b"lx\n", "[Test 9] Emergency off command (lx)")

        print("\n" + "="*60)
        print("✅ LED TEST COMPLETE")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Always turn off LEDs before closing
        try:
            print("\n🔒 Safety: Turning off all LEDs...")
            flush_serial(ser)
            ser.write(b"lx\n")
            time.sleep(0.15)
            ser.write(b"batch:0,0,0,0\n")
            time.sleep(0.15)
            print("✅ LEDs turned off")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        try:
            ser.close()
            print("✅ Connection closed")
        except:
            pass


if __name__ == "__main__":
    success = test_led_control()
    sys.exit(0 if success else 1)
