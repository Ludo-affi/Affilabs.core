"""Firmware ISR Timing Validation.

Tests the Pico firmware LED sequencer ISR to verify:
1. LED cycle timing (1000ms total, 250ms per LED)
2. READY signal timing (should arrive 50ms after LED turn-on)
3. Timing jitter and drift over multiple cycles
4. USB communication overhead

Expected timing:
- LED A: 0-250ms, READY @ 50ms
- LED B: 250-500ms, READY @ 300ms  
- LED C: 500-750ms, READY @ 550ms
- LED D: 750-1000ms, READY @ 800ms
"""

import serial
import time
import statistics
from collections import defaultdict


def test_firmware_timing(port="COM5", num_cycles=10):
    """Test firmware ISR timing accuracy over multiple cycles."""
    
    print(f"\n{'='*70}")
    print(f"FIRMWARE ISR TIMING VALIDATION")
    print(f"{'='*70}\n")
    print(f"Port: {port}")
    print(f"Test cycles: {num_cycles}")
    print(f"Expected: 1000ms/cycle, 250ms/LED, READY @ +50ms\n")
    
    # Connect to Pico
    ser = serial.Serial(port, 115200, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    # Clear any startup messages
    time.sleep(0.2)
    ser.read_all()
    
    # Storage for timing measurements
    cycle_times = []
    ready_times = defaultdict(list)  # {led: [time_from_start, ...]}
    led_durations = defaultdict(list)  # {led: [duration_ms, ...]}
    
    print("Starting rankbatch command...\n")
    
    for cycle in range(num_cycles):
        # Clear buffer
        ser.reset_input_buffer()
        
        # Send rankbatch command and start timer
        cmd_start = time.perf_counter()
        ser.write(b"rankbatch:a:150,b:150,c:150,d:150\n")
        
        # Track READY signals
        cycle_ready_times = {}
        led_order = []
        
        # Collect all 4 READY signals for this cycle
        response_buffer = b""
        all_responses = []  # Debug: collect all responses
        timeout_start = time.perf_counter()
        
        while len(cycle_ready_times) < 4:
            chunk = ser.read(128)
            if not chunk:
                # Timeout after 2 seconds
                if time.perf_counter() - timeout_start > 2.0:
                    break
                time.sleep(0.01)
                continue
            
            response_buffer += chunk
            all_responses.append(chunk)  # Debug
            
            # Parse READY signals
            lines = response_buffer.split(b'\n')
            for line in lines[:-1]:  # Process complete lines
                line = line.strip()
                if b':READY' in line:
                    led_char = chr(line[0]) if len(line) > 0 else '?'
                    if led_char in 'abcd' and led_char not in cycle_ready_times:
                        timestamp = time.perf_counter()
                        cycle_ready_times[led_char] = timestamp
                        led_order.append(led_char)
            
            # Keep incomplete line in buffer
            response_buffer = lines[-1]
        
        cycle_end = time.perf_counter()
        
        if len(cycle_ready_times) != 4:
            missing = set('abcd') - set(cycle_ready_times.keys())
            received = ', '.join([f"{led.upper()}" for led in sorted(cycle_ready_times.keys())])
            missing_str = ', '.join([f"{led.upper()}" for led in sorted(missing)])
            
            print(f"⚠️  Cycle {cycle+1}: Only received {len(cycle_ready_times)}/4 READY signals")
            print(f"     Received: {received}")
            print(f"     Missing: {missing_str}")
            
            # Show raw response for first failed cycle
            if cycle == 0:
                raw_data = b''.join(all_responses)
                print(f"     Raw response: {raw_data[:200]}")  # First 200 bytes
            continue
        
        # Calculate cycle duration
        cycle_duration = (cycle_end - cmd_start) * 1000  # Convert to ms
        cycle_times.append(cycle_duration)
        
        # Calculate timing for each LED
        print(f"Cycle {cycle+1}:")
        for i, led in enumerate(['a', 'b', 'c', 'd']):
            if led not in cycle_ready_times:
                continue
            
            # Time from cycle start to READY signal
            ready_offset = (cycle_ready_times[led] - cmd_start) * 1000  # ms
            ready_times[led].append(ready_offset)
            
            # Expected timing
            expected_start = i * 250  # ms
            expected_ready = expected_start + 50  # LED on for 50ms before READY
            
            # Calculate LED duration (time between consecutive READYs)
            if i > 0:
                prev_led = ['a', 'b', 'c', 'd'][i-1]
                if prev_led in cycle_ready_times:
                    duration = (cycle_ready_times[led] - cycle_ready_times[prev_led]) * 1000
                    led_durations[prev_led].append(duration)
            
            # LED D duration is from D_READY to cycle end
            if i == 3:
                d_duration = (cycle_end - cycle_ready_times[led]) * 1000
                led_durations[led].append(d_duration)
            
            error = ready_offset - expected_ready
            status = "✅" if abs(error) < 10 else "⚠️" if abs(error) < 20 else "❌"
            
            print(f"  {status} LED {led.upper()}: READY @ {ready_offset:6.1f}ms (expected {expected_ready:3.0f}ms, error {error:+5.1f}ms)")
        
        print(f"  Total cycle: {cycle_duration:.1f}ms (expected 1000ms, error {cycle_duration-1000:+.1f}ms)\n")
        
        # Small delay between cycles
        time.sleep(0.1)
    
    # Statistical analysis
    print(f"\n{'='*70}")
    print("TIMING STATISTICS")
    print(f"{'='*70}\n")
    
    # Overall cycle timing
    print("Cycle Duration:")
    print(f"  Mean: {statistics.mean(cycle_times):.1f}ms")
    print(f"  StdDev: {statistics.stdev(cycle_times):.2f}ms")
    print(f"  Min: {min(cycle_times):.1f}ms")
    print(f"  Max: {max(cycle_times):.1f}ms")
    print(f"  Jitter: {max(cycle_times) - min(cycle_times):.2f}ms")
    
    # Per-LED READY timing
    print("\nREADY Signal Timing (from cycle start):")
    for led in ['a', 'b', 'c', 'd']:
        if led not in ready_times or not ready_times[led]:
            continue
        
        times = ready_times[led]
        mean_time = statistics.mean(times)
        stddev = statistics.stdev(times) if len(times) > 1 else 0
        
        expected_ready = (['a', 'b', 'c', 'd'].index(led) * 250) + 50
        mean_error = mean_time - expected_ready
        
        print(f"  LED {led.upper()}: {mean_time:6.1f}ms ± {stddev:4.2f}ms (expected {expected_ready:3.0f}ms, error {mean_error:+5.1f}ms)")
    
    # LED-to-LED intervals (should be 250ms)
    print("\nLED Duration (READY-to-READY intervals):")
    for led in ['a', 'b', 'c', 'd']:
        if led not in led_durations or not led_durations[led]:
            continue
        
        durations = led_durations[led]
        mean_dur = statistics.mean(durations)
        stddev = statistics.stdev(durations) if len(durations) > 1 else 0
        error = mean_dur - 250  # All intervals should be 250ms
        
        status = "✅" if abs(error) < 10 else "⚠️" if abs(error) < 20 else "❌"
        print(f"  {status} LED {led.upper()}: {mean_dur:6.1f}ms ± {stddev:4.2f}ms (expected 250ms, error {error:+5.1f}ms)")
    
    # USB overhead estimation
    print("\nUSB Communication Overhead:")
    first_ready_times = [ready_times['a'][i] for i in range(len(ready_times['a']))]
    mean_first_ready = statistics.mean(first_ready_times)
    print(f"  Mean time to first READY: {mean_first_ready:.1f}ms")
    print(f"  Expected (USB latency + 50ms LED): ~50-55ms")
    print(f"  Estimated USB latency: {mean_first_ready - 50:.1f}ms")
    
    # Pass/Fail assessment
    print(f"\n{'='*70}")
    print("ASSESSMENT")
    print(f"{'='*70}\n")
    
    cycle_error = abs(statistics.mean(cycle_times) - 1000)
    cycle_jitter = max(cycle_times) - min(cycle_times)
    
    print(f"Cycle timing accuracy: {cycle_error:.1f}ms error, {cycle_jitter:.1f}ms jitter")
    if cycle_error < 10 and cycle_jitter < 20:
        print("  ✅ PASS: Cycle timing within spec")
    elif cycle_error < 20 and cycle_jitter < 50:
        print("  ⚠️  WARNING: Cycle timing acceptable but high jitter")
    else:
        print("  ❌ FAIL: Cycle timing outside acceptable range")
    
    # LED interval check
    all_durations = []
    for led in ['a', 'b', 'c', 'd']:
        if led in led_durations:
            all_durations.extend(led_durations[led])
    
    if all_durations:
        mean_interval = statistics.mean(all_durations)
        interval_error = abs(mean_interval - 250)
        print(f"\nLED interval accuracy: {interval_error:.1f}ms error")
        if interval_error < 10:
            print("  ✅ PASS: LED intervals within spec")
        elif interval_error < 20:
            print("  ⚠️  WARNING: LED intervals acceptable but high error")
        else:
            print("  ❌ FAIL: LED intervals outside acceptable range")
    
    # USB latency check
    usb_latency = mean_first_ready - 50
    print(f"\nUSB latency: {usb_latency:.1f}ms")
    if usb_latency < 5:
        print("  ✅ PASS: USB latency minimal")
    elif usb_latency < 10:
        print("  ⚠️  WARNING: USB latency elevated")
    else:
        print("  ❌ FAIL: USB latency too high (>10ms)")
    
    ser.close()
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import sys
    
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    try:
        test_firmware_timing(port, cycles)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
