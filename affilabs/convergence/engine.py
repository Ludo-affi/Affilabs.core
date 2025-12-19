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
    iteration_history: list = field(default_factory=list)  # Track iterations for analysis
    recent_integration_times: list = field(default_factory=list)  # For anti-oscillation

    def clear_for_integration_change(self) -> None:
        self.bounds.clear()
        # DON'T clear sticky_locked - preserve converged LED values across integration changes
        # self.sticky_locked.clear()
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
        sensitivity_model_path: Optional[str] = None,
        led_predictor_path: Optional[str] = None,
        convergence_predictor_path: Optional[str] = None,
    ) -> None:
        self.spectrometer = spectrometer
        self.roi = roi_extractor
        self.leds = led_actuator
        self.scheduler = scheduler
        self.log = logger

        # ML Models
        self.sensitivity_model = None
        self.led_predictor = None
        self.convergence_predictor = None

        # Load sensitivity classifier
        if sensitivity_model_path:
            try:
                import joblib
                self.sensitivity_model = joblib.load(sensitivity_model_path)
                self._log("info", f"[ML] Loaded sensitivity classifier from {sensitivity_model_path}")
            except Exception as e:
                self._log("warning", f"[ML] Could not load sensitivity classifier: {e}")

        # Load LED intensity predictor
        if led_predictor_path:
            try:
                import joblib
                self.led_predictor = joblib.load(led_predictor_path)
                self._log("info", f"[ML] Loaded LED predictor from {led_predictor_path}")
            except Exception as e:
                self._log("warning", f"[ML] Could not load LED predictor: {e}")

        # Load convergence feasibility predictor
        if convergence_predictor_path:
            try:
                import joblib
                self.convergence_predictor = joblib.load(convergence_predictor_path)
                self._log("info", f"[ML] Loaded convergence predictor from {convergence_predictor_path}")
            except Exception as e:
                self._log("warning", f"[ML] Could not load convergence predictor: {e}")

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
        use_ml_sensitivity: bool = True,
        use_ml_led_predictor: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> ConvergenceResult:
        # Predict convergence feasibility upfront (if ML model available)
        if self.convergence_predictor:
            try:
                import numpy as np
                # Prepare features: target_percent, avg_slope, min_slope, slope_imbalance, max_integration_ms
                avg_slope = 0.0
                min_slope = 0.0
                max_slope = 0.0
                if model_slopes_at_10ms:
                    slopes = list(model_slopes_at_10ms.values())
                    avg_slope = float(np.mean(slopes)) if slopes else 0.0
                    min_slope = float(np.min(slopes)) if slopes else 0.0
                    max_slope = float(np.max(slopes)) if slopes else 0.0

                slope_imbalance = max_slope / min_slope if min_slope > 0 else 1.0

                X_conv = [
                    recipe.target_percent * 100,  # target percentage
                    avg_slope,
                    min_slope,
                    max_slope,
                    slope_imbalance,
                    params.max_integration_time
                ]

                conv_prediction = self.convergence_predictor.predict([X_conv])[0]
                if conv_prediction == 0 or conv_prediction == False:  # 0 = won't converge
                    self._log("warning", "[ML] ⚠️  Convergence predictor: Target likely UNACHIEVABLE with current parameters")
                    self._log("warning", "    Consider: lower target_percent, higher max_integration_time, or check device calibration")
                else:
                    self._log("info", "[ML] ✓ Convergence predictor: Target appears ACHIEVABLE")
            except Exception as e:
                self._log("warning", f"[ML] Convergence predictor failed: {e}")

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

        # State - with smarter initial LED calculation
        initial_leds = {}
        for ch in recipe.channels:
            # Start with recipe default or 10
            led = recipe.initial_leds.get(ch, 10)

            # If we have model slopes, calculate a conservative initial LED to avoid saturation
            if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                slope_at_initial = model_slopes_at_10ms[ch] * (recipe.initial_integration_ms / 10.0)
                if slope_at_initial > 0:
                    # Calculate LED for target, then apply 75% safety factor
                    target_signal = recipe.target_percent * params.max_counts
                    predicted_led = target_signal / slope_at_initial
                    conservative_led = int(predicted_led * 0.75)  # Start conservative but not too low

                    # Use the more conservative value
                    if conservative_led < led and conservative_led >= 10:
                        led = conservative_led
                        self._log("info",
                                 f"  🔵 {ch.upper()} initial LED adjusted: {recipe.initial_leds.get(ch, 10)}→{led} "
                                 f"(75% of predicted based on slope={slope_at_initial:.1f})")

            initial_leds[ch] = led

        state = EngineState(
            integration_ms=recipe.initial_integration_ms,
            leds=initial_leds,
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

            # Progress callback removed - only major steps update progress to avoid jitter

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
                # Saturation count: Check BOTH pixel count AND max value
                # This catches cases where mean is OK but hot pixels are saturated
                roi = spec[wave_min_index:wave_max_index]
                max_pixel = float(max(roi)) if len(roi) > 0 else 0.0

                # Count saturated pixels
                sat_pixel_count = sum(1 for v in roi if v >= params.saturation_threshold)

                # CRITICAL: Check max pixel BEFORE it reaches saturation threshold
                # Saturation threshold is at 90% of max (58,981), so trigger reduction at 85% (55,705)
                # This gives headroom for reference capture with higher scan counts
                max_pixel_threshold = params.max_counts * 0.85  # 85% of max, well below 90% saturation

                if max_pixel >= max_pixel_threshold:
                    # Flag saturation even if pixel count is low
                    # Use max_pixel to determine severity for LED reduction
                    if max_pixel >= params.saturation_threshold:
                        # Already saturated - aggressive reduction needed
                        sat_pixel_count = max(sat_pixel_count, 1000)  # Force heavy reduction
                        self._log("warning", f"  🔴 {ch.upper()} MAX PIXEL SATURATED: {int(max_pixel)} counts ({max_pixel/params.max_counts*100:.1f}% of max)")
                    else:
                        # Approaching saturation - moderate reduction
                        sat_pixel_count = max(sat_pixel_count, 50)  # Force moderate reduction
                        self._log("warning", f"  ⚠️  {ch.upper()} max pixel {int(max_pixel)} at {max_pixel/params.max_counts*100:.1f}% (approaching saturation)")

                return sig, sat_pixel_count

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
            # Record iteration data for analysis phase
            state.iteration_history.append({
                'iteration': iteration,
                'integration_ms': state.integration_ms,
                'leds': dict(state.leds),
                'signals': dict(signals),
                'saturation': dict(saturation),
                'total_sat_pixels': sum(saturation.values())
            })

            # LEARNING FROM PREVIOUS ITERATIONS: Detect patterns
            iteration_trend = ""
            if len(state.iteration_history) >= 2:
                prev = state.iteration_history[-2]
                curr = state.iteration_history[-1]

                # Check if we're making progress or stuck
                prev_avg_error = sum(abs(prev['signals'][ch] - target_signal) for ch in recipe.channels) / len(recipe.channels)
                curr_avg_error = sum(abs(signals[ch] - target_signal) for ch in recipe.channels) / len(recipe.channels)

                if curr_avg_error < prev_avg_error * 0.9:
                    iteration_trend = "📈 IMPROVING"
                elif curr_avg_error > prev_avg_error * 1.1:
                    iteration_trend = "📉 GETTING WORSE"
                else:
                    iteration_trend = "➡️  STABLE"

                self._log("info", f"  {iteration_trend} (error: {curr_avg_error:.0f} counts)")

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

            # PARTIAL CONVERGENCE: If 3+ channels are acceptable, report progress
            if len(acc.acceptable) >= 3:
                remaining = [ch.upper() for ch in recipe.channels if ch not in acc.acceptable]
                self._log("info", f"  🎯 Partial convergence: {len(acc.acceptable)}/4 channels locked. Remaining: {', '.join(remaining)}")

            # Sensitivity classification (early iterations only)
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

                if use_ml_sensitivity and self.sensitivity_model:
                    # Prepare feature vector for ML model
                    X = [
                        features.integration_ms,
                        features.num_channels,
                        features.num_saturating,
                        features.total_saturated_pixels,
                        features.avg_signal_fraction_of_target,
                        features.avg_model_slope_10ms,
                    ]
                    try:
                        label = self.sensitivity_model.predict([X])[0]
                        conf = 1.0  # ML model confidence not available by default
                        reason = "ML classifier"
                    except Exception as e:
                        self._log("warning", f"[ML] Sensitivity classifier failed: {e}")
                        label, conf, reason = sensitivity_classifier.classify(features)
                else:
                    label, conf, reason = sensitivity_classifier.classify(features)

                if label == SensitivityLabel.HIGH or label == "HIGH":
                    high_sensitivity_detected = True
                    self._log("info", f"  🧭 Classifier: HIGH sensitivity (conf={conf:.2f}) [{reason}]")
                    self._log("info", f"     → Will cap integration time ≤20ms to prevent saturation spiral")

                    # PHASE 1 REFINEMENT: Lower integration immediately to reduce saturation risk
                    if state.integration_ms > 3.0:
                        state.integration_ms = 3.0
                        state.clear_for_integration_change()
                        self._log("info", f"     → Reduced integration to 3.0ms for HIGH sensitivity device")
                        continue
                else:
                    self._log("info", f"  🧭 Classifier: BASELINE (conf={conf:.2f}) [{reason}]")

            # Build locked set (sticky + current acceptable without saturation)
            # AGGRESSIVE LOCKING: Lock any channel that's in acceptable range
            for ch in acc.acceptable:
                state.sticky_locked[ch] = True

            # Unlock channels that are THEMSELVES saturating OR drifted far from target (>10%)
            locked = []
            for ch in list(state.sticky_locked.keys()):
                sat = saturation.get(ch, 0)
                sig = signals.get(ch, 0.0)
                error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0

                if sat > 0:
                    # Unlock if saturating
                    del state.sticky_locked[ch]
                elif error_pct > 0.10:
                    # Unlock if drifted >10% from target
                    self._log("info", f"  🔓 Unlocking {ch.upper()} (drifted {error_pct*100:.1f}% from target)")
                    del state.sticky_locked[ch]
                else:
                    locked.append(ch)

            # ALSO lock channels that are very close to target (within 5%) even if not formally "acceptable"
            # This prevents unnecessary micro-adjustments
            for ch in recipe.channels:
                if ch not in locked and saturation.get(ch, 0) == 0:
                    sig = signals.get(ch, 0.0)
                    error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0
                    if error_pct < 0.05:  # Within 5%
                        state.sticky_locked[ch] = True
                        locked.append(ch)
                        self._log("info", f"  🔐 {ch.upper()} locked at {state.leds[ch]} (within 5% of target: {error_pct*100:.1f}%)")

            # Log locked channels for visibility
            if locked and iteration > 1:
                locked_info = [f"{ch.upper()}@{state.leds[ch]}" for ch in locked]
                self._log("info", f"  🔒 Locked channels (converged): {', '.join(locked_info)}")

            # STRATEGY DECISION: Should we adjust integration time or LED intensities?
            # Use iteration history to make intelligent choice
            prefer_led_adjustment = False
            if len(state.iteration_history) >= 3:
                # Check last 3 iterations - if integration keeps changing but LEDs don't, prefer LED adjustment
                last_3 = state.iteration_history[-3:]
                integration_changed = len(set(round(h['integration_ms'], 1) for h in last_3)) >= 2
                leds_stable = all(
                    last_3[i]['leds'] == last_3[i+1]['leds']
                    for i in range(len(last_3)-1)
                )

                if integration_changed and leds_stable:
                    prefer_led_adjustment = True
                    self._log("info", f"  💡 Strategy: PREFER LED ADJUSTMENT (integration oscillating, LEDs stable)")

            # Early saturation handling with weakest channel protection
            if sum(saturation.values()) > 0:
                # SPECIAL CASE: All channels close to target but saturating
                # Solution: Reduce LEDs proportionally, then increase integration on next iteration
                all_saturating = len(acc.saturating) == len(recipe.channels)
                all_close_to_target = all(
                    0.85 <= signals[ch] / target_signal <= 1.05
                    for ch in recipe.channels
                ) if target_signal > 0 else False

                # Log total saturation for visibility
                total_sat_pixels = sum(saturation.values())
                self._log("info", f"  ⚠️  SATURATION DETECTED: {len(acc.saturating)}/{len(recipe.channels)} channels ({total_sat_pixels} total pixels)")

                if all_saturating and all_close_to_target:
                    self._log("info", f"  ⚠️  ALL channels close to target (85-105%) but saturating")
                    self._log("info", f"  💡 Strategy: MODEL-BASED LED reduction using SATURATED PIXEL COUNT")

                    for ch in recipe.channels:
                        old_led = state.leds[ch]
                        sig = signals[ch]
                        sat_pixels = saturation[ch]

                        # SATURATION SEVERITY: Use pixel count to determine how aggressively to reduce
                        # Few pixels (<100) = barely saturating, small reduction
                        # Many pixels (>5000) = heavily saturating, large reduction
                        if sat_pixels < 100:
                            safety_margin = 0.97  # 3% reduction
                        elif sat_pixels < 1000:
                            safety_margin = 0.93  # 7% reduction
                        elif sat_pixels < 5000:
                            safety_margin = 0.88  # 12% reduction
                        else:
                            safety_margin = 0.82  # 18% reduction

                        target_counts = target_signal * safety_margin

                        # MODEL-DRIVEN: Calculate exact LED reduction
                        if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                            slope_10ms = model_slopes_at_10ms[ch]
                            counts_per_led = slope_10ms * (state.integration_ms / 10.0)

                            # Estimate counts over target (since saturated, use safety margin)
                            counts_to_drop = sig - target_counts
                            led_reduction = counts_to_drop / counts_per_led if counts_per_led > 0 else 0

                            new_led = int(old_led - led_reduction)
                            new_led = max(10, min(255, new_led))
                            state.leds[ch] = new_led

                            self._log("info",
                                     f"     {ch.upper()}: LED {old_led}→{new_led} "
                                     f"({sat_pixels} sat pixels → {int((1-safety_margin)*100)}% reduction = Δ{int(led_reduction)})")
                        else:
                            # Fallback if no model
                            new_led = max(10, int(old_led * safety_margin))
                            state.leds[ch] = new_led
                            self._log("info", f"     {ch.upper()}: LED {old_led}→{new_led} ({sat_pixels} sat pixels → {int((1-safety_margin)*100)}%)")

                    # Continue to next iteration - integration will be increased if signals drop
                    continue

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

            # Check for LED saturation limits (max or min) preventing convergence
            # If any channel is at LED boundary and can't reach acceptance, increase integration
            if sum(saturation.values()) == 0:  # Only if no pixel saturation
                min_acceptable = target_signal - tol_signal

                # PHASE 1 REFINEMENT: If ALL channels below 80% of target for HIGH sensitivity at low integration,
                # increase integration time rather than continuing LED adjustments
                if high_sensitivity_detected and state.integration_ms < 10.0:
                    all_below_target = all(signals[ch] < target_signal * 0.80 for ch in recipe.channels)
                    if all_below_target and iteration > 3:
                        new_time = min(state.integration_ms * 1.4, 20.0)  # 40% increase, capped at 20ms
                        self._log("info", f"  ⚠️  HIGH-SENS: All channels < 80% of target at {state.integration_ms:.1f}ms")
                        self._log("info", f"  📈 Increasing integration: {state.integration_ms:.1f}ms → {new_time:.1f}ms")
                        state.integration_ms = new_time
                        state.clear_for_integration_change()
                        continue

                # Channels at MAXIMUM LED (255) but below acceptance
                maxed_below = [
                    ch for ch in recipe.channels
                    if ch not in locked and
                       state.leds[ch] >= 255 and
                       signals[ch] < min_acceptable
                ]

                # Channels at MINIMUM LED (10-15) but below acceptance
                # This happens after aggressive saturation reduction
                # For HIGH sensitivity, catch this earlier (LED ≤ 15 instead of 10)
                led_threshold = 15 if high_sensitivity_detected else 10
                minimized_below = [
                    ch for ch in recipe.channels
                    if ch not in locked and
                       state.leds[ch] <= led_threshold and
                       signals[ch] < min_acceptable
                ]

                boundary_limited = maxed_below + minimized_below
                if boundary_limited:
                    if maxed_below:
                        self._log("info", f"  ⚠️  Maxed LEDs (255) below acceptance: {maxed_below}")
                    if minimized_below:
                        self._log("info", f"  ⚠️  Minimized LEDs (10) below acceptance: {minimized_below}")

                    # DYNAMIC: Calculate integration scale from signal ratios
                    import numpy as np
                    factors = []
                    for ch in boundary_limited:
                        sig = max(1.0, signals[ch])
                        target_mid = (min_acceptable + target_signal) / 2.0
                        factor = target_mid / sig
                        factors.append(factor)

                    needed_scale = float(np.median(factors)) if factors else 1.05

                    # DYNAMIC capping based on previous iteration behavior
                    if len(state.iteration_history) >= 2:
                        prev = state.iteration_history[-2]
                        curr = state.iteration_history[-1]

                        # If we just had saturation, be more conservative
                        if prev['total_sat_pixels'] > 100:
                            needed_scale = min(needed_scale, 1.15)  # Conservative after saturation
                            self._log("info", f"    [ADAPTIVE] Limiting scale to 1.15x (prev iteration saturated)")
                        elif high_sensitivity_detected:
                            needed_scale = min(needed_scale, 1.3)  # Conservative for HIGH sens
                        else:
                            needed_scale = min(needed_scale, 1.5)  # Standard cap
                    else:
                        needed_scale = max(1.05, min(1.5, needed_scale))

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
                        # HYSTERESIS: Don't oscillate - check if we were recently near this time
                        recent_times = state.recent_integration_times[-5:] if len(state.recent_integration_times) >= 5 else []
                        if recent_times and any(abs(t - new_time) < 0.5 for t in recent_times):
                            self._log("info", f"  🔄 HYSTERESIS: Skipping integration change to {new_time:.1f}ms (was there recently)")
                        else:
                            reason = "LEDs at boundary" if (maxed_below and minimized_below) else \
                                     "maxed LEDs" if maxed_below else "minimized LEDs"
                            self._log(
                                "info",
                                f"  📈 Increasing integration: {state.integration_ms:.1f}ms → {new_time:.1f}ms ({reason} need more signal)",
                            )
                            state.integration_ms = new_time
                            state.clear_for_integration_change()
                            continue

            # ADAPTIVE INTEGRATION: Check if all channels are below target with no saturation
            # This happens after reducing LEDs to clear saturation - now we need more integration
            # BUT: Skip if strategy prefers LED adjustment
            if sum(saturation.values()) == 0 and not acc.converged and not prefer_led_adjustment:
                all_below_target = all(signals[ch] < target_signal * 0.95 for ch in recipe.channels)
                if all_below_target:
                    # DYNAMIC: Calculate exact integration needed based on weakest channel
                    import numpy as np
                    scale_factors = [target_signal / max(1.0, signals[ch]) for ch in recipe.channels]
                    needed_scale = float(np.median(scale_factors))

                    # ADAPTIVE capping based on iteration trend
                    if len(state.iteration_history) >= 3:
                        # Check if we're improving or stuck
                        recent_errors = [
                            sum(abs(h['signals'][ch] - target_signal) for ch in recipe.channels)
                            for h in state.iteration_history[-3:]
                        ]

                        improving = recent_errors[-1] < recent_errors[0] * 0.8
                        if improving:
                            # Allow larger steps when improving
                            needed_scale = min(1.4, max(1.1, needed_scale))
                        else:
                            # Smaller steps when stuck
                            needed_scale = min(1.2, max(1.05, needed_scale))
                            self._log("info", f"    [ADAPTIVE] Using smaller step (not improving)")
                    else:
                        needed_scale = min(1.3, max(1.1, needed_scale))

                    new_time = state.integration_ms * needed_scale
                    new_time = min(params.max_integration_time, new_time)

                    if high_sensitivity_detected:
                        new_time = min(new_time, 20.0)  # Cap at 20ms for HIGH sens

                    if new_time > state.integration_ms:
                        # HYSTERESIS: Don't oscillate
                        recent_times = state.recent_integration_times[-5:] if len(state.recent_integration_times) >= 5 else []
                        if recent_times and any(abs(t - new_time) < 0.5 for t in recent_times):
                            self._log("info", f"  🔄 HYSTERESIS: Skipping integration change to {new_time:.1f}ms (was there recently)")
                        else:
                            self._log("info", f"  📈 All channels < 95% target, increasing integration: {state.integration_ms:.1f}ms → {new_time:.1f}ms")
                            state.recent_integration_times.append(state.integration_ms)
                            state.integration_ms = new_time
                            state.clear_for_integration_change()
                            continue

            # MODEL-DRIVEN LED ADJUSTMENT: Use slopes to predict exact LED change needed
            # counts_per_LED = slope_at_10ms × (integration_ms / 10)
            # LED_change = counts_error / counts_per_LED

            # First pass: Calculate LED changes for all channels using model
            led_changes = {}
            for ch in recipe.channels:
                if ch in locked or saturation.get(ch, 0) > 0:
                    continue

                sig = signals.get(ch, 0)
                current_led = state.leds[ch]
                counts_error = target_signal - sig

                # Get slope at current integration time
                if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                    slope_10ms = model_slopes_at_10ms[ch]
                    counts_per_led = slope_10ms * (state.integration_ms / 10.0)

                    # Calculate exact LED change needed
                    led_delta = counts_error / counts_per_led if counts_per_led > 0 else 0
                    led_changes[ch] = {
                        'current': current_led,
                        'delta': led_delta,
                        'counts_per_led': counts_per_led,
                        'error': counts_error
                    }

            # Normalize LED changes across channels (strongest guides the rest)
            if led_changes and model_slopes_at_10ms:
                # Find strongest and weakest channels
                strongest_ch = max(model_slopes_at_10ms, key=model_slopes_at_10ms.get)
                weakest_ch = min(model_slopes_at_10ms, key=model_slopes_at_10ms.get)

                self._log("info", f"  📊 Model-based adjustment: Strongest={strongest_ch.upper()}, Weakest={weakest_ch.upper()}")

                # Adjust each channel
                for ch in recipe.channels:
                    if ch not in led_changes:
                        continue

                    info = led_changes[ch]
                    current_led = info['current']
                    led_delta = info['delta']
                    error_pct = abs(info['error']) / target_signal if target_signal > 0 else 1.0

                    # LAYERED FOCUS: Dampen adjustments based on proximity to target
                    if error_pct > 0.10:
                        # Tier 1: >10% error - Full adjustment with stability check
                        damping = 1.0
                        if len(state.iteration_history) >= 3:
                            recent = state.iteration_history[-3:]
                            signal_variance = max(h['signals'][ch] for h in recent) / max(1, min(h['signals'][ch] for h in recent))
                            if signal_variance > 1.5:
                                damping = 0.7  # Reduce if unstable
                    elif error_pct > 0.05:
                        # Tier 2: 5-10% error - Graduated damping (70% at 10%, 90% at 5%)
                        damping = 0.70 + (0.10 - error_pct) / 0.05 * 0.20
                    else:
                        # Tier 3: <5% error - Already locked, skip
                        continue

                    # Apply damping and calculate new LED
                    adjusted_delta = led_delta * damping
                    new_led = int(current_led + adjusted_delta)
                    new_led = max(10, min(255, new_led))

                    if abs(new_led - current_led) > 2:
                        tier = "TIER-1" if error_pct > 0.10 else "TIER-2"
                        self._log("info",
                                 f"  📐 {tier} {ch.upper()}: LED {current_led}→{new_led} "
                                 f"(Δ{int(adjusted_delta):+d}, {info['counts_per_led']:.1f} counts/LED, error {error_pct*100:.1f}%)")
                        state.leds[ch] = new_led

            # Fallback for channels without model slopes - use simple ratio
            for ch in recipe.channels:
                if ch in locked or saturation.get(ch, 0) > 0 or ch in led_changes:
                    continue

                sig = signals.get(ch, 0)
                current_led = state.leds[ch]
                error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 and sig > 0 else 1.0

                if sig > 0 and target_signal > 0 and error_pct > 0.05:
                    scale_factor = target_signal / sig

                    # Tier 1: FAR FROM TARGET (>10% error) - Full correction
                    if error_pct > 0.10:
                        # DYNAMIC limits based on iteration stability
                        if len(state.iteration_history) >= 3:
                            recent = state.iteration_history[-3:]
                            signal_variance = max(h['signals'][ch] for h in recent) / min(h['signals'][ch] for h in recent)

                            if signal_variance > 1.5:  # High variance = unstable
                                max_scale = 1.3  # More conservative
                                self._log("info", f"    [ADAPTIVE] Limiting scale (unstable: variance={signal_variance:.2f})")
                            else:
                                max_scale = 1.5  # Standard
                        else:
                            max_scale = 1.5

                        scale_factor = max(0.7, min(max_scale, scale_factor))
                        new_led = int(current_led * scale_factor)
                        new_led = max(10, min(255, new_led))

                        if abs(new_led - current_led) > 3:
                            self._log("info",
                                     f"  📐 TIER-1 {ch.upper()}: LED {current_led}→{new_led} "
                                     f"(error {error_pct*100:.1f}%, scale {scale_factor:.2f}x)")
                            state.leds[ch] = new_led

                    # Tier 2: MEDIUM RANGE (5-10% error) - Reduced correction
                    elif error_pct > 0.05:
                        # DYNAMIC: Reduce more as we get closer to 5%
                        # At 10% error: use 70% of correction
                        # At 5% error: use 90% of correction
                        damping = 0.70 + (0.10 - error_pct) / 0.05 * 0.20  # Linear from 70% to 90%
                        scale_factor = 1.0 + (scale_factor - 1.0) * damping
                        scale_factor = max(0.90, min(1.10, scale_factor))  # ±10% max
                        new_led = int(current_led * scale_factor)
                        new_led = max(10, min(255, new_led))

                        if abs(new_led - current_led) > 2:
                            self._log("info",
                                     f"  📐 TIER-2 {ch.upper()}: LED {current_led}→{new_led} "
                                     f"(error {error_pct*100:.1f}%, scale {scale_factor:.2f}x)")
                            state.leds[ch] = new_led

                    # Tier 3: CLOSE TO TARGET (<5% error) - Already locked above, no adjustment needed

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
                # PRIORITY 1: Respect locks - NEVER adjust locked channels
                if ch in locked:
                    self._log("info", f"  🔒 {ch.upper()} is locked - skipping adjustment")
                    continue

                # PRIORITY 2: Skip channels already in acceptable range
                if ch in acc.acceptable:
                    self._log("info", f"  ✓ {ch.upper()} already acceptable - skipping adjustment")
                    continue

                current_led = state.leds[ch]
                sig = signals[ch]
                sat = saturation.get(ch, 0)

                # SATURATION HANDLING: Use saturated pixel count to determine severity
                if sat > 0:
                    # Determine safety margin based on saturation severity (pixel count)
                    if sat < 100:
                        safety_margin = 0.97  # 3% reduction - barely saturating
                    elif sat < 1000:
                        safety_margin = 0.93  # 7% reduction - moderate
                    elif sat < 5000:
                        safety_margin = 0.88  # 12% reduction - significant
                    else:
                        safety_margin = 0.82  # 18% reduction - heavy saturation

                    target_counts = target_signal * safety_margin
                    counts_to_drop = sig - target_counts

                    # MODEL-DRIVEN: Calculate LED reduction using slopes
                    if model_slopes_at_10ms and ch in model_slopes_at_10ms and counts_to_drop > 0:
                        slope_10ms = model_slopes_at_10ms[ch]
                        counts_per_led = slope_10ms * (state.integration_ms / 10.0)
                        led_reduction = counts_to_drop / counts_per_led if counts_per_led > 0 else 0

                        # Clamp to reasonable range
                        led_reduction = max(5, min(current_led - 10, led_reduction))
                        new_led = int(current_led - led_reduction)
                        new_led = max(10, min(255, new_led))

                        self._log("warning",
                                 f"  🔴 {ch.upper()} SATURATED ({sat}px): LED {current_led}→{new_led} "
                                 f"(drop {int(counts_to_drop)} counts @ {counts_per_led:.1f} counts/LED)")
                    else:
                        # Fallback without model
                        new_led = max(10, int(current_led * safety_margin))
                        self._log("warning",
                                 f"  🔴 {ch.upper()} SATURATED ({sat}px): LED {current_led}→{new_led} (fallback {int((1-safety_margin)*100)}%)")

                    # Record this LED as a saturation boundary
                    b = state.get_bounds(ch)
                    if b.max_led_no_sat is None or current_led < b.max_led_no_sat:
                        b.max_led_no_sat = current_led

                    state.leds[ch] = new_led
                    continue  # Skip slope/ML calculation for saturated channels

                # Try ML LED predictor first (only for non-saturated channels)
                ml_led_predicted = None
                if use_ml_led_predictor and self.led_predictor:
                    try:
                        # Prepare features: channel, target_counts, integration_ms, slope_10ms, sensitivity
                        channel_encoding = {'a': 0, 'b': 1, 'c': 2, 'd': 3}.get(ch, 0)
                        slope_10ms = model_slopes_at_10ms.get(ch, 0.0) if model_slopes_at_10ms else 0.0
                        sensitivity_label = 1 if high_sensitivity_detected else 0  # 1=HIGH, 0=BASELINE

                        X_led = [
                            channel_encoding,
                            target_signal,
                            state.integration_ms,
                            slope_10ms,
                            sensitivity_label
                        ]

                        ml_led_predicted = int(self.led_predictor.predict([X_led])[0])
                        ml_led_predicted = max(10, min(255, ml_led_predicted))  # Clamp
                        self._log("info", f"    [ML] {ch.upper()} predicted LED: {ml_led_predicted}")
                    except Exception as e:
                        self._log("warning", f"[ML] LED predictor failed for {ch}: {e}")

                # If ML predicted, use it; otherwise fall back to slope-based calculation
                if ml_led_predicted is not None:
                    new_led = ml_led_predicted
                else:
                    # For HIGH sensitivity devices that recently cleared saturation,
                    # use gentler adjustments to avoid over-shooting
                    recent_saturation = iteration > 2 and high_sensitivity_detected and \
                                       any(saturation.get(c, 0) > 0 for c in recipe.channels if iteration > 1)

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

                    # DYNAMIC: After saturation, calculate precise recovery
                    if recent_saturation and current_led <= 15:
                        # Use physics: new_LED = (target / current_signal) × current_LED
                        if sig > 0:
                            scale = target_signal / sig
                            # Limit to small steps when recovering from low LEDs
                            scale = max(1.02, min(1.15, scale))
                            new_led = int(current_led * scale)
                            self._log("info", f"    [RECOVERY] {ch.upper()} LED {current_led}→{new_led} (scale {scale:.2f}x)")
                    elif slope is not None:
                        delta = error / slope

                        # DYNAMIC FINE ADJUSTMENT: Scale reduction based on error magnitude
                        error_pct = abs(error) / target_signal if target_signal > 0 else 1.0
                        if error_pct < 0.10:  # Within 10% of target
                            # Reduce proportionally: 10% error → 50% reduction, 5% error → 75% reduction
                            reduction = 0.5 + (0.05 - error_pct) / 0.05 * 0.25  # Maps 10%→50%, 5%→75%
                            reduction = max(0.5, min(0.8, reduction))
                            delta = delta * reduction
                            self._log("info", f"    [FINE] {ch.upper()} close to target - {int(reduction*100)}% step (error {error_pct*100:.1f}%)")

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

                # Only record slopes from non-saturated, reliable measurements
                if sat == 0:
                    state.slope_est.record(ch, state.leds[ch], sig)

                # Record saturation boundary if this channel saturated
                if sat > 0:
                    b = state.get_bounds(ch)
                    current_led = state.leds[ch]
                    if b.max_led_no_sat is None or current_led < b.max_led_no_sat:
                        b.max_led_no_sat = current_led
                else:
                    b = state.get_bounds(ch)
                    if b.max_led_no_sat is None or state.leds[ch] < b.max_led_no_sat:
                        b.max_led_no_sat = state.leds[ch]
                # above-target undershoot boundary
                if sig >= target_signal and saturation[ch] == 0:
                    b = state.get_bounds(ch)
                    if b.min_led_above_target is None or state.leds[ch] < b.min_led_above_target:
                        b.min_led_above_target = state.leds[ch]

        # ANALYSIS PHASE: If not converged and analysis enabled, do smart fine-tuning
        if recipe.enable_analysis_phase and len(state.iteration_history) >= 5:
            self._log("info", "\n" + "="*80)
            self._log("info", "📊 ANALYSIS PHASE: Analyzing 15 iterations for targeted fine-tuning")
            self._log("info", "="*80)

            # Analyze what went wrong
            analysis = self._analyze_convergence_failure(state, recipe, target_signal, params)

            # Apply targeted fixes based on analysis
            best_config = self._determine_optimal_config(analysis, state, recipe, target_signal)

            # Get best iteration data for reference
            best_iter_data = analysis.get('best_iter', {})

            if best_config:
                self._log("info", f"\n🎯 FINE-TUNING STRATEGY: {best_config['strategy']}")
                self._log("info", f"   Integration: {best_config['integration_ms']:.1f}ms")
                self._log("info", f"   LEDs: {best_config['leds']}")

                # Apply the optimal configuration
                state.integration_ms = best_config['integration_ms']
                state.leds = best_config['leds']
                state.clear_for_integration_change()

                # Run fine-tuning iterations
                for fine_iter in range(1, recipe.analysis_iterations + 1):
                    total_iter = recipe.max_iterations + fine_iter
                    self._log("info", f"\n--- Fine-Tune {fine_iter}/{recipe.analysis_iterations} (Total: {total_iter}) @ {state.integration_ms:.1f}ms ---")

                    # Progress callback removed - only major steps update progress to avoid jitter

                    # Measure ALL channels (always) to validate current LED settings
                    signals_fine: Dict[str, float] = {}
                    saturation_fine: Dict[str, int] = {}

                    for ch in recipe.channels:
                        # ALWAYS measure - we need current readings to validate convergence
                        spec = self.spectrometer.acquire(
                            integration_time_ms=state.integration_ms,
                            num_scans=recipe.num_scans,
                            channel=ch,
                            led_intensity=state.leds[ch],
                            use_batch_command=recipe.use_batch_command,
                        )
                        if spec is None or len(spec) == 0:
                            signals_fine[ch] = 0.0
                            saturation_fine[ch] = 0
                            continue

                        sig = float(self.roi(spec, wave_min_index, wave_max_index))
                        roi = spec[wave_min_index:wave_max_index]
                        sat = sum(1 for v in roi if v >= params.saturation_threshold)
                        signals_fine[ch] = sig
                        saturation_fine[ch] = sat

                    # Report
                    for ch in recipe.channels:
                        pct = 100.0 * signals_fine[ch] / target_signal if target_signal > 0 else 0.0
                        sat_txt = "no sat" if saturation_fine[ch] == 0 else f"SAT={saturation_fine[ch]}px"
                        self._log("info", f"  {ch.upper()}: LED={state.leds[ch]:3d} {int(signals_fine[ch]):7d} counts ({pct:5.1f}% of target) [{sat_txt}]")

                    # Check convergence
                    acc_fine = accept.evaluate(signals_fine, saturation_fine, target_signal, tol_signal, recipe)
                    if acc_fine.converged:
                        self._log("info", f"\n✅ CONVERGED in fine-tuning iteration {fine_iter}!")
                        return ConvergenceResult(state.integration_ms, dict(state.leds), dict(signals_fine), True)

                    # Minor adjustments for next fine-tune iteration (if not converged)
                    if fine_iter < recipe.analysis_iterations:
                        for ch in recipe.channels:
                            sig = signals_fine[ch]
                            sat = saturation_fine[ch]

                            # Skip saturated channels
                            if sat > 0:
                                continue

                            # Calculate error
                            error_counts = target_signal - sig
                            error_pct = abs(error_counts / target_signal) if target_signal > 0 else 0.0

                            # Only adjust if error > tolerance (no point adjusting if within tolerance)
                            if error_pct <= recipe.tolerance_percent:
                                continue

                            # MODEL-DRIVEN: Use slopes for precise adjustment
                            if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                                slope_10ms = model_slopes_at_10ms[ch]
                                counts_per_led = slope_10ms * (state.integration_ms / 10.0)
                                if counts_per_led > 0:
                                    led_adjustment = error_counts / counts_per_led
                                    # Fine-tuning: use 75% of calculated adjustment (conservative)
                                    led_adjustment = int(led_adjustment * 0.75)
                                    new_led = state.leds[ch] + led_adjustment
                                    new_led = max(10, min(255, new_led))
                                    state.leds[ch] = new_led
                                    self._log("debug", f"    Fine-tune {ch.upper()}: LED {state.leds[ch]}→{new_led} (error {error_pct*100:.1f}%)")
                            else:
                                # Fallback: proportional adjustment
                                adjustment = int(state.leds[ch] * error_pct * 0.5)
                                new_led = max(10, min(255, state.leds[ch] + adjustment))
                                state.leds[ch] = new_led

                # Return best result from fine-tuning
                return ConvergenceResult(state.integration_ms, dict(state.leds), dict(signals_fine), False)

        # Not converged - return last measured signals
        return ConvergenceResult(state.integration_ms, dict(state.leds), dict(signals), False)

    def _analyze_convergence_failure(self, state: EngineState, recipe: ConvergenceRecipe,
                                     target_signal: float, params: ConvergenceParams) -> dict:
        """Analyze why convergence failed and identify patterns."""
        history = state.iteration_history

        # Find closest approach to target
        best_iter = None
        best_distance = float('inf')
        for h in history:
            avg_pct = sum(h['signals'][ch] / target_signal for ch in recipe.channels) / len(recipe.channels)
            distance = abs(1.0 - avg_pct)
            if distance < best_distance:
                best_distance = distance
                best_iter = h

        # Detect oscillation (same integration/LED values repeating)
        oscillating = False
        last_5 = history[-5:] if len(history) >= 5 else history
        integration_values = [h['integration_ms'] for h in last_5]
        if len(set(integration_values)) <= 2 and len(last_5) >= 3:
            oscillating = True

        # Check saturation patterns
        saturation_iterations = [h for h in history if h['total_sat_pixels'] > 0]
        frequent_saturation = len(saturation_iterations) > len(history) * 0.4

        # Analyze per-channel issues
        channel_issues = {}
        for ch in recipe.channels:
            signals = [h['signals'][ch] for h in history]
            avg_pct = sum(s / target_signal for s in signals) / len(signals)
            max_signal = max(signals)
            saturated_count = sum(1 for h in history if h['saturation'][ch] > 0)

            channel_issues[ch] = {
                'avg_pct': avg_pct,
                'max_signal': max_signal,
                'max_pct': max_signal / target_signal,
                'saturated_count': saturated_count,
                'consistently_low': avg_pct < 0.70,
                'consistently_high': avg_pct > 1.10
            }

        self._log("info", f"   Best iteration: #{best_iter['iteration']} @ {best_iter['integration_ms']:.1f}ms")
        self._log("info", f"   Distance from target: {best_distance*100:.1f}%")
        self._log("info", f"   Oscillating: {oscillating}")
        self._log("info", f"   Frequent saturation: {frequent_saturation} ({len(saturation_iterations)}/{len(history)} iterations)")

        return {
            'best_iter': best_iter,
            'best_distance': best_distance,
            'oscillating': oscillating,
            'frequent_saturation': frequent_saturation,
            'saturation_iterations': len(saturation_iterations),
            'channel_issues': channel_issues,
            'history': history
        }

    def _determine_optimal_config(self, analysis: dict, state: EngineState,
                                   recipe: ConvergenceRecipe, target_signal: float) -> dict:
        """Determine optimal configuration based on analysis."""
        best_iter = analysis['best_iter']

        if analysis['oscillating']:
            # OSCILLATION FIX: Use midpoint between oscillating states
            last_5 = analysis['history'][-5:]
            integration_values = [h['integration_ms'] for h in last_5]
            unique_integrations = list(set(integration_values))

            if len(unique_integrations) == 2:
                # Oscillating between two integration times
                avg_integration = sum(unique_integrations) / 2

                # Find LED values from the iteration closest to target
                optimal_leds = dict(best_iter['leds'])

                # If best iteration was saturated, reduce LEDs slightly
                if best_iter['total_sat_pixels'] > 100:
                    for ch in recipe.channels:
                        if best_iter['saturation'][ch] > 0:
                            # Gentle 10% reduction instead of aggressive 40%
                            optimal_leds[ch] = int(optimal_leds[ch] * 0.90)

                self._log("info", f"   \ud83d\udd04 Detected oscillation between {unique_integrations[0]:.1f}ms and {unique_integrations[1]:.1f}ms")
                self._log("info", f"   Using midpoint: {avg_integration:.1f}ms")

                return {
                    'strategy': 'Oscillation fix - using midpoint integration',
                    'integration_ms': avg_integration,
                    'leds': optimal_leds
                }

        # CLOSE BUT SATURATING FIX: Slightly lower integration with slightly higher LEDs
        if best_iter and best_iter['total_sat_pixels'] > 50 and analysis['best_distance'] < 0.15:
            reduced_integration = best_iter['integration_ms'] * 0.85  # 15% lower
            adjusted_leds = {}
            for ch in recipe.channels:
                if best_iter['saturation'][ch] > 0:
                    # Reduce LED gently (10% instead of 40%)
                    adjusted_leds[ch] = int(best_iter['leds'][ch] * 0.90)
                else:
                    # Keep LEDs as-is for non-saturated channels
                    adjusted_leds[ch] = best_iter['leds'][ch]

            self._log("info", f"   \u26a0\ufe0f Best iteration saturated ({best_iter['total_sat_pixels']}px)")
            self._log("info", f"   Reducing integration to {reduced_integration:.1f}ms, LEDs by 10%")

            return {
                'strategy': 'Close but saturating - reduce both gently',
                'integration_ms': reduced_integration,
                'leds': adjusted_leds
            }

        # FAR FROM TARGET: Use best iteration's config and try small improvements
        if best_iter:
            self._log("info", f"   \ud83c\udfaf Using best iteration #{best_iter['iteration']} as starting point")
            return {
                'strategy': 'Continue from best iteration',
                'integration_ms': best_iter['integration_ms'],
                'leds': dict(best_iter['leds'])
            }

        return None
