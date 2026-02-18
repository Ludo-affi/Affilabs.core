"""Test v6B command for 6-port valve control."""

import serial
import serial.tools.list_ports
import time

def find_p4pro():
    """Find P4PRO controller."""
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x2E8A and port.pid == 0x000A:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                ser.write(b"id\n")
                response = ser.readline()
                if b"P4PRO" in response:
                    print(f"✓ Found P4PRO on {port.device}")
                    print(f"  Firmware: {response.decode().strip()}")
                    return ser
                ser.close()
            except Exception as e:
                print(f"Error checking {port.device}: {e}")
    return None

def send_command(ser, cmd, description):
    """Send command and show response."""
    print(f"\n[{description}]")
    print(f"  Sending: {cmd.strip()}")

    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.05)

    response = ser.read(1)
    print(f"  Response: {response!r}")

    if response == b'1':
        print("  ✓ SUCCESS")
        return True
    elif response == b'\x00':
        print("  ✗ FAILED (controller busy or error)")
        return False
    else:
        print("  ? UNEXPECTED RESPONSE")
        return False

if __name__ == "__main__":
    print("=== v6B Command Test ===\n")

    ser = find_p4pro()
    if not ser:
        print("\n✗ P4PRO not found")
        exit(1)

    try:
        # Test 1: Open valves (INJECT)
        print("\n" + "="*50)
        result1 = send_command(ser, "v631\n", "TEST 1: Open both 6-port valves (INJECT) - v631")
        if result1:
            print("\nDid you hear a CLICK? Both valves should be POWERED/ENERGIZED")

        input("\nPress ENTER to continue...")

        # Test 2: Close valves (LOAD)
        print("\n" + "="*50)
        result2 = send_command(ser, "v630\n", "TEST 2: Close both 6-port valves (LOAD) - v630")
        if result2:
            print("\nDid you hear a CLICK? Both valves should be UNPOWERED/DE-ENERGIZED")

        input("\nPress ENTER to continue...")

        # Test 3: Open again
        print("\n" + "="*50)
        result3 = send_command(ser, "v631\n", "TEST 3: Open valves again - v631")

        input("\nPress ENTER to continue...")

        # Test 4: Close again
        print("\n" + "="*50)
        result4 = send_command(ser, "v630\n", "TEST 4: Close valves again - v630")

        # Summary
        print("\n" + "="*50)
        print("\nTEST SUMMARY:")
        print(f"  Open (1st):  {'✓ PASS' if result1 else '✗ FAIL'}")
        print(f"  Close (1st): {'✓ PASS' if result2 else '✗ FAIL'}")
        print(f"  Open (2nd):  {'✓ PASS' if result3 else '✗ FAIL'}")
        print(f"  Close (2nd): {'✓ PASS' if result4 else '✗ FAIL'}")

        if all([result1, result2, result3, result4]):
            print("\n✓ ALL TESTS PASSED - v6B command working correctly")
        else:
            print("\n✗ SOME TESTS FAILED - check controller state or wiring")

    finally:
        ser.close()
        print("\nConnection closed")
