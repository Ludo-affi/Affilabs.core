"""Reusable LED calibration methods - REFACTORED.

Clean modular implementation:
- led_convergence_core.py: Primitives (measurement, adjustment, boundaries)
- led_convergence_algorithm.py: Main convergence loop (LEDconverge)
- This file: Legacy compatibility + supporting functions

Main entry point: LEDconverge (imported from led_convergence_algorithm)
"""

import time
from typing import Optional

import numpy as np

# Import clean implementations
from .led_convergence_core import (
    DetectorParams,
    count_saturated_pixels,
    analyze_saturation_severity,
)

from .led_convergence_algorithm import LEDconverge

# Re-export for backward compatibility
__all__ = [
    'DetectorParams',
    'count_saturated_pixels', 
    'analyze_saturation_severity',
    'calculate_led_reduction_from_saturation',
    'LEDconverge',
    'LEDnormalizationintensity',
    'LEDnormalizationtime',
]


# analyze_saturation_severity imported from led_convergence_core.py above
    severity = max_width * sat_fraction

    return {
        'sat_pixels': sat_count,
        'sat_fraction': sat_fraction,
        'max_contiguous_width': max_width,
        'num_sat_regions': num_regions,
        'severity_score': severity,
    }


def calculate_led_reduction_from_saturation(
    current_led: int,
    current_integration_ms: float,
    saturation_analysis: dict,
    model_slope: float,
    detector_params: DetectorParams,
    target_percent: float = 0.80,
    polarization: str = 'S',
    logger=None,
) -> tuple[int, str]:
    """Calculate intelligent LED reduction using model slope and saturation severity.

    Uses measured LED-to-signal slope from 3-step model combined with saturation
    severity metrics (pixel count + contiguous width) to calculate exact LED
    reduction needed.

    Strategy differs by polarization:
    - S-pol: Aggressive reduction (saturation-prone, high signal)
    - P-pol: Conservative reduction (rarely saturates, signal typically low)

    Args:
        current_led: Current LED intensity (0-255)
        current_integration_ms: Current integration time (ms)
        saturation_analysis: Output from analyze_saturation_severity()
        model_slope: Calibration slope (counts/LED) from 3-step model
        detector_params: Detector parameters (max_counts, saturation_threshold)
        target_percent: Target signal as fraction of detector max (e.g., 0.80)
        polarization: 'S' or 'P' - affects safety margins
        logger: Logger instance

    Returns:
        (new_led, reason): New LED intensity and explanation string
    """
    sat_fraction = saturation_analysis['sat_fraction']
    max_width = saturation_analysis['max_contiguous_width']
    severity = saturation_analysis['severity_score']

    target_counts = target_percent * detector_params.max_counts

    # Estimate TRUE unsaturated signal from saturation severity
    # Rule: each 1% saturation ≈ 0.5-1% signal underestimation (clipping loss)
    measured_signal = detector_params.saturation_threshold  # Clipped at this value
    estimated_loss_factor = 1.0 + (sat_fraction * 0.7)  # Conservative estimate
    true_signal_estimate = measured_signal * estimated_loss_factor

    # Calculate LED needed for target using model slope
    # Signal = LED × slope, so LED_target = target / slope
    if model_slope > 0:
        led_for_target = target_counts / model_slope
    else:
        # Fallback if slope unavailable: use fixed reduction
        led_for_target = current_led * 0.75

    # Apply safety margin based on severity AND polarization
    if polarization.upper() == 'S':
        # S-pol: More aggressive margins (saturation-prone)
        if severity > 50:  # High severity: large width × high fraction
            safety_factor = 0.80  # 20% safety margin
            reason = f"S-pol HIGH severity (width={max_width}, frac={sat_fraction:.1%}) → aggressive reduction"
        elif severity > 20:  # Medium severity
            safety_factor = 0.85  # 15% safety margin
            reason = f"S-pol MEDIUM severity (width={max_width}, frac={sat_fraction:.1%}) → moderate reduction"
        else:  # Low severity
            safety_factor = 0.90  # 10% safety margin
            reason = f"S-pol LOW severity (width={max_width}, frac={sat_fraction:.1%}) → minor reduction"
    else:
        # P-pol: Conservative margins (rarely saturates)
        if severity > 50:
            safety_factor = 0.90  # 10% safety margin
            reason = f"P-pol HIGH severity (width={max_width}, frac={sat_fraction:.1%}) → moderate reduction"
        else:
            safety_factor = 0.95  # 5% safety margin
            reason = f"P-pol severity (width={max_width}, frac={sat_fraction:.1%}) → minor reduction"

    new_led = int(led_for_target * safety_factor)

    # Bounds checking
    new_led = max(10, min(255, new_led))

    # Additional check: Don't reduce below a minimum delta
    reduction = current_led - new_led
    if reduction < 15 and severity > 20:
        # If saturation is significant, ensure at least 15-point reduction
        new_led = max(10, current_led - 15)
        reason += " (enforced minimum 15-point reduction)"

    if logger:
        logger.info(f"[SAT-RECOVERY] Saturation detected: {saturation_analysis['sat_pixels']} pixels ({sat_fraction:.1%})")
        logger.info(f"[SAT-RECOVERY]   Max contiguous width: {max_width} pixels")
        logger.info(f"[SAT-RECOVERY]   Severity score: {severity:.1f}")
        logger.info(f"[SAT-RECOVERY]   Model slope: {model_slope:.1f} counts/LED")
        logger.info(f"[SAT-RECOVERY]   Estimated true signal: {true_signal_estimate:.0f} (clipped at {measured_signal:.0f})")
        logger.info(f"[SAT-RECOVERY]   Target signal: {target_counts:.0f}")
        logger.info(f"[SAT-RECOVERY]   LED calculation: {target_counts:.0f} / {model_slope:.1f} = {led_for_target:.1f}")
        logger.info(f"[SAT-RECOVERY]   Safety factor ({polarization}-pol): {safety_factor:.2f}x")
        logger.info(f"[SAT-RECOVERY]   LED {current_led} → {new_led} (reduction: {reduction})")
        logger.info(f"[SAT-RECOVERY]   Reason: {reason}")

    return new_led, reason


