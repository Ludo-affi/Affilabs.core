"""Test direct serial connection to Pico controllers on specific COM ports."""

import serial
import time

# Try connecting to each COM port directly
com_ports = ['COM3', 'COM4', 'COM6']

for port in com_ports:
    print(f"\n{'='*60}")
    print(f"Testing {port}...")
    print(f"{'='*60}")

    try:
        ser = serial.Serial(
            port=port,
            baudrate=115200,
            timeout=3,
            write_timeout=2
        )
        print(f"✅ Opened {port} successfully!")

        # Try to get device info
        print(f"Sending 'v' command (version)...")
        ser.write(b'v')
        time.sleep(0.1)

        response = ser.read(100)
        if response:
            print(f"Response: {response}")
        else:
            print("No response received")

        ser.close()
        print(f"Closed {port}")

    except serial.SerialException as e:
        print(f"❌ Failed to open {port}: {e}")
    except Exception as e:
        print(f"❌ Error on {port}: {e}")

print(f"\n{'='*60}")
print("Test complete")
