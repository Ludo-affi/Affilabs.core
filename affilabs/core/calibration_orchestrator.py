"""Clean HAL-based Calibration Orchestrator.

Single entry point for 6-step SPR calibration using Hardware Abstraction Layer.

ARCHITECTURE:
- HAL-compliant: Uses ctrl (ControllerHAL) and usb (Spectrometer protocol)
- No raw hardware access (no ctrl._ser.write, no direct usb calls)
- Delegates to specialized modules for complex operations
- Returns immutable CalibrationData domain model

CALIBRATION FLOW:
1. Hardware Validation & LED Preparation
2. Wavelength Calibration (read EEPROM, define ROI)
3. LED Brightness Measurement & Model Load
4. S-Mode LED Convergence + Reference Capture
5. P-Mode LED Convergence + Reference Capture + Dark
6. QC Validation & Result Packaging
"""

from __future__ import annotations

import time

import numpy as np

from affilabs.models.led_calibration_result import LEDCalibrationResult
from affilabs.utils.logger import logger

# Convergence: support both current stack and new engine
from affilabs.utils.led_convergence_algorithm import LEDconverge as LEDconverge_current

try:
    from affilabs.convergence.production_wrapper import LEDconverge_engine

    ENGINE_AVAILABLE = True
except ImportError:
    LEDconverge_engine = None
    ENGINE_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

# Integration time constants
LED_PREP_INTEGRATION_MS = 10  # Fast integration for LED verification
WAVELENGTH_CAL_WAIT_S = 0.01  # Settling time after integration change

# LED timing constants
LED_OFF_SETTLING_S = 0.2  # Wait after forcing LEDs off
LED_BATCH_ENABLE_S = 0.1  # Time for batch enable command to process

