"""Simple firmware version check using pyserial."""

import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM5"

print(f"\n{'='*60}")
print(f"FIRMWARE VERSION CHECK - {port}")
print(f"{'='*60}")

try:
    # Note: Port may be in use by app - this will fail if exclusive lock
    ser = serial.Serial(port, 115200, timeout=1)
    time.sleep(0.2)

    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Send version command
    print("Sending 'iv' command...")
    ser.write(b"iv\n")
    time.sleep(0.3)

    # Read response
    response = ""
    start = time.time()
    while time.time() - start < 0.5:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
            time.sleep(0.05)

    ser.close()

    print(f"\n{'='*60}")
    print("RESPONSE:")
    print(f"{'='*60}")
    if response:
        print(response)

        if "V2.2" in response:
            print("\n✅ NEW FIRMWARE DETECTED (V2.2)")
            print("   ISR bug fixes are active")
        elif "V2.1" in response or "V2.0" in response:
            print("\n⚠️  OLD FIRMWARE DETECTED")
            print("   Flash didn't work - still running old firmware!")
        else:
            print(f"\n❓ Version: {response.strip()}")
    else:
        print("❌ No response")
        print("   (Port may be locked by running application)")
    print(f"{'='*60}\n")

except serial.SerialException as e:
    print(f"\n❌ Port in use: {e}")
    print("\n💡 Stop the application first, then run:")
    print(f"   python scripts\\check_firmware_version.py {port}\n")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
