"""
Detailed LED Command Timing Breakdown

Measures timing for each step:
1. turn_on_channel() - Enable LED
2. set_intensity batch command - Set PWM
3. Overall set_intensity() call
"""

import time
import sys
from pathlib import Path
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.logger import logger


def test_detailed_timing():
    print("="*80)
    print("DETAILED LED COMMAND TIMING BREAKDOWN")
    print("="*80)
    print()

    # Initialize hardware
    print("Initializing controller...")
    ctrl = PicoP4SPR()

    if not ctrl.open():
        print("ERROR: Controller not found")
        return

    print(f"OK: Controller connected")
    print()

    test_channel = 'a'
    led_intensity = 128

    print(f"Test Configuration:")
    print(f"  Channel: {test_channel.upper()}")
    print(f"  Intensity: {led_intensity}")
    print()

    # Test 1: turn_on_channel() timing
    print("TEST 1: turn_on_channel() timing")
    print("-" * 40)

    # Clear enabled channels first
    ctrl._channels_enabled.clear()

    t0 = time.perf_counter()
    ctrl.turn_on_channel(ch=test_channel)
    t1 = time.perf_counter()
    turn_on_time = (t1 - t0) * 1000

    print(f"  turn_on_channel(): {turn_on_time:.2f}ms")
    print()

    # Test 2: Batch intensity command (with channel already enabled)
    print("TEST 2: Batch command timing (channel already enabled)")
    print("-" * 40)

    t0 = time.perf_counter()
    batch_values = {test_channel: led_intensity}
    for ch in ['a', 'b', 'c', 'd']:
        if ch not in batch_values:
            batch_values[ch] = 0
    ctrl.set_batch_intensities(**batch_values)
    t1 = time.perf_counter()
    batch_time = (t1 - t0) * 1000

    print(f"  set_batch_intensities(): {batch_time:.2f}ms")
    print()

    # Test 3: Full set_intensity() call (includes turn_on_channel check)
    print("TEST 3: set_intensity() timing (full call)")
    print("-" * 40)

    # Clear enabled channels to force turn_on_channel
    ctrl._channels_enabled.clear()

    t0 = time.perf_counter()
    ctrl.set_intensity(ch=test_channel, raw_val=led_intensity)
    t1 = time.perf_counter()
    full_time = (t1 - t0) * 1000

    print(f"  set_intensity() FIRST call: {full_time:.2f}ms")
    print(f"    (includes turn_on_channel)")
    print()

    # Test 4: set_intensity() when channel already enabled
    print("TEST 4: set_intensity() timing (channel already enabled)")
    print("-" * 40)

    t0 = time.perf_counter()
    ctrl.set_intensity(ch=test_channel, raw_val=led_intensity)
    t1 = time.perf_counter()
    cached_time = (t1 - t0) * 1000

    print(f"  set_intensity() CACHED: {cached_time:.2f}ms")
    print(f"    (skips turn_on_channel)")
    print()

    # Test 5: Multiple consecutive calls
    print("TEST 5: 10 consecutive set_intensity() calls")
    print("-" * 40)

    ctrl._channels_enabled.clear()
    times = []

    for i in range(10):
        t0 = time.perf_counter()
        ctrl.set_intensity(ch=test_channel, raw_val=led_intensity)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    print(f"  Call #1 (cold): {times[0]:.2f}ms")
    print(f"  Call #2-10 (warm): avg={sum(times[1:])/9:.2f}ms, min={min(times[1:]):.2f}ms, max={max(times[1:]):.2f}ms")
    print()

    # Analysis
    print("="*80)
    print("ANALYSIS")
    print("="*80)
    print()

    print(f"Breakdown of set_intensity() FIRST call:")
    print(f"  turn_on_channel():        ~{turn_on_time:.1f}ms")
    print(f"  Batch command:            ~{batch_time:.1f}ms")
    print(f"  Other overhead:           ~{max(0, full_time - turn_on_time - batch_time):.1f}ms")
    print(f"  TOTAL:                    {full_time:.1f}ms")
    print()

    print(f"Performance comparison:")
    print(f"  First call (cold):        {full_time:.1f}ms")
    print(f"  Cached call (warm):       {cached_time:.1f}ms")
    print(f"  Speedup (warm):           {full_time/cached_time:.1f}x faster")
    print()

    if full_time > 100:
        print(f"WARNING: First call took {full_time:.1f}ms (expected <100ms)")
        print(f"  Possible causes:")
        print(f"    - Serial port buffering/latency")
        print(f"    - USB subsystem overhead")
        print(f"    - Firmware processing delay")
        print(f"    - Python thread scheduling")
    else:
        print(f"OK: First call timing is reasonable ({full_time:.1f}ms)")

    print()

    # Cleanup
    ctrl.turn_off_channels()

    print("Test complete")


if __name__ == '__main__':
    try:
        test_detailed_timing()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
