"""Asynchronous LED-Detector Acquisition Test

Tests detector-centric acquisition where:
1. LEDs cycle autonomously (firmware-controlled or timed)
2. Detector reads continuously at maximum rate
3. Post-processing correlates readings to LED states

This eliminates synchronization overhead and maximizes throughput.
"""

import io
import sys
import threading
import time
from pathlib import Path

import numpy as np

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def test_async_acquisition():
    """Test asynchronous LED-detector acquisition."""
    print("=" * 80)
    print("ASYNCHRONOUS LED-DETECTOR ACQUISITION TEST")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Initializing hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000()

    if not ctrl.open():
        print("ERROR: Controller not found")
        return

    if not usb.open():
        print("ERROR: Detector not found")
        return

    print("OK: Hardware connected")
    print()

    # Test parameters
    integration_time_ms = 70
    led_intensity = 200
    led_cycle_time_ms = 200  # Time per LED (ON + decay)
    num_cycles = 3  # Measure 3 complete 4-channel cycles

    usb.set_integration(integration_time_ms)

    print("Test Configuration:")
    print(f"  Integration time: {integration_time_ms}ms")
    print(f"  LED cycle time: {led_cycle_time_ms}ms per channel")
    print(f"  Number of cycles: {num_cycles}")
    print()

    # Strategy 1: Synchronized acquisition (baseline)
    print("=" * 80)
    print("STRATEGY 1: Synchronized Acquisition (baseline)")
    print("=" * 80)
    print()

    channels = ["a", "b", "c", "d"]

    ctrl.turn_off_channels()
    time.sleep(0.2)

    t0 = time.perf_counter()
    sync_data = []

    for cycle in range(num_cycles):
        for ch in channels:
            # Turn on LED
            ctrl.set_intensity(ch=ch, raw_val=led_intensity)

            # Wait for stabilization
            time.sleep(0.045)

            # Read spectrum
            spectrum = usb.read_intensity()

            # Turn off LED
            ctrl.turn_off_channels()

            # Wait for decay
            time.sleep(0.100)

            if spectrum is not None:
                sync_data.append(
                    {
                        "cycle": cycle,
                        "channel": ch,
                        "spectrum": spectrum,
                        "mean": np.mean(spectrum),
                    },
                )

    t1 = time.perf_counter()
    sync_time = (t1 - t0) * 1000

    print("Synchronized acquisition:")
    print(f"  Total time: {sync_time:.0f}ms")
    print(f"  Measurements: {len(sync_data)}")
    print(f"  Time per measurement: {sync_time/len(sync_data):.1f}ms")
    print()

    # Strategy 2: Asynchronous acquisition
    print("=" * 80)
    print("STRATEGY 2: Asynchronous Acquisition (detector-centric)")
    print("=" * 80)
    print()

    ctrl.turn_off_channels()
    time.sleep(0.2)

    # Data collection
    async_spectra = []
    async_timestamps = []
    led_events = []

    stop_flag = threading.Event()

    # Detector thread (reads continuously)
    def detector_thread():
        while not stop_flag.is_set():
            t = time.perf_counter()
            spectrum = usb.read_intensity()
            if spectrum is not None:
                async_spectra.append(spectrum)
                async_timestamps.append(t)

    # LED thread (cycles autonomously)
    def led_thread():
        for cycle in range(num_cycles):
            for ch in channels:
                t_on = time.perf_counter()

                # Turn on LED
                ctrl.set_intensity(ch=ch, raw_val=led_intensity)
                led_events.append(
                    {
                        "time": t_on,
                        "channel": ch,
                        "cycle": cycle,
                        "state": "ON",
                    },
                )

                # Keep LED on for cycle time
                time.sleep(led_cycle_time_ms / 1000.0)

                # Turn off LED
                ctrl.turn_off_channels()
                t_off = time.perf_counter()
                led_events.append(
                    {
                        "time": t_off,
                        "channel": ch,
                        "cycle": cycle,
                        "state": "OFF",
                    },
                )

        # Signal detector thread to stop
        time.sleep(0.1)
        stop_flag.set()

    print("Starting asynchronous acquisition...")
    print("  Detector: reading continuously")
    print("  LEDs: cycling autonomously")
    print()

    t0 = time.perf_counter()

    # Start threads
    det_thread = threading.Thread(target=detector_thread, daemon=True)
    led_thread_obj = threading.Thread(target=led_thread, daemon=True)

    det_thread.start()
    time.sleep(0.05)  # Small delay to start detector first
    led_thread_obj.start()

    # Wait for completion
    led_thread_obj.join()
    det_thread.join(timeout=1.0)

    t1 = time.perf_counter()
    async_time = (t1 - t0) * 1000

    print("Asynchronous acquisition:")
    print(f"  Total time: {async_time:.0f}ms")
    print(f"  Spectra captured: {len(async_spectra)}")
    print(f"  LED events: {len(led_events)}")
    print()

    # Post-processing: Correlate spectra to LED states
    print("Post-processing: Correlating spectra to LED states...")
    print()

    # Normalize timestamps (relative to start)
    t_start = min(async_timestamps[0], led_events[0]["time"])
    async_timestamps = [(t - t_start) * 1000 for t in async_timestamps]  # Convert to ms
    for event in led_events:
        event["time"] = (event["time"] - t_start) * 1000  # Convert to ms

    # Match spectra to LED ON periods
    async_data = []
    for i, (spectrum, t_spec) in enumerate(
        zip(async_spectra, async_timestamps, strict=False),
    ):
        # Find which LED was ON during this spectrum reading
        for j, event in enumerate(led_events):
            if event["state"] == "ON":
                # Find corresponding OFF event
                off_event = None
                for k in range(j + 1, len(led_events)):
                    if (
                        led_events[k]["channel"] == event["channel"]
                        and led_events[k]["state"] == "OFF"
                    ):
                        off_event = led_events[k]
                        break

                if off_event:
                    t_on = event["time"]
                    t_off = off_event["time"]

                    # Check if spectrum was captured during LED ON period
                    # Account for integration time
                    t_read_start = t_spec
                    t_read_end = t_spec + integration_time_ms

                    # Spectrum is valid if reading overlaps with LED ON period
                    if t_read_start >= t_on and t_read_end <= t_off:
                        async_data.append(
                            {
                                "cycle": event["cycle"],
                                "channel": event["channel"],
                                "spectrum": spectrum,
                                "mean": np.mean(spectrum),
                                "timestamp": t_spec,
                                "led_on": t_on,
                                "led_off": t_off,
                            },
                        )
                        break

    print(f"Correlated measurements: {len(async_data)}")
    print()

    # Analysis
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()

    print("                          | Synchronized | Asynchronous | Difference")
    print("--------------------------+--------------+--------------+------------")
    print(
        f"Total time                | {sync_time:8.0f}ms   | {async_time:8.0f}ms   | {sync_time - async_time:+7.0f}ms",
    )
    print(
        f"Valid measurements        | {len(sync_data):12d} | {len(async_data):12d} | {len(async_data) - len(sync_data):+10d}",
    )
    print(
        f"Time per measurement      | {sync_time/len(sync_data):8.1f}ms   | {async_time/len(async_data):8.1f}ms   | {sync_time/len(sync_data) - async_time/len(async_data):+7.1f}ms",
    )
    print()

    speedup = sync_time / async_time
    print(f"Speedup: {speedup:.2f}x")
    print()

    # Validate data quality
    if len(sync_data) == len(async_data):
        print("Data quality comparison:")
        for i in range(min(len(sync_data), len(async_data))):
            sync_mean = sync_data[i]["mean"]
            async_mean = async_data[i]["mean"]
            diff_percent = abs(sync_mean - async_mean) / sync_mean * 100
            ch = sync_data[i]["channel"]
            print(
                f"  Cycle {sync_data[i]['cycle']}, Ch {ch}: sync={sync_mean:.0f}, async={async_mean:.0f}, diff={diff_percent:.1f}%",
            )

    print()

    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    if speedup > 1.2:
        print(f"SUCCESS: Asynchronous acquisition is {speedup:.1f}x faster!")
        print()
        print("Advantages:")
        print("  - Eliminates synchronization overhead")
        print("  - Detector reads at maximum rate")
        print("  - No wasted time in delays")
        print()
        print("Implementation requirements:")
        print("  1. Firmware cycles LEDs autonomously (or use precise timing)")
        print("  2. Detector reads continuously in separate thread")
        print("  3. Post-process to correlate readings to LED states")
        print("  4. Timestamp precision: ~1ms required")
    else:
        print("RESULT: Minimal improvement over synchronized acquisition")
        print()
        print("Possible reasons:")
        print("  - Integration time dominates (detector bottleneck)")
        print("  - LED switching already optimized")
        print("  - Post-processing overhead offsets gains")

    print()

    # Cleanup
    ctrl.turn_off_channels()
    usb.close()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_async_acquisition()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback

        traceback.print_exc()
