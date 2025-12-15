"""Test with debug output to see parsing"""

import time

import serial

print("=" * 70)
print("PARSING DEBUG TEST")
print("=" * 70)

ser = serial.Serial("COM5", 115200, timeout=10)
time.sleep(2)
ser.reset_input_buffer()

# Enable debug mode
print("\n🔧 Enabling debug mode...")
ser.write(b"d\n")
time.sleep(0.5)
while ser.in_waiting > 0:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if line:
        print(f"  {line}")

# Send the test command
print("\n📤 Sending: rankbatch:100,150,200,250,1000,100,10")
print("=" * 70)

ser.write(b"rankbatch:100,150,200,250,1000,100,10\n")
start = time.time()

cycles_seen = 0

while time.time() - start < 60:
    if ser.in_waiting > 0:
        line = ser.readline().decode("utf-8", errors="ignore").strip()

        if line:
            print(f"  {line}")

            if line.startswith("Parsed:"):
                print("\n🔍 DEBUG OUTPUT FOUND!")
                print(f"  {line}\n")

            elif line.startswith("CYCLE:"):
                cycle_num = int(line.split(":")[1])
                cycles_seen = max(cycles_seen, cycle_num)

            elif line.endswith("READ"):
                ser.write(b"ack\n")

            elif line == "BATCH_END":
                elapsed = time.time() - start
                print("\n✅ BATCH_END")
                print(f"⏱️  Time: {elapsed:.1f}s")
                print(f"📊 Cycles: {cycles_seen}")

                if cycles_seen == 10:
                    print("\n✅✅✅ SUCCESS! Fixed! Got 10 cycles as expected!")
                else:
                    print(f"\n⚠️  Got {cycles_seen} cycles (expected 10)")

                break

ser.close()
print("\n📡 Disconnected")
