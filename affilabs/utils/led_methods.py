"""LED Calibration Methods - Clean Modular Implementation.

This module provides LED calibration strategies:
1. LEDconverge: Model-aware convergence with zero saturation tolerance
2. LEDnormalizationintensity: Brightness-based LED normalization
3. LEDnormalizationtime: Per-channel integration time calculation

Architecture:
- led_convergence_core.py: Primitives (measurement, adjustment, boundaries)
- led_convergence_algorithm.py: Main convergence loop (LEDconverge)
- This file: Supporting functions + backward compatibility
"""

# Import clean implementations
from .led_convergence_algorithm import LEDconverge
from .led_convergence_core import (
    DetectorParams,
    analyze_saturation_severity,
    count_saturated_pixels,
)

# Re-export for backward compatibility
__all__ = [
    "DetectorParams",
    "count_saturated_pixels",
    "analyze_saturation_severity",
    "calculate_led_reduction_from_saturation",
    "LEDconverge",
    "LEDnormalizationintensity",
    "LEDnormalizationtime",
]


# =============================================================================
# LED SATURATION RECOVERY (Legacy function for compatibility)
# =============================================================================


def calculate_led_reduction_from_saturation(
    current_led: int,
    current_integration_ms: float,
    saturation_analysis: dict,
    model_slope: float,
    detector_params: DetectorParams,
    target_percent: float = 0.80,
    polarization: str = "S",
    logger=None,
) -> tuple[int, str]:
    """Legacy wrapper - prefer using led_convergence_core functions directly."""
    sat_fraction = saturation_analysis["sat_fraction"]
    max_width = saturation_analysis["max_contiguous_width"]
    severity = saturation_analysis["severity_score"]

    target_counts = target_percent * detector_params.max_counts

    # Estimate true signal from saturation severity
    measured_signal = detector_params.saturation_threshold
    estimated_loss_factor = 1.0 + (sat_fraction * 0.7)
    true_signal_estimate = measured_signal * estimated_loss_factor

    # Calculate LED for target using model slope
    if model_slope > 0:
        led_for_target = target_counts / model_slope
    else:
        led_for_target = current_led * 0.75

    # Apply safety margins
    if polarization.upper() == "S":
        if severity > 50:
            safety_factor = 0.80
            reason = "S-pol HIGH severity → aggressive reduction"
        elif severity > 20:
            safety_factor = 0.85
            reason = "S-pol MEDIUM severity → moderate reduction"
        else:
            safety_factor = 0.90
            reason = "S-pol LOW severity → minor reduction"
    elif severity > 50:
        safety_factor = 0.90
        reason = "P-pol HIGH severity → moderate reduction"
    else:
        safety_factor = 0.95
        reason = "P-pol severity → minor reduction"

    new_led = int(led_for_target * safety_factor)
    new_led = max(10, min(255, new_led))

    # Enforce minimum reduction
    reduction = current_led - new_led
    if reduction < 15 and severity > 20:
        new_led = max(10, current_led - 15)
        reason += " (enforced min 15-point reduction)"

    if logger:
        logger.info(
            f"[SAT-RECOVERY] {saturation_analysis['sat_pixels']} px ({sat_fraction:.1%}), width={max_width}, severity={severity:.1f}",
        )
        logger.info(
            f"[SAT-RECOVERY] LED {current_led} → {new_led} (Δ={reduction}): {reason}",
        )

    return new_led, reason


# =============================================================================
# LED NORMALIZATION - INTENSITY STRATEGY
# =============================================================================


def LEDnormalizationintensity(
    channel_measurements: dict[str, tuple[float, float]],
    weakest_mean: float,
    min_led: int = 10,
    max_led: int = 255,
) -> dict[str, int]:
    """Normalize LED intensities based on brightness ratios.

    Weakest channel (lowest signal) gets max LED (255).
    Stronger channels scaled proportionally.

    Args:
        channel_measurements: {channel: (mean_signal, max_signal)}
        weakest_mean: Signal from weakest channel (reference)

    Returns:
        {channel: normalized_led_intensity}

    """
    normalized_leds: dict[str, int] = {}

    for ch, (mean_val, _max_val) in channel_measurements.items():
        brightness_ratio = mean_val / weakest_mean if weakest_mean > 0 else 1.0
        led_val = int(max_led / brightness_ratio)
        led_val = max(min_led, min(max_led, led_val))
        normalized_leds[ch] = led_val

    return normalized_leds


