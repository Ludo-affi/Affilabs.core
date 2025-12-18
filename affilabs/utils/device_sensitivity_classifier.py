from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class SensitivityLabel(str, Enum):
    HIGH = "high"
    BASELINE = "baseline"


@dataclass
class SensitivityFeatures:
    integration_ms: float
    num_channels: int
    num_saturating: int
    total_saturated_pixels: int
    avg_signal_fraction_of_target: float
    avg_model_slope_10ms: float
    dark_counts: float | None = None


class DeviceSensitivityClassifier:
    """Rule-based classifier stub for device sensitivity.

    Returns a label and confidence with human-readable reasons.
    This is intentionally simple and deterministic; can be replaced
    with a learned model later.
    """

    def classify(self, f: SensitivityFeatures) -> Tuple[SensitivityLabel, float, str]:
        reasons = []
        score = 0.0

        # Strong indicator: multiple channels saturating at <= 20ms
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

        # Low average signal fraction despite max LEDs suggests starvation
        if f.avg_signal_fraction_of_target < 0.6:
            score += 0.05
            reasons.append(
                f"avg_signal_fraction={f.avg_signal_fraction_of_target:.2f}"
            )

        # Confidence is the bounded score; label threshold at 0.6
        confidence = max(0.0, min(1.0, score))
        if confidence >= 0.6:
            return SensitivityLabel.HIGH, confidence, ", ".join(reasons)

        return SensitivityLabel.BASELINE, 1.0 - confidence, ", ".join(reasons) or "no strong indicators"
