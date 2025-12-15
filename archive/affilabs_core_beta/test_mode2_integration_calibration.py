"""Test Mode 2 (Alternative) Integration Time Calibration Method

This script tests the per-channel integration time calibration used in the
Alternative optical method (Global LED Intensity at 255).

Tests:
1. Hardware connection and initialization
2. Per-channel integration time optimization (LED=255)
3. Signal level verification at each integration time
4. Timing budget analysis (must stay under 100ms per channel)
5. Comparison of channel optical performance

Usage:
    python test_mode2_integration_calibration.py
"""

import sys
import time
from pathlib import Path

# Add current directory to path (for imports to work)
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from settings import (
    CH_LIST,
    LED_DELAY,
    MAX_INTEGRATION,
    MIN_INTEGRATION,
)
from utils.controller import ArduinoController, PicoP4SPR
from utils.logger import logger
from utils.usb4000_wrapper import USB4000


def find_controller():
    """Try to find and connect to available controller."""
    logger.info("Searching for controllers...")

    # Try Pico P4SPR first (most common)
    try:
        logger.debug("Trying PicoP4SPR...")
        ctrl = PicoP4SPR()
        if ctrl.open():
            logger.info("✅ Found PicoP4SPR controller")
            return ctrl
        ctrl.close()
    except Exception as e:
        logger.debug(f"PicoP4SPR not found: {e}")

    # Try Arduino
    try:
        logger.debug("Trying ArduinoController...")
        ctrl = ArduinoController()
        if ctrl.open():
            logger.info("✅ Found Arduino controller")
            return ctrl
        ctrl.close()
    except Exception as e:
        logger.debug(f"ArduinoController not found: {e}")

    return None


def find_spectrometer():
    """Try to find and connect to spectrometer."""
    logger.info("Searching for spectrometer...")

    # Create minimal mock app
    class MockApp:
        def __init__(self):
            pass

    try:
        # Try direct USB4000
        logger.debug("Trying USB4000...")
        usb = USB4000(MockApp())
        if usb.open():
            # USB4000 doesn't have .model attribute, use class name
            model_name = type(usb).__name__
            logger.info(
                f"✅ Found {model_name} spectrometer (S/N: {usb.serial_number})",
            )
            return usb
    except Exception as e:
        logger.debug(f"USB4000 not found: {e}")

    return None


def test_hardware_connection():
    """Test Step 1: Verify hardware is connected and responding."""
    logger.info("=" * 80)
    logger.info("TEST 1: Hardware Connection")
    logger.info("=" * 80)

    try:
        # Connect controller
        logger.info("📡 Connecting to controller...")
        ctrl = find_controller()
        if ctrl is None:
            logger.error("❌ Controller not found")
            return None, None
        logger.info(f"✅ Controller connected: {type(ctrl).__name__}")

        # Connect spectrometer
        logger.info("📡 Connecting to spectrometer...")
        usb = find_spectrometer()
        if usb is None:
            logger.error("❌ Spectrometer not found")
            ctrl.close()
            return None, None
        model_name = type(usb).__name__
        logger.info(f"✅ Spectrometer connected: {model_name}")
        logger.info(f"   Serial: {usb.serial_number}")
        logger.info(f"   Target counts: {usb.target_counts}")

        return ctrl, usb

    except Exception as e:
        logger.error(f"❌ Hardware connection failed: {e}")
        return None, None


