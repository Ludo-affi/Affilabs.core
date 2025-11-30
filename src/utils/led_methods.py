"""Reusable LED calibration methods.

This module defines two validated methods to be reused across calibration:

- LEDconverge: Gold-standard convergence that optimizes a shared integration time
  while applying per-channel LED corrections, explicitly avoiding saturation and
  driving signals to a target percentage using robust statistics.

- LEDnormalizationintensity: Normalizes per-channel LED intensities at a fixed
  integration time using inverse brightness ratios from a ranking pass, with
  proportional saturation handling.

Both functions are extracted from the tested real-hardware workflow used in
`test_led_calibration_steps_3_4.py` and are preserved for use in Step 3C and Step 4.
"""

from typing import Dict, Tuple, List
import time
import numpy as np


class DetectorParams:
    def __init__(self, max_counts: float, saturation_threshold: float, min_integration_time: float, max_integration_time: float):
        self.max_counts = max_counts
        self.saturation_threshold = saturation_threshold
        self.min_integration_time = min_integration_time
        self.max_integration_time = max_integration_time


def count_saturated_pixels(spectrum: np.ndarray, wave_min_index: int, wave_max_index: int, saturation_threshold: float) -> int:
    roi = spectrum[wave_min_index:wave_max_index]
    return int(np.sum(roi >= saturation_threshold))


def LEDnormalizationintensity(
    channel_measurements: Dict[str, Tuple[float, float]],
    weakest_mean: float,
    min_led: int = 10,
    max_led: int = 255,
) -> Dict[str, int]:
    """Compute normalized LED intensities for Step 3C.

    Args:
        channel_measurements: mapping `ch -> (mean_roi_counts, max_roi_counts)` measured at fixed integration and test LED.
        weakest_mean: mean ROI counts of the weakest channel used as reference.
        min_led: lower bound for LED value (default 10).
        max_led: upper bound for LED value (default 255).

    Returns:
        Dict of per-channel normalized LED intensities.
    """
    normalized_leds: Dict[str, int] = {}
    for ch, (mean_val, _max_val) in channel_measurements.items():
        brightness_ratio = mean_val / weakest_mean if weakest_mean > 0 else 1.0
        led_val = int(max_led / brightness_ratio)
        led_val = max(min_led, min(max_led, led_val))
        normalized_leds[ch] = led_val
    return normalized_leds


