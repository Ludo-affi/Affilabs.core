"""Check firmware version of connected PicoP4SPR"""

import serial
import serial.tools.list_ports
import time

def find_pico():
    """Find Pico COM port."""
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x2E8A:  # Pico VID
            return port.device
    return None

def check_version(port):
    """Query firmware version."""
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(1.5)  # Give device time to boot

        print(f"Connected to {port}")
        print("Sending version query...")

        # Clear buffer
        ser.reset_input_buffer()

        # Try 'id' command
        ser.write(b'id\n')
        time.sleep(0.3)

        print("\nResponse:")
        for i in range(5):
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line:
                print(f"  {line}")
                if line.startswith('V'):
                    print(f"\n✅ Firmware Version: {line}")

        ser.close()
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("=" * 60)
    print("PicoP4SPR Firmware Version Check")
    print("=" * 60)

    port = find_pico()
    if not port:
        print("\n❌ No Pico device found")
        return

    print(f"\nFound Pico on: {port}")
    check_version(port)

if __name__ == "__main__":
    main()
