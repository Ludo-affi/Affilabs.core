"""Test clearing stale data and proper initialization."""

import serial
import serial.tools.list_ports
import time

PICO_VID = 0x2E8A
PICO_PID = 0x000A

print("=" * 80)
print("PICO P4SPR - CLEAR AND REINITIALIZE TEST")
print("=" * 80)

# Find the device
port_found = None
for dev in serial.tools.list_ports.comports():
    if dev.pid == PICO_PID and dev.vid == PICO_VID:
        port_found = dev.device
        print(f"\n✓ Found PicoP4SPR on {dev.device}")
        break

if not port_found:
    print("\n✗ PicoP4SPR not found!")
    exit(1)

try:
    print(f"\nOpening {port_found} at 115200 baud...")
    ser = serial.Serial(port=port_found, baudrate=115200, timeout=1)

    print("\nStep 1: Draining any stale data...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.2)

    # Read and discard everything
    stale_data = ser.read(1000)
    if stale_data:
        print(f"   Cleared {len(stale_data)} bytes: {stale_data[:50]}")
    else:
        print("   No stale data found")

    print("\nStep 2: Sending newline to clear any partial command...")
    ser.write(b"\n")
    time.sleep(0.1)
    junk = ser.read(100)
    if junk:
        print(f"   Response: {junk}")

    print("\nStep 3: Flushing buffers again...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    print("\nStep 4: Sending 'id\\n' command...")
    ser.write(b"id\n")
    time.sleep(0.15)

    response = ser.readline()
    print(f"   Response: {response}")
    print(f"   Decoded: '{response.decode('ascii', errors='replace').strip()}'")

    if b'P4SPR' in response:
        print("\n✓ SUCCESS! Device identified as P4SPR")

        # Try to get version
        print("\nStep 5: Getting firmware version with 'iv\\n'...")
        ser.write(b"iv\n")
        time.sleep(0.1)
        version = ser.readline()
        print(f"   Version: '{version.decode('ascii', errors='replace').strip()}'")
    else:
        print(f"\n✗ FAILED - Expected 'P4SPR', got: '{response.decode('ascii', errors='replace').strip()}'")

        # Try sending multiple newlines to reset state
        print("\nStep 6: Trying to reset device state with multiple newlines...")
        for i in range(3):
            ser.write(b"\n")
            time.sleep(0.05)

        ser.reset_input_buffer()
        time.sleep(0.2)

        print("\nStep 7: Retry 'id\\n' command...")
        ser.write(b"id\n")
        time.sleep(0.15)
        response = ser.readline()
        print(f"   Response: {response}")
        print(f"   Decoded: '{response.decode('ascii', errors='replace').strip()}'")

    ser.close()
    print("\n✓ Test complete")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
