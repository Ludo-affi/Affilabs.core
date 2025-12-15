"""Core LED convergence engine.

Clean, focused implementation of LED intensity calibration using model-aware adjustments.
Separated concerns: measurement, adjustment, saturation handling, convergence logic.
"""

import numpy as np


class ConvergenceConfig:
    """Configuration constants for LED convergence algorithm."""

    # LED intensity limits
    MIN_LED = 10
    MAX_LED = 255

    # Saturation severity thresholds
    SEVERE_SAT_WIDTH = 20  # Contiguous saturated pixels for "severe"
    SEVERE_SAT_SEVERITY = 10.0  # Severity score for aggressive reduction
    MODERATE_SAT_WIDTH = 10
    MODERATE_SAT_SEVERITY = 5.0

    # LED adjustment limits
    LED_DELTA_NEAR_TARGET = 3  # Max LED change when within 10% of target
    LED_DELTA_FAR_TARGET = 50  # Max LED change when far from target
    NEAR_TARGET_PERCENT = 10.0  # Threshold for "near target"

    # Saturation recovery reduction factors
    SEVERE_REDUCTION = 0.60  # 40% reduction for severe saturation
    MODERATE_REDUCTION = 0.70  # 30% reduction for moderate saturation
    MILD_REDUCTION = 0.80  # 20% reduction for mild saturation
    FALLBACK_REDUCTION = 0.75  # 25% reduction when no model/spectrum

    # Ratio-based adjustment bounds
    RATIO_FAR_MIN = 0.5
    RATIO_FAR_MAX = 2.0
    RATIO_MID_MIN = 0.6
    RATIO_MID_MAX = 1.6
    RATIO_NEAR_MIN = 0.75
    RATIO_NEAR_MAX = 1.30

    # Distance thresholds for ratio bounds (fraction of target)
    DISTANCE_FAR = 0.5
    DISTANCE_MID = 0.75

    # Integration time boost
    MIN_TIME_BOOST = 1.15  # Minimum boost to overcome noise
    MAX_TIME_BOOST = 2.0  # Maximum safe boost
    BOOST_SIGNAL_THRESHOLD = 0.95  # Must be below this to trigger boost
    BOOST_MIN_SIGNAL = 0.50  # Must be above this (hardware check)
    STUCK_LED_THRESHOLD = 200  # LED value to consider "stuck"
    STUCK_SIGNAL_THRESHOLD = 0.90  # Signal threshold for stuck detection
    STUCK_ITERATION_MIN = 3  # Iterations before checking stuck

    # Convergence acceptance thresholds
    HARDWARE_LIMIT_THRESHOLD = 0.80  # Accept if ≥80% and at integration limit
    HARDWARE_LIMIT_FRACTION = 0.75  # Consider "at limit" at 75% of max
    RELAXED_TOLERANCE = 0.10  # ±10% for relaxed acceptance


class DetectorParams:
    """Detector hardware specifications."""

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


