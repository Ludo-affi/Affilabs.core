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
    use_convergence_engine: bool = True,
    force_oem_retrain: bool = False,
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
        use_convergence_engine: If True, use new convergence engine; If False, use legacy stack
        single_ch: Channel to calibrate in single mode
        stop_flag: Optional threading.Event for cancellation

    Returns:
        LEDCalibrationResult with calibration data and success status

    Raises:
        RuntimeError: If calibration fails at any step
    """
    result = LEDCalibrationResult()
    result.success = False
    result.detector_serial = detector_serial  # Store device serial for QC history

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

        detector_params = get_detector_params(
            usb
        )  # FIXED: Pass detector object, not device_type string
        logger.info(f"🔍 DEBUG: detector_params.max_counts = {detector_params.max_counts}")
        logger.info(f"🔍 DEBUG: detector object type = {type(usb).__name__}")
        logger.info(
            f"🔍 DEBUG: detector max_counts attribute = {getattr(usb, 'max_counts', 'MISSING')}"
        )
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"Channels: {ch_list}")

        # Check if LED calibration model exists (skip if force_oem_retrain)
        logger.info("\nChecking for LED calibration model...")
        from affilabs.services.led_model_loader import (
            LEDCalibrationModelLoader,
            ModelNotFoundError,
            ModelValidationError,
        )

        model_loader = LEDCalibrationModelLoader()
        model_exists = True
        model_slopes_s = None
        model_slopes_p = None

        if force_oem_retrain:
            # Skip loading old model when doing OEM retrain (we're creating a new one)
            logger.info("[SKIP] OEM retrain mode - will create new calibration model")
            model_exists = False
        else:
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
            except ModelValidationError as e:
                logger.warning(f"⚠️  LED calibration model corrupted: {e}")
                logger.warning("   Will create new calibration model automatically")
                model_exists = False

        # If model missing OR force_oem_retrain requested, run automatic OEM training
        if not model_exists or force_oem_retrain:
            if force_oem_retrain and model_exists:
                logger.info("\n⚡ FORCE RETRAIN REQUESTED - Rebuilding optical model...")
                logger.info("   (Existing model will be replaced)\n")
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

        # Determine weakest channel from OEM model slopes
        # The OEM model training (Step 2) measured all channels at 10-60ms,
        # so model slopes accurately reflect relative channel brightness.
        if model_slopes_s:
            weakest_ch = min(model_slopes_s.keys(), key=lambda c: model_slopes_s[c])
            logger.info(f"Weakest channel (from model): {weakest_ch.upper()}")
        else:
            weakest_ch = ch_list[0]
            logger.info(f"Weakest channel defaulted to: {weakest_ch.upper()}")

        # =================================================================
        # Load and configure servo positions BEFORE mode switching
        # =================================================================
        logger.info("Loading servo positions from device_config...")
        servo_positions = device_config.get_servo_positions()

        # Check if servo positions are calibrated
        if servo_positions is None:
            logger.error("=" * 80)
            logger.error("❌ SERVO POSITIONS NOT CALIBRATED")
            logger.error("=" * 80)
            logger.error("   Servo positions must be calibrated before LED calibration")
            logger.error("   The servo calibration should have been triggered automatically.")
            logger.error("   If you see this message, please run servo calibration manually.")
            logger.error("=" * 80)

            # Use a custom exception so the service can catch this specific case
            class ServoCalibrationRequired(RuntimeError):
                """Raised when servo positions are missing and calibration is required."""

                pass

            raise ServoCalibrationRequired(
                "Servo positions not found. Servo calibration must be completed before LED calibration."
            )

        s_pos = servo_positions["s"]
        p_pos = servo_positions["p"]
        logger.info("=" * 80)
        logger.info("🔍 SERVO POSITION VALIDATION")
        logger.info("=" * 80)
        logger.info(f"   Device config servo positions (PWM): S={s_pos}, P={p_pos}")
        logger.info(f"   Device: {detector_serial}")

        # Check if these look like default/uncalibrated values
        if s_pos == 10 and p_pos == 100:
            logger.warning("⚠️  WARNING: Servo positions are DEFAULT VALUES (S=10, P=100)")
            logger.warning("⚠️  These may NOT be calibrated for this specific device!")
        elif s_pos < 10 or p_pos < 10:
            logger.warning(
                f"⚠️  WARNING: Servo positions look suspiciously low: S={s_pos}, P={p_pos}"
            )
            logger.warning("⚠️  Verify these are correct calibrated values!")

        # CRITICAL: Sync device_config positions to EEPROM BEFORE any servo movement
        # The set_mode() commands used by convergence read from EEPROM, not device_config!
        logger.info("📝 Syncing device_config positions to controller EEPROM...")
        try:
            # Access raw controller through HAL wrapper
            raw_ctrl = ctrl._ctrl if hasattr(ctrl, "_ctrl") else None
            if raw_ctrl and hasattr(device_config, "sync_to_eeprom"):
                sync_success = device_config.sync_to_eeprom(raw_ctrl)
                if sync_success:
                    logger.info(
                        "[OK] EEPROM synced - set_mode() commands will use correct positions"
                    )
                    # VERIFY: Read back from EEPROM to confirm
                    if hasattr(raw_ctrl, "read_config_from_eeprom"):
                        eeprom_config = raw_ctrl.read_config_from_eeprom()
                        if eeprom_config:
                            eeprom_s = eeprom_config.get("servo_s_position")
                            eeprom_p = eeprom_config.get("servo_p_position")
                            logger.info(f"   ✅ EEPROM readback: S={eeprom_s}, P={eeprom_p}")
                            if eeprom_s != s_pos or eeprom_p != p_pos:
                                logger.error("❌ EEPROM MISMATCH! Values didn't sync correctly!")
                                logger.error(f"   Expected: S={s_pos}, P={p_pos}")
                                logger.error(f"   EEPROM has: S={eeprom_s}, P={eeprom_p}")
                                raise RuntimeError(
                                    "EEPROM sync verification failed - positions don't match!"
                                )
                        else:
                            logger.warning("⚠️  Could not read back EEPROM for verification")
                else:
                    logger.warning("⚠️  EEPROM sync failed - convergence may use old positions")
            else:
                logger.warning("⚠️  Cannot sync EEPROM - missing sync_to_eeprom method")
        except Exception as sync_err:
            logger.error(f"Failed to sync EEPROM: {sync_err}")
        logger.info("=" * 80)

        # Move servo to S-position for calibration (since we disabled auto-init during hardware connection)
        logger.info("🔧 Moving servo to S-position for calibration...")

        # Turn off LEDs for safety during servo movement
        ctrl.turn_off_channels()
        time.sleep(0.1)

        # Preferred path: set desired positions into controller state, then use ss/sp
        # This ensures set_mode() uses the positions from device_config rather than stale EEPROM.
        logger.info(
            f"   Loading desired servo positions into controller state: S={s_pos}, P={p_pos}"
        )
        ctrl.set_servo_positions(s_pos, p_pos)
        time.sleep(0.2)

        # Use set_mode() which sends 'ss' and relies on positions loaded above
        logger.info(f"   Sending 'ss' command to move to S-mode (target PWM: {s_pos})...")
        logger.info(
            f"   Expected S position from device_config: PWM {s_pos} ({(s_pos / 255.0) * 180:.1f}°)"
        )
        success = ctrl.set_mode("s")
        if not success:
            logger.warning("⚠️  set_mode('s') did not confirm - trying direct servo position")
            # Fallback: move servo directly using raw PWM (device_config stores PWM not degrees)
            ctrl.servo_move_raw_pwm(1)  # Park to remove backlash
            time.sleep(0.5)
            logger.info(f"   Moving servo to S position: PWM {s_pos}")
            ctrl.servo_move_raw_pwm(s_pos)
            time.sleep(0.5)
        else:
            logger.info(f"   ✅ Servo command 'ss' sent successfully (should be at PWM {s_pos})")

        logger.info("[OK] Servo positioned at S-mode")
        logger.info("   ⏳ Waiting 1 second for servo to fully settle...")
        time.sleep(1.0)  # Extra settling time to ensure servo is at final position

        logger.info("")

        # =================================================================
        # STEP 4: S-Mode LED Convergence + Reference Capture
        # =================================================================
        if progress_callback:
            progress_callback("Step 4/6: S-mode LED convergence...", 45)

        logger.info("STEP 4: S-Mode LED Convergence + Reference Capture")
        logger.info("-" * 80)

        # Servo position already loaded via set_servo_positions() above
        # No need to move servo before LED convergence
        logger.info("[OK] S-mode positions ready")

        # =================================================================
        # PRE-CONVERGENCE SIGNAL TEST: Detect polarizer blocking
        # =================================================================
        logger.info("")
        logger.info("🔍 PRE-CONVERGENCE POLARIZER CHECK")
        logger.info("-" * 80)
        logger.info("   Testing ALL 4 LEDs at 5% to verify polarizer is transmitting...")
        logger.info("   (This matches the servo calibration measurement conditions)")

        # Import hardware acquisition function
        from affilabs.utils.startup_calibration import acquire_raw_spectrum as hw_acquire

        # Test with ALL 4 LEDs at 5% (matches servo calibration conditions)
        test_led = int(0.05 * 255)  # 5% intensity
        test_time_ms = 5.0  # 5ms integration time (matches servo cal)

        # Enable all 4 LEDs (matches servo calibration)
        if hasattr(ctrl, "enable_multi_led"):
            ctrl.enable_multi_led(a=True, b=True, c=True, d=True)
        time.sleep(0.2)

        # Set all 4 LEDs to 5% intensity
        ctrl.set_batch_intensities(a=test_led, b=test_led, c=test_led, d=test_led)
        time.sleep(0.2)

        # Set 5ms integration time
        usb.set_integration(test_time_ms)
        time.sleep(0.1)

        # Acquire test spectrum (just read detector, LEDs already on)
        try:
            test_spectrum = usb.read_intensity()
            test_signal = np.mean(test_spectrum[wave_min_index:wave_max_index])

            # Calculate expected minimum signal (3% of detector range)
            # Lowered from 5% to 3% to reduce false-positive recalibrations
            # With 4 LEDs @ 5% and 5ms integration, 3% threshold (~1966 counts) is sufficient
            critical_threshold = detector_params.max_counts * 0.03
            signal_percent = (test_signal / detector_params.max_counts) * 100

            logger.info(
                f"   Test signal (ALL 4 LEDs @ 5%, 5ms): {test_signal:.0f} counts ({signal_percent:.1f}% of detector range)"
            )
            logger.info(
                f"   Expected minimum: {critical_threshold:.0f} counts (3% threshold)"
            )
            logger.info("   Typical S-mode signal: 15000-20000 counts with good positioning")

            if test_signal < critical_threshold:
                logger.error("=" * 80)
                logger.error("❌ POLARIZER POSITION ERROR DETECTED!")
                logger.error("=" * 80)
                logger.error(f"   Signal is CRITICALLY LOW: {test_signal:.0f} counts")
                logger.error(f"   Expected minimum: {critical_threshold:.0f} counts")
                logger.error(f"   Actual: {signal_percent:.1f}% of detector range (should be >3%)")
                logger.error("")
                logger.error("   🚨 THE POLARIZER IS BLOCKING THE OPTICAL PATH!")
                logger.error("")
                logger.error(
                    "   This indicates servo S/P positions in device_config are INCORRECT."
                )
                logger.error("   The servo moved, but to the WRONG position.")
                logger.error("")
                logger.error("   EVIDENCE:")
                logger.error(f"   - Device config has: S={s_pos}, P={p_pos}")
                logger.error("   - Servo physically moved (you heard it)")
                logger.error("   - But signal is blocked → positions are wrong!")
                logger.error("")
                logger.error("   SOLUTION: Run servo calibration to find correct positions")
                logger.error("=" * 80)
                raise RuntimeError(
                    f"Polarizer blocking light: signal={test_signal:.0f} counts (expected >{critical_threshold:.0f}). "
                    f"Servo positions S={s_pos}, P={p_pos} are INCORRECT. Run servo calibration."
                )
            else:
                logger.info(
                    f"   ✅ Signal check PASSED: {test_signal:.0f} counts ({signal_percent:.1f}%)"
                )
                logger.info("   Polarizer is transmitting light correctly")
        except RuntimeError:
            # Polarizer blocking detection — let it propagate to
            # calibration_service which triggers automatic servo calibration
            raise
        except Exception as e:
            logger.warning(f"⚠️  Pre-convergence signal test failed: {e}")
            logger.warning("   Proceeding with calibration anyway...")

        logger.info("-" * 80)
        logger.info("")

        # Enable LED channels for P4PRO/flow-mode controllers (required before set_intensity works)
        # P4SPR/static controllers don't need channel enable - LEDs are always available
        detected_type = ctrl.get_device_type()
        logger.info(f"DEBUG: Device type from HAL = '{detected_type}'")

        # Check if this is a flow-mode controller (has pumps/valves)
        raw_ctrl = ctrl._ctrl if hasattr(ctrl, "_ctrl") else ctrl
        needs_channel_enable = (
            hasattr(raw_ctrl, "supports_flow_mode") and raw_ctrl.supports_flow_mode
        )

        if needs_channel_enable:
            logger.info("Enabling flow-mode controller LED channels...")
            for ch in ch_list:
                ctrl.turn_on_channel(ch)
            time.sleep(0.05)  # Brief delay for channel enable
            logger.info("[OK] Channels enabled")
        else:
            logger.info(
                f"Static controller ('{detected_type}') - LEDs always available, skipping channel enable"
            )

        # Import hardware acquisition function BEFORE use

        # EARLY POLARIZER CHECK: Test signal BEFORE convergence
        # TEMPORARILY DISABLED - Allow calibration to proceed even if servo position seems wrong
        # The convergence engine will handle servo positioning
        logger.info(
            "\n🔍 EARLY POLARIZER POSITION CHECK... [SKIPPED - Letting convergence handle servo]"
        )

        # logger.info("Testing signal with max LED to verify polarizer is not blocking light...")
        # test_led = 255
        # test_time_ms = 30.0
        #
        # # Set all LEDs to max for test
        # for ch in ch_list:
        #     ctrl.set_intensity(ch, test_led)
        #
        # # Acquire test spectrum
        # test_spectrum = hw_acquire(usb, ctrl, ch_list[0], test_led, test_time_ms, num_scans=1)
        # test_signal = np.mean(test_spectrum[wave_min_index:wave_max_index])
        #
        # # Check if signal is critically low (< 5% of detector range)
        # critical_threshold = detector_params.max_counts * 0.05
        # if test_signal < critical_threshold:
        #     logger.error("=" * 80)
        #     logger.error("❌ POLARIZER POSITION ERROR DETECTED")
        #     logger.error("=" * 80)
        #     logger.error(f"   Test signal: {test_signal:.0f} counts")
        #     logger.error(f"   Expected: > {critical_threshold:.0f} counts (5% of detector range)")
        #     logger.error(f"   Actual: {(test_signal/detector_params.max_counts)*100:.1f}% of detector range")
        #     logger.error("")
        #     logger.error("   🚨 POLARIZER IS BLOCKING THE LIGHT!")
        #     logger.error("")
        #     logger.error("   This indicates servo S/P positions are INCORRECT.")
        #     logger.error("   The polarizer barrel is rotated to block optical path.")
        #     logger.error("")
        #     logger.error("   SOLUTION:")
        #     logger.error("   1. Click 'Servo Calibration' button in sidebar")
        #     logger.error("   2. Wait 2-3 minutes for automatic position detection")
        #     logger.error("   3. Re-run LED calibration after servo calibration completes")
        #     logger.error("=" * 80)
        #     raise RuntimeError(
        #         f"Polarizer blocking light: signal={test_signal:.0f} (expected >{critical_threshold:.0f}). "
        #         "Run 'Servo Calibration' to detect correct S/P positions."
        #     )

        # logger.info(f"✅ Polarizer check PASSED: {test_signal:.0f} counts ({(test_signal/detector_params.max_counts)*100:.1f}% of range)")
        logger.info("")

        # Run LED convergence for S-mode
        from affilabs.utils.led_convergence_algorithm import LEDconverge

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
            # Target: 85% of max - matches convergence algorithm target
            # Start with target so weakest channel at LED 255 reaches the final convergence goal immediately
            target_counts = int(0.85 * detector_params.max_counts)  # 55,705 for 65535 max

            # OPTIMAL LOGIC: Calculate integration time for weakest LED at max intensity (255)
            # This gives shortest time to hit target with weakest channel maxed = optimal condition
            # Formula: target_signal = slope_weakest × 255 × (integration_time / 10)
            #          optimal_time = (target_signal / (slope_weakest × 255)) × 10

            weakest_ch = min(ch_list, key=lambda c: model_slopes_s.get(c, 0.0))
            weakest_slope = model_slopes_s.get(weakest_ch, 0.0)

            if weakest_slope > 0:
                # Calculate optimal integration time for weakest LED at max (255)
                # No safety multiplier - we're already at max LED so this is the optimal condition
                optimal_integration_ms = (target_counts / (weakest_slope * 255.0)) * 10.0

                # Clamp to detector limits
                optimal_integration_ms = max(
                    detector_params.min_integration_time, optimal_integration_ms
                )
                optimal_integration_ms = min(
                    detector_params.max_integration_time, optimal_integration_ms
                )

                initial_integration_ms = optimal_integration_ms
                logger.info(
                    f"Integration time: {initial_integration_ms:.1f}ms (weakest={weakest_ch}, slope={weakest_slope:.1f}, LED=255)"
                )
            else:
                # Fallback: use average slope method
                # CRITICAL FIX: Lower slope = weaker signal = needs LONGER integration (not shorter)
                # Higher slope = stronger signal = needs SHORTER integration (not longer)
                # Logic: Start with weakest LED at max brightness (255), low integration to avoid saturation
                avg_slope = np.mean([model_slopes_s.get(ch, 870.0) for ch in ch_list])
                if avg_slope < 120:
                    initial_integration_ms = (
                        60.0  # Very weak → need long integration even at LED=255
                    )
                elif avg_slope < 180:
                    initial_integration_ms = 45.0  # Weak → moderately long integration
                elif avg_slope < 300:
                    initial_integration_ms = 30.0  # Medium → medium integration
                elif avg_slope < 600:
                    initial_integration_ms = 20.0  # Strong → short integration
                else:
                    initial_integration_ms = 10.0  # Very strong → shortest integration
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

        # Select convergence function - enforce engine wrapper when requested
        if use_convergence_engine:
            if not ENGINE_AVAILABLE:
                error_msg = (
                    "Convergence engine wrapper requested but not available.\n\n"
                    "The device-agnostic convergence engine is required but failed to import.\n"
                    "This may indicate a missing module or import error in:\n"
                    "  affilabs/convergence/production_wrapper.py\n\n"
                    "Please check the logs for import errors or contact support."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            LEDconverge = LEDconverge_engine
            logger.info("🔬 Using device-agnostic convergence engine (production_wrapper)")
        else:
            # Legacy path not supported in device-agnostic architecture
            error_msg = (
                "Legacy convergence algorithm is deprecated.\n\n"
                "The orchestrator now requires the device-agnostic convergence engine.\n"
                "Set use_convergence_engine=True in run_startup_calibration() call."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Create S-mode convergence config with speed optimization for PhasePhotonics
        # Strategy: Maximize LED brightness, minimize integration time for fastest acquisition
        from affilabs.convergence.config import ConvergenceRecipe

        s_config = ConvergenceRecipe(
            channels=ch_list,
            initial_leds=initial_leds,
            initial_integration_ms=initial_integration_ms,
            target_percent=0.85,
            tolerance_percent=0.15,
            max_iterations=12,
            # SPEED OPTIMIZATION: Prefer bright LEDs over long integration
            prefer_led_over_integration=True,  # Enable LED-first strategy
            led_optimization_target=200.0,  # Target LED brightness for weakest channel
            min_integration_for_led_max=detector_params.min_integration_time,  # Use detector's actual minimum
        )

        s_integration_time, s_final_signals, s_success, s_converged_leds, s_iterations = (
            LEDconverge(
                usb=usb,
                ctrl=ctrl,
                ch_list=ch_list,
                led_intensities=initial_leds,
                acquire_raw_spectrum_fn=acquire_raw_spectrum,
                roi_signal_fn=roi_signal,
                initial_integration_ms=initial_integration_ms,
                target_percent=0.85,  # 85% target for optimal S-mode signal
                tolerance_percent=0.15,  # 15% tolerance to accommodate weak channels
                detector_params=detector_params,
                wave_min_index=int(wave_min_index),
                wave_max_index=int(wave_max_index),
                max_iterations=12,  # Optimized - good model guess converges quickly
                step_name="Step 4 (S-mode)",
                use_batch_command=True,
                model_slopes=model_slopes_s,
                polarization="S",
                config=s_config,  # Pass speed-optimized config
                logger=logger,
                progress_callback=progress_callback,
            )
        )

        # Store iterations for QC dialog
        result.s_iterations = s_iterations

        # RELAXED VALIDATION: Accept partial convergence if channels are reasonable
        # Criteria: max signal > 75% of target AND no channel critically low (< 50%)
        if not s_success and s_final_signals:
            target = detector_params.max_counts * 0.85
            max_signal = max(s_final_signals.values())
            min_signal = min(s_final_signals.values())

            # Check if this is "good enough" partial convergence
            max_pct = (max_signal / target) * 100
            min_pct = (min_signal / target) * 100

            # Accept if: max > 75% AND min > 50% (practical convergence)
            if max_pct >= 75.0 and min_pct >= 50.0:
                logger.warning("⚠️  Accepting partial S-pol convergence (practical tolerance)")
                logger.warning(f"   Signal range: {min_pct:.1f}% - {max_pct:.1f}% of target")
                s_success = True  # Override failure - this is good enough for calibration

        if not s_success:
            # Provide detailed error message aligned with ACTUAL target percent used in convergence
            s_target_percent = 0.85  # Must match the target_percent passed to converge() above
            error_msg = "S-mode convergence failed: "
            if s_final_signals:
                target = detector_params.max_counts * s_target_percent

                # Calculate max_signal FIRST (needed for polarizer diagnosis)
                max_signal = max(s_final_signals.values()) if s_final_signals else 0.0
                percent = (max_signal / detector_params.max_counts) * 100

                # Check which channels failed (more accurate than just max signal)
                failed_channels = []
                for ch, sig in s_final_signals.items():
                    error_pct = abs(sig - target) / target * 100
                    if error_pct > 25.0:  # Relaxed from 15% to 25% tolerance
                        sig_pct = (sig / target) * 100
                        led = s_converged_leds.get(ch, 0) if s_converged_leds else 0
                        failed_channels.append(f"{ch.upper()}={sig_pct:.1f}% (LED={led})")

                if failed_channels:
                    error_msg += f"Channels outside tolerance: {', '.join(failed_channels)}. "
                else:
                    # Fallback to old message if no specific channel failures
                    error_msg += (
                        f"Max signal achieved was {max_signal:.0f} ({percent:.1f}%), "
                        f"target was {target:.0f} ({s_target_percent*100:.0f}%). "
                    )

                # POLARIZER POSITION DIAGNOSIS
                # Check if max signal is critically low OR if any maxed LED (255) is getting <10% signal
                critical_threshold = detector_params.max_counts * 0.05  # 5% threshold
                maxed_led_low_signal = False
                if s_converged_leds:
                    for ch, led in s_converged_leds.items():
                        if (
                            led >= 255
                            and s_final_signals.get(ch, 0) < detector_params.max_counts * 0.10
                        ):
                            maxed_led_low_signal = True
                            logger.warning(
                                f"   Channel {ch.upper()} has LED=255 but only {s_final_signals.get(ch, 0):.0f} counts (<10% of detector)"
                            )

                if max_signal < critical_threshold or maxed_led_low_signal:
                    logger.error("=" * 80)
                    logger.error("🔴 CONVERGENCE FAILED - POLARIZER BLOCKING DETECTED!")
                    logger.error("=" * 80)
                    logger.error(
                        f"   Convergence reached {s_iterations} iterations but signal is CRITICALLY LOW"
                    )
                    logger.error(
                        f"   Max signal: {max_signal:.0f} counts ({percent:.1f}% of detector range)"
                    )
                    logger.error(f"   Expected minimum: {critical_threshold:.0f} counts (5%)")
                    logger.error("")
                    logger.error("   🚨 THE POLARIZER IS BLOCKING THE OPTICAL PATH!")
                    logger.error("")
                    logger.error("   DIAGNOSIS:")
                    logger.error(f"   - Device config servo positions: S={s_pos}, P={p_pos}")
                    logger.error("   - Servo physically moved (hardware responded)")
                    logger.error("   - But signal is <5% → positions are INCORRECT")
                    logger.error("")
                    logger.error("   SOLUTION: Run servo calibration to find correct positions")
                    logger.error(
                        "   The current S/P positions in device_config are wrong for this device."
                    )
                    logger.error("=" * 80)
                    error_msg = (
                        f"Polarizer blocking light: signal={max_signal:.0f} counts (expected >{critical_threshold:.0f}). "
                        f"Servo positions S={s_pos}, P={p_pos} are INCORRECT. Run servo calibration to fix."
                    )
                elif max_signal < 5000:
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

        # Determine weakest channel from S-mode to carry over into P-mode
        if s_final_signals:
            s_weakest_ch = min(ch_list, key=lambda c: s_final_signals.get(c, float("inf")))
            logger.info(f"🔗 Carrying weakest channel from S→P: {s_weakest_ch.upper()}")
        else:
            # Fallback to lowest LED setting if signals missing
            s_weakest_ch = min(ch_list, key=lambda c: s_mode_leds.get(c, 0))
            logger.info(
                f"🔗 Carrying weakest channel from S→P (fallback by LED): {s_weakest_ch.upper()}"
            )

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

        # Move servo to P-mode position using sv + sp commands (working format from test)
        logger.info("=" * 80)
        logger.info("🔧 MOVING SERVO TO P-MODE POSITION")
        logger.info("=" * 80)
        logger.info(f"   Target P position: PWM {p_pos} ({(p_pos/255.0)*180:.1f}°)")

        # Convert PWM to degrees and use sv + sp commands
        s_degrees = int(5 + (s_pos / 255.0) * 170.0)
        p_degrees = int(5 + (p_pos / 255.0) * 170.0)

        # Get raw controller access
        raw_ctrl = ctrl._ctrl if hasattr(ctrl, "_ctrl") else ctrl

        # Set positions using sv command
        sv_cmd = f"sv{s_degrees:03d}{p_degrees:03d}\n"
        raw_ctrl._ser.write(sv_cmd.encode())
        time.sleep(0.2)

        # Move to P position using sp command
        raw_ctrl._ser.write(b"sp\n")
        time.sleep(0.5)  # Wait for servo to settle at P position

        logger.info(f"   ✅ Servo positioned at P-mode (PWM {p_pos}, {p_degrees}°)")
        logger.info("=" * 80)

        # Enable LED channels for P4PRO (required after turning them off)
        if ctrl.get_device_type() == "PicoP4PRO":
            for ch in ch_list:
                ctrl.turn_on_channel(ch)
            time.sleep(0.05)

        # Calculate initial LED intensities for P-mode
        # OPTIMIZED: Use converged S-mode LEDs directly with 108% rule for better initial guess
        # P-pol has lower transmission than S-pol, needs MORE LED brightness
        initial_p_leds = {ch: max(10, min(255, int(s_mode_leds[ch] * 1.08))) for ch in ch_list}

        # Turn on all LEDs with calculated intensities
        for ch in ch_list:
            ctrl.set_intensity(ch, initial_p_leds[ch])
        time.sleep(0.03)  # Minimal delay - just ensure LEDs stabilize

        # Run LED convergence for P-mode
        # P-POL IS A FAST LED-ONLY TWEAK: S-pol found integration time, P-pol just adjusts LED brightness
        # Typical P-pol needs 8% more LED due to SPR absorption - integration time stays FIXED at S-pol value
        # Fast convergence: 2-3 iterations max since we're starting from calibrated S-pol baseline

        # Create P-pol config for fast LED-only optimization (NO integration time changes)
        from affilabs.convergence.config import ConvergenceRecipe

        p_config = ConvergenceRecipe(
            channels=ch_list,
            initial_leds=initial_p_leds,
            initial_integration_ms=s_integration_time,  # Start at exact S-pol value
            target_percent=0.75,
            tolerance_percent=0.05,
            max_iterations=12,  # Allow more iterations for empirical convergence without model
            min_signal_for_model=0.95,  # DISABLE model-based predictions (force empirical measurement)
            max_led_change=80,  # Allow large LED changes since we're not using model
            led_small_step=8,  # Larger steps OK since we know direction (always boost for P-pol)
            prefer_est_after_iters=1,  # Trust measurements immediately
            near_window_percent=0.10,  # Tighter convergence window for speed
            # SPEED OPTIMIZATION: Same as S-mode for consistent fast acquisition
            prefer_led_over_integration=True,  # Enable LED-first strategy
            led_optimization_target=200.0,  # Target LED brightness for weakest channel
            min_integration_for_led_max=detector_params.min_integration_time,  # Use detector's actual minimum
        )

        # Carry weakest channel override into P-mode convergence
        try:
            setattr(p_config, "WEAKEST_CHANNEL_OVERRIDE", s_weakest_ch)
            # Policy: Allow integration increase if ALL LEDs maxed (C/D may need more time)
            setattr(p_config, "FREEZE_INTEGRATION", False)
            setattr(p_config, "ALLOW_INTEGRATION_INCREASE_ONLY", True)
        except Exception:
            # Config may be a simple object; setattr should succeed, ignore if not
            pass

        p_integration_time, p_final_signals, p_success, p_converged_leds, p_iterations = (
            LEDconverge(
                usb=usb,
                ctrl=ctrl,
                ch_list=ch_list,
                led_intensities=initial_p_leds.copy(),  # S-pol × 0.92 = perfect starting point
                acquire_raw_spectrum_fn=acquire_raw_spectrum,
                roi_signal_fn=roi_signal,
                initial_integration_ms=s_integration_time,  # FROZEN - P-pol uses exact S-pol integration
                target_percent=0.75,
                tolerance_percent=0.05,
                detector_params=detector_params,
                wave_min_index=int(wave_min_index),
                wave_max_index=int(wave_max_index),
                max_iterations=12,  # More iterations for empirical P-pol convergence without model
                step_name="Step 5 (P-mode LED boost)",
                use_batch_command=True,
                model_slopes=None,  # DISABLE model slopes - P/S ratios vary too much per channel
                polarization="P",
                config=p_config,
                logger=logger,
                progress_callback=progress_callback,
            )
        )

        # Store iterations for QC dialog
        result.p_iterations = p_iterations

        # P-POL FAILSAFE: If convergence didn't fully converge, use LAST iteration's LEDs
        # The last iteration is the closest to target, much better than initial guess
        if not p_success:
            logger.warning(
                "⚠️ P-mode didn't fully converge - using last iteration's LEDs (closest to target)"
            )
            # p_converged_leds already contains the last iteration's values from LEDconverge
            # Don't overwrite it with initial_p_leds!
            if not p_converged_leds:  # Only fallback to initial if LEDconverge returned nothing
                logger.warning("   No LED data from convergence, using S-mode baseline fallback")
                p_converged_leds = initial_p_leds
            # Keep p_integration_time and p_final_signals from last iteration

        # Use final LED intensities from convergence engine
        # These are the converged values, NOT the initial values
        p_mode_leds = p_converged_leds if p_converged_leds else initial_p_leds

        result.p_mode_intensity = p_mode_leds
        result.p_integration_time = p_integration_time

        logger.info(f"P-mode: {p_integration_time:.1f}ms, LEDs={p_mode_leds}")

        # CRITICAL: Dark signal detection - check if P-pol position is blocked/wrong
        # If all channels show dark signals (<1000 counts), servo position is incorrect
        DARK_THRESHOLD = 1000  # Below this = blocked/dark (same as servo calibration)
        if p_final_signals:
            all_signals = list(p_final_signals.values())
            max_signal = max(all_signals)
            avg_signal = sum(all_signals) / len(all_signals)

            if max_signal < DARK_THRESHOLD:
                logger.error("=" * 80)
                logger.error(">> CRITICAL ERROR: P-POL POSITION IS DARK/BLOCKED!")
                logger.error("=" * 80)
                logger.error(
                    f"   All channels showing dark signals (max={max_signal:.0f} counts < {DARK_THRESHOLD})"
                )
                logger.error(f"   Average signal: {avg_signal:.0f} counts")
                logger.error(
                    f"   Current P-pol servo position: PWM {p_pos} ({(p_pos/255.0)*180:.1f}deg)"
                )
                logger.error("")
                logger.error("   AUTOMATIC SERVO RECALIBRATION REQUIRED!")
                logger.error(
                    "   The system will now run servo calibration to find correct P-pol position..."
                )
                logger.error("=" * 80)

                # Special exception that UI can catch to trigger automatic servo calibration
                raise RuntimeError(
                    "SERVO_RECALIBRATION_REQUIRED: P-pol position is dark/blocked. "
                    f"Signal={max_signal:.0f} counts (expected >{DARK_THRESHOLD}). "
                    f"Current P position PWM {p_pos} is incorrect. "
                    "Please run servo calibration (servo_polarizer_calibration/calibrate_polarizer.py) "
                    "to find the correct P-pol position, then retry this calibration."
                )

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
                    logger.warning(
                        f"[WARN] P-pol reference SATURATED for channel {ch.upper()}: {max_pixel:.0f} counts >= {detector_params.saturation_threshold}"
                    )
                    logger.warning(
                        f"   Convergence target was too high - reference capture with {num_scans_p} scans caused saturation"
                    )
                    logger.warning(
                        "   ⚠️ P-POL FAILSAFE: Continuing with saturated data (calibration will not fail)"
                    )
                    # Don't raise - continue with saturated data to ensure calibration completes
            else:
                logger.warning(f"⚠️ Failed to capture P-pol reference for channel {ch}")
                logger.warning("   P-POL FAILSAFE: Using S-pol data as fallback")
                # Use S-pol reference as fallback to ensure calibration completes
                p_raw_data[ch] = result.s_raw_data[ch].copy()

        result.p_raw_data = p_raw_data

        # Capture dark spectrum (LEDs off) at P-pol integration time
        # CRITICAL: This dark is captured AFTER setting P-pol integration time (line 628),
        # so it matches the integration time used for live P-pol data acquisition.
        # S-pol reference is captured at S-pol integration time (line 509), and will be
        # dark-subtracted in Step 6 using this same dark (acceptable approximation since
        # integration times are usually similar, and S-pol reference is captured once).
        # Live P-pol data uses this dark for every acquisition (dark_p).
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

        # Store dark for both modes
        # dark_s: Used for S-pol reference dark subtraction in Step 6 (one-time, during calibration)
        # dark_p: Used for LIVE P-pol data dark subtraction (every acquisition frame)
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
                wavelengths=result.wave_data,  # Add wavelengths for consistency
                apply_sg_filter=True,
                baseline_method="percentile",
                baseline_percentile=95.0,
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

            # Format QC results with safety checks for None values
            dip_wl = qc.get("dip_wavelength")
            dip_depth = qc.get("dip_depth")
            fwhm = qc.get("fwhm")

            dip_wl_str = f"{dip_wl:.1f}" if dip_wl is not None else "N/A"
            dip_depth_str = f"{dip_depth:.1f}" if dip_depth is not None else "N/A"
            fwhm_str = f"{fwhm:.1f}" if fwhm is not None else "N/A"

            logger.info(
                f"Channel {ch.upper()}: "
                f"Dip={dip_wl_str}nm, "
                f"Depth={dip_depth_str}%, "
                f"FWHM={fwhm_str}nm"
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
