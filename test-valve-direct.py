"""Direct valve test - sends raw commands to P4PRO to test valve hardware."""

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

def test_valve(ser, valve_type, state):
    """Send valve command and check response."""
    if valve_type == "6port":
        cmd = f"v6B{state}\n"
    else:  # 3way
        cmd = f"v3B{state}\n"
    
    print(f"\n📤 Sending: {cmd.strip()}")
    ser.write(cmd.encode())
    time.sleep(0.1)
    response = ser.read(100)
    print(f"📥 Response: {response!r}")
    
    if response == b'1':
        print("✅ Firmware acknowledged command")
        print("🔊 LISTEN FOR VALVE CLICK - did you hear it?")
    else:
        print(f"❌ Unexpected response: {response}")
    
    return response == b'1'

if __name__ == "__main__":
    print("="*60)
    print("P4PRO VALVE HARDWARE TEST")
    print("="*60)
    
    ser = find_p4pro()
    if not ser:
        print("❌ P4PRO not found!")
        exit(1)
    
    print("\nThis will test the valve hardware directly.")
    print("You should hear LOUD CLICKS when valves activate.\n")
    
    input("Press ENTER to test 6-port valves (OPEN)...")
    test_valve(ser, "6port", 1)
    time.sleep(2)
    
    input("Press ENTER to test 6-port valves (CLOSE)...")
    test_valve(ser, "6port", 0)
    time.sleep(2)
    
    input("Press ENTER to test 3-way valves (OPEN)...")
    test_valve(ser, "3way", 1)
    time.sleep(2)
    
    input("Press ENTER to test 3-way valves (CLOSE)...")
    test_valve(ser, "3way", 0)
    
    ser.close()
    print("\n✅ Test complete")
    print("\nIf you heard NO clicks, check:")
    print("  1. Valve cables connected to P4PRO board?")
    print("  2. Valve power supply connected and ON?")
    print("  3. Valve solenoids functional (test with multimeter)?")
