"""Unified LED Convergence entrypoint.

Provides a single callable to run Step 3C/Step 4 convergence using either:
- lednormalizationintensity: normalize LEDs at a fixed time, then shared-time convergence
- lednormalizationtime: freeze LEDs at 255, compute per-channel times, optional final tighten

This wraps utilities from `src.utils.led_methods` and local ROI/acquisition helpers.
"""

from typing import Dict, List, Tuple
import time

try:
    from src.utils.led_methods import (
        LEDconverge,
        LEDnormalizationintensity,
        LEDnormalizationtime,
        DetectorParams,
        count_saturated_pixels,
    )
except Exception:
    LEDconverge = None
    LEDnormalizationintensity = None
    LEDnormalizationtime = None
    DetectorParams = None
    def count_saturated_pixels(*args, **kwargs):
        return 0


def run_convergence(
    usb,
    ctrl,
    ch_list: List[str],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    strategy: str = "intensity",  # "intensity" or "time"
    initial_integration_ms: float = 70.0,
    target_percent: float = 0.80,
    tolerance_percent: float = 0.025,
    tighten_final: bool = False,
    logger=None,
) -> Tuple[float | None, Dict[str, Dict[str, float]], bool]:
    """Run LED calibration convergence using selected strategy.

    Returns:
        (shared_integration_ms_or_None, per_channel_results, ok)
        - In time strategy, shared_integration_ms is None and per-channel times are returned.
        - In intensity strategy, shared_integration_ms is the converged value and per-channel signals are returned.
    """

    target_counts = target_percent * detector_params.max_counts

    if strategy == "time":
        # LEDs fixed at 255; compute per-channel times with optional final tighten
        per_times = LEDnormalizationtime(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            acquire_raw_spectrum_fn=acquire_raw_spectrum_fn,
            roi_signal_fn=roi_signal_fn,
            target_percent=target_percent,
            tolerance_percent=tolerance_percent,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            logger=logger,
            tighten_final=tighten_final,
        )
        results: Dict[str, Dict[str, float]] = {}
        for ch in ch_list:
            Tch = float(per_times.get(ch, initial_integration_ms))
            spec = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, Tch, 1, 45.0, 5.0, False)
            if spec is None:
                continue
            sig = roi_signal_fn(spec, wave_min_index, wave_max_index, method='median', top_n=50)
            results[ch] = {
                'final_led': 255,
                'final_integration_ms': Tch,
                'final_top50_counts': float(sig),
                'final_percentage': float((sig / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0),
            }
        ok = all(target_counts*(1.0 - tolerance_percent) <= results[ch]['final_top50_counts'] <= target_counts*(1.0 + tolerance_percent) for ch in results)
        return None, results, ok

    # intensity strategy: compute normalized LEDs then run shared-time convergence
    # Step 3A ranking at fixed LED and time
    test_led = 51
    usb.set_integration(initial_integration_ms)
    time.sleep(0.010)
    channel_measurements: Dict[str, Tuple[float, float]] = {}
    weakest_mean = None
    for ch in ch_list:
        # measure at fixed LED
        spec = acquire_raw_spectrum_fn(usb, ctrl, ch, test_led, initial_integration_ms, 1, 45.0, 5.0, False)
        if spec is None:
            continue
        mean_val = roi_signal_fn(spec, wave_min_index, wave_max_index, method='mean', top_n=None)
        max_val = roi_signal_fn(spec, wave_min_index, wave_max_index, method='max', top_n=None) if hasattr(roi_signal_fn, '__call__') else float(mean_val)
        channel_measurements[ch] = (float(mean_val), float(max_val))
        if weakest_mean is None or mean_val < weakest_mean:
            weakest_mean = float(mean_val)

    if weakest_mean is None:
        return initial_integration_ms, {}, False

    normalized_leds = LEDnormalizationintensity(channel_measurements, weakest_mean, min_led=10, max_led=255)

    # Run shared-time convergence
    shared_int, ch_signals, ok = LEDconverge(
        usb=usb,
        ctrl=ctrl,
        ch_list=ch_list,
        led_intensities=normalized_leds,
        acquire_raw_spectrum_fn=acquire_raw_spectrum_fn,
        roi_signal_fn=roi_signal_fn,
        initial_integration_ms=initial_integration_ms,
        target_percent=target_percent,
        tolerance_percent=tolerance_percent,
        detector_params=detector_params,
        wave_min_index=wave_min_index,
        wave_max_index=wave_max_index,
        max_iterations=5,
        step_name="Step 4",
        logger=logger,
    )

    # Format per-channel results
    results = {}
    for ch, sig in ch_signals.items():
        results[ch] = {
            'final_led': int(normalized_leds.get(ch, 255)),
            'final_integration_ms': float(shared_int),
            'final_top50_counts': float(sig),
            'final_percentage': float((sig / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0),
        }
    return shared_int, results, ok
