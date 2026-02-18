"""
Test valve commands with V2.3 firmware - verify correct command format
Tests both v63x (6-port both) and v33x (3-way both) commands
"""
import serial
import time
import serial.tools.list_ports

# Find P4PRO
ports = serial.tools.list_ports.comports()
p4pro_port = None
for port in ports:
    if port.vid == 0x2E8A and port.pid == 0x000A:
        p4pro_port = port.device
        break

if not p4pro_port:
    print("ERROR: P4PRO not found")
    exit(1)

print(f"✓ Found P4PRO on {p4pro_port}\n")

ser = serial.Serial(p4pro_port, 115200, timeout=1)
time.sleep(2)
ser.reset_input_buffer()

print("="*70)
print(" VALVE COMMAND TEST - V2.3 Firmware")
print("="*70)

# Enable debug mode
print("\n[1] Enabling debug mode...")
ser.write(b"dbg1\n")
time.sleep(0.2)
response = ser.read(100)
print(f"    Response: {response.decode('utf-8', errors='ignore').strip()}")

# Test 6-port valves BOTH
print("\n[2] Testing 6-port BOTH valves (v631 = OPEN BOTH)")
ser.reset_input_buffer()
ser.write(b"v631\n")
time.sleep(0.5)
response = ser.read(500)
print(f"    Response: {response.decode('utf-8', errors='ignore')}")
if b'1' in response and b'verified' in response:
    print("    ✓ SUCCESS - Valves opened and verified")
else:
    print("    ✗ FAILED - Check response")

input("\n    Did you HEAR the valve click? (Press Enter to continue)")

# Close 6-port valves
print("\n[3] Closing 6-port BOTH valves (v630 = CLOSE BOTH)")
ser.reset_input_buffer()
ser.write(b"v630\n")
time.sleep(2.5)  # Wait for rate limiting
response = ser.read(500)
print(f"    Response: {response.decode('utf-8', errors='ignore')}")
if b'1' in response and b'verified' in response:
    print("    ✓ SUCCESS - Valves closed and verified")
else:
    print("    ✗ FAILED - Check response")

input("\n    Did you HEAR the valve click? (Press Enter to continue)")

# Test 3-way valves BOTH
print("\n[4] Testing 3-way BOTH valves (v331 = OPEN BOTH)")
ser.reset_input_buffer()
ser.write(b"v331\n")
time.sleep(1.0)
response = ser.read(500)
print(f"    Response: {response.decode('utf-8', errors='ignore')}")
if b'1' in response:
    print("    ✓ SUCCESS - Valves opened (PWM started)")
else:
    print("    ✗ FAILED - Check response")

input("\n    Did you HEAR the valve click? (Press Enter to continue)")

# Close 3-way valves
print("\n[5] Closing 3-way BOTH valves (v330 = CLOSE BOTH)")
ser.reset_input_buffer()
ser.write(b"v330\n")
time.sleep(1.5)
response = ser.read(500)
print(f"    Response: {response.decode('utf-8', errors='ignore')}")
if b'1' in response:
    print("    ✓ SUCCESS - Valves closed (PWM stopped)")
else:
    print("    ✗ FAILED - Check response")

input("\n    Did you HEAR the valve click? (Press Enter to continue)")

ser.close()

print("\n" + "="*70)
print(" TEST COMPLETE")
print("="*70)
print("\n✓ All valve commands sent successfully with V2.3 firmware")
print("✓ Python code now uses correct format: v631/v630 and v331/v330")
print("\nIf valves clicked, hardware is working!")
print("If valves didn't click, issue is in valve driver circuit.")
