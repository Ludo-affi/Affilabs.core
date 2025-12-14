#!/usr/bin/env python3
"""Test with longer timeout to see if all 10 cycles complete."""

import serial
import time
import re

def test_cycles():
    port = "COM5"
    baud = 115200
    
    print("Testing: rankbatch:100,150,200,250,1000,100,10")
    print("Waiting up to 5 minutes to see if all 10 cycles complete...")
    print()
    
    with serial.Serial(port, baud, timeout=1) as ser:
        time.sleep(0.5)
        
        # Send command
        command = "rankbatch:100,150,200,250,1000,100,10\n"
        ser.write(command.encode())
        
        cycle_pattern = re.compile(r'CYCLE:\s*(\d+)')
        cycles_seen = set()
        
        start_time = time.time()
        last_cycle_time = start_time
        timeout = 300  # 5 minutes
        
        while time.time() - start_time < timeout:
            if ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    match = cycle_pattern.search(line)
                    if match:
                        cycle_num = int(match.group(1))
                        if cycle_num not in cycles_seen:
                            current_time = time.time()
                            elapsed = current_time - last_cycle_time
                            total_elapsed = current_time - start_time
                            print(f"  Cycle {cycle_num} at {total_elapsed:.1f}s (+{elapsed:.1f}s)")
                            cycles_seen.add(cycle_num)
                            last_cycle_time = current_time
                            
                            if len(cycles_seen) >= 10:
                                print(f"\n🎉 All 10 cycles completed in {total_elapsed:.1f}s!")
                                return True
                    
                except Exception as e:
                    pass
            
            time.sleep(0.01)
        
        total_time = time.time() - start_time
        print(f"\n⚠️ Timeout after {total_time:.1f}s")
        print(f"Cycles seen: {sorted(cycles_seen)}")
        print(f"Total cycles: {len(cycles_seen)}")
        return False

if __name__ == "__main__":
    test_cycles()
