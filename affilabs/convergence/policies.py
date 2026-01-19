from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .config import ConvergenceRecipe, DetectorParams


@dataclass
class AcceptanceResult:
    converged: bool
    acceptable: List[str]
    saturating: List[str]


class AcceptancePolicy:
    def evaluate(
        self,
        signals: Dict[str, float],
        saturation: Dict[str, int],
        target_signal: float,
        tol_signal: float,
        recipe: ConvergenceRecipe,
    ) -> AcceptanceResult:
        lower = target_signal - tol_signal
        upper = target_signal + tol_signal
        extra = recipe.accept_above_extra_percent * target_signal
        acceptable: List[str] = []
        saturating: List[str] = []
        for ch, sig in signals.items():
            sat = saturation.get(ch, 0)
            in_tol = (lower <= sig <= upper)
            above_but_safe = (sig > upper) and (sig <= upper + extra) and (sat == 0)

            # STRICT: No saturation allowed - must have sat == 0
            if (in_tol or above_but_safe) and sat == 0:
                acceptable.append(ch)
            if sat > 0:
                saturating.append(ch)

        # Converged if ALL channels acceptable with ZERO saturation
        converged = (len(acceptable) == len(signals))
        return AcceptanceResult(converged, acceptable, saturating)


class PriorityPolicy:
    def classify(
        self,
        channels: List[str],
        signals: Dict[str, float],
        saturation: Dict[str, int],
        target_signal: float,
        near_window_percent: float,
        locked: List[str],
    ) -> Tuple[List[str], List[str]]:
        urgent: List[str] = []
        near: List[str] = []
        margin = target_signal * near_window_percent
        low, high = target_signal - margin, target_signal + margin
        for ch in channels:
            if ch in locked:
                continue
            sat = saturation.get(ch, 0)
            sig = signals[ch]
            if sat > 0 or sig < low or sig > high:
                urgent.append(ch)
            else:
                near.append(ch)
        return urgent, near


class BoundaryPolicy:
    def __init__(self, margin: int, near_scale: float, near_window_percent: float) -> None:
        self.margin = margin
        self.near_scale = near_scale
        self.near_window_percent = near_window_percent

    def margin_for(self, current_signal: Optional[float], target_signal: float) -> int:
        if current_signal is None or target_signal <= 0:
            return self.margin
        err_pct = abs(current_signal - target_signal) / target_signal
        if err_pct <= self.near_window_percent:
            scaled = int(round(self.margin * self.near_scale))
            return max(1, scaled)
        return self.margin


class SlopeSelectionStrategy:
    def __init__(self, min_signal_for_model: float, prefer_est_after_iters: int) -> None:
        self.min_signal_for_model = min_signal_for_model
        self.prefer_est_after_iters = max(0, prefer_est_after_iters)

    def choose(
        self,
        *,
        iteration: int,
        model: Optional[float],
        estimated: Optional[float],
        current_signal: float,
        target_signal: float,
    ) -> Optional[float]:
        # Weak signals → avoid slope usage
        if current_signal <= target_signal * self.min_signal_for_model:
            return None

        def valid(x: Optional[float]) -> bool:
            return x is not None and abs(x) > 0.1

        prefer_est = self.prefer_est_after_iters >= 1 and iteration >= self.prefer_est_after_iters
        if prefer_est and valid(estimated):
            return estimated
        if valid(model):
            return model
        if valid(estimated):
            return estimated
        return None


class SaturationPolicy:
    def reduce_integration(
        self,
        saturation: Dict[str, int],
        current_integration_ms: float,
        params: DetectorParams,
        polarization_mode: str = "S",  # S or P polarization
    ) -> float:
        """Reduce integration time based on saturation severity.

        CRITICAL: P-pol NEVER reduces integration time!
        P-pol transmission is always lower than S-pol, so if S-pol converged
        successfully, P-pol will never saturate starting from same values.
        """
        # P-pol: NEVER reduce integration time
        if polarization_mode.upper() == "P":
            return current_integration_ms  # No reduction for P-pol!
        
        # S-pol: Less aggressive reduction, prefer LED adjustment
        total_sat = sum(saturation.values())
        if total_sat == 0:
            return current_integration_ms

        max_sat = max(saturation.values()) if saturation else 0
        num_saturating = sum(1 for s in saturation.values() if s > 0)

        # MUCH less aggressive - prefer LED brightness reduction
        # Only cut integration when ALL channels are severely saturating
        if num_saturating == 4 and max_sat > 100:  # All 4 channels severely saturating
            factor = 0.85  # Max 15% reduction
        elif num_saturating == 4 and max_sat > 50:  # All 4 channels moderately saturating  
            factor = 0.90  # 10% reduction
        else:  # 1-3 channels saturating - minimal reduction, let LED adjustment handle it
            factor = 0.95  # Only 5% reduction

        new_time = max(params.min_integration_time, current_integration_ms * factor)
        return new_time
