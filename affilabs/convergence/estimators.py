from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Tuple, Optional


@dataclass
class SlopeEstimator:
    """Estimate slopes from measurement history (ENHANCED from current stack).

    Uses robust estimation:
    - Linear regression when 3+ points available
    - Simple two-point slope as fallback
    - Ignores points with minimal LED change
    """
    max_points: int = 5  # Increased from 3 for better regression
    _history: Dict[str, Deque[Tuple[int, float]]] = field(default_factory=dict)

    def record(self, channel: str, led: int, signal: float) -> None:
        """Record a non-saturated measurement point."""
        dq = self._history.setdefault(channel, deque(maxlen=self.max_points))
        dq.append((led, signal))

    def estimate(self, channel: str) -> Optional[float]:
        """Estimate counts per LED unit from measurement history.

        Returns:
            Slope (counts per LED) or None if insufficient data
        """
        dq = self._history.get(channel)
        if not dq or len(dq) < 2:
            return None

        # Try linear regression if we have 3+ points
        if len(dq) >= 3:
            import numpy as np

            # Extract LED and signal values
            leds = np.array([led for led, _ in dq], dtype=np.float64)
            signals = np.array([sig for _, sig in dq], dtype=np.float64)

            # Check for sufficient LED variation
            led_range = np.ptp(leds)  # peak-to-peak (max - min)
            if led_range < 5:  # Minimum 5 LED units of variation
                # Fall back to two-point estimate
                (l1, s1), (l2, s2) = dq[-2], dq[-1]
                d_led = l2 - l1
                if abs(d_led) < 2:
                    return None
                return (s2 - s1) / d_led

            # Linear regression: slope = cov(x,y) / var(x)
            # This is more robust than simple two-point
            mean_led = np.mean(leds)
            mean_sig = np.mean(signals)

            cov = np.sum((leds - mean_led) * (signals - mean_sig))
            var = np.sum((leds - mean_led) ** 2)

            if var < 1e-6:  # Avoid division by zero
                return None

            slope = cov / var

            # Sanity check: slope should be positive and reasonable
            if slope <= 0 or slope > 1000:
                return None

            return float(slope)

        # Fallback: simple two-point slope
        (l1, s1), (l2, s2) = dq[-2], dq[-1]
        d_led = l2 - l1

        # Ignore minimal LED changes
        if abs(d_led) < 2:
            return None

        slope = (s2 - s1) / d_led

        # Sanity check
        if slope <= 0 or slope > 1000:
            return None

        return float(slope)

    def clear(self) -> None:
        """Clear all history (called when integration time changes)."""
        self._history.clear()
