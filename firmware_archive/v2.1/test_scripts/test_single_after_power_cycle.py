"""Single isolated test after power cycle"""
import serial
import time

print("="*70)
print("SINGLE ISOLATED TEST")
print("="*70)
print("\n⚠️  This test assumes device was JUST power cycled")
print("    and this is the FIRST command sent.\n")
print("="*70)

input("\nPress ENTER after power cycling the device...")

print("\n🔌 Connecting to COM5...")
connected = False
for attempt in range(5):
    try:
        ser = serial.Serial('COM5', 115200, timeout=30)
        time.sleep(3)
        ser.reset_input_buffer()
        connected = True
        print("✅ Connected\n")
        break
    except Exception as e:
        print(f"   Attempt {attempt + 1}/5 failed: {e}")
        time.sleep(2)

if not connected:
    print("❌ Could not connect to device")
    exit(1)

# Single test with the exact requested configuration
command = "rankbatch:100,150,200,250,1000,100,10\n"
print(f"📤 Sending: {command.strip()}")
print(f"   Expected: 10 cycles @ ~4.4s each = ~44s total\n")

ser.write(command.encode())
start_time = time.time()

cycles_seen = []
got_batch_start = False
got_batch_end = False

print("📊 Progress:")
print("-"*70)

while time.time() - start_time < 60:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()

        if line:
            if line.startswith("BATCH_START"):
                got_batch_start = True
                print("🚀 BATCH_START\n")

            elif line.startswith("CYCLE:"):
                cycle_num = int(line.split(":")[1])
                cycles_seen.append(cycle_num)
                elapsed = time.time() - start_time
                print(f"⏱️  CYCLE {cycle_num}/10 (elapsed: {elapsed:.1f}s)")
                print("   ", end="", flush=True)

            elif line.endswith("READY"):
                ch = line.split(":")[0].upper()
                print(f"{ch}:", end=" ", flush=True)

            elif line.endswith("READ"):
                ser.write(b"ack\n")
                print("📸", end=" ", flush=True)

            elif line.endswith("DONE"):
                print("✓", end=" ", flush=True)

            elif line.startswith("CYCLE_END"):
                print()

            elif line == "BATCH_END":
                got_batch_end = True
                elapsed = time.time() - start_time
                print(f"\n✅ BATCH_END\n")
                print(f"⏱️  Total time: {elapsed:.1f}s")
                print(f"📊 Cycles executed: {len(cycles_seen)}")
                if len(cycles_seen) > 0:
                    avg = elapsed / len(cycles_seen)
                    print(f"⚡ Average: {avg:.2f}s per cycle")
                break

if time.time() - start_time >= 60:
    print(f"\n⚠️  Timeout after 60s")

print("-"*70)

# Analysis
print("\nANALYSIS:")
print(f"  BATCH_START received: {'✅ YES' if got_batch_start else '❌ NO'}")
print(f"  BATCH_END received:   {'✅ YES' if got_batch_end else '❌ NO'}")
print(f"  Cycles executed:      {len(cycles_seen)}")
print(f"  Expected cycles:      10")

if len(cycles_seen) == 10 and got_batch_start and got_batch_end:
    print(f"\n✅ SUCCESS - Test passed!")
elif len(cycles_seen) == 1:
    print(f"\n❌ PARSING BUG - Cycle count not parsed, defaulted to 1")
elif len(cycles_seen) > 10:
    print(f"\n❌ EXECUTION BUG - Too many cycles, not stopping at requested count")
elif len(cycles_seen) < 10 and len(cycles_seen) > 1:
    print(f"\n❌ EARLY TERMINATION - Stopped before completing requested cycles")
else:
    print(f"\n❌ UNEXPECTED BEHAVIOR")

if not got_batch_start:
    print(f"⚠️  WARNING: No BATCH_START - may be continuing from queued command")
if not got_batch_end:
    print(f"⚠️  WARNING: No BATCH_END - function may not have exited properly")

ser.close()
print("\n📡 Disconnected")