class ConvergenceState:
    """Tracks convergence progress and boundary conditions."""

    def __init__(self):
        # Saturation boundaries: LED intensities that caused saturation (never exceed)
        self.max_saturating_intensity: dict[str, int] = {}

        # Undershoot boundaries: LED intensities that were too dim (never go below)
        self.min_undershooting_intensity: dict[str, int] = {}

        # Integration time boost tracking (prevent repeated boosts)
        self.time_boosted_channels: set[str] = set()

    def record_saturation(self, channel: str, led_intensity: int, logger=None):
        """Record LED intensity that caused saturation."""
        if (
            channel not in self.max_saturating_intensity
            or led_intensity < self.max_saturating_intensity[channel]
        ):
            self.max_saturating_intensity[channel] = led_intensity
            if logger:
                logger.info(
                    f"  ⚠️ {channel.upper()} saturated @ LED={led_intensity} - boundary recorded",
                )

    def record_undershoot(
        self,
        channel: str,
        led_intensity: int,
        signal: float,
        target: float,
        logger=None,
    ):
        """Record LED intensity that undershot target."""
        if (
            channel not in self.min_undershooting_intensity
            or led_intensity > self.min_undershooting_intensity[channel]
        ):
            self.min_undershooting_intensity[channel] = led_intensity
            if logger:
                logger.info(
                    f"  📉 {channel.upper()} undershot @ LED={led_intensity} ({signal/target*100:.1f}% of target) - boundary recorded",
                )

    def enforce_boundaries(self, channel: str, proposed_led: int, logger=None) -> int:
        """Apply boundary constraints to proposed LED adjustment."""
        original = proposed_led

        # Upper boundary: Never exceed saturation point
        if (
            channel in self.max_saturating_intensity
            and proposed_led >= self.max_saturating_intensity[channel]
        ):
            proposed_led = max(10, self.max_saturating_intensity[channel] - 5)
            if logger:
                logger.info(
                    f"  🔒 {channel.upper()} capped {original} → {proposed_led} (saturation boundary)",
                )

        # Lower boundary: Never go below undershoot point
        if (
            channel in self.min_undershooting_intensity
            and proposed_led <= self.min_undershooting_intensity[channel]
        ):
            proposed_led = min(255, self.min_undershooting_intensity[channel] + 5)
            if logger:
                logger.info(
                    f"  🔒 {channel.upper()} floored {original} → {proposed_led} (undershoot boundary)",
                )

        return proposed_led


# =============================================================================
# SATURATION ANALYSIS
# =============================================================================


def count_saturated_pixels(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
) -> int:
    """Count saturated pixels in ROI."""
    roi = spectrum[wave_min_index:wave_max_index]
    return int(np.sum(roi >= saturation_threshold))


def analyze_saturation_severity(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float = 65535,
) -> dict:
    """Analyze saturation: count + contiguous width."""
    roi = spectrum[wave_min_index:wave_max_index]
    saturated_mask = roi >= saturation_threshold

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

    if in_block:
        sat_blocks.append(len(saturated_mask) - block_start)

    max_width = max(sat_blocks) if sat_blocks else 0
    num_regions = len(sat_blocks)
    severity_score = max_width * sat_fraction

    return {
        "sat_pixels": sat_count,
        "sat_fraction": sat_fraction,
        "max_contiguous_width": max_width,
        "num_sat_regions": num_regions,
        "severity_score": severity_score,
    }


# =============================================================================
# LED ADJUSTMENT LOGIC
# =============================================================================


def calculate_model_aware_led_adjustment(
    channel: str,
    current_led: int,
    current_signal: float,
    target_signal: float,
    model_slope_at_current_integration: float,
    config: ConvergenceConfig,
    logger=None,
) -> int:
    """Calculate precise LED adjustment using model sensitivity.

    Args:
        model_slope_at_current_integration: counts per LED unit at current integration time
        config: ConvergenceConfig instance with algorithm parameters

    Returns:
        New LED intensity (10-255)

    """
    signal_error = target_signal - current_signal
    signal_error_percent = (signal_error / target_signal) * 100.0

    # Calculate LED delta: signal_error / slope
    if abs(model_slope_at_current_integration) < 0.1:
        if logger:
            logger.warning(
                f"  ⚠️ {channel.upper()} slope too small ({model_slope_at_current_integration:.3f}), using ratio fallback",
            )
        return calculate_ratio_based_led_adjustment(
            channel,
            current_led,
            current_signal,
            target_signal,
            config,
            logger,
        )

    led_delta = signal_error / model_slope_at_current_integration

    # Safety limits: smaller when close to target, larger when far
    if abs(signal_error_percent) < config.NEAR_TARGET_PERCENT:
        led_delta = max(
            -config.LED_DELTA_NEAR_TARGET,
            min(config.LED_DELTA_NEAR_TARGET, led_delta),
        )
    else:
        led_delta = max(
            -config.LED_DELTA_FAR_TARGET,
            min(config.LED_DELTA_FAR_TARGET, led_delta),
        )

    new_led = int(max(config.MIN_LED, min(config.MAX_LED, current_led + led_delta)))

    if logger:
        logger.info(
            f"  🎯 MODEL-AWARE {channel.upper()} LED {current_led} → {new_led} "
            f"(error={signal_error_percent:+.1f}%, slope={model_slope_at_current_integration:.1f}, delta={led_delta:+.1f})",
        )

    return new_led


