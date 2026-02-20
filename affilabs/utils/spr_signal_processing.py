from __future__ import annotations

"""Injection and SPR signal utilities — live acquisition path.

Live callers:
- auto_detect_injection_point   ← ManualInjectionDialog (per-channel injection detection)
- detect_injection_all_channels ← InjectionCoordinator (retroactive multi-channel scan)
- measure_delta_spr             ← cycle result reporting
- validate_sp_orientation       ← calibration orchestrator
- apply_centered_median_filter  ← sensorgram smoothing utility
"""

import numpy as np

from affilabs.utils.logger import logger


def apply_centered_median_filter(
    values: np.ndarray,
    current_index: int,
    window_size: int,
) -> float:
    """Apply centered median filter at a specific index.

    Uses a centered window around the current point for better temporal accuracy.
    For points near the beginning where a full centered window isn't available,
    uses all available data up to that point.

    Args:
        values: Array of values to filter (may contain NaN)
        current_index: Index of point to filter
        window_size: Median filter window size (should be odd)

    Returns:
        float: Filtered value (median of window), or np.nan if input is NaN

    """
    # If current value is NaN, return NaN
    if current_index >= len(values):
        return np.nan

    if np.isnan(values[current_index]):
        return np.nan

    # Not enough data for filtering yet
    if len(values) <= window_size:
        # Use all available data for initial values
        return float(np.nanmedian(values[: current_index + 1]))

    # Center the window on current point
    half_win = window_size // 2
    start_idx = max(0, current_index - half_win)
    end_idx = min(len(values), current_index + half_win + 1)

    window_data = values[start_idx:end_idx]

    return float(np.nanmedian(window_data))



