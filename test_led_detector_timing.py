"""
LED-to-Detector Timing Synchronization Test

This script measures the timing relationship between:
1. LED activation command sent
2. LED physically turning on (settling time)
3. Detector integration start
4. Detector read completion

Purpose: Diagnose if detector is sampling BEFORE LED stabilizes or AFTER LED turns off.
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
from utils.usb4000_wrapper import USB4000
from utils.logger import logger
import numpy as np


def test_led_detector_timing():
    """Test LED activation to detector read timing synchronization."""

    print("="*80)
    print("LED-TO-DETECTOR TIMING SYNCHRONIZATION TEST")
    print("="*80)
    print()

    # Initialize hardware
    print("🔧 Initializing hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000()

    if not ctrl.open():
        print("❌ Controller not found")
        return

    if not usb.open():
        print("❌ Detector not found")
        return

    print(f"✅ Controller: {ctrl.get_info() if hasattr(ctrl, 'get_info') else 'P4SPR'}")
    print(f"✅ Detector: FLMT09116")
    print()

    # Test parameters
    test_channel = 'a'
    led_intensity = 128
    integration_time_ms = 70  # Same as calibration

    # Various PRE-LED delays to test
    test_delays_ms = [0, 10, 20, 30, 40, 50, 60, 80, 100, 150, 200]

    print(f"Test Configuration:")
    print(f"  Channel: {test_channel.upper()}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  Integration Time: {integration_time_ms}ms")
    print(f"  Testing PRE-LED delays: {test_delays_ms}")
    print()

    # Set integration time once
    usb.set_integration(integration_time_ms)
    print(f"✅ Integration time set to {integration_time_ms}ms")
    print()

    results = []

    for delay_ms in test_delays_ms:
        print(f"Testing PRE-LED delay = {delay_ms}ms...")

        # Turn off all LEDs
        ctrl.turn_off_channels()
        time.sleep(0.2)  # Wait for LEDs to fully turn off

        # Timing sequence:
        t0 = time.perf_counter()

        # 1. Send LED command
        ctrl.set_intensity(ch=test_channel, raw_val=led_intensity)
        t1 = time.perf_counter()
        led_command_time = (t1 - t0) * 1000

        # 2. Wait PRE-LED delay (LED settling time)
        time.sleep(delay_ms / 1000.0)
        t2 = time.perf_counter()

        # 3. Read spectrum (this triggers detector integration)
        spectrum = usb.read_intensity()
        t3 = time.perf_counter()

        read_time = (t3 - t2) * 1000
        total_time = (t3 - t0) * 1000

        # Turn off LED
        ctrl.turn_off_channels()

        if spectrum is not None:
            signal_mean = np.mean(spectrum)
            signal_max = np.max(spectrum)
            signal_min = np.min(spectrum)

            print(f"  ✅ Delay={delay_ms:3d}ms | Signal: mean={signal_mean:6.0f}, max={signal_max:6.0f}, min={signal_min:6.0f}")
            print(f"     Timing: LED_cmd={led_command_time:.1f}ms, detector_read={read_time:.1f}ms, total={total_time:.1f}ms")

            results.append({
                'delay_ms': delay_ms,
                'signal_mean': signal_mean,
                'signal_max': signal_max,
                'signal_min': signal_min,
                'led_command_time_ms': led_command_time,
                'detector_read_time_ms': read_time,
                'total_time_ms': total_time
            })
        else:
            print(f"  ❌ Delay={delay_ms}ms | Failed to read spectrum")

        print()

    # Analysis
    print("="*80)
    print("ANALYSIS")
    print("="*80)
    print()

    if len(results) == 0:
        print("❌ No successful measurements")
        return

    # Find optimal delay (highest signal)
    max_signal_result = max(results, key=lambda x: x['signal_mean'])

    print(f"Signal vs PRE-LED Delay:")
    print()
    print(f"  Delay (ms) | Mean Signal | Max Signal | Status")
    print(f"  -----------+-------------+------------+------------------")

    baseline_signal = results[0]['signal_mean']  # 0ms delay (no LED settling)

    for r in results:
        delay = r['delay_ms']
        mean_sig = r['signal_mean']
        max_sig = r['signal_max']

        # Calculate improvement over 0ms delay
        improvement = ((mean_sig - baseline_signal) / baseline_signal * 100) if baseline_signal > 0 else 0

        status = ""
        if delay == 0:
            status = "BASELINE (no settling)"
        elif delay == max_signal_result['delay_ms']:
            status = "✅ OPTIMAL"
        elif mean_sig > max_signal_result['signal_mean'] * 0.95:
            status = "✅ Good"
        elif mean_sig < baseline_signal * 1.1:
            status = "⚠️  Low signal"

        print(f"  {delay:4d}       | {mean_sig:11.0f} | {max_sig:10.0f} | {status} {improvement:+5.1f}%")

    print()
    print(f"Recommendations:")
    print(f"  • Optimal PRE-LED delay: {max_signal_result['delay_ms']}ms")
    print(f"  • Signal improvement: {((max_signal_result['signal_mean'] - baseline_signal) / baseline_signal * 100):+.1f}%")
    print()

    # Check if signal plateaus
    signals = [r['signal_mean'] for r in results]
    plateau_start = None
    for i in range(1, len(signals)):
        if signals[i] > max_signal_result['signal_mean'] * 0.98:
            plateau_start = results[i]['delay_ms']
            break

    if plateau_start:
        print(f"  • Signal plateaus at: {plateau_start}ms")
        print(f"    (LED fully stabilized, no further improvement)")
    else:
        print(f"  ⚠️  Signal may still be increasing - test longer delays")

    print()
    print("Timing Breakdown:")
    print(f"  • LED command execution: {max_signal_result['led_command_time_ms']:.1f}ms")
    print(f"  • Detector read time: {max_signal_result['detector_read_time_ms']:.1f}ms")
    print(f"    (Expected: ~{integration_time_ms}ms + USB transfer ~10-20ms)")
    print()

    # Cleanup
    ctrl.turn_off_channels()
    usb.close()

    print("✅ Test complete")


if __name__ == '__main__':
    try:
        test_led_detector_timing()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
