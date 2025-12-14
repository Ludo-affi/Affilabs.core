"""
Command Batching Performance Test

Tests different command batching strategies:
1. Individual commands with wait-for-response
2. Pipelined commands (send multiple, then read responses)
3. Batch commands (if supported)
"""

import time
import sys
from pathlib import Path
import io
import numpy as np

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.logger import logger


def test_command_batching():
    """Test command batching strategies."""

    print("="*80)
    print("COMMAND BATCHING PERFORMANCE TEST")
    print("="*80)
    print()

    # Initialize hardware
    print("Initializing controller...")
    ctrl = PicoP4SPR()

    if not ctrl.open():
        print("ERROR: Controller not found")
        return

    print(f"OK: Controller connected (firmware: {ctrl.version})")
    print()

    # Check if rank sequence is available (V1.2+)
    has_rank = ctrl.version >= 'V1.2'
    print(f"Firmware capabilities:")
    print(f"  Version: {ctrl.version}")
    print(f"  Rank sequence (V1.2+): {'YES' if has_rank else 'NO'}")
    print()

    # Strategy 1: Individual commands (current method)
    print("="*80)
    print("STRATEGY 1: Individual Commands (wait for each response)")
    print("="*80)
    print()

    test_sequence = [
        ('a', 50),
        ('b', 100),
        ('c', 150),
        ('d', 200),
        ('a', 0),
        ('b', 0),
        ('c', 0),
        ('d', 0),
    ]

    times_individual = []
    for i in range(5):
        t0 = time.perf_counter()
        for ch, intensity in test_sequence:
            ctrl.set_intensity(ch=ch, raw_val=intensity)
        t1 = time.perf_counter()
        times_individual.append((t1 - t0) * 1000)

    avg_individual = np.mean(times_individual)
    std_individual = np.std(times_individual)

    print(f"8 commands (4 ON + 4 OFF):")
    print(f"  Average: {avg_individual:.1f}ms")
    print(f"  Std dev: {std_individual:.1f}ms")
    print(f"  Per command: {avg_individual/8:.1f}ms")
    print()

    # Strategy 2: Pipelined commands (send all, then read all)
    print("="*80)
    print("STRATEGY 2: Pipelined Commands (send bulk, read bulk)")
    print("="*80)
    print()

    times_pipelined = []
    for i in range(5):
        ctrl.turn_off_channels()
        time.sleep(0.05)

        t0 = time.perf_counter()

        # Send all commands without waiting
        with ctrl._lock:
            ctrl._ser.reset_input_buffer()
            for ch, intensity in test_sequence:
                if intensity == 0:
                    cmd = f"b{ch}000\n"
                else:
                    # Enable channel first
                    if ch not in ctrl._channels_enabled:
                        ctrl._ser.write(f"l{ch}\n".encode())
                        time.sleep(0.005)  # Small delay for enable
                        ctrl._channels_enabled.add(ch)
                    cmd = f"b{ch}{intensity:03d}\n"
                ctrl._ser.write(cmd.encode())

            # Now read all responses
            time.sleep(0.05)  # Wait for all commands to process
            responses = []
            for _ in range(len(test_sequence)):
                response = ctrl._ser.read(1)
                responses.append(response)

        t1 = time.perf_counter()
        times_pipelined.append((t1 - t0) * 1000)

        # Verify responses
        success_count = sum(1 for r in responses if r == b'1')
        print(f"  Run {i+1}: {(t1-t0)*1000:.1f}ms, {success_count}/{len(test_sequence)} successful")

    print()
    avg_pipelined = np.mean(times_pipelined)
    std_pipelined = np.std(times_pipelined)

    print(f"8 commands (pipelined):")
    print(f"  Average: {avg_pipelined:.1f}ms")
    print(f"  Std dev: {std_pipelined:.1f}ms")
    print(f"  Per command: {avg_pipelined/8:.1f}ms")
    print()

    # Strategy 3: Batch command (V1.1+)
    print("="*80)
    print("STRATEGY 3: Batch Commands (single command for all 4 LEDs)")
    print("="*80)
    print()

    # Simulate same sequence using batch commands
    batch_sequence = [
        {'a': 50, 'b': 100, 'c': 150, 'd': 200},  # All ON
        {'a': 0, 'b': 0, 'c': 0, 'd': 0},         # All OFF
    ]

    times_batch = []
    for i in range(5):
        t0 = time.perf_counter()
        for batch in batch_sequence:
            ctrl.set_batch_intensities(**batch)
        t1 = time.perf_counter()
        times_batch.append((t1 - t0) * 1000)

    avg_batch = np.mean(times_batch)
    std_batch = np.std(times_batch)

    print(f"2 batch commands (8 LED operations):")
    print(f"  Average: {avg_batch:.1f}ms")
    print(f"  Std dev: {std_batch:.1f}ms")
    print(f"  Per LED operation: {avg_batch/8:.1f}ms")
    print()

    # Analysis
    print("="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)
    print()

    print(f"Method                    | Total Time | Per Command | Speedup")
    print(f"--------------------------+------------+-------------+---------")
    print(f"Individual (baseline)     | {avg_individual:6.1f}ms   | {avg_individual/8:6.1f}ms    | 1.0x")
    print(f"Pipelined                 | {avg_pipelined:6.1f}ms   | {avg_pipelined/8:6.1f}ms    | {avg_individual/avg_pipelined:.1f}x")
    print(f"Batch (when applicable)   | {avg_batch:6.1f}ms   | {avg_batch/8:6.1f}ms    | {avg_individual/avg_batch:.1f}x")
    print()

    if avg_pipelined < avg_individual * 0.8:
        print("RESULT: Pipelined commands show significant improvement!")
        print(f"  Time saved: {avg_individual - avg_pipelined:.1f}ms ({(1 - avg_pipelined/avg_individual)*100:.0f}%)")
        print()
        print("RECOMMENDATION:")
        print("  Implement pipelined command execution for calibration")
        print("  Send all LED commands, then read all responses")
    else:
        print("RESULT: Pipelining does not improve performance significantly")
        print("  Likely bottleneck: Serial communication latency")

    print()

    # Strategy 4: Firmware sequence (if V1.2+)
    if has_rank:
        print("="*80)
        print("STRATEGY 4: Firmware-Side Sequence (V1.2+ only)")
        print("="*80)
        print()
        print("Firmware can autonomously execute LED sequences")
        print("Python only needs to read spectra when signaled")
        print()
        print("Expected performance: ~2.7x faster than Python control")
        print("Use led_rank_sequence() for optimal calibration speed")
    else:
        print("="*80)
        print("UPGRADE RECOMMENDATION")
        print("="*80)
        print()
        print("Firmware V1.2+ adds led_rank_sequence() command:")
        print("  - Firmware handles LED timing autonomously")
        print("  - Python only reads spectra on signal")
        print("  - 2.7x faster calibration")
        print()
        print("Current firmware: V1.1 (no rank sequence)")

    print()

    # Cleanup
    ctrl.turn_off_channels()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    try:
        test_command_batching()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
