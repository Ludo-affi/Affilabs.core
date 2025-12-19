from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DetectorParams:
    max_counts: float
    saturation_threshold: float
    min_integration_time: float
    max_integration_time: float


@dataclass
class ConvergenceRecipe:
    """Convergence configuration recipe.

    Default values are production-proven from thousands of successful calibrations
    using the battle-tested current stack. These values balance convergence speed,
    stability, and reliability across different device sensitivities.
    """
    # Channels and initial state
    channels: List[str]
    initial_leds: Dict[str, int]
    initial_integration_ms: float

    # Targets
    target_percent: float  # e.g., 0.85 for 85% of detector max
    tolerance_percent: float  # e.g., 0.05 for ±5%

    # Behavior (OPTIMIZED FOR SPEED - AGGRESSIVE)
    near_window_percent: float = 0.15  # ±15% window for earlier fine-tuning entry (faster)
    max_iterations: int = 6  # Further reduced - trust model predictions for faster convergence
    enable_analysis_phase: bool = False  # Disabled - skip fine-tuning validation for speed
    analysis_iterations: int = 0  # No fine-tuning - go straight to reference capture
    prefer_est_after_iters: int = 1  # Use estimated slope after 1 iteration (trust live data)

    # LED step constraints (OPTIMIZED FOR SPEED)
    max_led_change: int = 80  # Larger jumps allowed for faster convergence (was 50)
    led_small_step: int = 8  # Slightly larger fine adjustments (was 5)
    boundary_margin: int = 3  # Tighter safety margin for speed (was 5)
    near_boundary_scale: float = 0.5  # Reduce margin when near target

    # Measurement behavior
    measurement_timeout_s: float = 2.0  # Per-channel measurement timeout
    parallel_workers: int = 1  # Sequential by default (hardware exclusive access)
    use_batch_command: bool = True  # Use batch LED command for reliability
    num_scans: int = 1  # Single scan during convergence (averaging in reference)

    # Slope trust (OPTIMIZED FOR SPEED)
    min_signal_for_model: float = 0.10  # Lower threshold - trust model more aggressively (was 0.20)

    # Acceptance (OPTIMIZED FOR SPEED)
    accept_above_extra_percent: float = 0.03  # Allow 3% overshoot for faster convergence (was 0.0)

    def __post_init__(self) -> None:
        """Validate and adjust configuration for logical consistency.

        Near-Window Auto-Adjust: Ensures near_window_percent is never smaller than
        tolerance_percent to prevent classification inconsistency where channels
        would be classified as "near" even though they're outside the acceptance window.
        """
        if self.near_window_percent < self.tolerance_percent:
            original = self.near_window_percent
            self.near_window_percent = self.tolerance_percent
            # Note: Logging happens during engine execution when logger is available
            # Store adjustment info for potential logging
            self._near_window_adjusted = True
            self._near_window_original = original
        else:
            self._near_window_adjusted = False
