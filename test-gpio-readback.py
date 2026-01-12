"""
GPIO Readback Test - Verify firmware can read back GPIO states
Tests if P4PRO firmware can confirm GPIO outputs are actually set
"""
import serial
import time

# Find P4PRO
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
p4pro_port = None
for port in ports:
    if port.vid == 0x2E8A and port.pid == 0x000A:
        p4pro_port = port.device
        break

if not p4pro_port:
    print("ERROR: P4PRO not found")
    exit(1)

print(f"Found P4PRO on {p4pro_port}")

ser = serial.Serial(p4pro_port, 115200, timeout=1)
time.sleep(2)
ser.reset_input_buffer()

print("\n=== Testing GPIO Readback ===\n")

# Enable debug mode first
print("Enabling debug mode...")
ser.write(b"dbg1\n")
time.sleep(0.2)
response = ser.read(100)
print(f"Debug response: {response}\n")

# Test 6-port valve GPIO 4
print("1. Testing 6-port valve 1 (GPIO 4):")
print("   Sending: v631 (turn ON both)")
ser.write(b"v631\n")
time.sleep(0.3)
response = ser.read(200)
print(f"   Response: {response}")

print("\n   Sending: v630 (turn OFF both)")
ser.write(b"v630\n")
time.sleep(0.3)
response = ser.read(200)
print(f"   Response: {response}")

# Test 3-way valve GPIO 3 (PWM)
print("\n2. Testing 3-way valve 1 (GPIO 3 PWM):")
print("   Sending: v331 (turn ON both)")
ser.write(b"v331\n")
time.sleep(1.0)  # Wait for PWM to stabilize
response = ser.read(200)
print(f"   Response: {response}")

print("\n   Sending: v330 (turn OFF both)")
ser.write(b"v330\n")
time.sleep(0.3)
response = ser.read(200)
print(f"   Response: {response}")

ser.close()

print("\n=== Test Complete ===")
print("If all responses show '1' with '(verified)' messages:")
print("  ✓ GPIO peripheral working correctly")
print("  ✓ Firmware V2.3 GPIO readback successful")
print("  → If valves don't click, issue is valve driver circuit/hardware")
print("\nIf any response shows '0' or 'READBACK FAILED':")
print("  ✗ GPIO peripheral fault detected")
print("  → Possible dead GPIO pin or Pico hardware issue")