def calibrate_integration_per_channel_test(
    usb,
    ctrl,
    ch,
    led_intensity=255,
    target_counts=None,
):
    """Test implementation of per-channel integration time calibration.

    This is the core function used in Mode 2 (Alternative Method).

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch: Channel to calibrate ('a', 'b', 'c', 'd')
        led_intensity: Fixed LED intensity (255 for Mode 2)
        target_counts: Target signal level (default: usb.target_counts)

    Returns:
        dict with results: {
            'integration_time': optimal integration time (ms),
            'final_signal': achieved signal level,
            'iterations': number of steps taken,
            'target_met': True if target was reached,
            'timing_budget_ok': True if under 100ms
        }

    """
    if target_counts is None:
        target_counts = usb.target_counts

    logger.info(f"\n{'='*60}")
    logger.info(f"Testing Channel {ch.upper()} at LED={led_intensity}")
    logger.info(f"{'='*60}")
    logger.info(f"Target: {target_counts:.0f} counts")

    # Ensure all LEDs off first
    ctrl.turn_off_channels()
    time.sleep(0.1)

    # Set LED intensity
    logger.info(f"Setting LED intensity: {led_intensity}")
    ctrl.set_intensity(ch=ch, raw_val=led_intensity)
    time.sleep(LED_DELAY)

    # Start with minimum integration time
    integration = MIN_INTEGRATION
    max_integration_allowed = min(MAX_INTEGRATION, 100)  # 100ms budget for Mode 2

    logger.info(f"Starting integration time: {integration}ms")
    logger.info(f"Maximum allowed: {max_integration_allowed}ms (timing budget)")

    usb.set_integration(integration)
    time.sleep(0.1)

    # Read initial signal
    int_array = usb.read_intensity()
    if int_array is None:
        logger.error(f"❌ Failed to read intensity for channel {ch.upper()}")
        return None

    current_count = int_array.max()
    logger.info(f"Initial signal: {current_count:.0f} counts @ {integration}ms")

    # Track iterations
    iterations = 0
    step_size = 2  # ms increments

    # Increase integration time until target reached
    logger.info(f"\nOptimizing integration time (step size: {step_size}ms)...")
    while current_count < target_counts and integration < max_integration_allowed:
        iterations += 1
        integration += step_size
        usb.set_integration(integration)
        time.sleep(0.02)

        int_array = usb.read_intensity()
        if int_array is None:
            logger.error("❌ Read failed during optimization")
            return None

        new_count = int_array.max()
        delta = new_count - current_count

        # Log every 5th iteration to reduce spam
        if iterations % 5 == 0 or new_count >= target_counts:
            logger.info(
                f"  Step {iterations}: {integration}ms → {new_count:.0f} counts (Δ{delta:+.0f})",
            )

        current_count = new_count

    # Analyze results
    target_met = current_count >= target_counts
    timing_budget_ok = integration < max_integration_allowed

    logger.info(f"\n{'─'*60}")
    logger.info(f"RESULTS for Channel {ch.upper()}:")
    logger.info(f"{'─'*60}")
    logger.info(f"✓ Optimal integration time: {integration}ms")
    logger.info(f"✓ Final signal: {current_count:.0f} counts")
    logger.info(f"✓ Iterations: {iterations}")
    logger.info(f"✓ Target met: {'YES ✅' if target_met else 'NO ❌'}")
    logger.info(
        f"✓ Timing budget (< 100ms): {'OK ✅' if timing_budget_ok else 'EXCEEDED ⚠️'}",
    )

    if not target_met:
        shortage = target_counts - current_count
        logger.warning(f"⚠️ Signal {shortage:.0f} counts below target")
        logger.warning(
            f"   This indicates weak optical coupling for channel {ch.upper()}",
        )

    if not timing_budget_ok:
        overage = integration - max_integration_allowed
        logger.warning(f"⚠️ Integration time exceeds budget by {overage}ms")
        logger.warning("   This will reduce acquisition frequency")

    # Calculate headroom
    headroom_ms = max_integration_allowed - integration
    headroom_pct = (headroom_ms / max_integration_allowed) * 100

    if headroom_pct > 50:
        strength = "EXCELLENT"
    elif headroom_pct > 25:
        strength = "GOOD"
    elif headroom_pct > 10:
        strength = "MODERATE"
    else:
        strength = "LIMITED"

    logger.info(
        f"✓ Integration headroom: {headroom_ms}ms ({headroom_pct:.1f}%) - {strength}",
    )

    # Turn off LED
    ctrl.set_intensity(ch=ch, raw_val=0)
    ctrl.turn_off_channels()

    return {
        "channel": ch,
        "integration_time": integration,
        "final_signal": current_count,
        "iterations": iterations,
        "target_met": target_met,
        "timing_budget_ok": timing_budget_ok,
        "headroom_ms": headroom_ms,
        "headroom_pct": headroom_pct,
        "strength": strength,
    }