def LEDnormalizationintensity(
    channel_measurements: dict[str, tuple[float, float]],
    weakest_mean: float,
    min_led: int = 10,
    max_led: int = 255,
) -> dict[str, int]:
    """Compute normalized LED intensities for Step 3C.

    Args:
        channel_measurements: mapping `ch -> (mean_roi_counts, max_roi_counts)` measured at fixed integration and test LED.
        weakest_mean: mean ROI counts of the weakest channel used as reference.
        min_led: lower bound for LED value (default 10).
        max_led: upper bound for LED value (default 255).

    Returns:
        Dict of per-channel normalized LED intensities.

    """
    normalized_leds: dict[str, int] = {}
    for ch, (mean_val, _max_val) in channel_measurements.items():
        brightness_ratio = mean_val / weakest_mean if weakest_mean > 0 else 1.0
        led_val = int(max_led / brightness_ratio)
        led_val = max(min_led, min(max_led, led_val))
        normalized_leds[ch] = led_val
    return normalized_leds


# LEDconverge is imported from led_convergence_algorithm.py at top of file
# Old 680-line implementation removed - see new clean modules:
#   - led_convergence_core.py: Primitives and utilities
#   - led_convergence_algorithm.py: Main convergence loop


# =============================================================================
# SUPPORTING FUNCTIONS FOR LED NORMALIZATION TIME STRATEGY
# =============================================================================
    max_sig = (target_percent + tolerance_percent) * detector_max
    current = initial_integration_ms

    # Path A: If all LEDs are fixed at 255, jump directly to per-channel time fine-tune
    try:
        all_255 = all(int(led_intensities.get(ch, 0)) == 255 for ch in ch_list)
    except Exception:
        all_255 = False
    if all_255:
        if logger:
            logger.info(
                f"{step_name}: LEDs are all 255 — using per-channel integration time fine-tune path",
            )
        # Compute per-channel times to reach target using the seed-based method
        per_channel_times: dict[str, float] = {}
        seed_time = max(
            detector_params.min_integration_time,
            min(detector_params.max_integration_time, 35.0),
        )
        signals: dict[str, float] = {}
        for ch in ch_list:
            spec_seed = acquire_raw_spectrum_fn(
                usb, ctrl, ch, 255, seed_time, 1, 45.0, 5.0, False,
            )
            if spec_seed is None:
                continue
            sig_seed = roi_signal_fn(
                spec_seed, wave_min_index, wave_max_index, method="median", top_n=50,
            )
            if sig_seed <= 0:
                per_channel_times[ch] = seed_time
                signals[ch] = 0.0
                continue
            t_target = seed_time * (target / sig_seed)
            t_target = max(
                detector_params.min_integration_time,
                min(detector_params.max_integration_time, t_target),
            )
            # Verify and adjust within tolerance
            spec2 = acquire_raw_spectrum_fn(
                usb, ctrl, ch, 255, t_target, 1, 45.0, 5.0, use_batch_command,
            )
            if spec2 is not None:
                sig2 = roi_signal_fn(
                    spec2, wave_min_index, wave_max_index, method="median", top_n=50,
                )
                sat2 = count_saturated_pixels(
                    spec2,
                    wave_min_index,
                    wave_max_index,
                    detector_params.saturation_threshold,
                )
                if sat2 > 0:
                    # If we are at or near the minimum time and still saturated, reduce LED below 255 for this channel
                    near_min = (
                        abs(t_target - detector_params.min_integration_time) <= 0.5
                    )
                    if near_min:
                        # Compute LED scale to clear saturation towards target window
                        scale = max(
                            0.3, min(0.95, (target / sig2) if sig2 > 0 else 0.5),
                        )
                        new_led = int(max(10, min(255, round(255 * scale))))
                        if logger:
                            logger.info(
                                f"{step_name} per-channel: {ch.upper()} saturated at min time {t_target:.1f}ms — reducing LED 255→{new_led}",
                            )
                        # Re-measure with reduced LED at same time
                        spec2 = acquire_raw_spectrum_fn(
                            usb,
                            ctrl,
                            ch,
                            new_led,
                            t_target,
                            1,
                            45.0,
                            5.0,
                            use_batch_command,
                        )
                        sig2 = (
                            roi_signal_fn(
                                spec2,
                                wave_min_index,
                                wave_max_index,
                                method="median",
                                top_n=50,
                            )
                            if spec2 is not None
                            else sig2
                        )
                        # Update intensities for reporting path (although caller passed 255s)
                    else:
                        t_target *= 0.90
                        t_target = max(detector_params.min_integration_time, t_target)
                        spec2 = acquire_raw_spectrum_fn(
                            usb,
                            ctrl,
                            ch,
                            255,
                            t_target,
                            1,
                            45.0,
                            5.0,
                            use_batch_command,
                        )
                        sig2 = (
                            roi_signal_fn(
                                spec2,
                                wave_min_index,
                                wave_max_index,
                                method="median",
                                top_n=50,
                            )
                            if spec2 is not None
                            else sig2
                        )
                elif not (min_sig <= sig2 <= max_sig):
                    adj = max(0.90, min(1.10, (target / sig2) if sig2 > 0 else 1.0))
                    t_target *= adj
                    t_target = max(
                        detector_params.min_integration_time,
                        min(detector_params.max_integration_time, t_target),
                    )
            per_channel_times[ch] = float(t_target)
            # Final measurement at t_target
            spec_final = acquire_raw_spectrum_fn(
                usb,
                ctrl,
                ch,
                255,
                per_channel_times[ch],
                1,
                45.0,
                5.0,
                use_batch_command,
            )
            if spec_final is not None:
                sig_final = roi_signal_fn(
                    spec_final,
                    wave_min_index,
                    wave_max_index,
                    method="median",
                    top_n=50,
                )
                sat_final = count_saturated_pixels(
                    spec_final,
                    wave_min_index,
                    wave_max_index,
                    detector_params.saturation_threshold,
                )
                # Emergency saturation guard: immediately clear saturation with strong backoff
                if sat_final > 0:
                    # Prefer time backoff first; if near min, reduce LED sharply
                    near_min = (
                        abs(
                            per_channel_times[ch] - detector_params.min_integration_time,
                        )
                        <= 0.5
                    )
                    if not near_min:
                        per_channel_times[ch] = max(
                            detector_params.min_integration_time,
                            per_channel_times[ch] * 0.75,
                        )
                        spec_final = acquire_raw_spectrum_fn(
                            usb,
                            ctrl,
                            ch,
                            255,
                            per_channel_times[ch],
                            1,
                            45.0,
                            5.0,
                            use_batch_command,
                        )
                        if spec_final is not None:
                            sig_final = roi_signal_fn(
                                spec_final,
                                wave_min_index,
                                wave_max_index,
                                method="median",
                                top_n=50,
                            )
                            sat_final = count_saturated_pixels(
                                spec_final,
                                wave_min_index,
                                wave_max_index,
                                detector_params.saturation_threshold,
                            )
                    if near_min or sat_final > 0:
                        # Reduce LED using math toward target to clear saturation at min time
                        # scale = clamp(target/signal, 0.30..0.95)
                        scale = 0.5
                        if sig_final > 0:
                            scale = max(0.30, min(0.95, (target / sig_final)))
                        new_led = int(max(10, min(255, round(255 * scale))))
                        if logger:
                            logger.info(
                                f"{step_name} per-channel: {ch.upper()} emergency saturation clear — LED 255→{new_led} at T={per_channel_times[ch]:.1f}ms",
                            )
                        spec_final = acquire_raw_spectrum_fn(
                            usb,
                            ctrl,
                            ch,
                            new_led,
                            per_channel_times[ch],
                            1,
                            45.0,
                            5.0,
                            use_batch_command,
                        )
                        if spec_final is not None:
                            sig_final = roi_signal_fn(
                                spec_final,
                                wave_min_index,
                                wave_max_index,
                                method="median",
                                top_n=50,
                            )
                signals[ch] = sig_final
                if logger:
                    pct = sig_final / detector_max * 100.0 if detector_max else 0.0
                    logger.info(
                        f"{step_name} per-channel: S-{ch.upper()} {sig_final:.0f} ({pct:.1f}%) at T={per_channel_times[ch]:.1f}ms",
                    )
        # Return 0.0 for shared integration (unused) and converged flag based on tolerance
        ok = bool(signals) and all(min_sig <= signals[ch] <= max_sig for ch in signals)
        return 0.0, signals, ok

    # Track channels for which we've already increased integration time
    # (to avoid exponential time growth when channel can't reach target)
    time_boosted_for_channels: set[str] = set()
    
    # Track maximum LED intensity that caused saturation for each channel
    # Key: channel name, Value: max LED intensity that saturated
    # If a channel saturates at intensity X, never try X or higher again
    max_saturating_intensity: dict[str, int] = {}
    
    # Key: channel name, Value: min LED intensity that undershot target (signal below min_sig)
    # If a channel undershot at intensity Y, never go below Y when reducing from saturation
    # This prevents oscillation: don't drop below a value you know is too low
    min_undershooting_intensity: dict[str, int] = {}

    for i in range(max_iterations):
        usb.set_integration(current)
        time.sleep(0.010)
        signals: dict[str, float] = {}
        saturated_any = False
        sat_per_ch: dict[str, int] = {}

        for ch in ch_list:
            spec = acquire_raw_spectrum_fn(
                usb,
                ctrl,
                ch,
                led_intensities[ch],
                current,
                1,
                45.0,
                5.0,
                use_batch_command,
            )
            if spec is None:
                if logger:
                    logger.error(
                        f"{step_name} iter {i + 1}: {ch.upper()} read returned None @LED={led_intensities[ch]}, T={current:.1f}ms (batch={use_batch_command})",
                    )
                continue
            sig = roi_signal_fn(
                spec, wave_min_index, wave_max_index, method="median", top_n=50,
            )
            signals[ch] = sig
            sat = count_saturated_pixels(
                spec,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
            )
            sat_per_ch[ch] = sat
            saturated_any = saturated_any or (sat > 0)
            if logger:
                logger.info(
                    f"{step_name} iter {i + 1}: S-{ch.upper()} top50 {sig:.0f} counts ({sig / detector_max * 100:.1f}%) {'SAT' if sat > 0 else 'OK'} (sat_px={sat})",
                )

        if sat_per_ch and logger:
            total_sat = sum(sat_per_ch.values())
            logger.info(
                f"{step_name} iter {i + 1}: total_saturated_pixels={total_sat} per_channel={sat_per_ch}",
            )

        # Track which channels caused saturation this iteration
        for ch, sat_count in sat_per_ch.items():
            if sat_count > 0:
                current_intensity = led_intensities[ch]
                if ch not in max_saturating_intensity or current_intensity < max_saturating_intensity[ch]:
                    max_saturating_intensity[ch] = current_intensity
                    if logger:
                        logger.info(
                            f"{step_name} iter {i + 1}: {ch.upper()} saturated @ LED={current_intensity} - will not exceed this"
                        )
        
        # Track which channels undershot target (signal below minimum)
        # These define lower bounds - never go below an intensity that was too dim
        for ch in signals:
            if signals[ch] < min_sig:
                current_intensity = led_intensities[ch]
                if ch not in min_undershooting_intensity or current_intensity > min_undershooting_intensity[ch]:
                    min_undershooting_intensity[ch] = current_intensity
                    if logger:
                        logger.info(
                            f"{step_name} iter {i + 1}: {ch.upper()} undershot @ LED={current_intensity} ({signals[ch]/detector_max*100:.1f}%) - will not go below this"
                        )
        
        # Success condition: signals within tolerance band AND zero saturation
        # Zero saturation tolerance enforced - must continue iterating if any pixels saturated
        total_sat = sum(sat_per_ch.values()) if sat_per_ch else 0
        if signals and all(min_sig <= signals[ch] <= max_sig for ch in signals) and total_sat == 0:
            return current, signals, True
        
        # EARLY EXIT: If S and P polarization channels have converged, exit early
        # even if iteration cap not reached (optimization requested by user)
        # Zero saturation tolerance enforced for all early exits
        if polarization in ["s", "p"]:
            sp_channels = [ch for ch in signals if ch in ch_list]
            sp_sat = sum(sat_per_ch.get(ch, 0) for ch in sp_channels)
            if sp_channels and all(min_sig <= signals[ch] <= max_sig for ch in sp_channels) and sp_sat == 0:
                if logger:
                    logger.info(
                        f"{step_name} iter {i + 1}: {polarization.upper()}-pol converged early (all channels within target, zero saturation)"
                    )
                return current, signals, True
            
            # Additional early exit: If channels are stuck due to constraints and stable for 3+ iterations
            # (LED values haven't changed for 3 iterations), accept current state
            # Only if zero saturation achieved
            if i >= 5:  # Only after iteration 5+
                channels_in_relaxed_tolerance = [
                    ch for ch in sp_channels 
                    if (target_percent - 0.10) * detector_max <= signals[ch] <= (target_percent + 0.15) * detector_max
                ]
                if len(channels_in_relaxed_tolerance) == len(sp_channels) and sp_sat == 0:
                    if logger:
                        logger.info(
                            f"{step_name} iter {i + 1}: {polarization.upper()}-pol accepting (all channels within ±10-15% after 5+ iterations, zero saturation)"
                        )
                    return current, signals, True

        if signals and adjust_leds:
            # Identify which channels need adjustment (outside tolerance window)
            channels_needing_adjustment = [
                ch for ch in ch_list
                if ch in signals and not (min_sig <= signals[ch] <= max_sig)
            ]
            
            if not channels_needing_adjustment:
                # All channels are within tolerance - check saturation before accepting
                total_sat = sum(sat_per_ch.values()) if sat_per_ch else 0
                if total_sat == 0:
                    # All channels within tolerance AND zero saturation - converged!
                    return current, signals, True
                else:
                    if logger:
                        logger.warning(
                            f"{step_name} iter {i + 1}: All channels within tolerance but {total_sat} pixels saturated - continuing..."
                        )
            # Only rank channels that actually need adjustment
            errors = {ch: abs(signals[ch] - target) for ch in channels_needing_adjustment}
            ranked = sorted(errors.items(), key=lambda kv: kv[1], reverse=True)
            furthest = {ch for ch, _ in ranked[:2]}  # Top 2 channels furthest from target
            
            for ch in channels_needing_adjustment:
                sig = signals[ch]

                # Check for saturation - use slope-based recovery if available
                if sat_per_ch.get(ch, 0) > 0 and model_slopes and ch in model_slopes:
                    # SLOPE-BASED SATURATION RECOVERY
                    # Scale model slope (at 10ms reference) to current integration time
                    model_slope_at_current_int = model_slopes[ch] * (current / 10.0)

                    # Get full spectrum for severity analysis
                    spec_for_analysis = acquire_raw_spectrum_fn(
                        usb, ctrl, ch, led_intensities[ch], current,
                        num_scans=1, pre_led_delay_ms=45.0, post_led_delay_ms=5.0,
                        use_batch_command=use_batch_command,
                    )

                    if spec_for_analysis is not None:
                        sat_analysis = analyze_saturation_severity(
                            spec_for_analysis, wave_min_index, wave_max_index,
                            detector_params.saturation_threshold
                        )

                        new_int, reason = calculate_led_reduction_from_saturation(
                            current_led=led_intensities[ch],
                            current_integration_ms=current,
                            saturation_analysis=sat_analysis,
                            model_slope=model_slope_at_current_int,
                            detector_params=detector_params,
                            target_percent=target_percent,
                            polarization=polarization,
                            logger=logger,
                        )

                        if logger:
                            logger.info(
                                f"{step_name} iter {i + 1}: SLOPE-BASED recovery {ch.upper()} LED {led_intensities[ch]} → {new_int}"
                            )
                    else:
                        # Fallback if spectrum read fails
                        new_int = int(max(10, min(255, led_intensities[ch] * 0.75)))
                        if logger:
                            logger.warning(f"{step_name} iter {i + 1}: fallback reduction {ch.upper()} (spectrum read failed)")

                elif sat_per_ch.get(ch, 0) > 0:
                    # FALLBACK: Fixed reduction if no model slopes
                    new_int = int(max(10, min(255, led_intensities[ch] * 0.75)))
                    if logger:
                        logger.info(f"{step_name} iter {i + 1}: fixed 25% reduction {ch.upper()} (no model)")

                else:
                    # NO SATURATION: Model-aware convergence adjustment
                    # Use model slope to calculate precise LED adjustment based on signal error
                    if model_slopes and ch in model_slopes:
                        # Scale model slope (at 10ms reference) to current integration time
                        model_slope_at_current_int = model_slopes[ch] * (current / 10.0)
                        
                        # Calculate signal error (how far from target)
                        signal_error = target - sig  # Positive = need more signal, negative = too much signal
                        signal_error_percent = (signal_error / target) * 100.0
                        
                        # Calculate LED adjustment needed based on model sensitivity
                        # model_slope = counts per LED unit, so LED_delta = signal_error / slope
                        if abs(model_slope_at_current_int) > 0.1:  # Avoid division by near-zero
                            led_delta = signal_error / model_slope_at_current_int
                            
                            # Safety limits: Don't change by more than 50 LED units per iteration
                            # and be more conservative when close to target (±10% = ±3 LED max)
                            if abs(signal_error_percent) < 10.0:  # Within ±10% of target
                                led_delta = max(-3, min(3, led_delta))
                            else:
                                led_delta = max(-50, min(50, led_delta))
                            
                            new_int = int(max(10, min(255, led_intensities[ch] + led_delta)))
                            
                            if logger:
                                logger.info(
                                    f"{step_name} iter {i + 1}: MODEL-AWARE {ch.upper()} LED {led_intensities[ch]} → {new_int} "
                                    f"(error={signal_error_percent:+.1f}%, slope={model_slope_at_current_int:.1f} counts/LED, delta={led_delta:+.1f})"
                                )
                        else:
                            # Fallback if slope too small
                            desired_ratio = target / sig if sig > 0 else 1.5
                            desired_ratio = max(0.75, min(1.30, desired_ratio))
                            new_int = int(max(10, min(255, led_intensities[ch] * desired_ratio)))
                            if logger:
                                logger.warning(f"{step_name} iter {i + 1}: RATIO fallback {ch.upper()} (slope too small: {model_slope_at_current_int:.3f})")
                    else:
                        # Fallback if no model slopes available
                        # DYNAMIC: More aggressive bumps for signals far below target
                        if sig < target * 0.5:  # Signal less than 50% of target
                            lower, upper = (0.5, 2.0) if ch in furthest else (0.7, 1.5)
                        elif sig < target * 0.75:  # Signal less than 75% of target
                            lower, upper = (0.6, 1.6) if ch in furthest else (0.75, 1.35)
                        else:
                            lower, upper = (0.75, 1.30) if ch in furthest else (0.85, 1.15)
                        
                        desired_ratio = target / sig if sig > 0 else 1.5
                        desired_ratio = max(lower, min(upper, desired_ratio))
                        new_int = int(max(10, min(255, led_intensities[ch] * desired_ratio)))
                        if logger:
                            logger.info(f"{step_name} iter {i + 1}: RATIO-BASED {ch.upper()} (no model slopes)")

                # CRITICAL: Enforce convergence boundaries
                # Upper bound: Do not exceed intensity that previously caused saturation
                if ch in max_saturating_intensity and new_int >= max_saturating_intensity[ch]:
                    new_int = max(10, max_saturating_intensity[ch] - 5)  # Stay 5 below saturation point
                    if logger:
                        logger.info(
                            f"{step_name} iter {i + 1}: {ch.upper()} capped @ {new_int} (saturated previously @ {max_saturating_intensity[ch]})"
                        )
                
                # Lower bound: Do not go below intensity that previously undershot target
                # This forces convergence by preventing oscillation below known-too-dim values
                if ch in min_undershooting_intensity and new_int <= min_undershooting_intensity[ch]:
                    new_int = min(255, min_undershooting_intensity[ch] + 5)  # Stay 5 above undershoot point
                    if logger:
                        logger.info(
                            f"{step_name} iter {i + 1}: {ch.upper()} floored @ {new_int} (undershot previously @ {min_undershooting_intensity[ch]})"
                        )
                
                if new_int != led_intensities[ch]:
                    if logger and sat_per_ch.get(ch, 0) == 0:
                        # Only log normal adjustments (saturation recovery already logged)
                        logger.info(
                            f"{step_name} iter {i + 1}: adjust LED {ch.upper()} {led_intensities[ch]} → {new_int} ({'furthest' if ch in furthest else 'normal'})",
                        )
                    led_intensities[ch] = new_int

        # Check for LED-capped channels that need integration time increase
        # (e.g., P-pol Channel D at LED=255 but signal still below target)
        # IMPROVEMENT 2: Also trigger if ANY channel is significantly below target,
        # even if not maxed, when we're stuck in convergence loop
        # Only trigger if signal is at least 50% of target (otherwise it's a hardware failure)
        maxed_out_channels = {
            ch for ch in ch_list
            if ch in signals
            and led_intensities[ch] >= 255
            and signals[ch] < min_sig
            and signals[ch] >= (target * 0.50)  # Must be at least 50% of target
        }
        
        # If no maxed channels but convergence is stalled (same signals 3+ iterations),
        # also consider integration time increase
        if not maxed_out_channels and i >= 3:
            stuck_channels = {
                ch for ch in ch_list
                if ch in signals
                and signals[ch] < (target * 0.90)  # Below 90% of target
                and signals[ch] >= (target * 0.50)  # Above 50%
                and led_intensities[ch] >= 200  # Near max LED
            }
            if stuck_channels:
                maxed_out_channels = stuck_channels

        if maxed_out_channels:
            # Only increase integration time ONCE per convergence run
            # Filter to channels we haven't boosted for yet
            new_maxed_channels = maxed_out_channels - time_boosted_for_channels
            
            if new_maxed_channels:
                # Calculate integration time increase needed for weakest maxed channel
                weakest_ch = min(new_maxed_channels, key=lambda ch: signals[ch])
                required_ratio = target / signals[weakest_ch] if signals[weakest_ch] > 0 else 2.0

                # IMPROVEMENT 1: More aggressive increases for better convergence
                # Use at least 1.15x to overcome measurement noise and boundary effects
                # Cap at 2.0x for safety
                time_increase = min(2.0, max(1.15, required_ratio))
                new_integration = current * time_increase

                # Clamp to detector limits
                new_integration = max(
                    detector_params.min_integration_time,
                    min(detector_params.max_integration_time, new_integration)
                )

                if logger:
                    logger.info(
                        f"{step_name} iter {i + 1}: {weakest_ch.upper()} maxed at LED=255 with {signals[weakest_ch]/detector_max*100:.1f}% signal"
                    )
                    logger.info(
                        f"{step_name} iter {i + 1}: increasing integration time {current:.1f}ms → {new_integration:.1f}ms (ratio={time_increase:.2f}x)"
                    )

                current = new_integration
                
                # Mark these channels as boosted
                time_boosted_for_channels.update(new_maxed_channels)

                # After time increase, reduce LEDs proportionally for other channels
                # (they'll now get more signal at same LED)
                for ch in ch_list:
                    if ch not in maxed_out_channels and ch in signals:
                        # Estimate new LED based on time increase
                        led_intensities[ch] = int(max(10, led_intensities[ch] / time_increase))

        else:
            # Normal integration time adjustment
            avg = np.median(list(signals.values())) if signals else target
            if saturated_any:
                # Back off integration modestly to clear saturation, but keep iterating
                current *= 0.95
            else:
                factor = target / avg if avg > 0 else 1.0
                factor = max(0.95, min(1.05, factor))
                current *= factor
            current = max(
                detector_params.min_integration_time,
                min(detector_params.max_integration_time, current),
            )

    # FALLBACK: If iterations exhausted, check if we're "close enough"
    # Progressive tolerance relaxation: accept within ±10% as fallback success
    # IMPROVEMENT 3: Hardware-limited acceptance for high integration times
    if signals:
        # Check if we're hardware-limited (integration time near max)
        near_max_integration = current >= (detector_params.max_integration_time * 0.75)
        
        if near_max_integration:
            # Hardware-limited scenario: Accept 80%+ for all channels
            # (Can't increase integration time further, LED A maxed at 255)
            hardware_min = 0.80 * detector_max
            channels_above_hardware_min = [ch for ch in signals if signals[ch] >= hardware_min]
            
            if len(channels_above_hardware_min) == len(signals):
                if logger:
                    logger.warning(
                        f"{step_name}: Convergence incomplete after {max_iterations} iterations"
                    )
                    logger.warning(
                        f"{step_name}: ACCEPTING hardware-limited convergence (80%+ target, integration at {current/detector_params.max_integration_time*100:.0f}% of max)"
                    )
                    for ch in signals:
                        pct = signals[ch] / detector_max * 100.0
                        logger.info(f"  {ch.upper()}: {signals[ch]:.0f} ({pct:.1f}%) LED={led_intensities[ch]}")
                return current, signals, True
        
        # Normal fallback: ±10% tolerance
        fallback_tolerance = 0.10
        fallback_min = target * (1.0 - fallback_tolerance)
        fallback_max = target * (1.0 + fallback_tolerance)
        
        channels_in_fallback = [ch for ch in signals if fallback_min <= signals[ch] <= fallback_max]
        if len(channels_in_fallback) == len(signals):
            if logger:
                logger.warning(
                    f"{step_name}: Convergence incomplete after {max_iterations} iterations"
                )
                logger.warning(
                    f"{step_name}: ACCEPTING with relaxed tolerance (±{fallback_tolerance*100:.0f}%)"
                )
                for ch in signals:
                    pct = signals[ch] / detector_max * 100.0
                    logger.info(f"  {ch.upper()}: {signals[ch]:.0f} ({pct:.1f}%)")
            return current, signals, True
    
    return current, signals, False


