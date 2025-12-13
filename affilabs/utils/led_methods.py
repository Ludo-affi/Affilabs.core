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

import time
from typing import Optional

import numpy as np


class DetectorParams:
    def __init__(
        self,
        max_counts: float,
        saturation_threshold: float,
        min_integration_time: float,
        max_integration_time: float,
    ) -> None:
        self.max_counts = max_counts
        self.saturation_threshold = saturation_threshold
        self.min_integration_time = min_integration_time
        self.max_integration_time = max_integration_time


def count_saturated_pixels(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
) -> int:
    roi = spectrum[wave_min_index:wave_max_index]
    return int(np.sum(roi >= saturation_threshold))


def analyze_saturation_severity(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float = 65535,
) -> dict:
    """Analyze saturation severity: count + contiguous width.

    Measures both the number of saturated pixels and the maximum contiguous
    width of saturation. Contiguous saturation is more severe as it indicates
    entire spectral features are clipped.

    Args:
        spectrum: Full spectrum array
        wave_min_index: Start of ROI
        wave_max_index: End of ROI
        saturation_threshold: Saturation detection threshold (default 65535)

    Returns:
        Dictionary with:
            - sat_pixels: Total number of saturated pixels
            - sat_fraction: Fraction of ROI that is saturated
            - max_contiguous_width: Longest contiguous saturated block (pixels)
            - num_sat_regions: Number of separate saturated regions
            - severity_score: Combined severity metric (width × fraction)
    """
    roi = spectrum[wave_min_index:wave_max_index]
    saturated_mask = roi >= saturation_threshold

    # Count total saturated pixels
    sat_count = int(np.sum(saturated_mask))
    sat_fraction = sat_count / len(roi) if len(roi) > 0 else 0.0

    # Find contiguous saturated blocks
    sat_blocks = []
    in_block = False
    block_start = 0

    for i, is_sat in enumerate(saturated_mask):
        if is_sat and not in_block:
            block_start = i
            in_block = True
        elif not is_sat and in_block:
            sat_blocks.append(i - block_start)
            in_block = False

    if in_block:  # Block extends to end of ROI
        sat_blocks.append(len(saturated_mask) - block_start)

    max_width = max(sat_blocks) if sat_blocks else 0
    num_regions = len(sat_blocks)

    # Combined severity: width amplifies fraction
    # High width + high fraction = very severe
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


def LEDconverge(
    usb,
    ctrl,
    ch_list: list[str],
    led_intensities: dict[str, int],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 15,
    step_name: str = "Step 4",
    use_batch_command: bool = False,
    adjust_leds: bool = True,
    model_slopes: Optional[dict[str, float]] = None,
    polarization: str = 'S',
    logger=None,
) -> tuple[float, dict[str, float], bool]:
    """Gold-standard convergence method to reach target counts with shared integration time.

    - Uses median-driven integration adjustments to reduce bias.
    - Applies per-channel LED corrections with furthest-first prioritization.
    - Tracks and avoids saturation via slope-based intelligent reduction.

    New: Slope-based saturation recovery (when model_slopes provided):
    - S-pol: Aggressive saturation handling (high signal, saturation-prone)
    - P-pol: Conservative handling (low signal, rarely saturates)

    Args:
        model_slopes: Optional dict of calibration slopes {'a': slope, 'b': slope, ...}
                     Slopes are counts/LED at 10ms reference integration time.
                     If provided, enables intelligent slope-based saturation recovery.
        polarization: 'S' or 'P' - affects saturation recovery margins

    Returns:
        (final_integration_ms, per_channel_signals, converged_bool)

    """
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    # Wider tolerance for faster convergence: ±5% instead of ±2%
    tolerance_percent = max(tolerance_percent, 0.05)  # At least 5% tolerance
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

        # Success condition: signals within tolerance band.
        # Saturation is guidance during iteration, not a stop criteria.
        if signals and all(min_sig <= signals[ch] <= max_sig for ch in signals):
            return current, signals, True

        if signals and adjust_leds:
            errors = {ch: abs(signals[ch] - target) for ch in ch_list if ch in signals}
            ranked = sorted(errors.items(), key=lambda kv: kv[1], reverse=True)
            furthest = {ch for ch, _ in ranked[:2]}
            for ch, sig in signals.items():
                if min_sig <= sig <= max_sig:
                    continue

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
                    # NO SATURATION: Normal convergence adjustment
                    # DYNAMIC: More aggressive bumps for signals far below target
                    if sig < target * 0.5:  # Signal less than 50% of target
                        # Very aggressive increase for very low signals
                        lower, upper = (0.5, 2.0) if ch in furthest else (0.7, 1.5)
                    elif sig < target * 0.75:  # Signal less than 75% of target
                        # Aggressive increase for low signals
                        lower, upper = (0.6, 1.6) if ch in furthest else (0.75, 1.35)
                    else:
                        # Normal adjustment for signals near target
                        lower, upper = (0.75, 1.30) if ch in furthest else (0.85, 1.15)
                    
                    desired_ratio = target / sig if sig > 0 else 1.5
                    desired_ratio = max(lower, min(upper, desired_ratio))
                    new_int = int(max(10, min(255, led_intensities[ch] * desired_ratio)))

                if new_int != led_intensities[ch]:
                    if logger and sat_per_ch.get(ch, 0) == 0:
                        # Only log normal adjustments (saturation recovery already logged)
                        logger.info(
                            f"{step_name} iter {i + 1}: adjust LED {ch.upper()} {led_intensities[ch]} → {new_int} ({'furthest' if ch in furthest else 'normal'})",
                        )
                    led_intensities[ch] = new_int

        # Check for LED-capped channels that need integration time increase
        # (e.g., P-pol Channel D at LED=255 but signal still below target)
        # Only trigger if signal is at least 50% of target (otherwise it's a hardware failure)
        maxed_out_channels = {
            ch for ch in ch_list
            if ch in signals
            and led_intensities[ch] >= 255
            and signals[ch] < min_sig
            and signals[ch] >= (target * 0.50)  # Must be at least 50% of target
        }

        if maxed_out_channels:
            # Only increase integration time ONCE per convergence run
            # Filter to channels we haven't boosted for yet
            new_maxed_channels = maxed_out_channels - time_boosted_for_channels
            
            if new_maxed_channels:
                # Calculate integration time increase needed for weakest maxed channel
                weakest_ch = min(new_maxed_channels, key=lambda ch: signals[ch])
                required_ratio = target / signals[weakest_ch] if signals[weakest_ch] > 0 else 2.0

                # More aggressive increase to reach target (cap at 2.0x)
                # Use full ratio up to 2x for better convergence
                time_increase = min(2.0, required_ratio)
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
    if signals:
        fallback_tolerance = 0.10  # ±10% fallback tolerance
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
