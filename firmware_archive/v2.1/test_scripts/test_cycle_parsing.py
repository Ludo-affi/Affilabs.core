"""Test different cycle counts to isolate parsing issue"""
import serial
import time

ser = serial.Serial('COM5', 115200, timeout=2)
time.sleep(2)
ser.reset_input_buffer()

test_cases = [
    ("1 cycle", "rankbatch:100,150,200,250,250,250,1\n"),
    ("5 cycles", "rankbatch:100,150,200,250,250,250,5\n"),
    ("2 cycles", "rankbatch:100,150,200,250,250,250,2\n"),
]

for name, command in test_cases:
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Command: {command.strip()}")
    print('='*60)
    
    ser.reset_input_buffer()
    ser.write(command.encode())
    time.sleep(0.1)
    
    start = time.time()
    cycle_count = 0
    
    while time.time() - start < 15:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                if line.startswith("CYCLE:"):
                    cycle_count += 1
                    print(f"  {line}")
                elif "BATCH_END" in line:
                    print(f"  {line}")
                    break
                elif "READ" in line:
                    ser.write(b"ack\n")
    
    elapsed = time.time() - start
    print(f"Result: {cycle_count} cycles in {elapsed:.2f}s")
    time.sleep(1)

ser.close()
