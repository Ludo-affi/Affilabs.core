"""Try different command formats to identify the device."""

import serial
import serial.tools.list_ports
import time

PICO_VID = 0x2E8A
PICO_PID = 0x000A

print("=" * 80)
print("PICO P4SPR - COMMAND FORMAT DISCOVERY")
print("=" * 80)

# Find the device
port_found = None
for dev in serial.tools.list_ports.comports():
    if dev.pid == PICO_PID and dev.vid == PICO_VID:
        port_found = dev.device
        break

if not port_found:
    print("\n✗ PicoP4SPR not found!")
    exit(1)

try:
    ser = serial.Serial(port=port_found, baudrate=115200, timeout=1)

    # Test different command variations
    commands = [
        b"id\n",
        b"id\r\n",
        b"ID\n",
        b"i\n",
        b"?\n",
        b"help\n",
        b"v\n",
        b"version\n",
        b"*IDN?\n",  # SCPI standard
        b"status\n",
    ]

    for cmd in commands:
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)

        # Drain any junk
        ser.read(1000)
        time.sleep(0.05)

        print(f"\nTrying: {cmd}")
        ser.write(cmd)
        time.sleep(0.15)

        response = ser.read(100)
        if response:
            decoded = response.decode('ascii', errors='replace')
            print(f"   Response: {response[:50]}")
            print(f"   Decoded: '{decoded.strip()}'")

            if b'P4SPR' in response or b'pico' in response.lower():
                print("   ✓✓✓ FOUND IDENTIFIER! ✓✓✓")
        else:
            print("   (no response)")

    ser.close()

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
