"""
Test Enhanced Error Handling
Tests new error code dictionary and auto-recovery features
"""
from affipump_controller import AffipumpController
import time

controller = AffipumpController(port='COM8', baudrate=38400, auto_recovery=True)
controller.open()

try:
    print("=== Testing Enhanced Error Handling ===\n")

    # Test 1: Check current status with new error decoding
    print("1. Current Status (with ASCII error decoding):")
    status = controller.get_status(1)
    if status:
        print(f"   Status byte: 0x{status['status']:02x}")
        print(f"   Status char: {status['status_char']}")
        print(f"   Busy: {status['busy']}")
        print(f"   Error: {status['error']}")
        print(f"   Error message: {status['error_msg']}")
        print(f"   Data: {status['data']}")

    print("\n2. Error Code Query (enhanced):")
    error_info = controller.get_error_code(1)
    if error_info:
        print(f"   Error code: {error_info['error_code']}")
        print(f"   Error message: {error_info['error_msg']}")
        print(f"   Busy: {error_info['busy']}")
        print(f"   Data: {error_info['data']}")

    print("\n3. Current Position (with error checking):")
    try:
        pos = controller.get_position(1)
        print(f"   Position: {pos} µL")
    except controller.PumpError as e:
        print(f"   Error detected: {e}")

    print("\n4. Test Error Code Dictionary:")
    print("   Known error codes:")
    for code, info in list(controller.ERROR_CODES.items())[:10]:
        print(f"   {code.decode('ascii', errors='ignore')}: {info['error']} (Busy: {info['busy']})")

    print("\n5. Clear any existing errors:")
    controller.clear_errors(1)
    time.sleep(0.5)

    print("\n6. Re-check status after clear:")
    status = controller.get_status(1)
    if status:
        print(f"   Error: {status['error']}")
        print(f"   Error message: {status['error_msg']}")

    print("\n=== Test Complete ===")

finally:
    controller.close()
