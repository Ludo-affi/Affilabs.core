"""Data Acquisition Manager - Handles spectrum acquisition and processing.

ARCHITECTURE OVERVIEW (Matches Calibration Exactly):
====================================================

This module follows the same 4-layer architecture as calibration_6step.py:
"""

from __future__ import annotations

# =============================================================================
# ACQUISITION MODE CONFIGURATION
# =============================================================================
# Two acquisition methods available:
#
# 1. CYCLE_SYNC (V2.4 firmware) - Default, recommended
#    - Firmware sends ONE CYCLE_START event per cycle
#    - Python uses fixed timing offsets from CYCLE_START
#    - Performance: 1.0s/cycle, 75% less USB traffic
#    - Best for: Fast acquisition, deterministic timing
#
# 2. EVENT_RANK (Computer-level sync) - Fallback
#    - Firmware sends READY event for each LED (4 events/cycle)
#    - Python reads detector on each READY event
#    - Performance: 1.0-1.1s/cycle, more USB traffic
#    - Best for: Debugging, per-event validation
#
# Toggle between methods by changing USE_CYCLE_SYNC flag
# =============================================================================
USE_CYCLE_SYNC = True  # True = CYCLE_SYNC (V2.4), False = EVENT_RANK (computer-level)

# =============================================================================
# WATCHDOG CONFIGURATION
# =============================================================================
# Firmware watchdog prevents runaway operation if software crashes or disconnects
# Keepalive command "ka" must be sent periodically to keep firmware running
# =============================================================================
ENABLE_WATCHDOG = True  # Enable firmware watchdog safety feature
WATCHDOG_KEEPALIVE_INTERVAL = 60.0  # Send keepalive every 60 seconds

"""

LAYER 1: UI (main_simplified.py + LiveDataDialog)
  - User interface and display
  - Calls: data_mgr.start_acquisition()
  - Receives: Processed transmission via signals
  - Displays: LiveDataDialog.update_transmission_plot()

LAYER 2: SERVICE/COORDINATOR (DataAcquisitionManager)
  Public API:
    - start_acquisition() → spawns background thread
    - stop_acquisition() → stops background thread
    - apply_calibration(CalibrationData) → stores calibration
  Coordinator:
    - _acquisition_worker() → main acquisition loop (THIS FILE)
    - _queue_transmission_update() → queues data for UI

SPECTRUM DATA FIELD NAMING (UNIFIED):
======================================
  Standard field names in emitted data dictionaries:
    - 'raw_spectrum': Raw intensity data from detector (dark-corrected)
    - 'transmission_spectrum': Calculated transmission percentage
    - 'wavelengths': Wavelength array corresponding to spectra
    - 'wavelength': Single peak wavelength value (nm)
    - 'intensity': Single intensity value (for timeline)

  DEPRECATED aliases (kept only in test/debug utilities):
    - 'full_spectrum': Old alias for 'raw_spectrum' (DO NOT USE)

LAYER 3: HARDWARE ACQUISITION (DataAcquisitionManager)
  Function: _acquire_raw_spectrum(...all parameters..., pre_armed=False)

  SMART ACQUISITION with AUTO-OPTIMIZATION:
    Coordinator analyzes calibration data to detect optimization opportunities:

    Standard Mode (common integration time):
      ✅ Pre-arms detector ONCE before loop
      ✅ Passes pre_armed=True to skip set_integration()
      ✅ Saves ~7ms per channel (21ms per cycle)

    Alternative Mode (per-channel integration times):
      ⚡ Sets integration time for each channel
      ⚡ Passes pre_armed=False
      ⚡ Flexible but slower (necessary for per-channel times)

  Pattern (matches calibration exactly):
    0. Set integration time (SMART: only if not pre-armed)
    1. Set LED intensity (batch command - always)
    2. Wait pre_led_delay_ms (LED stabilization)
    3. Read spectrum from detector (num_scans averaging)
    4. Wait post_led_delay_ms (afterglow decay)
    5. Optional: LED overlap optimization
  Returns: RAW spectrum (numpy array) - NO PROCESSING

  MODE-AGNOSTIC + AUTO-OPTIMIZED:
    All parameters passed explicitly, coordinator decides optimization strategy

LAYER 4: PROCESSING (DataAcquisitionManager)
  Function: _process_spectrum(channel, spectrum_data)
  Steps (matches calibration Step 6 exactly):
    1. Dark Subtraction:
       SpectrumPreprocessor.process_polarization_data(
         raw_spectrum, dark_noise, channel_name, verbose=False
       )
    2. Transmission Calculation:
       TransmissionProcessor.process_single_channel(
         p_pol_clean, s_pol_ref, led_s, led_p, wavelengths,
         apply_sg_filter=True, baseline_method='percentile',
         baseline_percentile=95.0, verbose=False
       )
  Returns: Processed transmission ready for display

KEY PRINCIPLES:
==============
1. Hardware Layer Returns RAW Data
   - No processing, no dark subtraction
   - Just LED control + detector read
   - Same pattern in calibration and live

2. Processing Layer Uses Same Functions
   - SpectrumPreprocessor.process_polarization_data() for dark subtraction
   - TransmissionProcessor.process_single_channel() for transmission
   - Same parameters as calibration = same results

3. Pre-Arm Integration Time
   - Integration time SET INSIDE _acquire_raw_spectrum() for mode flexibility
   - Different modes may use different integration times
   - Standard: Single P-mode integration time for all channels
   - Alternative: Per-channel integration times possible
   - No pre-arm optimization - mode flexibility more important

4. Batch LED Commands
   - Use ctrl.set_batch_intensities(a=, b=, c=, d=)
   - 15x faster than individual commands
   - More deterministic timing

5. Architecture Consistency
   - Live acquisition MUST match calibration structure exactly
   - Same processing functions = same results
   - QC validation during calibration matches live view

BATCH PROCESSING:
================
All spectra are processed through the batch path for consistency:
1. Acquire raw spectrum from detector
2. Buffer in batch (size configurable, default 12)
3. Process batch:
   a. Dark noise subtraction (same as S-ref/P-ref measurements)
   b. Afterglow correction (residual LED decay from previous channel)
   c. Transmission calculation with LED intensity correction
   d. Baseline correction (polynomial flattening, matches QC report)
   e. Savitzky-Golay smoothing (window=21, polynomial=3 for denoising)
   f. Peak finding with FWHM validation
4. Apply SG filter to batch wavelengths for sensorgram smoothing
5. Emit processed data sequentially for smooth display

CRITICAL PRE-PROCESSING CONSISTENCY:
===================================
- Live P-pol data MUST receive the same dark/afterglow corrections as P-ref
- Transmission = (P-live - dark - afterglow) / (S-ref - dark - afterglow) × LED_correction
- Baseline correction applied to flatten spectral tilt (matches QC report exactly)
- Savitzky-Golay smoothing for noise reduction (preserves peak shape)
- This ensures live transmission matches QC report visualization EXACTLY

All operations run in background threads to avoid blocking the UI.
"""

import builtins
import contextlib
import gc
import queue
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

# Phase 1.1 Domain Model (replacing legacy CalibrationData type alias)
from affilabs.domain import CalibrationData
from affilabs.utils.logger import logger

# ✅ OPTIMIZATION: Disable automatic GC to eliminate random 10-50ms pauses
# Manual GC will be called periodically during safe times
gc.disable()