def LEDnormalizationtime(
    usb,
    ctrl,
    ch_list: list[str],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    logger=None,
    tighten_final: bool = False,
    use_batch_command: bool = False,
) -> dict[str, float]:
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

    per_channel_times: dict[str, float] = {}

    # Choose a safe seed time mid-range to avoid saturation while getting signal
    seed_time = max(
        detector_params.min_integration_time,
        min(detector_params.max_integration_time, 35.0),
    )

    for ch in ch_list:
        # Measure at seed
        spec = acquire_raw_spectrum_fn(
            usb, ctrl, ch, 255, seed_time, 1, 45.0, 5.0, use_batch_command,
        )
        if spec is None:
            continue
        sig = roi_signal_fn(
            spec, wave_min_index, wave_max_index, method="median", top_n=50,
        )
        sat = count_saturated_pixels(
            spec, wave_min_index, wave_max_index, detector_params.saturation_threshold,
        )
        if logger:
            logger.info(
                f"LEDnormalizationtime seed: {ch.upper()} {sig:.0f} ({sig / detector_max * 100:.1f}%), sat_px={sat}",
            )

        if sig <= 0:
            per_channel_times[ch] = seed_time
            continue

        # Compute exact time to hit target
        t_target = seed_time * (target / sig)
        t_target = max(
            detector_params.min_integration_time,
            min(detector_params.max_integration_time, t_target),
        )

        # Verify and micro-adjust if outside tolerance or saturated
        spec2 = acquire_raw_spectrum_fn(
            usb, ctrl, ch, 255, t_target, 1, 45.0, 5.0, use_batch_command,
        )
        if spec2 is not None:
            sig2 = roi_signal_fn(
                spec2, wave_min_index, wave_max_index, method="median", top_n=50,
            )
            sat2 = count_saturated_pixels(
                spec2,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
            )
            if sat2 > 0:
                # Back off 10% to clear saturation
                t_target *= 0.90
                t_target = max(detector_params.min_integration_time, t_target)
            elif not (min_sig <= sig2 <= max_sig):
                # Small proportional tweak within ±10%
                adj = max(0.90, min(1.10, (target / sig2) if sig2 > 0 else 1.0))
                t_target *= adj
                t_target = max(
                    detector_params.min_integration_time,
                    min(detector_params.max_integration_time, t_target),
                )

        per_channel_times[ch] = float(t_target)

    # Optional final tighten: one more math-driven pass using LED-intensity scaling
    if tighten_final:
        for ch in ch_list:
            t_cur = per_channel_times.get(ch, seed_time)
            spec3 = acquire_raw_spectrum_fn(
                usb, ctrl, ch, 255, t_cur, 1, 45.0, 5.0, use_batch_command,
            )
            if spec3 is None:
                continue
            sig3 = roi_signal_fn(
                spec3, wave_min_index, wave_max_index, method="median", top_n=50,
            )
            count_saturated_pixels(
                spec3,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
            )
            # Uniform clamp for all channels to keep behavior consistent
            scale = max(0.95, min(1.04, (target / sig3) if sig3 > 0 else 1.0))
            t_new = max(
                detector_params.min_integration_time,
                min(detector_params.max_integration_time, t_cur * scale),
            )
            # Micro-dither near min time to beat quantization
            if abs(t_new - detector_params.min_integration_time) < 1.0:
                candidates = [
                    detector_params.min_integration_time,
                    detector_params.min_integration_time + 0.5,
                    detector_params.min_integration_time + 1.0,
                ]
                best_sig = sig3
                best_t = t_cur
                for t in candidates:
                    specd = acquire_raw_spectrum_fn(
                        usb, ctrl, ch, 255, t, 1, 45.0, 5.0, use_batch_command,
                    )
                    if specd is None:
                        continue
                    sd = roi_signal_fn(
                        specd, wave_min_index, wave_max_index, method="median", top_n=50,
                    )
                    satd = count_saturated_pixels(
                        specd,
                        wave_min_index,
                        wave_max_index,
                        detector_params.saturation_threshold,
                    )
                    # prefer closest-to-target without saturation
                    if satd == 0 and abs(sd - target) < abs(best_sig - target):
                        best_sig = sd
                        best_t = t
                per_channel_times[ch] = best_t
                if logger:
                    logger.info(
                        f"LEDnormalizationtime tighten: {ch.upper()} T={best_t:.1f}ms, S={best_sig:.0f}",
                    )
            else:
                per_channel_times[ch] = t_new
                if logger:
                    logger.info(
                        f"LEDnormalizationtime tighten: {ch.upper()} {t_cur:.1f}→{t_new:.1f}ms (scale={scale:.3f})",
                    )

    return per_channel_times