def test_all_channels(usb, ctrl):
    """Test Step 2: Calibrate integration time for all channels."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Per-Channel Integration Time Calibration")
    logger.info("=" * 80)
    logger.info("Mode 2 (Alternative): LED fixed at 255, integration time varies\n")

    # Set S-mode
    logger.info("Setting polarization mode: S")
    ctrl.set_mode("s")
    time.sleep(0.5)

    results = {}

    for ch in CH_LIST:
        result = calibrate_integration_per_channel_test(
            usb=usb,
            ctrl=ctrl,
            ch=ch,
            led_intensity=255,
            target_counts=usb.target_counts,
        )

        if result:
            results[ch] = result
        else:
            logger.error(f"❌ Failed to calibrate channel {ch.upper()}")

        time.sleep(0.2)  # Brief pause between channels

    return results


def analyze_results(results):
    """Test Step 3: Analyze cross-channel performance."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Cross-Channel Analysis")
    logger.info("=" * 80)

    if not results:
        logger.error("❌ No results to analyze")
        return

    # Calculate statistics
    integration_times = [r["integration_time"] for r in results.values()]
    signals = [r["final_signal"] for r in results.values()]

    min_int = min(integration_times)
    max_int = max(integration_times)
    avg_int = sum(integration_times) / len(integration_times)

    logger.info("\nIntegration Time Statistics:")
    logger.info(f"  Min: {min_int}ms (strongest channel)")
    logger.info(f"  Max: {max_int}ms (weakest channel)")
    logger.info(f"  Avg: {avg_int:.1f}ms")
    logger.info(f"  Range: {max_int - min_int}ms")

    # Global integration time (max across channels)
    global_int = max_int
    logger.info(f"\n✓ Global Integration Time: {global_int}ms")
    logger.info("  (This is the max time needed across all channels)")

    # Channel-by-channel summary
    logger.info("\nPer-Channel Summary:")
    logger.info(
        f"{'Channel':<10} {'Int Time':<12} {'Signal':<12} {'Headroom':<15} {'Status'}",
    )
    logger.info(f"{'-'*70}")

    for ch, result in results.items():
        status = "✅" if result["target_met"] and result["timing_budget_ok"] else "⚠️"
        logger.info(
            f"{ch.upper():<10} {result['integration_time']:<12}ms "
            f"{result['final_signal']:<12.0f} "
            f"{result['headroom_pct']:<15.1f}% "
            f"{status} {result['strength']}",
        )

    # Timing analysis
    logger.info("\nTiming Budget Analysis:")
    overhead_ms = 50  # Estimated hardware overhead
    channel_time = global_int + overhead_ms
    channel_hz = 1000 / channel_time if channel_time > 0 else 0
    system_hz = channel_hz / len(results)

    logger.info(f"  Per-channel time: {channel_time}ms ({channel_hz:.2f}Hz)")
    logger.info(f"  System rate (4-ch): ~{system_hz:.2f}Hz")
    logger.info(
        f"  Timing budget status: {'OK ✅' if global_int < 100 else 'EXCEEDED ⚠️'}",
    )

    # Check for weak channels
    weak_channels = [
        ch
        for ch, r in results.items()
        if not r["target_met"] or r["integration_time"] > 90
    ]

    if weak_channels:
        logger.warning(
            f"\n⚠️ Weak Channels Detected: {', '.join([c.upper() for c in weak_channels])}",
        )
        logger.warning(
            "   → Check optical coupling (fiber alignment, sensor placement)",
        )
        logger.warning("   → Consider cleaning optical surfaces")
    else:
        logger.info("\n✅ All channels have good optical performance")
        logger.info("   → System is well-aligned and ready for measurements")

    # Check uniformity
    if max_int - min_int > 30:
        logger.warning(
            f"\n⚠️ Large variation in integration times ({max_int - min_int}ms)",
        )
        logger.warning(
            "   → This suggests non-uniform LED brightness or optical coupling",
        )
        logger.warning(
            f"   → Channels {[ch.upper() for ch, r in results.items() if r['integration_time'] == max_int]} need attention",
        )
    else:
        logger.info("\n✅ Good uniformity across channels")
        logger.info(
            f"   → Integration time variation: {max_int - min_int}ms (acceptable)",
        )


