"""
Simplified Calibration Manager - Direct path from UI to backend.

This replaces the fragmented calibration system with a single, clean interface.

CALIBRATION MODES:
------------------

1. FULL 6-STEP CALIBRATION (run_full_6step_calibration)
   When to use:
   - Initial device setup
   - After optical path changes (fiber, polarizer, detector)
   - If fast-track fails validation

   What it does:
   - Optimizes integration time (Step 5A)
   - Binary search for optimal LED intensities (Step 5B)
   - Multi-pass saturation validation (Step 5C)
   - Measures reference spectra (Step 5D)
   - Calibrates P-mode LEDs (Step 6A)
   - QC metrics and validation (Step 6C)

   Result: ALL parameters locked and transferred to live acquisition

2. FAST-TRACK CALIBRATION (run_fast_track_calibration)
   When to use:
   - Sensor/prism swap (optical coupling changes slightly)
   - LED intensity drift compensation
   - Quick validation after maintenance

   What it does:
   - Validates previous calibration (±10% tolerance)
   - Updates ONLY LED intensities for failed channels
   - Keeps integration time LOCKED from previous calibration
   - ~80% faster than full calibration

   Result: Only LED intensities updated (typically 5-15% tweaks)

PARAMETER LOCKING:
------------------
After full calibration, parameters are transferred to data_mgr and LOCKED:
- Integration time, num_scans, dark_noise, wavelength_data, S-ref, P-ref

Only LED intensities can be updated via fast-track on sensor change.
Live acquisition uses these locked parameters for all measurements.
"""

import threading
import numpy as np
from PySide6.QtCore import QObject, Signal
from utils.logger import logger


