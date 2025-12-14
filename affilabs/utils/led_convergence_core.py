"""Core LED convergence engine.

Clean, focused implementation of LED intensity calibration using model-aware adjustments.
Separated concerns: measurement, adjustment, saturation handling, convergence logic.
"""

import time
from typing import Optional
import numpy as np


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
        if channel not in self.max_saturating_intensity or led_intensity < self.max_saturating_intensity[channel]:
            self.max_saturating_intensity[channel] = led_intensity
            if logger:
                logger.info(f"  ⚠️ {channel.upper()} saturated @ LED={led_intensity} - boundary recorded")
    
    def record_undershoot(self, channel: str, led_intensity: int, signal: float, target: float, logger=None):
        """Record LED intensity that undershot target."""
        if channel not in self.min_undershooting_intensity or led_intensity > self.min_undershooting_intensity[channel]:
            self.min_undershooting_intensity[channel] = led_intensity
            if logger:
                logger.info(f"  📉 {channel.upper()} undershot @ LED={led_intensity} ({signal/target*100:.1f}% of target) - boundary recorded")
    
    def enforce_boundaries(self, channel: str, proposed_led: int, logger=None) -> int:
        """Apply boundary constraints to proposed LED adjustment."""
        original = proposed_led
        
        # Upper boundary: Never exceed saturation point
        if channel in self.max_saturating_intensity and proposed_led >= self.max_saturating_intensity[channel]:
            proposed_led = max(10, self.max_saturating_intensity[channel] - 5)
            if logger:
                logger.info(f"  🔒 {channel.upper()} capped {original} → {proposed_led} (saturation boundary)")
        
        # Lower boundary: Never go below undershoot point
        if channel in self.min_undershooting_intensity and proposed_led <= self.min_undershooting_intensity[channel]:
            proposed_led = min(255, self.min_undershooting_intensity[channel] + 5)
            if logger:
                logger.info(f"  🔒 {channel.upper()} floored {original} → {proposed_led} (undershoot boundary)")
        
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
    logger=None,
) -> int:
    """Calculate precise LED adjustment using model sensitivity.
    
    Args:
        model_slope_at_current_integration: counts per LED unit at current integration time
    
    Returns:
        New LED intensity (10-255)
    """
    signal_error = target_signal - current_signal
    signal_error_percent = (signal_error / target_signal) * 100.0
    
    # Calculate LED delta: signal_error / slope
    if abs(model_slope_at_current_integration) < 0.1:
        if logger:
            logger.warning(f"  ⚠️ {channel.upper()} slope too small ({model_slope_at_current_integration:.3f}), using ratio fallback")
        return calculate_ratio_based_led_adjustment(channel, current_led, current_signal, target_signal, logger)
    
    led_delta = signal_error / model_slope_at_current_integration
    
    # Safety limits: ±3 when close to target, ±50 when far
    if abs(signal_error_percent) < 10.0:
        led_delta = max(-3, min(3, led_delta))
    else:
        led_delta = max(-50, min(50, led_delta))
    
    new_led = int(max(10, min(255, current_led + led_delta)))
    
    if logger:
        logger.info(
            f"  🎯 MODEL-AWARE {channel.upper()} LED {current_led} → {new_led} "
            f"(error={signal_error_percent:+.1f}%, slope={model_slope_at_current_integration:.1f}, delta={led_delta:+.1f})"
        )
    
    return new_led


def calculate_ratio_based_led_adjustment(
    channel: str,
    current_led: int,
    current_signal: float,
    target_signal: float,
    logger=None,
) -> int:
    """Fallback LED adjustment using signal ratio."""
    if current_signal <= 0:
        ratio = 1.5
    else:
        ratio = target_signal / current_signal
    
    # Dynamic bounds based on distance from target
    if current_signal < target_signal * 0.5:
        ratio = max(0.5, min(2.0, ratio))
    elif current_signal < target_signal * 0.75:
        ratio = max(0.6, min(1.6, ratio))
    else:
        ratio = max(0.75, min(1.30, ratio))
    
    new_led = int(max(10, min(255, current_led * ratio)))
    
    if logger:
        logger.info(f"  📊 RATIO-BASED {channel.upper()} LED {current_led} → {new_led} (ratio={ratio:.2f})")
    
    return new_led


