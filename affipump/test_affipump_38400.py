"""
Test Cavro pumps with correct PuTTY settings: 38400 baud
"""
import serial
import time

def send_command(ser, command_str):
    """Send command and get response"""
    command = command_str.encode() + b'\r'
    print(f"\nSending: {command_str}")
    ser.write(command)
    time.sleep(0.3)

    response = ser.read(100)
    print(f"Response ({len(response)} bytes): {response}")

    if len(response) > 0:
        print(f"Hex: {' '.join(f'{b:02X}' for b in response)}")
        if len(response) > len(command) + 1:
            status = response[-2]
            print(f"✅ Status byte: 0x{status:02X} ({status:08b})")

            # Decode status
            if status & 0x20:
                print("  - Pump is IDLE")
            if status & 0x10:
                print("  - Pump is INITIALIZED")
            if status == 0x60:
                print("  - Ready for commands!")

    return response

print("="*60)
print("Testing Cavro Pumps with PuTTY settings (38400 baud)")
print("="*60)

try:
    # Open serial port with PuTTY settings
    ser = serial.Serial(
        port='COM8',
        baudrate=38400,  # CORRECT BAUD RATE!
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=1
    )

    print(f"\n✅ Port opened: {ser.name}")
    print(f"Baud rate: {ser.baudrate}")

    time.sleep(0.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Test 1: Query status
    print("\n" + "="*60)
    print("Test 1: Query pump 1 status")
    print("="*60)
    send_command(ser, "/1?")

    # Test 2: Initialize pumps
    print("\n" + "="*60)
    print("Test 2: Initialize both pumps (per engineer notes)")
    print("="*60)
    send_command(ser, "/AZR")

    print("\nWaiting 5 seconds for initialization...")
    time.sleep(5)

    # Test 3: Query status after init
    print("\n" + "="*60)
    print("Test 3: Query status after initialization")
    print("="*60)
    send_command(ser, "/1?")
    send_command(ser, "/2?")

    # Test 4: Query valve positions
    print("\n" + "="*60)
    print("Test 4: Query valve positions")
    print("="*60)
    send_command(ser, "/1?6")  # Query valve position
    send_command(ser, "/2?6")

    # Test 5: Query plunger positions
    print("\n" + "="*60)
    print("Test 5: Query plunger positions")
    print("="*60)
    send_command(ser, "/1?")
    send_command(ser, "/2?")

    ser.close()
    print("\n" + "="*60)
    print("✅ SUCCESS! Pumps are responding at 38400 baud!")
    print("="*60)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