def validate_sp_orientation(
    p_spectrum: np.ndarray,
    s_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    window_px: int = 200,
) -> dict:
    """Validate S/P polarizer orientation by analyzing transmission spectrum ONLY.

    IMPORTANT: This function analyzes the TRANSMISSION SPECTRUM (P/S ratio) to detect
    polarizer orientation. Raw P vs S intensity comparison is NOT used here - that's
    only done during servo/polarizer calibration to find optimal positions.

    DETECTION METHOD:
    Analyze transmission spectrum (P/S ratio) for:
    - Peak shape (dip vs hill)
    - Peak depth (transmission reduction at SPR wavelength)
    - Peak width (FWHM characteristics)
    - Triangulation (peak vs edges comparison)

    For correct orientation:
    - Transmission shows a DIP (valley, minimum) due to SPR absorption
    - Peak value is LOWER than surrounding edge baselines
    - Dip depth indicates SPR coupling strength

    For inverted orientation (swapped S/P positions):
    - Transmission shows a PEAK (hill, maximum) instead of dip
    - Peak value is HIGHER than surrounding edge baselines
    - No SPR absorption visible (high transmission at resonance wavelength)

    Key insight: With weak SPR coupling (marginal water contact), the dip may be
    very shallow or barely visible. We need to distinguish between:
    - Shallow dip (correct orientation, weak coupling)
    - Actual peak/hill (inverted orientation)

    Method:
    1. Calculate transmission = P/S ratio
    2. Find local min/max in SPR region (600-750nm)
    3. Compare peak vs edge baselines
    4. Determine if structure is dip (correct) or peak (inverted)

    Args:
        p_spectrum: P-mode intensity spectrum
        s_spectrum: S-mode reference spectrum
        wavelengths: Wavelength array
        window_px: Number of pixels to sample on each side of peak (default 200)

    Returns:
        dict with:
            - 'orientation_correct': bool - True if dip detected (correct), False if peak (inverted)
            - 'peak_idx': int - Index of peak/dip
            - 'peak_wl': float - Wavelength of peak/dip
            - 'peak_value': float - Transmission value at peak
            - 'left_value': float - Mean transmission left of peak
            - 'right_value': float - Mean transmission right of peak
            - 'is_flat': bool - True if spectrum is flat (saturation or dark)
            - 'confidence': float - Confidence score (0-1) based on peak prominence

    """
    # Calculate transmission
    transmission = calculate_transmission(p_spectrum, s_spectrum)

    # Find peak (could be min or max depending on orientation)
    min_idx = np.argmin(transmission)
    max_idx = np.argmax(transmission)

    min_val = transmission[min_idx]

    # Determine which is more prominent
    spectrum_range = np.ptp(transmission)  # peak-to-peak amplitude

    # Check if flat (saturation or dark signal)
    is_flat = spectrum_range < 5.0  # Less than 5% variation = flat

    if is_flat:
        logger.warning(
            f"[WARN] S/P validation: Flat transmission spectrum (range={spectrum_range:.2f}%) - possible saturation or dark signal",
        )
        return {
            "orientation_correct": None,  # Cannot determine
            "peak_idx": min_idx,
            "peak_wl": wavelengths[min_idx],
            "peak_value": min_val,
            "left_value": 0,
            "right_value": 0,
            "is_flat": True,
            "confidence": 0.0,
        }

    # NEW APPROACH: Check for local structure in SPR region (600-750nm) first
    # This is more robust than global min/max for weak coupling cases
    spr_region_start = np.searchsorted(wavelengths, 600)
    spr_region_end = np.searchsorted(wavelengths, 750)

    # Initialize edge values (will be overwritten if SPR region is valid)
    left_edge_mean = transmission[0] if len(transmission) > 0 else 0
    right_edge_mean = transmission[-1] if len(transmission) > 0 else 0

    # Initialize confidence (will be calculated based on structure prominence)
    confidence = 0.5  # Default moderate confidence

    if spr_region_end > spr_region_start:
        spr_transmission = transmission[spr_region_start:spr_region_end]
        spr_wavelengths = wavelengths[spr_region_start:spr_region_end]

        # Find local minimum in SPR region
        local_min_idx = np.argmin(spr_transmission)
        local_max_idx = np.argmax(spr_transmission)

        local_min_val = spr_transmission[local_min_idx]
        local_max_val = spr_transmission[local_max_idx]

        # Check structure: compare center vs edges of SPR region
        edge_width = min(50, len(spr_transmission) // 4)
        left_edge_mean = np.mean(spr_transmission[:edge_width])
        right_edge_mean = np.mean(spr_transmission[-edge_width:])
        edge_mean = (left_edge_mean + right_edge_mean) / 2

        # Calculate how much the min and max differ from edges
        min_deviation = local_min_val - edge_mean
        max_deviation = local_max_val - edge_mean

        logger.debug("   S/P validation in 600-750nm region:")
        logger.debug(
            f"     Min at {spr_wavelengths[local_min_idx]:.1f}nm: {local_min_val:.1f}% (deviation: {min_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Max at {spr_wavelengths[local_max_idx]:.1f}nm: {local_max_val:.1f}% (deviation: {max_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Edges: left={left_edge_mean:.1f}%, right={right_edge_mean:.1f}%",
        )

        # Decision logic:
        # - If min is BELOW edges: correct orientation (has a dip)
        # - If max is ABOVE edges MORE than min is below: inverted (has a peak instead)
        # - Allow some tolerance for weak coupling (±5% is acceptable noise)

        if min_deviation < -5:  # Clear dip present
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                1.0,
                abs(min_deviation) / 30.0,
            )  # Scale: 30% deviation = 100% confidence
            logger.debug(
                f"   ✓ SPR DIP detected: {min_deviation:.1f}% below edges - CORRECT orientation",
            )
        elif max_deviation > 10:  # Clear peak present (inverted)
            orientation_correct = False
            peak_idx = spr_region_start + local_max_idx
            peak_val = local_max_val
            confidence = min(1.0, max_deviation / 30.0)
            logger.debug(
                f"   ✗ SPR PEAK detected: {max_deviation:+.1f}% above edges - INVERTED orientation",
            )
        elif abs(min_deviation) > abs(
            max_deviation,
        ):  # Subtle dip more prominent than peak
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                0.7,
                abs(min_deviation) / 30.0,
            )  # Lower confidence for weak signal
            logger.debug(
                f"   ✓ Subtle SPR dip detected (weak coupling): {min_deviation:.1f}% - CORRECT orientation",
            )
        else:  # Weak structure, cannot reliably determine orientation
            logger.warning(
                "   [WARN] Weak SPR structure in 600-750nm - cannot determine orientation",
            )
            # Return None (indeterminate) rather than guessing
            orientation_correct = None  # Cannot determine with confidence
            peak_idx = min_idx
            peak_val = min_val
            confidence = 0.1  # Very low confidence for indeterminate
    else:
        # No valid SPR region - cannot determine orientation
        logger.warning("   [WARN] Invalid wavelength range for SPR analysis")
        orientation_correct = None  # Cannot determine without valid SPR region
        peak_idx = min_idx
        peak_val = min_val
        confidence = 0.0  # Zero confidence for invalid range

    return {
        "orientation_correct": orientation_correct,
        "peak_idx": peak_idx,
        "peak_wl": wavelengths[peak_idx],
        "peak_value": peak_val,
        "left_value": left_edge_mean,
        "right_value": right_edge_mean,
        "is_flat": False,
        "confidence": confidence,
    }


