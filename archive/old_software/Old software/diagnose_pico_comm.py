"""Diagnose PicoP4SPR communication."""

import time

import serial
import serial.tools.list_ports

PICO_VID = 0x2E8A
PICO_PID = 0x000A

print("=" * 80)
print("PICO P4SPR COMMUNICATION DIAGNOSTIC")
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

# Try to communicate
try:
    print(f"\nOpening {port_found} at 115200 baud...")
    ser = serial.Serial(port=port_found, baudrate=115200, timeout=1)

    # Flush buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    print("\nTest 1: Sending 'id\\n' command...")
    ser.write(b"id\n")
    time.sleep(0.1)

    # Read everything available
    raw_response = ser.read(100)
    print(f"   Raw bytes: {raw_response}")
    print(f"   Decoded: '{raw_response.decode('ascii', errors='replace')}'")
    print(f"   Length: {len(raw_response)} bytes")

    # Try again with longer delay
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    print("\nTest 2: Sending 'id\\n' with longer delay...")
    ser.write(b"id\n")
    time.sleep(0.2)

    raw_response = ser.read(100)
    print(f"   Raw bytes: {raw_response}")
    print(f"   Decoded: '{raw_response.decode('ascii', errors='replace')}'")
    print(f"   Length: {len(raw_response)} bytes")

    # Try readline
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    print("\nTest 3: Using readline()...")
    ser.write(b"id\n")
    line = ser.readline()
    print(f"   Raw bytes: {line}")
    print(f"   Decoded: '{line.decode('ascii', errors='replace')}'")
    print(f"   First 5 chars: '{line[0:5].decode('ascii', errors='replace')}'")

    # Firmware version
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)
    print("\nTest 4: Firmware version 'iv' ...")
    ser.write(b"iv\n")
    line = ser.readline()
    print(f"   Version: '{line.decode('ascii', errors='replace').strip()}'")

    # Temperature command(s)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)
    print("\nTest 5: Temperature 'it' ...")
    ser.write(b"it\n")
    line = ser.readline()
    print(f"   'it' reply: '{line.decode('ascii', errors='replace').strip()}'")

    # Optional LED-board temperature (if supported by FW)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)
    print("\nTest 6: LED-board temperature 'ilt' (if available) ...")
    ser.write(b"ilt\n")
    time.sleep(0.15)
    line = ser.readline()
    if line:
        print(f"   'ilt' reply: '{line.decode('ascii', errors='replace').strip()}'")
    else:
        print("   No response to 'ilt' (likely unsupported)")

    ser.close()
    print("\n✓ Diagnostic complete")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback

    traceback.print_exc()
