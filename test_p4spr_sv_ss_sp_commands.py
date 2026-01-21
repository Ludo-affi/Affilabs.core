"""\
Test P4SPR V2.4 ACTUAL servo commands: sv, ss, sp

Based on firmware analysis, P4SPR V2.4 CYCLE_SYNC does NOT have servo:ANGLE,DURATION.
Instead it uses:
  - sv{SSS}{PPP}  - Set S and P angles (3 digits each, 0-180 degrees)
  - ss            - Move to S position
  - sp            - Move to P position
  - sf            - Flash positions to EEPROM (we won't use this)
"""

import time

from affilabs.core.hardware_manager import HardwareManager


def get_serial_port(hm):
    """Get the underlying serial port from HardwareManager."""
    ctrl = hm.ctrl
    if ctrl is None:
        return None
    
    # Unwrap HAL adapter if present
    low_ctrl = getattr(ctrl, "_ctrl", ctrl)
    ser = getattr(low_ctrl, "_ser", None)
    return ser


def send_command(ser, cmd: str, description: str) -> bytes:
    """Send a command and return raw response."""
    print(f"\n{'='*70}")
    print(f"Command: {cmd.strip()}")
    print(f"Description: {description}")
    
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.1)
    
    response = ser.read(100)
    print(f"Response (raw): {response!r}")
    try:
        decoded = response.decode('utf-8', errors='ignore').strip()
        if decoded:
            print(f"Response (text): {decoded}")
    except Exception:
        pass
    
    return response


def main() -> None:
    print("=" * 70)
    print("P4SPR V2.4 SERVO COMMANDS TEST: sv, ss, sp")
    print("=" * 70)
    
    print("\nConnecting via HardwareManager...")
    hm = HardwareManager()
    hm.scan_and_connect(auto_connect=True)
    
    # Wait for connection
    t0 = time.time()
    while time.time() - t0 < 15.0:
        if hm.ctrl and hm.usb:
            break
        time.sleep(0.5)
    
    if not hm.ctrl or not hm.usb:
        print("\n❌ Hardware not connected")
        return
    
    ser = get_serial_port(hm)
    if ser is None:
        print("\n❌ Could not get serial port from controller")
        return
    
    print(f"  Serial port: {ser.port}, is_open={ser.is_open}")
    
    # Test sequence
    print("\n" + "=" * 70)
    print("TEST SEQUENCE")
    print("=" * 70)
    
    # Test 1: Set positions with sv command
    print("\n[1] Set S=5°, P=175° using sv command")
    print("    Format: sv{SSS}{PPP} where SSS=005, PPP=175")
    resp = send_command(ser, "sv005175\n", "Set S=5°, P=175° in RAM")
    
    if b"6" in resp:
        print("  ✅ Command accepted (response: '6')")
    else:
        print(f"  ⚠️ Unexpected response")
    
    time.sleep(0.3)
    
    # Test 2: Move to S position
    print("\n[2] Move to S position (should be 5°)")
    resp = send_command(ser, "ss\n", "Move servo to S position")
    
    if b"6" in resp:
        print("  ✅ Command accepted")
    else:
        print(f"  ⚠️ Unexpected response")
    
    time.sleep(0.7)  # Wait for movement
    input("  >>> Did servo move to ~5°? Press Enter to continue...")
    
    # Test 3: Move to P position
    print("\n[3] Move to P position (should be 175°)")
    resp = send_command(ser, "sp\n", "Move servo to P position")
    
    if b"6" in resp:
        print("  ✅ Command accepted")
    else:
        print(f"  ⚠️ Unexpected response")
    
    time.sleep(0.7)
    input("  >>> Did servo move to ~175°? Press Enter to continue...")
    
    # Test 4: Try different positions
    print("\n[4] Set S=45°, P=135°")
    resp = send_command(ser, "sv045135\n", "Set S=45°, P=135°")
    time.sleep(0.3)
    
    print("\n[5] Move to S (45°)")
    resp = send_command(ser, "ss\n", "Move to S position")
    time.sleep(0.7)
    input("  >>> Did servo move to ~45°? Press Enter to continue...")
    
    print("\n[6] Move to P (135°)")
    resp = send_command(ser, "sp\n", "Move to P position")
    time.sleep(0.7)
    input("  >>> Did servo move to ~135°? Press Enter to continue...")
    
    # Test 5: Middle position
    print("\n[7] Set S=90°, P=90° (both middle)")
    resp = send_command(ser, "sv090090\n", "Set both to 90°")
    time.sleep(0.3)
    
    print("\n[8] Move to S (90°)")
    resp = send_command(ser, "ss\n", "Move to 90°")
    time.sleep(0.7)
    input("  >>> Did servo move to ~90°? Press Enter to continue...")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nPlease report:")
    print("  1. Which commands moved the servo")
    print("  2. Which angles worked")
    print("  3. Any error responses")


if __name__ == "__main__":
    main()
