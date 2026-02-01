"""
Test script to verify batch acquisition timing fix
Expected: ~1000ms per 4-channel cycle (250ms per channel)
Before fix: ~5000ms per cycle (num_scans=8 causing delays)
After fix: ~1000ms per cycle (num_scans=1 in batch mode)
"""

import sys
import time
from pathlib import Path

# Add affilabs to path
sys.path.insert(0, str(Path(__file__).parent / "affilabs"))

import settings
from utils.hal.controller_hal import PicoP4PROAdapter
from utils.hal.detector_hal import OceanSpectrometerAdapter
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s'
)
logger = logging.getLogger(__name__)

def test_batch_timing():
    """Test batch acquisition timing with the fix"""

    print("=" * 80)
    print("BATCH TIMING TEST")
    print("=" * 80)
    print(f"LED_ON_TIME_MS: {settings.LED_ON_TIME_MS}ms")
    print(f"DETECTOR_WAIT_MS: {settings.DETECTOR_WAIT_MS}ms")
    print(f"Target: 4 channels × {settings.LED_ON_TIME_MS}ms = {4 * settings.LED_ON_TIME_MS}ms")
    print("=" * 80)

    # Connect to hardware
    print("\n[1/4] Connecting to spectrometer...")
    usb = OceanSpectrometerAdapter()
    if not usb.connect():
        print("❌ Failed to connect to spectrometer")
        return False
    print("✓ Spectrometer connected")

    print("\n[2/4] Connecting to controller...")
    ctrl = PicoP4PROAdapter()
    if not ctrl.connect():
        print("❌ Failed to connect to controller")
        return False
    print("✓ Controller connected")

    # Setup
    print("\n[3/4] Setting up batch mode...")
    channels = ['a', 'b', 'c', 'd']
    intensities = {ch: 200 for ch in channels}  # Medium brightness

    ctrl.set_batch_intensities(intensities)
    print(f"✓ Batch intensities set: {intensities}")

    # Set integration time
    integration_time_ms = 22.4
    usb.set_integration_time(integration_time_ms)
    print(f"✓ Integration time: {integration_time_ms}ms")

    # Test batch acquisition
    print("\n[4/4] Testing batch acquisition timing...")
    print("-" * 80)

    num_test_cycles = 5
    num_scans = 8  # Test with multiple scans sent 1-by-1
    cycle_times = []

    print(f"  Using {num_scans} scans per channel (sent individually)")

    for cycle in range(num_test_cycles):
        cycle_start = time.perf_counter()

        for ch in channels:
            # Turn on LED
            ctrl.turn_on_channel(ch)

            # Wait for LED stabilization
            time.sleep(settings.DETECTOR_WAIT_MS / 1000.0)

            # Read spectrum multiple times and average (1-by-1)
            import numpy as np
            spectrum_length = 2997 - 1140
            stack = np.zeros(spectrum_length, dtype=np.float64)

            for i in range(num_scans):
                scan = usb.read_roi(
                    wave_min_index=1140,
                    wave_max_index=2997,
                    num_scans=1  # ALWAYS 1 - send individually
                )
                if scan is not None:
                    stack += scan

            spectrum = (stack / num_scans).astype(np.uint32)

            # Turn off LED
            ctrl.turn_off_channel(ch)

        cycle_end = time.perf_counter()
        cycle_time_ms = (cycle_end - cycle_start) * 1000
        cycle_times.append(cycle_time_ms)

        status = "✓" if cycle_time_ms < 1500 else "⚠️"
        print(f"  Cycle {cycle + 1}: {cycle_time_ms:6.1f}ms {status}")

    # Results
    print("-" * 80)
    avg_time = sum(cycle_times) / len(cycle_times)
    target_time = 4 * settings.LED_ON_TIME_MS

    print("\nRESULTS:")
    print(f"  Average cycle time: {avg_time:.1f}ms")
    print(f"  Target cycle time:  {target_time:.1f}ms")
    print(f"  Difference:         {avg_time - target_time:+.1f}ms")

    if avg_time < 1500:
        print(f"\n✅ PASS - Batch timing is fast! ({avg_time:.0f}ms < 1500ms threshold)")
        success = True
    else:
        print(f"\n❌ FAIL - Batch timing still slow ({avg_time:.0f}ms)")
        success = False

    # Cleanup
    print("\n[Cleanup] Turning off LEDs...")
    ctrl.turn_off_all_leds()

    return success

if __name__ == "__main__":
    try:
        success = test_batch_timing()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
