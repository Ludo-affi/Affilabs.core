"""Test P4PRO servo with correct firmware commands."""
import serial
import time

port = 'COM3'
print(f"Testing P4PRO servo on {port}...\n")

ser = serial.Serial(port, 115200, timeout=1)

# Step 1: Program positions to flash
print("STEP 1: Program S=7, P=87 to flash")
print("Command: sv007087")
ser.reset_input_buffer()
ser.write(b"sv007087\n")
time.sleep(0.2)
resp = ser.read(20)
print(f"Response: {resp!r}")
print(f"Result: {'✅ Programmed' if b'1' in resp else '❌ Failed'}\n")

time.sleep(2)

# Step 2: Move to S-mode
print("STEP 2: Move to S-mode (7°)")
print("Command: ss")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.2)
resp = ser.read(20)
print(f"Response: {resp!r}")
print(f"Result: {'✅ Moved to S' if b'1' in resp else '❌ Failed'}")
print("Listen for servo movement...")

time.sleep(3)

# Step 3: Move to P-mode
print("\nSTEP 3: Move to P-mode (87°)")
print("Command: sp")
ser.reset_input_buffer()
ser.write(b"sp\n")
time.sleep(0.2)
resp = ser.read(20)
print(f"Response: {resp!r}")
print(f"Result: {'✅ Moved to P' if b'1' in resp else '❌ Failed'}")
print("Listen for servo movement...")

time.sleep(3)

# Step 4: Move back to S-mode
print("\nSTEP 4: Move back to S-mode (7°)")
print("Command: ss")
ser.reset_input_buffer()
ser.write(b"ss\n")
time.sleep(0.2)
resp = ser.read(20)
print(f"Response: {resp!r}")
print(f"Result: {'✅ Moved to S' if b'1' in resp else '❌ Failed'}")
print("Listen for servo movement...")

ser.close()
print("\n✅ Test complete!")
