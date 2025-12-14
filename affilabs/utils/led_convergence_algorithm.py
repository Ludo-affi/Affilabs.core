"""LED Convergence Algorithm - Clean Implementation.

Main convergence loop using model-aware adjustments and zero-saturation enforcement.
"""

import time
import numpy as np
from typing import Optional

from .led_convergence_core import (
    DetectorParams,
    ConvergenceState,
    measure_channel,
    check_convergence,
    calculate_model_aware_led_adjustment,
    calculate_ratio_based_led_adjustment,
    calculate_saturation_recovery,
    calculate_integration_time_boost,
    analyze_saturation_severity,
)


def LEDconverge(
    usb,
    ctrl,
    ch_list: list[str],
    led_intensities: dict[str, int],
    acquire_raw_spectrum_fn,
    roi_signal_fn,
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 15,
    step_name: str = "Step 4",
    use_batch_command: bool = True,
    model_slopes: Optional[dict[str, float]] = None,
    polarization: str = 'S',
    logger=None,
) -> tuple[float, dict[str, float], bool]:
    """LED convergence to target signal with zero saturation tolerance.
    
    Uses model-aware LED adjustments when model_slopes provided.
    Enforces strict boundary tracking to prevent oscillation.
    
    Args:
        model_slopes: Optional {'a': counts_per_led @ 10ms, 'b': ...}
        polarization: 'S' or 'P' (currently unused, reserved for future)
    
    Returns:
        (final_integration_ms, {channel: signal_counts}, converged)
    """
    detector_max = detector_params.max_counts
    target = target_percent * detector_max
    tolerance_percent = max(tolerance_percent, 0.05)  # Minimum 5%
    
    current_integration = initial_integration_ms
    state = ConvergenceState()
    
    if logger:
        logger.info(f"\n{'='*70}")
        logger.info(f"{step_name}: LED Convergence Started")
        logger.info(f"  Target: {target_percent*100:.1f}% ({target:.0f} counts)")
        logger.info(f"  Tolerance: ±{tolerance_percent*100:.1f}%")
        logger.info(f"  Initial LEDs: {led_intensities}")
        logger.info(f"  Model slopes: {'Yes' if model_slopes else 'No (using ratios)'}")
        logger.info(f"{'='*70}\n")
    
    # =============================================================================
    # CONVERGENCE LOOP
    # =============================================================================
    
    for iteration in range(max_iterations):
        # Set integration time
        usb.set_integration(current_integration)
        time.sleep(0.010)
        
        # Measure all channels
        signals: dict[str, float] = {}
        sat_per_ch: dict[str, int] = {}
        
        if logger:
            logger.info(f"\n--- Iteration {iteration + 1}/{max_iterations} @ T={current_integration:.1f}ms ---")
        
        for ch in ch_list:
            signal, sat_pixels = measure_channel(
                usb, ctrl, ch,
                led_intensities[ch],
                current_integration,
                acquire_raw_spectrum_fn,
                roi_signal_fn,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold,
                use_batch_command,
            )
            
            if signal is None:
                if logger:
                    logger.error(f"  ❌ {ch.upper()} measurement failed @ LED={led_intensities[ch]}")
                continue
            
            signals[ch] = signal
            sat_per_ch[ch] = sat_pixels
            
            pct = (signal / detector_max) * 100.0
            status = "🚨 SAT" if sat_pixels > 0 else "✅ OK"
            if logger:
                logger.info(f"  {ch.upper()}: {signal:.0f} ({pct:.1f}%) LED={led_intensities[ch]:3d} {status} sat_px={sat_pixels}")
        
        # Log iteration summary
        total_sat = sum(sat_per_ch.values())
        if logger:
            logger.info(f"  Total saturated pixels: {total_sat}")
        
        # Update boundary tracking
        for ch in signals:
            if sat_per_ch.get(ch, 0) > 0:
                state.record_saturation(ch, led_intensities[ch], logger)
            
            min_sig = (target_percent - tolerance_percent) * detector_max
            if signals[ch] < min_sig:
                state.record_undershoot(ch, led_intensities[ch], signals[ch], target, logger)
        
        # Check convergence
        converged, reason = check_convergence(
            signals,
            sat_per_ch,
            target_percent,
            tolerance_percent,
            detector_max,
        )
        
        if converged:
            if logger:
                logger.info(f"\n🎉 CONVERGED in {iteration + 1} iterations")
                logger.info(f"   Integration: {current_integration:.1f}ms")
                logger.info(f"   Final LEDs: {led_intensities}")
                logger.info(f"   Saturation: {total_sat} pixels (ZERO REQUIRED)")
            return current_integration, signals, True
        
        if logger:
            logger.info(f"  Status: {reason}")
        
        # =============================================================================
        # CHANNEL ADJUSTMENTS
        # =============================================================================
        
        # Identify channels needing adjustment
        min_sig = (target_percent - tolerance_percent) * detector_max
        max_sig = (target_percent + tolerance_percent) * detector_max
        
        channels_needing_adjustment = [
            ch for ch in ch_list
            if ch in signals and not (min_sig <= signals[ch] <= max_sig)
        ]
        
        if not channels_needing_adjustment and total_sat > 0:
            # All channels in tolerance but saturation remains - continue to clear it
            channels_needing_adjustment = [ch for ch in ch_list if sat_per_ch.get(ch, 0) > 0]
            if logger:
                logger.warning(f"  ⚠️ Tolerance met but {total_sat} saturated - forcing saturation recovery")
        
        for ch in channels_needing_adjustment:
            sig = signals[ch]
            current_led = led_intensities[ch]
            
            # --- SATURATION RECOVERY ---
            if sat_per_ch.get(ch, 0) > 0:
                # Get spectrum for severity analysis
                spec = acquire_raw_spectrum_fn(
                    usb, ctrl, ch, current_led, current_integration,
                    num_scans=1, pre_led_delay_ms=45.0, post_led_delay_ms=5.0,
                    use_batch_command=use_batch_command,
                )
                
                if spec is not None and model_slopes and ch in model_slopes:
                    # Model-based saturation recovery
                    sat_analysis = analyze_saturation_severity(
                        spec, wave_min_index, wave_max_index,
                        detector_params.saturation_threshold
                    )
                    
                    model_slope = model_slopes[ch] * (current_integration / 10.0)
                    
                    new_led = calculate_saturation_recovery(
                        ch, current_led, sat_analysis,
                        model_slope, target, detector_max, logger
                    )
                else:
                    # Fallback: 25% reduction
                    new_led = int(max(10, current_led * 0.75))
                    if logger:
                        logger.info(f"  📉 FALLBACK {ch.upper()} LED {current_led} → {new_led} (no model or spectrum)")
            
            # --- NORMAL ADJUSTMENT ---
            else:
                if model_slopes and ch in model_slopes:
                    # Model-aware adjustment
                    model_slope = model_slopes[ch] * (current_integration / 10.0)
                    new_led = calculate_model_aware_led_adjustment(
                        ch, current_led, sig, target, model_slope, logger
                    )
                else:
                    # Ratio-based fallback
                    new_led = calculate_ratio_based_led_adjustment(
                        ch, current_led, sig, target, logger
                    )
            
            # Apply boundary constraints
            new_led = state.enforce_boundaries(ch, new_led, logger)
            
            # Update LED intensity
            if new_led != current_led:
                led_intensities[ch] = new_led
        
        # =============================================================================
        # INTEGRATION TIME ADJUSTMENT
        # =============================================================================
        
        # Check if integration boost needed
        new_integration, boosted_channels = calculate_integration_time_boost(
            signals,
            led_intensities,
            target,
            current_integration,
            state,
            detector_params,
            iteration,
            logger,
        )
        
        if boosted_channels:
            # Integration time increased - reduce other channels proportionally
            boost_ratio = new_integration / current_integration
            state.time_boosted_channels.update(boosted_channels)
            
            for ch in ch_list:
                if ch not in boosted_channels and ch in signals:
                    old_led = led_intensities[ch]
                    led_intensities[ch] = int(max(10, old_led / boost_ratio))
                    if logger and led_intensities[ch] != old_led:
                        logger.info(f"     Proportional reduction: {ch.upper()} LED {old_led} → {led_intensities[ch]}")
            
            current_integration = new_integration
        else:
            # Normal integration adjustment based on median signal
            if signals:
                median_signal = np.median(list(signals.values()))
                
                if total_sat > 0:
                    # Saturation present - reduce integration
                    current_integration *= 0.95
                else:
                    # No saturation - adjust toward target
                    factor = target / median_signal if median_signal > 0 else 1.0
                    factor = max(0.95, min(1.05, factor))
                    current_integration *= factor
                
                # Clamp to detector limits
                current_integration = max(
                    detector_params.min_integration_time,
                    min(detector_params.max_integration_time, current_integration)
                )
    
    # =============================================================================
    # FALLBACK ACCEPTANCE (iterations exhausted)
    # =============================================================================
    
    if logger:
        logger.warning(f"\n⚠️ Maximum iterations ({max_iterations}) reached without convergence")
    
    # Check hardware-limited acceptance (integration near max)
    if signals and current_integration >= (detector_params.max_integration_time * 0.75):
        hardware_min = 0.80 * detector_max
        all_above_80 = all(signals[ch] >= hardware_min for ch in signals)
        
        if all_above_80 and total_sat == 0:
            if logger:
                logger.warning(f"✅ ACCEPTING hardware-limited convergence (all ≥80%, zero saturation)")
                for ch in signals:
                    pct = (signals[ch] / detector_max) * 100.0
                    logger.info(f"   {ch.upper()}: {signals[ch]:.0f} ({pct:.1f}%) LED={led_intensities[ch]}")
            return current_integration, signals, True
    
    # Check relaxed tolerance (±10%)
    if signals:
        relaxed_min = target * 0.90
        relaxed_max = target * 1.10
        all_in_relaxed = all(relaxed_min <= signals[ch] <= relaxed_max for ch in signals)
        
        if all_in_relaxed and total_sat == 0:
            if logger:
                logger.warning(f"⚠️ ACCEPTING with relaxed tolerance (±10%, zero saturation)")
                for ch in signals:
                    pct = (signals[ch] / detector_max) * 100.0
                    logger.info(f"   {ch.upper()}: {signals[ch]:.0f} ({pct:.1f}%)")
            return current_integration, signals, True
    
    # Failed convergence
    if logger:
        logger.error(f"❌ CONVERGENCE FAILED")
        logger.error(f"   Final saturation: {total_sat} pixels (ZERO REQUIRED)")
        for ch in signals:
            pct = (signals[ch] / detector_max) * 100.0
            sat = sat_per_ch.get(ch, 0)
            logger.error(f"   {ch.upper()}: {signals[ch]:.0f} ({pct:.1f}%) LED={led_intensities[ch]} sat={sat}")
    
    return current_integration, signals, False
