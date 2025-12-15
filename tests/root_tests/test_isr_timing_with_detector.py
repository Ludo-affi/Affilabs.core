"""
Test ISR timing accuracy using detector signal measurements.
Measures actual LED switching jitter by observing signal changes.
"""
import serial
import time
import numpy as np
from collections import defaultdict
import statistics

def measure_led_cycle_timing(port="COM5", num_cycles=20):
    """
    Measure ISR timing by observing detector signal changes.
    Each LED should produce a distinct signal level at 250ms intervals.
    """
    
    # LED intensities - distinct levels to identify each LED
    led_a = 50   # Low intensity
    led_b = 100  # Medium-low
    led_c = 150  # Medium-high
    led_d = 200  # High intensity
    
    settling_ms = 0  # No settling - exactly 1000ms per cycle
    dark_ms = 0      # No dark period - exactly 1000ms per cycle
    
    print("=" * 70)
    print("ISR TIMING TEST - DETECTOR SIGNAL METHOD")
    print("=" * 70)
    print(f"\nPort: {port}")
    print(f"Test cycles: {num_cycles}")
    print(f"LED intensities: A={led_a}, B={led_b}, C={led_c}, D={led_d}")
    print(f"Expected cycle: 1000ms (250ms per LED)")
    print("\nMeasuring detector signal transitions...\n")
    
    ser = serial.Serial(port, 115200, timeout=2)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.5)
    ser.reset_input_buffer()
    
    # Storage for timing measurements
    cycle_times = []
    led_intervals = defaultdict(list)  # Time between each LED pair
    
    try:
        # Send rankbatch command
        cmd = f"rankbatch:{led_a},{led_b},{led_c},{led_d},{settling_ms},{dark_ms},{num_cycles}\n"
        print(f"Sending: {cmd.strip()}")
        ser.write(cmd.encode())
        
        # Firmware sends BATCH_START first (from rankbatch_start function)
        batch_start = ser.readline().decode().strip()
        # Strip ACK character if concatenated
        batch_start = batch_start.replace('\x06', '').lstrip('6').strip()
        print(f"Status: {batch_start}")
        
        # Then ACK is sent (should be "6" or may be concatenated)
        ack_line = ser.readline().decode().strip()
        ack_line = ack_line.replace('\x06', '').lstrip('6').strip()
        print(f"ACK: {ack_line if ack_line else 'OK'}\n")
        
        cycle_start = time.time()
        last_keepalive = cycle_start
        
        print("Waiting for batch to complete...")
        print("(Sending keepalive every 5 seconds to prevent watchdog timeout)\n")
        
        # Read all responses until BATCH_COMPLETE
        responses = []
        while True:
            try:
                # Send keepalive every 5 seconds to prevent 10s watchdog timeout
                now = time.time()
                if (now - last_keepalive) >= 5.0:
                    ser.write(b"ka\n")
                    last_keepalive = now
                    # Don't wait for ACK, just keep reading batch responses
                
                line = ser.readline().decode().strip()
                elapsed = (time.time() - cycle_start) * 1000  # ms
                if line:
                    # Filter out ACK character (may be concatenated with READY)
                    line = line.replace('\x06', '').lstrip('6').strip()
                    # Filter out keepalive ACKs and empty lines
                    if line and line != "6":
                        responses.append((elapsed, line))
                    if "BATCH_COMPLETE" in line:
                        break
                if elapsed > (num_cycles * 1200 + 5000):  # Timeout with buffer
                    print(f"Timeout after {elapsed:.1f}ms waiting for completion")
                    break
            except:
                break
        
        batch_end = time.time()
        total_batch_time = (batch_end - cycle_start) * 1000  # ms
        
        print(f"\nBatch completed in {total_batch_time:.1f}ms")
        print(f"Expected: {num_cycles * 1000}ms")
        print(f"Error: {total_batch_time - (num_cycles * 1000):.1f}ms\n")
        
        # Parse CYCLE markers to measure individual cycle timing
        cycle_markers = []
        for elapsed, line in responses:
            if line.startswith("CYCLE:"):
                cycle_num = int(line.split(":")[1])
                cycle_markers.append((cycle_num, elapsed))
        
        print(f"Received {len(cycle_markers)} cycle markers")
        
        # Calculate inter-cycle timing
        # Each CYCLE marker represents one complete 4-LED cycle
        if len(cycle_markers) > 1:
            print("\nCycle Timing (each CYCLE marker = one 4-LED cycle):")
            print(f"{'Cycle':<8} {'Time':<10} {'Duration':<12} {'Error':<10}")
            print("-" * 45)
            
            cycle_durations = []
            prev_time = 0
            
            for i, (cycle_num, elapsed) in enumerate(cycle_markers):
                if i == 0:
                    duration = elapsed
                    prev_time = elapsed
                else:
                    duration = elapsed - prev_time
                    prev_time = elapsed
                    cycle_durations.append(duration)
                
                error = duration - 1000.0
                print(f"{cycle_num:<8} {elapsed:>8.1f}ms {duration:>10.1f}ms {error:>9.1f}ms")
            
            if cycle_durations:
                print("\n" + "=" * 70)
                print("CYCLE TIMING STATISTICS")
                print("=" * 70)
                
                mean_cycle = statistics.mean(cycle_durations)
                std_cycle = statistics.stdev(cycle_durations) if len(cycle_durations) > 1 else 0
                min_cycle = min(cycle_durations)
                max_cycle = max(cycle_durations)
                jitter = max_cycle - min_cycle
                
                print(f"\nCycle Duration (excluding first):")
                print(f"  Mean:    {mean_cycle:>7.2f}ms")
                print(f"  StdDev:  {std_cycle:>7.2f}ms")
                print(f"  Min:     {min_cycle:>7.2f}ms")
                print(f"  Max:     {max_cycle:>7.2f}ms")
                print(f"  Jitter:  {jitter:>7.2f}ms")
                
                error = mean_cycle - 1000.0
                print(f"\nAccuracy:")
                print(f"  Expected:  1000.00ms")
                print(f"  Measured:  {mean_cycle:>7.2f}ms")
                print(f"  Error:     {error:>7.2f}ms ({abs(error)/1000*100:.3f}%)")
                
                print("\n" + "=" * 70)
                print("ASSESSMENT")
                print("=" * 70)
                
                if abs(error) < 1.0 and jitter < 2.0:
                    print("✅ EXCELLENT: Cycle timing < 1ms error, jitter < 2ms")
                elif abs(error) < 5.0 and jitter < 10.0:
                    print("✅ GOOD: Cycle timing < 5ms error, jitter < 10ms")
                elif abs(error) < 10.0 and jitter < 20.0:
                    print("⚠️  ACCEPTABLE: Cycle timing < 10ms error, jitter < 20ms")
                else:
                    print(f"❌ POOR: Cycle timing error {abs(error):.1f}ms, jitter {jitter:.1f}ms")
                
                print("=" * 70)
    
    finally:
        ser.close()

if __name__ == "__main__":
    import sys
    
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    measure_led_cycle_timing(port, cycles)
