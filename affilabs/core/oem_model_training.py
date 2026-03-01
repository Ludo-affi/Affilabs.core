"""OEM LED Model Training Workflow

Automatically creates 3-stage linear LED calibration model for new devices.

This workflow:
1. Measures LED response at multiple integration times (10, 20, 30, 45, 60ms)
2. Fits linear models: counts = slope × intensity
3. Saves model to led_calibration_official/spr_calibration/data/
4. Returns success/failure for automatic calibration continuation

CRITICAL: Uses OFFICIAL LED calibration method intensities:
- Base: [30, 60, 90, 120, 150] (NOT [10, 15, 20, 25, 30])
- Matches led_calibration_official/1_create_model.py
- Higher intensities = better SNR and dynamic range
- Fixed 2025-01-04: Updated from incorrect low intensities

Author: ezControl-AI System
Date: December 17, 2025
Updated: January 4, 2026 - Fixed intensity values to match official method
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
    # ALSO measure ultra-sensitive times [5, 10, 15]ms upfront so they're ready if needed
    logger.info("Step 1/4: Measuring dark current...")
    # Send individual turn-off commands for each LED (more reliable than batch)
    controller.set_intensity("a", 0)
    controller.set_intensity("b", 0)
    controller.set_intensity("c", 0)
    controller.set_intensity("d", 0)
    # Send batch turn-off as well for redundancy
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    logger.info("Waiting 3 seconds for LEDs to fully turn off...")
    time.sleep(3.0)  # Increased from 0.5s - LEDs need time to fully shut down

    dark_counts_per_time = {}
    # Measure dark for normal times [10, 20, 30, 45, 60]ms
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

    # ALSO measure ultra-sensitive times [5, 10, 15]ms (will use if ultra-sensitive detected)
    logger.info("Pre-measuring ultra-sensitive integration times...")
    for time_ms in [5, 10, 15]:
        if time_ms not in dark_counts_per_time:  # Don't re-measure 10ms
            spectrometer.set_integration(float(time_ms))
            time.sleep(0.5)
            scans = []
            for _ in range(3):
                scans.append(spectrometer.read_intensity())
                time.sleep(0.05)
            spectrum = np.mean(scans, axis=0)
            dark = float(spectrum.max())
            dark_counts_per_time[time_ms] = dark
            logger.info(f"  {time_ms}ms: {dark:.0f} counts")

    logger.info("")

    # Base intensities - MATCH OFFICIAL LED CALIBRATION METHOD
    # Official script: [30, 60, 90, 120, 150] for better SNR and dynamic range
    # Previous (WRONG): [10, 15, 20, 25, 30] - too low, poor SNR
    base_intensities = [30, 60, 90, 120, 150]
    detector_wait_ms = 50

    # Storage for model data
    led_models = {"A": [], "B": [], "C": [], "D": []}

    # Train model at each integration time (with potential restart for ultra-sensitive devices)
    max_training_attempts = 2  # Allow one restart if saturation detected
    already_ultra_sensitive = False  # Prevent double-trigger on short integration times

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
            # Scale down from base_intensities [30, 60, 90, 120, 150] at longer integration times
            if time_ms >= 60:
                intensities_for_stage = [15, 30, 45, 60, 75]  # 50% of base
            elif time_ms >= 45:
                intensities_for_stage = [20, 40, 60, 80, 100]  # 67% of base
            elif time_ms >= 30:
                intensities_for_stage = [24, 48, 72, 96, 120]  # 80% of base
            elif time_ms >= 20:
                intensities_for_stage = [
                    20,
                    40,
                    60,
                    80,
                    100,
                ]  # Conservative for 20ms to avoid early saturation
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

                        # ADAPTIVE: For ultra-sensitive devices, try intermediate intensities to get 2nd point
                        if len(led_data) == 1:
                            logger.info(
                                "  Only 1 data point - attempting adaptive intermediate collection..."
                            )
                            last_good_intensity = led_data[-1][0]
                            # Try multiple intermediate points, getting progressively closer to last good
                            attempts = [
                                int((last_good_intensity + intensity) / 2),  # Halfway
                                int((last_good_intensity + intensity) / 3)
                                + last_good_intensity,  # 1/3 from last good
                                int((intensity - last_good_intensity) / 4)
                                + last_good_intensity,  # 1/4 from last good
                            ]

                            for intermediate in attempts:
                                if intermediate <= last_good_intensity or intermediate >= intensity:
                                    continue
                                logger.info(f"  Trying intermediate intensity {intermediate}...")
                                result_mid = measure_led_response(
                                    controller,
                                    spectrometer,
                                    led_char,
                                    intermediate,
                                    integration_time,
                                    dark_counts,
                                    detector_wait_ms,
                                )
                                if not result_mid["is_saturated"]:
                                    corrected_mid = result_mid["corrected_counts"]
                                    led_data.append((intermediate, corrected_mid))
                                    logger.info(f"  I={intermediate}: {corrected_mid:.0f} counts ✓")
                                    break  # Got our 2nd point, stop trying
                                else:
                                    logger.warning(
                                        f"  I={intermediate}: SATURATED - trying lower..."
                                    )
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
                    # Insufficient data - check if this is due to ultra-high sensitivity
                    if saturated_early and time_ms >= 10 and not needs_shorter_times:
                        logger.warning(
                            f"  LED {led_name} saturated too early at {time_ms}ms - marking for ultra-sensitive restart"
                        )
                        saturation_count += 1
                        # Don't raise error yet - let the ultra-sensitive detection handle it
                        continue
                    elif needs_shorter_times:
                        # In ultra-sensitive mode but still couldn't get 2 points - log warning and skip this integration time
                        logger.warning(
                            f"  LED {led_name}: Could not collect 2 points at {time_ms}ms (ultra-sensitive) - skipping this integration time"
                        )
                        continue
                    else:
                        msg = f"Insufficient data for LED {led_name} at {time_ms}ms"
                        raise ModelTrainingError(msg)

            # Check if we should switch to shorter integration times
            # If any LED saturated early at ≥10ms, device is ultra-sensitive
            # Threshold at 10ms: detectors saturating at 10ms will never work at 20ms+
            if time_ms >= 10 and saturation_count >= 1 and not needs_shorter_times and not already_ultra_sensitive:
                logger.warning("")
                logger.warning("=" * 80)
                logger.warning("⚠ ULTRA-SENSITIVE DEVICE DETECTED:")
                logger.warning(
                    f"  {saturation_count}/{total_leds} LED(s) saturated at low intensities with {time_ms}ms"
                )
                logger.warning("  Switching to shorter integration times: [5, 10, 15]ms")
                logger.warning("  Switching to lower intensities: [10, 20, 30, 40, 60]")
                logger.warning("=" * 80)
                logger.warning("")

                # Clear existing models and restart with shorter times and lower intensities
                led_models = {"A": [], "B": [], "C": [], "D": []}
                integration_times = [5, 10, 15]
                base_intensities = [10, 20, 30, 40, 60]  # Lower intensities for ultra-sensitive devices
                needs_shorter_times = True
                already_ultra_sensitive = True

                # Dark current already measured at top - no need to re-measure!
                logger.info(
                    "Using pre-measured dark current for ultra-sensitive integration times:"
                )
                for short_time_ms in integration_times:
                    logger.info(
                        f"  {short_time_ms}ms: {dark_counts_per_time[short_time_ms]:.0f} counts"
                    )
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
        "ultra_sensitive": needs_shorter_times,
    }

    # Save to BOTH active location and legacy archive
    from affilabs.utils.resource_path import get_resource_path

    project_root = get_resource_path("")

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
        # STEP 1: Servo Polarizer Calibration (ALWAYS RUN FOR P4SPR)
        # ====================================================================
        device_type = (
            ctrl.get_device_type() if hasattr(ctrl, "get_device_type") else type(ctrl).__name__
        )

        logger.info(f"\n[DEBUG] Device type detected: {device_type}")
        logger.info(f"[DEBUG] Controller class: {type(ctrl).__name__}")

        # ALWAYS run servo calibration for devices with servo polarizer
        # Includes: PicoP4SPR, PicoP4PRO, PicoEZSPR, PicoAFFINITE
        has_servo = any(
            name in device_type for name in ["PicoP4SPR", "PicoP4PRO", "PicoEZSPR", "PicoAFFINITE"]
        )
        if (
            has_servo
            or "picop4spr" in device_type.lower()
            or "picoezspr" in device_type.lower()
            or "p4pro" in device_type.lower()
        ):
            logger.info("\n" + "=" * 80)
            logger.info("⚙️  STEP 1/2: SERVO POLARIZER CALIBRATION (RUNNING NOW)")
            logger.info("=" * 80)
            logger.info("🔄 Detecting polarizer type and finding S/P window positions...")
            logger.info("⏱️  This will take ~2-5 minutes depending on polarizer type.")
            logger.info("🔍 Watch for servo movement during sweep phase...\n")

            if progress_callback:
                progress_callback("Step 1: Servo polarizer calibration...", 0)

            # Import servo calibration module
            import sys
            from pathlib import Path as PathLib

            servo_cal_dir = PathLib(__file__).parent.parent.parent / "calibrations" / "servo_polarizer"
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
                    logger.error("=" * 80)
                    logger.error("❌ SERVO POLARIZER CALIBRATION FAILED")
                    logger.error("=" * 80)
                    logger.error("")
                    logger.error(
                        "The automatic servo position detection did not complete successfully."
                    )
                    logger.error("")
                    logger.error("POSSIBLE CAUSES:")
                    logger.error("  1. Servo not moving (check firmware v2.1+ loaded)")
                    logger.error("  2. Signal too low (detector not receiving light)")
                    logger.error("  3. Signal saturated (LED intensity too high)")
                    logger.error("")
                    logger.error("MANUAL WORKAROUND:")
                    logger.error("  1. Click 'Servo Calibration' button in sidebar")
                    logger.error("  2. Manually observe which PWM positions give HIGH signal")
                    logger.error("  3. Edit affilabs/config/device_config.json:")
                    logger.error("     - Set 'polarizer_s_position' to S degrees (5-175)")
                    logger.error("     - Set 'polarizer_p_position' to P degrees (5-175)")
                    logger.error("  4. Save file and restart calibration")
                    logger.error("=" * 80)
                    return False

                logger.info("\n[OK] Servo polarizer calibration complete")

            except ImportError as e:
                logger.error(f"❌ Could not import servo calibration module: {e}")
                logger.error(f"Expected path: {servo_cal_dir}")
                logger.error("Cannot proceed without servo calibration - fix the path and retry")
                return False
            except Exception as e:
                logger.error(f"❌ Servo calibration crashed with error: {e}")
                logger.exception("Full traceback:")
                logger.error("Cannot proceed without valid S/P positions")
                return False
        else:
            logger.info(f"\n[INFO] Device type '{device_type}' does not have servo polarizer")
            logger.info("Skipping servo calibration step\n")

        # ====================================================================
        # STEP 1.5: Move polarizer to S position for LED model training
        # ====================================================================
        if has_servo:
            logger.info("\n" + "=" * 80)
            logger.info("Moving polarizer to S position for LED model training...")
            logger.info("=" * 80)

            # Get S position from device_config.json
            try:
                import json

                # Use device-specific config path (matches where servo cal saves)
                from affilabs.utils.resource_path import get_affilabs_resource

                config_path = get_affilabs_resource(
                    f"config/devices/{detector_serial}/device_config.json"
                )

                # Fallback to global config if device-specific doesn't exist
                if not config_path.exists():
                    config_path = get_affilabs_resource("config/device_config.json")

                logger.info(f"Loading servo positions from: {config_path}")

                with open(config_path) as f:
                    device_config = json.load(f)

                # Servo positions are stored in hardware section
                s_pwm = device_config.get("hardware", {}).get("servo_s_position")

                if s_pwm is None:
                    logger.error("❌ S position not found in device_config.json!")
                    logger.error(f"   Config path: {config_path}")
                    logger.error(f"   Hardware section: {device_config.get('hardware', {})}")
                    return False

                logger.info(f"Moving servo to S position: {s_pwm} PWM")

                # Convert PWM to degrees for sv command
                s_degrees = int(s_pwm * 180.0 / 255.0)

                # Access underlying controller (ctrl is PicoP4SPRAdapter wrapper)
                raw_ctrl = ctrl._ctrl if hasattr(ctrl, "_ctrl") else ctrl

                # Use sv+sp commands (works for P4SPR)
                sv_cmd = f"sv{s_degrees:03d}{s_degrees:03d}\n"
                raw_ctrl._ser.write(sv_cmd.encode())
                time.sleep(0.1)
                raw_ctrl._ser.readline()  # Read ACK

                raw_ctrl._ser.write(b"sp\n")
                time.sleep(2.0)  # Wait for servo to reach position
                raw_ctrl._ser.readline()  # Read ACK

                logger.info("[OK] Polarizer moved to S position")

            except Exception as e:
                logger.error(f"❌ Failed to move polarizer to S position: {e}")
                return False

        # ====================================================================
        # STEP 2/2: LED Calibration Model Training
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

        # Persist ultra_sensitive flag to device_config.json
        try:
            with open(model_file) as f:
                saved_model = json.load(f)
            is_ultra = saved_model.get("ultra_sensitive", False)
            from affilabs.utils.resource_path import get_affilabs_resource
            config_path = get_affilabs_resource(f"config/devices/{detector_serial}/device_config.json")
            if config_path.exists():
                with open(config_path) as f:
                    cfg = json.load(f)
                cfg.setdefault("hardware", {})["ultra_sensitive"] = is_ultra
                with open(config_path, "w") as f:
                    json.dump(cfg, f, indent=2)
                logger.info(f"[OK] device_config.json updated: ultra_sensitive={is_ultra}")
        except Exception as e:
            logger.warning(f"Could not update ultra_sensitive in device_config.json: {e}")

        return True

    except Exception as e:
        logger.error(f"❌ OEM workflow failed: {e}")
        logger.exception("Full traceback:")
        return False
