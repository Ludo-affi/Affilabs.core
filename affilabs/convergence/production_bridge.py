"""Helper functions to bridge production code with convergence engine.

This module provides utilities to convert between the existing
production data structures and the convergence engine's configuration.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from .config import ConvergenceRecipe, DetectorParams
from affilabs.utils.led_convergence_core import ConvergenceConfig


def create_recipe_from_production_config(
    channels: List[str],
    initial_leds: Dict[str, int],
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    config: Optional[ConvergenceConfig] = None,
    polarization_mode: str = "S",  # S or P polarization mode
) -> ConvergenceRecipe:
    """Convert production ConvergenceConfig to engine ConvergenceRecipe.

    This allows the engine to use the same configuration parameters
    as the existing production convergence algorithm.

    Args:
        channels: List of channel names (e.g., ['a', 'b', 'c', 'd'])
        initial_leds: Initial LED intensities per channel
        initial_integration_ms: Starting integration time
        target_percent: Target signal as fraction of detector max (e.g., 0.85)
        tolerance_percent: Tolerance as fraction (e.g., 0.05 for ±5%)
        config: Optional ConvergenceConfig (uses defaults if None)

    Returns:
        ConvergenceRecipe configured for production use
    """
    if config is None:
        config = ConvergenceConfig()

    return ConvergenceRecipe(
        # Channels and initial state
        channels=channels,
        initial_leds=initial_leds.copy(),
        initial_integration_ms=initial_integration_ms,

        # Targets (same as production)
        target_percent=target_percent,
        tolerance_percent=tolerance_percent,

        # Polarization mode - CRITICAL for P-pol physics
        polarization_mode=polarization_mode.upper(),  # Normalize to uppercase S or P

        # Behavior from production config
        near_window_percent=getattr(config, 'NEAR_WINDOW_PERCENT', 0.10),
        max_iterations=getattr(config, 'MAX_ITERATIONS', 15),
        prefer_est_after_iters=getattr(config, 'PREFER_ESTIMATED_AFTER_ITERS', 1),

        # LED step constraints from production config
        max_led_change=getattr(config, 'MAX_LED_CHANGE', 50),
        led_small_step=getattr(config, 'LED_SMALL_STEP', 5),
        boundary_margin=getattr(config, 'BOUNDARY_MARGIN', 5),
        near_boundary_scale=getattr(config, 'NEAR_BOUNDARY_SCALE', 0.5),

        # Measurement behavior
        measurement_timeout_s=getattr(config, 'MEASUREMENT_TIMEOUT_S', 2.0),
        parallel_workers=getattr(config, 'MAX_MEASURE_WORKERS', 1) if getattr(config, 'PARALLEL_MEASUREMENTS', False) else 1,
        use_batch_command=True,  # Production always uses batch command
        # CRITICAL: Use same num_scans as reference capture (180ms detector window)
        # This ensures saturation is detected during convergence, not after
        num_scans=max(1, int(180.0 / initial_integration_ms)),

        # Slope trust
        min_signal_for_model=getattr(config, 'MIN_SIGNAL_FOR_MODEL', 0.20),

        # Acceptance
        accept_above_extra_percent=getattr(config, 'ACCEPT_ABOVE_EXTRA_PERCENT', 0.0),
    )


def create_detector_params_from_production(
    max_counts: float,
    saturation_threshold: float,
    min_integration_time: float,
    max_integration_time: float,
    polarization_mode: str = "S",  # S or P polarization
) -> DetectorParams:
    """Create engine DetectorParams from production parameters.

    Args:
        max_counts: Maximum detector counts (e.g., 65535 for USB4000)
        saturation_threshold: Saturation threshold in counts
        min_integration_time: Minimum integration time in ms
        max_integration_time: Maximum integration time in ms
        polarization_mode: S or P polarization - P-pol gets higher max integration (62.5ms)

    Returns:
        DetectorParams configured for production detector
    """
    # P-pol can use higher integration time since it's always lower intensity than S-pol
    # (P-pol transmission < S-pol transmission at SPR resonance)
    if polarization_mode.upper() == "P":
        max_integration_time = 62.5  # P-pol: higher max integration allowed
    
    return DetectorParams(
        max_counts=max_counts,
        saturation_threshold=saturation_threshold,
        min_integration_time=min_integration_time,
        max_integration_time=max_integration_time,
    )


def validate_engine_result(
    result,
    expected_channels: List[str],
) -> bool:
    """Validate engine result matches production expectations.

    Args:
        result: ConvergenceResult from engine
        expected_channels: Expected channel list

    Returns:
        True if result is valid for production use
    """
    if not result:
        return False

    # Check all channels present (don't require convergence - return data even if not converged)
    if set(result.final_leds.keys()) != set(expected_channels):
        return False

    if set(result.signals.keys()) != set(expected_channels):
        return False

    # Check integration time is valid
    if result.integration_ms <= 0:
        return False

    # Check LED values are in range
    for ch, led in result.final_leds.items():
        if not (0 <= led <= 255):
            return False

    # Check signals are positive
    for ch, sig in result.signals.items():
        if sig < 0:
            return False

    return True


def convert_engine_result_to_production(
    result,
    channel_list: List[str],
) -> tuple[float, Dict[str, float], bool, Dict[str, int]]:
    """Convert engine result to production LEDconverge return format.

    Args:
        result: ConvergenceResult from engine
        channel_list: List of channels (for validation)

    Returns:
        Tuple (integration_ms, signals_dict, converged, final_leds)
        Extended format with final LED values
    """
    if not validate_engine_result(result, channel_list):
        # Return failure format
        return result.integration_ms, {}, False, {}

    return (
        result.integration_ms,
        result.signals.copy(),
        result.converged,
        result.final_leds.copy(),
    )