def calculate_ratio_based_led_adjustment(
    channel: str,
    current_led: int,
    current_signal: float,
    target_signal: float,
    config: ConvergenceConfig,
    logger=None,
) -> int:
    """Fallback LED adjustment using signal ratio."""
    if current_signal <= 0:
        ratio = 1.5
    else:
        ratio = target_signal / current_signal

    # Dynamic bounds based on distance from target
    if current_signal < target_signal * config.DISTANCE_FAR:
        ratio = max(config.RATIO_FAR_MIN, min(config.RATIO_FAR_MAX, ratio))
    elif current_signal < target_signal * config.DISTANCE_MID:
        ratio = max(config.RATIO_MID_MIN, min(config.RATIO_MID_MAX, ratio))
    else:
        ratio = max(config.RATIO_NEAR_MIN, min(config.RATIO_NEAR_MAX, ratio))

    new_led = int(max(config.MIN_LED, min(config.MAX_LED, current_led * ratio)))

    if logger:
        logger.info(
            f"  📊 RATIO-BASED {channel.upper()} LED {current_led} → {new_led} (ratio={ratio:.2f})",
        )

    return new_led


def calculate_saturation_recovery(
    channel: str,
    current_led: int,
    saturation_analysis: dict,
    model_slope: float,
    target_signal: float,
    detector_max: float,
    config: ConvergenceConfig,
    logger=None,
) -> int:
    """Calculate LED reduction to clear saturation using model slope."""
    severity = saturation_analysis["severity_score"]
    sat_pixels = saturation_analysis["sat_pixels"]
    max_width = saturation_analysis["max_contiguous_width"]

    # Aggressive reduction for severe saturation
    if severity > config.SEVERE_SAT_SEVERITY or max_width > config.SEVERE_SAT_WIDTH:
        reduction_factor = config.SEVERE_REDUCTION
    elif (
        severity > config.MODERATE_SAT_SEVERITY or max_width > config.MODERATE_SAT_WIDTH
    ):
        reduction_factor = config.MODERATE_REDUCTION
    else:
        reduction_factor = config.MILD_REDUCTION

    # Model-based refinement: estimate LED needed for target
    if abs(model_slope) > 0.1:
        led_for_target = target_signal / model_slope
        led_for_target = max(config.MIN_LED, min(current_led * 0.95, led_for_target))

        # Blend model estimate with safety reduction
        new_led = int((led_for_target * 0.7) + (current_led * reduction_factor * 0.3))
    else:
        new_led = int(current_led * reduction_factor)

    new_led = max(config.MIN_LED, min(config.MAX_LED, new_led))

    if logger:
        logger.info(
            f"  🚨 SATURATION-RECOVERY {channel.upper()} LED {current_led} → {new_led} "
            f"(sat_px={sat_pixels}, width={max_width}, severity={severity:.1f})",
        )

    return new_led


# =============================================================================
# CHANNEL MEASUREMENT
# =============================================================================


def measure_channel(
    usb,
    ctrl,
    channel: str,
    led_intensity: int,
    integration_ms: float,
    acquire_spectrum_fn,
    roi_signal_fn,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
    use_batch: bool,
) -> tuple[float | None, int, dict | None, object | None]:
    """Measure single channel: signal + saturation analysis + cached spectrum.

    Returns:
        (signal_counts, saturated_pixels, saturation_analysis_dict, spectrum)
        saturation_analysis_dict is None if no saturation detected
        Returns (None, 0, None, None) on measurement failure

    """
    spec = acquire_spectrum_fn(
        usb=usb,
        ctrl=ctrl,
        channel=channel,
        led_intensity=led_intensity,
        integration_time_ms=integration_ms,
        num_scans=1,
        pre_led_delay_ms=45.0,
        post_led_delay_ms=5.0,
        use_batch_command=use_batch,
    )

    if spec is None:
        return None, 0, None, None

    signal = roi_signal_fn(
        spec,
        wave_min_index,
        wave_max_index,
        method="median",
        top_n=50,
    )
    sat_pixels = count_saturated_pixels(
        spec,
        wave_min_index,
        wave_max_index,
        saturation_threshold,
    )

    # If saturated, perform severity analysis now (cache it for later use)
    sat_analysis = None
    if sat_pixels > 0:
        sat_analysis = analyze_saturation_severity(
            spec,
            wave_min_index,
            wave_max_index,
            saturation_threshold,
        )

    return signal, sat_pixels, sat_analysis, spec