def test_led_delay_impact(usb, ctrl):
    """Test Step 4: Measure LED settling time impact."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: LED Delay Impact Analysis")
    logger.info("=" * 80)

    ch = "a"  # Test with channel A
    logger.info(f"Testing LED settling behavior on channel {ch.upper()}")

    # Ensure LED off
    ctrl.turn_off_channels()
    time.sleep(0.2)

    # Set integration time
    usb.set_integration(40)
    time.sleep(0.1)

    # Test different delay times
    delays = [0.001, 0.005, 0.01, 0.02, LED_DELAY]

    logger.info("\nTesting signal stability with varying delays:")
    logger.info(f"{'Delay (s)':<12} {'Signal (counts)':<20} {'Stability'}")
    logger.info(f"{'-'*50}")

    for delay in delays:
        # Turn on LED
        ctrl.set_intensity(ch=ch, raw_val=255)
        time.sleep(delay)

        # Take 3 readings
        readings = []
        for _ in range(3):
            int_array = usb.read_intensity()
            if int_array is not None:
                readings.append(int_array.max())
            time.sleep(0.05)

        # Turn off LED
        ctrl.set_intensity(ch=ch, raw_val=0)
        ctrl.turn_off_channels()
        time.sleep(0.2)

        if readings:
            avg_signal = sum(readings) / len(readings)
            std_signal = (
                sum((x - avg_signal) ** 2 for x in readings) / len(readings)
            ) ** 0.5
            stability = "STABLE ✅" if std_signal < 100 else "UNSTABLE ⚠️"

            logger.info(
                f"{delay:<12.3f} {avg_signal:<20.0f} {stability} (σ={std_signal:.1f})",
            )
        else:
            logger.error(f"{delay:<12.3f} READ FAILED")

    logger.info(f"\n✓ Current LED_DELAY setting: {LED_DELAY}s")
    logger.info(
        f"  This is {'SUFFICIENT ✅' if LED_DELAY >= 0.02 else 'TOO SHORT ⚠️'} for Mode 2",
    )


def test_afterglow_measurement(usb, ctrl):
    """Test Step 5: Measure LED afterglow decay and impact on stability for all channels."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: LED Afterglow Decay Measurement (All Channels)")
    logger.info("=" * 80)

    logger.info("Measuring LED afterglow decay for all 4 channels")
    logger.info(
        "This tests whether afterglow significantly affects measurement stability",
    )

    # Ensure LED off and wait for complete decay
    ctrl.turn_off_channels()
    time.sleep(0.5)  # Long wait to ensure all afterglow gone

    # Set integration time
    integration_ms = 40
    usb.set_integration(integration_ms)
    time.sleep(0.1)

    # STEP 0: Measure dark reference (detector baseline with LED off)
    logger.info("\n📊 STEP 0: Dark Reference Measurement")
    logger.info("Measuring detector dark current + stray light baseline")

    ctrl.turn_off_channels()
    time.sleep(0.5)  # Ensure complete darkness

    dark_readings = []
    for _ in range(5):
        int_array = usb.read_intensity()
        if int_array is not None:
            dark_readings.append(int_array.max())
        time.sleep(0.1)

    dark_signal = sum(dark_readings) / len(dark_readings) if dark_readings else 0
    dark_std = (
        (sum((x - dark_signal) ** 2 for x in dark_readings) / len(dark_readings)) ** 0.5
        if len(dark_readings) > 1
        else 0
    )
    logger.info(f"Dark signal: {dark_signal:.0f} ± {dark_std:.1f} counts")
    logger.info("This will be subtracted to isolate true afterglow")

    # Test all 4 channels
    channels = ["a", "b", "c", "d"]
    all_afterglow_data = {}
    delays_ms = [1, 5, 10, 20, 50, 100, 150, 200, 250]

    for ch in channels:
        logger.info(f"\n{'='*80}")
        logger.info(
            f"PART 1: Channel {ch.upper()} - LED Turn-off Afterglow Decay Profile",
        )
        logger.info(f"{'='*80}")
        logger.info(
            f"{'Delay (ms)':<12} {'Raw (counts)':<15} {'Dark-Sub':<15} {'% of Peak':<15} {'Status'}",
        )
        logger.info(f"{'-'*75}")
        logger.info(
            f"NOTE: Measurements taken DURING integration window ({integration_ms}ms)",
        )
        logger.info(
            f"      Effective delay = delay + {integration_ms/2:.0f}ms (integration midpoint)",
        )
        logger.info(f"{'-'*75}")

        # First get peak signal (LED fully on)
        ctrl.set_intensity(ch=ch, raw_val=255)
        time.sleep(0.25)  # Let LED stabilize
        int_array = usb.read_intensity()
        raw_peak = int_array.max() if int_array is not None else 0
        peak_signal = raw_peak - dark_signal  # Dark-subtracted peak
        logger.info(
            f"Peak signal (LED on): {raw_peak:.0f} counts (dark-subtracted: {peak_signal:.0f} counts)",
        )

        # Now measure afterglow at different delays
        afterglow_data = []

        for delay_ms in delays_ms:
            # Turn LED on briefly to charge phosphor
            ctrl.set_intensity(ch=ch, raw_val=255)
            time.sleep(0.25)  # Charge phosphor fully

            # Turn LED off (instant command, no delay)
            ctrl.set_intensity(ch=ch, raw_val=0)
            ctrl.turn_off_channels()

            # Wait ONLY the specified delay (no LED_DELAY here - we want raw timing)
            time.sleep(delay_ms / 1000.0)

            # Measure residual signal
            int_array = usb.read_intensity()
            if int_array is not None:
                raw_signal = int_array.max()
                signal = raw_signal - dark_signal  # Subtract dark to get true afterglow
                pct_of_peak = (signal / peak_signal * 100) if peak_signal > 0 else 0
                afterglow_data.append((delay_ms, signal, pct_of_peak))

                # Determine status
                if pct_of_peak > 10:
                    status = "HIGH ⚠️"
                elif pct_of_peak > 1:
                    status = "MODERATE 📊"
                else:
                    status = "LOW ✅"

                logger.info(
                    f"{delay_ms:<12} {raw_signal:<15.0f} {signal:<15.0f} {pct_of_peak:<15.2f} {status}",
                )

            # Wait for complete decay before next measurement
            time.sleep(0.3)

        all_afterglow_data[ch] = {
            "peak": peak_signal,
            "data": afterglow_data,
        }

    # Summary comparison across channels
    logger.info(f"\n{'='*80}")
    logger.info("AFTERGLOW SUMMARY - All Channels @ 50ms Delay")
    logger.info(f"{'='*80}")
    logger.info(
        f"{'Channel':<12} {'Peak (counts)':<18} {'Afterglow @ 50ms':<20} {'% of Peak':<15} {'Status'}",
    )
    logger.info(f"{'-'*75}")

    for ch in channels:
        peak = all_afterglow_data[ch]["peak"]
        data = all_afterglow_data[ch]["data"]
        # Find 50ms measurement
        afterglow_50ms = next((d[1] for d in data if d[0] == 50), 0)
        pct_50ms = (afterglow_50ms / peak * 100) if peak > 0 else 0

        if pct_50ms > 1:
            status = "MODERATE 📊"
        else:
            status = "LOW ✅"

        logger.info(
            f"{ch.upper():<12} {peak:<18.0f} {afterglow_50ms:<20.0f} {pct_50ms:<15.2f} {status}",
        )

        logger.info(
            f"{ch.upper():<12} {peak:<18.0f} {afterglow_50ms:<20.0f} {pct_50ms:<15.2f} {status}",
        )

    # PART 2: Test stability on channel A (representative test)
    ch = "a"
    logger.info(f"\n{'='*80}")
    logger.info("PART 2: Stability Test - Fast Acquisition (25ms delay)")
    logger.info(f"{'='*80}")
    logger.info("Testing 25ms delay (2x faster) with and without afterglow correction")
    logger.info("Extended time series: 30 measurements each")

    # Test A: 25ms delay WITHOUT afterglow correction
    logger.info("\nTest A: 25ms delay WITHOUT afterglow correction (30 points)")
    logger.info("  LED on 200ms → 25ms wait after off → Acquire (raw signal)")

    ctrl.turn_off_channels()
    time.sleep(0.5)  # Start fresh

    fast_no_correction = []
    for i in range(30):  # 30 samples for time series
        # Turn LED on for 200ms (matches operation)
        ctrl.set_intensity(ch=ch, raw_val=255)
        time.sleep(0.2)  # 200ms LED on time

        # Turn LED off
        ctrl.set_intensity(ch=ch, raw_val=0)
        ctrl.turn_off_channels()
        time.sleep(0.025)  # 25ms delay after turn-off

        # Acquire signal (afterglow present)
        int_array = usb.read_intensity()
        if int_array is not None:
            fast_no_correction.append(int_array.max())

    if fast_no_correction:
        avg_fast_raw = sum(fast_no_correction) / len(fast_no_correction)
        std_fast_raw = (
            sum((x - avg_fast_raw) ** 2 for x in fast_no_correction)
            / len(fast_no_correction)
        ) ** 0.5
        cv_fast_raw = (std_fast_raw / avg_fast_raw * 100) if avg_fast_raw > 0 else 0
        min_raw = min(fast_no_correction)
        max_raw = max(fast_no_correction)
        range_raw = max_raw - min_raw
        logger.info(f"  Data points: {len(fast_no_correction)}")
        logger.info(f"  First 10: {[f'{r:.0f}' for r in fast_no_correction[:10]]}")
        logger.info(f"  Last 10:  {[f'{r:.0f}' for r in fast_no_correction[-10:]]}")
        logger.info(
            f"  Mean: {avg_fast_raw:.0f}, Std: {std_fast_raw:.1f}, CV: {cv_fast_raw:.2f}%",
        )
        logger.info(
            f"  Range: {min_raw:.0f} - {max_raw:.0f} (Δ={range_raw:.0f} counts)",
        )
        logger.info(f"  Stability: {'POOR ⚠️' if cv_fast_raw > 1.0 else 'GOOD ✅'}")

    # Test B: 25ms delay WITH afterglow correction (subtract measured afterglow)
    logger.info("\nTest B: 25ms delay WITH afterglow correction (30 points)")
    logger.info(
        "  LED on 200ms → 25ms wait after off → Acquire → Subtract afterglow (~0.6% correction)",
    )

    # Get afterglow value for 25ms delay (from earlier measurements)
    # Use the 20ms measurement as proxy (closest to 25ms effective delay)
    afterglow_25ms = next(
        (s for t, s, _ in all_afterglow_data["a"]["data"] if t == 20),
        260,
    )
    logger.info(f"  Using afterglow correction: {afterglow_25ms:.0f} counts")

    ctrl.turn_off_channels()
    time.sleep(0.5)  # Start fresh

    fast_with_correction = []
    for i in range(30):
        # Turn LED on for 200ms (matches operation)
        ctrl.set_intensity(ch=ch, raw_val=255)
        time.sleep(0.2)  # 200ms LED on time

        # Turn LED off
        ctrl.set_intensity(ch=ch, raw_val=0)
        ctrl.turn_off_channels()
        time.sleep(0.025)  # 25ms delay after turn-off

        # Acquire signal and apply correction
        int_array = usb.read_intensity()
        if int_array is not None:
            corrected_signal = int_array.max() - dark_signal - afterglow_25ms
            fast_with_correction.append(corrected_signal)

    if fast_with_correction:
        avg_fast_corr = sum(fast_with_correction) / len(fast_with_correction)
        std_fast_corr = (
            sum((x - avg_fast_corr) ** 2 for x in fast_with_correction)
            / len(fast_with_correction)
        ) ** 0.5
        cv_fast_corr = (std_fast_corr / avg_fast_corr * 100) if avg_fast_corr > 0 else 0
        min_corr = min(fast_with_correction)
        max_corr = max(fast_with_correction)
        range_corr = max_corr - min_corr
        logger.info(f"  Data points: {len(fast_with_correction)}")
        logger.info(f"  First 10: {[f'{r:.0f}' for r in fast_with_correction[:10]]}")
        logger.info(f"  Last 10:  {[f'{r:.0f}' for r in fast_with_correction[-10:]]}")
        logger.info(
            f"  Mean: {avg_fast_corr:.0f}, Std: {std_fast_corr:.1f}, CV: {cv_fast_corr:.2f}%",
        )
        logger.info(
            f"  Range: {min_corr:.0f} - {max_corr:.0f} (Δ={range_corr:.0f} counts)",
        )
        logger.info(f"  Stability: {'POOR ⚠️' if cv_fast_corr > 1.0 else 'GOOD ✅'}")

    # Test C: Original 50ms baseline for comparison
    logger.info("\nTest C: 50ms delay - baseline (30 points)")
    logger.info("  LED on 200ms → 50ms wait after off → Acquire")

    ctrl.turn_off_channels()
    time.sleep(0.5)  # Start fresh

    baseline_50ms = []
    for i in range(30):
        # Turn LED on for 200ms (matches operation)
        ctrl.set_intensity(ch=ch, raw_val=255)
        time.sleep(0.2)  # 200ms LED on time

        # Turn LED off
        ctrl.set_intensity(ch=ch, raw_val=0)
        ctrl.turn_off_channels()
        time.sleep(0.05)  # 50ms delay after turn-off

        # Acquire signal (afterglow present)
        int_array = usb.read_intensity()
        if int_array is not None:
            baseline_50ms.append(int_array.max())

    if baseline_50ms:
        avg_baseline = sum(baseline_50ms) / len(baseline_50ms)
        std_baseline = (
            sum((x - avg_baseline) ** 2 for x in baseline_50ms) / len(baseline_50ms)
        ) ** 0.5
        cv_baseline = (std_baseline / avg_baseline * 100) if avg_baseline > 0 else 0
        min_baseline = min(baseline_50ms)
        max_baseline = max(baseline_50ms)
        range_baseline = max_baseline - min_baseline
        logger.info(f"  Data points: {len(baseline_50ms)}")
        logger.info(f"  First 10: {[f'{r:.0f}' for r in baseline_50ms[:10]]}")
        logger.info(f"  Last 10:  {[f'{r:.0f}' for r in baseline_50ms[-10:]]}")
        logger.info(
            f"  Mean: {avg_baseline:.0f}, Std: {std_baseline:.1f}, CV: {cv_baseline:.2f}%",
        )
        logger.info(
            f"  Range: {min_baseline:.0f} - {max_baseline:.0f} (Δ={range_baseline:.0f} counts)",
        )
        logger.info(f"  Stability: {'POOR ⚠️' if cv_baseline > 1.0 else 'GOOD ✅'}")

    # Compare all three
    logger.info("\n📊 COMPARISON - 25ms vs 50ms delay:")
    if fast_no_correction and fast_with_correction and baseline_50ms:
        logger.info(
            f"  25ms (no correction):   σ = {std_fast_raw:.1f} counts, CV = {cv_fast_raw:.2f}%",
        )
        logger.info(
            f"  25ms (with correction): σ = {std_fast_corr:.1f} counts, CV = {cv_fast_corr:.2f}%",
        )
        logger.info(
            f"  50ms (baseline):        σ = {std_baseline:.1f} counts, CV = {cv_baseline:.2f}%",
        )

        improvement_correction = (
            ((std_fast_raw - std_fast_corr) / std_fast_raw * 100)
            if std_fast_raw > 0
            else 0
        )
        logger.info(
            f"\n  Afterglow correction improvement: {improvement_correction:.1f}%",
        )

        if cv_fast_corr < 0.5:
            logger.info("\n  ✅ 25ms delay with correction is EXCELLENT")
            logger.info("     → 2x faster than 50ms with good precision")
            logger.info("     → Afterglow correction RECOMMENDED for 25ms operation")
        elif cv_fast_raw < 0.5:
            logger.info("\n  ✅ 25ms delay without correction is ACCEPTABLE")
            logger.info("     → 2x faster than 50ms")
            logger.info("     → Afterglow correction optional")
        else:
            logger.info("\n  ⚠️ 25ms delay shows increased noise")
            logger.info("     → Consider using 50ms delay for better stability")

    # PART 3: Estimate decay constant (tau) for each channel
    logger.info(f"\n{'='*80}")
    logger.info("PART 3: Afterglow Decay Analysis (All Channels)")
    logger.info(f"{'='*80}")

    for ch in channels:
        afterglow_data = all_afterglow_data[ch]["data"]
        peak = all_afterglow_data[ch]["peak"]

        logger.info(f"\nChannel {ch.upper()}:")

        if len(afterglow_data) >= 3:
            # Simple exponential fit: y = A * exp(-t/tau)
            # Taking log: ln(y) = ln(A) - t/tau
            # Fit on early decay points (first 100ms)
            early_data = [(t, s) for t, s, _ in afterglow_data if t <= 100 and s > 100]

            if len(early_data) >= 3:
                import math

                # Remove peak signal (subtract baseline)
                baseline = afterglow_data[-1][1]  # Last measurement as baseline

                # Linear fit in log space
                t_vals = [t for t, s in early_data]
                y_vals = [
                    math.log(s - baseline) if s > baseline else 0 for t, s in early_data
                ]

                # Simple linear regression
                n = len(t_vals)
                if n >= 2 and all(y > 0 for y in y_vals):
                    mean_t = sum(t_vals) / n
                    mean_y = sum(y_vals) / n
                    slope = sum(
                        (t - mean_t) * (y - mean_y)
                        for t, y in zip(t_vals, y_vals, strict=False)
                    ) / sum((t - mean_t) ** 2 for t in t_vals)

                    tau_ms = -1.0 / slope if slope < 0 else 0

                    if 5 < tau_ms < 200:  # Physically reasonable for LED phosphors
                        logger.info(f"  Estimated decay constant (τ): {tau_ms:.1f}ms")
                        logger.info(
                            f"  Decay equation: y(t) = A × exp(-t/{tau_ms:.1f})",
                        )

                        # Predict residual at 50ms (typical operating delay)
                        residual_50ms = early_data[0][1] * math.exp(-50 / tau_ms)
                        residual_pct = (residual_50ms / peak * 100) if peak > 0 else 0
                        logger.info(
                            f"  Predicted residual @ 50ms: {residual_50ms:.0f} counts ({residual_pct:.2f}% of peak)",
                        )

                        if residual_pct > 1:
                            logger.info(
                                "     ⚠️ Significant residual - afterglow correction RECOMMENDED",
                            )
                        else:
                            logger.info(
                                "     ✅ Low residual - afterglow correction optional",
                            )
                    else:
                        logger.warning(
                            f"  Could not fit decay constant (τ = {tau_ms:.1f}ms outside expected range)",
                        )
                else:
                    logger.warning("  Insufficient data for decay fit")
            else:
                logger.warning("  Insufficient early decay data points")
        else:
            logger.warning("  Insufficient afterglow data")

    # Clean up
    ctrl.turn_off_channels()