def LEDconverge(
    usb,
    ctrl,
    ch_list: List[str],
    led_intensities: Dict[str, int],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 5,
    step_name: str = 'Step 4',
    logger=None,
) -> Tuple[float, Dict[str, float], bool]:
    """Gold-standard convergence method to reach target counts with shared integration time.

    - Uses median-driven integration adjustments to reduce bias.
    - Applies per-channel LED corrections with furthest-first prioritization.
    - Tracks and avoids saturation via proportional reductions.

    Returns:
        (final_integration_ms, per_channel_signals, converged_bool)
    """
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    min_sig = (target_percent - tolerance_percent) * detector_max
    max_sig = (target_percent + tolerance_percent) * detector_max
    current = initial_integration_ms

    # Path A: If all LEDs are fixed at 255, jump directly to per-channel time fine-tune
    try:
        all_255 = all(int(led_intensities.get(ch, 0)) == 255 for ch in ch_list)
    except Exception:
        all_255 = False
    if all_255:
        if logger:
            logger.info(f"{step_name}: LEDs are all 255 — using per-channel integration time fine-tune path")
        # Compute per-channel times to reach target using the seed-based method
        per_channel_times: Dict[str, float] = {}
        seed_time = max(detector_params.min_integration_time,
                        min(detector_params.max_integration_time, 35.0))
        signals: Dict[str, float] = {}
        for ch in ch_list:
            spec_seed = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, seed_time, 1, 45.0, 5.0, False)
            if spec_seed is None:
                continue
            sig_seed = roi_signal_fn(spec_seed, wave_min_index, wave_max_index, method='median', top_n=50)
            if sig_seed <= 0:
                per_channel_times[ch] = seed_time
                signals[ch] = 0.0
                continue
            t_target = seed_time * (target / sig_seed)
            t_target = max(detector_params.min_integration_time, min(detector_params.max_integration_time, t_target))
            # Verify and adjust within tolerance
            spec2 = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, t_target, 1, 45.0, 5.0, False)
            if spec2 is not None:
                sig2 = roi_signal_fn(spec2, wave_min_index, wave_max_index, method='median', top_n=50)
                sat2 = count_saturated_pixels(spec2, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                if sat2 > 0:
                    # If we are at or near the minimum time and still saturated, reduce LED below 255 for this channel
                    near_min = abs(t_target - detector_params.min_integration_time) <= 0.5
                    if near_min:
                        # Compute LED scale to clear saturation towards target window
                        scale = max(0.3, min(0.95, (target / sig2) if sig2 > 0 else 0.5))
                        new_led = int(max(10, min(255, round(255 * scale))))
                        if logger:
                            logger.info(f"{step_name} per-channel: {ch.upper()} saturated at min time {t_target:.1f}ms — reducing LED 255→{new_led}")
                        # Re-measure with reduced LED at same time
                        spec2 = acquire_raw_spectrum_fn(usb, ctrl, ch, new_led, t_target, 1, 45.0, 5.0, False)
                        sig2 = roi_signal_fn(spec2, wave_min_index, wave_max_index, method='median', top_n=50) if spec2 is not None else sig2
                        # Update intensities for reporting path (although caller passed 255s)
                    else:
                        t_target *= 0.90
                        t_target = max(detector_params.min_integration_time, t_target)
                        spec2 = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, t_target, 1, 45.0, 5.0, False)
                        sig2 = roi_signal_fn(spec2, wave_min_index, wave_max_index, method='median', top_n=50) if spec2 is not None else sig2
                elif not (min_sig <= sig2 <= max_sig):
                    adj = max(0.90, min(1.10, (target / sig2) if sig2 > 0 else 1.0))
                    t_target *= adj
                    t_target = max(detector_params.min_integration_time, min(detector_params.max_integration_time, t_target))
            per_channel_times[ch] = float(t_target)
            # Final measurement at t_target
            spec_final = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, per_channel_times[ch], 1, 45.0, 5.0, False)
            if spec_final is not None:
                sig_final = roi_signal_fn(spec_final, wave_min_index, wave_max_index, method='median', top_n=50)
                sat_final = count_saturated_pixels(spec_final, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                # Emergency saturation guard: immediately clear saturation with strong backoff
                if sat_final > 0:
                    # Prefer time backoff first; if near min, reduce LED sharply
                    near_min = abs(per_channel_times[ch] - detector_params.min_integration_time) <= 0.5
                    if not near_min:
                        per_channel_times[ch] = max(detector_params.min_integration_time, per_channel_times[ch] * 0.75)
                        spec_final = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, per_channel_times[ch], 1, 45.0, 5.0, False)
                        if spec_final is not None:
                            sig_final = roi_signal_fn(spec_final, wave_min_index, wave_max_index, method='median', top_n=50)
                            sat_final = count_saturated_pixels(spec_final, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                    if near_min or sat_final > 0:
                        # Reduce LED using math toward target to clear saturation at min time
                        # scale = clamp(target/signal, 0.30..0.95)
                        scale = 0.5
                        if sig_final > 0:
                            scale = max(0.30, min(0.95, (target / sig_final)))
                        new_led = int(max(10, min(255, round(255 * scale))))
                        if logger:
                            logger.info(f"{step_name} per-channel: {ch.upper()} emergency saturation clear — LED 255→{new_led} at T={per_channel_times[ch]:.1f}ms")
                        spec_final = acquire_raw_spectrum_fn(usb, ctrl, ch, new_led, per_channel_times[ch], 1, 45.0, 5.0, False)
                        if spec_final is not None:
                            sig_final = roi_signal_fn(spec_final, wave_min_index, wave_max_index, method='median', top_n=50)
                signals[ch] = sig_final
                if logger:
                    pct = sig_final / detector_max * 100.0 if detector_max else 0.0
                    logger.info(f"{step_name} per-channel: S-{ch.upper()} {sig_final:.0f} ({pct:.1f}%) at T={per_channel_times[ch]:.1f}ms")
        # Return 0.0 for shared integration (unused) and converged flag based on tolerance
        ok = bool(signals) and all(min_sig <= signals[ch] <= max_sig for ch in signals)
        return 0.0, signals, ok

    for i in range(max_iterations):
        usb.set_integration(current)
        time.sleep(0.010)
        signals: Dict[str, float] = {}
        saturated_any = False
        sat_per_ch: Dict[str, int] = {}

        for ch in ch_list:
            spec = acquire_raw_spectrum_fn(usb, ctrl, ch, led_intensities[ch], current, 1, 45.0, 5.0, False)
            if spec is None:
                continue
            sig = roi_signal_fn(spec, wave_min_index, wave_max_index, method='median', top_n=50)
            signals[ch] = sig
            sat = count_saturated_pixels(spec, wave_min_index, wave_max_index, detector_params.saturation_threshold)
            sat_per_ch[ch] = sat
            saturated_any = saturated_any or (sat > 0)
            if logger:
                logger.info(f"{step_name} iter {i+1}: S-{ch.upper()} top50 {sig:.0f} counts ({sig/detector_max*100:.1f}%) {'SAT' if sat>0 else 'OK'} (sat_px={sat})")

        if sat_per_ch and logger:
            total_sat = sum(sat_per_ch.values())
            logger.info(f"{step_name} iter {i+1}: total_saturated_pixels={total_sat} per_channel={sat_per_ch}")

        if signals and all(min_sig <= signals[ch] <= max_sig for ch in signals) and not saturated_any:
            return current, signals, True

        if signals:
            errors = {ch: abs(signals[ch] - target) for ch in ch_list if ch in signals}
            ranked = sorted(errors.items(), key=lambda kv: kv[1], reverse=True)
            furthest = {ch for ch, _ in ranked[:2]}
            for ch, sig in signals.items():
                if min_sig <= sig <= max_sig:
                    continue
                lower, upper = (0.80, 1.20) if ch in furthest else (0.92, 1.08)
                desired_ratio = target / sig if sig > 0 else 1.0
                desired_ratio = max(lower, min(upper, desired_ratio))
                new_int = int(max(10, min(255, led_intensities[ch] * desired_ratio)))
                if sat_per_ch.get(ch, 0) > 0:
                    new_int = int(max(10, min(255, new_int * 0.85)))
                if new_int != led_intensities[ch]:
                    if logger:
                        logger.info(f"{step_name} iter {i+1}: adjust LED {ch.upper()} {led_intensities[ch]} → {new_int} ({'furthest' if ch in furthest else 'normal'})")
                    led_intensities[ch] = new_int

        avg = np.median(list(signals.values())) if signals else target
        if saturated_any:
            current *= 0.95
        else:
            factor = target / avg if avg > 0 else 1.0
            factor = max(0.95, min(1.05, factor))
            current *= factor
        current = max(detector_params.min_integration_time, min(detector_params.max_integration_time, current))

    return current, signals, False


def LEDnormalizationtime(
    usb,
    ctrl,
    ch_list: List[str],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    logger=None,
    tighten_final: bool = False,
) -> Dict[str, float]:
    """Compute per-channel integration times at LED=255 to hit target.

    Strategy:
    - Fix LED=255 for all channels (one-at-a-time measurement).
    - For each channel, measure signal at a seed integration time, then
      compute exact integration needed: T_target = T_seed * (target/signal).
    - Clamp to detector limits; verify and adjust within ±tolerance.

    Returns:
        Dict mapping channel -> per-channel integration time (ms) to reach target.
    """
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    min_sig = (target_percent - tolerance_percent) * detector_max
    max_sig = (target_percent + tolerance_percent) * detector_max

    per_channel_times: Dict[str, float] = {}

    # Choose a safe seed time mid-range to avoid saturation while getting signal
    seed_time = max(detector_params.min_integration_time,
                    min(detector_params.max_integration_time, 35.0))

    for ch in ch_list:
        # Measure at seed
        spec = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, seed_time, 1, 45.0, 5.0, False)
        if spec is None:
            continue
        sig = roi_signal_fn(spec, wave_min_index, wave_max_index, method='median', top_n=50)
        sat = count_saturated_pixels(spec, wave_min_index, wave_max_index, detector_params.saturation_threshold)
        if logger:
            logger.info(f"LEDnormalizationtime seed: {ch.upper()} {sig:.0f} ({sig/detector_max*100:.1f}%), sat_px={sat}")

        if sig <= 0:
            per_channel_times[ch] = seed_time
            continue

        # Compute exact time to hit target
        t_target = seed_time * (target / sig)
        t_target = max(detector_params.min_integration_time, min(detector_params.max_integration_time, t_target))

        # Verify and micro-adjust if outside tolerance or saturated
        spec2 = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, t_target, 1, 45.0, 5.0, False)
        if spec2 is not None:
            sig2 = roi_signal_fn(spec2, wave_min_index, wave_max_index, method='median', top_n=50)
            sat2 = count_saturated_pixels(spec2, wave_min_index, wave_max_index, detector_params.saturation_threshold)
            if sat2 > 0:
                # Back off 10% to clear saturation
                t_target *= 0.90
                t_target = max(detector_params.min_integration_time, t_target)
            elif not (min_sig <= sig2 <= max_sig):
                # Small proportional tweak within ±10%
                adj = max(0.90, min(1.10, (target / sig2) if sig2 > 0 else 1.0))
                t_target *= adj
                t_target = max(detector_params.min_integration_time, min(detector_params.max_integration_time, t_target))

        per_channel_times[ch] = float(t_target)

    # Optional final tighten: one more math-driven pass using LED-intensity scaling
    if tighten_final:
        for ch in ch_list:
            t_cur = per_channel_times.get(ch, seed_time)
            spec3 = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, t_cur, 1, 45.0, 5.0, False)
            if spec3 is None:
                continue
            sig3 = roi_signal_fn(spec3, wave_min_index, wave_max_index, method='median', top_n=50)
            sat3 = count_saturated_pixels(spec3, wave_min_index, wave_max_index, detector_params.saturation_threshold)
            # Uniform clamp for all channels to keep behavior consistent
            scale = max(0.95, min(1.04, (target / sig3) if sig3 > 0 else 1.0))
            t_new = max(detector_params.min_integration_time, min(detector_params.max_integration_time, t_cur * scale))
            # Micro-dither near min time to beat quantization
            if abs(t_new - detector_params.min_integration_time) < 1.0:
                candidates = [detector_params.min_integration_time,
                              detector_params.min_integration_time + 0.5,
                              detector_params.min_integration_time + 1.0]
                best_sig = sig3
                best_t = t_cur
                for t in candidates:
                    specd = acquire_raw_spectrum_fn(usb, ctrl, ch, 255, t, 1, 45.0, 5.0, False)
                    if specd is None:
                        continue
                    sd = roi_signal_fn(specd, wave_min_index, wave_max_index, method='median', top_n=50)
                    satd = count_saturated_pixels(specd, wave_min_index, wave_max_index, detector_params.saturation_threshold)
                    # prefer closest-to-target without saturation
                    if satd == 0 and abs(sd - target) < abs(best_sig - target):
                        best_sig = sd
                        best_t = t
                per_channel_times[ch] = best_t
                if logger:
                    logger.info(f"LEDnormalizationtime tighten: {ch.upper()} T={best_t:.1f}ms, S={best_sig:.0f}")
            else:
                per_channel_times[ch] = t_new
                if logger:
                    logger.info(f"LEDnormalizationtime tighten: {ch.upper()} {t_cur:.1f}→{t_new:.1f}ms (scale={scale:.3f})")

    return per_channel_times