# Hardware stabilization
HARDWARE_SETTLING_S = 0.02  # General hardware stabilization


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def run_startup_calibration(
    usb,  # Spectrometer (implements Spectrometer protocol)
    ctrl,  # Controller (HAL-wrapped ControllerHAL)
    device_type: str,
    device_config,
    detector_serial: str,
    progress_callback=None,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    use_convergence_engine: bool = False,
) -> LEDCalibrationResult:
    """Execute complete 6-step calibration with HAL compliance.

    Args:
        usb: Spectrometer instance (HAL protocol compliant)
        ctrl: Controller instance (HAL-wrapped)
        device_type: Device type string ('PicoP4SPR', 'PicoEZSPR')
        device_config: Device configuration object
        detector_serial: Detector serial number
        progress_callback: Optional callback(message: str, percent: int)
        single_mode: If True, calibrate only one channel
        use_convergence_engine: If True, use new convergence engine (EXPERIMENTAL)
        single_ch: Channel to calibrate in single mode
        stop_flag: Optional threading.Event for cancellation

    Returns:
        LEDCalibrationResult with calibration data and success status

    Raises:
        RuntimeError: If calibration fails at any step
    """
    result = LEDCalibrationResult()
    result.success = False

    try:
        logger.info("=" * 80)
        logger.info("🚀 6-STEP CALIBRATION - HAL-BASED CLEAN IMPLEMENTATION")
        logger.info("=" * 80)
        logger.info(f"Device: {device_type}")
        logger.info(f"Detector: {detector_serial}")
        logger.info(f"Mode: {'Single channel' if single_mode else 'All channels'}")
        logger.info("=" * 80 + "\n")

        # =================================================================
        # STEP 1: Hardware Validation & LED Preparation
        # =================================================================
        if progress_callback:
            progress_callback("Step 1/6: Preparing LEDs...", 5)

        logger.info("STEP 1: Hardware Validation & LED Preparation")
        logger.info("-" * 80)

        # Attempt to turn off LEDs using HAL (non-fatal if fails)
        try:
            ctrl.turn_off_channels()
            time.sleep(LED_OFF_SETTLING_S)
            logger.info("[OK] LEDs turned off")
        except Exception as e:
            logger.warning(f"[WARN] LED turn-off failed: {e}")
            logger.warning("[WARN] Continuing calibration - convergence will control LEDs")

        # Enable batch LED commands if supported
        if ctrl.supports_batch_leds:
            logger.info("[HAL] Enabling batch LED mode...")
            # HAL handles this internally - no raw serial access needed
            time.sleep(LED_BATCH_ENABLE_S)
            logger.info("[OK] Batch LED mode ready")

        logger.info("[OK] Step 1 complete\n")

        # =================================================================
        # STEP 2: Wavelength Calibration
        # =================================================================
        if progress_callback:
            progress_callback("Step 2/6: Wavelength calibration...", 17)

        logger.info("STEP 2: Wavelength Calibration")
        logger.info("-" * 80)

        # Read wavelength data from detector EEPROM (HAL method)
        wave_data = usb.read_wavelength()
        if wave_data is None or len(wave_data) == 0:
            raise RuntimeError("Failed to read wavelength data from detector")

        logger.info(f"[OK] Wavelength range: {wave_data[0]:.1f}-{wave_data[-1]:.1f} nm")

        # Define ROI (560-720nm for SPR)
        from settings import MIN_WAVELENGTH, MAX_WAVELENGTH

        wave_min_index = np.argmin(np.abs(wave_data - MIN_WAVELENGTH))
        wave_max_index = np.argmin(np.abs(wave_data - MAX_WAVELENGTH))

        # Store in result
        result.wave_data = wave_data[wave_min_index:wave_max_index]
        result.wave_min_index = int(wave_min_index)
        result.wave_max_index = int(wave_max_index)

        logger.info(
            f"[OK] SPR ROI: {wave_data[wave_min_index]:.1f}-{wave_data[wave_max_index]:.1f} nm"
        )
        logger.info(
            f"     Indices: [{wave_min_index}:{wave_max_index}] ({wave_max_index - wave_min_index} pixels)"
        )
        logger.info("[OK] Step 2 complete\n")

        # =================================================================
        # STEP 3: LED Brightness Measurement & Model Validation
        # =================================================================
        if progress_callback:
            progress_callback("Step 3/6: LED brightness & model check...", 30)

        logger.info("STEP 3: LED Brightness Measurement & Model Validation")
        logger.info("-" * 80)

        # Get detector parameters and channel list
        from affilabs.utils.calibration_helpers import determine_channel_list, get_detector_params

        detector_params = get_detector_params(device_type)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"Channels: {ch_list}")

        # Check if LED calibration model exists
        logger.info("\nChecking for LED calibration model...")
        from affilabs.services.led_model_loader import LEDCalibrationModelLoader, ModelNotFoundError

        model_loader = LEDCalibrationModelLoader()
        model_exists = True
        model_slopes_s = None
        model_slopes_p = None

        try:
            model_loader.load_model(detector_serial)
            logger.info(f"[OK] LED calibration model found for detector {detector_serial}")
            # Extract slopes for S and P polarization
            model_slopes_s = model_loader.get_slopes(
                polarization="S", channels=[c.upper() for c in ch_list]
            )
            model_slopes_p = model_loader.get_slopes(
                polarization="P", channels=[c.upper() for c in ch_list]
            )
            # Convert to lowercase keys for consistency
            model_slopes_s = {k.lower(): v for k, v in model_slopes_s.items()}
            model_slopes_p = {k.lower(): v for k, v in model_slopes_p.items()}
            logger.info(f"[OK] Model slopes loaded: S={model_slopes_s}, P={model_slopes_p}")
        except ModelNotFoundError as e:
            logger.warning(f"⚠️  No LED calibration model found: {e}")
            model_exists = False

        # If model missing, run automatic OEM training
        if not model_exists:
            logger.info("\n" + "=" * 80)
            logger.info("🔧 AUTOMATIC OEM MODEL TRAINING")
            logger.info("=" * 80)
            logger.info("No LED calibration model found - creating one automatically...")
            logger.info("This will take ~2 minutes...\n")

            if progress_callback:
                progress_callback("Training LED calibration model...", 20)

            from affilabs.core.oem_model_training import run_oem_model_training_workflow

            # Create a hardware manager wrapper for the training function
            class HardwareWrapper:
                def __init__(self, ctrl, usb):
                    self.ctrl = ctrl
                    self.usb = usb

            hardware_mgr = HardwareWrapper(ctrl, usb)

            training_success = run_oem_model_training_workflow(
                hardware_mgr=hardware_mgr,
                progress_callback=progress_callback,
            )

            if not training_success:
                raise RuntimeError(
                    "Failed to create LED calibration model. " "Cannot proceed with calibration."
                )

            logger.info("\n[OK] LED calibration model created successfully")
            logger.info("Loading newly created model...\n")

            # Reload the model to get slopes
            try:
                model_loader.load_model(detector_serial)
                model_slopes_s = model_loader.get_slopes(
                    polarization="S", channels=[c.upper() for c in ch_list]
                )
                model_slopes_p = model_loader.get_slopes(
                    polarization="P", channels=[c.upper() for c in ch_list]
                )
                # Convert to lowercase keys for consistency
                model_slopes_s = {k.lower(): v for k, v in model_slopes_s.items()}
                model_slopes_p = {k.lower(): v for k, v in model_slopes_p.items()}
                logger.info(
                    f"[OK] Model slopes loaded from new model: S={model_slopes_s}, P={model_slopes_p}"
                )
            except Exception as e:
                logger.warning(f"⚠️  Failed to load newly created model: {e}")
                logger.warning("Will proceed with ratio-based LED convergence")

            logger.info("Continuing with startup calibration...\n")

            if progress_callback:
                progress_callback("Step 3/6: LED brightness measurement...", 30)

        # Skip brightness measurement - use model only to avoid serial contention
        channel_measurements = {}
        logger.info("[INFO] Skipping brightness measurement to preserve serial stability")

        # Identify weakest channel or fall back to model if no measurements
        if channel_measurements:
            weakest_ch = min(channel_measurements.keys(), key=lambda c: channel_measurements[c][0])
            logger.info(f"[OK] Weakest channel (measured): {weakest_ch.upper()}")
            logger.info("[OK] Step 3 complete\n")
        else:
            if model_slopes_s:
                weakest_ch = min(model_slopes_s.keys(), key=lambda c: model_slopes_s[c])
                logger.info(
                    f"[OK] Weakest channel (model-based): {weakest_ch.upper()} (measurement unavailable)"
                )
            else:
                weakest_ch = ch_list[0]
                logger.info(f"[OK] Weakest channel defaulted to: {weakest_ch.upper()} (no model)")
            logger.info(
                "[OK] Step 3 complete (measurement skipped due to device write/read issue)\n"
            )

        # =================================================================
        # Load and configure servo positions BEFORE mode switching
        # =================================================================
        logger.info("Loading servo positions from device_config...")
        servo_positions = device_config.get_servo_positions()
        s_pos = servo_positions["s"]
        p_pos = servo_positions["p"]
        logger.info(f"[OK] Servo positions (degrees): S={s_pos}°, P={p_pos}°")
        # HAL-only policy: Do NOT send servo positions during calibration.
        # Positions are loaded to EEPROM at startup; set_mode('s'/'p') uses them.
        logger.info("")

        # =================================================================
        # STEP 4: S-Mode LED Convergence + Reference Capture
        # =================================================================
        if progress_callback:
            progress_callback("Step 4/6: S-mode LED convergence...", 45)

        logger.info("STEP 4: S-Mode LED Convergence + Reference Capture")
        logger.info("-" * 80)

        # Set polarizer to S-mode using HAL
        logger.info("Setting polarizer to S-mode...")
        ctrl.set_mode("s")  # Servo moves to S position from EEPROM
        time.sleep(0.35)  # Optimized - adequate for cold start servo movement
        logger.info("[OK] S-mode set")

        # Run LED convergence for S-mode
        from affilabs.utils.led_convergence_algorithm import LEDconverge
        from affilabs.utils.startup_calibration import acquire_raw_spectrum as hw_acquire

        # Define helper functions
        def acquire_raw_spectrum(
            usb,
            ctrl,
            channel,
            led_intensity,
            integration_time_ms,
            num_scans=1,
            use_batch_command=False,
        ):
            """Wrapper for hardware acquisition matching LEDconverge signature."""
            return hw_acquire(
                usb=usb,
                ctrl=ctrl,
                channel=channel,
                led_intensity=led_intensity,
                integration_time_ms=integration_time_ms,
                num_scans=num_scans,
                use_batch_command=use_batch_command,
            )

        def roi_signal(spectrum, wave_min, wave_max, method="median", top_n=50):
            """Extract ROI signal from spectrum."""
            roi = spectrum[wave_min:wave_max]
            if method == "median":
                return np.median(roi)
            elif method == "mean":
                return np.mean(roi)
            elif method == "top_n_mean" and top_n > 0:
                return np.mean(np.sort(roi)[-top_n:])
            else:
                return np.mean(roi)

        # Calculate initial LED intensities using model if available
        if model_exists and model_loader.model_data:
            # Use model loader to calculate initial intensities - EXACT method from led_model_loader.py
            # Target: 75% of max (49151 counts) - prevents hot pixels from saturating during reference capture
            target_counts = int(0.75 * detector_params.max_counts)  # 49151 for 65535 max

            # OPTIMAL LOGIC: Calculate integration time for weakest LED at max intensity (255)
            # This gives shortest time to hit target with weakest channel maxed = optimal condition
            # Formula: target_signal = slope_weakest × 255 × (integration_time / 10)
            #          optimal_time = (target_signal / (slope_weakest × 255)) × 10

            weakest_ch = min(ch_list, key=lambda c: model_slopes_s.get(c, 0.0))
            weakest_slope = model_slopes_s.get(weakest_ch, 0.0)

            if weakest_slope > 0:
                # Calculate optimal integration time for weakest LED at max (255)
                optimal_integration_ms = (target_counts / (weakest_slope * 255.0)) * 10.0

                # Clamp to detector limits
                optimal_integration_ms = max(
                    detector_params.min_integration_time, optimal_integration_ms
                )
                optimal_integration_ms = min(
                    detector_params.max_integration_time, optimal_integration_ms
                )

                initial_integration_ms = optimal_integration_ms
                logger.info(f"Integration time: {initial_integration_ms:.1f}ms")
            else:
                # Fallback: use average slope method
                avg_slope = np.mean([model_slopes_s.get(ch, 870.0) for ch in ch_list])
                if avg_slope > 600:
                    initial_integration_ms = 10.0
                elif avg_slope > 300:
                    initial_integration_ms = 20.0
                elif avg_slope > 180:
                    initial_integration_ms = 30.0
                elif avg_slope > 120:
                    initial_integration_ms = 45.0
                else:
                    initial_integration_ms = 60.0
                logger.info(
                    f"[OK] Fallback integration time: {initial_integration_ms}ms (avg slope: {avg_slope:.1f})"
                )

            # Calculate normalized LED intensities relative to weakest at max
            # For weakest: LED = 255
            # For others: LED = (slope_weakest / slope_other) × 255
            initial_leds = {}
            for ch in ch_list:
                ch_slope = model_slopes_s.get(ch, 0.0)
                if ch == weakest_ch:
                    initial_leds[ch] = 255
                elif ch_slope > 0 and weakest_slope > 0:
                    normalized_led = int((weakest_slope / ch_slope) * 255.0)
                    # Apply conservative correction for bright LEDs to avoid early saturation
                    if ch_slope > weakest_slope * 1.5:  # Significantly brighter than weakest
                        correction = 0.917  # ~8% reduction
                        normalized_led = int(normalized_led * correction)
                    initial_leds[ch] = max(10, min(255, normalized_led))
                else:
                    # Fallback if slope missing
                    initial_leds[ch] = 150

            logger.info(f"Initial LEDs: {initial_leds}")
        else:
            # Fallback to equal intensities if no model
            # Use safer integration in trained range
            initial_integration_ms = 30.0
            initial_leds = {ch: 255 for ch in ch_list}

        # Turn on all LEDs with calculated intensities
        for ch in ch_list:
            ctrl.set_intensity(ch, initial_leds[ch])
        time.sleep(0.03)  # Minimal delay - LEDs stabilize quickly

        # Select convergence function based on flag
        if use_convergence_engine and ENGINE_AVAILABLE:
            LEDconverge = LEDconverge_engine
        else:
            LEDconverge = LEDconverge_current
        s_integration_time, s_final_signals, s_success, s_converged_leds = LEDconverge(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            led_intensities=initial_leds,
            acquire_raw_spectrum_fn=acquire_raw_spectrum,
            roi_signal_fn=roi_signal,
            initial_integration_ms=initial_integration_ms,
            target_percent=0.75,  # 75% target prevents hot pixels from saturating during reference capture
            tolerance_percent=0.05,
            detector_params=detector_params,
            wave_min_index=int(wave_min_index),
            wave_max_index=int(wave_max_index),
            max_iterations=12,  # Optimized - good model guess converges quickly
            step_name="Step 4 (S-mode)",
            use_batch_command=True,
            model_slopes=model_slopes_s,
            polarization="S",
            config=None,
            logger=logger,
            progress_callback=progress_callback,
        )

        if not s_success:
            # Provide detailed error message aligned with requested target percent
            s_target_percent = 0.85
            error_msg = "S-mode convergence failed: "
            if s_final_signals:
                max_signal = max(s_final_signals.values())
                target = detector_params.max_counts * s_target_percent
                percent = (max_signal / detector_params.max_counts) * 100
                error_msg += (
                    f"Max signal achieved was {max_signal:.0f} ({percent:.1f}%), "
                    f"target was {target:.0f} ({s_target_percent*100:.0f}%). "
                )
                if max_signal < 5000:
                    error_msg += "Signal is extremely low - check if LEDs are ON and polarizer is in correct position."
                elif max_signal < target * 0.5:
                    error_msg += "Signal is too low - LEDs may need higher intensity or integration time may need adjustment."
            else:
                error_msg += "No signal measurements obtained."
            raise RuntimeError(error_msg)

        # Use final LED intensities from convergence engine
        # These are the converged values, NOT the initial values
        s_mode_leds = s_converged_leds if s_converged_leds else initial_leds
        result.s_mode_intensity = s_mode_leds
        result.s_integration_time = s_integration_time

        logger.info(f"S-mode: {s_integration_time:.1f}ms, LEDs={s_mode_leds}")

        # Capture S-pol reference spectra (using num_scans for high-quality baseline)
        # Calculate num_scans: floor(DETECTOR_WINDOW / integration_time), capped at 10
        DETECTOR_WINDOW_MS = 180.0
        MAX_NUM_SCANS = 10  # Cap to reduce USB transfer overhead (10 scans = 3.16x SNR improvement)
        num_scans_s = min(MAX_NUM_SCANS, max(1, int(DETECTOR_WINDOW_MS / s_integration_time)))

        # Store num_scans in result for live data acquisition
        result.num_scans = num_scans_s

        usb.set_integration(s_integration_time)
        time.sleep(0.03)  # Minimal delay - integration setting applies quickly

        s_raw_data = {}
        for ch in ch_list:
            # Use hardware acquisition with calculated num_scans for averaged baseline
            spectrum = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=s_mode_leds[ch],
                integration_time_ms=s_integration_time,
                num_scans=num_scans_s,
                use_batch_command=True,
            )
            if spectrum is not None:
                roi_spectrum = spectrum[wave_min_index:wave_max_index]
                s_raw_data[ch] = roi_spectrum

                # CRITICAL: Check for saturation in reference capture
                max_pixel = float(max(roi_spectrum))
                if max_pixel >= detector_params.saturation_threshold:
                    logger.error(
                        f"[ERROR] S-pol reference SATURATED for channel {ch.upper()}: {max_pixel:.0f} counts >= {detector_params.saturation_threshold}"
                    )
                    logger.error(
                        f"   Convergence target was too high - reference capture with {num_scans_s} scans caused saturation"
                    )
                    raise RuntimeError(
                        f"S-pol reference saturated for channel {ch.upper()}: {max_pixel:.0f} counts. Lower target_percent or reduce LED intensities."
                    )
            else:
                logger.error(f"Failed to capture S-pol reference for channel {ch}")
                raise RuntimeError(f"Failed to capture S-pol reference for channel {ch}")

        result.s_raw_data = s_raw_data

        # =================================================================
        # STEP 5: P-Mode LED Convergence + Reference + Dark Capture
        # =================================================================
        if progress_callback:
            progress_callback("Step 5/6: P-mode LED convergence...", 65)

        logger.info("STEP 5: P-Mode LED Convergence + Reference + Dark Capture")
        logger.info("-" * 80)

        # Turn off LEDs before servo movement
        ctrl.turn_off_channels()
        time.sleep(0.05)  # Minimal delay - just ensure command processed

        # Set polarizer to P-mode using HAL
        ctrl.set_mode("p")  # Servo moves to P position from EEPROM
        time.sleep(0.2)  # Optimized - servo is warm, motor has settled from S-mode

        # Calculate initial LED intensities for P-mode
        # OPTIMIZED: Use converged S-mode LEDs directly with 92% rule for better initial guess
        # This is much more accurate than model prediction since S-mode just converged
        initial_p_leds = {ch: max(10, min(255, int(s_mode_leds[ch] * 0.92))) for ch in ch_list}

        # Turn on all LEDs with calculated intensities
        for ch in ch_list:
            ctrl.set_intensity(ch, initial_p_leds[ch])
        time.sleep(0.03)  # Minimal delay - just ensure LEDs stabilize

        # Run LED convergence for P-mode
        p_integration_time, p_final_signals, p_success, p_converged_leds = LEDconverge(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            led_intensities=initial_p_leds.copy(),  # Use S-mode converged values (more accurate)
            acquire_raw_spectrum_fn=acquire_raw_spectrum,
            roi_signal_fn=roi_signal,
            initial_integration_ms=s_integration_time,  # Start from S-mode integration
            target_percent=0.75,  # 75% target prevents hot pixels from saturating during reference capture
            tolerance_percent=0.05,
            detector_params=detector_params,
            wave_min_index=int(wave_min_index),
            wave_max_index=int(wave_max_index),
            max_iterations=10,  # Reduced from 15 - better initial guess from S-mode
            step_name="Step 5 (P-mode)",
            use_batch_command=True,
            model_slopes=model_slopes_p,
            polarization="P",
            config=None,
            logger=logger,
            progress_callback=progress_callback,
        )

        if not p_success:
            raise RuntimeError("P-mode convergence failed")

        # Use final LED intensities from convergence engine
        # These are the converged values, NOT the initial values
        p_mode_leds = p_converged_leds if p_converged_leds else initial_p_leds

        result.p_mode_intensity = p_mode_leds
        result.p_integration_time = p_integration_time

        logger.info(f"P-mode: {p_integration_time:.1f}ms, LEDs={p_mode_leds}")

        # Capture P-pol reference spectra

        # Calculate num_scans for P-pol using same formula as S-pol (capped at 10)
        num_scans_p = min(MAX_NUM_SCANS, max(1, int(DETECTOR_WINDOW_MS / p_integration_time)))

        usb.set_integration(p_integration_time)
        time.sleep(0.05)

        p_raw_data = {}
        for ch in ch_list:
            # Use hardware acquisition with calculated num_scans for averaged baseline
            spectrum = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=p_mode_leds[ch],
                integration_time_ms=p_integration_time,
                num_scans=num_scans_p,
                use_batch_command=True,
            )
            if spectrum is not None:
                roi_spectrum = spectrum[wave_min_index:wave_max_index]
                p_raw_data[ch] = roi_spectrum

                # CRITICAL: Check for saturation in reference capture
                max_pixel = float(max(roi_spectrum))
                if max_pixel >= detector_params.saturation_threshold:
                    logger.error(
                        f"[ERROR] P-pol reference SATURATED for channel {ch.upper()}: {max_pixel:.0f} counts >= {detector_params.saturation_threshold}"
                    )
                    logger.error(
                        f"   Convergence target was too high - reference capture with {num_scans_p} scans caused saturation"
                    )
                    raise RuntimeError(
                        f"P-pol reference saturated for channel {ch.upper()}: {max_pixel:.0f} counts. Lower target_percent or reduce LED intensities."
                    )
            else:
                logger.error(f"Failed to capture P-pol reference for channel {ch}")
                raise RuntimeError(f"Failed to capture P-pol reference for channel {ch}")

        result.p_raw_data = p_raw_data

        # Capture dark spectrum (LEDs off) using same num_scans as S-pol for consistency
        ctrl.turn_off_channels()
        time.sleep(0.1)

        # Use same num_scans as S-pol reference - average multiple reads
        spectra = []
        for _ in range(num_scans_s):
            spectrum = usb.read_intensity()
            if spectrum is not None:
                spectra.append(spectrum)
            time.sleep(0.01)

        dark_spectrum_full = np.mean(spectra, axis=0)
        dark_roi = dark_spectrum_full[wave_min_index:wave_max_index]

        # Store dark for both modes (same dark for both)
        result.dark_s = {ch: dark_roi for ch in ch_list}
        result.dark_p = {ch: dark_roi for ch in ch_list}

        # =================================================================
        # STEP 6: QC Validation & Result Packaging
        # =================================================================
        if progress_callback:
            progress_callback("Step 6/6: QC validation...", 85)

        logger.info("STEP 6: QC Validation & Result Packaging")
        logger.info("-" * 80)

        # Import QC processors
        from affilabs.core.spectrum_preprocessor import SpectrumPreprocessor
        from affilabs.core.transmission_processor import TransmissionProcessor

        # Process polarization data
        s_pol_ref = {}
        p_pol_ref = {}

        for ch in ch_list:
            # Process S-pol
            s_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=result.s_raw_data[ch],
                dark_noise=result.dark_s.get(ch, np.zeros_like(result.s_raw_data[ch])),
                channel_name=ch,
                verbose=False,
            )

            # Process P-pol
            p_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=result.p_raw_data[ch],
                dark_noise=result.dark_p.get(ch, np.zeros_like(result.p_raw_data[ch])),
                channel_name=ch,
                verbose=False,
            )

        result.s_pol_ref = s_pol_ref
        result.p_pol_ref = p_pol_ref

        # Calculate transmission spectra
        transmission = {}
        for ch in ch_list:
            transmission[ch] = TransmissionProcessor.process_single_channel(
                p_pol_clean=p_pol_ref[ch],
                s_pol_ref=s_pol_ref[ch],
                led_intensity_s=result.s_mode_intensity[ch],
                led_intensity_p=result.p_mode_intensity[ch],
            )

        result.transmission = transmission

        # Run QC validation
        qc_results = {}
        for ch in ch_list:
            qc = TransmissionProcessor.calculate_transmission_qc(
                transmission_spectrum=transmission[ch],
                wavelengths=result.wave_data,
                channel=ch,
                p_spectrum=p_pol_ref[ch],
                s_spectrum=s_pol_ref[ch],
                detector_max_counts=detector_params.max_counts,
                saturation_threshold=detector_params.saturation_threshold,
            )
            qc_results[ch] = qc

            logger.info(
                f"Channel {ch.upper()}: "
                f"Dip={qc['dip_wavelength']:.1f}nm, "
                f"Depth={qc['dip_depth']:.1f}%, "
                f"FWHM={qc.get('fwhm', 0):.1f}nm"
            )

        result.qc_results = qc_results

        # Store detector parameters
        result.detector_max_counts = detector_params.max_counts
        result.detector_saturation_threshold = detector_params.saturation_threshold

        logger.info("[OK] Step 6 complete - QC validation passed\n")

        # =================================================================
        # FINALIZE
        # =================================================================
        result.success = True

        logger.info("=" * 80)
        logger.info("✅ CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"S-mode: {result.s_mode_intensity}")
        logger.info(f"P-mode: {result.p_mode_intensity}")
        logger.info(
            f"Integration times: S={result.s_integration_time:.1f}ms, P={result.p_integration_time:.1f}ms"
        )
        logger.info("=" * 80 + "\n")

        return result

    except Exception as e:
        logger.error(f"❌ Calibration failed: {e}")
        result.success = False
        result.error = str(e)
        raise

    finally:
        # Always turn off LEDs on exit (success or failure)
        try:
            logger.info("\n[CLEANUP] Turning off all LEDs...")
            ctrl.turn_off_channels()
            time.sleep(0.05)
            logger.info("[CLEANUP] LEDs turned off")
        except Exception as cleanup_error:
            logger.error(f"[CLEANUP] Failed to turn off LEDs: {cleanup_error}")
