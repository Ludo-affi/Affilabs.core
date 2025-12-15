"""Data Acquisition Manager - Handles spectrum acquisition and processing.

This class manages:
- Continuous spectrum acquisition from spectrometer
- Calibration routines (dark noise, reference spectrum, LED calibration)
- Spectrum processing (filtering, temporal processing, peak finding)
- Data buffering and time tracking
- Signal processing (Fourier weights, median filtering)
- Spectral correction (normalizes LED profile differences per channel)

Key Processing Steps (applied in sequence):
1. Dark noise subtraction
2. Spectral correction (LED profile normalization)
3. Afterglow correction (residual LED decay from previous channel)
4. Weighted Fourier peak finding (accounts for SPR signal shape)

The spectral correction system addresses the challenge that different LED
channels have wildly different spectral profiles (intensity distribution
across wavelengths), which can bias peak finding. During calibration, S-mode
reference spectra (ref_sig) are captured for each channel, showing the LED
profile. Correction weights are computed to normalize these profiles so all
channels have similar spectral shapes for accurate peak detection.

All operations run in background threads to avoid blocking the UI.
"""

import queue
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from utils.logger import logger

# System Intelligence integration (DISABLED - will be refined later)
try:
    from core.system_intelligence import get_system_intelligence

    SYSTEM_INTELLIGENCE_AVAILABLE = False  # Disabled for now
except ImportError:
    SYSTEM_INTELLIGENCE_AVAILABLE = False
    # logger.warning("System Intelligence not available - operating without ML guidance")