class CalibrationManager(QObject):
    """Manages LED calibration with direct backend access.

    Signals:
        calibration_started: Emitted when calibration begins
        calibration_progress: Emitted with (message: str, percent: int)
        calibration_complete: Emitted with calibration data dict
        calibration_failed: Emitted with error message string
    """

    calibration_started = Signal()
    calibration_progress = Signal(str, int)  # (message, percent)
    calibration_complete = Signal(dict)
    calibration_failed = Signal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._thread = None
        self._running = False

    def start_calibration(self):
        """Start calibration in background thread."""
        if self._running:
            logger.warning("Calibration already in progress")
            return False

        logger.info("🎬 Starting LED calibration...")
        self._running = True
        self.calibration_started.emit()

        # Run in background thread
        self._thread = threading.Thread(target=self._run_calibration, daemon=True, name="CalibrationManager")
        self._thread.start()
        return True

    def _run_calibration(self):
        """Main calibration routine (runs in background thread)."""
        try:
            # Get hardware directly
            self.calibration_progress.emit("Initializing...", 5)

            hardware_mgr = self.app.hardware_mgr
            ctrl = hardware_mgr.ctrl
            usb = hardware_mgr.usb

            logger.info(f"Hardware check: ctrl={type(ctrl).__name__ if ctrl else 'None'}, usb={type(usb).__name__ if usb else 'None'}")

            if not ctrl:
                raise RuntimeError("Controller not connected. Please connect the P4SPR controller.")

            if not usb:
                raise RuntimeError("Spectrometer not connected. Please connect the USB4000.")

            # Test controller communication
            logger.info("Testing controller communication...")
            try:
                ctrl.turn_off_channels()
                ctrl.turn_on_channel('a')
                import time
                time.sleep(0.5)
                ctrl.set_intensity('a', 200)
                time.sleep(0.5)
                ctrl.turn_off_channels()
                logger.info("✅ Controller responding to commands")
            except Exception as e:
                logger.error(f"Controller communication error: {e}")
                raise RuntimeError(f"Controller communication error: {e}")

            logger.info("✅ Hardware ready - proceeding with calibration")

            # Load configuration
            self.calibration_progress.emit("Loading configuration...", 10)
            from settings import INTEGRATION_STEP, MIN_WAVELENGTH, MAX_WAVELENGTH
            from utils.device_configuration import DeviceConfiguration

            device_serial = getattr(usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            # Step 3: Read wavelength data
            self.calibration_progress.emit("Reading wavelength data...", 15)
            wave_data = usb.read_wavelength()
            wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)

            # Step 4: Load afterglow correction if available
            afterglow_correction = None
            try:
                from afterglow_correction import AfterglowCorrection
                from utils.device_integration import get_device_optical_calibration_path

                optical_cal_path = get_device_optical_calibration_path()
                if optical_cal_path and optical_cal_path.exists():
                    afterglow_correction = AfterglowCorrection(optical_cal_path)
                    logger.info(f"✅ Loaded afterglow correction: {optical_cal_path.name}")
            except Exception as e:
                logger.debug(f"Afterglow correction not available: {e}")

            # Step 5: Run calibration using 6-step flow
            logger.info("🚀 Starting 6-step LED calibration flow...")

            def progress_update(msg):
                """Map backend messages to progress percentages."""
                if "step 1" in msg.lower() or "hardware" in msg.lower():
                    self.calibration_progress.emit(msg, 10)
                elif "step 2" in msg.lower() or "quick dark" in msg.lower():
                    self.calibration_progress.emit(msg, 15)
                elif "step 3" in msg.lower() or "initializ" in msg.lower():
                    self.calibration_progress.emit(msg, 20)
                elif "step 4" in msg.lower() or "oem position" in msg.lower():
                    self.calibration_progress.emit(msg, 25)
                elif "step 5a" in msg.lower() or "led optimization" in msg.lower():
                    self.calibration_progress.emit(msg, 35)
                elif "step 5b" in msg.lower() or "integration time" in msg.lower():
                    self.calibration_progress.emit(msg, 50)
                elif "step 5c" in msg.lower() or "saturation check" in msg.lower():
                    self.calibration_progress.emit(msg, 60)
                elif "step 5d" in msg.lower() or "s-mode ref" in msg.lower():
                    self.calibration_progress.emit(msg, 70)
                elif "step 5e" in msg.lower() or "final dark" in msg.lower():
                    self.calibration_progress.emit(msg, 75)
                elif "step 6a" in msg.lower() or "p-mode led" in msg.lower():
                    self.calibration_progress.emit(msg, 80)
                elif "step 6b" in msg.lower() or "polarity" in msg.lower():
                    self.calibration_progress.emit(msg, 85)
                elif "step 6c" in msg.lower() or "qc metric" in msg.lower():
                    self.calibration_progress.emit(msg, 90)
                elif "fast-track" in msg.lower() or "validat" in msg.lower():
                    self.calibration_progress.emit(msg, 40)
                else:
                    logger.info(f"Progress: {msg}")

            # Import calibration functions (Standard method - Global Integration Time)
            from utils.led_calibration import perform_full_led_calibration  # Standard method: Global Integration, Variable LED
            from utils.calibration_6step import run_fast_track_calibration  # Fast-track only
            from datetime import datetime, timedelta

            # Get LED timing delays from device config (device-specific, user-configurable)
            pre_led_delay_ms = device_config.get_pre_led_delay_ms()
            post_led_delay_ms = device_config.get_post_led_delay_ms()
            logger.info(f"📊 Using LED timing from device config: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")

            # Check if fast-track is possible
            use_fast_track = False
            cal_data = device_config.load_led_calibration()

            if cal_data and 's_mode_intensities' in cal_data:
                # Check consecutive use count (max 5)
                fast_track_count = cal_data.get('fast_track_count', 0)

                # Check calibration age (max 30 days)
                cal_date_str = cal_data.get('calibration_date')
                calibration_age_ok = False
                if cal_date_str:
                    try:
                        cal_date = datetime.fromisoformat(cal_date_str.replace('Z', '+00:00'))
                        age_days = (datetime.now() - cal_date).days
                        calibration_age_ok = age_days <= 30
                        logger.info(f"Previous calibration age: {age_days} days")
                    except:
                        logger.warning("Could not parse calibration date")

                # Decide if fast-track is allowed
                if fast_track_count >= 5:
                    logger.info(f"⚠️ Fast-track limit reached ({fast_track_count}/5) - forcing full calibration")
                elif not calibration_age_ok:
                    logger.info(f"⚠️ Calibration too old (>30 days) - forcing full calibration")
                else:
                    use_fast_track = True
                    logger.info(f"✅ Attempting fast-track calibration (validates GLOBAL integration time, use {fast_track_count + 1}/5)")

            # Run calibration (GLOBAL LED INTENSITY METHOD ONLY)
            if use_fast_track:
                logger.info("✅ Using fast-track validation (validates GLOBAL integration time)")
                cal_result = run_fast_track_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type='P4SPR',
                    device_config=device_config,
                    detector_serial=device_serial,
                    single_mode=False,
                    single_ch='a',
                    stop_flag=None,
                    progress_callback=progress_update,
                    afterglow_correction=afterglow_correction,
                    pre_led_delay_ms=pre_led_delay_ms,
                    post_led_delay_ms=post_led_delay_ms
                )
            else:
                logger.info("✅ Using STANDARD calibration (Global Integration Time, Variable LED per channel)")
                cal_result = perform_full_led_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type='P4SPR',
                    single_mode=False,
                    single_ch='a',
                    stop_flag=None,
                    progress_callback=progress_update,
                    device_config=device_config,
                    pre_led_delay_ms=pre_led_delay_ms,
                    post_led_delay_ms=post_led_delay_ms
                )

            # Step 6: Validate results
            self.calibration_progress.emit("Validating results...", 90)

            logger.info(f"🔍 Calibration result validation:")
            logger.info(f"   success: {cal_result.success}")
            logger.info(f"   integration_time: {cal_result.integration_time}")
            logger.info(f"   ref_sig channels: {list(cal_result.ref_sig.keys()) if cal_result.ref_sig else 'None'}")
            logger.info(f"   ch_error_list: {cal_result.ch_error_list}")

            if not cal_result.success:
                error_msg = getattr(cal_result, 'error_message', None) or getattr(cal_result, 'error', None)
                if not error_msg:
                    # Check for channel errors
                    if cal_result.ch_error_list:
                        error_msg = f"Calibration failed for channels: {', '.join(cal_result.ch_error_list)}"
                    else:
                        error_msg = "Calibration completed but marked as unsuccessful"
                logger.error(f"❌ Calibration validation failed: {error_msg}")
                raise RuntimeError(f"Calibration failed: {error_msg}")

            if not cal_result.ref_sig or len(cal_result.ref_sig) == 0:
                raise RuntimeError("No reference spectra acquired")

            logger.info("✅ Calibration backend completed successfully")

            # ===================================================================
            # STEP 7: STORE CALIBRATION RESULTS
            # ===================================================================
            # Transfer calibration parameters to data acquisition manager.
            # Live acquisition will use these parameters EXACTLY as provided.
            #
            # CRITICAL: Calibration method determines these parameters.
            # Live acquisition is method-agnostic - it just executes them.
            # ===================================================================
            self.calibration_progress.emit("Storing results...", 95)

            data_mgr = self.app.data_mgr

            # Core acquisition parameters
            data_mgr.integration_time = cal_result.integration_time  # Integration time (ms)
            data_mgr.num_scans = cal_result.num_scans                # Scans per spectrum
            data_mgr.dark_noise = cal_result.dark_noise              # Dark noise baseline
            data_mgr.wave_data = cal_result.wave_data                # Wavelength calibration
            data_mgr.ref_sig = cal_result.ref_sig                    # S-mode reference spectra
            data_mgr.p_ref_sig = getattr(cal_result, 'p_ref_sig', {})  # P-mode reference (if available)

            # LED intensities per channel
            data_mgr.ref_intensity = cal_result.ref_intensity        # S-mode LED intensities
            data_mgr.leds_calibrated = cal_result.leds_calibrated    # P-mode LED intensities

            # LED timing delays (ensure live acquisition uses same delays as calibration)
            data_mgr._pre_led_delay_ms = pre_led_delay_ms
            data_mgr._post_led_delay_ms = post_led_delay_ms

            # Validate critical parameters exist
            if not data_mgr.integration_time or data_mgr.integration_time <= 0:
                logger.error(f"❌ INVALID: integration_time={data_mgr.integration_time}ms")
                raise ValueError(f"Invalid integration time from calibration: {data_mgr.integration_time}ms")

            if not data_mgr.leds_calibrated or not isinstance(data_mgr.leds_calibrated, dict):
                logger.error(f"❌ INVALID: leds_calibrated={data_mgr.leds_calibrated}")
                raise ValueError("Invalid LED calibration data")

            logger.info("")
            logger.info("✅ Calibration parameters stored successfully:")
            logger.info(f"   Integration Time: {data_mgr.integration_time}ms")
            logger.info(f"   Scans per Spectrum: {data_mgr.num_scans}")
            logger.info(f"   P-mode LEDs: {data_mgr.leds_calibrated}")
            logger.info(f"   S-mode LEDs: {data_mgr.ref_intensity}")
            logger.info(f"   LED Delays: PRE={data_mgr._pre_led_delay_ms}ms, POST={data_mgr._post_led_delay_ms}ms")
            logger.info("")

            # Quality control and diagnostic data:
            data_mgr.ch_error_list = cal_result.ch_error_list.copy()
            data_mgr.s_ref_qc_results = getattr(cal_result, 's_ref_qc_results', {})
            data_mgr.channel_performance = getattr(cal_result, 'channel_performance', {})
            # Extract FWHM from transmission_validation for backward compatibility
            spr_fwhm = {ch: data.get('fwhm') for ch, data in getattr(cal_result, 'transmission_validation', {}).items() if data.get('fwhm') is not None}
            data_mgr.spr_fwhm = spr_fwhm  # For QC report (extracted from transmission_validation)
            data_mgr.orientation_validation = getattr(cal_result, 'orientation_validation', {})  # Orientation validation for QC report
            data_mgr.transmission_validation = getattr(cal_result, 'transmission_validation', {})  # Transmission validation for QC report
            data_mgr.weakest_channel = getattr(cal_result, 'weakest_channel', None)  # Hardware characteristic

            # QC display data from finalcalibQC (Step 6) - ORIGINAL PROCESSED DATA
            # ⚠️ PRIORITY: Always use this original data for QC graphs (not re-calculated!)
            # - transmission_spectra: From LiveRtoT_QC (Step 6 Part C) with full pipeline:
            #   dark removal, afterglow correction, LED boost, 95th percentile baseline, SG filtering
            # - afterglow_curves: Same predict_afterglow() used during processing
            data_mgr.transmission_spectra = getattr(cal_result, 'transmission', {})
            data_mgr.afterglow_curves = getattr(cal_result, 'afterglow_curves', {})

            if data_mgr.transmission_spectra:
                logger.info(f"✅ Transmission spectra stored from LiveRtoT_QC: {len(data_mgr.transmission_spectra)} channels")
            if data_mgr.afterglow_curves:
                logger.info(f"✅ Afterglow curves stored: {len(data_mgr.afterglow_curves)} channels")

            # DEBUG: Log P-ref data transfer
            if data_mgr.p_ref_sig:
                logger.info(f"✅ P-ref data stored: {len(data_mgr.p_ref_sig)} channels")
            else:
                logger.debug("ℹ️ No P-ref data in calibration result")

            # Store wavelength indices
            data_mgr.wave_min_index = wave_min_index
            data_mgr.wave_max_index = wave_max_index

            # Calculate Fourier weights
            data_mgr._calculate_snr_aware_fourier_weights()

            # Mark as calibrated
            data_mgr.calibrated = True

            # Load afterglow correction for live acquisition (if method exists)
            afterglow_available = False
            try:
                if hasattr(data_mgr, '_load_afterglow_correction'):
                    data_mgr._load_afterglow_correction()
                    afterglow_available = getattr(data_mgr, '_afterglow_correction', None) is not None
            except Exception as e:
                logger.debug(f"Afterglow loading skipped: {e}")

            logger.info("✅ Calibration data stored in data_mgr")

            # Step 8: Prepare calibration data for UI
            # Detect if fast-track was used (has fast_track_passed attribute)
            is_fast_track = hasattr(cal_result, 'fast_track_passed') and cal_result.fast_track_passed

            calibration_data = {
                'integration_time': cal_result.integration_time,
                'num_scans': cal_result.num_scans,
                'ref_intensity': cal_result.ref_intensity,
                'leds_calibrated': cal_result.leds_calibrated.copy(),
                'led_intensities': cal_result.ref_intensity.copy(),  # For QC summary display
                'ch_error_list': cal_result.ch_error_list.copy(),
                's_ref_qc_results': data_mgr.s_ref_qc_results,
                'channel_performance': data_mgr.channel_performance,
                'calibration_type': 'fast_track' if is_fast_track else 'full',
                'afterglow_available': afterglow_available,
                'skip_qc_dialog': is_fast_track,  # Skip QC for fast-track
                'optics_ready': len(cal_result.ch_error_list) == 0,  # Set optics ready if all channels passed

                # Spectral data for QC graphs
                's_pol_spectra': cal_result.ref_sig.copy() if cal_result.ref_sig else {},  # S-mode reference spectra
                'p_pol_spectra': data_mgr.p_ref_sig.copy() if data_mgr.p_ref_sig else {},  # P-mode reference spectra
                'dark_scan': {'combined': cal_result.dark_noise} if cal_result.dark_noise is not None else {},  # Dark noise
                'wavelengths': cal_result.wave_data if cal_result.wave_data is not None else np.array([]),  # Wavelength array

                # QC validation results
                'orientation_validation': data_mgr.orientation_validation,
                'spr_fwhm': data_mgr.spr_fwhm,
                'transmission_validation': data_mgr.transmission_validation,
            }

            # Complete
            self.calibration_progress.emit("Complete!", 100)
            self.calibration_complete.emit(calibration_data)

            logger.info("✅ Calibration complete - all channels calibrated")
            if len(cal_result.ch_error_list) == 0:
                logger.info("✅ Optics ready: All channels passed calibration")

        except Exception as e:
            # Print full traceback immediately to console before any dialog handling
            import traceback
            print("\n" + "="*80)
            print("CALIBRATION ERROR - FULL TRACEBACK:")
            print("="*80)
            traceback.print_exc()
            print("="*80 + "\n")

            logger.error(f"❌ Calibration failed: {e}", exc_info=True)
            self.calibration_failed.emit(str(e))
        finally:
            # Ensure hardware is in safe state (turn off all LEDs)
            try:
                if hasattr(self.app, 'hardware_mgr') and self.app.hardware_mgr:
                    ctrl = self.app.hardware_mgr.ctrl
                    if ctrl:
                        logger.debug("Calibration cleanup: turning off all LEDs...")
                        ctrl.turn_off_channels()
                        logger.debug("✅ Calibration cleanup complete")
            except Exception as cleanup_error:
                logger.warning(f"Error during calibration cleanup: {cleanup_error}")

            self._running = False

    def is_running(self):
        """Check if calibration is currently running."""
        return self._running
