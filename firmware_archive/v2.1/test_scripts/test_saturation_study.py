"""Saturation Study: Understand relationship between LED intensity, saturation pixels, and true signal.

Purpose:
- Measure saturation behavior across LED intensity range
- Find relationship between # saturated pixels and true signal level
- Build empirical model for LED reduction when saturated
"""

import json
import time
from pathlib import Path

import numpy as np

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger


def count_saturated_pixels(spectrum, wave_min_idx, wave_max_idx, sat_threshold=65535):
    """Count pixels at or above saturation threshold in ROI."""
    if spectrum is None or len(spectrum) == 0:
        return 0
    roi = spectrum[wave_min_idx:wave_max_idx]
    return int(np.sum(roi >= sat_threshold))


def measure_at_led_intensity(
    ctrl,
    usb,
    channel,
    led_intensity,
    integration_time_ms,
    wave_min_idx,
    wave_max_idx,
):
    """Measure spectrum at specific LED intensity and return signal + saturation."""
    # Use direct single LED command
    ctrl.set_intensity(channel, led_intensity)
    ctrl.turn_on_channel(channel)
    time.sleep(0.050)  # LED stabilization

    # Set integration and read
    usb.set_integration(integration_time_ms)
    spectrum = usb.read_intensity()

    # Turn off
    ctrl.turn_off_channels()
    time.sleep(0.020)

    if spectrum is None or len(spectrum) == 0:
        return None

    # Calculate metrics
    roi = spectrum[wave_min_idx:wave_max_idx]
    median_signal = float(np.median(roi))
    mean_signal = float(np.mean(roi))
    max_signal = float(np.max(roi))
    sat_pixels = count_saturated_pixels(spectrum, wave_min_idx, wave_max_idx)
    sat_fraction = sat_pixels / len(roi)

    return {
        "led_intensity": led_intensity,
        "integration_time_ms": integration_time_ms,
        "median_signal": median_signal,
        "mean_signal": mean_signal,
        "max_signal": max_signal,
        "saturated_pixels": sat_pixels,
        "saturation_fraction": sat_fraction,
        "total_roi_pixels": len(roi),
    }


