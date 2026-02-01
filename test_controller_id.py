"""Test what the controller actually identifies itself as."""
import serial
import time

print("=" * 80)
print("CONTROLLER IDENTITY TEST")
print("=" * 80)

# Try to find the controller on common ports
ports_to_try = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8']

for port in ports_to_try:
    try:
        print(f"\nTrying {port}...")
        s = serial.Serial(port, 115200, timeout=1.0)
        time.sleep(0.5)
        s.reset_input_buffer()

        # Send ID command
        s.write(b'id\n')
        time.sleep(0.1)

        # Read response
        resp = s.readline().decode('utf-8', errors='ignore').strip()

        if resp:
            print(f"  ✓ Found controller on {port}")
            print(f"  Response: '{resp}'")
            print()
            print("=" * 80)
            print(f"CONTROLLER IDENTIFICATION: {resp}")
            print("=" * 80)

            # Also try version command
            s.write(b'version\n')
            time.sleep(0.1)
            ver_resp = s.readline().decode('utf-8', errors='ignore').strip()
            if ver_resp:
                print(f"Version: {ver_resp}")

            s.close()
            break
        else:
            s.close()
            print(f"  ✗ No response from {port}")

    except Exception as e:
        print(f"  ✗ Error on {port}: {e}")

print("\nTest complete.")