def main():
    """Run all tests for Mode 2 integration time calibration."""
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info(
        "║"
        + "  MODE 2 (ALTERNATIVE) INTEGRATION TIME CALIBRATION TEST".center(78)
        + "║",
    )
    logger.info("║" + " " * 78 + "║")
    logger.info(
        "║" + "  Tests per-channel integration time optimization".center(78) + "║",
    )
    logger.info(
        "║" + "  with LEDs fixed at 255 (Global LED Intensity method)".center(78) + "║",
    )
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")

    # Test 1: Hardware connection
    ctrl, usb = test_hardware_connection()
    if ctrl is None or usb is None:
        logger.error("\n❌ TEST FAILED: Cannot proceed without hardware")
        return 1

    try:
        # Test 2: Calibrate all channels
        results = test_all_channels(usb, ctrl)

        if not results:
            logger.error("\n❌ TEST FAILED: No channels calibrated successfully")
            return 1

        # Test 3: Analyze results
        analyze_results(results)

        # Test 4: LED delay impact
        test_led_delay_impact(usb, ctrl)

        # Test 5: Afterglow measurement and stability impact
        test_afterglow_measurement(usb, ctrl)

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)

        all_passed = all(
            r["target_met"] and r["timing_budget_ok"] for r in results.values()
        )

        if all_passed:
            logger.info("✅ ALL TESTS PASSED")
            logger.info("   Mode 2 integration time calibration is working correctly")
            logger.info("   System is ready for Alternative calibration method")
        else:
            logger.warning("⚠️ SOME TESTS FAILED")
            logger.warning("   Review warnings above for specific issues")
            logger.warning("   System may need optical alignment or LED replacement")

        logger.info("\n" + "=" * 80)

        return 0 if all_passed else 1

    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Test interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED with exception: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        try:
            if ctrl:
                ctrl.turn_off_channels()
                ctrl.close()
                logger.info("✓ Controller closed")
        except:
            pass

        try:
            if usb:
                usb.close()
                logger.info("✓ Spectrometer closed")
        except:
            pass


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