def run_saturation_study(
    channel="a",
    integration_time_ms=60.0,
    led_start=50,
    led_end=255,
    led_step=10,
):
    """Run saturation study by sweeping LED intensity.

    Args:
        channel: LED channel to test ('a', 'b', 'c', 'd')
        integration_time_ms: Fixed integration time for all measurements
        led_start: Starting LED intensity (should be unsaturated)
        led_end: Ending LED intensity (will be saturated)
        led_step: Step size for LED sweep

    """
    print("=" * 80)
    print(f"SATURATION STUDY - Channel {channel.upper()}")
    print("=" * 80)
    print(f"Integration Time: {integration_time_ms:.1f}ms")
    print(f"LED Range: {led_start} → {led_end} (step {led_step})")
    print()

    # Initialize hardware
    logger.info("Connecting to hardware...")
    hw_mgr = HardwareManager()
    logger.info("Scanning for devices...")
    connection_result = hw_mgr.scan_and_connect(auto_connect=True)
    logger.info(f"Connection result: {connection_result}")
    # Wait briefly for background init
    start_t = time.time()
    while time.time() - start_t < 10:
        if hw_mgr.usb and hw_mgr.ctrl:
            break
        time.sleep(0.5)
    if not hw_mgr.usb or not hw_mgr.ctrl:
        logger.error(
            f"Hardware not connected (usb={hw_mgr.usb is not None}, ctrl={hw_mgr.ctrl is not None})",
        )
        # Fall back to analysis-only guidance
        print("\n=== ANALYSIS ONLY (no hardware test) ===\n")
        print("To actually test, run calibration in main app and observe:")
        print("  - Saturation pixel counts")
        print("  - Estimated true signal values")
        print("  - LED reduction ratios")
        print("\nThe hybrid saturation logic is already active!")
        return None
    logger.info(f"✓ Detector: {hw_mgr.usb.serial_number}")
    ctrl_name = getattr(
        hw_mgr.ctrl,
        "device_type",
        getattr(hw_mgr.ctrl, "device", type(hw_mgr.ctrl).__name__),
    )
    logger.info(f"✓ Controller: {ctrl_name}")

    # Load calibration for ROI
    cal_file = Path("calibration_results/latest_calibration.json")
    if not cal_file.exists():
        print(f"ERROR: Calibration file not found: {cal_file}")
        return None

    with open(cal_file, encoding="utf-8") as f:
        cal_json = json.load(f)

    wave_min_idx = cal_json.get("wave_min_index", 1063)
    wave_max_idx = cal_json.get("wave_max_index", 3060)
    print(f"✓ ROI: pixels {wave_min_idx}:{wave_max_idx}")
    print()

    # LED intensity sweep
    results = []
    led_intensities = list(range(led_start, led_end + 1, led_step))

    print("Starting LED sweep...")
    print("-" * 80)
    print(
        f"{'LED':<6} {'Median':<10} {'Mean':<10} {'Max':<10} {'Sat Px':<10} {'Sat %':<8}",
    )
    print("-" * 80)

    for led_int in led_intensities:
        result = measure_at_led_intensity(
            hw_mgr.ctrl,
            hw_mgr.usb,
            channel,
            led_int,
            integration_time_ms,
            wave_min_idx,
            wave_max_idx,
        )

        if result is None:
            print(f"{led_int:<6} FAILED")
            continue

        results.append(result)

        # Print result
        sat_indicator = " SAT!" if result["saturated_pixels"] > 0 else ""
        print(
            f"{result['led_intensity']:<6} "
            f"{result['median_signal']:<10.0f} "
            f"{result['mean_signal']:<10.0f} "
            f"{result['max_signal']:<10.0f} "
            f"{result['saturated_pixels']:<10} "
            f"{result['saturation_fraction']*100:<7.1f}%"
            f"{sat_indicator}",
        )

        time.sleep(0.1)  # Brief pause between measurements

    print("-" * 80)
    print(f"Completed {len(results)} measurements")
    print()

    # Disconnect hardware
    try:
        hw_mgr.ctrl.turn_off_channels()
    except Exception:
        pass
    # No explicit disconnect method on HardwareManager; rely on OS/driver cleanup

    # Save results
    output_file = Path(
        f"saturation_study_ch{channel}_{int(integration_time_ms)}ms.json",
    )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "channel": channel,
                "integration_time_ms": integration_time_ms,
                "led_range": {"start": led_start, "end": led_end, "step": led_step},
                "measurements": results,
            },
            f,
            indent=2,
        )

    print(f"✓ Results saved: {output_file}")
    print()

    # Analysis
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    # Find saturation onset
    first_sat_idx = next(
        (i for i, r in enumerate(results) if r["saturated_pixels"] > 0),
        None,
    )
    if first_sat_idx is not None:
        first_sat = results[first_sat_idx]
        last_unsat = results[first_sat_idx - 1] if first_sat_idx > 0 else None

        print("Saturation Onset:")
        if last_unsat:
            print(
                f"  Last unsaturated: LED={last_unsat['led_intensity']}, signal={last_unsat['median_signal']:.0f}",
            )
        print(
            f"  First saturated:  LED={first_sat['led_intensity']}, signal={first_sat['median_signal']:.0f}, sat_px={first_sat['saturated_pixels']}",
        )
        print()

        # Compare heavily saturated to onset
        heavy_sat = results[-1]  # Last measurement (highest LED)
        if heavy_sat["saturated_pixels"] > 0:
            print(f"Heavy Saturation (LED={heavy_sat['led_intensity']}):")
            print(
                f"  Saturated pixels: {heavy_sat['saturated_pixels']} ({heavy_sat['saturation_fraction']*100:.1f}%)",
            )
            print(f"  Median signal: {heavy_sat['median_signal']:.0f} (clipped)")
            print()

            # Estimate true signal from LED ratio
            if last_unsat:
                led_ratio = heavy_sat["led_intensity"] / last_unsat["led_intensity"]
                estimated_true = last_unsat["median_signal"] * led_ratio
                print(f"  Estimated TRUE signal: {estimated_true:.0f} (if linear)")
                print(f"    LED ratio: {led_ratio:.2f}x")
                print(f"    Baseline signal: {last_unsat['median_signal']:.0f}")
                print(
                    f"    Predicted: {last_unsat['median_signal']:.0f} × {led_ratio:.2f} = {estimated_true:.0f}",
                )
                print()

    # Build saturation model
    print("Saturation Pixel Count vs LED Intensity:")
    saturated_results = [r for r in results if r["saturated_pixels"] > 0]
    if len(saturated_results) >= 2:
        for r in saturated_results:
            print(
                f"  LED={r['led_intensity']:<4} → {r['saturated_pixels']:<6} pixels ({r['saturation_fraction']*100:>5.1f}%)",
            )
        print()

        # Estimate relationship
        print("Key Insight:")
        print("  More saturated pixels = higher TRUE signal (above detector max)")
        print("  Use saturation fraction to estimate reduction needed")
        print()

    # Recommend reduction: LED and/or integration time
    print("RECOMMENDED REDUCTION")
    print("-" * 80)
    target_median = 60000.0
    recommended = {
        "recommended_led": None,
        "recommended_integration_ms": None,
        "basis": "heuristic",
    }

    # Heuristic: prefer integration reduction when heavy saturation
    heavy_sat = any(r["saturation_fraction"] >= 0.5 for r in results)
    if heavy_sat:
        new_int = max(int(round(integration_time_ms * 0.6)), 10)
        recommended["recommended_integration_ms"] = float(new_int)
    # LED recommendation based on onset
    if first_sat_idx is not None:
        last_unsat = results[first_sat_idx - 1] if first_sat_idx > 0 else None
        if last_unsat:
            base_led = int(last_unsat["led_intensity"])
            base_med = float(last_unsat["median_signal"])
            scale_led = target_median / max(base_med, 1.0)
            rec_led = max(int(round(base_led * scale_led)), max(5, base_led - 5))
            recommended["recommended_led"] = rec_led
        else:
            # No unsat baseline; scale from first saturated median
            base_led = int(results[first_sat_idx]["led_intensity"])
            base_med = float(results[first_sat_idx]["median_signal"])
            scale_led = target_median / max(base_med, 1.0)
            recommended["recommended_led"] = max(int(round(base_led * scale_led)), 5)
    else:
        # No saturation observed: if median above target, scale down
        mid = results[-1]["median_signal"] if results else target_median
        if mid > target_median and results:
            led_last = int(results[-1]["led_intensity"])
            scale_led = target_median / max(mid, 1.0)
            recommended["recommended_led"] = int(round(led_last * scale_led))

    print(
        f"  LED → {recommended['recommended_led'] if recommended['recommended_led'] is not None else 'no change'}",
    )
    print(
        f"  Integration → {recommended['recommended_integration_ms'] if recommended['recommended_integration_ms'] is not None else 'no change'} ms",
    )
    print()

    # Save recommendations alongside results
    output_file = Path(
        f"saturation_study_ch{channel}_{int(integration_time_ms)}ms.json",
    )
    try:
        with open(output_file, encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        existing = None
    payload = {
        "channel": channel,
        "integration_time_ms": integration_time_ms,
        "led_range": {"start": led_start, "end": led_end, "step": led_step},
        "measurements": results,
        "recommendations": recommended,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"✓ Recommendations saved with results: {output_file}")

    return results


if __name__ == "__main__":
    # Run study on channel C with 25ms integration
    results = run_saturation_study(
        channel="c",
        integration_time_ms=25.0,
        led_start=50,
        led_end=255,
        led_step=15,  # Larger steps for faster sweep
    )

    if results:
        print("✓ Saturation study complete!")
        print("Review the JSON file for detailed data")