def calculate_saturation_recovery(
    channel: str,
    current_led: int,
    saturation_analysis: dict,
    model_slope: float,
    target_signal: float,
    detector_max: float,
    logger=None,
) -> int:
    """Calculate LED reduction to clear saturation using model slope."""
    severity = saturation_analysis["severity_score"]
    sat_pixels = saturation_analysis["sat_pixels"]
    max_width = saturation_analysis["max_contiguous_width"]
    
    # Aggressive reduction for severe saturation
    if severity > 10.0 or max_width > 20:
        reduction_factor = 0.60  # 40% reduction
    elif severity > 5.0 or max_width > 10:
        reduction_factor = 0.70  # 30% reduction
    else:
        reduction_factor = 0.80  # 20% reduction
    
    # Model-based refinement: estimate LED needed for target
    if abs(model_slope) > 0.1:
        led_for_target = target_signal / model_slope
        led_for_target = max(10, min(current_led * 0.95, led_for_target))
        
        # Blend model estimate with safety reduction
        new_led = int((led_for_target * 0.7) + (current_led * reduction_factor * 0.3))
    else:
        new_led = int(current_led * reduction_factor)
    
    new_led = max(10, min(255, new_led))
    
    if logger:
        logger.info(
            f"  🚨 SATURATION-RECOVERY {channel.upper()} LED {current_led} → {new_led} "
            f"(sat_px={sat_pixels}, width={max_width}, severity={severity:.1f})"
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
) -> tuple[Optional[float], int]:
    """Measure single channel: signal + saturation count.
    
    Returns:
        (signal_counts, saturated_pixels) or (None, 0) on failure
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
        return None, 0
    
    signal = roi_signal_fn(spec, wave_min_index, wave_max_index, method="median", top_n=50)
    sat_pixels = count_saturated_pixels(spec, wave_min_index, wave_max_index, saturation_threshold)
    
    return signal, sat_pixels


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
    zero_saturation = (total_sat == 0)
    
    if in_tolerance and zero_saturation:
        return True, "converged"
    elif in_tolerance and not zero_saturation:
        return False, f"in_tolerance_but_{total_sat}_saturated"
    elif zero_saturation and not in_tolerance:
        return False, "zero_sat_but_outside_tolerance"
    else:
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
    logger=None,
) -> tuple[float, set[str]]:
    """Determine if integration time boost needed for maxed/stuck channels.
    
    Returns:
        (new_integration_ms, channels_to_boost)
    """
    # Find channels that need integration boost
    maxed_channels = {
        ch for ch, led in led_intensities.items()
        if ch in signals
        and led >= 255
        and signals[ch] < target * 0.95  # Below target
        and signals[ch] >= target * 0.50  # But not hardware failure
    }
    
    # Also consider stuck channels (near max LED but not converging)
    if iteration >= 3:
        stuck_channels = {
            ch for ch, led in led_intensities.items()
            if ch in signals
            and signals[ch] < target * 0.90
            and signals[ch] >= target * 0.50
            and led >= 200  # Near max
        }
        maxed_channels.update(stuck_channels)
    
    # Only boost channels not previously boosted
    new_channels_needing_boost = maxed_channels - state.time_boosted_channels
    
    if not new_channels_needing_boost:
        return current_integration, set()
    
    # Calculate boost needed for weakest channel
    weakest_ch = min(new_channels_needing_boost, key=lambda ch: signals[ch])
    required_ratio = target / signals[weakest_ch] if signals[weakest_ch] > 0 else 2.0
    
    # Minimum 1.15x boost (overcome noise), maximum 2.0x (safety)
    time_increase = min(2.0, max(1.15, required_ratio))
    new_integration = current_integration * time_increase
    
    # Clamp to detector limits
    new_integration = max(
        detector_params.min_integration_time,
        min(detector_params.max_integration_time, new_integration)
    )
    
    if logger:
        logger.info(
            f"  🚀 Integration boost: {weakest_ch.upper()} maxed at LED=255 with {signals[weakest_ch]/target*100:.1f}% signal"
        )
        logger.info(f"     {current_integration:.1f}ms → {new_integration:.1f}ms ({time_increase:.2f}x)")
    
    return new_integration, new_channels_needing_boost
