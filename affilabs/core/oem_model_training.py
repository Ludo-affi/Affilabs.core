"""OEM LED Model Training Workflow

Automatically creates 3-stage linear LED calibration model for new devices.

This workflow:
1. Measures LED response at multiple integration times (10, 20, 30, 45, 60ms)
2. Fits linear models: counts = slope × intensity
3. Saves model to led_calibration_official/spr_calibration/data/
4. Returns success/failure for automatic calibration continuation

Author: ezControl-AI System
Date: December 17, 2025
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from affilabs.utils.led_model_helpers import fit_linear_model, measure_led_response
from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from affilabs.utils.controller import PicoP4SPR
    from affilabs.utils.usb4000_wrapper import USB4000


class ModelTrainingError(Exception):
    """Raised when model training fails."""


def train_led_model(
    controller: PicoP4SPR,
    spectrometer: USB4000,
    detector_serial: str,
    progress_callback=None,
) -> Path:
    """Train 3-stage LED calibration model for new device.

    Args:
        controller: PicoP4SPR controller instance
        spectrometer: USB4000 spectrometer instance
        detector_serial: Detector serial number
        progress_callback: Optional callback for progress updates (message, percent)

    Returns:
        Path to saved model file

    Raises:
        ModelTrainingError: If training fails

    """
    logger.info("=" * 80)
    logger.info("STARTING OEM LED MODEL TRAINING")
    logger.info("=" * 80)
    logger.info(f"Detector: {detector_serial}")
    logger.info("")

    if progress_callback:
        progress_callback("OEM Model Training: Measuring dark current...", 5)

    # Integration times for model - start with normal times, adapt if saturation detected
    # Normal devices: [10, 20, 30, 45, 60]ms
    # Ultra-sensitive devices: will auto-switch to [5, 10, 15]ms if saturation at 20ms+
    integration_times = [10, 20, 30, 45, 60]

    # Track if we need to use shorter times due to saturation
    needs_shorter_times = False

    # Measure dark current at each integration time
    logger.info("Step 1/4: Measuring dark current...")
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.5)

    dark_counts_per_time = {}
    for time_ms in integration_times:
        spectrometer.set_integration(float(time_ms))
        time.sleep(0.5)
        # Average 3 scans using HAL method
        scans = []
        for _ in range(3):
            scans.append(spectrometer.read_intensity())
            time.sleep(0.05)
        spectrum = np.mean(scans, axis=0)
        dark = float(spectrum.max())
        dark_counts_per_time[time_ms] = dark
        logger.info(f"  {time_ms}ms: {dark:.0f} counts")

    logger.info("")

    # Base intensities; per-stage list will be derived from these to avoid saturation at long times
    base_intensities = [10, 15, 20, 25, 30]
    detector_wait_ms = 50

    # Storage for model data
    led_models = {"A": [], "B": [], "C": [], "D": []}

    # Train model at each integration time (with potential restart for ultra-sensitive devices)
    max_training_attempts = 2  # Allow one restart if saturation detected

    for attempt in range(max_training_attempts):
        total_measurements = len(integration_times) * 4 * len(base_intensities)
        current_measurement = 0
        needs_shorter_times = False

        for stage_idx, time_ms in enumerate(integration_times):
            logger.info("=" * 80)
            logger.info(
                f"STAGE {stage_idx + 1}/{len(integration_times)}: {time_ms}ms Integration Time"
            )
            logger.info("=" * 80)

            integration_time = float(time_ms)
            dark_counts = dark_counts_per_time[time_ms]

            # Track saturation across all LEDs at this integration time
            saturation_count = 0
            total_leds = 4

            # Derive safe intensities for this stage to reduce saturation risk at long times
            if time_ms >= 60:
                intensities_for_stage = [5, 8, 10, 12, 15]
            elif time_ms >= 45:
                intensities_for_stage = [6, 9, 12, 15, 18]
            elif time_ms >= 30:
                intensities_for_stage = [8, 12, 16, 20, 24]
            else:
                intensities_for_stage = base_intensities

            for led_name, led_char in [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d")]:
                logger.info(f"\n{led_name}:")
                led_data = []
                saturated_early = False

                for intensity in intensities_for_stage:
                    current_measurement += 1
                    # Progress scaled to total measurements; long stages still fit in 5-75%
                    progress = int(5 + (current_measurement / total_measurements) * 70)
                    if progress_callback:
                        progress_callback(
                            f"Training LED {led_name} at {time_ms}ms, intensity {intensity}...",
                            progress,
                        )

                    result = measure_led_response(
                        controller,
                        spectrometer,
                        led_char,
                        intensity,
                        integration_time,
                        dark_counts,
                        detector_wait_ms,
                    )

                    # Stop if saturated
                    if result["is_saturated"]:
                        logger.warning(
                            f"  I={intensity}: SATURATED ({result['raw_counts']:.0f} counts) - stopping",
                        )
                        # Check if saturation happened very early (first 2 intensities)
                        if intensity <= base_intensities[1]:
                            saturated_early = True
                        break

                    corrected = result["corrected_counts"]
                    led_data.append((intensity, corrected))
                    logger.info(f"  I={intensity}: {corrected:.0f} counts")

                # Track if this LED saturated early
                if saturated_early:
                    saturation_count += 1

                # Fit linear model for this LED at this integration time
                if len(led_data) >= 2:
                    slope = fit_linear_model(led_data)
                    if slope:
                        led_models[led_name].append({"time_ms": time_ms, "slope": slope})
                        logger.info(f"  → Slope: {slope:.2f} counts/intensity")
                    else:
                        msg = f"Failed to fit model for LED {led_name} at {time_ms}ms"
                        raise ModelTrainingError(msg)
                else:
                    msg = f"Insufficient data for LED {led_name} at {time_ms}ms"
                    raise ModelTrainingError(msg)

            # Check if we should switch to shorter integration times
            # If 50%+ of LEDs saturated early at ≥20ms, device is ultra-sensitive
            if time_ms >= 20 and saturation_count >= total_leds / 2 and not needs_shorter_times:
                logger.warning("")
                logger.warning("=" * 80)
                logger.warning("⚠ ULTRA-SENSITIVE DEVICE DETECTED:")
                logger.warning(
                    f"  {saturation_count}/{total_leds} LEDs saturated at low intensities with {time_ms}ms"
                )
                logger.warning("  Switching to shorter integration times: [5, 10, 15]ms")
                logger.warning("=" * 80)
                logger.warning("")

                # Clear existing models and restart with shorter times
                led_models = {"A": [], "B": [], "C": [], "D": []}
                integration_times = [5, 10, 15]
                needs_shorter_times = True

                # Re-measure dark current at shorter times
                logger.info("Re-measuring dark current at shorter integration times...")
                controller.set_batch_intensities(a=0, b=0, c=0, d=0)
                time.sleep(0.5)

                dark_counts_per_time = {}
                for short_time_ms in integration_times:
                    spectrometer.set_integration(float(short_time_ms))
                    time.sleep(0.5)
                    scans = []
                    for _ in range(3):
                        scans.append(spectrometer.read_intensity())
                        time.sleep(0.05)
                    spectrum = np.mean(scans, axis=0)
                    dark = float(spectrum.max())
                    dark_counts_per_time[short_time_ms] = dark
                    logger.info(f"  {short_time_ms}ms: {dark:.0f} counts")
                logger.info("")

                # Restart the loop with shorter times
                total_measurements = len(integration_times) * 4 * len(base_intensities)
                current_measurement = 0
                break

            # If this was the last stage and we detected saturation, abort this loop
            if needs_shorter_times:
                break

        # If we completed all stages without needing shorter times, break the attempt loop
        if not needs_shorter_times:
            break

    if progress_callback:
        progress_callback("Saving model...", 80)

    # Validate all LEDs have models
    for led_name in ["A", "B", "C", "D"]:
        if len(led_models[led_name]) != len(integration_times):
            msg = f"LED {led_name} missing model stages: {len(led_models[led_name])}/{len(integration_times)}"
            raise ModelTrainingError(msg)

    # Save model
    logger.info("\n" + "=" * 80)
    logger.info("Step 4/4: Saving model...")
    logger.info("=" * 80)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_data = {
        "detector_serial": detector_serial,
        "timestamp": timestamp,
        "model_type": "3-stage-linear",
        "model_equation": "counts = slope_10ms × intensity × (time_ms / 10)",
        "integration_times": integration_times,
        "dark_counts_per_time": dark_counts_per_time,
        "led_models": led_models,
        "training_method": "automatic_oem_workflow",
        "detector_wait_ms": detector_wait_ms,
    }

    # Save to BOTH active location and legacy archive
    project_root = Path(__file__).resolve().parents[2]

    # 1. Save to active calibrations (primary location)
    active_dir = project_root / "calibrations" / "active" / detector_serial
    active_dir.mkdir(parents=True, exist_ok=True)
    active_file = active_dir / "led_model.json"
    with open(active_file, "w") as f:
        json.dump(model_data, f, indent=2)
    logger.info(f"✓ Active model saved: calibrations/active/{detector_serial}/led_model.json")

    # 2. Save timestamped copy to legacy archive (for history)
    output_dir = project_root / "led_calibration_official" / "spr_calibration" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"led_calibration_3stage_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(model_data, f, indent=2)
    logger.info(f"✓ Archive saved: {output_file.name}")
    logger.info("")

    # Print summary
    logger.info("=" * 80)
    logger.info("✅ OEM LED MODEL TRAINING COMPLETE")
    logger.info("=" * 80)
    for led_name in ["A", "B", "C", "D"]:
        stages = led_models[led_name]
        slopes_str = ", ".join([f"{s['time_ms']}ms={s['slope']:.1f}" for s in stages])
        logger.info(f"  LED {led_name}: {slopes_str}")
    logger.info(f"\nModel file: {output_file}")
    logger.info("=" * 80)
    logger.info("")

    # Turn off LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    logger.info("✓ LEDs turned off")

    if progress_callback:
        progress_callback("Model training complete!", 100)

    return output_file


def run_oem_model_training_workflow(
    hardware_mgr,
    progress_callback=None,
) -> bool:
    """Run complete OEM model training workflow.

    Workflow order (user requirement):
    1. Servo Polarizer Calibration (if PicoP4SPR with servo)
    2. LED Calibration Model Training

    Args:
        hardware_mgr: Hardware manager with controller and spectrometer
        progress_callback: Optional callback for progress updates (message, percent)

    Returns:
        True if successful, False otherwise

    """
    try:
        ctrl = hardware_mgr.ctrl
        usb = hardware_mgr.usb

        if not ctrl:
            msg = "Controller not connected"
            raise ModelTrainingError(msg)
        if not usb:
            msg = "Spectrometer not connected"
            raise ModelTrainingError(msg)

        # Get detector serial
        detector_serial = getattr(usb, "serial_number", "UNKNOWN")
        if detector_serial == "UNKNOWN":
            msg = "Could not determine detector serial number"
            raise ModelTrainingError(msg)

        # ====================================================================
        # STEP 1: Servo Polarizer Calibration (runs FIRST per user request)
        # ====================================================================
        device_type = (
            ctrl.get_device_type() if hasattr(ctrl, "get_device_type") else type(ctrl).__name__
        )

        # Check if device has servo polarizer (PicoP4SPR only)
        if "PicoP4SPR" in device_type or "picop4spr" in device_type.lower():
            logger.info("\n" + "=" * 80)
            logger.info("STEP 1: SERVO POLARIZER CALIBRATION")
            logger.info("=" * 80)
            logger.info("Detecting polarizer type and finding S/P positions...")
            logger.info("This will take ~2-5 minutes depending on polarizer type.\n")

            if progress_callback:
                progress_callback("Step 1: Servo polarizer calibration...", 0)

            # Import servo calibration module
            import sys
            from pathlib import Path as PathLib

            servo_cal_dir = PathLib(__file__).parent.parent.parent / "servo_polarizer_calibration"
            if str(servo_cal_dir) not in sys.path:
                sys.path.insert(0, str(servo_cal_dir))

            try:
                # Import and run servo calibration
                from calibrate_polarizer import run_servo_calibration_from_hardware_mgr

                servo_success = run_servo_calibration_from_hardware_mgr(
                    hardware_mgr=hardware_mgr,
                    progress_callback=progress_callback,
                )

                if not servo_success:
                    logger.error("❌ Servo polarizer calibration failed")
                    logger.error("Cannot proceed without valid S/P positions")
                    return False

                logger.info("\n[OK] Servo polarizer calibration complete")

            except ImportError as e:
                logger.warning(f"⚠️  Could not import servo calibration module: {e}")
                logger.warning("Servo calibration will be skipped")
                logger.warning("Ensure device_config.json has valid S/P positions")
        else:
            logger.info(f"\n[INFO] Device type '{device_type}' does not have servo polarizer")
            logger.info("Skipping servo calibration step\n")

        # ====================================================================
        # STEP 2: LED Calibration Model Training
        # ====================================================================
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: LED CALIBRATION MODEL TRAINING")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 2: LED model training...", 50)

        # Run LED model training
        model_file = train_led_model(
            controller=ctrl,
            spectrometer=usb,
            detector_serial=detector_serial,
            progress_callback=progress_callback,
        )

        logger.info(f"[OK] Model training successful: {model_file.name}")
        return True

    except Exception as e:
        logger.error(f"❌ OEM workflow failed: {e}")
        logger.exception("Full traceback:")
        return False
