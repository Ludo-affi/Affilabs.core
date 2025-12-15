"""Test LED overlap timing strategy for 210ms integration time.
Target: 900-1100ms cycle time for 4 channels.

Timing configuration:
- PRE: 20ms (LED stabilization)
- Integration: 210ms (user requirement)
- POST: 50ms (afterglow decay)
- Overlap: 40ms (turn on next LED after 40ms of POST)

Expected per channel:
- Ch A: 20ms PRE + 210ms ACQ + 10ms remaining POST = 240ms
- Ch B-D: 0ms PRE (satisfied) + 210ms ACQ + 10ms POST = 220ms each
- Total: 240 + (220×3) = 900ms
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from settings import (
    LED_OVERLAP_MS,
    POST_LED_DELAY_MS,
    PRE_LED_DELAY_MS,
)
from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def test_timing_cycle():
    """Test acquisition timing with LED overlap strategy."""
    print("=" * 80)
    print("LED OVERLAP TIMING TEST - 210ms Integration")
    print("=" * 80)
    print("Configuration:")
    print(f"  PRE delay: {PRE_LED_DELAY_MS}ms")
    print(f"  POST delay: {POST_LED_DELAY_MS}ms")
    print(f"  LED overlap: {LED_OVERLAP_MS}ms")
    print("  Expected cycle time: 900-1100ms")
    print("=" * 80)
    print()

    # Initialize controller and detector
    print("Initializing controller...")
    ctrl = PicoP4SPR()

    try:
        ctrl.open()
        print("✅ Connected to controller")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False

    print("Initializing detector...")
    detector = USB4000(parent=None)
    try:
        detector.open()
        print("✅ Connected to detector")
    except Exception as e:
        print(f"❌ Failed to connect to detector: {e}")
        ctrl.close()
        return False

    print()

    # Note: Integration time must be set through calibration system
    # For this test, we'll just measure timing with whatever integration is currently set
    print("Note: Using current device integration time setting")
    print("      (Integration time is managed by calibration system)")
    print()

    # Run timing test
    channels = ["a", "b", "c", "d"]
    num_cycles = 5

    print(f"Running {num_cycles} acquisition cycles...")
    print("=" * 80)
    print()

    cycle_times = []

    for cycle in range(num_cycles):
        print(f"Cycle {cycle + 1}/{num_cycles}")
        print("-" * 80)

        cycle_start = time.perf_counter()

        # Acquire all channels with overlap
        success = True
        for idx, ch in enumerate(channels):
            ch_start = time.perf_counter()

            try:
                # Turn ON current LED
                led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
                led_values[ch] = 255
                ctrl.set_batch_intensities(**led_values)

                # PRE delay (or check overlap)
                if idx > 0:
                    # LED should already be ON from previous overlap
                    # In real implementation, we'd skip or reduce PRE
                    pass
                else:
                    time.sleep(PRE_LED_DELAY_MS / 1000.0)

                # Acquire spectrum
                spectrum = detector.read_intensity()
                if spectrum is None or len(spectrum) == 0:
                    print(f"❌ Ch {ch}: No spectrum data")
                    success = False
                    break

                # Turn OFF current LED
                ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

                # POST delay with overlap
                if idx < len(channels) - 1:
                    # Wait overlap period
                    time.sleep(LED_OVERLAP_MS / 1000.0)

                    # Turn ON next LED during POST
                    next_ch = channels[idx + 1]
                    next_led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
                    next_led_values[next_ch] = 255
                    ctrl.set_batch_intensities(**next_led_values)

                    # Wait remaining POST
                    remaining_post = POST_LED_DELAY_MS - LED_OVERLAP_MS
                    time.sleep(remaining_post / 1000.0)
                else:
                    # Last channel, full POST
                    time.sleep(POST_LED_DELAY_MS / 1000.0)

                ch_time = (time.perf_counter() - ch_start) * 1000.0
                print(f"  Ch {ch}: {ch_time:.1f}ms (spectrum: {len(spectrum)} pixels)")

            except Exception as e:
                print(f"❌ Ch {ch}: {e}")
                success = False
                break

        cycle_end = time.perf_counter()
        cycle_time_ms = (cycle_end - cycle_start) * 1000.0

        if success:
            cycle_times.append(cycle_time_ms)
            print()
            print(f"✅ Cycle {cycle + 1} complete: {cycle_time_ms:.1f}ms")

            if cycle_time_ms < 900:
                print("   ⚠️ Faster than expected (target: 900-1100ms)")
            elif cycle_time_ms > 1100:
                print("   ⚠️ Slower than expected (target: 900-1100ms)")
            else:
                print("   ✅ Within target range")
        else:
            print(f"❌ Cycle {cycle + 1} failed")

        print()
        time.sleep(0.5)  # Small delay between cycles

    # Statistics
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)

    if cycle_times:
        avg_time = sum(cycle_times) / len(cycle_times)
        min_time = min(cycle_times)
        max_time = max(cycle_times)

        print(f"Successful cycles: {len(cycle_times)}/{num_cycles}")
        print(f"Average cycle time: {avg_time:.1f}ms")
        print(f"Min cycle time: {min_time:.1f}ms")
        print(f"Max cycle time: {max_time:.1f}ms")
        print(f"Jitter (max-min): {max_time - min_time:.1f}ms")
        print()

        if 900 <= avg_time <= 1100:
            print("✅ PASS: Average cycle time within target (900-1100ms)")
        else:
            print("❌ FAIL: Average cycle time outside target")
            print("   Expected: 900-1100ms")
            print(f"   Actual: {avg_time:.1f}ms")

        print()
        print("Individual cycle times:")
        for i, t in enumerate(cycle_times, 1):
            status = "✅" if 900 <= t <= 1100 else "⚠️"
            print(f"  {status} Cycle {i}: {t:.1f}ms")
    else:
        print("❌ No successful cycles")

    print()

    # Cleanup
    detector.close()
    ctrl.close()
    print("Hardware disconnected")

    return len(cycle_times) > 0 and (900 <= avg_time <= 1100 if cycle_times else False)


if __name__ == "__main__":
    try:
        success = test_timing_cycle()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