class DataAcquisitionManager(QObject):
    """Manages spectrum acquisition ONLY - no processing.

    Responsibilities:
    - Acquire raw spectra from hardware
    - Emit raw spectrum data via spectrum_acquired signal

    NOT responsible for:
    - Processing (dark subtraction, transmission calculation, peak finding)
    - Calibration (handled by CalibrationService)

    Processing is handled by a separate component that subscribes to spectrum_acquired.
    """

    # Signals for data updates
    spectrum_acquired = Signal(dict)  # RAW spectrum data with calibration refs
    acquisition_error = Signal(str)  # Error message
    acquisition_started = Signal()  # Emitted when acquisition loop starts
    acquisition_stopped = Signal()  # Emitted when acquisition loop stops

    def __init__(self, hardware_mgr) -> None:
        super().__init__()

        # Reference to hardware manager
        self.hardware_mgr = hardware_mgr

        # ===================================================================
        # CALIBRATION DATA (Single Source of Truth)
        # ===================================================================
        # All calibration parameters stored in immutable CalibrationData model.
        # Access via: self.calibration_data.integration_time, etc.
        #
        # CRITICAL: Live acquisition uses calibration_data directly.
        # No duplication, no conflicts, single source of truth.
        # ===================================================================
        self.calibrated = False
        self.calibration_data = None  # CalibrationData instance (set by apply_calibration)

        # Runtime state
        self.ch_error_list = []  # Failed channels from calibration

        # LED overlap optimization state
        self._led_overlap_active = False  # Track if LED is already ON from previous overlap

        # V2.4 CYCLE_SYNC state tracking
        self._rankbatch_running = False  # Track if rankbatch is active
        self._led_overlap_channel = None  # Track which LED is ON from overlap
        self._led_overlap_start_time = None  # Track when overlap LED was turned ON

        # Timing jitter tracking for SNR optimization
        self._timing_jitter_stats = {ch: [] for ch in ["a", "b", "c", "d"]}
        self._jitter_window_size = 100  # Track last 100 measurements per channel
        self._last_jitter_report = 0  # Time of last jitter statistics report

        # Firmware acquisition capabilities
        self._batch_supported = False  # Batch command support (DEFAULT)
        self._firmware_supports_rank = False  # Rankbatch/CYCLE_SYNC support (OPTIONAL)
        self._rank_mode_enabled = False  # Rankbatch mode enabled flag

        # Data loss tracking (acquisition only)
        self._dropped_acquisition = 0  # Spectra dropped at acquisition (queue full)
        self._last_drop_report = time.time()

        # Queue mode acquisition (sequential A→B→C→D)
        import settings as root_settings

        self.queue_size = getattr(root_settings, "QUEUE_SIZE", 4)

        # LED timing now controlled via Advanced Settings (LED_ON_TIME_MS, LED_OFF_TIME_MS)
        # No device-specific delays loaded - timing is global configuration

        # Timing instrumentation for LED/detector synchronization analysis
        self._enable_timing_instrumentation = getattr(
            root_settings,
            "ENABLE_TIMING_INSTRUMENTATION",
            True,
        )
        TIMING_LOG_INTERVAL = getattr(root_settings, "TIMING_LOG_INTERVAL", 100)
        self._timing_log_interval = TIMING_LOG_INTERVAL
        self._timing_data = {
            "led_command_times": [],  # Time to send LED command
            "led_to_read_delays": [],  # Time from LED ON to detector read start
            "detector_read_times": [],  # Time for detector to return data
            "total_cycle_times": [],  # Total time per channel
            "acquisition_count": 0,
        }

        # Acquisition state
        self._acquiring = False
        self._acquisition_thread = None
        self._stop_acquisition = threading.Event()
        self._pause_acquisition = threading.Event()  # Pause flag
        self._stop_processing = threading.Event()  # Processing thread stop flag

        # One-time run parameter summary flag (reset on each start)
        self._run_params_logged = False

    # LED TIMING ARCHITECTURE (Modern):
    # ==================================
    # LED timing is now controlled via Advanced Settings tab:
    # - LED_ON_TIME_MS (default 250ms) - LED illumination duration
    # - LED_OFF_TIME_MS (default 0ms) - LED transition/dark time
    #
    # BATCH mode: SOFTWARE-CONTROLLED synchronization
    #             - Python code handles timing (time.sleep)
    #             - Uses LED_ON/OFF values for software delays
    #             - Manual sequencing through channels
    #
    # RANKBATCH mode: FIRMWARE-CONTROLLED synchronization
    #                 - Hardware timer controls LED timing
    #                 - Passes LED_ON/OFF as "settle" and "dark" to firmware
    #                 - Format: rankbatch:a,b,c,d,settle,dark,cycles
    #                 - Example: rankbatch:128,128,128,128,250,0,3600
    #
    # Obsolete PRE/POST LED delay parameters have been removed.

    def set_queue_size(self, queue_size: int) -> None:
        """Set number of channels in sequential acquisition queue.

        Args:
            queue_size: Number of channels (typically 4 for A, B, C, D).
                       Not used for batching - acquisition is sequential/queued.

        """
        if queue_size < 1:
            logger.warning(f"Invalid queue_size {queue_size}, using minimum of 1")
            queue_size = 1

        old_queue_size = self.queue_size
        self.queue_size = queue_size
        logger.info(f"Queue size changed: {old_queue_size} -> {queue_size}")

    def apply_calibration(self, calibration_data: CalibrationData) -> None:
        """Apply calibration data to acquisition manager.

        This is the single entry point for setting calibration parameters.
        Replaces old pattern of setting 40+ individual attributes.

        Args:
            calibration_data: Immutable CalibrationData instance from calibration service.

        CRITICAL: This method must be called after successful calibration to enable
        live acquisition. It:
        1. Stores calibration_data reference (single source of truth)
        2. Computes derived data (Fourier weights, spectral correction)
        3. Sets calibrated=True to enable start_acquisition()

        All calibration parameters (integration times, LED intensities, spectra, etc.)
        are accessed via self.calibration_data.* throughout acquisition.

        """
        try:
            logger.info("=" * 80)
            logger.info("📊 APPLYING CALIBRATION DATA")
            logger.info("=" * 80)

            # Validate input
            if calibration_data is None:
                msg = "calibration_data cannot be None"
                raise ValueError(msg)

            # Validate calibration data integrity
            if not calibration_data.validate():
                msg = "Calibration data validation failed"
                raise ValueError(msg)

            # Store calibration data (single source of truth)
            self.calibration_data = calibration_data

            # DIAGNOSTIC: Log S-pol ref dictionary contents
            spol_channels = (
                list(calibration_data.s_pol_ref.keys()) if calibration_data.s_pol_ref else []
            )
            logger.info(f"  S-pol ref channels in calibration_data: {spol_channels}")
            for ch in spol_channels:
                ref = calibration_data.s_pol_ref[ch]
                logger.info(
                    f"    Ch {ch}: {'None' if ref is None else f'len={len(ref)}, type={type(ref).__name__}'}",
                )

            # Log key parameters
            logger.info(f"  Integration Time: {calibration_data.integration_time}ms")
            logger.info(f"  Scans per Spectrum: {calibration_data.num_scans}")
            logger.info(f"  Calibrated Channels: {calibration_data.get_channels()}")
            logger.info(
                f"  Wavelength Range: {calibration_data.wavelength_min:.1f}-{calibration_data.wavelength_max:.1f}nm",
            )
            logger.info(
                f"  SPR Range Indices: {calibration_data.wave_min_index}-{calibration_data.wave_max_index}",
            )

            # LED timing now controlled via Advanced Settings (LED_ON_TIME_MS, LED_OFF_TIME_MS)
            # These parameters are used in firmware RANKBATCH command and BATCH preset timing

            # Mark as calibrated (enables start_acquisition)
            self.calibrated = True

            logger.info("Calibration data applied successfully")
            logger.info("Acquisition manager ready for live measurements")
            logger.info("=" * 80)
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Failed to apply calibration data: {e}", exc_info=True)
            self.calibrated = False
            self.calibration_data = None
            raise

    # ========================================================================
    # DATA FLOW ARCHITECTURE
    # ========================================================================
    # ACQUISITION ONLY - NO PROCESSING
    #
    # DataAcquisitionManager:
    #   1. Receives CalibrationData from CalibrationService
    #   2. Acquires raw spectra from hardware
    #   3. Emits RAW spectrum data via spectrum_acquired signal
    #
    # Processing Component (separate, subscribes to spectrum_acquired):
    #   1. Receives raw spectrum data
    #   2. Performs dark subtraction, transmission calculation, peak finding
    #   3. Emits processed results to UI
    #
    # Calibration handled by CalibrationService → apply_calibration()
    # ========================================================================

    def start_acquisition(self) -> None:
        """Start continuous spectrum acquisition (non-blocking)."""
        try:
            logger.info("🎯 start_acquisition called")

            if not self.calibrated:
                self.acquisition_error.emit("Calibrate before starting acquisition")
                return

            # ✨ CRITICAL: Validate calibration data before starting acquisition
            if not self.calibration_data:
                logger.error(
                    "❌ FATAL: calibration_data is None - cannot start acquisition",
                )
                self.acquisition_error.emit(
                    "Calibration data missing. Please recalibrate.",
                )
                return

            if not self.calibration_data.s_pol_ref or len(self.calibration_data.s_pol_ref) == 0:
                logger.error(
                    "❌ FATAL: S-pol reference spectra are empty - cannot start acquisition",
                )
                self.acquisition_error.emit(
                    "S-pol reference data missing. Please recalibrate.",
                )
                return

            if (
                self.calibration_data.wavelengths is None
                or len(self.calibration_data.wavelengths) == 0
            ):
                logger.error(
                    "❌ FATAL: wavelength data is empty - cannot start acquisition",
                )
                self.acquisition_error.emit(
                    "Wavelength calibration missing. Please recalibrate.",
                )
                return

            # Validate S-pol reference shapes match wavelength data
            invalid_channels = []
            for ch, ref_spectrum in self.calibration_data.s_pol_ref.items():
                if ref_spectrum is None or len(ref_spectrum) != len(
                    self.calibration_data.wavelengths,
                ):
                    invalid_channels.append(ch)
                    logger.error(
                        f"❌ Channel {ch}: Invalid s_pol_ref (len={len(ref_spectrum) if ref_spectrum is not None else 'None'} vs wave={len(self.calibration_data.wavelengths)})",
                    )

            if invalid_channels:
                logger.error(
                    f"❌ FATAL: Invalid calibration data for channels: {invalid_channels}",
                )
                self.acquisition_error.emit(
                    f"Calibration corrupted for channels {invalid_channels}. Please recalibrate.",
                )
                return

            if self._acquiring:
                self.acquisition_started.emit()
                return

            logger.info("=" * 80)
            logger.info("🚀 STARTING ACQUISITION")
            logger.info(f"Integration: {self.calibration_data.integration_time}ms")
            logger.info(f"Scans per spectrum: {self.calibration_data.num_scans}")
            logger.info("=" * 80)

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
                    ctrl.set_mode("p")
                    try:
                        import settings

                        settle_ms = getattr(settings, "POLARIZER_SETTLE_MS", 400)
                    except Exception:
                        settle_ms = 400
                    time.sleep(max(0, float(settle_ms)) / 1000.0)
                    logger.info("✅ Polarizer → P-mode")
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer: {e}")

            # ✨ FIRMWARE DETECTION: Check acquisition capabilities
            try:
                ctrl = self.hardware_mgr.ctrl

                # Check for batch command support (DEFAULT - all firmware)
                self._batch_supported = hasattr(
                    ctrl,
                    "set_batch_intensities",
                ) and callable(ctrl.set_batch_intensities)

                # Check for rankbatch/CYCLE_SYNC support (OPTIONAL - V2.4+)
                self._firmware_supports_rank = hasattr(
                    ctrl,
                    "led_rank_sequence",
                ) and callable(ctrl.led_rank_sequence)

                # Acquisition mode selection (can be configured via settings)
                try:
                    use_rankbatch = getattr(root_settings, "USE_RANKBATCH_MODE", False)
                except Exception:
                    use_rankbatch = False

                self._rank_mode_enabled = self._firmware_supports_rank and use_rankbatch

                if self._rank_mode_enabled:
                    logger.info("� Mode: RANKBATCH (V2.4+ firmware)")
                elif self._batch_supported:
                    logger.info("📦 Mode: BATCH (standard)")
                else:
                    logger.info("📦 Mode: SEQUENTIAL (fallback)")

            except Exception as e:
                logger.warning(f"⚠️ Failed to detect firmware capabilities: {e}")
                self._firmware_supports_rank = False
                self._rank_mode_enabled = False
                self._batch_supported = False

            # Reset timing instrumentation
            if self._enable_timing_instrumentation:
                self._timing_data = {
                    "led_command_times": [],
                    "led_to_read_delays": [],
                    "detector_read_times": [],
                    "total_cycle_times": [],
                    "acquisition_count": 0,
                }
                logger.info(
                    f"📊 Timing instrumentation enabled - will log every {self._timing_log_interval} acquisitions",
                )

            # Defer thread start to event loop to ensure all UI updates
            # from calibration completion have finished on main thread.
            self._acquiring = True
            self._stop_acquisition.clear()
            self._pause_acquisition.clear()
            self._stop_processing.clear()

            # Diagnostic: verify calibration data is present
            logger.info(
                f"[ACQ] Starting acquisition with: wave_data={'present' if self.calibration_data and self.calibration_data.wavelengths is not None else 'MISSING'}, s_pol_ref={'present' if self.calibration_data and self.calibration_data.s_pol_ref else 'MISSING'}",
            )

            def _launch_worker() -> None:
                try:
                    logger.info("=" * 80)
                    logger.info("🎬 _launch_worker() CALLBACK FIRED")
                    logger.info("=" * 80)

                    if not self._acquiring or self._stop_acquisition.is_set():
                        logger.warning(
                            "[DAQ] Acquisition canceled before worker launch",
                        )
                        logger.warning(
                            f"  _acquiring={self._acquiring}, _stop_acquisition={self._stop_acquisition.is_set()}",
                        )
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
                    logger.info(
                        f"   Thread alive: {self._acquisition_thread.is_alive()}",
                    )
                    logger.info(f"   Thread name: {self._acquisition_thread.name}")
                    logger.info("=" * 80)
                except Exception as e:
                    logger.error(f"❌ CRASH in _launch_worker: {e}", exc_info=True)
                    with contextlib.suppress(builtins.BaseException):
                        pass

            logger.info("📅 Scheduling worker launch in 50ms...")
            logger.info(f"   Current thread: {threading.current_thread().name}")
            logger.info(f"   _acquiring flag: {self._acquiring}")
            logger.info("   QTimer.singleShot will call _launch_worker in 50ms")
            QTimer.singleShot(
                50,
                _launch_worker,
            )  # Small delay for UI thread to finish calibration updates
            logger.info(
                "✅ start_acquisition completed successfully - worker will start in 50ms",
            )
            # Reset one-time applied-parameters summary flag for this run
            self._run_params_logged = False
        except Exception as e:
            logger.error(f"❌ CRASH in start_acquisition: {e}", exc_info=True)
            with contextlib.suppress(builtins.BaseException):
                pass

    def stop_acquisition(self) -> None:
        """Stop spectrum acquisition and flush remaining batches."""
        if not self._acquiring:
            logger.debug("stop_acquisition called but not acquiring")
            return

        logger.info("Stopping spectrum acquisition...")

        # Signal threads to stop
        self._stop_acquisition.set()

        # V2.2: Send firmware stop command FIRST to halt rankbatch timer
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and ctrl._ser and ctrl._ser.is_open:
                # Send stop command to halt hardware timer sequencer
                ctrl._ser.write(b"stop\n")
                time.sleep(
                    0.05,
                )  # Wait for firmware to halt timer and send BATCH_STOPPED

                # Flush any pending firmware responses
                if ctrl._ser.in_waiting > 0:
                    response = ctrl._ser.read(ctrl._ser.in_waiting)
                    if b"BATCH_STOPPED" in response:
                        logger.info("✅ Firmware rankbatch timer stopped")
        except Exception as e:
            logger.debug(f"Firmware stop command failed (non-critical): {e}")

        # Emergency shutdown all LEDs (V1.1+ firmware)
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, "emergency_shutdown"):
                ctrl.emergency_shutdown()
                logger.info("✅ Emergency shutdown - all LEDs off")

            # Unlock servo control (P4SPR safeguard)
            if ctrl:
                ctrl._acquisition_blocked = False
                logger.info("🔓 Servo control UNLOCKED")
        except Exception as e:
            logger.debug(
                f"Emergency shutdown or servo unlock failed (non-critical): {e}",
            )

        # Wait for acquisition thread to finish (with timeout)
        if self._acquisition_thread and self._acquisition_thread.is_alive():
            logger.debug("Waiting for acquisition thread to stop...")
            self._acquisition_thread.join(timeout=3.0)
            if self._acquisition_thread.is_alive():
                logger.warning("⚠️ Acquisition thread did not stop within timeout")
            else:
                logger.info("✅ Acquisition thread stopped cleanly")

        self._acquisition_thread = None

        self.acquisition_stopped.emit()

    def pause_acquisition(self) -> None:
        """Pause spectrum acquisition without stopping the thread."""
        if not self._acquiring:
            return

        logger.info("⏸ Acquisition paused")
        self._pause_acquisition.set()  # Set flag to pause

    def resume_acquisition(self) -> None:
        """Resume spectrum acquisition after pause."""
        if not self._acquiring:
            return

        logger.info("▶️ Acquisition resumed")
        self._pause_acquisition.clear()

    # ========================================================================
    # LAYER 2: COORDINATOR (_acquisition_worker)
    # ========================================================================
    # Orchestrates the acquisition loop:
    #   1. Pre-arm integration time (once before loop)
    #   2. Loop through channels
    #   3. Call Layer 3 (_acquire_raw_spectrum) for hardware acquisition
    #   4. Process immediately (inline processing)
    #   5. Emit results directly to UI
    # ========================================================================

    def _acquisition_worker(self) -> None:
        """LAYER 2: Main acquisition coordinator (background thread).

        Coordinates acquisition flow:
        1. Pre-arm detector (set integration time once)
        2. Loop through channels calling _acquire_raw_spectrum (Layer 3)
        3. Emit RAW spectrum data via spectrum_acquired signal
        4. Processing happens elsewhere (separate component subscribes to signal)

        Optimizations:
        - Pre-arm integration time (saves 21ms per cycle)
        - Batch LED commands (15x faster)
        - LED overlap strategy (saves 40ms per transition)

        NO PROCESSING - Pure acquisition and emission.
        """
        try:
            channels = ["a", "b", "c", "d"]
            consecutive_errors = 0
            max_consecutive_errors = 5
            cycle_count = 0

            # ===================================================================
            # SMART PARAMETER ANALYSIS: Detect what's common across channels
            # ===================================================================
            # Integration time analysis (consistent naming with calibration)
            p_integration_time_effective = self.calibration_data.p_integration_time
            if not p_integration_time_effective or p_integration_time_effective <= 0:
                p_integration_time_effective = self.calibration_data.s_mode_integration_time

            # Check if we have per-channel integration times (alternative mode)
            has_per_channel_integration_times = bool(
                self.calibration_data.channel_integration_times,
            )

            # Allow settings override for integration behavior
            try:
                import settings

                mode = getattr(settings, "INTEGRATION_MODE", "auto")
            except Exception:
                mode = "auto"

            if mode == "fixed":
                has_per_channel_integration_times = False
            elif mode == "per_channel":
                has_per_channel_integration_times = True

            if has_per_channel_integration_times:
                logger.info("[PRE-ARM] Disabled: Using per-channel integration times")
            else:
                # Standard mode: Pre-arm integration time ONCE (optimization)
                try:
                    usb = self.hardware_mgr.usb
                    if usb:
                        result = usb.set_integration(
                            p_integration_time_effective
                        )  # API expects milliseconds
                        if result:
                            logger.info(
                                f"[PRE-ARM] ✓ Integration time pre-armed: {p_integration_time_effective:.1f}ms",
                            )
                            logger.info(
                                "[PRE-ARM] Optimization active: Skipping set_integration() in acquisition loop (saves ~7ms/channel)",
                            )
                        else:
                            logger.warning(
                                f"[PRE-ARM] ✗ Failed to pre-arm integration time: {p_integration_time_effective:.1f}ms",
                            )
                    else:
                        logger.warning(
                            "[PRE-ARM] ✗ Spectrometer not available for pre-arm",
                        )
                except Exception as e:
                    logger.error(f"[PRE-ARM] ✗ Exception during pre-arm: {e}")
                    import traceback

                    traceback.print_exc()

            # Common parameters (same for all channels)
            # Cap num_scans to 10 maximum (match reference capture quality)
            num_scans = (
                self.calibration_data.num_scans
                if self.calibration_data.num_scans and self.calibration_data.num_scans > 0
                else 1
            )
            MAX_LIVE_SCANS = 10  # Match calibration reference quality
            num_scans = min(num_scans, MAX_LIVE_SCANS) if num_scans else MAX_LIVE_SCANS

            # TIMING TRACK MODE: Override calibration delays with new timing architecture
            # LED Track: OFF 55ms → ON 260ms (total 315ms per channel)
            # Detector Track: Wait 100ms → Detect 210ms (total 310ms per channel)
            import settings as root_settings

            use_timing_tracks = True  # New architecture enabled

            if use_timing_tracks:
                # ALL timing derived from base parameters in settings
                led_on_total_ms = root_settings.LED_ON_TIME_MS
                detector_wait_ms = root_settings.DETECTOR_WAIT_MS  # Max integration per scan
                safety_buffer_ms = root_settings.SAFETY_BUFFER_MS

                # Calculate derived timing
                detector_on_time_ms = led_on_total_ms - detector_wait_ms
                detector_window_ms = detector_on_time_ms - safety_buffer_ms

                # CRITICAL: Enforce integration time cap BEFORE calculating num_scans
                # DETECTOR_WAIT_MS = MAX INTEGRATION TIME PER SCAN
                # Formula: DETECTOR_ON_TIME = LED_ON_TIME_MS - DETECTOR_WAIT_MS
                #          DETECTOR_WINDOW = DETECTOR_ON_TIME - SAFETY_BUFFER_MS
                #          integration_time ≤ DETECTOR_WAIT_MS (per-scan cap)
                #          num_scans = floor(DETECTOR_WINDOW / integration_time)
                max_integration_per_scan_ms = detector_wait_ms

                if p_integration_time_effective > max_integration_per_scan_ms:
                    logger.warning(
                        f"⚠️ Integration time ({p_integration_time_effective:.1f}ms) exceeds "
                        f"max per-scan limit ({max_integration_per_scan_ms:.1f}ms) - capping to prevent timing issues"
                    )
                    p_integration_time_effective = max_integration_per_scan_ms

                # Calculate maximum scans that fit in detection window
                max_scans_in_window = int(
                    detector_window_ms / p_integration_time_effective,
                )

                # Apply window constraint
                if num_scans > max_scans_in_window:
                    num_scans = max_scans_in_window if max_scans_in_window > 0 else 1

                # Map timing to delay parameters for _acquire_raw_spectrum
                # PRE delay = detector wait time (LED stabilization)
                # POST delay = remaining LED ON time after detector finishes
                pre_led_delay = detector_wait_ms

                # Calculate actual detection time needed
                actual_detection_ms = num_scans * p_integration_time_effective
                post_led_delay = led_on_total_ms - detector_wait_ms - actual_detection_ms

                # CRITICAL: POST delay can't be negative
                post_led_delay = max(post_led_delay, 0)

            else:
                # Legacy mode: Not used (timing tracks always enabled)
                # LED timing controlled via LED_ON_TIME_MS and LED_OFF_TIME_MS
                pre_led_delay = detector_wait_ms  # Detector wait time
                post_led_delay = 0  # No post delay in modern architecture

            # =============================================================================
            # TIMING ALIGNMENT REMOVED FROM MAIN LOOP
            # =============================================================================
            # Timing alignment now runs in background after calibration completes.
            # See: _start_background_timing_alignment(), called from apply_calibration()
            # This allows user to start live data immediately without waiting ~10 seconds.
            # =============================================================================

            # One-time applied parameter summary (concise)
            if not self._run_params_logged:
                try:
                    try:
                        wl = self.calibration_data.wavelengths
                        if wl is not None and len(wl) > 0:
                            pass
                    except Exception:
                        pass
                finally:
                    self._run_params_logged = True

            while not self._stop_acquisition.is_set():
                cycle_count += 1

                # Manual GC every 100 cycles (during safe time, not critical path)
                if cycle_count % 100 == 0:
                    gc.collect(generation=0)

                # Manual GC every 100 cycles
                if cycle_count % 100 == 0:
                    gc.collect(generation=0)

                try:
                    # Check if paused
                    if self._pause_acquisition.is_set():
                        time.sleep(0.1)
                        continue

                    batch_success = False
                    spectra_acquired = 0

                    # Overnight mode: Add delay before starting cycle
                    try:
                        import settings as root_settings

                        if getattr(root_settings, "OVERNIGHT_MODE", False):
                            delay_s = getattr(root_settings, "OVERNIGHT_DELAY_SECONDS", 15.0)
                            # Only delay after first cycle to avoid initial startup delay
                            if cycle_count > 1:
                                time.sleep(delay_s)
                    except Exception:
                        pass  # Continue normal acquisition if settings unavailable

                    # Start cycle timing (detector window to detector window)
                    cycle_start = (
                        time.perf_counter() if self._enable_timing_instrumentation else None
                    )

                    # ========================================================================
                    # ACQUISITION METHOD 1: RANKBATCH (CYCLE_SYNC) - FIRMWARE SYNC
                    # ========================================================================
                    # FIRMWARE-CONTROLLED timing: Hardware timer handles LED sequencing
                    # Only enabled if firmware supports it AND configured in settings
                    if self._rank_mode_enabled:
                        try:
                            # Build LED intensity dict for rank
                            led_intensities = {}
                            for ch in channels:
                                led_int = self.calibration_data.p_mode_intensities.get(
                                    ch,
                                )
                                if led_int is not None:
                                    led_intensities[ch] = led_int

                            # Fallback: if P-mode intensities missing or all zero, use available defaults
                            if (not led_intensities) or all(
                                (led_intensities.get(ch, 0) or 0) == 0 for ch in channels
                            ):
                                try:
                                    # Try S-mode first
                                    s_ints = (
                                        getattr(
                                            self.calibration_data,
                                            "s_mode_intensities",
                                            {},
                                        )
                                        or {}
                                    )
                                    if s_ints and any(
                                        (s_ints.get(ch, 0) or 0) > 0 for ch in channels
                                    ):
                                        led_intensities = {ch: s_ints.get(ch, 0) for ch in channels}
                                        logger.warning(
                                            "[RANK] P-mode intensities missing/zero; using S-mode intensities as fallback",
                                        )
                                    else:
                                        # Use generic intensities or a safe default
                                        generic_ints = (
                                            getattr(
                                                self.calibration_data,
                                                "led_intensities",
                                                {},
                                            )
                                            or {}
                                        )
                                        if generic_ints and any(
                                            (generic_ints.get(ch, 0) or 0) > 0 for ch in channels
                                        ):
                                            led_intensities = {
                                                ch: generic_ints.get(ch, 128) for ch in channels
                                            }
                                            logger.warning(
                                                "[RANK] P-mode intensities missing/zero; using generic LED intensities fallback",
                                            )
                                        else:
                                            led_intensities = {ch: 128 for ch in channels}
                                            logger.warning(
                                                "[RANK] No calibrated intensities available; using default 128 for rank preset",
                                            )
                                except Exception:
                                    led_intensities = {ch: 128 for ch in channels}
                                    logger.warning(
                                        "[RANK] Fallback to default 128 intensities due to exception",
                                    )

                            # Build per-channel integration times if available
                            per_channel_integration = None
                            if has_per_channel_integration_times:
                                per_channel_integration = {}
                                for ch in channels:
                                    ch_int_time = (
                                        self.calibration_data.channel_integration_times.get(
                                            ch,
                                            p_integration_time_effective,
                                        )
                                    )
                                    per_channel_integration[ch] = ch_int_time

                            # === RANKBATCH ACQUISITION (EVENT-DRIVEN) ===
                            # V2.4+ firmware - ONE CYCLE_START event per cycle
                            # - Firmware-controlled LED timing
                            # - Software reads at calculated offsets
                            # - Lowest USB traffic (1 event per cycle)
                            channel_spectra = self._acquire_all_channels_rankbatch(
                                channels=channels,
                                led_intensities=led_intensities,
                                integration_time_ms=p_integration_time_effective,
                                per_channel_integration=per_channel_integration,
                            )

                            # RAW EMISSION: Spectra are emitted as raw data
                            # (see _emit_raw_spectrum called inside _acquire_all_channels_rankbatch)
                            # Processing happens in separate component that subscribes to spectrum_acquired
                            spectra_acquired += len(channel_spectra)
                            batch_success = True

                        except Exception as rank_err:
                            logger.error(
                                f"[RANKBATCH] Failed, falling back to batch/sequential: {rank_err}",
                            )
                            # Fall through to batch or sequential acquisition

                    # ========================================================================
                    # ACQUISITION METHOD 2: BATCH PRESET (DEFAULT) - SOFTWARE SYNC
                    # ========================================================================
                    # SOFTWARE-CONTROLLED timing: Python code handles all sequencing
                    # Use set_batch_intensities() to preset all 4 LEDs, then sequence manually
                    # This is the standard production method - reliable and predictable
                    if not self._rank_mode_enabled and self._batch_supported:
                        try:
                            # Build LED intensity dict
                            led_intensities = {}
                            for ch in channels:
                                led_int = self.calibration_data.p_mode_intensities.get(
                                    ch,
                                )
                                if led_int is not None:
                                    led_intensities[ch] = led_int

                            # Acquire all channels using batch preset
                            channel_spectra = self._acquire_all_channels_batch(
                                channels=channels,
                                led_intensities=led_intensities,
                                integration_time_ms=p_integration_time_effective,
                                num_scans=num_scans,
                            )

                            # Emit raw spectra (no processing)
                            for ch in channels:
                                raw_spectrum = channel_spectra.get(ch)
                                if raw_spectrum is not None:
                                    led_time_ms = (
                                        (time.perf_counter() - cycle_start) * 1000
                                        if cycle_start
                                        else None
                                    )
                                    self._emit_raw_spectrum(
                                        ch,
                                        raw_spectrum,
                                        led_intensities,
                                    )
                                    spectra_acquired += 1
                                    batch_success = True

                            # Log batch timing every 10 cycles
                            if cycle_start and cycle_count % 10 == 1:
                                total_batch_time = (time.perf_counter() - cycle_start) * 1000
                                logger.info(
                                    f"[BATCH-TIMING] Cycle {cycle_count}: Total batch time = {total_batch_time:.1f}ms "
                                    f"({len(channels)} channels × 250ms target = 1000ms)"
                                )

                            # Skip sequential fallback
                            continue

                        except Exception as batch_err:
                            logger.error(
                                f"[BATCH] Failed, falling back to sequential: {batch_err}",
                            )
                            # Fall through to sequential acquisition

                    # ========================================================================
                    # ACQUISITION METHOD 3: SEQUENTIAL (FALLBACK)
                    # ========================================================================
                    # One LED at a time - compatible with all firmware versions
                    # Process each channel in cycle
                    for idx, ch in enumerate(channels):
                        try:
                            if self._stop_acquisition.is_set():
                                break

                            # Determine next channel for LED overlap optimization
                            next_ch = channels[idx + 1] if idx + 1 < len(channels) else None

                            # Get LED intensity for this channel
                            led_intensity = self.calibration_data.p_mode_intensities.get(ch)
                            if led_intensity is None:
                                continue

                            # Get LED intensity for next channel (for overlap optimization)
                            next_led_int = None
                            if next_ch:
                                next_led_int = self.calibration_data.p_mode_intensities.get(
                                    next_ch,
                                )

                            # SMART: Get integration time (per-channel if available, else common)
                            ch_integration_time = p_integration_time_effective
                            if has_per_channel_integration_times:
                                ch_integration_time = (
                                    self.calibration_data.channel_integration_times.get(
                                        ch,
                                        p_integration_time_effective,
                                    )
                                )

                            # Fixed cadence timing (optional)
                            import settings as root_settings

                            fixed_cycle_ms = None
                            if getattr(root_settings, "ENABLE_FIXED_CADENCE", False):
                                fixed_cycle_ms = getattr(
                                    root_settings,
                                    "FIXED_CYCLE_TIME_MS",
                                    None,
                                )

                            # LAYER 3: Smart acquire - auto-detects if pre-arm optimization is possible
                            raw_spectrum = self._acquire_raw_spectrum(
                                channel=ch,
                                led_intensity=led_intensity,
                                integration_time_ms=ch_integration_time,
                                num_scans=num_scans,
                                pre_led_delay_ms=pre_led_delay,
                                post_led_delay_ms=post_led_delay,
                                next_channel=next_ch,
                                next_led_intensity=next_led_int,
                                pre_armed=not has_per_channel_integration_times,  # Optimization flag
                                fixed_cycle_time_ms=fixed_cycle_ms,
                            )


                                self._emit_raw_spectrum(ch, raw_spectrum, led_intensities)

                                batch_success = True
                                spectra_acquired += 1

                                # Clear channel error count on success
                                channel_error_counts[ch] = 0

                            else:
                                # Acquisition failed for this channel
                                channel_error_counts[ch] += 1

                                # Disable channel if too many consecutive errors
                                if channel_error_counts[ch] >= 20:
                                    channel_disabled[ch] = True

                        except Exception as e:
                            channel_error_counts[ch] += 1

                            # Check for connection errors
                            import serial

                            if isinstance(
                                e,
                                (serial.SerialException, ConnectionError, OSError),
                            ):
                                # Trigger connection recovery after this cycle
                                consecutive_errors = (
                                    max_consecutive_errors - 1
                                )  # Will trigger recovery

                    # Measure complete batch cycle time (detector window to detector window)
                    if self._enable_timing_instrumentation and cycle_start is not None:
                        cycle_time_ms = (time.perf_counter() - cycle_start) * 1000
                        self._timing_data["total_cycle_times"].append(cycle_time_ms)
                        self._timing_data["acquisition_count"] += 1

                    if cycle_count % 10 == 1:
                        pass

                    # Reset error counter if successful
                    if batch_success:
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1

                        # Stop after too many failures
                        if consecutive_errors >= max_consecutive_errors:
                            with contextlib.suppress(queue.Full):
                                self._emission_queue.put_nowait(
                                    {
                                        "_error": "Acquisition failed - check hardware and timing",
                                    },
                                )
                            self._stop_acquisition.set()
                            break

                    # Intelligent delay between cycles:
                    # - If we're getting valid data: minimal 1ms delay (fast acquisition)
                    # - If we got nothing this cycle: 50ms delay to prevent CPU thrashing
                    if batch_success or spectra_acquired > 0:
                        time.sleep(0.001)  # Fast mode: got data
                    else:
                        time.sleep(0.05)  # Throttle mode: no data, prevent CPU spike

                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        with contextlib.suppress(queue.Full):
                            self._emission_queue.put_nowait(
                                {"_error": f"Too many errors: {e}"},
                            )
                        self._stop_acquisition.set()
                        break
                    time.sleep(0.5)

        except Exception as e:
            # Top-level exception handler - catch ANY uncaught exception
            import traceback

            error_msg = f"FATAL: Acquisition worker crashed: {e}\n{traceback.format_exc()}"
            with contextlib.suppress(builtins.BaseException):
                self._emission_queue.put_nowait({"_error": error_msg})

    def _check_hardware(self) -> bool:
        """Check if required hardware is connected."""
        return self.hardware_mgr.ctrl is not None and self.hardware_mgr.usb is not None

    # ========================================================================
    # LAYER 3: HARDWARE ACQUISITION (Pure Hardware Control)
    # ========================================================================
    # This layer matches calibration_6step.py hardware pattern exactly:
    #   1. Set LED intensity (batch command)
    #   2. LED ON period (LED_ON_TIME_MS from Advanced Settings, default 250ms)
    #   3. Read spectrum from detector during LED ON window
    #   4. LED OFF period (LED_OFF_TIME_MS from Advanced Settings, default 0ms)
    #   5. Turn off LED (or auto-transition to next LED)
    # Returns RAW spectrum with NO processing (dark subtraction in Layer 4)
    # ========================================================================

    def _emit_raw_spectrum(self, channel: str, raw_spectrum, led_intensities: dict):
        """Emit raw spectrum data - no processing, acquisition only.

        This is the ONLY output from DataAcquisitionManager.
        Processing happens in a separate component that subscribes to this signal.
        Peak wavelength/intensity added by pipeline processing, NOT here.
        """
        try:
            # Get channel-specific timestamp (captured immediately after detector read)
            if hasattr(self, "_channel_timestamps") and channel in self._channel_timestamps:
                channel_timestamp = self._channel_timestamps[channel]
            else:
                channel_timestamp = time.time()  # Fallback if timestamp not captured

            # Package RAW spectrum data with all context needed for processing
            # NO PLACEHOLDERS - peak comes from pipeline or crashes
            spectrum_data = {
                "channel": channel,
                "raw_spectrum": raw_spectrum,
                "wavelengths": self.calibration_data.wavelengths,  # Array for plotting (plural!)
                # wavelength and intensity added by pipeline processing
                "intensity": 0,  # Raw intensity (will be calculated from spectrum if needed)
                "timestamp": channel_timestamp,  # Channel-specific acquisition time
                "integration_time": self.calibration_data.integration_time,
                "num_scans": self.calibration_data.num_scans,
                "led_intensity": led_intensities.get(channel, 0),
                # Calibration data reference for processing component
                "s_pol_ref": self.calibration_data.s_pol_ref.get(channel),
                "dark_s": self.calibration_data.dark_s.get(
                    channel,
                ),  # S-pol dark reference
                "wave_min_index": self.calibration_data.wave_min_index,
                "wave_max_index": self.calibration_data.wave_max_index,
            }

            # Emit RAW data - processing happens elsewhere
            self.spectrum_acquired.emit(spectrum_data)

        except Exception as e:
            logger.error(f"[EMIT] Failed to emit raw spectrum for {channel}: {e}")

    def _acquire_all_channels_batch(
        self,
        channels: list,
        led_intensities: dict,
        integration_time_ms: float,
        num_scans: int,
    ) -> dict:
        """Acquire all channels using batch preset + SOFTWARE synchronization (DEFAULT method).

        BATCH MODE (Standard Production):
        - Uses set_batch_intensities() to preset all 4 LEDs once
        - SOFTWARE-CONTROLLED timing: Python code sequences channels
        - Manual sequencing: turn on → software delay → read → turn off
        - Same pattern as LEDconverge (reliable, predictable)
        - Compatible with all firmware versions that support batch command

        Timing Flow:
          Setup:    set_batch_intensities(a=X, b=Y, c=Z, d=W)

          LED A:    turn_on('a') → read spectrum (250ms cycle) → auto-off when next LED turns on
          LED B:    turn_on('b') → read spectrum (250ms cycle) → auto-off when next LED turns on
          LED C:    turn_on('c') → read spectrum (250ms cycle) → auto-off when next LED turns on
          LED D:    turn_on('d') → read spectrum (250ms cycle) → manual turn_off_all at end

        Args:
            channels: List of channels to acquire ['a', 'b', 'c', 'd']
            led_intensities: Dict of LED intensities {ch: intensity}
            integration_time_ms: Integration time (ms)
            num_scans: Number of scans to average

        Returns:
            dict: {channel: raw_spectrum_array} for all channels

        """
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                logger.error("[BATCH] Hardware not available")
                return {}

            # CRITICAL: Ensure integration time is set (verify pre-arm or set now)
            # If pre-arm failed, this will catch it before reading spectra
            try:
                usb.set_integration(integration_time_ms)  # API expects milliseconds
                # logger.debug removed - fires every batch, causes terminal lag
            except (ConnectionError, OSError) as conn_e:
                logger.error(
                    f"[BATCH] USB disconnected while setting integration time: {conn_e}",
                )
                self._acquiring = False
                if self.hardware_mgr:
                    self.hardware_mgr.hardware_disconnected.emit()
                raise
            except Exception as e:
                logger.error(f"[BATCH] Failed to set integration time: {e}")
                return {}

            # ========================================================================
            # LED CONTROL (Intensities already set post-calibration)
            # ========================================================================
            # LED intensities are set once after calibration and don't change
            # during the run. Just cycle LEDs with turn_on_channel()
            # ========================================================================

            # Get LED ON timing from settings (respects Advanced Settings)
            import settings as root_settings

            led_on_time_ms = getattr(root_settings, "LED_ON_TIME_MS", 240.0)
            detector_wait_ms = getattr(root_settings, "DETECTOR_WAIT_MS", 45.0)

            # Acquire each channel sequentially
            channel_spectra = {}

            for ch in channels:
                try:
                    # Track LED on time for enforcement
                    led_on_start = time.perf_counter()

                    # Turn on LED (intensity already set, just switches channel)
                    turn_on_start = time.perf_counter()
                    ctrl.turn_on_channel(ch=ch)
                    turn_on_time = (time.perf_counter() - turn_on_start) * 1000

                    # Wait for LED to stabilize before reading
                    time.sleep(detector_wait_ms / 1000.0)

                    # Acquire spectrum while LED is on
                    # CRITICAL FIX: Send scans 1-by-1 instead of batch to avoid blocking
                    # Calling read_roi with num_scans=8 blocks for ~1+ second
                    # Instead, call it 8 times with num_scans=1 and average ourselves

                    # DIAGNOSTIC: Log details (first cycle only)
                    if not hasattr(self, "_num_scans_logged"):
                        logger.info(f"[BATCH] num_scans={num_scans} (sent 1-by-1, not batched)")
                        logger.info(
                            f"[BATCH] ROI: {self.calibration_data.wave_min_index} to {self.calibration_data.wave_max_index}"
                        )
                        logger.info(f"[BATCH] usb type: {type(usb).__name__}")
                        logger.info(f"[BATCH] usb has read_roi: {hasattr(usb, 'read_roi')}")
                        self._num_scans_logged = True

                    # Send scans one-by-one and average
                    read_start = time.perf_counter()
                    if num_scans == 1:
                        raw_spectrum = usb.read_roi(
                            self.calibration_data.wave_min_index,
                            self.calibration_data.wave_max_index,
                            num_scans=1,
                        )
                    else:
                        # Multiple scans: send individually and average
                        import numpy as np

                        spectrum_length = (
                            self.calibration_data.wave_max_index
                            - self.calibration_data.wave_min_index
                        )
                        stack = np.zeros(spectrum_length, dtype=np.float64)
                        for i in range(num_scans):
                            scan = usb.read_roi(
                                self.calibration_data.wave_min_index,
                                self.calibration_data.wave_max_index,
                                num_scans=1,  # Always send 1 at a time
                            )
                            if scan is not None:
                                stack += scan
                            else:
                                logger.warning(
                                    f"[BATCH] Scan {i+1}/{num_scans} for channel {ch} returned None"
                                )
                        raw_spectrum = (stack / num_scans).astype(np.uint32)
                    read_time = (time.perf_counter() - read_start) * 1000

                    # Log channel timing (first cycle only)
                    if not hasattr(self, "_channel_timing_logged"):
                        logger.info(
                            f"[BATCH-CH-{ch.upper()}] turn_on={turn_on_time:.1f}ms, wait={detector_wait_ms:.1f}ms, read={read_time:.1f}ms"
                        )
                        if ch == channels[-1]:  # Last channel
                            self._channel_timing_logged = True

                    # Capture timestamp immediately after detector read for this specific channel
                    channel_timestamp = time.time()

                    # ENFORCEMENT: Wait remaining time to ensure LED stays on for full duration
                    elapsed_since_led_on = (time.perf_counter() - led_on_start) * 1000  # ms
                    remaining_time_ms = max(0, led_on_time_ms - elapsed_since_led_on)
                    if remaining_time_ms > 0:
                        time.sleep(remaining_time_ms / 1000.0)

                    # DEBUG: Log what read_roi returned (first time only)
                    if not hasattr(self, "_read_roi_logged"):
                        logger.info(
                            f"[BATCH DEBUG] Ch {ch}: raw_spectrum type={type(raw_spectrum)}, len={len(raw_spectrum) if raw_spectrum is not None else 'None'}"
                        )
                        if raw_spectrum is not None and len(raw_spectrum) > 0:
                            logger.info(
                                f"[BATCH DEBUG] First 5 values: {raw_spectrum[:5]}, max={max(raw_spectrum):.0f}"
                            )
                        self._read_roi_logged = True

                    if raw_spectrum is not None and len(raw_spectrum) > 0:
                        # Ensure spectrum length matches calibrated wavelength array length
                        if len(raw_spectrum) != len(self.calibration_data.wavelengths):
                            raw_spectrum = raw_spectrum[: len(self.calibration_data.wavelengths)]

                        channel_spectra[ch] = raw_spectrum
                        # Store timestamp for this channel
                        if not hasattr(self, "_channel_timestamps"):
                            self._channel_timestamps = {}
                        self._channel_timestamps[ch] = channel_timestamp
                        # logger.debug removed - fires every channel every cycle
                    else:
                        # Throttle empty spectrum warnings to avoid log spam
                        if not hasattr(self, "_empty_batch_count"):
                            self._empty_batch_count = {}
                        self._empty_batch_count[ch] = self._empty_batch_count.get(ch, 0) + 1
                        if self._empty_batch_count[ch] <= 3:  # Only log first 3
                            logger.warning(
                                f"[BATCH] Ch {ch}: Empty spectrum (returned: {raw_spectrum})"
                            )
                        elif self._empty_batch_count[ch] == 4:
                            logger.warning(
                                f"[BATCH] Ch {ch}: Empty spectrum (suppressing further warnings)"
                            )

                except (ConnectionError, OSError) as conn_e:
                    logger.error(f"[BATCH] Ch {ch} connection lost: {conn_e}")
                    logger.error(
                        "CRITICAL: Detector disconnected during batch acquisition",
                    )
                    ctrl.turn_off_channels()  # Clean up LEDs
                    self._acquiring = False  # Stop acquisition loop
                    if self.hardware_mgr:
                        self.hardware_mgr.hardware_disconnected.emit()
                    raise  # Propagate to stop acquisition

                except Exception as e:
                    logger.error(f"[BATCH] Ch {ch} failed: {e}")

            # Don't turn off LEDs - controller auto-disables previous LED when next turns on
            # Final LED stays on briefly but gets turned off at start of next cycle

            return channel_spectra

        except (ConnectionError, OSError):
            # Re-raise USB disconnection errors
            raise
        except Exception as e:
            logger.error(f"[BATCH] Acquisition failed: {e}")
            return {}

    def _acquire_all_channels_rankbatch(
        self,
        channels: list,
        led_intensities: dict,
        integration_time_ms: float,
        per_channel_integration: dict = None,
    ) -> dict:
        """Acquire all channels using RANKBATCH with FIRMWARE synchronization (CYCLE_SYNC).

        RANKBATCH MODE (V2.4+ Firmware):
        - FIRMWARE-CONTROLLED timing: Hardware timer sequences LEDs automatically
        - Firmware sends ONE CYCLE_START event per cycle (75% less USB traffic)
        - Software reads at calculated offsets from CYCLE_START
        - Deterministic timing, lowest USB overhead
        - Watchdog on separate Timer 1 (zero impact on LED timing)

        Timing Flow (250ms LED ON, 0ms LED OFF):
          t=0ms:    CYCLE_START event, LED_A ON
          t=60ms:   Python reads LED_A spectrum
          t=250ms:  LED_B ON (automatic)
          t=310ms:  Python reads LED_B spectrum
          t=500ms:  LED_C ON (automatic)
          t=560ms:  Python reads LED_C spectrum
          t=750ms:  LED_D ON (automatic)
          t=810ms:  Python reads LED_D spectrum
          t=1000ms: Next CYCLE_START event

        Args:
            channels: List of channels to acquire ['a', 'b', 'c', 'd']
            led_intensities: Dict of LED intensities per channel {ch: intensity}
            integration_time_ms: Global integration time (ms)
            per_channel_integration: Optional per-channel integration times

        Returns:
            dict: {channel: raw_spectrum_array} for one complete cycle

        """
        import time

        # Constants
        LED_ON_TIME_MS = 250  # Firmware RANKBATCH LED ON duration
        LED_OFF_TIME_MS = 0  # Firmware RANKBATCH LED OFF duration
        RANKBATCH_CYCLES = 3600  # ~1 hour of continuous operation

        # LED timing in firmware (LED turns on at these offsets from CYCLE_START)
        FIRMWARE_LED_OFFSETS = {"a": 0.000, "b": 0.250, "c": 0.500, "d": 0.750}

        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                logger.error("[CYCLE-SYNC] Hardware not available")
                return {}

            # Get detector wait time (software delay after LED turns on)
            detector_wait_ms = getattr(self, "detector_wait_ms", 60)
            detector_wait_s = detector_wait_ms / 1000.0

            # Calculate read timing: firmware LED offset + detector wait
            led_read_offsets = {ch: FIRMWARE_LED_OFFSETS[ch] + detector_wait_s for ch in channels}

            # === INITIALIZATION: Start firmware rankbatch command ===
            if not self._rankbatch_running:
                rankbatch_cmd = (
                    f"rankbatch:{led_intensities.get('a', 0)},"
                    f"{led_intensities.get('b', 0)},"
                    f"{led_intensities.get('c', 0)},"
                    f"{led_intensities.get('d', 0)},"
                    f"{LED_ON_TIME_MS},{LED_OFF_TIME_MS},{RANKBATCH_CYCLES}\n"
                )

                ctrl._ser.write(rankbatch_cmd.encode())
                logger.info(f"[CYCLE-SYNC] Rankbatch started: {rankbatch_cmd.strip()}")
                self._rankbatch_running = True

                # Initialize watchdog
                if ENABLE_WATCHDOG:
                    self._last_keepalive = time.time()
                    logger.info(
                        f"[WATCHDOG] Enabled ({WATCHDOG_KEEPALIVE_INTERVAL}s interval)",
                    )

            # === MAIN LOOP: Wait for CYCLE_START, acquire channels, return ===
            channel_spectra = {}

            while not self._stop_acquisition.is_set():
                # Check for CYCLE_START event
                if ctrl._ser.in_waiting > 0:
                    line = ctrl._ser.readline().decode("utf-8", errors="ignore").strip()

                    if line.startswith("CYCLE_START:"):
                        cycle_num = int(line.split(":")[1])
                        cycle_start_time = time.time()
                        logger.debug(
                            f"[CYCLE-SYNC] CYCLE_START:{cycle_num} at t={cycle_start_time:.3f}",
                        )

                        # Send watchdog keepalive (after CYCLE_START to avoid blocking)
                        if (
                            ENABLE_WATCHDOG
                            and (time.time() - self._last_keepalive) >= WATCHDOG_KEEPALIVE_INTERVAL
                        ):
                            ctrl._ser.write(b"ka\n")
                            self._last_keepalive = time.time()
                            # logger.debug removed - fires frequently, causes terminal lag

                        # Acquire each channel at its scheduled time
                        for ch in channels:
                            if self._stop_acquisition.is_set():
                                break

                            # Wait until LED read time
                            target_time = cycle_start_time + led_read_offsets[ch]
                            time_to_wait = target_time - time.time()
                            if time_to_wait > 0:
                                time.sleep(time_to_wait)

                            # Set integration time
                            ch_int_time = (
                                per_channel_integration.get(ch, integration_time_ms)
                                if per_channel_integration
                                else integration_time_ms
                            )
                            usb.set_integration(ch_int_time)  # API expects milliseconds

                            # Read spectrum using HAL interface
                            spectrum = usb.read_roi(
                                self.calibration_data.wave_min_index,
                                self.calibration_data.wave_max_index,
                                num_scans=num_scans,
                            )

                            # Validate spectrum
                            if spectrum is None or len(spectrum) == 0:
                                logger.warning(
                                    f"[CYCLE-SYNC] Ch {ch}: Empty spectrum, skipping",
                                )
                                continue
                            if np.max(spectrum) == 0:
                                logger.warning(
                                    f"[CYCLE-SYNC] Ch {ch}: Zero spectrum, skipping",
                                )
                                continue

                            # logger.debug removed - fires every channel every cycle, causes VS Code lag

                            # Store and emit raw spectrum
                            channel_spectra[ch] = spectrum
                            self._emit_raw_spectrum(ch, spectrum, led_intensities)

                        # Cycle complete - return to acquisition worker
                        # logger.debug removed - fires every cycle, causes terminal lag
                        return channel_spectra

                    if line == "BATCH_COMPLETE":
                        logger.info("[CYCLE-SYNC] Firmware batch complete")
                        self._rankbatch_running = False
                        return channel_spectra

                time.sleep(0.001)  # Avoid busy-wait

            # Stopped - reset state
            self._rankbatch_running = False
            return channel_spectra

        except Exception as e:
            import traceback

            logger.error(f"[CYCLE-SYNC] Failed: {e}")
            logger.error(f"[CYCLE-SYNC] Traceback: {traceback.format_exc()}")
            return {}

    # _acquire_all_channels_via_rank REMOVED - Unused EVENT_RANK fallback
    # Production uses CYCLE_SYNC method only (_acquire_all_channels_cycle_sync)
    # EVENT_RANK was kept for debugging but is no longer needed

    def _acquire_raw_spectrum(
        self,
        channel: str,
        led_intensity: int,
        integration_time_ms: float,
        num_scans: int,
        pre_led_delay_ms: float,
        post_led_delay_ms: float,
        next_channel: str | None = None,
        next_led_intensity: int | None = None,
        pre_armed: bool = False,
        fixed_cycle_time_ms: float | None = None,
    ) -> np.ndarray | None:
        """LAYER 3: Acquire raw spectrum from detector (hardware only, no processing).

        SMART ACQUISITION with AUTO-OPTIMIZATION:
        - Automatically detects when all channels share the same integration time
        - Uses pre-arm optimization (skip set_integration) when possible
        - Falls back to per-channel integration time setting when needed
        - Coordinator analyzes calibration data and sets 'pre_armed' flag

        MODE-AGNOSTIC DESIGN:
        All parameters are passed explicitly to support different calibration modes
        (standard and alternative) with potentially different:
        - Integration times (per-mode or per-channel)
        - Number of scans (averaging strategy)
        - LED timing delays (device-specific or mode-specific)

        This function matches the calibration hardware pattern exactly:
        - Set LED intensity using batch command
        - Wait for LED stabilization (pre_led_delay_ms)
        - Read spectrum from detector (num_scans averaging)
        - Wait for afterglow decay (post_led_delay_ms)
        - Optional: LED overlap optimization

        Args:
            channel: Channel to acquire ('a', 'b', 'c', or 'd')
            led_intensity: LED intensity value (0-255)
            integration_time_ms: Integration time in milliseconds (mode-specific)
            num_scans: Number of scans to average (mode-specific)
            pre_led_delay_ms: LED stabilization delay in ms (device/mode-specific)
            post_led_delay_ms: Afterglow decay delay in ms (device/mode-specific)
            next_channel: Next channel for LED overlap optimization
            next_led_intensity: LED intensity for next channel (for overlap)
            pre_armed: True if integration time was pre-armed (optimization)

        Returns:
            Raw spectrum as numpy array (no processing), or None if error

        Note: This is a pure hardware function - no dark subtraction,
        no processing. All processing happens in Layer 4.

        """
        # Keep future-compat parameters without changing callers
        _ = (next_channel, next_led_intensity, fixed_cycle_time_ms)
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                return None

            # ===================================================================
            # STEP 0: Set Integration Time (SMART: Skip if pre-armed)
            # ===================================================================
            # Integration time is passed as parameter to support mode-agnostic operation
            # Different modes may use different integration times:
            # - Standard mode: P-mode integration time (same for all channels) → PRE-ARMED
            # - Alternative mode: Per-channel integration times → SET EACH TIME
            # - Legacy fast-track removed
            if not pre_armed:
                # Per-channel mode: Set integration time each time
                try:
                    usb.set_integration(integration_time_ms)  # API expects milliseconds
                except (ConnectionError, OSError) as conn_e:
                    logger.error(
                        f"Connection lost while setting integration time: {conn_e}",
                    )
                    logger.error(
                        "CRITICAL: Spectrometer disconnected - stopping acquisition",
                    )
                    self._acquiring = False  # Stop acquisition loop
                    if self.hardware_mgr:
                        self.hardware_mgr.hardware_disconnected.emit()
                    return None
                except Exception as e:
                    logger.error(f"Failed to set integration time: {e}")
                    return None
            # Integration time already pre-armed (optimization - saves ~7ms)
            # Log only first occurrence to avoid spam
            elif not hasattr(self, "_prearm_skip_logged"):
                self._prearm_skip_logged = True
                logger.debug(
                    f"[PRE-ARM] Skipping set_integration() - using pre-armed {integration_time_ms:.1f}ms",
                )

            # Start cycle timer for fixed-cadence timing
            cycle_start_time = time.perf_counter()

            # Initialize timing variables (no LED OFF phase needed - batch command handles it)
            led_command_time_ms = 0.0
            led_settle_time_ms = 0.0
            detector_read_time_ms = 0.0

            # Get timing parameters from settings
            import settings as root_settings

            LED_ON_PERIOD_MS = root_settings.LED_ON_TIME_MS
            DETECTOR_WAIT_BEFORE_MS = root_settings.DETECTOR_WAIT_MS

            # =============================================================================
            # LED TRACK: Turn on target LED (automatically turns off others via batch command)
            # =============================================================================
            # The batch command sets all 4 LEDs atomically, so setting others to 0
            # automatically turns them off. No separate LED OFF phase needed!
            # =============================================================================
            led_command_start = time.perf_counter() if self._enable_timing_instrumentation else None

            led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
            led_values[channel] = led_intensity

            # LED command (logging disabled for performance - saves ~40ms)
            led_on_time = None
            try:
                success = ctrl.set_batch_intensities(
                    a=led_values["a"],
                    b=led_values["b"],
                    c=led_values["c"],
                    d=led_values["d"],
                )

                led_on_time = time.perf_counter()

                if not success:
                    logger.warning(
                        f"Failed to set LED intensities for channel {channel}",
                    )
                    return None

            except (ConnectionError, OSError) as conn_e:
                logger.error(f"Connection lost while setting LED: {conn_e}")
                logger.error("CRITICAL: Controller disconnected - stopping acquisition")
                self._acquiring = False  # Stop acquisition loop
                if self.hardware_mgr:
                    self.hardware_mgr.hardware_disconnected.emit()
                return None
            except Exception as e:
                logger.error(f"Failed to set LED intensities: {e}")
                return None

            # Log LED command timing
            if self._enable_timing_instrumentation and led_command_start:
                led_command_time_ms = (time.perf_counter() - led_command_start) * 1000
                self._timing_data["led_command_times"].append(led_command_time_ms)

            # =============================================================================
            # DETECTOR TRACK - STEP 1: Wait for LED stabilization
            # =============================================================================
            # Detector waits while LED stabilizes (35ms)
            led_settle_start = time.perf_counter()
            time.sleep(DETECTOR_WAIT_BEFORE_MS / 1000.0)
            led_settle_time_ms = (time.perf_counter() - led_settle_start) * 1000

            # =============================================================================
            # DETECTOR TRACK - STEP 2: Detection window (spectrum acquisition)
            # =============================================================================
            # Detector reads spectrum during 210ms window
            detector_window_start = time.perf_counter()

            # Log LED-to-Read delay (synchronization tracking)
            if self._enable_timing_instrumentation and led_on_time:
                led_to_read_delay_ms = (detector_window_start - led_on_time) * 1000
                self._timing_data["led_to_read_delays"].append(led_to_read_delay_ms)

            # Collect num_scans during the 210ms detection window using HAL interface
            try:
                # Use read_roi with built-in averaging (HAL architecture)
                raw_spectrum = usb.read_roi(
                    self.calibration_data.wave_min_index,
                    self.calibration_data.wave_max_index,
                    num_scans=num_scans,
                )

                if raw_spectrum is None:
                    logger.error(
                        f"[CH-{channel}] Failed to acquire spectrum with {num_scans} scans",
                    )
                    return None

            except (ConnectionError, OSError) as conn_e:
                logger.error(
                    f"[CH-{channel}] Connection lost while reading spectrum: {conn_e}",
                )
                logger.error(
                    f"[CH-{channel}] CRITICAL: Spectrometer disconnected - stopping acquisition",
                )
                self._acquiring = False  # Stop acquisition loop immediately
                if self.hardware_mgr:
                    self.hardware_mgr.hardware_disconnected.emit()
                return None
            except Exception as e:
                logger.error(f"[CH-{channel}] Failed to read spectrum: {e}")
                import traceback

                logger.error(f"[CH-{channel}] Traceback: {traceback.format_exc()}")
                return None

            # Log detector window timing
            detector_read_time_ms = (time.perf_counter() - detector_window_start) * 1000
            if self._enable_timing_instrumentation:
                self._timing_data["detector_read_times"].append(detector_read_time_ms)

            # Validate spectrum (guard against empty/zero reads); retry once if needed
            try:
                if raw_spectrum is None or np.count_nonzero(raw_spectrum) == 0:
                    # Brief wait then one retry using HAL interface (single scan for speed)
                    time.sleep(0.005)
                    retry_spectrum = usb.read_roi(
                        self.calibration_data.wave_min_index,
                        self.calibration_data.wave_max_index,
                        num_scans=1,  # Single scan retry for fast recovery
                    )
                    if retry_spectrum is None or np.count_nonzero(retry_spectrum) == 0:
                        logger.warning(
                            f"Empty/zero spectrum on channel {channel} (drop)",
                        )
                        return None
                    raw_spectrum = retry_spectrum
            except Exception:
                return None

            # Track timing jitter for SNR analysis
            if led_on_time is not None:
                led_to_detector_ms = (detector_window_start - led_on_time) * 1000.0
                jitter_stats = self._timing_jitter_stats[channel]
                jitter_stats.append(led_to_detector_ms)
                if len(jitter_stats) > self._jitter_window_size:
                    jitter_stats.pop(0)

            # Trim spectrum to calibrated wavelength range
            if len(raw_spectrum) != len(self.calibration_data.wavelengths):
                # DEBUG: Log ROI cropping on first spectrum
                if not hasattr(self, "_roi_crop_logged"):
                    (self.calibration_data.wave_max_index - self.calibration_data.wave_min_index)

                if self.calibration_data.wave_min_index and self.calibration_data.wave_max_index:
                    raw_spectrum = raw_spectrum[
                        self.calibration_data.wave_min_index : self.calibration_data.wave_max_index
                    ]

                    if not hasattr(self, "_roi_crop_logged"):
                        if len(raw_spectrum) == len(self.calibration_data.wavelengths):
                            pass
                        else:
                            pass
                        self._roi_crop_logged = True
                else:
                    raw_spectrum = raw_spectrum[: len(self.calibration_data.wavelengths)]
                    if not hasattr(self, "_roi_crop_logged"):
                        self._roi_crop_logged = True

            # =============================================================================
            # LED TRACK - STEP 3: LED stays ON for remaining period
            # =============================================================================
            # LED remains ON for rest of 245ms period while detector completes
            # Detector finishes at 35ms + 210ms = 245ms total
            # LED stays ON until end of period (245ms), then OFF at next cycle
            elapsed_since_led_on = (time.perf_counter() - led_on_time) * 1000 if led_on_time else 0
            remaining_led_on_ms = max(0, LED_ON_PERIOD_MS - elapsed_since_led_on)

            if remaining_led_on_ms > 0:
                time.sleep(remaining_led_on_ms / 1000.0)

            # Note: LED will be turned OFF at start of next channel cycle (LED_OFF_PERIOD_MS)
            # This completes the 250ms cycle: 5ms OFF + 245ms ON = 250ms per channel

            # Calculate total cycle time and log detailed breakdown
            total_cycle_ms = (time.perf_counter() - cycle_start_time) * 1000

            # Log timing breakdown every 10 cycles to identify bottlenecks
            if not hasattr(self, "_timing_log_counter"):
                self._timing_log_counter = {}
            if channel not in self._timing_log_counter:
                self._timing_log_counter[channel] = 0

            self._timing_log_counter[channel] += 1
            if self._timing_log_counter[channel] % 10 == 1:  # Log first and every 10th
                logger.info(
                    f"[TIMING-CH-{channel.upper()}] Cycle breakdown:\n"
                    f"  LED command:        {led_command_time_ms:6.1f}ms (batch command turns off prev LED)\n"
                    f"  LED settle wait:    {led_settle_time_ms:6.1f}ms\n"
                    f"  Detector read:      {detector_read_time_ms:6.1f}ms\n"
                    f"  Remaining LED ON:   {remaining_led_on_ms:6.1f}ms\n"
                    f"  ─────────────────────────────\n"
                    f"  TOTAL CYCLE:        {total_cycle_ms:6.1f}ms (target: 250ms)",
                )

            # ===================================================================
            # Return RAW spectrum (NO processing - matches calibration pattern)
            # ===================================================================
            return raw_spectrum

        except Exception as e:
            logger.error(f"Error in _acquire_raw_spectrum for channel {channel}: {e}")
            return None

    # _apply_baseline_correction REMOVED - unused visualization correction

    def set_led_delays(self, pre_delay_ms: float, post_delay_ms: float) -> None:
        """Set PRE and POST LED delays for spectrum acquisition.

        Args:
            pre_delay_ms: Settling time after LED on before measurement (0-200ms)
            post_delay_ms: Dark time after LED off for afterglow decay (0-100ms)

        """
        self._pre_led_delay_ms = max(0.0, min(200.0, pre_delay_ms))
        self._post_led_delay_ms = max(0.0, min(100.0, post_delay_ms))
        logger.info(
            f"LED delays updated: PRE={self._pre_led_delay_ms:.1f}ms, POST={self._post_led_delay_ms:.1f}ms",
        )

    # ========================================================================
    # PROCESSING METHODS - DELEGATED TO PROCESSING MODULE
    # ========================================================================
    # All spectrum processing functionality has been moved to:
    #   affilabs/processing/spectrum_processor.py
    #
    # This includes dark subtraction, transmission calculation, peak finding,
    # and signal intelligence. DataAcquisitionManager now focuses purely on
    # hardware control and raw data collection.
    # ========================================================================

    def clear_buffers(self) -> None:
        """Clear all data buffers."""
        for ch in ["a", "b", "c", "d"]:
            self.channel_buffers[ch].clear()
            self.time_buffers[ch].clear()
        logger.info("Data buffers cleared")

    # _compute_spectral_correction REMOVED - deprecated spectral correction

    # _load_afterglow_correction REMOVED - afterglow correction no longer used
