"""Device sensitivity classification for convergence engine.

Detects HIGH sensitivity detectors early (first 2 iterations) to prevent
saturation spiral by capping integration time at 20ms.

Migrated from production stack: affilabs/utils/device_sensitivity_classifier.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class SensitivityLabel(str, Enum):
    """Device sensitivity classification."""
    HIGH = "high"
    BASELINE = "baseline"


@dataclass
class SensitivityFeatures:
    """Features for sensitivity classification."""
    integration_ms: float
    num_channels: int
    num_saturating: int
    total_saturated_pixels: int
    avg_signal_fraction_of_target: float
    avg_model_slope_10ms: float


class SensitivityClassifier:
    """Rule-based classifier for device sensitivity.

    Returns label, confidence, and human-readable reason.
    Intentionally simple and deterministic - can be replaced with learned model later.

    Migrated from production stack with proven thresholds.
    """

    def classify(self, f: SensitivityFeatures) -> Tuple[SensitivityLabel, float, str]:
        """Classify device sensitivity from early-iteration features.

        Args:
            f: Feature set from first 2 iterations

        Returns:
            (label, confidence, reason) tuple
        """
        reasons = []
        score = 0.0

        # Strong indicator: multiple channels saturating at ≤20ms
        if f.integration_ms <= 20.0 and f.num_saturating >= 2:
            score += 0.6
            reasons.append(
                f"{f.num_saturating}/{f.num_channels} channels saturating at {f.integration_ms:.1f}ms"
            )

        # More total saturated pixels increases likelihood
        if f.total_saturated_pixels >= 1000:
            score += 0.2
            reasons.append(f"total_sat_pixels={f.total_saturated_pixels}")

        # Very high slopes (bright LEDs) often saturate at low times
        if f.avg_model_slope_10ms >= 700.0:
            score += 0.15
            reasons.append(f"avg_slope_10ms={f.avg_model_slope_10ms:.1f}")

        # High average signal fraction also indicates high sensitivity
        if f.avg_signal_fraction_of_target >= 1.2:
            score += 0.15
            reasons.append(f"avg_signal={f.avg_signal_fraction_of_target:.2f}× target")

        # Classify based on score
        if score >= 0.5:
            label = SensitivityLabel.HIGH
        else:
            label = SensitivityLabel.BASELINE

        confidence = min(1.0, score)
        reason = "; ".join(reasons) if reasons else "no indicators"

        return label, confidence, reason
