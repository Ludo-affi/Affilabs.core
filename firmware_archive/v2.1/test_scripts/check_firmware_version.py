"""Check firmware version and capabilities"""

import time

import serial

print("=" * 60)
print("FIRMWARE VERSION CHECK")
print("=" * 60)

ser = serial.Serial("COM5", 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

# Send version command
print("Sending version command...")
ser.write(b"v\n")
time.sleep(0.5)

print("\nFirmware response:")
print("-" * 60)
while ser.in_waiting > 0:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if line:
        print(f"  {line}")

print("-" * 60)

# Try a simple rankbatch with 2 cycles to see behavior
print("\nTesting rankbatch with 2 cycles...")
ser.reset_input_buffer()
ser.write(b"rankbatch:100,150,200,250,500,50,2\n")
time.sleep(0.5)

response = []
start = time.time()
while time.time() - start < 15:  # Wait up to 15 seconds
    if ser.in_waiting > 0:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            response.append(line)
            print(f"  {line}")
            if "BATCH_END" in line:
                break

print(f"\nTotal lines received: {len(response)}")
print(f"Time elapsed: {time.time() - start:.1f}s")

# Check if we got cycle information
cycles_seen = [line for line in response if line.startswith("CYCLE:")]
print(f"Cycles detected: {len(cycles_seen)}")
for cycle_line in cycles_seen:
    print(f"  {cycle_line}")

ser.close()
print("\n📡 Disconnected")
