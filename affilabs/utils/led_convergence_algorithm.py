"""LED Convergence Algorithm - Clean rewrite.

Simple, device-agnostic convergence loop:
1. Measure all channels
2. Check convergence (all in tolerance + zero saturation)
3. For each channel needing adjustment:
   - If saturating: reduce LED (and possibly integration time)
   - If too low: increase LED using linear model
4. Apply boundaries (never return to known-bad LED values)
5. Repeat until converged or max iterations
"""

from __future__ import annotations

import time
import numpy as np
from typing import Dict, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from .led_convergence_core import (
    ConvergenceConfig,
    ConvergenceState,
    DetectorParams,
    AcquireSpectrumFn,
    ROISignalFn,
    _log,
    calculate_integration_time_reduction,
    calculate_led_adjustment,
    calculate_saturation_recovery,
    check_convergence,
    measure_channel,
)
# Note: No device-specific classifiers in the core algorithm.
# Device sensitivity handling (ML/rule-based) is handled upstream
# in orchestrators/adapters when needed.


def LEDconverge(
    usb: object,
    ctrl: object,
    ch_list: List[str],
    led_intensities: Dict[str, int],
    acquire_raw_spectrum_fn: AcquireSpectrumFn,
    roi_signal_fn: ROISignalFn,
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 15,
    step_name: str = "Step 4",
    use_batch_command: bool = True,
    model_slopes: Optional[Dict[str, float]] = None,
    polarization: str = "S",
    config: Optional[ConvergenceConfig] = None,
    logger: Optional[object] = None,
) -> Tuple[float, Dict[str, float], bool]:
    """LED convergence to target signal with zero saturation tolerance.

    Args:
        usb: USB device handle
        ctrl: Controller instance
        ch_list: List of channel names (e.g., ['a', 'b', 'c', 'd'])
        led_intensities: Starting LED intensities per channel
        acquire_raw_spectrum_fn: Function to acquire spectrum
        roi_signal_fn: Function to extract ROI signal from spectrum
        initial_integration_ms: Starting integration time
        target_percent: Target signal as fraction of detector max (e.g., 0.85 for 85%)
        tolerance_percent: Tolerance as fraction (e.g., 0.05 for ±5%)
        detector_params: DetectorParams with max_counts, saturation_threshold, time limits
        wave_min_index: ROI start index
        wave_max_index: ROI end index
        max_iterations: Maximum convergence iterations
        step_name: Name for logging
        use_batch_command: Use batch LED command
        model_slopes: Dict of counts_per_led slopes at 10ms (scaled for current integration)
        polarization: Polarization state for logging
        config: ConvergenceConfig instance (uses default if None)
        logger: Logger instance

    Returns:
        (final_integration_time, final_signals_dict, converged)
    """
    if config is None:
        config = ConvergenceConfig()

    # Initialize state
    state = ConvergenceState()
    integration_ms = initial_integration_ms

    # Convergence policy flags
    freeze_integration = bool(getattr(config, "FREEZE_INTEGRATION", False))
    allow_increase_only = bool(getattr(config, "ALLOW_INTEGRATION_INCREASE_ONLY", False))

    # Calculate target signal in counts
    target_signal = target_percent * detector_params.max_counts
    tolerance_signal = tolerance_percent * detector_params.max_counts

    _log(logger, "info", f"\n{'='*80}")
    _log(logger, "info", f"{step_name}: LED Convergence - {polarization} polarization")
    _log(logger, "info", f"  Target: {target_signal:.0f} counts ({target_percent*100:.1f}% of {detector_params.max_counts:.0f})")
    _log(logger, "info", f"  Tolerance: ±{tolerance_signal:.0f} counts (±{tolerance_percent*100:.1f}%)")
    _log(logger, "info", f"  Saturation threshold: {detector_params.saturation_threshold:.0f} counts (ZERO pixels allowed)")
    _log(logger, "info", f"  Starting integration time: {integration_ms:.1f}ms")
    _log(logger, "info", f"  Starting LEDs: {led_intensities}")
    _log(logger, "info", f"{'='*80}\n")

    # Device-agnostic: no sensitivity classification in this core loop.

    # CRITICAL: Track weakest LED priority and integration time lock
    weakest_led_at_max = False
    integration_locked = False
    locked_integration_time = None

    # Main convergence loop
    for iteration in range(1, max_iterations + 1):
        _log(logger, "info", f"\n--- Iteration {iteration}/{max_iterations} @ {integration_ms:.1f}ms ---")

        # Update integration time in state (clears boundaries if changed)
        state.update_integration_time(integration_ms, logger)

        # STEP 1: Measure all channels (non-blocking with timeout support)
        signals = {}
        sat_per_ch = {}
        spectra = {}
        early_sat_detected = False

        def _measure_one(channel: str) -> Tuple[str, int, Optional[float], int, Optional[object]]:
            led = led_intensities[channel]
            return (
                channel,
                led,
                *measure_channel(
                    usb=usb,
                    ctrl=ctrl,
                    channel=channel,
                    led_intensity=led,
                    integration_ms=integration_ms,
                    acquire_spectrum_fn=acquire_raw_spectrum_fn,
                    roi_signal_fn=roi_signal_fn,
                    wave_min_index=wave_min_index,
                    wave_max_index=wave_max_index,
                    saturation_threshold=detector_params.saturation_threshold,
                    use_batch=use_batch_command,
                ),
            )

        if config.PARALLEL_MEASUREMENTS:
            max_workers = max(1, config.MAX_MEASURE_WORKERS or 1)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_measure_one, ch): ch for ch in ch_list}
                for future in futures:
                    ch = futures[future]
                    try:
                        ch_name, led, signal, sat_pixels, spectrum = future.result(timeout=config.MEASUREMENT_TIMEOUT_S)
                    except FuturesTimeoutError:
                        _log(logger, "error", f"  ⏱️ {ch.upper()} measurement timed out ({config.MEASUREMENT_TIMEOUT_S:.1f}s)")
                        return integration_ms, {}, False
                    except Exception as e:  # pylint: disable=broad-except
                        _log(logger, "error", f"  ❌ {ch.upper()} measurement error: {e}")
                        return integration_ms, {}, False

                    if signal is None:
                        _log(logger, "error", f"  ❌ {ch.upper()} measurement failed")
                        return integration_ms, {}, False

                    signals[ch_name] = signal
                    sat_per_ch[ch_name] = sat_pixels
                    spectra[ch_name] = spectrum

                    signal_pct = (signal / target_signal) * 100.0
                    sat_str = f"SAT={sat_pixels}px" if sat_pixels > 0 else "no sat"
                    _log(logger, "info", f"  {ch_name.upper()}: LED={led:3d} → {signal:7.0f} counts ({signal_pct:5.1f}% of target) [{sat_str}]")
                    if sat_pixels == 0:
                        state.record_non_saturated_point(ch_name, led, signal)
        else:
            for ch in ch_list:
                ch_name, led, signal, sat_pixels, spectrum = _measure_one(ch)
                if signal is None:
                    _log(logger, "error", f"  ❌ {ch.upper()} measurement failed")
                    return integration_ms, {}, False
                signals[ch_name] = signal
                sat_per_ch[ch_name] = sat_pixels
                spectra[ch_name] = spectrum
                signal_pct = (signal / target_signal) * 100.0
                sat_str = f"SAT={sat_pixels}px" if sat_pixels > 0 else "no sat"
                _log(logger, "info", f"  {ch_name.upper()}: LED={led:3d} → {signal:7.0f} counts ({signal_pct:5.1f}% of target) [{sat_str}]")
                # Record slope history for non-saturated point
                if sat_pixels == 0:
                    state.record_non_saturated_point(ch_name, led, signal)
                else:
                    early_sat_detected = True
                    break

        # If sequential and early saturation detected, reduce integration and retry
        # CRITICAL: Respect FREEZE_INTEGRATION flag - P-MODE MUST NEVER REDUCE INTEGRATION!
        # P-mode should maintain S-mode integration time and only adjust LEDs
        if (not config.PARALLEL_MEASUREMENTS) and early_sat_detected:
            if not freeze_integration and not allow_increase_only:
                _log(logger, "info", "  ⚠️ Early saturation detected - reducing integration time")
                new_integration = calculate_integration_time_reduction(
                    sat_per_ch=sat_per_ch,
                    current_integration=integration_ms,
                    detector_params=detector_params,
                    config=config,
                    logger=logger,
                )
                if new_integration < integration_ms:
                    integration_ms = new_integration
                    # Restart iteration after integration change
                    yield_cb = getattr(config, "YIELD_CALLBACK", None)
                    if yield_cb is not None:
                        try:
                            yield_cb()
                        except Exception:
                            pass
                    # No sleep needed - hardware timing already handled in measurement
                    continue
            else:
                # Integration frozen - log and let main saturation handler reduce LEDs instead
                _log(logger, "info", f"  🔒 Early saturation detected but integration FROZEN at {integration_ms:.1f}ms")
                _log(logger, "info", "  ℹ️ Will reduce saturating channel LEDs instead (continuing to convergence check)")
            # Fall through to convergence check - don't continue/restart iteration

        # STEP 2: Check convergence
        # For clarity, compute acceptance window in both counts and % of target
        min_signal = target_signal - tolerance_signal
        max_signal = target_signal + tolerance_signal
        # Also compute a wider "near" window (e.g., ±10%) for prioritization
        # Ensure near window percent is not smaller than tolerance percent
        configured_near_percent = getattr(config, "NEAR_WINDOW_PERCENT", 0.10)
        effective_near_percent = max(configured_near_percent, tolerance_percent)
        if effective_near_percent > configured_near_percent:
            _log(logger, "info", f"  Adjusted near window from ±{configured_near_percent*100:.1f}% to ±{effective_near_percent*100:.1f}% to match tolerance")
        near_margin = target_signal * effective_near_percent
        near_lower = target_signal - near_margin
        near_upper = target_signal + near_margin
        lower_pct_of_target = (min_signal / target_signal) * 100.0 if target_signal > 0 else 0.0
        upper_pct_of_target = (max_signal / target_signal) * 100.0 if target_signal > 0 else 0.0
        _log(logger, "info", f"  Acceptance window: {min_signal:.0f}..{max_signal:.0f} counts ({lower_pct_of_target:.2f}%..{upper_pct_of_target:.2f}% of target)")
        _log(logger, "info", f"  Near window: {near_lower:.0f}..{near_upper:.0f} counts (±{effective_near_percent*100:.1f}% of target)")

        # Note: second value is list of ACCEPTABLE channels (in tolerance OR above without saturation)
        converged, channels_acceptable, channels_saturating = check_convergence(
            signals=signals,
            sat_per_ch=sat_per_ch,
            target_signal=target_signal,
            tolerance_signal=tolerance_signal,
            config=config,
        )

        # Device-agnostic: no sensitivity classification in algorithm.
        # Integration time behavior is controlled by recipe/config and detector params.

        if converged:
            _log(logger, "info", f"\n✅ CONVERGED at iteration {iteration}!")
            _log(logger, "info", "   All channels in tolerance + zero saturation")
            _log(logger, "info", f"   Final integration time: {integration_ms:.1f}ms")
            _log(logger, "info", f"   Final LEDs: {led_intensities}")
            return integration_ms, signals, True

        # Identify locked channels: ACCEPTABLE AND zero saturation
        # Channels with saturation MUST be adjusted even if acceptable
        locked_channels = set()
        for ch in channels_acceptable:
            if sat_per_ch.get(ch, 0) == 0:
                locked_channels.add(ch)
                # Promote to sticky lock at this integration time
                state.lock_channel(ch)

        # Merge with sticky locks (persist from prior iterations at same integration)
        locked_channels |= set([ch for ch in state.get_locked() if sat_per_ch.get(ch, 0) == 0])

        # Determine weakest channel with optional override from config
        # If config.WEAKEST_CHANNEL_OVERRIDE is provided (e.g., from S-pol), honor it across polarizations
        weakest_override = getattr(config, "WEAKEST_CHANNEL_OVERRIDE", None) if config is not None else None
        if weakest_override in ch_list:
            weakest_ch = weakest_override
            _log(logger, "info", f"  🎯 Using weakest channel override from previous polarization: {weakest_ch.upper()}")
        else:
            # Avoid lambda capturing loop-local dict to satisfy linters
            weakest_ch = ch_list[0] if ch_list else ""
            weakest_val = signals.get(weakest_ch, 0.0) if weakest_ch else 0.0
            for _c in ch_list[1:]:
                _v = signals.get(_c, 0.0)
                if _v < weakest_val:
                    weakest_ch = _c
                    weakest_val = _v

        weakest_led = led_intensities.get(weakest_ch, 0)
        weakest_signal = signals.get(weakest_ch, 0.0)

        # CRITICAL: Lock integration time when weakest LED hits max (255)
        # This prevents oscillation - other channels will adjust LEDs to match
        # Don't wait for weakest to be "in tolerance" - lock immediately when it maxes out
        if weakest_led >= config.MAX_LED and not integration_locked:
            integration_locked = True
            locked_integration_time = integration_ms
            _log(logger, "info", f"\n🔒 INTEGRATION TIME LOCKED: {weakest_ch.upper()} at max LED={weakest_led}")
            _log(logger, "info", f"   Signal: {weakest_signal:.0f} counts ({weakest_signal/target_signal*100:.1f}% of target)")
            _log(logger, "info", f"   Integration time LOCKED at {integration_ms:.1f}ms")
            _log(logger, "info", "   Remaining iterations will ONLY adjust other channel LEDs\n")

        # Classify remaining channels into priority groups
        urgent_channels = []  # outside ±10% OR any saturation
        near_channels = []    # within ±10% but outside tolerance, zero saturation

        for ch in ch_list:
            if ch in locked_channels:
                continue
            sig = signals[ch]
            sat = sat_per_ch.get(ch, 0)
            if sat > 0 or (sig < near_lower) or (sig > near_upper):
                urgent_channels.append(ch)
            else:
                # Not locked, within near window, zero saturation → near
                near_channels.append(ch)

        # Needs adjustment are urgent first, then near
        needs_adjustment = urgent_channels + near_channels

        # Record boundaries for locked channels (LEDs that give good signal)
        for ch in locked_channels:
            state.record_above_target(ch, led_intensities[ch], logger=None)

        # Log convergence status
        if logger is not None:
            in_tol_str = ", ".join([ch.upper() for ch in locked_channels]) if locked_channels else "none"
            urgent_str = ", ".join([ch.upper() for ch in urgent_channels]) if urgent_channels else "none"
            near_str = ", ".join([ch.upper() for ch in near_channels]) if near_channels else "none"
            sat_str = ", ".join([ch.upper() for ch in channels_saturating]) if channels_saturating else "none"
            _log(logger, "info", f"  🔒 LOCKED (≤±{tolerance_percent*100:.1f}% & no sat): [{in_tol_str}]")
            _log(logger, "info", f"  🚩 PRIORITY (sat or >±{getattr(config, 'NEAR_WINDOW_PERCENT', 0.10)*100:.0f}%): [{urgent_str}]")
            _log(logger, "info", f"  🟡 NEAR (within ±{getattr(config, 'NEAR_WINDOW_PERCENT', 0.10)*100:.0f}% but outside tolerance): [{near_str}]")
            _log(logger, "info", f"  ⚠️  SATURATING: [{sat_str}]")
            # Skipping detailed per-channel reasons to keep output concise here

        # STEP 3: Handle saturation (reduce LED intensities OR integration time)
        # CRITICAL P-MODE POLICY: If freeze_integration=True (P-mode), NEVER reduce integration!
        # P-mode MUST maintain S-mode integration time. Only LED adjustment allowed.
        total_sat = sum(sat_per_ch.values())
        if total_sat > 0:
            # CRITICAL: If integration time is locked OR policy forbids reduction,
            # NEVER reduce integration. Instead, ALWAYS reduce saturating channel LEDs.
            if integration_locked or freeze_integration or allow_increase_only:
                if freeze_integration:
                    _log(logger, "info", f"  🔒 P-MODE FREEZE POLICY ACTIVE - Integration LOCKED at {integration_ms:.1f}ms")
                    _log(logger, "info", f"     P-mode inherits S-mode integration time and NEVER reduces it")
                else:
                    _log(logger, "info", f"  🔒 Integration time LOCKED at {locked_integration_time:.1f}ms")
                _log(logger, "info", f"  ℹ️ Weakest channel {weakest_ch.upper()} locked at max LED ({weakest_led})")
                _log(logger, "info", "  ℹ️ Reducing saturating channels' LEDs (integration time unchanged)")

                weakest_slope = model_slopes.get(weakest_ch) if model_slopes else None
                weakest_signal = signals.get(weakest_ch, 0.0)

                # Normalize saturating channels using slope ratios
                for ch in channels_saturating:
                    old_led = led_intensities[ch]
                    ch_slope = model_slopes.get(ch) if model_slopes else None

                    if weakest_slope and ch_slope and weakest_slope > 0 and ch_slope > 0:
                        # Calculate normalized LED: LED_norm = (slope_weakest / slope_ch) × 255
                        # This ensures ch produces same signal as weakest at max LED
                        normalized_led = int((weakest_slope / ch_slope) * config.MAX_LED)

                        # Add 3% safety margin below target to clear saturation
                        safety_factor = 0.97
                        new_led = int(normalized_led * safety_factor)
                        new_led = max(config.MIN_LED, min(config.MAX_LED, new_led))

                        _log(logger, "info", f"  📐 {ch.upper()} LED {old_led}→{new_led} (normalized via slopes: {weakest_slope:.1f}/{ch_slope:.1f} × 255 × 0.97)")
                    else:
                        # Fallback: use saturation recovery if slopes unavailable
                        new_led = calculate_saturation_recovery(
                            channel=ch,
                            current_led=old_led,
                            current_signal=signals[ch],
                            target_signal=target_signal,
                            sat_pixels=sat_per_ch[ch],
                            model_slope=ch_slope,
                            config=config,
                            logger=logger,
                        )

                    led_intensities[ch] = new_led

                # Don't reduce integration time, continue to next iteration
                continue

            else:
                # Weakest channel can still increase LED -> reduce integration time
                # CRITICAL: This branch should NEVER execute in P-mode!
                # If you see this in P-mode logs, freeze_integration check FAILED!
                if freeze_integration:
                    _log(logger, "error", f"  ❌ BUG: P-mode attempting to reduce integration time!")
                    _log(logger, "error", f"     freeze_integration={freeze_integration} but else branch executed!")
                    _log(logger, "error", f"     This should NEVER happen - skipping integration reduction")
                    # Don't reduce integration in P-mode even if we got here by mistake
                else:
                    _log(logger, "info", f"  ⚠️ Multiple channels saturating - reducing integration time")
                    new_integration = calculate_integration_time_reduction(
                        sat_per_ch=sat_per_ch,
                        current_integration=integration_ms,
                        detector_params=detector_params,
                        config=config,
                        logger=logger,
                    )

                    if new_integration < integration_ms:
                        integration_ms = new_integration
                        # Integration time changed, boundaries will be cleared on next iteration
                        continue

        # STEP 3b: If signals are uniformly low and LEDs are pegged, increase integration
        # CRITICAL: Skip if integration time is locked (weakest LED at max)
        # Condition: no saturation, majority of adjustable channels at MAX_LED and below target
        if total_sat == 0 and not integration_locked and not freeze_integration:
            adjustable = [ch for ch in ch_list if ch not in locked_channels]
            if adjustable:
                maxed_and_low = [
                    ch for ch in adjustable
                    if led_intensities.get(ch, 0) >= config.MAX_LED and
                       signals.get(ch, 0.0) < (target_signal - tolerance_signal)
                ]
                # Be conservative: require at least half of adjustable channels to be starved at max LED
                if len(maxed_and_low) >= max(1, len(adjustable) // 2):
                    # Estimate scale factor from measured signals for maxed channels
                    factors = []
                    for ch in maxed_and_low:
                        sig = max(1.0, signals.get(ch, 1.0))
                        factors.append(target_signal / sig)
                    # Median is robust to outliers
                    needed_scale = float(np.median(factors)) if factors else 1.0
                    # Limit per-iteration jump and absolute maximum
                    per_iter_cap = 2.5
                    needed_scale = max(1.2, min(per_iter_cap, needed_scale))
                    candidate_integration = integration_ms * needed_scale
                    # Clamp to detector limits
                    candidate_integration = min(detector_params.max_integration_time, candidate_integration)
                    candidate_integration = max(detector_params.min_integration_time, candidate_integration)

                    # Predictive guard: avoid increasing into saturation using model slopes
                    max_safe_counts = min(near_upper, detector_params.saturation_threshold * 0.98)
                    integration_max_safe = detector_params.max_integration_time
                    if model_slopes:
                        for ch in adjustable:
                            slope_10 = model_slopes.get(ch, 0.0)
                            if slope_10 and slope_10 > 0:
                                # predicted counts = slope_10 * 255 * (t/10)
                                # solve t for max_safe_counts
                                t_max = (max_safe_counts / (slope_10 * 255.0)) * 10.0
                                if t_max > 0:
                                    integration_max_safe = min(integration_max_safe, t_max)

                    # Cap candidate integration by predicted safe maximum
                    candidate_integration = min(candidate_integration, integration_max_safe)

                    # Device-agnostic: do not hard-cap integration here; limits come from detector_params.

                    new_integration = candidate_integration
                    if new_integration > integration_ms * 1.05:  # require at least +5% to apply
                        _log(
                            logger,
                            "info",
                            (
                                f"  ⏱️ Signals low with LEDs at max → increasing integration: "
                                f"{integration_ms:.1f}ms → {new_integration:.1f}ms"
                            ),
                        )
                        integration_ms = new_integration
                        # Integration time changed, restart next iteration
                        continue

        # STEP 3c: Check for maxed LEDs below acceptance threshold
        # CRITICAL: Skip if integration time is locked (weakest LED at max)
        # If any channel is at max LED and below acceptance window, increase integration
        # This handles the case where weak channels are maxed but still below target
        if total_sat == 0 and not integration_locked and not freeze_integration:  # Only if no saturation and policy allows
            min_acceptable_signal = target_signal - tolerance_signal  # Lower bound of acceptance window
            maxed_below_threshold = [
                ch for ch in needs_adjustment
                if led_intensities.get(ch, 0) >= config.MAX_LED and
                   signals.get(ch, 0.0) < min_acceptable_signal
            ]

            if maxed_below_threshold:
                _log(logger, "info", f"  ⚠️  Channels at max LED but below acceptance threshold: {maxed_below_threshold}")

                # Calculate required scale factor
                factors = []
                for ch in maxed_below_threshold:
                    sig = max(1.0, signals.get(ch, 1.0))
                    # Target the middle of acceptance window for safety
                    target_mid = (min_acceptable_signal + target_signal) / 2.0
                    factors.append(target_mid / sig)

                needed_scale = float(np.median(factors)) if factors else 1.0
                needed_scale = max(1.05, min(2.0, needed_scale))  # 5-100% increase per iteration

                new_integration = integration_ms * needed_scale
                new_integration = min(detector_params.max_integration_time, new_integration)
                new_integration = max(detector_params.min_integration_time, new_integration)

                if new_integration > integration_ms:
                    _log(logger, "info", f"  📈 Increasing integration: {integration_ms:.1f}ms → {new_integration:.1f}ms (maxed LEDs below threshold)")
                    integration_ms = new_integration
                    # Integration time changed, restart next iteration
                    continue
                else:
                    _log(logger, "warning", f"  ⚠️  Cannot increase integration further (at max: {detector_params.max_integration_time:.1f}ms)")
                    # Continue with LED adjustment even though it won't help

        # STEP 4: Adjust LEDs ONLY for channels needing adjustment (not locked)
        # CRITICAL PRIORITY: If weakest LED not yet at max OR not in tolerance, prioritize it
        # Once weakest LED reaches 255 AND achieves acceptable signal, switch to reducing other LEDs
        
        weakest_in_tolerance = weakest_ch in locked_channels
        
        if (weakest_led < config.MAX_LED or not weakest_in_tolerance) and weakest_ch not in locked_channels:
            # PRIORITY MODE: Focus ONLY on weakest channel until it reaches 255 AND acceptable signal
            if weakest_led < config.MAX_LED:
                _log(logger, "info", f"\n🎯 PRIORITY: Boosting weakest channel {weakest_ch.upper()} (LED={weakest_led}, target 255)")
            else:
                _log(logger, "info", f"\n🎯 PRIORITY: Weakest channel {weakest_ch.upper()} at max LED but below target - need integration time increase")
            
            ch = weakest_ch
            signal = signals[ch]
            sat_pixels = sat_per_ch[ch]
            current_led = led_intensities[ch]
            
            # If saturating, reduce integration time instead of LED
            # CRITICAL: Respect FREEZE_INTEGRATION flag - P-MODE MUST NEVER REDUCE INTEGRATION!
            if sat_pixels > 0:
                if not freeze_integration and not allow_increase_only:
                    _log(logger, "info", f"  ⚠️ Weakest channel {ch.upper()} saturating - reducing integration time")
                    new_integration = calculate_integration_time_reduction(
                        sat_per_ch=sat_per_ch,
                        current_integration=integration_ms,
                        detector_params=detector_params,
                        config=config,
                        logger=logger,
                    )
                    if new_integration < integration_ms:
                        integration_ms = new_integration
                        continue
                else:
                    # Integration FROZEN (P-mode) - reduce LED instead even for weakest channel
                    _log(logger, "info", f"  🔒 P-MODE: Integration FROZEN at {integration_ms:.1f}ms")
                    _log(logger, "info", f"     Weakest channel {ch.upper()} saturating - reducing LED instead of integration")
                    new_led = calculate_saturation_recovery(
                        channel=ch,
                        current_led=current_led,
                        current_signal=signal,
                        target_signal=target_signal,
                        sat_pixels=sat_pixels,
                        model_slope=model_slopes.get(ch) if model_slopes else None,
                        config=config,
                        logger=logger,
                    )
                    led_intensities[ch] = new_led
                    continue
            
            # If below target, increase LED toward 255
            if signal < target_signal - tolerance_signal:
                # Get model slope
                model_slope = None
                if model_slopes and ch in model_slopes:
                    model_slope = model_slopes[ch] * (integration_ms / 10.0)
                est_slope = state.get_estimated_slope(ch)
                
                # Calculate LED increase, capping at 255
                new_led = calculate_led_adjustment(
                    channel=ch,
                    current_led=current_led,
                    current_signal=signal,
                    target_signal=target_signal,
                    iteration=iteration,
                    model_slope=model_slope,
                    estimated_slope=est_slope,
                    config=config,
                    logger=logger,
                )
                
                # Enforce max LED
                new_led = min(config.MAX_LED, new_led)
                led_intensities[ch] = new_led
                _log(logger, "info", f"  🎯 {ch.upper()} LED {current_led}→{new_led} (weakest priority)")
            
            # Skip all other channels this iteration
            continue
        
        # NORMAL MODE: Weakest LED is at max AND in tolerance, adjust all other channels
        # Locked channels are within tolerance and will not be modified
        for ch in needs_adjustment:
            signal = signals[ch]
            sat_pixels = sat_per_ch[ch]
            current_led = led_intensities[ch]
            signal_pct = (signal / target_signal) * 100.0

            # Handle saturation
            if sat_pixels > 0:
                # Record saturation boundary
                state.record_saturation(ch, current_led, logger)

                # Get model slope (scaled to current integration time)
                model_slope = None
                if model_slopes and ch in model_slopes:
                    model_slope = model_slopes[ch] * (integration_ms / 10.0)

                # Calculate precise LED reduction using model
                new_led = calculate_saturation_recovery(
                    channel=ch,
                    current_led=current_led,
                    current_signal=signal,
                    target_signal=target_signal,
                    sat_pixels=sat_pixels,
                    model_slope=model_slope,
                    config=config,
                    logger=logger,
                )

                # Apply boundaries
                new_led = state.enforce_boundaries(
                    ch,
                    new_led,
                    config,
                    logger=None,
                    current_signal=signals.get(ch),
                    target_signal=target_signal,
                )

                led_intensities[ch] = new_led
                continue

            # Handle too low signal
            if signal < target_signal - tolerance_signal:
                # Get model slope (scale from 10ms to current integration time)
                model_slope = None
                if model_slopes and ch in model_slopes:
                    # Scale slope: slope @ current_time = slope @ 10ms * (current_time / 10ms)
                    model_slope = model_slopes[ch] * (integration_ms / 10.0)
                # Get estimated slope from recent history
                est_slope = state.get_estimated_slope(ch)

                # Calculate LED increase
                new_led = calculate_led_adjustment(
                    channel=ch,
                    current_led=current_led,
                    current_signal=signal,
                    target_signal=target_signal,
                    iteration=iteration,
                    model_slope=model_slope,
                    estimated_slope=est_slope,
                    config=config,
                    logger=logger,
                )

                # Apply boundaries
                new_led = state.enforce_boundaries(
                    ch,
                    new_led,
                    config,
                    logger=None,
                    current_signal=signals.get(ch),
                    target_signal=target_signal,
                )

                led_intensities[ch] = new_led
                continue

            # Handle too high signal (above tolerance)
            if signal > target_signal + tolerance_signal:
                _log(logger, "info", f"  📉 {ch.upper()} above tolerance ({signal_pct:.1f}%) → reduce LED")

                # Small LED reduction
                new_led = max(config.MIN_LED, current_led - config.LED_SMALL_STEP)

                # Apply boundaries
                new_led = state.enforce_boundaries(
                    ch,
                    new_led,
                    config,
                    logger=None,
                    current_signal=signals.get(ch),
                    target_signal=target_signal,
                )

                led_intensities[ch] = new_led
                continue

        # Yield to UI/event loop if provided; otherwise tiny sleep to avoid tight loop
        yield_callback = getattr(config, "YIELD_CALLBACK", None)
        if yield_callback is not None:
            try:
                yield_callback()
            except Exception:
                pass
        else:
            time.sleep(0.01)

    # Max iterations reached without convergence
    _log(logger, "warning", f"\n⚠️ Max iterations ({max_iterations}) reached without convergence")
    _log(logger, "warning", f"   Final integration time: {integration_ms:.1f}ms")
    _log(logger, "warning", f"   Final LEDs: {led_intensities}")
    _log(logger, "warning", f"   Final signals: {signals}")
    _log(logger, "warning", f"   Acceptable: {channels_acceptable}")
    _log(logger, "warning", f"   Saturating: {channels_saturating}")

    return integration_ms, signals, False
