"""Debug test to see raw cycle counting"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

# Send command with 10 cycles
command = "rankbatch:100,150,200,250,250,250,10\n"
print(f"Sending: {command.strip()}")
print("="*60)

ser.write(command.encode())

# Read ALL output for 25 seconds (should be enough for 10 cycles @ 2s each)
start = time.time()
lines = []

while time.time() - start < 25:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(line)
            lines.append(line)
            
            # Send ACK when needed
            if "READ" in line:
                ser.write(b"ack\n")
            
            # Stop when we see BATCH_END
            if line == "BATCH_END":
                break

ser.close()

print("="*60)
print(f"\nTotal lines: {len(lines)}")
print(f"Total time: {time.time() - start:.2f}s")

# Count cycles
cycles = [l for l in lines if l.startswith("CYCLE:")]
print(f"Cycles seen: {len(cycles)}")
if cycles:
    print(f"First cycle: {cycles[0]}")
    print(f"Last cycle: {cycles[-1]}")