class DataAcquisitionManager(QObject):
    """Manages spectrum acquisition and processing."""

    # Signals for data updates
    spectrum_acquired = Signal(
        dict,
    )  # {channel: str, wavelength: float, intensity: float, timestamp: float}
    calibration_started = Signal()
    calibration_complete = Signal(
        dict,
    )  # {integration_time, num_scans, ref_intensity, leds_calibrated, ch_error_list}
    calibration_failed = Signal(str)  # Error message
    calibration_progress = Signal(str)  # Progress message
    acquisition_error = Signal(str)  # Error message
    acquisition_started = Signal()  # Emitted when acquisition loop starts
    acquisition_stopped = Signal()  # Emitted when acquisition loop stops

    def __init__(self, hardware_mgr):
        super().__init__()

        # Reference to hardware manager
        self.hardware_mgr = hardware_mgr

        # Calibration state
        self.calibrated = False
        self.integration_time = (
            15  # ms (global in standard method, max in alternative method)
        )
        self.num_scans = 5
        self.ref_intensity = 255
        self.leds_calibrated = {}  # {channel: intensity}
        self.ch_error_list = []  # List of failed channels from calibration

        # Calibration method tracking
        self.calibration_method = "standard"  # 'standard' or 'alternative'
        self.per_channel_integration = {}  # {channel: integration_time_ms} for alternative method
        self.per_channel_dark_noise = {}  # {channel: dark_noise_array} for alternative method

        # Spectrum data
        self.wave_data = None  # Wavelength array
        self.wave_min_index = 0
        self.wave_max_index = -1
        self.dark_noise = None
        self.ref_spectrum = None

        # Fourier weights for peak finding
        self.fourier_weights = {}  # {channel: weights_array}

        # S-mode reference spectra (LED profiles per channel)
        self.ref_sig = {}  # {channel: reference_spectrum}

        # Spectral correction weights (computed from ref_sig)
        self.spectral_correction = {}  # {channel: correction_weights}

        # Afterglow correction (loaded from device-specific calibration)
        self.afterglow_correction = None
        self.afterglow_enabled = False
        self.afterglow_mode = "normal"  # 'fast', 'normal', or 'slow'
        self._previous_channel = None  # Track previous channel for afterglow correction
        self._led_delay_ms = (
            45.0  # Default LED delay in milliseconds (PRE_LED_DELAY_MS)
        )
        self._led_post_delay_ms = 5.0  # Default LED post delay in milliseconds

        # S/P orientation validation tracking
        self._sp_validation_results = {}  # {channel: {orientation_correct, confidence, peak_wl, timestamp}}
        self._sp_orientation_validated = (
            set()
        )  # Set of channels validated during runtime

        # FWHM tracking for quality control
        self._fwhm_values = {}  # {channel: fwhm_nm}

        # Batched acquisition settings (from settings.py)
        from settings import BATCH_SIZE, ENABLE_INTERPOLATED_DISPLAY

        self.batch_size = BATCH_SIZE  # Minimum raw spectra to buffer before processing (reduces USB overhead)
        self._spectrum_batch = {
            "a": [],
            "b": [],
            "c": [],
            "d": [],
        }  # Batch buffers per channel
        self._batch_timestamps = {
            "a": [],
            "b": [],
            "c": [],
            "d": [],
        }  # Timestamp buffers

        # Display smoothing: emit partial updates during batch processing
        self.enable_interpolated_display = ENABLE_INTERPOLATED_DISPLAY
        self._last_emitted_wavelength = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }  # For interpolation

        # Thread-safe queue for worker → main thread communication
        self._spectrum_queue = queue.Queue(
            maxsize=1000,
        )  # Buffer up to 1000 spectrum events

        # QTimer to process queue in main thread (initialized here to ensure main thread ownership)
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._process_spectrum_queue)

        # Acquisition state
        self._acquiring = False
        self._acquisition_thread = None
        self._stop_acquisition = threading.Event()
        self._pause_acquisition = (
            threading.Event()
        )  # Pause flag (set=paused, clear=running)

        # Data buffers (using channel manager pattern)
        self.channel_buffers = {ch: [] for ch in ["a", "b", "c", "d"]}
        self.time_buffers = {ch: [] for ch in ["a", "b", "c", "d"]}

        # Spectrum processor (will be imported when needed)
        self.spectrum_processor = None

        logger.info("DataAcquisitionManager initialized")

    def set_batch_size(self, batch_size: int) -> None:
        """Set minimum batch size for spectrum acquisition.

        Args:
            batch_size: Minimum number of raw spectra to buffer before processing.
                       Higher values reduce USB overhead but increase latency.
                       Recommended: 4-8 for balance, 1 for real-time, 16+ for throughput.

        """
        if batch_size < 1:
            logger.warning(f"Invalid batch_size {batch_size}, using minimum of 1")
            batch_size = 1

        old_batch_size = self.batch_size
        self.batch_size = batch_size
        logger.info(f"Batch size changed: {old_batch_size} -> {batch_size}")

    def start_calibration(self):
        """Start calibration routine (non-blocking)."""
        if not self._check_hardware():
            self.calibration_failed.emit("Hardware not connected")
            return

        # Wait briefly for acquisition to fully stop if it's in the process of stopping
        if self._acquiring:
            logger.debug(
                "Acquisition flag set - checking if thread is actually running...",
            )
            import time

            # Give it a moment to finish stopping
            for _ in range(10):  # 1 second max wait
                if not self._acquiring or (
                    self._acquisition_thread and not self._acquisition_thread.is_alive()
                ):
                    break
                time.sleep(0.1)

            # Check again after wait
            if (
                self._acquiring
                and self._acquisition_thread
                and self._acquisition_thread.is_alive()
            ):
                logger.warning("Cannot calibrate while acquiring")
                self.calibration_failed.emit("Stop acquisition before calibrating")
                return
            logger.debug("Acquisition stopped - proceeding with calibration")
            self._acquiring = False  # Clear stale flag

        logger.info("Starting calibration...")

        # Clear previous calibration state for fresh start
        self.calibrated = False
        self.ch_error_list = []

        self.calibration_started.emit()

        # Run calibration in background thread
        thread = threading.Thread(
            target=self._calibration_worker,
            daemon=True,
            name="CalibrationWorker",
        )
        thread.start()

    def _calibration_worker(self):
        """Calibration routine running in background thread."""
        try:
            from settings import (
                INTEGRATION_STEP,
                MAX_WAVELENGTH,
                MIN_WAVELENGTH,
                USE_ALTERNATIVE_CALIBRATION,
            )
            from utils.device_configuration import DeviceConfiguration
            from utils.led_calibration import (
                perform_alternative_calibration,
                perform_full_led_calibration,
            )

            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                raise Exception("Hardware not available")

            self.calibration_progress.emit("Initializing...")

            # Get wavelength calibration data ONCE (optimization: avoid redundant USB reads)
            logger.info("Reading wavelength calibration data...")
            wave_data = usb.read_wavelength()
            wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
            self.wave_data = wave_data[wave_min_index:wave_max_index]

            # Store indices for efficient trimming during live acquisition
            self.wave_min_index = wave_min_index
            self.wave_max_index = wave_max_index
            logger.info(
                f"Wavelength range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm (indices {wave_min_index}-{wave_max_index})",
            )

            # Load device configuration ONCE (optimization: avoid redundant file reads)
            device_serial = getattr(usb, "serial_number", None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            # Load afterglow correction ONCE (optimization: avoid redundant file I/O)
            afterglow_correction = None
            try:
                from afterglow_correction import AfterglowCorrection

                from utils.device_integration import get_device_optical_calibration_path

                optical_cal_path = get_device_optical_calibration_path()
                if optical_cal_path and optical_cal_path.exists():
                    afterglow_correction = AfterglowCorrection(optical_cal_path)
                    logger.info(
                        f"✅ Pre-loaded afterglow correction for calibration: {optical_cal_path.name}",
                    )
                else:
                    logger.debug("No afterglow correction available for pre-loading")
            except Exception as e:
                logger.debug(f"Afterglow pre-loading skipped: {e}")

            self.calibration_progress.emit("Calibrating system...")

            # Select calibration method based on configuration
            if USE_ALTERNATIVE_CALIBRATION:
                logger.info(
                    "Using ALTERNATIVE calibration method (Global LED Intensity)",
                )
                cal_result = perform_alternative_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type="P4SPR",
                    single_mode=False,
                    single_ch="a",
                    stop_flag=None,
                    progress_callback=lambda msg: self.calibration_progress.emit(msg),
                    wave_data=wave_data,  # Pass pre-read wavelength data
                    wave_min_index=wave_min_index,
                    wave_max_index=wave_max_index,
                    device_config=device_config,  # Pass pre-loaded device config
                    afterglow_correction=afterglow_correction,  # Pass pre-loaded afterglow correction
                )
            else:
                logger.info(
                    "Using STANDARD calibration method (Global Integration Time)",
                )
                cal_result = perform_full_led_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type="P4SPR",
                    single_mode=False,
                    single_ch="a",
                    integration_step=INTEGRATION_STEP,
                    stop_flag=None,
                    progress_callback=lambda msg: self.calibration_progress.emit(msg),
                    wave_data=wave_data,  # Pass pre-read wavelength data
                    wave_min_index=wave_min_index,
                    wave_max_index=wave_max_index,
                    device_config=device_config,  # Pass pre-loaded device config
                    afterglow_correction=afterglow_correction,  # Pass pre-loaded afterglow correction
                )

            # Check for complete failure (all channels failed or critical error)
            # Partial failures (some channels work) are allowed and handled in UI
            if cal_result.integration_time is None or cal_result.integration_time == 0:
                raise Exception(
                    "Critical calibration failure: Could not determine integration time",
                )

            # Check if ref_sig is empty (complete calibration failure)
            if not cal_result.ref_sig or len(cal_result.ref_sig) == 0:
                raise Exception(
                    "Critical calibration failure: No S-mode reference spectra acquired",
                )

            # Log partial failures but continue
            if len(cal_result.ch_error_list) > 0:
                logger.warning(
                    f"⚠️ Partial calibration: {len(cal_result.ch_error_list)} channel(s) failed: {cal_result.ch_error_list}",
                )

            self.calibration_progress.emit("Finalizing...")

            # Store calibration results
            self.integration_time = cal_result.integration_time
            self.num_scans = cal_result.num_scans
            self.ref_intensity = cal_result.ref_intensity
            self.leds_calibrated = cal_result.leds_calibrated
            self.dark_noise = cal_result.dark_noise

            # Store alternative method specific data (per-channel integration and dark noise)
            self.calibration_method = getattr(
                cal_result,
                "calibration_method",
                "standard",
            )
            self.per_channel_integration = getattr(
                cal_result,
                "per_channel_integration",
                {},
            )
            self.per_channel_dark_noise = getattr(
                cal_result,
                "per_channel_dark_noise",
                {},
            )

            logger.info(
                f"📋 Stored calibration: method={self.calibration_method}, integration_time={self.integration_time}ms, num_scans={self.num_scans}",
            )
            if self.calibration_method == "alternative":
                logger.info(
                    f"   Per-channel integration times: {self.per_channel_integration}",
                )

            self.wave_data = cal_result.wave_data
            # Note: cal_result.fourier_weights is a base array, we'll compute per-channel weights below
            self.ref_sig = cal_result.ref_sig  # S-mode reference spectra
            self.ch_error_list = cal_result.ch_error_list.copy()
            self.s_ref_qc_results = getattr(
                cal_result,
                "s_ref_qc_results",
                {},
            )  # Optical QC results

            # ✨ CRITICAL: Validate ref_sig data integrity
            logger.info("🔍 Validating calibration data integrity...")
            for ch, ref_spectrum in self.ref_sig.items():
                if ref_spectrum is None:
                    logger.warning(f"   Channel {ch}: ref_sig is None")
                elif len(ref_spectrum) == 0:
                    logger.warning(f"   Channel {ch}: ref_sig is empty array")
                elif len(ref_spectrum) != len(self.wave_data):
                    logger.error(
                        f"   Channel {ch}: ref_sig length mismatch! ref={len(ref_spectrum)} vs wave={len(self.wave_data)}",
                    )
                else:
                    logger.info(
                        f"   ✅ Channel {ch}: ref_sig valid ({len(ref_spectrum)} points)",
                    )

            # Store channel performance metrics for ML system intelligence
            self.channel_performance = getattr(cal_result, "channel_performance", {})

            # Calculate SNR-aware Fourier weights from S-ref LED profiles
            # Uses LED profile as metadata to guide peak finding (not for flattening)
            # This will populate self.fourier_weights as a dict: {channel: weights_array}
            logger.info("Starting Fourier weights calculation...")
            self._calculate_snr_aware_fourier_weights()
            logger.info("Fourier weights calculation complete")

            self.calibration_progress.emit("Completing calibration...")

            # Mark as calibrated
            self.calibrated = True

            # Load afterglow correction if available
            afterglow_loaded = self._load_afterglow_correction()

            # Emit calibration complete with settings and channel errors
            calibration_data = {
                "integration_time": self.integration_time,
                "num_scans": self.num_scans,
                "ref_intensity": self.ref_intensity,
                "leds_calibrated": self.leds_calibrated.copy(),
                "ch_error_list": self.ch_error_list.copy(),
                "s_ref_qc_results": self.s_ref_qc_results,  # Include optical QC results
                "channel_performance": self.channel_performance,  # Per-channel metrics for ML
                "calibration_type": "full",  # This is full LED calibration with afterglow
                "afterglow_available": afterglow_loaded,  # Flag for UI to prompt OEM calibration
                "sp_validation_results": getattr(
                    self,
                    "_sp_validation_results",
                    {},
                ),  # S/P orientation data
            }

            if len(self.ch_error_list) > 0:
                logger.warning(
                    f"⚠️ Calibration complete with errors in channels: {self.ch_error_list}",
                )
            else:
                logger.info("✅ Calibration complete - all channels OK")

            # Update system intelligence with calibration metrics (DISABLED)
            # if SYSTEM_INTELLIGENCE_AVAILABLE:
            #     self._update_calibration_intelligence(calibration_data)

            self.calibration_complete.emit(calibration_data)

        except Exception as e:
            logger.exception(f"Calibration failed: {e}")
            self.calibration_failed.emit(str(e))

    def start_acquisition(self):
        """Start continuous spectrum acquisition (non-blocking)."""
        try:
            logger.info("🎯 start_acquisition called")

            if not self.calibrated:
                self.acquisition_error.emit("Calibrate before starting acquisition")
                return

            if not self._check_hardware():
                self.acquisition_error.emit("Hardware not connected")
                return

            # ✨ CRITICAL: Validate calibration data before starting acquisition
            if not self.ref_sig or len(self.ref_sig) == 0:
                logger.error(
                    "❌ FATAL: ref_sig is empty or None - cannot start acquisition",
                )
                self.acquisition_error.emit(
                    "Calibration data missing. Please recalibrate.",
                )
                return

            if self.wave_data is None or len(self.wave_data) == 0:
                logger.error(
                    "❌ FATAL: wave_data is empty or None - cannot start acquisition",
                )
                self.acquisition_error.emit(
                    "Wavelength calibration missing. Please recalibrate.",
                )
                return

            # Validate ref_sig shapes match wave_data
            invalid_channels = []
            for ch, ref_spectrum in self.ref_sig.items():
                if ref_spectrum is None or len(ref_spectrum) != len(self.wave_data):
                    invalid_channels.append(ch)
                    logger.error(
                        f"❌ Channel {ch}: Invalid ref_sig (len={len(ref_spectrum) if ref_spectrum is not None else 'None'} vs wave={len(self.wave_data)})",
                    )

            if invalid_channels:
                logger.error(
                    f"❌ FATAL: Invalid calibration data for channels: {invalid_channels}",
                )
                self.acquisition_error.emit(
                    f"Calibration corrupted for channels {invalid_channels}. Please recalibrate.",
                )
                return

            logger.info("✅ Calibration data validation passed")

            if self._acquiring:
                logger.warning("Acquisition already running")
                return

            logger.info("Starting spectrum acquisition...")
            logger.info(
                f"📊 Calibrated settings: integration_time={self.integration_time}ms, num_scans={self.num_scans}",
            )
            logger.info(f"📊 LED intensities: {self.leds_calibrated}")

            # Ensure any previous acquisition thread is fully stopped
            if self._acquisition_thread and self._acquisition_thread.is_alive():
                logger.warning(
                    "Previous acquisition thread still running - waiting for cleanup...",
                )
                self._stop_acquisition.set()
                self._acquisition_thread.join(timeout=3.0)
                if self._acquisition_thread.is_alive():
                    logger.error(
                        "Failed to stop previous acquisition thread - forcing new start",
                    )

            # ✨ CRITICAL: Switch polarizer to P-mode ONCE before starting acquisition
            # S-ref and dark were already measured during calibration and are reused
            try:
                ctrl = self.hardware_mgr.ctrl
                if ctrl and hasattr(ctrl, "set_mode"):
                    logger.info(
                        "🔄 Switching polarizer to P-mode for live measurements...",
                    )
                    ctrl.set_mode("p")
                    time.sleep(0.4)  # Wait for servo to settle
                    logger.info(
                        "✅ Polarizer in P-mode - using calibrated S-ref and dark",
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer: {e}")

            # Clear batch buffers for fresh start
            for ch in ["a", "b", "c", "d"]:
                self._spectrum_batch[ch].clear()
                self._batch_timestamps[ch].clear()
                self._last_emitted_wavelength[ch] = None

            # Defer thread start to event loop to ensure all UI updates
            # from calibration completion have finished on main thread.
            self._acquiring = True
            self._stop_acquisition.clear()
            self._pause_acquisition.clear()

            # Start queue processing timer (runs in main thread)
            logger.info("Starting queue processing timer...")
            self._queue_timer.start(10)  # Process queue every 10ms

            # Diagnostic: verify calibration data is present
            logger.info(
                f"[ACQ] Starting acquisition with: wave_data={'present' if self.wave_data is not None else 'MISSING'}, ref_sig={'present' if self.ref_sig else 'MISSING'}",
            )

            def _launch_worker():
                try:
                    if not self._acquiring or self._stop_acquisition.is_set():
                        logger.debug("[DAQ] Acquisition canceled before worker launch")
                        return
                    logger.info("🚀 [DAQ] Launching acquisition worker thread")

                    # Emit signal BEFORE starting worker thread (safer)
                    self.acquisition_started.emit()
                    logger.info("✅ [DAQ] Acquisition started signal emitted")

                    self._acquisition_thread = threading.Thread(
                        target=self._acquisition_worker,
                        daemon=True,
                        name="AcquisitionWorker",
                    )
                    self._acquisition_thread.start()
                    logger.info("✅ [DAQ] Acquisition worker thread launched")
                except Exception as e:
                    logger.error(f"❌ CRASH in _launch_worker: {e}", exc_info=True)
                    import traceback

                    traceback.print_exc()

            logger.info("Scheduling worker launch in 50ms...")
            QTimer.singleShot(
                50,
                _launch_worker,
            )  # Small delay for UI thread to finish calibration updates
            logger.info("✅ start_acquisition completed successfully")
        except Exception as e:
            logger.error(f"❌ CRASH in start_acquisition: {e}", exc_info=True)
            import traceback

            traceback.print_exc()

    def stop_acquisition(self):
        """Stop spectrum acquisition and flush remaining batches."""
        if not self._acquiring:
            logger.debug("stop_acquisition called but not acquiring")
            return

        logger.info("Stopping spectrum acquisition...")

        # Stop queue processing timer
        if self._queue_timer:
            self._queue_timer.stop()

        # Signal thread to stop first
        self._stop_acquisition.set()
        self._acquiring = False

        # No batching anymore - just process remaining queue items
        self._process_spectrum_queue()

        # Wait for thread to finish (with timeout)
        if self._acquisition_thread and self._acquisition_thread.is_alive():
            logger.debug("Waiting for acquisition thread to stop...")
            self._acquisition_thread.join(timeout=3.0)
            if self._acquisition_thread.is_alive():
                logger.warning("⚠️ Acquisition thread did not stop within timeout")
            else:
                logger.info("✅ Acquisition thread stopped cleanly")

        self._acquisition_thread = None
        self.acquisition_stopped.emit()

    def pause_acquisition(self):
        """Pause spectrum acquisition without stopping the thread."""
        if not self._acquiring:
            return

        logger.info("⏸ Acquisition paused")
        self._pause_acquisition.set()  # Set flag to pause

    def resume_acquisition(self):
        """Resume spectrum acquisition after pause."""
        if not self._acquiring:
            return

        logger.info("▶️ Acquisition resumed")
        self._pause_acquisition.clear()  # Clear flag to resume

    def _process_spectrum_queue(self):
        """Process spectrum data from worker thread queue and emit Qt signals.

        This method runs in the main thread (called by QTimer) and safely
        emits Qt signals with data from the worker thread queue.
        """
        try:
            # Process multiple items per timer tick for efficiency
            max_items = 20
            items_processed = 0

            while items_processed < max_items:
                try:
                    data = self._spectrum_queue.get_nowait()

                    # Check if this is an error message (special key '_error')
                    if isinstance(data, dict) and "_error" in data:
                        self.acquisition_error.emit(data["_error"])
                    else:
                        # Regular spectrum data
                        self.spectrum_acquired.emit(data)

                    items_processed += 1
                except queue.Empty:
                    break  # Queue empty, done for this tick

        except Exception as e:
            logger.error(f"Error processing spectrum queue: {e}")

    def _acquisition_worker(self):
        """Main acquisition loop running in background thread with batched processing."""
        print("\n" + "=" * 70)
        print("ACQUISITION WORKER THREAD ENTERED")
        print("=" * 70)

        try:
            # Remove Qt initialization delay - might be causing USB threading conflicts
            # time.sleep(0.2)  # DISABLED - caused segfault
            print("[Worker] Starting immediately (no Qt init delay)")

            print("\n" + "=" * 70)
            print("ACQUISITION WORKER STARTED")
            print("=" * 70)

            channels = ["a", "b", "c", "d"]
            consecutive_errors = 0
            max_consecutive_errors = 5  # Stop after 5 consecutive failures
            cycle_count = 0

            # Pre-flight check
            print(
                f"[Worker] Hardware check: ctrl={self.hardware_mgr.ctrl is not None}, usb={self.hardware_mgr.usb is not None}",
            )
            print(
                f"[Worker] Calibration check: wave_data={self.wave_data is not None}, leds={len(self.leds_calibrated)} channels",
            )

            while not self._stop_acquisition.is_set():
                cycle_count += 1
                if cycle_count % 10 == 1:
                    print(f"[Worker] Cycle {cycle_count} - acquiring spectra...")
                try:
                    # Check if paused - sleep and skip acquisition cycle
                    if self._pause_acquisition.is_set():
                        time.sleep(0.1)  # Sleep while paused
                        continue

                    cycle_success = False

                    # Acquire spectrum for each channel (immediate processing, no batching)
                    for ch in channels:
                        try:
                            if self._stop_acquisition.is_set():
                                break

                            # Get raw spectrum from hardware (fast read)
                            spectrum_data = self._acquire_channel_spectrum(ch)

                            if spectrum_data:
                                if cycle_count % 10 == 1:
                                    print(f"   [OK] Channel {ch}: Got spectrum data")

                                # Process and emit immediately (no batching)
                                timestamp = time.time()
                                cycle_success = True

                                # Process spectrum immediately
                                try:
                                    processed = self._process_spectrum(
                                        ch,
                                        spectrum_data,
                                    )

                                    # Buffer the data
                                    self.channel_buffers[ch].append(
                                        processed["wavelength"],
                                    )
                                    self.time_buffers[ch].append(timestamp)

                                    # Put processed data in queue for emission
                                    data = {
                                        "channel": ch,
                                        "wavelength": processed["wavelength"],
                                        "intensity": processed["intensity"],
                                        "full_spectrum": processed.get("full_spectrum"),
                                        "raw_spectrum": processed.get("raw_spectrum"),
                                        "transmission_spectrum": processed.get(
                                            "transmission_spectrum",
                                        ),
                                        "wavelengths": self.wave_data,  # Wavelength array for plotting
                                        "timestamp": timestamp,
                                        "is_preview": False,
                                    }

                                    try:
                                        self._spectrum_queue.put_nowait(data)
                                        if cycle_count % 10 == 1:
                                            print(
                                                f"   [EMIT] Channel {ch}: Data queued for UI",
                                            )
                                    except queue.Full:
                                        pass  # Queue full, skip

                                    # Store last emitted wavelength
                                    self._last_emitted_wavelength[ch] = processed[
                                        "wavelength"
                                    ]

                                except Exception as e:
                                    print(
                                        f"   [ERROR] Channel {ch}: Processing failed - {e}",
                                    )
                                    import traceback

                                    traceback.print_exc()
                            elif cycle_count % 10 == 1:
                                print(
                                    f"   [ERROR] Channel {ch}: No spectrum data returned",
                                )

                        except Exception as e:
                            print(f"   [FATAL] Channel {ch} loop crashed: {e}")
                            import traceback

                            traceback.print_exc()

                    # Reset error counter if we got at least one successful acquisition
                    if cycle_success:
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                        print(
                            f"[Worker] Cycle {cycle_count}: NO successful acquisitions - consecutive_errors={consecutive_errors}/{max_consecutive_errors}",
                        )

                        # Stop if too many consecutive errors
                        if consecutive_errors >= max_consecutive_errors:
                            print(
                                f"[Worker] ❌ STOPPING: {max_consecutive_errors} consecutive failed cycles",
                            )
                            # Removed logger.error to prevent Qt threading issues
                            # Use queue to send error signal from worker thread
                            try:
                                self._spectrum_queue.put_nowait(
                                    {
                                        "_error": "Hardware communication lost - stopping acquisition",
                                    },
                                )
                            except queue.Full:
                                pass
                            self._stop_acquisition.set()
                            break

                    # Small delay between acquisition cycles
                    time.sleep(0.01)

                except Exception as e:
                    # Catch exceptions in acquisition loop
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        try:
                            self._spectrum_queue.put_nowait(
                                {"_error": f"Too many errors: {e}"},
                            )
                        except queue.Full:
                            pass
                        self._stop_acquisition.set()
                        break
                    time.sleep(0.5)

        except Exception as e:
            # Top-level exception handler - catch ANY uncaught exception
            import traceback

            error_msg = (
                f"FATAL: Acquisition worker crashed: {e}\n{traceback.format_exc()}"
            )
            print(error_msg)  # Print to console
            try:
                self._spectrum_queue.put_nowait({"_error": error_msg})
            except:
                pass

    def _check_hardware(self) -> bool:
        """Check if required hardware is connected."""
        return self.hardware_mgr.ctrl is not None and self.hardware_mgr.usb is not None

    def _read_wavelength_data(self) -> bool:
        """Read wavelength calibration from spectrometer."""
        try:
            usb = self.hardware_mgr.usb
            if not usb:
                return False

            # Get wavelength array from spectrometer
            # This is a placeholder - actual implementation depends on detector API
            logger.info("Reading wavelength calibration data...")
            # wave_data = usb.read_wavelength()
            # self.wave_data = wave_data[self.wave_min_index:self.wave_max_index]

            # Placeholder: create dummy wavelength array
            self.wave_data = np.linspace(400, 900, 2048)
            return True

        except Exception as e:
            logger.error(f"Failed to read wavelength data: {e}")
            return False

    def _measure_dark_noise(self) -> bool:
        """Measure dark noise with LEDs off."""
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                return False

            logger.info("Measuring dark noise...")
            # Turn off all LEDs
            # ctrl.all_leds_off()
            time.sleep(0.1)

            # Read spectrum
            # self.dark_noise = usb.read_spectrum()

            # Placeholder
            self.dark_noise = np.zeros(len(self.wave_data))
            return True

        except Exception as e:
            logger.error(f"Failed to measure dark noise: {e}")
            return False

    def _calibrate_reference_led(self) -> bool:
        """Calibrate reference LED to target intensity."""
        try:
            logger.info("Calibrating reference LED...")
            # Placeholder - would adjust LED intensity to target
            self.ref_intensity = 255
            return True

        except Exception as e:
            logger.error(f"Failed to calibrate reference LED: {e}")
            return False

    def _read_reference_spectrum(self) -> bool:
        """Read reference spectrum."""
        try:
            logger.info("Reading reference spectrum...")
            # Placeholder
            self.ref_spectrum = np.ones(len(self.wave_data)) * self.ref_intensity
            return True

        except Exception as e:
            logger.error(f"Failed to read reference spectrum: {e}")
            return False

    def _calculate_snr_aware_fourier_weights(self):
        """Calculate SNR-aware Fourier weights from S-ref LED profiles.

        Uses the S-mode reference spectrum (LED profile) as metadata to guide
        peak finding toward high-SNR regions, rather than flattening the spectrum.

        Key advantages:
        - Preserves true signal shape (no S-mode vs P-mode mismatch artifacts)
        - Weights peak finding toward reliable data (high LED intensity regions)
        - Accounts for wavelength-dependent noise (lower at blue end)
        """
        try:
            from utils.spr_signal_processing import calculate_snr_aware_fourier_weights

            # Check if we have required data (use proper numpy array checks)
            if not self.ref_sig or self.wave_data is None or len(self.wave_data) == 0:
                logger.warning(
                    "Cannot calculate SNR-aware weights: missing ref_sig or wave_data",
                )
                return

            logger.info("Calculating SNR-aware Fourier weights from LED profiles...")

            for ch in ["a", "b", "c", "d"]:
                if ch in self.ref_sig and self.ref_sig[ch] is not None:
                    # Calculate weights that favor high-SNR regions of LED profile
                    self.fourier_weights[ch] = calculate_snr_aware_fourier_weights(
                        ref_spectrum=self.ref_sig[ch],
                        wavelengths=self.wave_data,
                        alpha=2e3,  # Standard Fourier denoising strength
                        snr_weight_strength=0.5,  # 50% SNR weighting, 50% uniform
                    )
                    logger.info(f"✓ Ch {ch.upper()}: SNR-aware weights calculated")
                else:
                    logger.warning(
                        f"Ch {ch.upper()}: No ref spectrum, using uniform weights",
                    )
                    self.fourier_weights[ch] = np.ones(len(self.wave_data) - 1)

        except Exception as e:
            logger.warning(f"Failed to calculate SNR-aware Fourier weights: {e}")
            logger.exception(e)  # Show full traceback for debugging
            # Fallback to uniform weights
            for ch in ["a", "b", "c", "d"]:
                self.fourier_weights[ch] = np.ones(len(self.wave_data) - 1)

    def _process_and_emit_batch(self, channel: str) -> None:
        """Process and emit a batch of spectra for a channel.

        Processes all buffered raw spectra and emits them individually to maintain
        compatibility with existing UI code while reducing acquisition overhead.
        """
        batch = self._spectrum_batch[channel]
        timestamps = self._batch_timestamps[channel]

        if not batch:
            return

        # Process each spectrum in the batch
        for spectrum_data, timestamp in zip(batch, timestamps, strict=False):
            try:
                # Process spectrum (filtering, peak finding)
                processed = self._process_spectrum(channel, spectrum_data)

                # Buffer the data
                self.channel_buffers[channel].append(processed["wavelength"])
                self.time_buffers[channel].append(timestamp)

                # Put processed data in queue instead of emitting directly
                data = {
                    "channel": channel,
                    "wavelength": processed["wavelength"],
                    "intensity": processed["intensity"],
                    "full_spectrum": processed.get("full_spectrum"),
                    "raw_spectrum": processed.get(
                        "raw_spectrum",
                    ),  # P-mode spectrum for transmission calc
                    "transmission_spectrum": processed.get(
                        "transmission_spectrum",
                    ),  # P/S ratio
                    "timestamp": timestamp,
                    "is_preview": False,  # Real processed data
                }

                try:
                    self._spectrum_queue.put_nowait(data)
                except queue.Full:
                    pass  # Queue full, drop this data point

                # Update last emitted wavelength for interpolation
                self._last_emitted_wavelength[channel] = processed["wavelength"]

            except Exception:
                # Removed logger.error to prevent Qt threading issues
                pass  # Silent failure to avoid Qt threading crashes

        # Clear the batch buffers
        self._spectrum_batch[channel].clear()
        self._batch_timestamps[channel].clear()

    def _emit_interpolated_preview(self, channel: str, timestamp: float) -> None:
        """Emit interpolated preview point for smooth display during batch accumulation.

        While waiting for batch to fill, emit preview points that interpolate
        between last known wavelength and current timestamp. This creates smooth
        visual feedback without compromising data accuracy.

        The actual processed data will overwrite these preview points when batch completes.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            timestamp: Current acquisition timestamp

        """
        try:
            last_wavelength = self._last_emitted_wavelength[channel]

            if last_wavelength is None:
                return  # No previous data to interpolate from

            # Put preview data in queue instead of emitting directly
            # This avoids Qt threading violations
            data = {
                "channel": channel,
                "wavelength": last_wavelength,  # Hold last value (simple interpolation)
                "intensity": 0.0,  # Placeholder
                "full_spectrum": None,
                "timestamp": timestamp,
                "is_preview": True,  # Flag to indicate this is interpolated
            }

            try:
                self._spectrum_queue.put_nowait(data)
            except queue.Full:
                pass  # Queue full, skip this preview

        except Exception:
            # Removed logger.debug to prevent Qt threading issues
            pass  # Silent failure

    def _acquire_channel_spectrum(self, channel: str) -> dict | None:
        """Acquire raw spectrum for a channel."""
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                print(
                    f"[ACQ ERROR] Channel {channel}: Hardware not available (ctrl={ctrl is not None}, usb={usb is not None})",
                )
                return None

            # Check if we have wave_data from calibration
            if self.wave_data is None or len(self.wave_data) == 0:
                print(
                    f"[ACQ ERROR] Channel {channel}: No wavelength data from calibration",
                )
                return None

            # Turn on LED for channel (already in P-mode from start_acquisition)
            led_intensity = (
                self.leds_calibrated.get(channel, 180)
                if isinstance(self.leds_calibrated, dict)
                else 180
            )
            # NOTE: Polarizer is already in P-mode (set once at start_acquisition)
            # No need to call set_mode('p') here - that would cause unnecessary servo rotation
            try:
                ctrl.set_intensity(ch=channel, raw_val=led_intensity)
            except Exception as e:
                print(
                    f"[ACQ ERROR] Channel {channel}: Failed to set LED intensity: {e}",
                )
                return None

            # Use configured LED delay (default 45ms)
            time.sleep(self._led_delay_ms / 1000.0)  # Convert ms to seconds

            # Set integration time
            try:
                usb.set_integration(self.integration_time)
            except ConnectionError:
                print(
                    f"[ACQ ERROR] Channel {channel}: Spectrometer disconnected during integration set",
                )
                self.acquisition_error.emit(
                    "Spectrometer disconnected. Please reconnect and restart.",
                )
                self.stop_acquisition()
                return None
            except Exception as e:
                print(
                    f"[ACQ ERROR] Channel {channel}: Failed to set integration time: {e}",
                )
                return None

            # Read spectrum intensities
            try:
                raw_spectrum = usb.read_intensity()
            except ConnectionError:
                print(
                    f"[ACQ ERROR] Channel {channel}: Spectrometer disconnected during read",
                )
                self.acquisition_error.emit(
                    "Spectrometer disconnected. Please reconnect and restart.",
                )
                self.stop_acquisition()
                return None
            except Exception as e:
                print(f"[ACQ ERROR] Channel {channel}: Failed to read spectrum: {e}")
                return None

            if raw_spectrum is None:
                print(f"[ACQ ERROR] Channel {channel}: read_intensity returned None")
                return None

            # Trim spectrum to match wave_data range using stored indices from calibration
            if len(raw_spectrum) != len(self.wave_data):
                # Use indices stored during calibration (eliminates expensive USB read)
                if hasattr(self, "wave_min_index") and hasattr(self, "wave_max_index"):
                    raw_spectrum = raw_spectrum[
                        self.wave_min_index : self.wave_max_index
                    ]
                else:
                    # Fallback if indices not available (shouldn't happen after calibration)
                    raw_spectrum = raw_spectrum[: len(self.wave_data)]

            return {
                "wavelength": self.wave_data.copy(),
                "intensity": raw_spectrum,
            }

        except Exception as e:
            print(f"[ACQ FATAL] Channel {channel}: Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            return None

        except Exception:
            # Removed logger.error to prevent Qt threading issues
            return None

    def _process_spectrum(self, channel: str, spectrum_data: dict) -> dict:
        """Process raw spectrum (filtering, afterglow correction, peak finding)."""
        try:
            wavelength = spectrum_data["wavelength"]
            intensity = spectrum_data["intensity"]

            # Subtract dark noise
            if self.dark_noise is not None:
                # ✨ CRITICAL: Check shape compatibility before subtraction
                if len(intensity) != len(self.dark_noise):
                    print(
                        f"[PROCESS] WARNING: Shape mismatch - intensity({len(intensity)}) vs dark({len(self.dark_noise)})",
                    )
                    print(
                        f"[PROCESS] Using first {min(len(intensity), len(self.dark_noise))} elements",
                    )
                    min_len = min(len(intensity), len(self.dark_noise))
                    intensity = intensity[:min_len] - self.dark_noise[:min_len]
                    wavelength = wavelength[:min_len]
                else:
                    intensity = intensity - self.dark_noise

            # Store raw spectrum (dark corrected)
            raw_spectrum = intensity.copy()

            # Calculate transmission spectrum (P/S ratio) for peak finding
            transmission_spectrum = None
            if channel in self.ref_sig and self.ref_sig[channel] is not None:
                try:
                    from utils.spr_signal_processing import calculate_transmission

                    # ✨ CRITICAL: Check shape compatibility before transmission calculation
                    ref_spectrum = self.ref_sig[channel]
                    if len(raw_spectrum) != len(ref_spectrum):
                        print(
                            f"[PROCESS] ERROR: Shape mismatch - raw({len(raw_spectrum)}) vs ref({len(ref_spectrum)})",
                        )
                        print(
                            "[PROCESS] This should never happen! Calibration data may be corrupted.",
                        )
                        # Resize ref_spectrum to match raw_spectrum
                        min_len = min(len(raw_spectrum), len(ref_spectrum))
                        raw_spectrum_aligned = raw_spectrum[:min_len]
                        ref_spectrum_aligned = ref_spectrum[:min_len]
                        transmission_spectrum = calculate_transmission(
                            raw_spectrum_aligned,
                            ref_spectrum_aligned,
                        )
                        print(f"[PROCESS] Recovered by trimming to {min_len} points")
                    else:
                        # Calculate transmission percentage
                        transmission_spectrum = calculate_transmission(
                            raw_spectrum,
                            ref_spectrum,
                        )
                except Exception as e:
                    print(f"[PROCESS] Transmission calc failed: {e}")
                    import traceback

                    traceback.print_exc()
                    transmission_spectrum = None

            # SIMPLIFIED: Find peak by simple min-finding (bypass complex Fourier analysis)
            peak_input = (
                transmission_spectrum
                if transmission_spectrum is not None
                else intensity
            )
            if len(peak_input) > 0 and len(wavelength) == len(peak_input):
                min_idx = np.argmin(peak_input)
                peak_wavelength = wavelength[min_idx]
            else:
                peak_wavelength = 650.0  # Default fallback

            return {
                "wavelength": peak_wavelength,
                "intensity": intensity[np.argmin(intensity)]
                if len(intensity) > 0
                else 0.0,
                "full_spectrum": raw_spectrum,
                "raw_spectrum": raw_spectrum,
                "transmission_spectrum": transmission_spectrum,
                "fwhm": None,
            }

        except Exception as e:
            print(f"[PROCESS] ERROR in _process_spectrum: {e}")
            import traceback

            traceback.print_exc()
            # Return raw data on error
            return {
                "wavelength": 650.0,
                "intensity": 0.0,
                "full_spectrum": spectrum_data["intensity"],
                "raw_spectrum": spectrum_data["intensity"],
            }

    def _find_resonance_peak(
        self,
        wavelength: np.ndarray,
        spectrum: np.ndarray,
        channel: str,
    ) -> float:
        """Find resonance peak wavelength using SNR-aware Fourier analysis.

        Uses the Fourier transform method with SNR-aware weights to find
        the resonance dip minimum. The Fourier approach:
        1. Denoises spectrum in frequency domain
        2. Calculates derivative via IDCT
        3. Finds zero-crossing (dip minimum)

        The SNR-aware weights guide the algorithm toward high-quality regions
        of the spectrum (high LED intensity = high SNR).

        Args:
            wavelength: Wavelength array
            spectrum: Transmission spectrum (P/S ratio %) or P-mode intensity
            channel: Channel identifier for accessing channel-specific SNR weights

        Returns:
            Resonance wavelength in nm

        Note:
            This output can feed both processing pipelines:
            - Pipeline 1: Zero-finding method (this Fourier approach)
            - Pipeline 2: Multi-parametric approach (centroid, width, etc.)

        """
        try:
            from utils.spr_signal_processing import find_resonance_wavelength_fourier

            # Get channel-specific SNR-aware Fourier weights if available
            weights = (
                self.fourier_weights.get(channel)
                if isinstance(self.fourier_weights, dict)
                else self.fourier_weights
            )

            if weights is not None and len(weights) > 0:
                # Use SNR-aware Fourier analysis (frequency-domain denoising + zero-finding)
                peak_wavelength = find_resonance_wavelength_fourier(
                    transmission_spectrum=spectrum,
                    wavelengths=wavelength,
                    fourier_weights=weights,
                )

                # Validate result
                if (
                    not np.isnan(peak_wavelength)
                    and wavelength[0] <= peak_wavelength <= wavelength[-1]
                ):
                    return peak_wavelength
                # Fourier method failed, using fallback

            # Fallback to simple minimum finding (proven reliable main code pipeline)
            peak_idx = np.argmin(spectrum)
            peak_wavelength = wavelength[peak_idx]
            return peak_wavelength

        except Exception:
            # Removed logger.debug to prevent Qt threading issues
            # Final fallback
            peak_idx = np.argmin(spectrum) if len(spectrum) > 0 else 0
            return wavelength[peak_idx] if len(wavelength) > peak_idx else 650.0

    def _calculate_fwhm(
        self,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
        peak_wl: float,
    ) -> float:
        """Calculate Full Width at Half Maximum (FWHM) of SPR dip.

        FWHM is the width of the SPR dip at half the depth between the minimum
        and the baseline. It's a key quality metric:
        - <30nm = excellent coupling (sharp resonance)
        - 30-50nm = acceptable (typical for buffer)
        - >80nm = poor coupling (possible dry sensor or air bubble)

        Args:
            wavelengths: Wavelength array (nm)
            transmission: Transmission spectrum (P/S ratio %)
            peak_wl: Peak wavelength (minimum of dip)

        Returns:
            FWHM in nm, or NaN if calculation fails

        """
        try:
            # Define SPR search region (600-750nm)
            mask = (wavelengths >= 600) & (wavelengths <= 750)
            wl = wavelengths[mask]
            trans = transmission[mask]

            if len(trans) < 10:
                return np.nan

            # Find minimum (dip bottom)
            min_idx = np.argmin(trans)
            min_val = trans[min_idx]

            # Estimate baseline from edges of SPR region
            edge_width = min(50, len(trans) // 4)
            baseline = (np.mean(trans[:edge_width]) + np.mean(trans[-edge_width:])) / 2

            # Half maximum level
            half_depth = min_val + 0.5 * (baseline - min_val)

            # Find crossing points on left and right sides of minimum
            left_trans = trans[:min_idx]
            right_trans = trans[min_idx:]

            # Left crossing (find where transmission crosses half_depth going down)
            left_crossing_idx = np.where(left_trans <= half_depth)[0]
            if len(left_crossing_idx) == 0:
                left_wl = wl[0]  # Use edge as fallback
            else:
                left_wl = wl[left_crossing_idx[-1]]  # Last crossing before minimum

            # Right crossing (find where transmission crosses half_depth going up)
            right_crossing_idx = np.where(right_trans <= half_depth)[0]
            if len(right_crossing_idx) == 0:
                right_wl = wl[-1]  # Use edge as fallback
            else:
                right_wl = wl[
                    min_idx + right_crossing_idx[-1]
                ]  # Last crossing after minimum

            # FWHM is the distance between crossings
            fwhm = right_wl - left_wl

            # Sanity check: FWHM should be reasonable (5-200nm)
            if 5 <= fwhm <= 200:
                return float(fwhm)
            return np.nan

        except Exception:
            return np.nan

    def _compute_spectral_correction(self):
        """DEPRECATED: Spectral correction removed.

        The LED profile correction was flawed because:
        1. S-ref captured in S-mode, live data in P-mode
        2. LED profiles differ between S and P polarizations
        3. Dividing P-mode by S-mode ref creates artifacts
        4. Output doesn't match transmission band shape

        New approach: Use S-ref as SNR metadata in Fourier weights
        - Guides peak finding toward high-SNR regions
        - No spectrum flattening (preserves true signal)
        - See: _calculate_snr_aware_fourier_weights()
        """
        logger.info(
            "Spectral correction disabled - using SNR-aware peak finding instead",
        )

    def _load_afterglow_correction(self) -> bool:
        """Load device-specific afterglow correction calibration.

        Implements three-tier automatic mode selection:
        - FAST mode (< 50ms total delay): Correction enabled for high-speed acquisition
        - NORMAL mode (50-100ms): Correction enabled (default)
        - SLOW mode (> 100ms): Correction disabled (afterglow negligible)

        This is OPTIONAL - system works fine without it (legacy devices).
        Missing calibration is normal and expected for devices in the field.

        Returns:
            True if afterglow correction loaded successfully, False otherwise

        """
        try:
            from afterglow_correction import AfterglowCorrection

            from settings import (
                AFTERGLOW_AUTO_MODE,
                AFTERGLOW_FAST_THRESHOLD_MS,
                AFTERGLOW_SLOW_THRESHOLD_MS,
                LED_DELAY,
                LED_POST_DELAY,
            )
            from utils.device_integration import get_device_optical_calibration_path

            optical_cal_path = get_device_optical_calibration_path()

            if optical_cal_path and optical_cal_path.exists():
                self.afterglow_correction = AfterglowCorrection(optical_cal_path)

                # Determine afterglow mode based on total acquisition delay
                if AFTERGLOW_AUTO_MODE:
                    # Calculate total delay (pre + post)
                    total_delay_ms = (LED_DELAY * 1000) + (LED_POST_DELAY * 1000)

                    if total_delay_ms < AFTERGLOW_FAST_THRESHOLD_MS:
                        self.afterglow_mode = "fast"
                        self.afterglow_enabled = True
                        logger.info(
                            f"✅ Optical correction loaded: {optical_cal_path.name}",
                        )
                        logger.info(
                            f"   Mode: FAST (total delay {total_delay_ms:.1f}ms < {AFTERGLOW_FAST_THRESHOLD_MS}ms)",
                        )
                        logger.info(
                            "   High-speed acquisition: Afterglow correction enabled for 2x faster operation",
                        )
                    elif total_delay_ms <= AFTERGLOW_SLOW_THRESHOLD_MS:
                        self.afterglow_mode = "normal"
                        self.afterglow_enabled = True
                        logger.info(
                            f"✅ Optical correction loaded: {optical_cal_path.name}",
                        )
                        logger.info(
                            f"   Mode: NORMAL (total delay {total_delay_ms:.1f}ms, optimal range)",
                        )
                        logger.info(
                            "   Standard operation: Afterglow correction enabled for better stability",
                        )
                    else:
                        self.afterglow_mode = "slow"
                        self.afterglow_enabled = False
                        logger.info(
                            f"✅ Optical correction loaded: {optical_cal_path.name}",
                        )
                        logger.info(
                            f"   Mode: SLOW (total delay {total_delay_ms:.1f}ms > {AFTERGLOW_SLOW_THRESHOLD_MS}ms)",
                        )
                        logger.info(
                            "   Afterglow negligible (<0.2% of signal), correction disabled",
                        )
                else:
                    # Manual mode - always enable if calibration exists
                    self.afterglow_mode = "manual"
                    self.afterglow_enabled = True
                    logger.info(
                        f"✅ Optical correction loaded: {optical_cal_path.name}",
                    )
                    logger.info(
                        "   Mode: MANUAL (auto mode disabled, correction always enabled)",
                    )

                # Calculate optimal LED delay if enabled
                try:
                    from settings import (
                        LED_DELAY_TARGET_RESIDUAL,
                        USE_DYNAMIC_LED_DELAY,
                    )

                    if USE_DYNAMIC_LED_DELAY and self.integration_time:
                        optimal_delay = self.afterglow_correction.get_optimal_led_delay(
                            integration_time_ms=float(self.integration_time),
                            target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                        )
                        # Convert to ms and validate range (5ms - 200ms)
                        optimal_delay_ms = optimal_delay * 1000
                        if 5.0 <= optimal_delay_ms <= 200.0:
                            self._led_delay_ms = optimal_delay_ms
                            logger.info(
                                f"   Optimal LED delay: {self._led_delay_ms:.1f} ms",
                            )
                except Exception as e:
                    logger.debug(f"Dynamic LED delay calculation skipped: {e}")
                return True
            # Normal for legacy devices - not an error condition
            logger.debug(
                "No optical calibration file found (normal for legacy devices)",
            )
            self.afterglow_enabled = False
            return False
        except FileNotFoundError:
            # Expected for devices without optical calibration - completely silent
            logger.debug("Optical calibration not present (legacy device)")
            self.afterglow_enabled = False
            return False
        except Exception as e:
            # Only log actual errors (corrupted file, invalid format, etc.)
            logger.info(f"Optical correction not available: {e}")
            self.afterglow_enabled = False
            return False

    def _update_calibration_intelligence(self, calibration_data: dict):
        """Update system intelligence with calibration metrics.

        Args:
            calibration_data: Dict containing calibration results including channel_performance

        """
        si = get_system_intelligence()

        # Calculate per-channel quality scores from S-ref QC results
        quality_scores = {}
        failed_channels = []

        if "s_ref_qc_results" in calibration_data:
            for ch, qc_data in calibration_data["s_ref_qc_results"].items():
                # QC score combines multiple factors (intensity, noise, etc.)
                # Higher is better, range 0-1
                quality_score = qc_data.get("quality_score", 0.0)
                quality_scores[ch] = quality_score

                if qc_data.get("failed", False):
                    failed_channels.append(ch)

        # If no QC results, estimate quality from error list
        if not quality_scores:
            for ch in ["a", "b", "c", "d"]:
                if ch in self.ch_error_list:
                    quality_scores[ch] = 0.0
                    failed_channels.append(ch)
                else:
                    quality_scores[ch] = 0.9  # Assume good if no error

        # Update intelligence with calibration results
        success = len(failed_channels) == 0
        si.update_calibration_metrics(
            success=success,
            quality_scores=quality_scores,
            failed_channels=failed_channels if not success else None,
        )

        # Update LED health from calibrated intensities
        for ch, intensity in self.leds_calibrated.items():
            # Target is typically 30000 counts
            target = 30000
            si.update_led_health(
                channel=ch,
                intensity=intensity,
                target=target,
            )

        # NEW: Update channel performance characteristics for ML guidance
        # These metrics inform peak tracking sensitivity and noise models
        if "channel_performance" in calibration_data:
            for ch, perf in calibration_data["channel_performance"].items():
                # Store per-channel characteristics
                si.update_channel_characteristics(
                    channel=ch,
                    max_signal=perf.get("max_counts", 0),
                    utilization_pct=perf.get("utilization_pct", 0),
                    boost_ratio=perf.get("boost_ratio", 1.0),
                    optical_limit_reached=perf.get("optical_limit_reached", False),
                    hit_saturation=perf.get("hit_saturation", False),
                )

    def _update_signal_intelligence(
        self,
        channel: str,
        wavelength: float,
        snr: float,
        transmission_quality: float,
    ):
        """Update system intelligence with signal quality metrics.

        Args:
            channel: Channel ID ('a', 'b', 'c', 'd')
            wavelength: Detected resonance wavelength (nm)
            snr: Signal-to-noise ratio (dB)
            transmission_quality: Quality metric for transmission spectrum (0-1)

        """
        if not SYSTEM_INTELLIGENCE_AVAILABLE:
            return

        si = get_system_intelligence()
        si.update_signal_quality(
            channel=channel,
            snr=snr,
            peak_wavelength=wavelength,
            transmission_quality=transmission_quality,
        )

    def clear_buffers(self):
        """Clear all data buffers."""
        for ch in ["a", "b", "c", "d"]:
            self.channel_buffers[ch].clear()
            self.time_buffers[ch].clear()
        logger.info("Data buffers cleared")
