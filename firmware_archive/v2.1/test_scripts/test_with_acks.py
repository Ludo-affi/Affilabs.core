#!/usr/bin/env python3
"""Test rankbatch with proper ACK responses."""

import serial
import time
import re

def test_cycles():
    port = "COM5"
    baud = 115200
    
    print("Testing: rankbatch:100,150,200,250,1000,100,10")
    print("Sending ACKs after each LED READY signal")
    print("Expected: ~4.4 seconds per cycle, ~44 seconds total")
    print()
    
    try:
        with serial.Serial(port, baud, timeout=0.1) as ser:
            time.sleep(0.5)
            
            # Send command
            command = "rankbatch:100,150,200,250,1000,100,10\n"
            ser.write(command.encode())
            print(f"Sent: {command.strip()}")
            
            cycle_pattern = re.compile(r'CYCLE:(\d+)')
            ready_pattern = re.compile(r'([a-d]):READY')
            cycles_seen = set()
            
            start_time = time.time()
            last_cycle_time = start_time
            
            while True:
                if ser.in_waiting:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"  {line}")
                            
                            # Check for READY - send ACK
                            if ready_pattern.search(line):
                                ser.write(b'\x06')  # ACK character
                                ser.flush()
                            
                            # Check for cycle number
                            match = cycle_pattern.search(line)
                            if match:
                                cycle_num = int(match.group(1))
                                if cycle_num not in cycles_seen:
                                    current_time = time.time()
                                    elapsed = current_time - last_cycle_time
                                    total_elapsed = current_time - start_time
                                    print(f"\n>>> Cycle {cycle_num} at {total_elapsed:.1f}s (interval: {elapsed:.1f}s)\n")
                                    cycles_seen.add(cycle_num)
                                    last_cycle_time = current_time
                            
                            # Check for completion
                            if "BATCH_END" in line:
                                total_time = time.time() - start_time
                                print(f"\n{'='*60}")
                                print(f"🎉 Test completed!")
                                print(f"Total time: {total_time:.1f}s")
                                print(f"Cycles: {len(cycles_seen)}")
                                print(f"Average per cycle: {total_time/len(cycles_seen):.1f}s")
                                print(f"{'='*60}")
                                return len(cycles_seen) == 10
                                
                    except Exception as e:
                        print(f"Error reading: {e}")
                
                # Timeout after 2 minutes
                if time.time() - start_time > 120:
                    print("\n⚠️ Test timeout")
                    break
                
                time.sleep(0.001)
            
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_cycles()
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n⚠️ Test incomplete")
