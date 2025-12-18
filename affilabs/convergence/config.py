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

    # Behavior (PRODUCTION-PROVEN VALUES)
    near_window_percent: float = 0.10  # ±10% window for fine-tuning
    max_iterations: int = 15  # Typical convergence in 3-7 iterations
    prefer_est_after_iters: int = 1  # Use estimated slope after 1 iteration

    # LED step constraints (PRODUCTION-PROVEN VALUES)
    max_led_change: int = 50  # Maximum LED jump per iteration
    led_small_step: int = 5  # Small adjustment for fine-tuning
    boundary_margin: int = 5  # Safety margin from known-bad values
    near_boundary_scale: float = 0.5  # Reduce margin when near target

    # Measurement behavior
    measurement_timeout_s: float = 2.0  # Per-channel measurement timeout
    parallel_workers: int = 1  # Sequential by default (hardware exclusive access)
    use_batch_command: bool = True  # Use batch LED command for reliability
    num_scans: int = 1  # Single scan during convergence (averaging in reference)

    # Slope trust (PRODUCTION-PROVEN VALUE)
    min_signal_for_model: float = 0.20  # Require 20% of target for slope usage

    # Acceptance (PRODUCTION-PROVEN VALUE)
    accept_above_extra_percent: float = 0.0  # Strict: must be in tolerance

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
