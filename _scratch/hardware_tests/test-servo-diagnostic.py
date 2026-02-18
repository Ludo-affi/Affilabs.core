"""
Servo Diagnostic Test - Check if servo commands are working
Tests servo movement and firmware response with V2.3
Tests the EXACT commands used by calibration_orchestrator.py
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
print(" SERVO DIAGNOSTIC TEST - V2.3 Firmware")
print("="*70)

# Enable debug mode
print("\n[1] Enabling debug mode...")
ser.write(b"dbg1\n")
time.sleep(0.2)
response = ser.read(100)
print(f"    Response: {response.decode('utf-8', errors='ignore').strip()}")

# Test EXACT sequence from calibration_orchestrator.py
print("\n[2] Testing EXACT calibration sequence:")
print("    Step 1: Park servo (PWM=1, removes backlash)")

# Convert PWM 1 to degrees (same as controller.py does)
s_pos_pwm = 7  # From device config S=4 degrees
degrees_park = int(5 + (1 * 170 / 255))
duration_ms = 500

print(f"    Sending: servo:{degrees_park},{duration_ms}")
ser.reset_input_buffer()
ser.write(f"servo:{degrees_park},{duration_ms}\n".encode())
time.sleep(0.7)
response = ser.read(100)
print(f"    Response: {response!r}")
if b'1' in response or b'\x01' in response:
    print("    ✓ Firmware responded SUCCESS")
else:
    print(f"    ✗ Unexpected response: {response}")

input("\n    Did the servo MOVE to park position? (Press Enter to continue)")

print("\n    Step 2: Move to S-position (PWM=7)")
degrees_s = int(5 + (s_pos_pwm * 170 / 255))
print(f"    Sending: servo:{degrees_s},{duration_ms}")
ser.reset_input_buffer()
ser.write(f"servo:{degrees_s},{duration_ms}\n".encode())
time.sleep(0.7)
response = ser.read(100)
print(f"    Response: {response!r}")
if b'1' in response or b'\x01' in response:
    print("    ✓ Firmware responded SUCCESS")
else:
    print(f"    ✗ Unexpected response: {response}")

input("\n    Did the servo MOVE to S position? (Press Enter to continue)")

# Test alternative: Use ss command (move to S from flash)
print("\n[3] Testing legacy 'ss' command (move to S from EEPROM)")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.7)
response = ser.read(100)
print(f"    Response: {response!r}")

input("\n    Did the servo MOVE? (Press Enter to continue)")

# Test P position
print("\n[4] Testing 'sp' command (move to P from EEPROM)")
ser.reset_input_buffer()
ser.write(b"sp\n")
time.sleep(0.7)
response = ser.read(100)
print(f"    Response: {response!r}")

input("\n    Did the servo MOVE? (Press Enter to continue)")

# Check current servo values in flash
print("\n[5] Reading servo values from flash (sr)")
ser.reset_input_buffer()
ser.write(b"sr\n")
time.sleep(0.2)
response = ser.read(100)
print(f"    Response: {response!r}")
print(f"    Decoded: {response.decode('utf-8', errors='ignore').strip()}")

ser.close()

print("\n" + "="*70)
print(" DIAGNOSTIC COMPLETE")
print("="*70)
print("\nTroubleshooting:")
print("  - If firmware responds '1' but servo doesn't move:")
print("    → Servo power issue or mechanical jam")
print("  - If firmware doesn't respond:")
print("    → Command format wrong or serial communication issue")
print("  - If firmware responds '0' or NAK:")
print("    → Servo parameters out of range (5-175 degrees)")
