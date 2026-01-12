"""Comprehensive valve diagnostic - tests all possible valve commands."""

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
                response = ser.readline().decode().strip()
                if "P4PRO" in response:
                    print(f"✅ Found P4PRO on {port.device}")
                    return ser
                ser.close()
            except:
                pass
    return None

def send_cmd(ser, cmd, desc):
    """Send command and show response."""
    print(f"\n📤 {desc}")
    print(f"   Command: {cmd.strip()}")
    ser.reset_input_buffer()
    ser.write(cmd.encode())
    time.sleep(0.1)
    response = ser.read(100)
    print(f"   Response: {response!r}")
    return response

if __name__ == "__main__":
    print("="*70)
    print("P4PRO VALVE DIAGNOSTIC - TESTING ALL VALVE COMMANDS")
    print("="*70)
    
    ser = find_p4pro()
    if not ser:
        print("❌ P4PRO not found!")
        exit(1)
    
    # Get firmware version
    send_cmd(ser, "iv\n", "Getting firmware version")
    
    # Test if there's a valve enable command
    print("\n" + "="*70)
    print("TESTING POSSIBLE VALVE ENABLE COMMANDS")
    print("="*70)
    
    possible_enables = [
        ("ve\n", "Valve Enable (ve)"),
        ("valve:enable\n", "Valve Enable (valve:enable)"),
        ("knx:enable\n", "KNX Enable (knx:enable)"),
        ("valve:on\n", "Valve On (valve:on)"),
    ]
    
    for cmd, desc in possible_enables:
        send_cmd(ser, cmd, desc)
    
    # Test individual valve commands
    print("\n" + "="*70)
    print("TESTING INDIVIDUAL VALVE COMMANDS")
    print("="*70)
    
    input("\nPress ENTER to test 6-port valve CH1 OPEN (v611)...")
    send_cmd(ser, "v611\n", "6-port CH1 OPEN (v611)")
    print("🔊 Did you hear a click?")
    
    time.sleep(1)
    
    input("\nPress ENTER to test 6-port valve CH1 CLOSE (v610)...")
    send_cmd(ser, "v610\n", "6-port CH1 CLOSE (v610)")
    print("🔊 Did you hear a click?")
    
    time.sleep(1)
    
    # Test batch commands
    print("\n" + "="*70)
    print("TESTING BATCH VALVE COMMANDS")
    print("="*70)
    
    input("\nPress ENTER to test BOTH 6-port valves OPEN (v6B1)...")
    send_cmd(ser, "v6B1\n", "BOTH 6-port OPEN (v6B1)")
    print("🔊 Did you hear TWO clicks?")
    
    time.sleep(1)
    
    input("\nPress ENTER to test BOTH 6-port valves CLOSE (v6B0)...")
    send_cmd(ser, "v6B0\n", "BOTH 6-port CLOSE (v6B0)")
    print("🔊 Did you hear TWO clicks?")
    
    ser.close()
    
    print("\n" + "="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70)
    print("\nIf firmware responds with b'1' but you hear NO clicks:")
    print("  ❌ Valve driver circuitry on P4PRO board may be disabled/broken")
    print("  ❌ Valves may not be connected to P4PRO valve output headers")
    print("  ❌ Check with multimeter: voltage on valve output pins when commanded?")