def auto_detect_injection_point(
    times: np.ndarray,
    values: np.ndarray,
    smoothing_window: int = 11,
    baseline_points: int = 5,
    min_rise_threshold: float = 2.0,
    sensitivity_factor: float = 1.0,
) -> dict:
    """Automatically detect injection point in SPR sensorgram data.

    Finds where the signal FIRST breaks from baseline trend (injection start point).
    Handles both upward shifts (binding events) and downward shifts.

    Algorithm:
    1. Fit linear trend to baseline (first N points)
    2. Calculate deviation from baseline trend for each point
    3. Find sustained deviation crossing (signal breaks trend)
    4. This gives injection START, not steepest slope
    5. Return injection time and confidence score

    Args:
        times: Time array (seconds)
        values: SPR signal array (RU or raw units)
        smoothing_window: Savitzky-Golay window for slope smoothing (default: 11, must be odd)
        baseline_points: Number of initial points to use for baseline mean (default: 50)
        min_rise_threshold: Minimum absolute signal change (RU) to confirm injection (default: 2.0)
        sensitivity_factor: Scales detection sensitivity. <1.0 = more sensitive
            (lower thresholds, fewer sustain points needed), >1.0 = less sensitive.
            Used by method mode: manual→0.6, semi-automated→1.0, priority→0.5.

    Returns:
        dict: {
            'injection_time': float - Detected injection time (seconds), or None if not found
            'injection_index': int - Array index of injection point, or None
            'confidence': float - Detection confidence 0-1 (1=high confidence)
            'max_slope': float - Maximum slope value at injection (RU/s, signed)
            'signal_rise': float - Total signal change after injection (RU, signed)
            'snr': float - Signal-to-noise ratio (absolute)
            'baseline_noise': float - Baseline noise level (RU std dev)
        }

    Example:
        >>> times = np.linspace(0, 300, 1000)
        >>> values = np.concatenate([np.zeros(400), np.linspace(0, 50, 600)])  # Step at t=120s
        >>> result = auto_detect_injection_point(times, values)
        >>> print(f"Injection at {result['injection_time']:.1f}s, confidence: {result['confidence']:.2f}")
    """
    try:
        if len(times) < 10 or len(values) < 10:
            return {
                'injection_time': None,
                'injection_index': None,
                'confidence': 0.0,
                'max_slope': 0.0,
                'signal_rise': 0.0,
                'snr': 0.0,
                'baseline_noise': 0.0,
            }

        # Calculate baseline statistics (from first N points)
        baseline_end = min(baseline_points, int(len(values) * 0.33))  # Use up to 33% of data for baseline
        if baseline_end < 10:
            baseline_end = min(10, len(values) // 2)

        baseline_values = values[:baseline_end]
        baseline_mean = np.mean(baseline_values)
        baseline_noise = np.std(baseline_values)
        baseline_noise = max(baseline_noise, 0.1)  # Minimum noise floor

        # Fit linear trend to baseline to account for drift
        baseline_times = times[:baseline_end]
        try:
            baseline_coeffs = np.polyfit(baseline_times, baseline_values, 1)
            baseline_trend = np.poly1d(baseline_coeffs)
            baseline_slope = baseline_coeffs[0]  # Drift rate
        except Exception:
            baseline_trend = lambda t: baseline_mean
            baseline_slope = 0.0

        # Calculate expected trend for all times
        expected_trend = baseline_trend(times)

        # Calculate deviation from baseline trend for each point
        deviation = values - expected_trend
        abs_deviation = np.abs(deviation)

        # Threshold for "breaking from baseline" = 2.5 standard deviations
        # This is more sensitive than the original 3.0 threshold
        # sensitivity_factor scales: <1.0 lowers threshold (more sensitive), >1.0 raises it
        threshold = 2.5 * baseline_noise * sensitivity_factor

        # Scale min_rise_threshold by sensitivity_factor too
        effective_rise_threshold = min_rise_threshold * sensitivity_factor

        # Find FIRST point where signal deviates from baseline AND is sustained
        injection_idx = None
        # Fewer sustain points needed when sensitivity_factor < 1.0
        base_sustain = min(5, max(2, len(values) // 50))
        sustain_window = max(2, int(base_sustain * sensitivity_factor))

        for i in range(baseline_end, len(values) - sustain_window):
            # Check if deviation exceeds threshold at this point
            if abs_deviation[i] > threshold:
                # Verify sustained deviation over next few points (signal doesn't drop back)
                next_deviations = abs_deviation[i:i + sustain_window]
                if np.mean(next_deviations) > threshold * 0.8:  # Allow some wiggle
                    injection_idx = i
                    logger.debug(
                        f"Auto-detect: Found injection breakpoint at index {i}, "
                        f"deviation {abs_deviation[i]:.2f} RU (threshold {threshold:.2f})"
                    )
                    break

        # Fallback: If no sustained crossing found, use highest deviation point
        if injection_idx is None:
            candidate_idx = np.argmax(abs_deviation[baseline_end:]) + baseline_end
            if abs_deviation[candidate_idx] > threshold * 0.5:  # At least 50% of threshold
                injection_idx = candidate_idx
                logger.debug(
                    f"Auto-detect: Using highest deviation fallback at index {injection_idx}, "
                    f"deviation {abs_deviation[candidate_idx]:.2f} RU"
                )

        if injection_idx is None:
            return {
                'injection_time': None,
                'injection_index': None,
                'confidence': 0.0,
                'max_slope': 0.0,
                'signal_rise': 0.0,
                'snr': 0.0,
                'baseline_noise': float(baseline_noise),
            }

        injection_time = times[injection_idx]

        # Calculate slope at injection point for reporting
        # np.gradient uses centered diff for interior points, forward/backward at edges
        max_slope_value = float(np.gradient(values, times)[injection_idx])

        # Determine injection direction
        injection_direction = 1 if max_slope_value >= 0 else -1

        # Signal change after injection
        post_injection_values = values[injection_idx:]
        if len(post_injection_values) > 5:
            if injection_direction > 0:
                signal_extreme = np.max(post_injection_values)
            else:
                signal_extreme = np.min(post_injection_values)
            signal_rise = signal_extreme - baseline_mean
        else:
            signal_rise = deviation[injection_idx]

        # Signal-to-noise ratio
        abs_signal_rise = abs(signal_rise)
        snr = abs_signal_rise / baseline_noise

        # Calculate confidence score
        # Primary: Deviation from baseline (should be >2.5 sigma)
        deviation_confidence = min(abs_deviation[injection_idx] / threshold, 1.0)

        # Secondary: Signal sustains after injection (no drop-off)
        if len(post_injection_values) > 5:
            post_mean_deviation = np.mean(abs_deviation[injection_idx:injection_idx+10])
            sustain_confidence = min(post_mean_deviation / threshold, 1.0)
        else:
            sustain_confidence = 0.7

        # Penalize edge detections
        edge_margin = int(len(times) * 0.05)
        if injection_idx < edge_margin or injection_idx > len(times) - edge_margin:
            edge_confidence = 0.3
        else:
            edge_confidence = 1.0

        # Weighted confidence: Deviation + sustain + edge position
        confidence = (deviation_confidence * 0.5 + sustain_confidence * 0.3 + edge_confidence * 0.2)

        # Penalize if signal change is weak
        if abs_signal_rise < effective_rise_threshold:
            confidence *= 0.5

        direction_label = "rise" if injection_direction > 0 else "fall"
        logger.debug(
            f"Auto-detected injection at t={injection_time:.2f}s "
            f"({direction_label}, deviation: {abs_deviation[injection_idx]:.2f} RU, "
            f"SNR: {snr:.1f}, change: {signal_rise:.1f} RU, conf: {confidence:.2%})"
        )

        return {
            'injection_time': float(injection_time),
            'injection_index': int(injection_idx),
            'confidence': float(confidence),
            'max_slope': float(max_slope_value),
            'signal_rise': float(signal_rise),
            'snr': float(snr),
            'baseline_noise': float(baseline_noise),
        }

    except Exception as e:
        logger.debug(f"Auto-detection failed: {e}")
        return {
            'injection_time': None,
            'injection_index': None,
            'confidence': 0.0,
            'max_slope': 0.0,
            'signal_rise': 0.0,
            'snr': 0.0,
            'baseline_noise': 0.0,
        }


def measure_delta_spr(
    times: np.ndarray,
    spr_values: np.ndarray,
    injection_time: float,
    contact_time: float,
    avg_points: int = 3,
    pre_offset: float = 10.0,
) -> dict:
    """Measure delta SPR between pre-injection baseline and contact time endpoint.

    Computes the SPR shift caused by analyte binding during the contact phase.
    Uses N-point averaging at both measurement points for noise reduction.

    Measurement points:
      - START: avg_points centered at (injection_time - pre_offset)
      - END:   avg_points centered at (injection_time + contact_time)

    Args:
        times: Time array in seconds (RAW_ELAPSED coordinates)
        spr_values: SPR signal array in RU (resonance units)
        injection_time: Detected injection time in seconds (RAW_ELAPSED)
        contact_time: Contact duration in seconds
        avg_points: Number of points to average at each measurement site (default: 3)
        pre_offset: Seconds before injection to measure baseline (default: 10.0)

    Returns:
        dict: {
            'delta_spr': float or None - SPR shift in RU (end - start), None if measurement failed
            'start_spr': float - Averaged SPR at pre-injection point (RU)
            'end_spr': float - Averaged SPR at contact time endpoint (RU)
            'start_time': float - Actual time of start measurement
            'end_time': float - Actual time of end measurement
            'start_indices': list[int] - Indices used for start average
            'end_indices': list[int] - Indices used for end average
            'quality': str - 'good', 'extrapolated', or 'failed'
        }

    Example:
        >>> result = measure_delta_spr(time_array, spr_array,
        ...                            injection_time=120.0, contact_time=300.0)
        >>> print(f"Delta SPR: {result['delta_spr']:.2f} RU")
    """
    result = {
        'delta_spr': None,
        'start_spr': 0.0,
        'end_spr': 0.0,
        'start_time': 0.0,
        'end_time': 0.0,
        'start_indices': [],
        'end_indices': [],
        'quality': 'failed',
    }

    try:
        if len(times) < avg_points or len(spr_values) < avg_points:
            logger.warning("Insufficient data for delta SPR measurement")
            return result

        def _avg_at(target: float) -> tuple[int, int, float, float]:
            """Return (lo, hi, spr_mean, actual_time) for a centered avg_points window."""
            center = int(np.argmin(np.abs(times - target)))
            half = avg_points // 2
            lo = max(0, center - half)
            hi = min(len(spr_values), lo + avg_points)
            lo = max(0, hi - avg_points)  # re-clamp if near end
            return lo, hi, float(np.mean(spr_values[lo:hi])), float(times[center])

        # --- Start measurement: injection_time - pre_offset ---
        start_lo, start_hi, start_spr, start_time = _avg_at(injection_time - pre_offset)
        start_indices = list(range(start_lo, start_hi))

        # --- End measurement: injection_time + contact_time ---
        end_lo, end_hi, end_spr, end_time = _avg_at(injection_time + contact_time)
        end_indices = list(range(end_lo, end_hi))

        # Quality check: how close are actual times to targets?
        start_gap = abs(start_time - start_target)
        end_gap = abs(end_time - end_target)
        # Allow up to 2 seconds of gap (data rate ~4 Hz → 0.25s spacing typical)
        if start_gap > 2.0 or end_gap > 2.0:
            quality = 'extrapolated'
            logger.debug(
                f"Delta SPR measurement gaps: start={start_gap:.1f}s, end={end_gap:.1f}s"
            )
        else:
            quality = 'good'

        delta = end_spr - start_spr

        result.update({
            'delta_spr': float(delta),
            'start_spr': start_spr,
            'end_spr': end_spr,
            'start_time': start_time,
            'end_time': end_time,
            'start_indices': start_indices,
            'end_indices': end_indices,
            'quality': quality,
        })

        logger.debug(
            f"Delta SPR measured: {delta:.2f} RU "
            f"(start={start_spr:.2f} @ t={start_time:.1f}s, "
            f"end={end_spr:.2f} @ t={end_time:.1f}s, quality={quality})"
        )

    except Exception as e:
        logger.warning(f"Delta SPR measurement failed: {e}")

    return result


def detect_injection_all_channels(
    timeline_data: dict,
    window_start_time: float,
    window_end_time: float,
    min_confidence: float = 0.70,
) -> dict:
    """Detect injection points on ALL channels within a time window.

    Runs auto_detect_injection_point on each channel independently.
    Returns per-channel injection times and confidences.

    Args:
        timeline_data: Dict of channel → ChannelBuffer (from buffer_mgr.timeline_data)
        window_start_time: Start of detection window (RAW_ELAPSED seconds)
        window_end_time: End of detection window (RAW_ELAPSED seconds)
        min_confidence: Minimum confidence threshold (default: 0.30)

    Returns:
        dict: {
            'times': {'A': 123.5, 'B': 124.1, ...}  - injection times per channel (only detected)
            'confidences': {'A': 0.85, 'B': 0.72, ...}  - confidence per channel
            'all_results': {'A': {...}, 'B': {...}, ...}  - full detection results per channel
        }
    """
    detected_times = {}
    detected_confidences = {}
    all_results = {}

    for ch in ['a', 'b', 'c', 'd']:
        if ch not in timeline_data:
            continue

        channel_data = timeline_data[ch]
        if not channel_data or len(channel_data.time) < 10:
            continue

        times = np.array(channel_data.time)
        wavelengths = np.array(channel_data.wavelength)

        if len(times) < 10 or len(wavelengths) < 10:
            continue

        # Mask to detection window
        window_mask = (times >= window_start_time) & (times <= window_end_time)
        window_times = times[window_mask]
        window_wl = wavelengths[window_mask]

        if len(window_times) < 10:
            continue

        # Convert wavelength to RU for detection
        baseline = window_wl[0] if len(window_wl) > 0 else 0
        window_ru = (window_wl - baseline) * 355.0

        result = auto_detect_injection_point(window_times, window_ru)
        all_results[ch.upper()] = result

        if result['injection_time'] is not None and result['confidence'] >= min_confidence:
            detected_times[ch.upper()] = result['injection_time']
            detected_confidences[ch.upper()] = result['confidence']
            logger.debug(
                f"Channel {ch.upper()}: injection at {result['injection_time']:.2f}s "
                f"(confidence: {result['confidence']:.0%})"
            )
        else:
            conf = result.get('confidence', 0)
            logger.debug(f"Channel {ch.upper()}: no injection detected (confidence: {conf:.0%})")

    return {
        'times': detected_times,
        'confidences': detected_confidences,
        'all_results': all_results,
    }
