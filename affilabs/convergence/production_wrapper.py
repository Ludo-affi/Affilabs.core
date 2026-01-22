"""Convergence engine wrapper for production calibration.

This module provides a drop-in replacement for LEDconverge() that uses
the new convergence engine architecture while maintaining full compatibility
with the existing calibration orchestrator.

Usage:
    # Replace LEDconverge import with:
    from affilabs.convergence.production_wrapper import LEDconverge_engine as LEDconverge

    # Or use conditionally:
    if use_engine:
        from affilabs.convergence.production_wrapper import LEDconverge_engine
        result = LEDconverge_engine(...)
    else:
        from affilabs.utils.led_convergence_algorithm import LEDconverge
        result = LEDconverge(...)
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, List

from affilabs.convergence import (
    ConvergenceEngine,
    create_production_adapters,
    create_recipe_from_production_config,
    create_detector_params_from_production,
    convert_engine_result_to_production,
)
from affilabs.utils.led_convergence_core import (
    ConvergenceConfig,
    DetectorParams as ProductionDetectorParams,
    AcquireSpectrumFn,
    ROISignalFn,
)


def LEDconverge_engine(
    usb: object,
    ctrl: object,
    ch_list: List[str],
    led_intensities: Dict[str, int],
    acquire_raw_spectrum_fn: AcquireSpectrumFn,
    roi_signal_fn: ROISignalFn,
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: ProductionDetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 15,
    step_name: str = "Step 4",
    use_batch_command: bool = True,
    model_slopes: Optional[Dict[str, float]] = None,
    polarization: str = "S",
    config: Optional[ConvergenceConfig] = None,
    logger: Optional[object] = None,
    progress_callback: Optional[callable] = None,
    detector_serial: Optional[int] = None,
) -> Tuple[float, Dict[str, float], bool]:
    """LED convergence using the new convergence engine.

    This is a drop-in replacement for LEDconverge() from led_convergence_algorithm.py
    It has the exact same signature and return format, but uses the cleaner
    convergence engine architecture internally.

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

    # Log engine usage
    if logger:
        logger.info(f"\n{'='*80}")
        logger.info(f"🔬 USING CONVERGENCE ENGINE (EXPERIMENTAL)")
        logger.info(f"{step_name}: LED Convergence - {polarization} polarization")
        logger.info(f"{'='*80}\n")

    # Create production adapters
    adapters = create_production_adapters(
        usb=usb,
        ctrl=ctrl,
        acquire_spectrum_fn=acquire_raw_spectrum_fn,
        logger=logger,
        use_batch_command=use_batch_command,
    )

    # Create engine recipe from production config
    recipe = create_recipe_from_production_config(
        channels=ch_list,
        initial_leds=led_intensities,
        initial_integration_ms=initial_integration_ms,
        target_percent=target_percent,
        tolerance_percent=tolerance_percent,
        config=config,
        polarization_mode=polarization,  # Pass S or P mode to recipe
    )

    # Override max_iterations if provided
    if max_iterations != 15:
        recipe.max_iterations = max_iterations

    # Create detector params
    engine_detector_params = create_detector_params_from_production(
        max_counts=detector_params.max_counts,
        saturation_threshold=detector_params.saturation_threshold,
        min_integration_time=detector_params.min_integration_time,
        max_integration_time=detector_params.max_integration_time,
        polarization_mode=polarization,  # Pass polarization mode for P-pol specific limits
    )

    # Check for trained ML models (bundled with application)
    from pathlib import Path
    import sys
    
    # Determine base path (works for both frozen .exe and development)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as compiled .exe - models are in _MEIPASS
        base_path = Path(sys._MEIPASS) / "affilabs" / "convergence" / "models"
    else:
        # Running from source - use relative path from this file
        base_path = Path(__file__).parent / "models"
    
    sensitivity_model_path = None
    led_predictor_path = None
    convergence_predictor_path = None

    if base_path.exists():
        sensitivity_path = base_path / "sensitivity_classifier.joblib"
        led_path = base_path / "led_predictor.joblib"
        convergence_path = base_path / "convergence_predictor.joblib"

        if sensitivity_path.exists():
            sensitivity_model_path = str(sensitivity_path)
        if led_path.exists():
            led_predictor_path = str(led_path)
        if convergence_path.exists():
            convergence_predictor_path = str(convergence_path)

    # Create and run engine
    engine = ConvergenceEngine(
        spectrometer=adapters['spectrometer'],
        roi_extractor=adapters['roi_extractor'],
        led_actuator=adapters['led_actuator'],
        scheduler=None,  # No parallel scheduler for now (production uses sequential)
        logger=adapters['logger'],
        sensitivity_model_path=sensitivity_model_path,
        led_predictor_path=led_predictor_path,
        convergence_predictor_path=convergence_predictor_path,
    )

    # Run convergence
    try:
        result = engine.run(
            recipe=recipe,
            params=engine_detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            model_slopes_at_10ms=model_slopes,
            progress_callback=progress_callback,
            detector_serial=detector_serial,
        )

        # Convert engine result to production format
        integration_ms, signals, converged, final_leds, best_iteration = convert_engine_result_to_production(
            result=result,
            channel_list=ch_list,
        )

        if logger:
            if converged:
                logger.info(f"\n✅ ENGINE CONVERGED!")
                logger.info(f"   Final integration time: {integration_ms:.1f}ms")
                logger.info(f"   Converged at iteration: {best_iteration}")
                logger.info(f"   Final signals: {signals}")
            else:
                logger.warning(f"\n⚠️  ENGINE DID NOT CONVERGE")
                logger.warning(f"   Final integration time: {integration_ms:.1f}ms")
                logger.warning(f"   Best iteration: {best_iteration}")

        return integration_ms, signals, converged, final_leds, best_iteration

    except Exception as e:
        if logger:
            logger.error(f"❌ ENGINE ERROR: {e}")
            logger.exception("Engine execution failed")

        # Return failure format
        return initial_integration_ms, {}, False, {}, 0
