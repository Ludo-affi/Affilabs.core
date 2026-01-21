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
from typing import Dict, Optional, Tuple, List
import numpy as np

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
    # QC warning flags
    qc_warnings: List[str] = None  # Warnings for QC review
    best_iteration: int = 0  # Which iteration produced this result
    max_signal_achieved_pct: float = 0.0  # Actual max signal as % of max_counts


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

    # Per-channel best brightness tracking: pick best per-channel across iterations
    best_per_channel_leds: Dict[str, int] = field(default_factory=dict)
    best_per_channel_signals: Dict[str, float] = field(default_factory=dict)
    best_per_channel_error: Dict[str, float] = field(default_factory=dict)
    best_per_channel_integration: Dict[str, float] = field(default_factory=dict)  # Track integration time per channel

    # ML context for enhanced fallback
    ml_sensitivity_detected: bool = field(default=False)
    ml_target_signal: float = field(default=0.0)

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
    # Constants for convergence thresholds
    SATURATION_THRESHOLD_RATIO = 0.85  # Trigger at 85% of max_counts (below 90% saturation)
    CONSERVATIVE_LED_FACTOR = 0.75  # Start at 75% of predicted LED for safety
    MIN_ITERATIONS_FOR_EARLY_STOP = 5  # Minimum iterations before allowing early stop
    EARLY_STOP_ERROR_THRESHOLD = 10.0  # Maximum average error % for early stopping
    FINE_TUNE_ERROR_THRESHOLD = 0.05  # Lock channels within 5% of target
    UNLOCK_DRIFT_THRESHOLD = 0.10  # Unlock if drifted >10% from target
    
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

        # Check if sklearn is available (required for ML models)
        sklearn_available = False
        try:
            import sklearn
            sklearn_available = True
        except ImportError:
            pass  # sklearn not installed - ML features will be disabled

        # Load sensitivity classifier
        if sensitivity_model_path and sklearn_available:
            try:
                import joblib
                self.sensitivity_model = joblib.load(sensitivity_model_path)
                self._log("info", f"[ML] Loaded sensitivity classifier from {sensitivity_model_path}")
            except Exception as e:
                self._log("warning", f"[ML] Could not load sensitivity classifier: {e}")

        # Load LED intensity predictor
        if led_predictor_path and sklearn_available:
            try:
                import joblib
                self.led_predictor = joblib.load(led_predictor_path)
                self._log("info", f"[ML] Loaded LED predictor from {led_predictor_path}")
            except Exception as e:
                self._log("warning", f"[ML] Could not load LED predictor: {e}")

        # Load convergence feasibility predictor
        if convergence_predictor_path and sklearn_available:
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

    def _check_early_stopping(self, iteration: int, iteration_trend: str, avg_error_pct: float, 
                              saturation: Dict[str, int], state: EngineState, signals: Dict[str, float]) -> bool:
        """Check if early stopping conditions are met.
        
        Returns True if convergence should stop early to prevent overshooting.
        """
        if iteration < self.MIN_ITERATIONS_FOR_EARLY_STOP:
            return False
            
        has_saturation = sum(saturation.values()) > 0
        is_stable_or_improving = iteration_trend in ["➡️  STABLE", "📈 IMPROVING"]
        error_is_low = avg_error_pct < self.EARLY_STOP_ERROR_THRESHOLD
        
        if not has_saturation and is_stable_or_improving and error_is_low:
            self._log("info", f"\n✅ EARLY STOP: System stable with {avg_error_pct:.1f}% error and no saturation")
            self._log("info", f"   Stopping at iteration {iteration} to prevent overshooting from model predictions")
            return True
            
        return False
    
    def _apply_led_updates(self, led_dict: Dict[str, int], locked_set: set, 
                          state: EngineState, log_prefix: str = "  📐") -> None:
        """Apply LED updates to state and log changes."""
        for ch, new_led in led_dict.items():
            if ch not in locked_set:
                old_led = state.leds[ch]
                state.leds[ch] = new_led
                self._log("info", f"{log_prefix} {ch.upper()}: LED {old_led}→{new_led}")
            else:
                self._log("info", f"{log_prefix} {ch.upper()} is locked - skipping")
    
    def _apply_saturation_fallback(self, current_led: int, sat_pixels: int, channel: str, reason: str) -> int:
        """Apply percentage-based LED reduction when slope data unavailable.

        Args:
            current_led: Current LED value
            sat_pixels: Number of saturated pixels
            channel: Channel identifier for logging
            reason: Why fallback is being used

        Returns:
            New LED value after reduction
        """
        # Determine reduction percentage based on saturation severity
        if sat_pixels < 100:
            margin = 0.98  # 2% reduction (minor saturation)
            severity = "minor"
        elif sat_pixels < 1000:
            margin = 0.93  # 7% reduction (moderate)
            severity = "moderate"
        else:
            margin = 0.85  # 15% reduction (heavy)
            severity = "heavy"

        new_led = max(10, int(current_led * margin))
        reduction_pct = int((1 - margin) * 100)
        self._log("warning",
                 f"  🔴 {channel.upper()} SATURATED ({sat_pixels}px, {severity}): "
                 f"LED {current_led}→{new_led} (-{reduction_pct}%, {reason})")
        return new_led

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
        detector_serial: Optional[int] = None,
    ) -> ConvergenceResult:
        # Log device serial for ML training correlation
        if detector_serial:
            self._log("info", f"DEVICE_SERIAL: {detector_serial}")

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
                    # Calculate LED for target, then apply safety factor
                    target_signal = recipe.target_percent * params.max_counts
                    predicted_led = target_signal / slope_at_initial
                    conservative_led = int(predicted_led * self.CONSERVATIVE_LED_FACTOR)

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

        # Store slopes for use in the algorithm (AFTER state is created)
        state.model_slopes_at_10ms = model_slopes_at_10ms or {}
        self._log("debug", f"Model slopes: {state.model_slopes_at_10ms}")
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

                # Trigger LED reduction below saturation threshold
                # Provides headroom for reference capture with higher scan counts
                max_pixel_threshold = params.max_counts * self.SATURATION_THRESHOLD_RATIO

                if max_pixel >= max_pixel_threshold:
                    # Flag saturation using max pixel value for severity-based LED reduction
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

            # Track best brightness PER CHANNEL across iterations
            # This allows combining best results from different iterations
            for ch in recipe.channels:
                ch_signal = signals[ch]
                ch_led = state.leds[ch]
                ch_sat = saturation[ch]
                ch_error = abs(ch_signal - target_signal)

                # Track channels with ZERO saturation OR minor saturation (<100 pixels)
                # Minor saturation is acceptable if it's MUCH closer to target than previous best
                is_trackable = (ch_sat == 0) or (ch_sat < 100 and ch_error < target_signal * 0.30)

                if is_trackable:
                    # Initialize on first valid measurement
                    if ch not in state.best_per_channel_error:
                        state.best_per_channel_error[ch] = ch_error
                        state.best_per_channel_leds[ch] = ch_led
                        state.best_per_channel_signals[ch] = ch_signal
                        state.best_per_channel_integration[ch] = state.integration_ms
                        sat_note = f" ({ch_sat}px sat)" if ch_sat > 0 else ""
                        self._log("debug", f"  📌 {ch.upper()}: Initial best - LED={ch_led}, signal={ch_signal:.0f} ({ch_signal/target_signal*100:.1f}%) @ {state.integration_ms:.1f}ms{sat_note}")
                    # Update if this iteration has better brightness for this channel
                    elif ch_error < state.best_per_channel_error[ch]:
                        prev_signal = state.best_per_channel_signals[ch]
                        state.best_per_channel_error[ch] = ch_error
                        state.best_per_channel_leds[ch] = ch_led
                        state.best_per_channel_signals[ch] = ch_signal
                        state.best_per_channel_integration[ch] = state.integration_ms
                        sat_note = f" ({ch_sat}px sat)" if ch_sat > 0 else ""
                        self._log("debug", f"  💡 {ch.upper()}: New best brightness - LED={ch_led}, signal={ch_signal:.0f} ({ch_signal/target_signal*100:.1f}%) @ {state.integration_ms:.1f}ms [was {prev_signal:.0f}]{sat_note}")

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

                # Calculate enhanced features for both ML and fallback
                signal_fractions = [signals[ch] / target_signal for ch in recipe.channels] if target_signal > 0 else [0.0] * len(recipe.channels)
                led_values = [state.leds[ch] for ch in recipe.channels]

                features = SensitivityFeatures(
                    integration_ms=state.integration_ms,
                    num_channels=len(recipe.channels),
                    num_saturating=len(acc.saturating),
                    total_saturated_pixels=sum(saturation.values()),
                    avg_signal_fraction_of_target=float(
                        sum(signals[ch] / target_signal for ch in recipe.channels) / len(recipe.channels)
                    ) if target_signal > 0 else 0.0,
                    avg_model_slope_10ms=avg_slope_10ms,
                    # Enhanced features from ML
                    max_signal_fraction=max(signal_fractions) if signal_fractions else 0.0,
                    min_signal_fraction=min(signal_fractions) if signal_fractions else 0.0,
                    signal_imbalance=float(np.std(signal_fractions)) if signal_fractions else 0.0,
                    avg_led=float(np.mean(led_values)) if led_values else 0.0,
                    max_led=max(led_values) if led_values else 0,
                    min_led=min(led_values) if led_values else 0,
                )

                # Try ML first (default), fallback to rule-based with enhanced features
                if use_ml_sensitivity and self.sensitivity_model:
                    X = [
                        features.integration_ms,
                        features.num_channels,
                        features.num_saturating,
                        features.total_saturated_pixels,
                        features.avg_signal_fraction_of_target,
                        features.max_signal_fraction,
                        features.min_signal_fraction,
                        features.signal_imbalance,
                        features.avg_led,
                        features.max_led,
                        features.min_led,
                    ]
                    try:
                        label = self.sensitivity_model.predict([X])[0]
                        conf = 1.0
                        reason = "ML classifier"
                        self._log("info", f"  🤖 [ML] Sensitivity: {label} (using ML model)")
                    except Exception as e:
                        self._log("warning", f"[ML] Sensitivity classifier failed: {e}")
                        self._log("info", "  🔄 [FALLBACK] Using rule-based classifier with ML features")
                        label, conf, reason = sensitivity_classifier.classify(features)
                else:
                    label, conf, reason = sensitivity_classifier.classify(features)

                if label == SensitivityLabel.HIGH or label == "HIGH":
                    high_sensitivity_detected = True
                    self._log("info", f"  🧭 Classifier: HIGH sensitivity (conf={conf:.2f}) [{reason}]")
                    self._log("info", f"     → Will cap integration time ≤20ms to prevent saturation spiral")

                    # PHASE 1 REFINEMENT: Only reduce integration if significantly over target
                    # Don't panic-reduce if channels are close to target (within 20%)
                    max_signal = max(signals.values()) if signals else 0
                    over_target_pct = (max_signal / target_signal - 1.0) if target_signal > 0 else 0

                    if state.integration_ms > 3.0 and over_target_pct > 0.25:  # Only if >25% over target
                        # Calculate proportional reduction instead of fixed drop to 3.0ms
                        # If 50% over target, reduce by 33% (multiply by 0.67)
                        # If 25% over target, reduce by 20% (multiply by 0.80)
                        reduction_factor = 1.0 / (1.0 + over_target_pct * 0.5)  # Smoother reduction
                        new_time = max(3.0, state.integration_ms * reduction_factor)

                        state.integration_ms = new_time
                        state.clear_for_integration_change()
                        self._log("info", f"     → Reduced integration to {new_time:.1f}ms (HIGH sens, {over_target_pct*100:.1f}% over target)")
                        # Update hardware integration time
                        self.spectrometer.set_integration(state.integration_ms)
                        import time
                        time.sleep(0.02)  # Brief settling delay
                        continue
                    elif over_target_pct <= 0.25:
                        self._log("info", f"     → Keeping integration at {state.integration_ms:.1f}ms (only {over_target_pct*100:.1f}% over target)")
                else:
                    self._log("info", f"  🧭 Classifier: BASELINE (conf={conf:.2f}) [{reason}]")

            # Convergence prediction (iteration 1 only, after first real signals)
            if iteration == 1 and self.convergence_predictor:
                try:
                    import numpy as np
                    # Calculate initial signal statistics
                    initial_leds = [state.leds[ch] for ch in recipe.channels]
                    signal_fractions = [signals[ch] / target_signal for ch in recipe.channels] if target_signal > 0 else [0.0] * len(recipe.channels)

                    X_conv = [
                        state.integration_ms,  # initial_integration_ms
                        recipe.target_percent * 100,  # target_percent
                        float(np.mean(initial_leds)),  # avg_initial_led
                        max(initial_leds),  # max_initial_led
                        min(initial_leds),  # min_initial_led
                        float(np.std(initial_leds)) if len(initial_leds) > 1 else 0.0,  # led_imbalance
                        float(np.mean(signal_fractions)),  # avg_signal_fraction
                        min(signal_fractions),  # min_signal_fraction
                        max(signal_fractions),  # max_signal_fraction
                        float(np.var(signal_fractions)) if len(signal_fractions) > 1 else 0.0,  # signal_variance
                        1 if sum(saturation.values()) > 0 else 0,  # early_saturation
                        sum(saturation.values()),  # total_sat_pixels
                        len(recipe.channels),  # num_channels
                        0.0,  # led_convergence_rate (not available at iteration 1)
                        0.0,  # signal_stability (not available at iteration 1)
                        0,  # oscillation_detected (not available at iteration 1)
                        0,  # phase1_iterations (not available at iteration 1)
                        0,  # phase2_iterations (not available at iteration 1)
                        0,  # phase3_iterations (not available at iteration 1)
                        # Device history features (14 features, defaults for unknown device)
                        0.0,  # device_total_calibrations
                        0.5,  # device_success_rate (neutral default)
                        6.0,  # device_avg_s_iterations (typical default)
                        4.0,  # device_avg_p_iterations (typical default)
                        10.0,  # device_avg_total_iterations
                        2.0,  # device_std_s_iterations
                        75.0,  # device_avg_fwhm (typical SPR FWHM)
                        5.0,  # device_std_fwhm
                        50.0,  # device_avg_snr (typical SNR)
                        1.0,  # device_avg_warnings
                        100.0,  # device_avg_final_led_s
                        150.0,  # device_avg_final_led_p
                        0.5,  # device_avg_convergence_rate
                        0.8,  # device_avg_stability
                        0.2,  # device_oscillation_frequency
                        30.0,  # device_days_since_last_cal
                        30.0,  # device_calibration_frequency_days
                    ]

                    conv_prediction = self.convergence_predictor.predict([X_conv])[0]
                    self._log("info", f"[ML] Convergence prediction: {conv_prediction} ({'ACHIEVABLE' if conv_prediction else 'UNACHIEVABLE'})")

                    if conv_prediction == 0 or conv_prediction == False:  # 0 = won't converge
                        self._log("warning", "[ML] ⚠️  Convergence predictor: Target likely UNACHIEVABLE with current parameters")

                        # Only trigger fallback on first attempt (not during retry)
                        if not _ml_fallback_retry:
                            self._log("warning", "🔄 [ML FALLBACK] ML predicts failure - switching to ALGORITHM-ONLY mode")
                            self._log("info", "    💡 Restarting convergence with ML disabled for full 12 iterations...")

                            # Retry with ML completely disabled
                            return self.run(
                                recipe=recipe,
                                params=params,
                                wave_min_index=wave_min_index,
                                wave_max_index=wave_max_index,
                                model_slopes_at_10ms=model_slopes_at_10ms,
                                use_ml_sensitivity=False,  # Disable ML sensitivity
                                use_ml_led_predictor=False,  # Disable ML LED predictor
                                progress_callback=progress_callback,
                                detector_serial=detector_serial,
                                _ml_fallback_retry=True,  # Mark as retry to prevent infinite loop
                            )
                        else:
                            # Already in fallback mode, just log warning
                            self._log("warning", "    ⚠️  Algorithm-only mode also predicting difficulty")
                    else:
                        self._log("info", "[ML] ✓ Convergence predictor: Target appears ACHIEVABLE")
                except Exception as e:
                    self._log("warning", f"[ML] Convergence predictor failed: {e}")

            # Build locked set (sticky + current acceptable without saturation)
            # AGGRESSIVE LOCKING: Lock any channel that's in acceptable range
            for ch in acc.acceptable:
                state.sticky_locked[ch] = True

            # Calculate metrics for ML training logging
            total_error = sum(abs(signals[ch] - target_signal) for ch in recipe.channels)
            avg_error_pct = (total_error / (target_signal * len(recipe.channels))) * 100 if target_signal > 0 else 0.0

            # Unlock channels that are THEMSELVES saturating OR drifted far from target (>10%)
            # OR are significantly above target while other channels are below
            # OR are below target when ANY channel (including locked ones) is also below target
            locked = []

            # Check if ANY channel is struggling (below target) - includes locked channels
            any_channel_below_target = any(
                signals.get(ch, 0.0) < target_signal * 0.95  # >5% below target
                for ch in recipe.channels
            )

            for ch in list(state.sticky_locked.keys()):
                sat = saturation.get(ch, 0)
                sig = signals.get(ch, 0.0)
                error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0

                # Check if any unlocked channel is significantly below target
                has_lagging_channel = any(
                    signals.get(other_ch, 0.0) < target_signal * 0.92  # >8% below target
                    for other_ch in recipe.channels
                    if other_ch not in state.sticky_locked
                )

                if sat > 0:
                    # Unlock if saturating
                    del state.sticky_locked[ch]
                elif error_pct > self.UNLOCK_DRIFT_THRESHOLD:
                    # Unlock if drifted from target
                    self._log("info", f"  🔓 Unlocking {ch.upper()} (drifted {error_pct*100:.1f}% from target)")
                    del state.sticky_locked[ch]
                elif has_lagging_channel and sig > target_signal * 1.10:
                    # Unlock if >10% over target while other channels lag significantly
                    self._log("info", f"  🔓 Unlocking {ch.upper()} (above target {(sig/target_signal-1)*100:.1f}% while others lag)")
                    del state.sticky_locked[ch]
                elif any_channel_below_target and sig < target_signal:
                    # Unlock if below target while other channels are struggling (prevents premature locking)
                    self._log("info", f"  🔓 Unlocking {ch.upper()} (below target {(sig/target_signal)*100:.1f}% while system converging)")
                    del state.sticky_locked[ch]
                else:
                    locked.append(ch)

            # ALSO lock channels that are very close to target (within 5%) even if not formally "acceptable"
            # This prevents unnecessary micro-adjustments
            # BUT: Only lock if NO channel is lagging significantly below target
            all_channels_near_target = all(
                signals.get(ch, 0.0) >= target_signal * 0.92  # Within 8% of target
                for ch in recipe.channels
            )

            for ch in recipe.channels:
                if ch not in locked and saturation.get(ch, 0) == 0:
                    sig = signals.get(ch, 0.0)
                    error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0
                    # Only lock if within threshold AND (all channels near target OR this channel is not above target)
                    can_lock = error_pct < self.FINE_TUNE_ERROR_THRESHOLD and (all_channels_near_target or sig <= target_signal * 1.02)
                    if can_lock:
                        state.sticky_locked[ch] = True
                        locked.append(ch)
                        self._log("info", f"  🔐 {ch.upper()} locked at {state.leds[ch]} (within 5% of target: {error_pct*100:.1f}%)")

            # ML TRAINING: Log iteration-level metrics (after locked is fully calculated)
            locked_count = len(locked)
            self._log("info", f"ITERATION_METRICS: total_error={total_error:.0f}, avg_error_pct={avg_error_pct:.2f}%, locked={locked_count}/{len(recipe.channels)}")

            # Log locked channels for visibility
            if locked and iteration > 1:
                locked_info = [f"{ch.upper()}@{state.leds[ch]}" for ch in locked]
                self._log("info", f"  🔒 Locked channels (converged): {', '.join(locked_info)}")

            # EARLY STOPPING: Check if system is stable with good results
            if self._check_early_stopping(iteration, iteration_trend, avg_error_pct, saturation, state, signals):
                return ConvergenceResult(
                    integration_ms=state.integration_ms,
                    final_leds=dict(state.leds),
                    signals=dict(signals),
                    converged=True
                )

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
                            # ML TRAINING: LED decision reasoning
                            self._log("info", f"    LED_DECISION: {ch.upper()} {old_led}→{new_led} (reason=saturation_model, sat_pixels={sat_pixels}, confidence=high)")
                        else:
                            # Fallback if no model
                            new_led = max(10, int(old_led * safety_margin))
                            state.leds[ch] = new_led
                            self._log("info", f"     {ch.upper()}: LED {old_led}→{new_led} ({sat_pixels} sat pixels → {int((1-safety_margin)*100)}%)")
                            # ML TRAINING: LED decision reasoning
                            self._log("info", f"    LED_DECISION: {ch.upper()} {old_led}→{new_led} (reason=saturation_fallback, sat_pixels={sat_pixels}, confidence=medium)")

                    # Continue to next iteration - integration will be increased if signals drop
                    continue

                # WEAKEST CHANNEL PROTECTION: Check if weakest channel is maxed and locked
                # If yes, normalize saturating channels' LEDs instead of reducing integration time
                weakest_ch = min(recipe.channels, key=lambda c: signals.get(c, 0.0))
                weakest_led = state.leds[weakest_ch]
                weakest_locked = weakest_ch in locked

                # Check if we should reduce saturated channel LEDs instead of integration time
                # Conditions:
                # 1. Weakest channel at max LED and locked (original protection)
                # 2. OR 3 or fewer channels saturating - reduce their LEDs instead (EXPANDED from 2)
                num_saturating = sum(1 for s in saturation.values() if s > 0)
                should_adjust_leds_not_time = (
                    (weakest_led >= 255 and weakest_locked) or  # Original protection
                    (num_saturating <= 3)  # EXPANDED: Reduce saturated LEDs if 3 or fewer channels saturating
                )

                if should_adjust_leds_not_time:
                    if weakest_led >= 255 and weakest_locked:
                        self._log("info", f"  ℹ️  Weakest channel {weakest_ch.upper()} at max LED (255) and locked")
                        self._log("info", f"  ℹ️  Normalizing saturating channels relative to weakest using slopes")
                    else:
                        self._log("info", f"  💡 {num_saturating} channel(s) saturating (≤3) - reducing their LEDs instead of cutting integration")

                    weakest_slope = None
                    if model_slopes_at_10ms and weakest_ch in model_slopes_at_10ms:
                        weakest_slope = model_slopes_at_10ms[weakest_ch] * (state.integration_ms / 10.0)

                    # Normalize/reduce saturating channels
                    for ch in acc.saturating:
                        sat_pixels = saturation[ch]

                        # Severity-based reduction factor
                        if sat_pixels < 100:
                            safety_margin = 0.97  # 3% reduction (barely saturating)
                        elif sat_pixels < 1000:
                            safety_margin = 0.93  # 7% reduction
                        elif sat_pixels < 5000:
                            safety_margin = 0.88  # 12% reduction
                        else:
                            safety_margin = 0.82  # 18% reduction (heavy saturation)

                        if ch == weakest_ch:
                            continue  # Don't adjust weakest itself

                        ch_slope = None
                        if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                            ch_slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)

                        if weakest_slope and ch_slope and weakest_slope > 0 and ch_slope > 0 and (weakest_led >= 255 and weakest_locked):
                            # Normalize: LED_norm = (slope_weakest / slope_ch) × 255 × safety
                            normalized_led = int((weakest_slope / ch_slope) * 255)
                            new_led = int(normalized_led * safety_margin)
                            new_led = max(10, min(255, new_led))

                            self._log("info",
                                     f"  📐 {ch.upper()} LED {state.leds[ch]}→{new_led} "
                                     f"(normalized: {weakest_slope:.1f}/{ch_slope:.1f} × 255 × {safety_margin:.2f}, {sat_pixels} sat px)")

                            # ML TRAINING: LED decision reasoning
                            self._log("info", f"    LED_DECISION: {ch.upper()} {state.leds[ch]}→{new_led} (reason=weakest_normalization, weakest_ratio={weakest_slope/ch_slope:.3f}, sat_pixels={sat_pixels}, confidence=high)")

                            state.leds[ch] = new_led
                        else:
                            # Just reduce by safety margin (saturation-driven reduction)
                            old_led = state.leds[ch]
                            new_led = int(old_led * safety_margin)
                            new_led = max(10, min(255, new_led))
                            self._log("info", f"  📉 {ch.upper()} LED {old_led}→{new_led} (reduce by {int((1-safety_margin)*100)}% to clear {sat_pixels} sat px)")
                            # ML TRAINING: LED decision reasoning
                            self._log("info", f"    LED_DECISION: {ch.upper()} {old_led}→{new_led} (reason=saturation_reduction, sat_pixels={sat_pixels}, confidence=high)")
                            state.leds[ch] = new_led

                    # Also boost non-saturated channels that are far below target
                    # This prevents channels like B getting stuck at 60% while we handle saturation
                    non_saturated = [ch for ch in recipe.channels if saturation.get(ch, 0) == 0 and ch not in locked]
                    for ch in non_saturated:
                        sig = signals.get(ch, 0.0)
                        error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 0.0

                        # Only boost if significantly below target (>10% error)
                        if sig < target_signal * 0.90:
                            # Try ML prediction first
                            if self.led_predictor:
                                try:
                                    sensitivity = sensitivity_encoded
                                    predicted_led = self._predict_led_intensity(ch, target_signal, state.integration_ms, sensitivity)

                                    if predicted_led is not None:
                                        # Apply damping to avoid overcorrection
                                        old_led = state.leds[ch]
                                        delta = predicted_led - old_led
                                        damping = 0.5  # Conservative 50% step
                                        new_led = int(old_led + delta * damping)
                                        new_led = max(10, min(255, new_led))

                                        self._log("info", f"  🤖 {ch.upper()} LED {old_led}→{new_led} (+{new_led-old_led}, ML boost, {error_pct*100:.1f}% below target)")
                                        self._log("info", f"    LED_DECISION: {ch.upper()} {old_led}→{new_led} (reason=ml_boost_during_saturation_handling, error_pct={error_pct*100:.1f}%, confidence=medium)")
                                        state.leds[ch] = new_led
                                        continue
                                except Exception:
                                    pass

                            # Fallback to slope-based boost
                            if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                                slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)
                                if slope > 0:
                                    needed_counts = target_signal - sig
                                    led_increase = needed_counts / slope

                                    # Apply damping
                                    old_led = state.leds[ch]
                                    new_led = int(old_led + led_increase * 0.5)  # 50% step
                                    new_led = max(10, min(255, new_led))

                                    self._log("info", f"  📈 {ch.upper()} LED {old_led}→{new_led} (+{new_led-old_led}, slope boost, {error_pct*100:.1f}% below target)")
                                    self._log("info", f"    LED_DECISION: {ch.upper()} {old_led}→{new_led} (reason=slope_boost_during_saturation_handling, error_pct={error_pct*100:.1f}%, confidence=medium)")
                                    state.leds[ch] = new_led

                    # Don't reduce integration time - we adjusted LEDs instead
                    # Continue to next iteration to re-measure with new LED values
                    continue

                # Original saturation handling (reduce integration time)
                # Only executed if multiple channels (3+) are saturating
                self._log("info", f"  ⚠️  Multiple channels ({num_saturating}) saturating - reducing integration time")
                new_time = saturation_policy.reduce_integration(
                    saturation,
                    state.integration_ms,
                    params,
                    polarization_mode=recipe.polarization_mode,  # Pass polarization mode
                )
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
                        self._log("info", f"  📊 Maxed LEDs (255) below acceptance: {maxed_below}")
                    if minimized_below:
                        self._log("info", f"  ⚠️  Minimized LEDs (10) below acceptance: {minimized_below}")

                    # AGGRESSIVE SCALING: If LEDs are maxed, we need significant integration boost
                    # Calculate needed scale from signal ratios
                    import numpy as np
                    factors = []
                    for ch in boundary_limited:
                        sig = max(1.0, signals[ch])
                        target_mid = (min_acceptable + target_signal) / 2.0
                        factor = target_mid / sig
                        factors.append(factor)

                    needed_scale = float(np.median(factors)) if factors else 2.0

                    # SMART AGGRESSIVE: Cap based on saturation risk and distance to target
                    # If current max signal is close to target, use moderate scaling
                    # If far from target and no recent saturation, use aggressive scaling
                    current_max_signal = max(signals.values()) if signals else 0
                    signal_fraction = current_max_signal / target_signal if target_signal > 0 else 0

                    if len(state.iteration_history) >= 2:
                        prev = state.iteration_history[-2]

                        # If we just had saturation, be very cautious
                        if prev['total_sat_pixels'] > 100:
                            needed_scale = min(needed_scale, 1.3)
                            self._log("info", f"    [ADAPTIVE] Limiting scale to 1.3x (prev iteration saturated)")
                        # If we're close to target (>80%), use moderate scaling
                        elif signal_fraction > 0.80:
                            needed_scale = min(needed_scale, 1.5)
                            self._log("info", f"    [ADAPTIVE] Limiting scale to 1.5x (close to target at {signal_fraction*100:.1f}%)")
                        # If far from target (<60%), use aggressive scaling
                        elif signal_fraction < 0.60:
                            needed_scale = min(needed_scale, 2.5)
                            self._log("info", f"    [ADAPTIVE] Using 2.5x scale (far from target at {signal_fraction*100:.1f}%)")
                        else:
                            # Mid-range (60-80%), use moderate-aggressive
                            needed_scale = min(needed_scale, 2.0)
                            self._log("info", f"    [ADAPTIVE] Using 2.0x scale (mid-range at {signal_fraction*100:.1f}%)")
                    else:
                        # First iteration - be moderately aggressive
                        needed_scale = min(needed_scale, 2.0)

                    new_time = state.integration_ms * needed_scale
                    new_time = min(params.max_integration_time, new_time)
                    new_time = max(params.min_integration_time, new_time)

                    # Cap integration time for HIGH sensitivity devices
                    if high_sensitivity_detected:
                        max_allowed = min(20.0, params.max_integration_time)
                        if new_time > max_allowed:
                            self._log("info", f"  ⚠️  HIGH sensitivity: Capping integration at {max_allowed:.1f}ms")
                            new_time = max_allowed

                    if new_time > state.integration_ms:
                        reason = "LEDs at boundary" if (maxed_below and minimized_below) else \
                                 "maxed LEDs" if maxed_below else "minimized LEDs"
                        self._log(
                            "info",
                            f"  📈 Increasing integration: {state.integration_ms:.1f}ms → {new_time:.1f}ms ({reason} need more signal)",
                        )
                        state.integration_ms = new_time
                        state.clear_for_integration_change()
                        continue

            # REMOVED: Adaptive integration logic that was reducing integration time
            # even when no saturation occurred. This caused Phase 2 to start at lower
            # integration times when good convergence was already achieved at higher times.

            # ============================================================================
            # PROGRESSIVE MODEL-TO-EMPIRICAL CONVERGENCE STRATEGY
            # Phase 1 (iter 1-4): 80% model / 20% empirical - Learn from data
            # Phase 2 (iter 5-8): 50% model / 50% empirical - Balanced hybrid
            # Phase 3 (iter 9-12): 20% model / 80% empirical - Trust live data
            # ============================================================================

            # Determine convergence phase and weighting
            prev_phase = state.iteration_history[-1].get('phase', 'PHASE-1') if state.iteration_history else 'PHASE-1'
            if iteration <= 4:
                phase = "PHASE-1"
                model_weight = 0.80
                empirical_weight = 0.20
            elif iteration <= 8:
                phase = "PHASE-2"
                model_weight = 0.50
                empirical_weight = 0.50
            else:
                phase = "PHASE-3"
                model_weight = 0.20
                empirical_weight = 0.80

            # ML TRAINING: Log phase transitions
            if prev_phase != phase:
                self._log("info", f"PHASE_CHANGE: {prev_phase}→{phase} (reason=iteration_threshold, locked={len(locked)}/{len(recipe.channels)})")

            self._log("info", f"  🎯 {phase}: Model {int(model_weight*100)}% / Empirical {int(empirical_weight*100)}%")

            # ============================================================================
            # CALCULATE EMPIRICAL SLOPES from iteration history
            # ============================================================================
            empirical_slopes_at_current_int = {}  # Slope at current integration time
            empirical_slopes_normalized = {}      # Slope normalized to counts/LED/ms

            if len(state.iteration_history) >= 2:
                for ch in recipe.channels:
                    if ch in locked or saturation.get(ch, 0) > 0:
                        continue

                    # Calculate slope from LED changes at SAME integration time
                    same_int_slopes = []
                    for i in range(len(state.iteration_history) - 1):
                        curr = state.iteration_history[i]
                        next_iter = state.iteration_history[i + 1]

                        if abs(curr['integration_ms'] - next_iter['integration_ms']) < 0.1:  # Same integration
                            led_delta = next_iter['leds'][ch] - curr['leds'][ch]
                            signal_delta = next_iter['signals'][ch] - curr['signals'][ch]

                            if led_delta != 0:
                                slope = signal_delta / led_delta  # counts per LED at this integration
                                if slope > 0:  # Sanity check
                                    same_int_slopes.append(slope)

                    if same_int_slopes:
                        # Average empirical slope at current integration time
                        empirical_slopes_at_current_int[ch] = sum(same_int_slopes) / len(same_int_slopes)

                        # Calculate normalized slope: counts per LED per ms
                        empirical_slopes_normalized[ch] = empirical_slopes_at_current_int[ch] / state.integration_ms
                        self._log("debug", f"  📈 {ch.upper()} empirical: {empirical_slopes_at_current_int[ch]:.1f} counts/LED")

            # ============================================================================
            # BLEND MODEL + EMPIRICAL slopes
            # ============================================================================
            blended_slopes = {}  # counts per LED at current integration time
            averaged_normalized_slopes = {}  # counts per LED per ms (for optimization)

            for ch in recipe.channels:
                if ch in locked or saturation.get(ch, 0) > 0:
                    continue

                # Model slope at current integration
                model_slope = None
                model_normalized = None
                if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                    model_slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)
                    model_normalized = model_slopes_at_10ms[ch] / 10.0  # counts per LED per ms

                # Empirical slope
                empirical_slope = empirical_slopes_at_current_int.get(ch)
                empirical_normalized = empirical_slopes_normalized.get(ch)

                # Blend slopes
                if model_slope and empirical_slope:
                    blended_slopes[ch] = (model_weight * model_slope) + (empirical_weight * empirical_slope)
                    averaged_normalized_slopes[ch] = (model_weight * model_normalized) + (empirical_weight * empirical_normalized)

                    self._log("debug",
                             f"  🔀 {ch.upper()} blended: {blended_slopes[ch]:.1f} counts/LED "
                             f"(M:{model_slope:.1f} × {model_weight:.0%}, E:{empirical_slope:.1f} × {empirical_weight:.0%})")
                elif model_slope:
                    blended_slopes[ch] = model_slope
                    averaged_normalized_slopes[ch] = model_normalized
                    self._log("debug", f"  📊 {ch.upper()} model-only: {model_slope:.1f} counts/LED")
                elif empirical_slope:
                    blended_slopes[ch] = empirical_slope
                    averaged_normalized_slopes[ch] = empirical_normalized
                    self._log("debug", f"  📈 {ch.upper()} empirical-only: {empirical_slope:.1f} counts/LED")

            # ============================================================================
            # OPTIMIZE LED + INTEGRATION TIME COMBINATION (Phase 2-3 only)
            # Use averaged slopes to find optimal (LED, integration_ms) combo
            # ============================================================================
            optimization_applied = False

            if averaged_normalized_slopes and phase in ["PHASE-2", "PHASE-3"] and iteration >= 5:
                # Calculate required LED×ms product for each channel to hit target
                # Formula: signal = slope_normalized × LED × integration_ms
                required_products = {}
                for ch in averaged_normalized_slopes:
                    if ch in locked:
                        continue

                    slope_norm = averaged_normalized_slopes[ch]
                    if slope_norm > 0:
                        # target_signal = slope_norm × LED × integration_ms
                        # LED × integration_ms = target_signal / slope_norm
                        required_products[ch] = target_signal / slope_norm

                if required_products:
                    # Find the channel that needs the MOST (LED × ms) product (limiting channel)
                    limiting_ch = max(required_products, key=required_products.get)
                    max_product = required_products[limiting_ch]

                    self._log("info", f"  🎯 Limiting channel: {limiting_ch.upper()} (needs {max_product:.0f} LED×ms)")

                    # Option 1: Keep current integration, calculate needed LED
                    option1_leds = {}
                    option1_feasible = True
                    for ch in required_products:
                        needed_led = required_products[ch] / state.integration_ms
                        if needed_led < 10 or needed_led > 255:
                            option1_feasible = False
                            break
                        option1_leds[ch] = int(needed_led)

                    # Option 2: Keep current LEDs, calculate needed integration
                    option2_integration = None
                    option2_feasible = True
                    max_needed_int = 0
                    for ch in required_products:
                        current_led = state.leds[ch]
                        if current_led < 10:
                            current_led = 10
                        needed_int = required_products[ch] / current_led
                        max_needed_int = max(max_needed_int, needed_int)

                    if max_needed_int < params.min_integration_time or max_needed_int > params.max_integration_time:
                        option2_feasible = False
                    else:
                        option2_integration = max_needed_int

                    # Option 3: Balance both - aim for mid-high LED (180) and adjust integration
                    option3_integration = None
                    option3_leds = {}
                    option3_feasible = True

                    target_led_for_limiting = 180  # Aim for high-ish LED to leave integration time reasonable
                    option3_integration = max_product / target_led_for_limiting

                    if params.min_integration_time <= option3_integration <= params.max_integration_time:
                        for ch in required_products:
                            needed_led = required_products[ch] / option3_integration
                            if needed_led < 10 or needed_led > 255:
                                option3_feasible = False
                                break
                            option3_leds[ch] = int(needed_led)
                    else:
                        option3_feasible = False

                    # Choose best option
                    chosen_option = None
                    if option1_feasible:
                        # Check if LED adjustments are reasonable (not too extreme)
                        max_led_change = max(abs(option1_leds[ch] - state.leds[ch]) for ch in option1_leds)
                        if max_led_change < 50:  # Reasonable change
                            chosen_option = "option1"

                    if chosen_option is None and option3_feasible:
                        chosen_option = "option3"

                    if chosen_option is None and option2_feasible:
                        chosen_option = "option2"

                    # Apply chosen optimization
                    if chosen_option == "option1":
                        self._log("info", f"  🎯 Optimization: Adjust LEDs (keep integration @ {state.integration_ms:.1f}ms)")
                        self._apply_led_updates(option1_leds, locked, state, log_prefix="  📐 [OPT]")
                        optimization_applied = True

                    elif chosen_option == "option2":
                        self._log("info", f"  🎯 Optimization: Adjust integration {state.integration_ms:.1f}ms → {option2_integration:.1f}ms")
                        state.integration_ms = option2_integration
                        state.clear_for_integration_change()
                        optimization_applied = True
                        continue  # Skip to next iteration with new integration time

                    elif chosen_option == "option3":
                        self._log("info", f"  🎯 Optimization: Balance both (LED & integration)")
                        self._log("info", f"      Integration: {state.integration_ms:.1f}ms → {option3_integration:.1f}ms")
                        state.integration_ms = option3_integration
                        self._apply_led_updates(option3_leds, locked, state, log_prefix="     ")
                        state.clear_for_integration_change()
                        optimization_applied = True
                        continue  # Skip to next iteration with new settings

                    else:
                        self._log("warning", "  ⚠️  Optimization infeasible - falling back to incremental")

            # ============================================================================
            # INCREMENTAL LED ADJUSTMENTS (if optimization didn't apply)
            # ============================================================================
            if not optimization_applied:
                if blended_slopes:
                    adjustments_made = False

                    for ch in recipe.channels:
                        if ch in locked or saturation.get(ch, 0) > 0:
                            continue

                        if ch not in blended_slopes:
                            continue

                        sig = signals.get(ch, 0)
                        current_led = state.leds[ch]
                        counts_error = target_signal - sig
                        error_pct = abs(counts_error) / target_signal if target_signal > 0 else 1.0

                        # Skip very small errors
                        if error_pct < 0.02:
                            continue

                        # Calculate LED delta using blended slope
                        counts_per_led = blended_slopes[ch]
                        led_delta = counts_error / counts_per_led if counts_per_led > 0 else 0

                        # Progressive damping based on error magnitude
                        if error_pct > 0.15:
                            base_damping = 0.90
                        elif error_pct > 0.10:
                            base_damping = 0.80
                        elif error_pct > 0.05:
                            base_damping = 0.70
                        else:
                            base_damping = 0.50

                        # Stability check: reduce damping if oscillating
                        if len(state.iteration_history) >= 3:
                            recent = state.iteration_history[-3:]
                            recent_signals = [h['signals'][ch] for h in recent]
                            signal_range = max(recent_signals) - min(recent_signals)
                            avg_signal = sum(recent_signals) / len(recent_signals)

                            if avg_signal > 0 and signal_range / avg_signal > 0.20:  # >20% variance
                                stability_penalty = 0.6
                                self._log("debug", f"  ⚠️  {ch.upper()} unstable - reducing step")
                            else:
                                stability_penalty = 1.0
                        else:
                            stability_penalty = 1.0

                        final_damping = base_damping * stability_penalty
                        adjusted_delta = led_delta * final_damping

                        # Clamp to reasonable step size
                        max_step = 30 if error_pct > 0.15 else 15 if error_pct > 0.10 else 8 if error_pct > 0.05 else 3
                        adjusted_delta = max(-max_step, min(max_step, adjusted_delta))

                        new_led = int(current_led + adjusted_delta)
                        new_led = max(10, min(255, new_led))

                        if abs(new_led - current_led) >= 1:
                            slope_source = "blend" if ch in empirical_slopes_at_current_int else "model"
                            # Calculate predicted counts with new LED
                            predicted_counts = sig + (new_led - current_led) * counts_per_led
                            self._log("info",
                                     f"  📐 [{phase}] {ch.upper()}: LED {current_led}→{new_led} "
                                     f"(Δ{int(adjusted_delta):+d}, {slope_source}, damp {final_damping:.0%}, err {error_pct*100:.1f}%)")
                            # ML TRAINING: Model prediction tracking
                            self._log("info", f"    MODEL_PRED: {ch.upper()} expected_counts={predicted_counts:.0f}, current={sig:.0f}, target={target_signal:.0f}, source={slope_source}")
                            # ML TRAINING: LED decision reasoning
                            self._log("info", f"    LED_DECISION: {ch.upper()} {current_led}→{new_led} (reason=model_adjustment, error_pct={error_pct*100:.2f}%, confidence=high)")
                            state.leds[ch] = new_led
                            adjustments_made = True

                    if not adjustments_made:
                        self._log("info", f"  ✓ [{phase}] Converged - no adjustments needed")

                else:
                    # Fallback ratio method if no slopes available
                    self._log("warning", f"  ⚠️  [{phase}] No slopes - using ratio fallback")

                    for ch in recipe.channels:
                        if ch in locked or saturation.get(ch, 0) > 0:
                            continue

                        sig = signals.get(ch, 0)
                        current_led = state.leds[ch]
                        error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 and sig > 0 else 1.0

                        if sig > 0 and target_signal > 0 and error_pct > 0.03:
                            scale = target_signal / sig
                            damping = 0.75 if error_pct > 0.10 else 0.60 if error_pct > 0.05 else 0.40
                            scale = 1.0 + (scale - 1.0) * damping
                            scale = max(0.70, min(1.40, scale))

                            new_led = int(current_led * scale)
                            new_led = max(10, min(255, new_led))

                            if abs(new_led - current_led) >= 1:
                                self._log("info",
                                         f"  📐 [{phase}] {ch.upper()}: LED {current_led}→{new_led} "
                                         f"(ratio {scale:.2f}x, err {error_pct*100:.1f}%)")
                                state.leds[ch] = new_led

            # ============================================================================
            # LEGACY ADJUSTMENT CODE DELETED
            # ============================================================================
            # The old LED adjustment code (lines 1282-1469) has been DELETED to prevent
            # duplicate adjustments. It was running AFTER Phase-1/2 and causing LEDs to
            # be adjusted TWICE per iteration (e.g., 34→55→79 concatenating values).
            # Phase-1/2 (lines 1175-1280) now handles all LED adjustments using slopes.
            # ============================================================================

            # Record boundaries and slope history for next iteration
            for ch in recipe.channels:
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

                # SATURATION HANDLING: Calculate exact LED reduction using model slopes
                if sat > 0:
                    # PHYSICS-BASED REDUCTION: Use model slopes to calculate exact LED change needed
                    # Formula: LED_reduction = (current_counts - safe_target) / slope

                    if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                        slope_10ms = model_slopes_at_10ms[ch]
                        counts_per_led = slope_10ms * (state.integration_ms / 10.0)

                        if counts_per_led > 0:
                            # CRITICAL: safe_target must not exceed convergence target!
                            # Otherwise signal stays above target and never converges
                            convergence_target_counts = target_signal  # This is the 85% target

                            # Determine safe target based on saturation severity
                            # But NEVER go above the convergence target
                            if sat < 100:
                                # Minor saturation: Drop just below saturation threshold + 5% safety
                                # Saturation threshold is at 90% of max_counts
                                safe_target = min(params.saturation_threshold * 0.95, convergence_target_counts)
                                approach = "gentle"
                            elif sat < 1000:
                                # Moderate saturation: Drop to 85% of max (below threshold with margin)
                                safe_target = min(params.max_counts * 0.85, convergence_target_counts)
                                approach = "moderate"
                            else:
                                # Heavy saturation: Drop to 80% of max (aggressive margin)
                                safe_target = min(params.max_counts * 0.80, convergence_target_counts)
                                approach = "aggressive"

                            # Calculate exact counts to drop
                            counts_to_drop = sig - safe_target

                            if counts_to_drop > 0:
                                # Calculate exact LED reduction from slope
                                led_reduction = counts_to_drop / counts_per_led

                                # Apply minimum reduction for safety (at least 1 LED)
                                led_reduction = max(1, int(led_reduction))

                                # Sanity check: don't reduce more than 80% of current LED
                                max_reduction = int(current_led * 0.80)
                                led_reduction = min(led_reduction, max_reduction)

                                new_led = max(10, current_led - led_reduction)

                                self._log("warning",
                                         f"  🔴 {ch.upper()} SATURATED ({sat}px, {approach}): LED {current_led}→{new_led} "
                                         f"(-{led_reduction} LED, drop {int(counts_to_drop)} counts @ {counts_per_led:.1f} counts/LED)")
                            else:
                                # Already below safe target - no reduction needed
                                new_led = current_led
                                self._log("debug", f"  {ch.upper()} sat={sat}px but signal already safe: {sig:.0f} < {safe_target:.0f}")
                        else:
                            # Slope unavailable - use percentage fallback
                            new_led = self._apply_saturation_fallback(current_led, sat, ch, "no slope data")
                    else:
                        # No model slopes - use percentage fallback
                        new_led = self._apply_saturation_fallback(current_led, sat, ch, "no model")

                    # Record this LED as a saturation boundary
                    b = state.get_bounds(ch)
                    if b.max_led_no_sat is None or current_led < b.max_led_no_sat:
                        b.max_led_no_sat = current_led

                    state.leds[ch] = new_led
                    continue  # Skip slope/ML calculation for saturated channels

                # Store ML context for fallback
                state.ml_sensitivity_detected = high_sensitivity_detected
                state.ml_target_signal = target_signal

                # Try ML LED predictor first (default approach)
                ml_led_predicted = None
                ml_features_available = False

                if use_ml_led_predictor and self.led_predictor:
                    try:
                        # Prepare features: channel, target_counts, integration_ms, sensitivity
                        channel_encoding = {'a': 0, 'b': 1, 'c': 2, 'd': 3}.get(ch, 0)
                        sensitivity_label = 1 if high_sensitivity_detected else 0  # 1=HIGH, 0=BASELINE

                        # Get model slope for this channel (scaled to current integration time)
                        model_slope = 0.0
                        if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                            model_slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)

                        # Polarization mode encoding
                        pol_mode = 1 if recipe.polarization_mode.upper() == "P" else 0  # 1=P-pol, 0=S-pol

                        X_led = [
                            channel_encoding,       # 0-3 for a/b/c/d
                            target_signal,          # Target counts
                            state.integration_ms,   # Integration time
                            sensitivity_label,      # 0=BASELINE, 1=HIGH
                            sig,                    # Current signal (counts) - NEW
                            current_led,            # Current LED value - NEW
                            model_slope,            # Channel slope at current integration - NEW
                            1.0,                    # Deprecated slope_boost (kept for ML compatibility) - LEGACY
                            pol_mode,               # Polarization mode: 0=S, 1=P - NEW
                        ]

                        ml_led_predicted = int(self.led_predictor.predict([X_led])[0])
                        ml_led_predicted = max(10, min(255, ml_led_predicted))  # Clamp

                        # VALIDATE ML PREDICTION AGAINST MODEL SLOPE (if available)
                        if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                            model_slope = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)
                            expected_counts_from_ml = model_slope * ml_led_predicted

                            # Check if ML prediction would overshoot target by >50%
                            if expected_counts_from_ml > target_signal * 1.5:
                                # Calculate model-based LED instead
                                model_led = int(target_signal / model_slope) if model_slope > 0 else ml_led_predicted
                                model_led = max(10, min(255, model_led))
                                self._log("warning", f"    ⚠️  [ML] Prediction {ml_led_predicted} would overshoot (expected {expected_counts_from_ml:.0f} vs target {target_signal:.0f})")
                                self._log("info", f"    🔧 [MODEL-AWARE] Using model-based LED {model_led} instead")
                                ml_led_predicted = model_led

                        self._log("info", f"    🤖 [ML] {ch.upper()} LED prediction: {ml_led_predicted}")
                        ml_features_available = True
                    except Exception as e:
                        self._log("warning", f"[ML] LED predictor failed for {ch}: {e}")
                        self._log("info", f"    🔄 [FALLBACK] Using slope-based LED calculation with ML context")
                        ml_features_available = True  # We have the features even if prediction failed

                # BLEND ML prediction with model-based calculation (30% ML, 70% model)
                if ml_led_predicted is not None:
                    # Calculate model-based LED for blending
                    model = None
                    if model_slopes_at_10ms and ch in model_slopes_at_10ms:
                        model = model_slopes_at_10ms[ch] * (state.integration_ms / 10.0)

                    if model and model > 0 and sig > 0:
                        # Model-based LED calculation
                        model_led = int(target_signal / model) if model > 0 else current_led
                        model_led = max(10, min(255, model_led))

                        # BLEND: 30% ML + 70% Model (reduces ML influence)
                        ml_weight = 0.30
                        model_weight = 0.70
                        new_led = int(ml_weight * ml_led_predicted + model_weight * model_led)
                        new_led = max(10, min(255, new_led))

                        self._log("info", f"    🎯 [BLEND] ML={ml_led_predicted} (30%) + Model={model_led} (70%) → {new_led}")
                    else:
                        # No model available, use ML directly
                        new_led = ml_led_predicted
                        self._log("info", f"    🤖 [ML-ONLY] Using ML prediction {new_led} (no model available)")
                else:
                    # ENHANCED FALLBACK: Use ML context for better slope-based decisions
                    # For HIGH sensitivity devices (detected by ML or rules),
                    # use gentler adjustments to avoid over-shooting
                    if ml_features_available and state.ml_sensitivity_detected:
                        self._log("debug", f"    💡 [ENHANCED] Applying HIGH-sensitivity constraints from ML")

                    recent_saturation = iteration > 2 and state.ml_sensitivity_detected and \
                                       any(saturation.get(c, 0) > 0 for c in recipe.channels if iteration > 1)

                    # If ML features were available, apply ML-informed adjustments
                    if ml_features_available and state.ml_sensitivity_detected:
                        self._log("debug", f"    💡 [ENHANCED] Applying HIGH-sensitivity constraints from ML")

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

        # Not converged - return per-channel best if all from SAME integration time
        if state.best_per_channel_leds:
            # Check if all per-channel best are from same integration time
            integration_times = set(state.best_per_channel_integration.values())

            if len(integration_times) == 1:
                # All from same integration time - use per-channel best
                best_integration = list(integration_times)[0]
                final_leds = dict(state.best_per_channel_leds)
                final_signals = dict(state.best_per_channel_signals)

                # Boost LED for channels below target
                # Use OBSERVED signal/LED ratio from THIS channel's data (device-agnostic)
                for ch in recipe.channels:
                    sig = final_signals[ch]
                    led = final_leds[ch]

                    if sig < target_signal * 0.90 and led < 255:  # Only boost if below 90% of target
                        # Calculate needed LED using observed linear relationship
                        # At current LED: signal = sig
                        # At needed LED: signal = target_signal
                        # Assuming linear: target_signal / sig = led_needed / led
                        # Therefore: led_needed = led * (target_signal / sig)

                        ratio = target_signal / sig if sig > 0 else 1.15
                        led_needed = int(led * ratio)
                        led_needed = min(255, max(led + 5, led_needed))  # At least +5, max 255

                        self._log("info", f"   📈 Boosting {ch.upper()} LED: {led} → {led_needed} (signal {sig:.0f} → ~{target_signal:.0f})")
                        final_leds[ch] = led_needed
                        # Estimate new signal using same linear ratio
                        final_signals[ch] = sig * ratio

                self._log("info", f"\n📊 Using PER-CHANNEL best brightness (all from {best_integration:.1f}ms, boosted where needed):")
                for ch in recipe.channels:
                    pct = (final_signals[ch] / target_signal * 100) if target_signal > 0 else 0
                    self._log("info", f"   {ch.upper()}: LED={final_leds[ch]:3d}, signal={final_signals[ch]:7.0f} counts ({pct:5.1f}% of target)")

                # Use the integration time from per-channel best
                final_integration = best_integration
            else:
                # Mixed integration times - use final iteration complete result
                final_leds = dict(state.leds)
                final_signals = dict(signals)
                final_integration = state.integration_ms

                self._log("warning", f"\n⚠️  Per-channel best from mixed integration times - using final iteration")
                self._log("info", f"\n📊 Using final iteration LEDs (complete set at {state.integration_ms:.1f}ms):")
                for ch in recipe.channels:
                    pct = (final_signals[ch] / target_signal * 100) if target_signal > 0 else 0
                    self._log("info", f"   {ch.upper()}: LED={final_leds[ch]:3d}, signal={final_signals[ch]:7.0f} counts ({pct:5.1f}% of target)")

            # Calculate QC metrics using final combined results
            qc_warnings = []
            max_signal = max(final_signals.values()) if final_signals else 0
            max_signal_pct = (max_signal / params.max_counts) * 100 if params.max_counts > 0 else 0
            target_pct = recipe.target_percent * 100

            # Determine if close enough to accept as success
            # Require strict adherence to target - no relaxed acceptance
            target_gap = abs(max_signal_pct - target_pct)

            # STRICT: Accept only if ALL channels are within tolerance
            # Individual channel check - each must be within tolerance (±15% for most recipes)
            all_channels_acceptable = True
            acceptance_tolerance = max(recipe.tolerance_percent, 0.15)  # Use recipe tolerance or 15%, whichever is larger

            for ch in recipe.channels:
                sig = final_signals.get(ch, 0)
                sig_pct = (sig / target_signal * 100) if target_signal > 0 else 0
                error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0

                # Channel is acceptable if within tolerance
                if error_pct > acceptance_tolerance:
                    all_channels_acceptable = False
                    self._log("warning", f"{ch.upper()}: error {error_pct*100:.1f}% exceeds tolerance {acceptance_tolerance*100:.1f}%")
                    break

            # Accept convergence only if average is within 5% of target
            converged_best_effort = (target_gap <= 5.0) and all_channels_acceptable

            # Check each channel for warnings
            for ch in recipe.channels:
                sig = final_signals.get(ch, 0)
                led = final_leds.get(ch, 0)
                sig_pct = (sig / target_signal * 100) if target_signal > 0 else 0
                error_pct = abs(sig - target_signal) / target_signal if target_signal > 0 else 1.0

                if error_pct > recipe.tolerance_percent:
                    if sig_pct < 90:
                        qc_warnings.append(f"Channel {ch.upper()}: Low signal ({sig_pct:.1f}% of target)")
                    elif sig_pct > 115:
                        qc_warnings.append(f"Channel {ch.upper()}: High signal ({sig_pct:.1f}% of target)")

                if led >= 255:
                    qc_warnings.append(f"Channel {ch.upper()}: Maxed LED (possible weak channel or LED degradation)")

            # Add target gap warning
            if not converged_best_effort:
                qc_warnings.append(f"Target not reached: {max_signal_pct:.1f}% achieved vs {target_pct:.1f}% target (short by {target_gap:.1f}%)")
            elif target_gap > 1.0:
                qc_warnings.append(f"Near-target: {max_signal_pct:.1f}% vs {target_pct:.1f}% target (\u2206{target_gap:.1f}%)")

            # Log result
            if converged_best_effort:
                self._log("info", f"\n\u2705 CONVERGED (BEST EFFORT) - iteration {iteration} (combined per-channel best)")
                if qc_warnings:
                    self._log("warning", f"   \u26a0\ufe0f  QC Review Recommended: {len(qc_warnings)} warning(s)")
            else:
                self._log("warning", f"\n\u26a0\ufe0f  PARTIAL CONVERGENCE - returning BEST iteration (combined per-channel best)")
                self._log("info", f"   Max signal achieved: {max_signal_pct:.1f}%, target: {target_pct:.1f}%")

            self._log("info", f"   Final integration time: {final_integration:.1f}ms")

            if qc_warnings:
                self._log("warning", "   QC Warnings:")
                for warning in qc_warnings:
                    self._log("warning", f"     \u2022 {warning}")

            return ConvergenceResult(
                final_integration,
                final_leds,  # Use per-channel best (if same integration) or final iteration
                final_signals,  # Use per-channel best (if same integration) or final iteration
                converged_best_effort,  # True if within strict criteria
                qc_warnings=qc_warnings if qc_warnings else [],
                best_iteration=iteration,
                max_signal_achieved_pct=max_signal_pct,
            )
        else:
            # Fallback if no iterations completed
            return ConvergenceResult(
                state.integration_ms,
                dict(state.leds),
                dict(signals),
                False,
                qc_warnings=["No valid iterations completed"],
                best_iteration=0,
                max_signal_achieved_pct=0.0,
            )

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