# =============================================================================
# LED NORMALIZATION - TIME STRATEGY
# =============================================================================


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
    use_batch_command: bool = True,
) -> dict[str, float]:
    """Calculate per-channel integration times at LED=255.

    Strategy:
    1. Fix LED=255 for all channels
    2. Measure signal at seed integration time
    3. Calculate T_target = T_seed × (target/signal)
    4. Verify and adjust within tolerance

    Returns:
        {channel: integration_time_ms}

    """
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    min_sig = (target_percent - tolerance_percent) * detector_max
    max_sig = (target_percent + tolerance_percent) * detector_max

    per_channel_times: dict[str, float] = {}

    # Seed time: mid-range, avoid saturation
    seed_time = max(
        detector_params.min_integration_time,
        min(detector_params.max_integration_time, 35.0),
    )

    for ch in ch_list:
        # Measure at seed time
        spec_seed = acquire_raw_spectrum_fn(
            usb,
            ctrl,
            ch,
            255,
            seed_time,
            1,
            45.0,
            5.0,
            use_batch_command,
        )

        if spec_seed is None:
            if logger:
                logger.error(f"[TIME-NORM] {ch.upper()} seed measurement failed")
            per_channel_times[ch] = seed_time
            continue

        sig_seed = roi_signal_fn(
            spec_seed,
            wave_min_index,
            wave_max_index,
            method="median",
            top_n=50,
        )

        if sig_seed <= 0:
            per_channel_times[ch] = seed_time
            if logger:
                logger.warning(f"[TIME-NORM] {ch.upper()} zero signal @ seed time")
            continue

        # Calculate target integration time
        t_target = seed_time * (target / sig_seed)
        t_target = max(
            detector_params.min_integration_time,
            min(detector_params.max_integration_time, t_target),
        )

        # Verify at target time
        spec_verify = acquire_raw_spectrum_fn(
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

        if spec_verify is not None:
            sig_verify = roi_signal_fn(
                spec_verify,
                wave_min_index,
                wave_max_index,
                method="median",
                top_n=50,
            )
            sat_verify = count_saturated_pixels(
                spec_verify,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
            )

            # Saturation handling
            if sat_verify > 0:
                if logger:
                    logger.warning(
                        f"[TIME-NORM] {ch.upper()} saturated @ {t_target:.1f}ms - reducing time",
                    )
                t_target *= 0.90
                t_target = max(detector_params.min_integration_time, t_target)

            # Tolerance adjustment
            elif not (min_sig <= sig_verify <= max_sig):
                adj = max(
                    0.90,
                    min(1.10, (target / sig_verify) if sig_verify > 0 else 1.0),
                )
                t_target *= adj
                t_target = max(
                    detector_params.min_integration_time,
                    min(detector_params.max_integration_time, t_target),
                )

        per_channel_times[ch] = float(t_target)

        if logger:
            pct = (
                (sig_verify if "sig_verify" in locals() else sig_seed)
                / detector_max
                * 100.0
            )
            logger.info(
                f"[TIME-NORM] {ch.upper()}: T={t_target:.1f}ms → {pct:.1f}% signal",
            )

    # Optional final tightening pass
    if tighten_final:
        if logger:
            logger.info("[TIME-NORM] Tightening pass...")

        for ch in ch_list:
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

            if spec_final is None:
                continue

            sig_final = roi_signal_fn(
                spec_final,
                wave_min_index,
                wave_max_index,
                method="median",
                top_n=50,
            )

            if not (min_sig <= sig_final <= max_sig) and sig_final > 0:
                adj = max(0.95, min(1.05, target / sig_final))
                per_channel_times[ch] *= adj
                per_channel_times[ch] = max(
                    detector_params.min_integration_time,
                    min(detector_params.max_integration_time, per_channel_times[ch]),
                )
                if logger:
                    logger.info(
                        f"[TIME-NORM] {ch.upper()} tightened: T={per_channel_times[ch]:.1f}ms",
                    )

    return per_channel_times