# =============================================================================
# CONVERGENCE CHECKS
# =============================================================================


def check_convergence(
    signals: dict[str, float],
    sat_per_ch: dict[str, int],
    target: float,
    tolerance: float,
    detector_max: float,
) -> tuple[bool, str]:
    """Check if convergence achieved: all channels in tolerance + zero saturation.

    Returns:
        (converged, reason)

    """
    if not signals:
        return False, "no_signals"

    min_sig = (target - tolerance) * detector_max
    max_sig = (target + tolerance) * detector_max
    total_sat = sum(sat_per_ch.values())

    # Must satisfy BOTH conditions
    in_tolerance = all(min_sig <= signals[ch] <= max_sig for ch in signals)
    zero_saturation = total_sat == 0

    if in_tolerance and zero_saturation:
        return True, "converged"
    if in_tolerance and not zero_saturation:
        return False, f"in_tolerance_but_{total_sat}_saturated"
    if zero_saturation and not in_tolerance:
        return False, "zero_sat_but_outside_tolerance"
    return False, f"outside_tolerance_and_{total_sat}_saturated"


# =============================================================================
# INTEGRATION TIME ADJUSTMENT
# =============================================================================


def calculate_integration_time_boost(
    signals: dict[str, float],
    led_intensities: dict[str, int],
    target: float,
    current_integration: float,
    state: ConvergenceState,
    detector_params: DetectorParams,
    iteration: int,
    config: ConvergenceConfig,
    logger=None,
) -> tuple[float, set[str]]:
    """Determine if integration time boost needed for maxed/stuck channels.

    Returns:
        (new_integration_ms, channels_to_boost)

    """
    # Find channels that need integration boost
    maxed_channels = {
        ch
        for ch, led in led_intensities.items()
        if ch in signals
        and led >= config.MAX_LED
        and signals[ch] < target * config.BOOST_SIGNAL_THRESHOLD
        and signals[ch] >= target * config.BOOST_MIN_SIGNAL
    }

    # Also consider stuck channels (near max LED but not converging)
    if iteration >= config.STUCK_ITERATION_MIN:
        stuck_channels = {
            ch
            for ch, led in led_intensities.items()
            if ch in signals
            and signals[ch] < target * config.STUCK_SIGNAL_THRESHOLD
            and signals[ch] >= target * config.BOOST_MIN_SIGNAL
            and led >= config.STUCK_LED_THRESHOLD
        }
        maxed_channels.update(stuck_channels)

    # Only boost channels not previously boosted
    new_channels_needing_boost = maxed_channels - state.time_boosted_channels

    if not new_channels_needing_boost:
        return current_integration, set()

    # Calculate boost needed for weakest channel
    weakest_ch = min(new_channels_needing_boost, key=lambda ch: signals[ch])
    required_ratio = (
        target / signals[weakest_ch]
        if signals[weakest_ch] > 0
        else config.MAX_TIME_BOOST
    )

    # Apply boost limits
    time_increase = min(
        config.MAX_TIME_BOOST,
        max(config.MIN_TIME_BOOST, required_ratio),
    )
    new_integration = current_integration * time_increase

    # Clamp to detector limits
    new_integration = max(
        detector_params.min_integration_time,
        min(detector_params.max_integration_time, new_integration),
    )

    if logger:
        logger.info(
            f"  🚀 Integration boost: {weakest_ch.upper()} maxed at LED=255 with {signals[weakest_ch]/target*100:.1f}% signal",
        )
        logger.info(
            f"     {current_integration:.1f}ms → {new_integration:.1f}ms ({time_increase:.2f}x)",
        )

    return new_integration, new_channels_needing_boost
