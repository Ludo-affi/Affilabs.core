"""Core LED convergence engine - Clean rewrite.

Simple, device-agnostic LED calibration with clear logic:
1. Measure channels
2. Check convergence (all in tolerance AND zero saturation)
3. Adjust LEDs using linear model
4. Track boundaries per integration time
5. Handle saturation by reducing LED/integration time
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Callable, Protocol

import numpy as np


class ConvergenceConfig:
    """Configuration constants - all device-agnostic thresholds."""

    # LED intensity limits
    MIN_LED = 10
    MAX_LED = 255

    # LED adjustment safety margins
    LED_SMALL_STEP = 5  # Small adjustment when close to boundaries
    LED_BOUNDARY_MARGIN = 5  # Safety margin from known-bad LEDs

    # Saturation handling
    SATURATION_LED_REDUCTION = 10  # LED reduction when saturating
    SATURATION_TIME_REDUCTION_MILD = 0.90  # Reduce time by 10% for mild saturation
    SATURATION_TIME_REDUCTION_SEVERE = 0.70  # Reduce time by 30% for severe saturation
    SEVERE_SAT_PIXEL_COUNT = 50  # Pixel count threshold for "severe"

    # Model-based adjustments
    MAX_LED_CHANGE = 50  # Maximum LED change per iteration
    MIN_SIGNAL_FOR_MODEL = 0.20  # Minimum signal to trust linear model

    # Convergence thresholds
    ALLOW_EXIT_WITH_SATURATION = False  # Require zero saturation to converge
    # Allow locking slightly above tolerance (e.g., +5%) when NOT saturating
    # Set to 0.0 for strict ±tolerance acceptance
    ACCEPT_ABOVE_EXTRA_PERCENT = 0.0

    # Measurement behavior
    # Parallel measurements disabled - hardware (USB spectrometer) requires exclusive access
    # Single-threaded sequential measurement is faster and more reliable than thread overhead
    PARALLEL_MEASUREMENTS = False
    MAX_MEASURE_WORKERS = 1
    # Per-channel measurement timeout (seconds). Reduced from 2s for faster failure detection.
    MEASUREMENT_TIMEOUT_S = 1.0
    # Optional callback invoked to yield to UI/event loop between steps (set by caller if needed)
    YIELD_CALLBACK: Optional[Callable[[], None]] = None

    # Classification window for "near" channels (e.g., ±10% of target)
    NEAR_WINDOW_PERCENT = 0.10
    # When within the near window, scale down LED step to avoid overshoot
    NEAR_DAMPING = 0.5

    # Prefer using estimated slope after N iterations (even if model exists)
    # Set to 0 to never prefer estimated, 1 to switch after first pass
    PREFER_ESTIMATED_SLOPE_AFTER_ITERS = 1

    # Dynamic boundary margin scaling when close to target (within near window)
    # Effective margin = LED_BOUNDARY_MARGIN * NEAR_BOUNDARY_SCALE (min 1)
    NEAR_BOUNDARY_SCALE = 0.5


class AcquireSpectrumFn(Protocol):
    def __call__(
        self,
        *,
        usb: object,
        ctrl: object,
        channel: str,
        led_intensity: int,
        integration_time_ms: float,
        num_scans: int,
        use_batch_command: bool,
    ) -> Optional[object]: ...


class ROISignalFn(Protocol):
    def __call__(
        self,
        spectrum: object,
        wave_min_index: int,
        wave_max_index: int,
        method: str,
        top_n: int,
    ) -> float: ...


def _log(logger: Optional[object], level: str, msg: str) -> None:
    fn = getattr(logger, level, None)
    if callable(fn):
        try:
            fn(msg)
        except Exception:
            pass


class DetectorParams:
    """Detector hardware specifications - device-specific values."""

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


class ChannelBoundaries:
    """Tracks LED boundaries for one channel at current integration time."""

    def __init__(self) -> None:
        self.max_led_no_sat: Optional[int] = None  # Highest LED that didn't saturate
        self.min_led_above_target: Optional[int] = None  # Lowest LED above target


class ConvergenceState:
    """Tracks convergence state per integration time."""

    def __init__(self) -> None:
        # Per-channel boundaries (cleared when integration time changes)
        self.boundaries: Dict[str, ChannelBoundaries] = {}

        # Current integration time (to detect changes)
        self.current_integration_time: Optional[float] = None

        # Recent non-saturated measurements per channel at current integration
        # Stores up to last 3 points (led, signal) to estimate slope
        self.history: Dict[str, List[Tuple[int, float]]] = {}

        # Sticky locks: channels accepted at this integration time stay locked
        # across subsequent iterations (unless integration time changes)
        self.sticky_locked: set[str] = set()

    def clear_boundaries(self, logger: Optional[object] = None) -> None:
        """Clear all boundaries (called when integration time changes)."""
        if self.boundaries:
            _log(logger, "info", "  🔄 Integration time changed → clearing all LED boundaries")
        self.boundaries.clear()
        self.history.clear()
        if self.sticky_locked:
            self.sticky_locked.clear()

    def update_integration_time(self, new_time: float, logger: Optional[object] = None) -> None:
        """Update integration time and clear boundaries if changed."""
        if self.current_integration_time is not None and self.current_integration_time != new_time:
            self.clear_boundaries(logger)
        self.current_integration_time = new_time

    def get_boundaries(self, channel: str) -> ChannelBoundaries:
        """Get boundaries for channel (create if doesn't exist)."""
        if channel not in self.boundaries:
            self.boundaries[channel] = ChannelBoundaries()
        return self.boundaries[channel]

    def record_non_saturated_point(self, channel: str, led: int, signal: float) -> None:
        """Record a non-saturated measurement point for slope estimation."""
        if channel not in self.history:
            self.history[channel] = []
        self.history[channel].append((led, signal))
        if len(self.history[channel]) > 3:
            self.history[channel].pop(0)

    def get_estimated_slope(self, channel: str) -> Optional[float]:
        """Estimate counts/LED slope from last two non-saturated points."""
        pts = self.history.get(channel, [])
        if len(pts) < 2:
            return None
        (led1, sig1), (led2, sig2) = pts[-2], pts[-1]
        d_led = led2 - led1
        d_sig = sig2 - sig1
        if d_led == 0:
            return None
        return d_sig / d_led

    def record_saturation(self, channel: str, led: int, logger: Optional[object] = None) -> None:
        """Record that this LED caused saturation."""
        bounds = self.get_boundaries(channel)
        if bounds.max_led_no_sat is None or led < bounds.max_led_no_sat:
            bounds.max_led_no_sat = led
            _log(logger, "info", f"  ⚠️ {channel.upper()} saturated @ LED={led} → never exceed LED={led-5}")

    def record_above_target(self, channel: str, led: int, logger: Optional[object] = None) -> None:
        """Record that this LED achieved above-target signal."""
        bounds = self.get_boundaries(channel)
        if bounds.min_led_above_target is None or led < bounds.min_led_above_target:
            bounds.min_led_above_target = led

    def enforce_boundaries(
        self,
        channel: str,
        proposed_led: int,
        config: ConvergenceConfig,
        logger: Optional[object] = None,
        *,
        current_signal: Optional[float] = None,
        target_signal: Optional[float] = None,
    ) -> int:
        """Clamp proposed LED to safe range based on boundaries.

        Applies a smaller boundary margin when the channel's current signal
        is within the configured near window around the target.
        """
        if channel not in self.boundaries:
            return proposed_led

        bounds = self.boundaries[channel]
        original_led = proposed_led

        # Compute dynamic margin (smaller when near target)
        margin = config.LED_BOUNDARY_MARGIN
        if current_signal is not None and target_signal and target_signal > 0:
            err_pct = abs(current_signal - target_signal) / target_signal
            if err_pct <= getattr(config, "NEAR_WINDOW_PERCENT", 0.10):
                scaled = int(round(config.LED_BOUNDARY_MARGIN * getattr(config, "NEAR_BOUNDARY_SCALE", 0.5)))
                margin = max(1, scaled)

        # Don't exceed LED that caused saturation (minus margin)
        if bounds.max_led_no_sat is not None:
            max_safe = bounds.max_led_no_sat - margin
            if proposed_led > max_safe:
                proposed_led = max(config.MIN_LED, max_safe)
                _log(logger, "info", f"  🔒 {channel.upper()} capped LED {original_led}→{proposed_led} (saturation boundary)")

        # Don't go below LED that gave good signal (plus margin)
        if bounds.min_led_above_target is not None:
            min_safe = bounds.min_led_above_target + margin
            if proposed_led < min_safe:
                proposed_led = min(config.MAX_LED, min_safe)
                _log(logger, "info", f"  🔒 {channel.upper()} raised LED {original_led}→{proposed_led} (undershoot boundary)")

        return proposed_led

    # Sticky lock helpers
    def lock_channel(self, channel: str) -> None:
        self.sticky_locked.add(channel)

    def is_locked(self, channel: str) -> bool:
        return channel in self.sticky_locked

    def get_locked(self) -> List[str]:
        return list(self.sticky_locked)


def count_saturated_pixels(
    spectrum: object,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
) -> int:
    """Count saturated pixels in ROI."""
    arr = np.asarray(spectrum)
    roi = arr[wave_min_index:wave_max_index]
    return int(np.sum(roi >= saturation_threshold))


def measure_channel(
    usb: object,
    ctrl: object,
    channel: str,
    led_intensity: int,
    integration_ms: float,
    acquire_spectrum_fn: AcquireSpectrumFn,
    roi_signal_fn: ROISignalFn,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
    use_batch: bool,
) -> Tuple[Optional[float], int, Optional[object]]:
    """Measure single channel: signal + saturation count + spectrum.

    Returns:
        (signal_counts, saturated_pixels, spectrum)
        Returns (None, 0, None) on measurement failure
    """
    spec = acquire_spectrum_fn(
        usb=usb,
        ctrl=ctrl,
        channel=channel,
        led_intensity=led_intensity,
        integration_time_ms=integration_ms,
        num_scans=1,
        use_batch_command=use_batch,
    )

    if spec is None:
        return None, 0, None

    signal = roi_signal_fn(spec, wave_min_index, wave_max_index, method="top_n_mean", top_n=50)

    sat_pixels = count_saturated_pixels(
        spec,
        wave_min_index,
        wave_max_index,
        saturation_threshold,
    )

    return signal, sat_pixels, spec


def check_convergence(
    signals: Dict[str, float],
    sat_per_ch: Dict[str, int],
    target_signal: float,
    tolerance_signal: float,
    config: Optional[ConvergenceConfig] = None,
) -> Tuple[bool, List[str], List[str]]:
    """Check convergence: all channels acceptable + zero saturation.

    Acceptable = within tolerance (80-90%) OR above tolerance without saturation

    NEW RULE: If above 90% (up to 95%) but NOT saturating → PASS (lock it)
              Only reject if saturating OR below 80%

    Returns:
        (converged, channels_acceptable, channels_saturating)
    """
    if config is None:
        config = ConvergenceConfig()
    min_signal = target_signal - tolerance_signal  # 80% threshold
    max_signal = target_signal + tolerance_signal  # 90% threshold

    channels_acceptable = []
    channels_saturating = []

    for ch in signals:
        sig = signals[ch]
        sat = sat_per_ch.get(ch, 0)

        # In standard tolerance range (target ± tolerance)
        in_tolerance = min_signal <= sig <= max_signal

        # Above tolerance but not saturating.
        # Only allow up to an extra +config.ACCEPT_ABOVE_EXTRA_PERCENT of target.
        upper_safe = max_signal + (target_signal * config.ACCEPT_ABOVE_EXTRA_PERCENT)
        above_but_safe = (sig > max_signal) and (sig <= upper_safe) and (sat == 0)

        # Channel is acceptable if in tolerance OR above without saturation
        if in_tolerance or above_but_safe:
            channels_acceptable.append(ch)

        if sat > 0:
            channels_saturating.append(ch)

    # Converged = ALL channels acceptable AND ZERO saturation
    converged = (len(channels_acceptable) == len(signals)) and (len(channels_saturating) == 0)

    return converged, channels_acceptable, channels_saturating


def calculate_led_adjustment(
    channel: str,
    current_led: int,
    current_signal: float,
    target_signal: float,
    iteration: int,
    model_slope: Optional[float],
    estimated_slope: Optional[float],
    config: ConvergenceConfig,
    logger: Optional[object] = None,
) -> int:
    """Calculate new LED using linear/estimated slope or ratio-based fallback.

    Args:
        model_slope: counts per LED unit at current integration time
        estimated_slope: counts per LED unit estimated from recent non-sat points

    Returns:
        New LED intensity (clamped to MIN_LED-MAX_LED)
    """
    signal_error = target_signal - current_signal

    # Choose slope per config and iteration
    prefer_est = (
        isinstance(config.PREFER_ESTIMATED_SLOPE_AFTER_ITERS, int)
        and config.PREFER_ESTIMATED_SLOPE_AFTER_ITERS >= 1
        and iteration >= config.PREFER_ESTIMATED_SLOPE_AFTER_ITERS
    )

    def _valid(x: Optional[float]) -> bool:
        return x is not None and abs(x) > 0.1

    effective_slope: Optional[float] = None
    if prefer_est and _valid(estimated_slope):
        effective_slope = estimated_slope
    elif _valid(model_slope):
        effective_slope = model_slope
    elif _valid(estimated_slope):
        effective_slope = estimated_slope

    # Use slope if available and signal is strong enough
    if effective_slope is not None and current_signal > target_signal * config.MIN_SIGNAL_FOR_MODEL:
        led_delta = signal_error / effective_slope

        # Calculate minimum meaningful step based on slope and tolerance
        # For 5% tolerance: strong LED (slope=151) -> min_step=22, weak LED (slope=45) -> min_step=73
        # This ensures adjustment is significant enough to be detectable
        tolerance_signal = target_signal * 0.05  # Assuming 5% tolerance (can be parameterized)
        min_step_for_slope = tolerance_signal / effective_slope if effective_slope > 0 else 1.0
        min_step_for_slope = max(1.0, min_step_for_slope)  # At least 1 LED unit

        # Enforce minimum step (unless already very close)
        if abs(led_delta) > 0 and abs(led_delta) < min_step_for_slope:
            led_delta = min_step_for_slope if led_delta > 0 else -min_step_for_slope

        led_delta = max(-config.MAX_LED_CHANGE, min(config.MAX_LED_CHANGE, led_delta))

        # Dampen when within near window to avoid overshoot
        err_pct = abs(signal_error) / target_signal if target_signal > 0 else 0.0
        if err_pct <= config.NEAR_WINDOW_PERCENT:
            # LESS damping when going UP (increasing LED) vs going DOWN
            # This makes convergence more aggressive when approaching target from below
            if led_delta > 0:  # Increasing LED (signal below target)
                led_delta *= min(config.NEAR_DAMPING * 1.5, 0.9)  # Less damping, max 90%
            else:  # Decreasing LED (signal above target)
                led_delta *= config.NEAR_DAMPING  # Keep conservative damping

        new_led = int(current_led + led_delta)
        if effective_slope is model_slope:
            slope_str = f"model:{model_slope:.1f}"
        else:
            slope_str = f"est:{(estimated_slope or 0.0):.1f}"
        _log(logger, "info", f"  🎯 {channel.upper()} LED {current_led}→{new_led} (Δ{led_delta:+.1f}, {slope_str})")

    else:
        # Fallback: ratio-based adjustment
        if current_signal > 0:
            ratio = target_signal / current_signal
            ratio = max(0.5, min(2.0, ratio))
        else:
            ratio = 1.5

        new_led = int(current_led * ratio)
        _log(logger, "info", f"  📊 {channel.upper()} LED {current_led}→{new_led} (ratio: {ratio:.2f})")

    # Clamp to valid range
    new_led = max(config.MIN_LED, min(config.MAX_LED, new_led))
    return new_led

def calculate_saturation_recovery(
    channel: str,
    current_led: int,
    current_signal: float,
    target_signal: float,
    sat_pixels: int,
    model_slope: Optional[float],
    config: ConvergenceConfig,
    logger: Optional[object] = None,
) -> int:
    """Calculate precise LED reduction to clear saturation using model slope.

    Logic: If close to target with mild saturation, make tiny adjustment.
           Use model slope to calculate exact LED reduction needed.
    """
    # Calculate how far above target we are (as percentage)
    signal_excess_pct = ((current_signal - target_signal) / target_signal) * 100.0

    # Use model slope for precise adjustment if available
    if model_slope is not None and abs(model_slope) > 0.1:
        # Estimate signal reduction needed: aim for ~2-3% below target to clear saturation
        target_with_margin = target_signal * 0.97  # 3% below target for safety
        signal_to_drop = current_signal - target_with_margin

        # Calculate LED reduction: signal_to_drop / slope
        led_reduction = signal_to_drop / model_slope

        # Minimum reduction based on severity
        if sat_pixels > config.SEVERE_SAT_PIXEL_COUNT:
            min_reduction = 5  # At least 5 LEDs for severe saturation
        elif sat_pixels > 20:
            min_reduction = 3  # At least 3 LEDs for moderate
        else:
            min_reduction = 2  # At least 2 LEDs for mild (10px case)

        led_reduction = max(min_reduction, led_reduction)

    else:
        # Fallback: severity-based reduction
        if sat_pixels > config.SEVERE_SAT_PIXEL_COUNT:
            led_reduction = config.SATURATION_LED_REDUCTION * 3  # 30 LEDs
        elif sat_pixels > 20:
            led_reduction = config.SATURATION_LED_REDUCTION * 1.5  # 15 LEDs
        else:
            led_reduction = config.SATURATION_LED_REDUCTION * 0.5  # 5 LEDs

    new_led = int(max(config.MIN_LED, current_led - led_reduction))

    if model_slope:
        _log(logger, "info", f"  🚨 {channel.upper()} saturated ({sat_pixels}px, {signal_excess_pct:+.1f}% above target) → LED {current_led}→{new_led} (Δ-{led_reduction:.1f}, slope={model_slope:.1f})")
    else:
        _log(logger, "info", f"  🚨 {channel.upper()} saturated ({sat_pixels}px) → LED {current_led}→{new_led} (Δ-{led_reduction:.0f})")

    return new_led


def calculate_integration_time_reduction(
    sat_per_ch: Dict[str, int],
    current_integration: float,
    detector_params: DetectorParams,
    config: ConvergenceConfig,
    logger: Optional[object] = None,
) -> float:
    """Reduce integration time if saturation present."""
    total_sat = sum(sat_per_ch.values())

    if total_sat == 0:
        return current_integration

    # Determine severity
    max_sat = max(sat_per_ch.values()) if sat_per_ch else 0

    if max_sat > config.SEVERE_SAT_PIXEL_COUNT:
        reduction_factor = config.SATURATION_TIME_REDUCTION_SEVERE
    else:
        reduction_factor = config.SATURATION_TIME_REDUCTION_MILD

    new_integration = current_integration * reduction_factor
    new_integration = max(detector_params.min_integration_time, new_integration)

    if new_integration < current_integration:
        _log(logger, "info", f"  ⏱️ Reducing integration time: {current_integration:.1f}ms → {new_integration:.1f}ms (saturation: {total_sat}px)")

    return new_integration
