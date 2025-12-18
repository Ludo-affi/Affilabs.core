"""Convergence Engine - Enhanced with proven elements from production stack.

MERGED ENHANCEMENTS:
- Maxed LED detection: Automatically increases integration when LEDs at 255 but below target
- Robust slope estimation: Linear regression with 3+ points, fallback to two-point
- Boundary tracking: Prevents returning to known-bad LED values (saturation/undershoot)
- Sticky locks: Channels in tolerance persist locked across iterations at same integration
- Adaptive margins: Smaller margins when near target for fine-tuning
- Sensitivity classification: Detects HIGH sensitivity devices early, caps integration ≤20ms
- Weakest channel protection: ✅ IMPLEMENTED (Dec 18, 2025) - Normalizes saturating channels
  via slope ratios when weakest channel is maxed+locked, preventing integration time reduction
  that would drop weakest channel below target. Critical for mixed-sensitivity devices.
- Near-window auto-adjust: ✅ IMPLEMENTED (Dec 18, 2025) - Automatically ensures near_window
  is never smaller than tolerance to prevent classification inconsistency. Validation happens
  in ConvergenceRecipe.__post_init__().

This engine combines the clean architecture of the original design with battle-tested
logic from thousands of successful calibrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .config import ConvergenceRecipe, DetectorParams
from .interfaces import Spectrometer, LEDActuator, ROIExtractor, Logger, Scheduler
from .estimators import SlopeEstimator
from .policies import (
    AcceptancePolicy,
    PriorityPolicy,
    BoundaryPolicy,
    SlopeSelectionStrategy,
    SaturationPolicy,
)
from .sensitivity import SensitivityClassifier, SensitivityFeatures, SensitivityLabel


@dataclass
class ConvergenceResult:
    integration_ms: float
    final_leds: Dict[str, int]
    signals: Dict[str, float]
    converged: bool


@dataclass
class ChannelBounds:
    max_led_no_sat: Optional[int] = None  # highest LED that did NOT saturate
    min_led_above_target: Optional[int] = None  # lowest LED that was above target


@dataclass
class EngineState:
    integration_ms: float
    leds: Dict[str, int]
    bounds: Dict[str, ChannelBounds] = field(default_factory=dict)
    sticky_locked: Dict[str, bool] = field(default_factory=dict)
    slope_est: SlopeEstimator = field(default_factory=SlopeEstimator)

    def clear_for_integration_change(self) -> None:
        self.bounds.clear()
        self.sticky_locked.clear()
        self.slope_est.clear()

    def get_bounds(self, ch: str) -> ChannelBounds:
        b = self.bounds.get(ch)
        if b is None:
            b = ChannelBounds()
            self.bounds[ch] = b
        return b


class ConvergenceEngine:
    def __init__(
        self,
        spectrometer: Spectrometer,
        roi_extractor: ROIExtractor,
        led_actuator: Optional[LEDActuator] = None,
        scheduler: Optional[Scheduler] = None,
        logger: Optional[Logger] = None,
    ) -> None:
        self.spectrometer = spectrometer
        self.roi = roi_extractor
        self.leds = led_actuator
        self.scheduler = scheduler
        self.log = logger

    def _log(self, level: str, msg: str) -> None:
        if self.log:
            fn = getattr(self.log, level, None)
            if callable(fn):
                try:
                    fn(msg)
                except Exception:
                    pass

    def run(
        self,
        recipe: ConvergenceRecipe,
        params: DetectorParams,
        wave_min_index: int,
        wave_max_index: int,
        model_slopes_at_10ms: Optional[Dict[str, float]] = None,
    ) -> ConvergenceResult:
        # Policies
        accept = AcceptancePolicy()
        priority = PriorityPolicy()
        boundary = BoundaryPolicy(
            margin=recipe.boundary_margin,
            near_scale=recipe.near_boundary_scale,
            near_window_percent=recipe.near_window_percent,
        )
        slope_strategy = SlopeSelectionStrategy(
            min_signal_for_model=recipe.min_signal_for_model,
            prefer_est_after_iters=recipe.prefer_est_after_iters,
        )
        saturation_policy = SaturationPolicy()
        sensitivity_classifier = SensitivityClassifier()

        # State
        state = EngineState(
            integration_ms=recipe.initial_integration_ms,
            leds={ch: recipe.initial_leds.get(ch, 10) for ch in recipe.channels},
        )
        high_sensitivity_detected = False

        target_signal = recipe.target_percent * params.max_counts
        tol_signal = recipe.tolerance_percent * params.max_counts

        # Log near-window auto-adjustment if it occurred
        if getattr(recipe, '_near_window_adjusted', False):
            original = getattr(recipe, '_near_window_original', 0.0)
            self._log("info",
                     f"  ℹ️  Near-window auto-adjusted: ±{original*100:.1f}% → ±{recipe.near_window_percent*100:.1f}% "
                     f"(matched tolerance to prevent classification inconsistency)")

        for iteration in range(1, recipe.max_iterations + 1):
            self._log("info", f"\n--- Iteration {iteration}/{recipe.max_iterations} @ {state.integration_ms:.1f}ms ---")

            # Measure all channels
            signals: Dict[str, float] = {}
            saturation: Dict[str, int] = {}

            def measure_one(ch: str) -> Tuple[float, int]:
                spec = self.spectrometer.acquire(
                    integration_time_ms=state.integration_ms,
                    num_scans=recipe.num_scans,
                    channel=ch,
                    led_intensity=state.leds[ch],
                    use_batch_command=recipe.use_batch_command,
                )
                if spec is None:
                    return 0.0, 0
                sig = float(self.roi(spec, wave_min_index, wave_max_index))
                # Saturation count: simple threshold within ROI
                roi = spec[wave_min_index:wave_max_index]
                sat = sum(1 for v in roi if v >= params.saturation_threshold)
                return sig, sat

            if self.scheduler and recipe.parallel_workers > 1:
                results = self.scheduler.map_with_timeout(
                    recipe.channels, measure_one, timeout_s=recipe.measurement_timeout_s
                )
                for ch in recipe.channels:
                    if ch in results:
                        sig, sat = results[ch]
                    else:
                        sig, sat = 0.0, 0
                    signals[ch] = sig
                    saturation[ch] = sat
            else:
                for ch in recipe.channels:
                    sig, sat = measure_one(ch)
                    signals[ch] = sig
                    saturation[ch] = sat

            # Report
            for ch in recipe.channels:
                pct = 100.0 * signals[ch] / target_signal if target_signal > 0 else 0.0
                sat_txt = "no sat" if saturation[ch] == 0 else f"SAT={saturation[ch]}px"
                self._log(
                    "info",
                    f"  {ch.upper()}: LED={state.leds[ch]:3d} {int(signals[ch]):7d} counts ({pct:5.1f}% of target) [{sat_txt}]",
                )

            # Acceptance
            acc = accept.evaluate(signals, saturation, target_signal, tol_signal, recipe)
            if acc.converged:
                self._log("info", f"\n✅ CONVERGED at iteration {iteration}!")
                return ConvergenceResult(state.integration_ms, dict(state.leds), dict(signals), True)

            # Sensitivity classification (early iterations only - MERGED FROM CURRENT STACK)
            if iteration <= 2 and not high_sensitivity_detected:
                avg_slope_10ms = 0.0
                if model_slopes_at_10ms:
                    vals = [v for v in model_slopes_at_10ms.values() if v > 0]
                    if vals:
                        import numpy as np
                        avg_slope_10ms = float(np.mean(vals))

                features = SensitivityFeatures(
                    integration_ms=state.integration_ms,
                    num_channels=len(recipe.channels),
                    num_saturating=len(acc.saturating),
                    total_saturated_pixels=sum(saturation.values()),
                    avg_signal_fraction_of_target=float(
                        sum(signals[ch] / target_signal for ch in recipe.channels) / len(recipe.channels)
                    ) if target_signal > 0 else 0.0,
                    avg_model_slope_10ms=avg_slope_10ms,
                )

                label, conf, reason = sensitivity_classifier.classify(features)
                if label == SensitivityLabel.HIGH:
                    high_sensitivity_detected = True
                    self._log("info", f"  🧭 Classifier: HIGH sensitivity (conf={conf:.2f}) [{reason}]")
                    self._log("info", f"     → Will cap integration time ≤20ms to prevent saturation spiral")
                else:
                    self._log("info", f"  🧭 Classifier: BASELINE (conf={conf:.2f}) [{reason}]")

            # Build locked set (sticky + current acceptable without saturation)
            for ch in acc.acceptable:
                state.sticky_locked[ch] = True
            locked = [ch for ch in state.sticky_locked.keys() if saturation.get(ch, 0) == 0]

            # Early saturation handling with weakest channel protection
            if sum(saturation.values()) > 0:
                # WEAKEST CHANNEL PROTECTION: Check if weakest channel is maxed and locked
                # If yes, normalize saturating channels' LEDs instead of reducing integration time
                weakest_ch = min(recipe.channels, key=lambda c: signals.get(c, 0.0))
                weakest_led = state.leds[weakest_ch]
                weakest_locked = weakest_ch in locked

                # Check if weakest is maxed and locked
                if weakest_led >= 255 and weakest_locked:
                    self._log("info", f"  ℹ️  Weakest channel {weakest_ch.upper()} at max LED (255) and locked")
                    self._log("info", f"  ℹ️  Normalizing saturating channels relative to weakest using slopes")

                    weakest_slope = None
                    if model_slopes_at_10ms and weakest_ch in model_slopes_at_10ms:
                        weakest_slope = model_slopes_at_10ms[weakest_ch] * (state.integration_ms / 10.0)

                    # Normalize saturating channels
                    for ch in acc.saturating:
                        if ch == weakest_ch:
                            continue  # Don't adjust weakest itself

                        ch_slope = None
                        if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                            ch_slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)

                        if weakest_slope and ch_slope and weakest_slope > 0 and ch_slope > 0:
                            # Normalize: LED_norm = (slope_weakest / slope_ch) × 255 × 0.97
                            normalized_led = int((weakest_slope / ch_slope) * 255)
                            new_led = int(normalized_led * 0.97)  # 3% safety margin
                            new_led = max(10, min(255, new_led))

                            self._log("info",
                                     f"  📐 {ch.upper()} LED {state.leds[ch]}→{new_led} "
                                     f"(normalized: {weakest_slope:.1f}/{ch_slope:.1f} × 255 × 0.97)")

                            state.leds[ch] = new_led
                        else:
                            # Fallback: reduce by 10% if slopes unavailable
                            new_led = int(state.leds[ch] * 0.90)
                            new_led = max(10, min(255, new_led))
                            self._log("info", f"  📐 {ch.upper()} LED {state.leds[ch]}→{new_led} (fallback: -10%)")
                            state.leds[ch] = new_led

                    # Don't reduce integration time - we adjusted LEDs instead
                    # Continue to next iteration to re-measure with new LED values
                    continue

                # Original saturation handling (reduce integration time)
                # Only executed if weakest channel is NOT maxed and locked
                new_time = saturation_policy.reduce_integration(saturation, state.integration_ms, params)
                if new_time < state.integration_ms:
                    self._log(
                        "info",
                        f"  ⏱️ Reducing integration time: {state.integration_ms:.1f}ms → {new_time:.1f}ms",
                    )
                    state.integration_ms = new_time
                    state.clear_for_integration_change()
                    continue

            # Check for maxed LEDs below acceptance threshold (MERGED FROM CURRENT STACK)
            # If any channel is at max LED and below acceptance window, increase integration
            if sum(saturation.values()) == 0:  # Only if no saturation
                min_acceptable = target_signal - tol_signal
                maxed_below = [
                    ch for ch in recipe.channels
                    if ch not in locked and
                       state.leds[ch] >= 255 and
                       signals[ch] < min_acceptable
                ]

                if maxed_below:
                    self._log("info", f"  ⚠️  Maxed LEDs below acceptance: {maxed_below}")

                    # Calculate required scale factor
                    import numpy as np
                    factors = []
                    for ch in maxed_below:
                        sig = max(1.0, signals[ch])
                        target_mid = (min_acceptable + target_signal) / 2.0
                        factors.append(target_mid / sig)

                    needed_scale = float(np.median(factors)) if factors else 1.05
                    needed_scale = max(1.05, min(2.0, needed_scale))

                    new_time = state.integration_ms * needed_scale
                    new_time = min(params.max_integration_time, new_time)
                    new_time = max(params.min_integration_time, new_time)

                    # Cap integration time for HIGH sensitivity devices (MERGED FROM CURRENT STACK)
                    if high_sensitivity_detected:
                        max_allowed = min(20.0, params.max_integration_time)
                        if new_time > max_allowed:
                            self._log("info", f"  ⚠️  HIGH sensitivity: Capping integration at {max_allowed:.1f}ms")
                            new_time = max_allowed

                    if new_time > state.integration_ms:
                        self._log(
                            "info",
                            f"  📈 Increasing integration: {state.integration_ms:.1f}ms → {new_time:.1f}ms (maxed LEDs need more signal)",
                        )
                        state.integration_ms = new_time
                        state.clear_for_integration_change()
                        continue

            # Classify adjustments
            urgent, near = priority.classify(
                channels=recipe.channels,
                signals=signals,
                saturation=saturation,
                target_signal=target_signal,
                near_window_percent=recipe.near_window_percent,
                locked=locked,
            )
            needs = urgent + near

            # Adjust
            for ch in needs:
                current_led = state.leds[ch]
                sig = signals[ch]
                # Pick slope (model scaled to integration) or estimate
                model = None
                if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                    model = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)
                est = state.slope_est.estimate(ch)
                slope = slope_strategy.choose(
                    iteration=iteration,
                    model=model,
                    estimated=est,
                    current_signal=sig,
                    target_signal=target_signal,
                )

                # Compute new LED
                error = target_signal - sig
                if slope is not None:
                    delta = error / slope
                    # clamp
                    if delta > recipe.max_led_change:
                        delta = float(recipe.max_led_change)
                    if delta < -recipe.max_led_change:
                        delta = float(-recipe.max_led_change)
                    new_led = int(current_led + delta)
                else:
                    # ratio fallback
                    ratio = (target_signal / sig) if sig > 0 else 1.5
                    if ratio < 0.5:
                        ratio = 0.5
                    if ratio > 2.0:
                        ratio = 2.0
                    new_led = int(current_led * ratio)

                # Enforce boundaries
                b = state.get_bounds(ch)
                margin = boundary.margin_for(sig, target_signal)
                # cap by saturation boundary
                if b.max_led_no_sat is not None:
                    max_safe = b.max_led_no_sat - margin
                    if new_led > max_safe:
                        new_led = max(max_safe, 10)
                # raise by undershoot boundary
                if b.min_led_above_target is not None:
                    min_safe = b.min_led_above_target + margin
                    if new_led < min_safe:
                        new_led = min_safe

                # Clamp absolute range
                new_led = max(10, min(255, new_led))

                state.leds[ch] = new_led

            # Record boundaries and slope history for next iteration
            for ch in recipe.channels:
                sig = signals[ch]
                sat = saturation[ch]
                if sat == 0:
                    state.slope_est.record(ch, state.leds[ch], sig)
                else:
                    b = state.get_bounds(ch)
                    if b.max_led_no_sat is None or state.leds[ch] < b.max_led_no_sat:
                        b.max_led_no_sat = state.leds[ch]
                # above-target undershoot boundary
                if sig >= target_signal and saturation[ch] == 0:
                    b = state.get_bounds(ch)
                    if b.min_led_above_target is None or state.leds[ch] < b.min_led_above_target:
                        b.min_led_above_target = state.leds[ch]

        # Not converged
        return ConvergenceResult(state.integration_ms, dict(state.leds), {}, False)
