"""Data Acquisition Manager - Handles spectrum acquisition and processing.

ARCHITECTURE OVERVIEW (Matches Calibration Exactly):
====================================================

This module follows the same 4-layer architecture as calibration_6step.py:"""

from __future__ import annotations

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

import gc
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from affilabs.core.spectrum_preprocessor import SpectrumPreprocessor
from affilabs.core.transmission_processor import TransmissionProcessor

# Phase 1.1 Domain Model (replacing legacy CalibrationData type alias)
from affilabs.domain import CalibrationData
from affilabs.utils.logger import logger

# ============================================================================
# SHARED PROCESSING ALIASES (Same processors used in calibration & live)
# ============================================================================
# These processors are used identically in both calibration_6step.py and
# data_acquisition_manager.py to ensure consistent results:
#
# DarkSubtractor = SpectrumPreprocessor
#   - Removes dark noise from raw spectra
#   - Called: process_polarization_data(raw_spectrum, dark_noise, ...)
#
# TransmissionCalculator = TransmissionProcessor
#   - Calculates P/S transmission ratio with LED correction
#   - Called: process_single_channel(p_pol_clean, s_pol_ref, led_s, led_p, ...)
#
# Both use IDENTICAL parameters:
#   - baseline_method='percentile', baseline_percentile=95.0
#   - apply_sg_filter=True
# ============================================================================
DarkSubtractor = SpectrumPreprocessor
TransmissionCalculator = TransmissionProcessor

# ✅ OPTIMIZATION: Disable automatic GC to eliminate random 10-50ms pauses
# Manual GC will be called periodically during safe times
gc.disable()
import builtins
import contextlib
import queue
import time

import numpy as np

# System Intelligence integration (DISABLED - will be refined later)
try:
    from core.system_intelligence import get_system_intelligence

    SYSTEM_INTELLIGENCE_AVAILABLE = False  # Disabled for now
except ImportError:
    SYSTEM_INTELLIGENCE_AVAILABLE = False
    # logger.warning("System Intelligence not available - operating without ML guidance")


class DataAcquisitionManager(QObject):
    """Manages spectrum acquisition and processing.

    Note: Calibration is handled by CalibrationService.
    DataAcquisitionManager only handles live spectrum acquisition after calibration.
    """

    # Signals for data updates
    spectrum_acquired = Signal(
        dict,
    )  # {channel: str, wavelength: float, intensity: float, timestamp: float}
    # CALIBRATION SIGNALS REMOVED - handled by CalibrationManager
    # calibration_started = Signal()
    # calibration_complete = Signal(dict)
    # calibration_failed = Signal(str)
    # calibration_progress = Signal(str)
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
        self.calibration_data = (
            None  # CalibrationData instance (set by apply_calibration)
        )

        # Derived/computed data (not part of calibration)
        self.fourier_weights = {}  # {channel: weights_array} - computed from calibration
        self.spectral_correction = {}  # {channel: correction_weights} - computed

        # Runtime state (acquisition-specific, not calibration)
        self.ch_error_list = []  # Failed channels from calibration

        # LED timing (from device config, can override calibration_data)
        self._pre_led_delay_ms = (
            None  # PRE LED delay (device-specific, loaded from config)
        )
        self._post_led_delay_ms = (
            None  # POST LED delay (device-specific, loaded from config)
        )
        self._led_overlap_active = (
            False  # Track if LED is already ON from previous overlap
        )
        self._led_overlap_channel = None  # Track which LED is ON from overlap
        self._led_overlap_start_time = None  # Track when overlap LED was turned ON

        # Timing jitter tracking for SNR optimization
        self._timing_jitter_stats = {ch: [] for ch in ["a", "b", "c", "d"]}
        self._jitter_window_size = 100  # Track last 100 measurements per channel
        self._last_jitter_report = 0  # Time of last jitter statistics report

        # Firmware V2.0+ rank sequence support
        self._firmware_supports_rank = False  # Detected at runtime
        self._rank_mode_enabled = False  # Set to True when firmware V2.0+ detected

        # Data loss tracking and monitoring
        self._dropped_acquisition = 0  # Spectra dropped at acquisition (queue full)
        self._dropped_processing = 0  # Spectra dropped during processing (errors)
        self._dropped_emission = 0  # Spectra dropped at emission (queue full)
        self._empty_transmission_count = 0  # Transmission arrays that came back empty
        self._last_drop_report = time.time()

        # S/P orientation validation tracking
        self._sp_validation_results = {}  # {channel: {orientation_correct, confidence, peak_wl, timestamp}}
        self._sp_orientation_validated = (
            set()
        )  # Set of channels validated during runtime

        # FWHM tracking for quality control
        self._fwhm_values = {}  # {channel: fwhm_nm}
        self._last_peak_wavelength = {}  # {channel: wavelength_nm} for continuity checking

        # Queue mode acquisition (sequential A→B→C→D)
        import settings as root_settings

        QUEUE_SIZE = getattr(root_settings, "QUEUE_SIZE", 4)
        self.queue_size = QUEUE_SIZE  # Number of channels in sequential acquisition
        # STREAMLINED: Removed _spectrum_queue_internal and _queue_timestamps_internal (unused)

        # Load LED timing delays from device config (device-specific, persisted)
        self._load_led_delays_from_config()

        # STREAMLINED: No intermediate emission queue - emit directly from processing thread
        # QTimer no longer needed - Qt signals are thread-safe for cross-thread emission

        # ═══════════════════════════════════════════════════════════════════════
        # BATCHED PROCESSING PIPELINE (sequential mixed-channel batches)
        # ═══════════════════════════════════════════════════════════════════════
        # Each batch = 12 spectra in acquisition sequence (A-B-C-D x 3 cycles)
        # This maintains temporal ordering across all channels
        self._enable_batched_processing = getattr(
            root_settings, "ENABLE_BATCHED_PROCESSING", True,
        )
        # Low-latency defaults: process each spectrum immediately if settings missing
        PROCESSING_BATCH_SIZE = getattr(root_settings, "PROCESSING_BATCH_SIZE", 1)
        PROCESSING_BATCH_TIMEOUT_MS = getattr(
            root_settings, "PROCESSING_BATCH_TIMEOUT_MS", 20,
        )
        self._processing_batch_size = PROCESSING_BATCH_SIZE
        self._processing_batch_timeout_ms = PROCESSING_BATCH_TIMEOUT_MS

        # SEQUENTIAL batch buffer (all channels in order: A,B,C,D,A,B,C,D,...)
        self._sequential_batch_buffer = []  # Stores spectra in acquisition order
        self._last_batch_process_time = time.time()

        # Processing thread (background batch processor)
        self._processing_thread = None
        self._processing_queue = queue.Queue(maxsize=5000)  # Large buffer for raw data
        self._stop_processing = threading.Event()

        # STREAMLINED: Removed reorder buffer and spike filter - unnecessary complexity for production

        # Timing instrumentation for LED/detector synchronization analysis
        self._enable_timing_instrumentation = getattr(
            root_settings, "ENABLE_TIMING_INSTRUMENTATION", True,
        )
        TIMING_LOG_INTERVAL = getattr(root_settings, "TIMING_LOG_INTERVAL", 100)
        self._timing_log_interval = TIMING_LOG_INTERVAL
        self._timing_data = {
            "led_command_times": [],  # Time to send LED command
            "led_to_read_delays": [],  # Time from LED ON to detector read start
            "detector_read_times": [],  # Time for detector to return data
            "processing_times": [],  # Time to process spectrum
            "total_cycle_times": [],  # Total time per channel
            "acquisition_count": 0,
        }

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

        # Initialized silently

        # One-time run parameter summary flag (reset on each start)
        self._run_params_logged = False

    def _load_led_delays_from_config(self) -> None:
        """Load PRE/POST LED delays from device configuration.

        This is called during initialization to set initial defaults.
        These values will be overridden by apply_calibration() with the
        actual delays used during calibration (single source of truth).

        Falls back to hard-coded defaults (45ms/5ms) if config not available.

        Note: Uses silent loading to avoid verbose logging at startup.
        Device config summary will be logged when hardware is powered on.
        """
        try:
            from affilabs.utils.device_configuration import DeviceConfiguration

            device_serial = (
                getattr(self.hardware_mgr.usb, "serial_number", None)
                if self.hardware_mgr.usb
                else None
            )

            # Silent load - don't trigger verbose config summary at startup
            device_config = DeviceConfiguration(
                device_serial=device_serial, silent_load=True,
            )

            self._pre_led_delay_ms = device_config.get_pre_led_delay_ms()
            self._post_led_delay_ms = device_config.get_post_led_delay_ms()

            logger.debug(
                f"Loaded LED timing delays from device config: PRE={self._pre_led_delay_ms}ms, POST={self._post_led_delay_ms}ms",
            )
        except Exception:
            # Fall back to defaults if config loading fails
            self._pre_led_delay_ms = 45.0
            self._post_led_delay_ms = 5.0
            logger.debug("Using default LED delays: PRE=45ms, POST=5ms")

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
                list(calibration_data.s_pol_ref.keys())
                if calibration_data.s_pol_ref
                else []
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

            # Load Fourier weights from calibration data
            logger.info("Loading Fourier weights from calibration...")
            if (
                hasattr(calibration_data, "fourier_weights")
                and calibration_data.fourier_weights is not None
            ):
                self.fourier_weights = calibration_data.fourier_weights
                logger.info("Using pre-calculated Fourier weights from calibration")
            else:
                logger.warning(
                    "⚠️ No Fourier weights in calibration data, will calculate on-the-fly",
                )
                self.fourier_weights = None

            # Compute spectral correction weights (normalize LED profiles)
            self.spectral_correction = {}
            for ch in calibration_data.get_channels():
                ref_spectrum = calibration_data.s_pol_ref.get(ch)
                if ref_spectrum is not None:
                    try:
                        # Normalize to mean=1 for correction
                        spr_spectrum = ref_spectrum[
                            calibration_data.wave_min_index : calibration_data.wave_max_index
                        ]
                        mean_intensity = np.mean(spr_spectrum)
                        if mean_intensity > 0:
                            correction = spr_spectrum / mean_intensity
                            self.spectral_correction[ch] = correction
                        else:
                            logger.warning(
                                f"  Channel {ch}: Zero mean intensity, skipping correction",
                            )
                            self.spectral_correction[ch] = None
                    except Exception as e:
                        logger.warning(
                            f"  Channel {ch}: Failed to compute spectral correction: {e}",
                        )
                        self.spectral_correction[ch] = None

            # Update LED timing delays from calibration data (single source of truth)
            # These are the delays that were actually used during calibration
            self._pre_led_delay_ms = calibration_data.pre_led_delay_ms
            self._post_led_delay_ms = calibration_data.post_led_delay_ms
            logger.info(
                f"LED timing updated: PRE={self._pre_led_delay_ms}ms, POST={self._post_led_delay_ms}ms",
            )

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
    # LEGACY CALIBRATION REMOVED
    # ========================================================================
    # The start_calibration() and _calibration_worker() methods were removed
    # as they are now handled by CalibrationService.
    # Calibration now flows through: CalibrationService → apply_calibration()
    # CalibrationService emits CalibrationData which is applied via apply_calibration().
    #
    # TIMING ALIGNMENT MOVED TO CALIBRATION STEP 6
    # Timing alignment now runs as Step 6 during calibration (before Step 7: S-ref)
    # Results are stored in calibration_data.timing_sync for QC display.
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

            if (
                not self.calibration_data.s_pol_ref
                or len(self.calibration_data.s_pol_ref) == 0
            ):
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

            logger.info("✅ Calibration data validation passed")

            if self._acquiring:
                logger.warning("Acquisition already running")

                # Ensure batch processing worker is running (may not be started if QC warmup path didn't start it)
                if (
                    not self._processing_thread
                    or not self._processing_thread.is_alive()
                ):
                    logger.info(
                        "🔄 Starting batch processing worker (was not running)...",
                    )
                    self._stop_processing.clear()
                    self._processing_thread = threading.Thread(
                        target=self._batch_processing_worker,
                        daemon=True,
                        name="BatchProcessingWorker",
                    )
                    self._processing_thread.start()
                    logger.info("✅ Batch processing worker started")
                else:
                    logger.info("✅ Batch processing worker already running")

                # Just emit the started signal since acquisition is already running
                self.acquisition_started.emit()
                return

            logger.info("=" * 80)
            logger.info("🚀 STARTING LIVE ACQUISITION")
            logger.info("=" * 80)
            logger.info(
                f"Integration: {self.calibration_data.integration_time}ms × {self.calibration_data.num_scans} scans",
            )
            pre_led_delay = (
                self.calibration_data.pre_led_delay_ms
                if getattr(self.calibration_data, "pre_led_delay_ms", None)
                else self._pre_led_delay_ms
            )
            post_led_delay = (
                self.calibration_data.post_led_delay_ms
                if getattr(self.calibration_data, "post_led_delay_ms", None)
                else self._post_led_delay_ms
            )
            logger.info(f"LED Delays: PRE={pre_led_delay}ms, POST={post_led_delay}ms")
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
                    logger.info(
                        "🔄 Switching polarizer to P-mode for live measurements...",
                    )
                    ctrl.set_mode("p")
                    try:
                        # Use unified settle delay if available; fallback to 400ms
                        import settings

                        settle_ms = getattr(settings, "POLARIZER_SETTLE_MS", 400)
                    except Exception:
                        settle_ms = 400
                    time.sleep(max(0, float(settle_ms)) / 1000.0)
                    logger.info(
                        "✅ Polarizer in P-mode - using calibrated S-ref and dark",
                    )
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer: {e}")

            # ✨ FIRMWARE V2.0+ DETECTION: Check for rank sequence support
            try:
                ctrl = self.hardware_mgr.ctrl
                if ctrl and hasattr(ctrl, 'led_rank_sequence') and callable(ctrl.led_rank_sequence):
                    self._firmware_supports_rank = True
                    # ENABLED: Use RANKBATCH mode for live acquisition
                    self._rank_mode_enabled = True
                    logger.info("🔧 RANK mode ENABLED - using firmware-synchronized rankbatch command")
                    logger.info("   Firmware V2.0+ detected - using event-driven LED sequencing")
                else:
                    self._firmware_supports_rank = False
                    self._rank_mode_enabled = False
                    logger.info("📌 Firmware V1.9 or earlier - using sequential LED control")
            except Exception as e:
                logger.warning(f"⚠️ Failed to detect firmware version: {e}")
                self._firmware_supports_rank = False
                self._rank_mode_enabled = False

            # STREAMLINED: No intermediate queue buffers to clear

            # Clear sequential batch buffer
            self._sequential_batch_buffer.clear()
            self._last_batch_process_time = time.time()

            # Reset timing instrumentation
            if self._enable_timing_instrumentation:
                self._timing_data = {
                    "led_command_times": [],
                    "led_to_read_delays": [],
                    "detector_read_times": [],
                    "processing_times": [],
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

            # STREAMLINED: No batch processing worker needed - processing is inline
            # Batch worker thread has been removed - processing happens in acquisition thread
            logger.info(
                "✅ STREAMLINED: Inline processing mode (no batch worker thread)",
            )

            # Start queue processing timer (runs in main thread)
            logger.info("Starting queue processing timer...")
            # STREAMLINED: No queue timer needed - direct emission from processing thread
            # self._queue_timer.start(10)  # REMOVED - Qt signals are thread-safe

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
                50, _launch_worker,
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

        # Stop queue processing timer
        # STREAMLINED: No queue timer to stop
        # if self._queue_timer:
        #     self._queue_timer.stop()

        # Signal threads to stop
        self._stop_acquisition.set()
        self._stop_processing.set()
        self._acquiring = False

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
            logger.debug(f"Emergency shutdown or servo unlock failed (non-critical): {e}")

        # Flush batch processing queue (send shutdown signal)
        if self._processing_thread:
            try:
                self._processing_queue.put(
                    "SHUTDOWN", timeout=0.5,
                )  # Shutdown signal (string to avoid None confusion)
            except:
                pass

        # Wait for batch processing thread to stop
        if self._processing_thread and self._processing_thread.is_alive():
            logger.debug("Waiting for batch processing thread to stop...")
            self._processing_thread.join(timeout=2.0)
            if self._processing_thread.is_alive():
                logger.warning("⚠️ Batch processing thread did not stop within timeout")
            else:
                logger.info("✅ Batch processing thread stopped cleanly")
        self._processing_thread = None

        # Process remaining queue items
        self._process_spectrum_queue()

        # Wait for acquisition thread to finish (with timeout)
        if self._acquisition_thread and self._acquisition_thread.is_alive():
            logger.debug("Waiting for acquisition thread to stop...")
            self._acquisition_thread.join(timeout=3.0)
            if self._acquisition_thread.is_alive():
                logger.warning("⚠️ Acquisition thread did not stop within timeout")
            else:
                logger.info("✅ Acquisition thread stopped cleanly")

        self._acquisition_thread = None

        # Log timing statistics if instrumentation enabled
        if (
            self._enable_timing_instrumentation
            and self._timing_data["acquisition_count"] > 0
        ):
            self._log_timing_statistics()

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
        self._pause_acquisition.clear()  # Clear flag to resume

    # STREAMLINED: _process_spectrum_queue() REMOVED - No longer needed
    # Emission now happens directly from processing thread via Qt signals (thread-safe)

    # STREAMLINED: Spike filter REMOVED - Unnecessary complexity for production

    # ========================================================================
    # BATCH PROCESSING WORKER (background thread for vectorized processing)
    # ========================================================================

    # STREAMLINED: _batch_processing_worker() REMOVED - Processing now done inline in acquisition thread
    # No more separate processing thread, queue, or batching - direct processing for minimal latency

    def _batch_processing_worker(self) -> None:
        """DEPRECATED: Batch processing worker removed - now using inline processing.

        This method is kept for backward compatibility but does nothing.
        Processing now happens directly in _acquisition_worker for minimal latency.
        """
        return  # Exit immediately - not needed anymore

        batch_count = 0

        try:
            while not self._stop_processing.is_set():
                try:
                    # Get raw spectrum from queue (short timeout for immediate processing)
                    try:
                        raw_data = self._processing_queue.get(
                            timeout=0.001,
                        )  # 1ms - process immediately!

                        if raw_data == "SHUTDOWN":  # Shutdown signal
                            break

                        # Add to SEQUENTIAL batch buffer (maintains order)
                        self._sequential_batch_buffer.append(raw_data)

                    except queue.Empty:
                        # No new data, but check if we should process buffered data due to timeout
                        if len(self._sequential_batch_buffer) == 0:
                            continue  # Nothing to process

                    # Check if batch is ready (size or timeout)
                    buffer_size = len(self._sequential_batch_buffer)
                    time_since_last = (
                        time.time() - self._last_batch_process_time
                    ) * 1000

                    should_process = buffer_size >= self._processing_batch_size or (
                        buffer_size > 0
                        and time_since_last >= self._processing_batch_timeout_ms
                    )

                    # Debug: Log buffer status only for first few or if accumulating
                    if not hasattr(self, "_batch_log_count"):
                        self._batch_log_count = 0
                    if self._batch_log_count < 5 or buffer_size > 4:
                        self._batch_log_count += 1

                    if not should_process:
                        continue

                    # Process batch
                    batch_start = time.perf_counter()
                    batch_data = self._sequential_batch_buffer
                    self._sequential_batch_buffer = []  # Clear buffer
                    self._last_batch_process_time = time.time()

                    # Process all spectra in sequential order
                    processed_results = []
                    for item in batch_data:
                        channel = item["channel"]
                        try:
                            processed = self._process_spectrum(
                                channel, item["spectrum_data"],
                            )
                            if processed:
                                # Validate processed data before adding to results
                                trans = processed.get("transmission_spectrum")
                                raw = processed.get("raw_spectrum")

                                # Check for empty or invalid arrays
                                if (
                                    trans is None
                                    or (hasattr(trans, "__len__") and len(trans) == 0)
                                    or (
                                        hasattr(trans, "__len__")
                                        and np.count_nonzero(trans) == 0
                                    )
                                ):
                                    self._empty_transmission_count += 1

                                processed_results.append(
                                    {
                                        "channel": channel,
                                        "wavelength": processed["wavelength"],
                                        "intensity": processed["intensity"],
                                        "raw_spectrum": raw,
                                        "transmission_spectrum": trans,
                                        "wavelengths": self.calibration_data.wavelengths,
                                        "timestamp": item["timestamp"],
                                        "is_preview": False,
                                        "batch_processed": True,
                                        "integration_time": self.calibration_data.integration_time,
                                        "num_scans": self.calibration_data.num_scans,
                                        "led_intensity": self.calibration_data.p_mode_intensities.get(
                                            channel, 0,
                                        ),
                                    },
                                )
                            else:
                                # Processing returned None - count as drop
                                self._dropped_processing += 1
                        except Exception:
                            self._dropped_processing += 1
                            import traceback

                            traceback.print_exc()
                            continue

                    (time.perf_counter() - batch_start) * 1000

                    # STREAMLINED: Emit directly to Qt signal (thread-safe, no intermediate queue)
                    for result in processed_results:
                        try:
                            self.spectrum_acquired.emit(result)
                        except Exception:
                            self._dropped_emission += 1
                            ch = result.get("channel", "?")

                    batch_count += 1
                    # Log batch processing results and data loss stats
                    if batch_count <= 3 or batch_count % 20 == 0:
                        channel_dist = {}
                        for r in processed_results:
                            ch = r.get("channel", "unknown")
                            channel_dist[ch] = channel_dist.get(ch, 0) + 1

                        # Report data loss every 20 batches
                        if batch_count % 20 == 0:
                            total_drops = (
                                self._dropped_acquisition
                                + self._dropped_processing
                                + self._dropped_emission
                            )
                            if total_drops > 0:
                                pass

                except Exception:
                    import traceback

                    traceback.print_exc()
                    continue

        finally:
            pass

    def _log_timing_statistics(self) -> None:
        """Log timing statistics for LED/detector synchronization analysis."""
        if len(self._timing_data["led_command_times"]) > 0:
            pass

        if len(self._timing_data["led_to_read_delays"]) > 0:
            pass

        if len(self._timing_data["detector_read_times"]) > 0:
            pass

        if len(self._timing_data["processing_times"]) > 0:
            pass

        if len(self._timing_data["total_cycle_times"]) > 0:
            pass

    # ========================================================================
    # LAYER 2: COORDINATOR (_acquisition_worker)
    # ========================================================================
    # Orchestrates the acquisition loop:
    #   1. Pre-arm integration time (once before loop)
    #   2. Loop through channels
    #   3. Call Layer 3 (_acquire_raw_spectrum) for hardware acquisition
    #   4. Queue raw data for batch processing OR process immediately
    #   5. Batched results queued for UI (Layer 1)
    # ========================================================================

    def _acquisition_worker(self) -> None:
        """LAYER 2: Main acquisition coordinator (background thread).

        Coordinates acquisition flow:
        1. Pre-arm detector (set integration time once)
        2. Loop through channels calling _acquire_raw_spectrum (Layer 3)
        3. Queue raw data for batch processing (if enabled) OR process immediately
        4. Batch processor handles processing in background (vectorized)
        5. Results queued for UI update (throttled)

        Optimizations:
        - Pre-arm integration time (saves 21ms per cycle)
        - Batch LED commands (15x faster)
        - LED overlap strategy (saves 40ms per transition)
        """
        try:
            channels = ["a", "b", "c", "d"]
            consecutive_errors = 0
            max_consecutive_errors = 5
            cycle_count = 0

            # Connection resilience tracking
            channel_error_counts = {"a": 0, "b": 0, "c": 0, "d": 0}
            channel_disabled = {"a": False, "b": False, "c": False, "d": False}

            # Pre-flight check

            # Prepare LED intensities for batch command
            self.calibration_data.p_mode_intensities.get("a", 0)
            self.calibration_data.p_mode_intensities.get("b", 0)
            self.calibration_data.p_mode_intensities.get("c", 0)
            self.calibration_data.p_mode_intensities.get("d", 0)

            # ===================================================================
            # SMART PARAMETER ANALYSIS: Detect what's common across channels
            # ===================================================================
            # Integration time analysis (consistent naming with calibration)
            p_integration_time_effective = self.calibration_data.p_integration_time
            if not p_integration_time_effective or p_integration_time_effective <= 0:
                p_integration_time_effective = (
                    self.calibration_data.s_mode_integration_time
                )

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
            else:
                pass

            if has_per_channel_integration_times:
                logger.info("[PRE-ARM] Disabled: Using per-channel integration times")
            else:
                # Standard mode: Pre-arm integration time ONCE (optimization)
                try:
                    usb = self.hardware_mgr.usb
                    if usb:
                        result = usb.set_integration(p_integration_time_effective)
                        if result:
                            logger.info(f"[PRE-ARM] ✓ Integration time pre-armed: {p_integration_time_effective:.1f}ms")
                            logger.info(f"[PRE-ARM] Optimization active: Skipping set_integration() in acquisition loop (saves ~7ms/channel)")
                        else:
                            logger.warning(f"[PRE-ARM] ✗ Failed to pre-arm integration time: {p_integration_time_effective:.1f}ms")
                    else:
                        logger.warning("[PRE-ARM] ✗ Spectrometer not available for pre-arm")
                except Exception as e:
                    logger.error(f"[PRE-ARM] ✗ Exception during pre-arm: {e}")
                    import traceback
                    traceback.print_exc()

            # Common parameters (same for all channels)
            num_scans = (
                self.calibration_data.num_scans
                if self.calibration_data.num_scans
                and self.calibration_data.num_scans > 0
                else 1
            )

            # TIMING TRACK MODE: Override calibration delays with new timing architecture
            # LED Track: OFF 55ms → ON 260ms (total 315ms per channel)
            # Detector Track: Wait 100ms → Detect 210ms (total 310ms per channel)
            import settings as root_settings

            use_timing_tracks = True  # New architecture enabled

            if use_timing_tracks:
                # Use timing track parameters (not calibration delays)
                detector_wait_ms = getattr(
                    root_settings, "DETECTOR_WAIT_BEFORE_MS", 100.0,
                )
                detector_window_ms = getattr(root_settings, "DETECTOR_WINDOW_MS", 210.0)

                # CRITICAL: Calculate maximum scans that fit in detection window
                # Each scan takes integration_time_ms to complete
                max_scans_in_window = int(
                    detector_window_ms / p_integration_time_effective,
                )
                if num_scans > max_scans_in_window:
                    num_scans = max_scans_in_window if max_scans_in_window > 0 else 1

                # Map timing tracks to delay parameters for _acquire_raw_spectrum
                # PRE delay = detector wait time (LED stabilization)
                # POST delay = remaining LED ON time after detector finishes
                led_on_total_ms = getattr(root_settings, "LED_ON_PERIOD_MS", 260.0)
                pre_led_delay = detector_wait_ms  # 100ms - LED stabilization

                # Calculate actual detection time needed
                actual_detection_ms = num_scans * p_integration_time_effective
                post_led_delay = (
                    led_on_total_ms - detector_wait_ms - actual_detection_ms
                )

                # CRITICAL: POST delay can't be negative
                post_led_delay = max(post_led_delay, 0)

            else:
                # Legacy mode: Use calibration delays
                pre_led_delay = (
                    self.calibration_data.pre_led_delay_ms
                    if self.calibration_data.pre_led_delay_ms is not None
                    else self._pre_led_delay_ms
                )
                post_led_delay = (
                    self.calibration_data.post_led_delay_ms
                    if self.calibration_data.post_led_delay_ms is not None
                    else self._post_led_delay_ms
                )

            # Log LED overlap optimization
            overlap_ms = getattr(root_settings, "LED_OVERLAP_MS", 0)
            if overlap_ms > 0:
                pre_led_delay + (post_led_delay - overlap_ms)
            else:
                pass

            # CRITICAL: Log delay source for troubleshooting
            if self.calibration_data.pre_led_delay_ms is not None:
                pass
            else:
                pass

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

                if cycle_count % 10 == 1:
                    # Periodic LED verification (V1.1+ firmware)
                    if (
                        self.hardware_mgr
                        and self.hardware_mgr.ctrl
                        and hasattr(self.hardware_mgr.ctrl, "verify_led_state")
                    ):
                        try:
                            # Verify all LEDs are off between batches
                            expected_off = {"a": 0, "b": 0, "c": 0, "d": 0}
                            if not self.hardware_mgr.ctrl.verify_led_state(
                                expected_off, tolerance=10,
                            ):
                                pass
                        except Exception:
                            pass

                try:
                    # Check if paused
                    if self._pause_acquisition.is_set():
                        time.sleep(0.1)
                        continue

                    batch_success = False
                    spectra_acquired = 0

                    # Start cycle timing (detector window to detector window)
                    cycle_start = (
                        time.perf_counter()
                        if self._enable_timing_instrumentation
                        else None
                    )

                    # ========================================================================
                    # FIRMWARE V2.0+ RANK SEQUENCE (30% FASTER)
                    # ========================================================================
                    # If firmware supports rank sequence, acquire all channels in one call
                    # using firmware-controlled LED sequencing (700ms vs 1000ms)
                    if self._rank_mode_enabled:
                        try:
                            # Build LED intensity dict for rank
                            led_intensities = {}
                            for ch in channels:
                                led_int = self.calibration_data.p_mode_intensities.get(ch)
                                if led_int is not None:
                                    led_intensities[ch] = led_int

                            # Fallback: if P-mode intensities missing or all zero, use available defaults
                            if (not led_intensities) or all((led_intensities.get(ch, 0) or 0) == 0 for ch in channels):
                                try:
                                    # Try S-mode first
                                    s_ints = getattr(self.calibration_data, 's_mode_intensities', {}) or {}
                                    if s_ints and any((s_ints.get(ch, 0) or 0) > 0 for ch in channels):
                                        led_intensities = {ch: s_ints.get(ch, 0) for ch in channels}
                                        logger.warning("[RANK] P-mode intensities missing/zero; using S-mode intensities as fallback")
                                    else:
                                        # Use generic intensities or a safe default
                                        generic_ints = getattr(self.calibration_data, 'led_intensities', {}) or {}
                                        if generic_ints and any((generic_ints.get(ch, 0) or 0) > 0 for ch in channels):
                                            led_intensities = {ch: generic_ints.get(ch, 128) for ch in channels}
                                            logger.warning("[RANK] P-mode intensities missing/zero; using generic LED intensities fallback")
                                        else:
                                            led_intensities = {ch: 128 for ch in channels}
                                            logger.warning("[RANK] No calibrated intensities available; using default 128 for rank preset")
                                except Exception:
                                    led_intensities = {ch: 128 for ch in channels}
                                    logger.warning("[RANK] Fallback to default 128 intensities due to exception")

                            # Build per-channel integration times if available
                            per_channel_integration = None
                            if has_per_channel_integration_times:
                                per_channel_integration = {}
                                for ch in channels:
                                    ch_int_time = self.calibration_data.channel_integration_times.get(
                                        ch, p_integration_time_effective
                                    )
                                    per_channel_integration[ch] = ch_int_time

                            # Acquire all channels via rank sequence (firmware-controlled timing)
                            # Firmware controls full LED cycle: OFF 5ms → ON 245ms
                            # sync_test.py validated timing: settle=245ms, dark=5ms, 50ms wait after READY event
                            led_on_time_ms = 245.0  # Total LED ON time (firmware holds LED on)
                            led_off_period = 5.0     # LED OFF between channels

                            channel_spectra = self._acquire_all_channels_via_rank(
                                channels=channels,
                                led_intensities=led_intensities,
                                integration_time_ms=p_integration_time_effective,
                                per_channel_integration=per_channel_integration,
                                settling_ms=led_on_time_ms,  # 245ms - Total LED ON time (sync_test validated)
                                dark_ms=led_off_period,       # 5ms - LED OFF between channels
                            )

                            # ASYNC PROCESSING: Spectra are already being processed in background threads
                            # (see _process_and_emit_spectrum_immediate called inside _acquire_all_channels_via_rank)
                            # Just update success tracking and continue to next batch
                            spectra_acquired += len(channel_spectra)
                            batch_success = True
                            
                            # Skip old synchronous processing path - using async now
                            continue

                            # OLD SYNCHRONOUS PROCESSING (DISABLED - now using async)
                            # Process each spectrum from rank acquisition
                            for ch in channels:
                                raw_spectrum = channel_spectra.get(ch)

                                if raw_spectrum is not None:
                                    # Record timing for this channel
                                    led_time_ms = None
                                    if (
                                        self._enable_timing_instrumentation
                                        and cycle_start is not None
                                    ):
                                        led_time_ms = (time.perf_counter() - cycle_start) * 1000

                                    # Package data for processing
                                    spectrum_data = {
                                        "raw_spectrum": raw_spectrum,
                                        "wavelength": self.calibration_data.wavelengths,
                                        "timestamp": time.time(),
                                        "led_time_ms": led_time_ms,
                                        "integration_time": self.calibration_data.integration_time,
                                        "num_scans": self.calibration_data.num_scans,
                                        "led_intensity": self.calibration_data.p_mode_intensities.get(ch, 0),
                                    }

                                    timestamp = time.time()
                                    batch_success = True
                                    spectra_acquired += 1

                                    # Process and emit spectrum
                                    try:
                                        process_start = time.perf_counter()
                                        processed = self._process_spectrum(ch, spectrum_data)

                                        if processed:
                                            trans = processed.get("transmission_spectrum")
                                            raw = processed.get("raw_spectrum")

                                            if (
                                                trans is None
                                                or (hasattr(trans, "__len__") and len(trans) == 0)
                                                or (hasattr(trans, "__len__") and np.count_nonzero(trans) == 0)
                                            ):
                                                self._empty_transmission_count += 1
                                            else:
                                                result = {
                                                    "channel": ch,
                                                    "wavelength": processed["wavelength"],
                                                    "intensity": processed["intensity"],
                                                    "raw_spectrum": raw,
                                                    "transmission_spectrum": trans,
                                                    "wavelengths": self.calibration_data.wavelengths,
                                                    "timestamp": timestamp,
                                                    "is_preview": False,
                                                    "batch_processed": False,
                                                    "integration_time": self.calibration_data.integration_time,
                                                    "num_scans": self.calibration_data.num_scans,
                                                    # Use the actual intensity we preset for rank (may be fallback)
                                                    "led_intensity": led_intensities.get(ch, 0),
                                                }
                                                self.spectrum_acquired.emit(result)
                                                (time.perf_counter() - process_start) * 1000
                                        else:
                                            self._dropped_processing += 1

                                    except Exception:
                                        self._dropped_processing += 1
                                        import traceback
                                        traceback.print_exc()

                                    # Clear error count on success
                                    channel_error_counts[ch] = 0
                                else:
                                    # Acquisition failed for this channel
                                    channel_error_counts[ch] += 1
                                    if channel_error_counts[ch] >= 20:
                                        channel_disabled[ch] = True

                            # Skip sequential acquisition loop
                            continue

                        except Exception as rank_err:
                            logger.error(f"[RANK] Failed, falling back to sequential: {rank_err}")
                            # Fall through to sequential acquisition

                    # ========================================================================
                    # SEQUENTIAL ACQUISITION (V1.9 COMPATIBLE FALLBACK)
                    # ========================================================================
                    # Acquire one complete 4-channel cycle, then emit immediately
                    # Process each channel in cycle
                    for idx, ch in enumerate(channels):
                        try:
                            if self._stop_acquisition.is_set():
                                break

                            # Skip channel if disabled due to persistent errors
                            if channel_disabled[ch]:
                                if cycle_count % 50 == 1:
                                    pass
                                continue

                            # Determine next channel for LED overlap optimization
                            next_ch = (
                                channels[idx + 1] if idx + 1 < len(channels) else None
                            )

                            # Get LED intensity for this channel
                            led_intensity = (
                                self.calibration_data.p_mode_intensities.get(ch)
                            )
                            if led_intensity is None:
                                continue

                            # Get LED intensity for next channel (for overlap optimization)
                            next_led_int = None
                            if next_ch:
                                next_led_int = (
                                    self.calibration_data.p_mode_intensities.get(
                                        next_ch,
                                    )
                                )

                            # SMART: Get integration time (per-channel if available, else common)
                            ch_integration_time = p_integration_time_effective
                            if has_per_channel_integration_times:
                                ch_integration_time = (
                                    self.calibration_data.channel_integration_times.get(
                                        ch, p_integration_time_effective,
                                    )
                                )

                            # Fixed cadence timing (optional)
                            import settings as root_settings

                            fixed_cycle_ms = None
                            if getattr(root_settings, "ENABLE_FIXED_CADENCE", False):
                                fixed_cycle_ms = getattr(
                                    root_settings, "FIXED_CYCLE_TIME_MS", None,
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

                            # Record per-LED timing (time since batch start)
                            led_time_ms = None
                            if (
                                self._enable_timing_instrumentation
                                and cycle_start is not None
                            ):
                                led_time_ms = (time.perf_counter() - cycle_start) * 1000

                            if raw_spectrum is not None:
                                # DEBUG: Log first raw spectrum
                                if not hasattr(self, "_first_raw_logged"):
                                    self._first_raw_logged = True

                                # Package data for processing
                                # Note: wavelength array is immutable calibration data - no need to copy
                                spectrum_data = {
                                    "raw_spectrum": raw_spectrum,
                                    "wavelength": self.calibration_data.wavelengths,  # Reference, not copy (wavelengths never change)
                                    "timestamp": time.time(),
                                    "led_time_ms": led_time_ms,  # Time since batch start when this LED's detector window completed
                                    "integration_time": self.calibration_data.integration_time,
                                    "num_scans": self.calibration_data.num_scans,
                                    "led_intensity": self.calibration_data.p_mode_intensities.get(
                                        ch, 0,
                                    ),
                                }

                                timestamp = time.time()
                                batch_success = True
                                spectra_acquired += 1

                                # STREAMLINED: Process immediately in acquisition thread (no queue, no batch worker)
                                try:
                                    process_start = time.perf_counter()

                                    # Process spectrum directly
                                    processed = self._process_spectrum(
                                        ch, spectrum_data,
                                    )

                                    if processed:
                                        # Validate processed data
                                        trans = processed.get("transmission_spectrum")
                                        raw = processed.get("raw_spectrum")

                                        # Check for empty or invalid arrays
                                        if (
                                            trans is None
                                            or (
                                                hasattr(trans, "__len__")
                                                and len(trans) == 0
                                            )
                                            or (
                                                hasattr(trans, "__len__")
                                                and np.count_nonzero(trans) == 0
                                            )
                                        ):
                                            self._empty_transmission_count += 1
                                        else:
                                            # Package result
                                            result = {
                                                "channel": ch,
                                                "wavelength": processed["wavelength"],
                                                "intensity": processed["intensity"],
                                                "raw_spectrum": raw,
                                                "transmission_spectrum": trans,
                                                "wavelengths": self.calibration_data.wavelengths,
                                                "timestamp": timestamp,
                                                "is_preview": False,
                                                "batch_processed": False,  # Inline processing, not batched
                                                "integration_time": self.calibration_data.integration_time,
                                                "num_scans": self.calibration_data.num_scans,
                                                "led_intensity": self.calibration_data.p_mode_intensities.get(
                                                    ch, 0,
                                                ),
                                            }

                                            # Emit directly (Qt signals are thread-safe)
                                            self.spectrum_acquired.emit(result)

                                            (time.perf_counter() - process_start) * 1000
                                    else:
                                        # Processing returned None - count as drop
                                        self._dropped_processing += 1

                                except Exception:
                                    self._dropped_processing += 1
                                    import traceback

                                    traceback.print_exc()

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
                                e, (serial.SerialException, ConnectionError, OSError),
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

                        # Log statistics periodically
                        if (
                            self._timing_data["acquisition_count"]
                            % self._timing_log_interval
                            == 0
                        ):
                            self._log_timing_statistics()

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

                    # Minimal delay between batch cycles for timing precision
                    # Old: 10ms (blocked acquisition for no reason)
                    # New: 1ms (allows faster batch processing, better jitter)
                    time.sleep(0.001)

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

            error_msg = (
                f"FATAL: Acquisition worker crashed: {e}\n{traceback.format_exc()}"
            )
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
    #   2. Wait PRE_LED_DELAY_MS (LED stabilization)
    #   3. Read spectrum from detector
    #   4. Wait POST_LED_DELAY_MS (afterglow decay)
    #   5. Turn off LED
    # Returns RAW spectrum with NO processing (dark subtraction in Layer 4)
    # ========================================================================

    def _process_and_emit_spectrum_immediate(self, channel: str, raw_spectrum, led_intensities: dict):
        """Queue spectrum for async processing - non-blocking for continuous acquisition.
        
        This queues the spectrum for background processing instead of blocking acquisition.
        Processing happens in parallel thread while we continue acquiring next channels.
        """
        try:
            # Package data for async processing
            spectrum_data = {
                "channel": channel,
                "raw_spectrum": raw_spectrum,
                "wavelength": self.calibration_data.wavelengths,
                "timestamp": time.time(),
                "led_time_ms": None,
                "integration_time": self.calibration_data.integration_time,
                "num_scans": self.calibration_data.num_scans,
                "led_intensity": led_intensities.get(channel, 0),
            }

            # Queue for async processing - NON-BLOCKING
            # Processing thread will handle dark subtraction + transmission calculation
            threading.Thread(
                target=self._process_and_emit_async,
                args=(spectrum_data,),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"[ASYNC-QUEUE] Failed to queue {channel}: {e}")

    def _process_and_emit_async(self, spectrum_data: dict):
        """Background processing thread - runs in parallel with acquisition."""
        try:
            channel = spectrum_data["channel"]
            
            # Process spectrum (dark subtraction + transmission calculation)
            processed = self._process_spectrum(channel, spectrum_data)

            if processed:
                trans = processed.get("transmission_spectrum")
                raw = processed.get("raw_spectrum")

                # Only emit if transmission is valid
                if trans is not None and (not hasattr(trans, "__len__") or (len(trans) > 0 and np.count_nonzero(trans) > 0)):
                    result = {
                        "channel": channel,
                        "wavelength": processed["wavelength"],
                        "intensity": processed["intensity"],
                        "raw_spectrum": raw,
                        "transmission_spectrum": trans,
                        "wavelengths": self.calibration_data.wavelengths,
                        "timestamp": spectrum_data["timestamp"],
                        "is_preview": False,
                        "batch_processed": False,
                        "integration_time": spectrum_data["integration_time"],
                        "num_scans": spectrum_data["num_scans"],
                        "led_intensity": spectrum_data["led_intensity"],
                    }
                    # Qt signals are thread-safe - can emit from background thread
                    self.spectrum_acquired.emit(result)
                else:
                    logger.warning(f"[ASYNC] Ch {channel}: Empty transmission, not emitting")
            else:
                logger.warning(f"[ASYNC] Ch {channel}: Processing returned None")
        except Exception as e:
            import traceback
            logger.error(f"[ASYNC-PROCESS] Failed to process {spectrum_data.get('channel', '?')}: {e}")
            logger.error(f"[ASYNC-PROCESS] Traceback: {traceback.format_exc()}")
            logger.error(f"[ASYNC-PROCESS] Failed to process {spectrum_data.get('channel', '?')}: {e}")

    def _acquire_all_channels_via_rank(
        self,
        channels: list,
        led_intensities: dict,
        integration_time_ms: float,
        per_channel_integration: dict = None,
        settling_ms: float = 245,  # LED ON time: 245ms
        dark_ms: float = 5,         # LED OFF time: 5ms
    ) -> dict:
        """Acquire all channels using event-driven RANKBATCH synchronization.

        **NEW EVENT-DRIVEN APPROACH (0.3% stability):**
        - Send rankbatch command (4 cycles at a time for responsive Stop)
        - Listen to firmware LED events (a:READY, b:READY, c:READY, d:READY)
        - When 'x:READY' received -> LED just turned on
        - Wait 50ms for LED stabilization (validated optimal timing)
        - Acquire spectrum while LED is stable
        - Timestamp = READY event time (firmware timing, not Python prediction)

        Args:
            channels: List of channels to acquire (e.g., ['a', 'b', 'c', 'd'])
            led_intensities: Dict of LED intensities per channel {ch: intensity}
            integration_time_ms: Global integration time (if no per-channel)
            per_channel_integration: Optional dict of per-channel integration times
            settling_ms: LED ON time (default 245ms - 50ms rise + 195ms stable)
            dark_ms: LED OFF time between channels (default 5ms)

        Returns:
            dict: {channel: raw_spectrum_array} for all channels acquired in this 4-cycle batch

        Performance:
            Event-driven: ~1025ms per 4-LED cycle (0.31-0.37% signal stability)
            Stop responsiveness: <1 second (finishes current 4-cycle batch)
        """
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                logger.error("[RANK-EVENT] Controller or detector not available")
                return {}

            # EVENT-DRIVEN RANKBATCH: Truly autonomous LED operation
            # Very high cycle count = firmware runs LEDs for hours without Python intervention
            # This eliminates restart gaps and provides smooth continuous operation
            # 3600 cycles = 14400 LED activations = ~1 hour of autonomous operation
            # Trade-off: Pause delay is ~15 seconds (but acquisition is meant to run continuously)
            # This allows valve operations from external devices without Python interference
            n_cycles = 3600

            # Extract LED intensities (rankbatch embeds them in command - sync_test.py pattern)
            int_a = led_intensities.get('a', 0)
            int_b = led_intensities.get('b', 0)
            int_c = led_intensities.get('c', 0)
            int_d = led_intensities.get('d', 0)

            # PRE-ARM OPTIMIZATION: Set integration time BEFORE rankbatch if not using per-channel
            # This saves ~7ms per acquisition and ensures detector is ready when LED turns on
            if not per_channel_integration:
                usb.set_integration(integration_time_ms)
                logger.debug(f"[PRE-ARM] Integration time set to {integration_time_ms}ms before rankbatch")
            
            # Build rankbatch command with CORRECT PARAMETER ORDER: A,B,C,D,SETTLE,DARK,CYCLES
            # Firmware expects: rankbatch:A,B,C,D,SETTLE,DARK,CYCLES (intensities embedded)
            rankbatch_cmd = f"rankbatch:{int_a},{int_b},{int_c},{int_d},{int(settling_ms)},{int(dark_ms)},{n_cycles}\n"

            logger.debug(f"[RANK-EVENT] Acquiring single batch: {rankbatch_cmd.strip()}")

            # Storage for spectra from THIS batch only
            channel_spectra = {}
            led_names = ['a', 'b', 'c', 'd']

            # SINGLE BATCH ACQUISITION (called repeatedly by acquisition worker)
            # Acquire ONE batch (4 cycles), then return to let worker process data

            # Send rankbatch command to firmware
            ctrl._ser.write(rankbatch_cmd.encode())

            # Wait for firmware acknowledgment
            ack_received = False
            for _ in range(20):  # Wait up to 2 seconds
                if ctrl._ser.in_waiting > 0:
                    response = ctrl._ser.readline().decode('utf-8', errors='ignore').strip()
                    if "BATCH_START" in response or "pos=" in response:
                        ack_received = True
                        break
                time.sleep(0.1)

            if not ack_received:
                logger.warning(f"[RANK-EVENT] No firmware acknowledgment - proceeding anyway")

            # Acquire spectra for this batch
            current_cycle = 0
            batch_acquisitions = 0
            batch_start = time.perf_counter()
            timeout_start = time.perf_counter()
            # Timeout should be longer than batch duration: 3600 cycles × 1s per cycle = 1 hour + buffer
            max_wait = 4000.0  # Max ~1 hour per batch (very long for truly continuous operation)

            # Event-driven acquisition loop for this batch
            while current_cycle < n_cycles:
                # Check timeout
                if time.perf_counter() - timeout_start > max_wait:
                    logger.warning(f"[RANK-EVENT] Batch timeout after {max_wait}s")
                    break

                # Check for stop signal (finish current batch gracefully)
                if self._stop_acquisition.is_set():
                    logger.debug(f"[RANK-EVENT] Stop requested, finishing current batch")
                    break

                # Read serial output
                if ctrl._ser.in_waiting > 0:
                    line = ctrl._ser.readline().decode('utf-8', errors='ignore').strip()

                    # Track cycle number
                    if line.startswith("CYCLE:"):
                        cycle_num = int(line.split(":")[1])
                        if cycle_num > current_cycle:
                            current_cycle = cycle_num

                    # Check for LED READY events (LED just turned on)
                    for led_name in led_names:
                        if line == f"{led_name}:READY":
                            # LED just turned ON! Wait 50ms for LED stabilization (validated optimal)
                            time.sleep(0.050)

                            # Set integration time ONLY if using per-channel (otherwise pre-armed)
                            if per_channel_integration:
                                int_time = per_channel_integration.get(led_name, integration_time_ms)
                                usb.set_integration(int_time)
                                # Note: This adds ~7ms delay per channel but required for per-channel integration

                            # Acquire spectrum - detector is already armed and ready
                            try:
                                num_scans = self.calibration_data.num_scans if hasattr(self.calibration_data, 'num_scans') else 1

                                if num_scans > 1:
                                    # Multiple scans - average them
                                    spectra = []
                                    for scan_idx in range(num_scans):
                                        scan = usb.read_intensity()
                                        if scan is not None and len(scan) > 0:
                                            spectra.append(scan)

                                    if spectra:
                                        spectrum = np.mean(spectra, axis=0)
                                        channel_spectra[led_name] = spectrum
                                        batch_acquisitions += 1
                                        
                                        # IMMEDIATE PROCESSING: Process and emit spectrum as soon as acquired
                                        # This eliminates batch delay and provides continuous data flow
                                        self._process_and_emit_spectrum_immediate(led_name, spectrum, led_intensities)
                                else:
                                    # Single scan
                                    spectrum = usb.read_intensity()
                                    if spectrum is not None and len(spectrum) > 0:
                                        channel_spectra[led_name] = spectrum
                                        batch_acquisitions += 1
                                        
                                        # IMMEDIATE PROCESSING: Process and emit spectrum as soon as acquired
                                        self._process_and_emit_spectrum_immediate(led_name, spectrum, led_intensities)

                            except Exception as e:
                                logger.error(f"[RANK-EVENT] Failed to acquire {led_name}: {e}")
                else:
                    # No data available, small sleep to avoid busy-waiting
                    time.sleep(0.001)

            # Drain remaining serial output after batch completes
            time.sleep(0.1)
            while ctrl._ser.in_waiting > 0:
                line = ctrl._ser.readline().decode('utf-8', errors='ignore').strip()
                if "BATCH_END" in line:
                    logger.debug(f"[RANK-EVENT] Batch complete")

            batch_elapsed = time.perf_counter() - batch_start
            logger.debug(f"[RANK-EVENT] Batch: {batch_acquisitions} spectra in {batch_elapsed:.2f}s")
            logger.debug(f"[RANK-EVENT] Returning {len(channel_spectra)} channels: {list(channel_spectra.keys())}")
            
            return channel_spectra

        except Exception as e:
            logger.error(f"[RANK-EVENT] Fatal error: {e}")
            import traceback
            logger.error(f"[RANK-EVENT] Traceback: {traceback.format_exc()}")
            return {}

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
                    usb.set_integration(integration_time_ms)
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
            else:
                # Integration time already pre-armed (optimization - saves ~7ms)
                # Log only first occurrence to avoid spam
                if not hasattr(self, '_prearm_skip_logged'):
                    self._prearm_skip_logged = True
                    logger.debug(f"[PRE-ARM] Skipping set_integration() - using pre-armed {integration_time_ms:.1f}ms")

            # Start cycle timer for fixed-cadence timing
            cycle_start_time = time.perf_counter()

            # Initialize timing variables (no LED OFF phase needed - batch command handles it)
            led_command_time_ms = 0.0
            led_settle_time_ms = 0.0
            detector_read_time_ms = 0.0

            # Get timing parameters from settings
            import settings as root_settings

            LED_OFF_PERIOD_MS = getattr(root_settings, "LED_OFF_PERIOD_MS", 5.0)
            LED_ON_PERIOD_MS = getattr(root_settings, "LED_ON_PERIOD_MS", 245.0)
            DETECTOR_WAIT_BEFORE_MS = getattr(
                root_settings, "DETECTOR_WAIT_BEFORE_MS", 35.0,
            )
            getattr(root_settings, "DETECTOR_WINDOW_MS", 210.0)

            # =============================================================================
            # LED TRACK: Turn on target LED (automatically turns off others via batch command)
            # =============================================================================
            # The batch command sets all 4 LEDs atomically, so setting others to 0
            # automatically turns them off. No separate LED OFF phase needed!
            # =============================================================================
            led_command_start = (
                time.perf_counter() if self._enable_timing_instrumentation else None
            )

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

            # Collect num_scans during the 210ms detection window
            try:
                if num_scans > 1:
                    spectra = []
                    for _scan_idx in range(num_scans):
                        spectrum = usb.read_intensity()
                        if spectrum is not None:
                            spectra.append(spectrum)

                    if len(spectra) == 0:
                        logger.error(
                            f"[CH-{channel}] All {num_scans} scans failed - no valid spectra acquired",
                        )
                        return None

                    raw_spectrum = np.mean(spectra, axis=0)
                else:
                    raw_spectrum = usb.read_intensity()

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
                    # Brief wait then one retry
                    time.sleep(0.005)
                    retry_spectrum = usb.read_intensity()
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

                # Report jitter every 30 seconds
                current_time = time.time()
                if current_time - self._last_jitter_report > 30.0:
                    self._report_timing_jitter()
                    self._last_jitter_report = current_time

            # Trim spectrum to calibrated wavelength range
            if len(raw_spectrum) != len(self.calibration_data.wavelengths):
                # DEBUG: Log ROI cropping on first spectrum
                if not hasattr(self, "_roi_crop_logged"):
                    (
                        self.calibration_data.wave_max_index
                        - self.calibration_data.wave_min_index
                    )

                if (
                    self.calibration_data.wave_min_index
                    and self.calibration_data.wave_max_index
                ):
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
                    raw_spectrum = raw_spectrum[
                        : len(self.calibration_data.wavelengths)
                    ]
                    if not hasattr(self, "_roi_crop_logged"):
                        self._roi_crop_logged = True

            # =============================================================================
            # LED TRACK - STEP 3: LED stays ON for remaining period
            # =============================================================================
            # LED remains ON for rest of 245ms period while detector completes
            # Detector finishes at 35ms + 210ms = 245ms total
            # LED stays ON until end of period (245ms), then OFF at next cycle
            elapsed_since_led_on = (
                (time.perf_counter() - led_on_time) * 1000 if led_on_time else 0
            )
            remaining_led_on_ms = max(0, LED_ON_PERIOD_MS - elapsed_since_led_on)

            if remaining_led_on_ms > 0:
                time.sleep(remaining_led_on_ms / 1000.0)

            # Note: LED will be turned OFF at start of next channel cycle (LED_OFF_PERIOD_MS)
            # This completes the 250ms cycle: 5ms OFF + 245ms ON = 250ms per channel

            # Calculate total cycle time and log detailed breakdown
            total_cycle_ms = (time.perf_counter() - cycle_start_time) * 1000

            # Log timing breakdown every 10 cycles to identify bottlenecks
            if not hasattr(self, '_timing_log_counter'):
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
                    f"  TOTAL CYCLE:        {total_cycle_ms:6.1f}ms (target: 250ms)"
                )

            # ===================================================================
            # Return RAW spectrum (NO processing - matches calibration pattern)
            # ===================================================================
            return raw_spectrum

        except Exception as e:
            logger.error(f"Error in _acquire_raw_spectrum for channel {channel}: {e}")
            return None

    def _report_timing_jitter(self) -> None:
        """Report LED-to-detector timing jitter statistics for SNR analysis.

        Lower jitter = better SNR due to more consistent LED illumination timing.
        Target: <1ms std dev for optimal spectroscopy performance.
        """
        try:
            for ch in ["a", "b", "c", "d"]:
                jitter_data = self._timing_jitter_stats[ch]
                if len(jitter_data) < 10:  # Need at least 10 samples
                    continue

                import numpy as np

                np.mean(jitter_data)
                std_ms = np.std(jitter_data)
                np.min(jitter_data)
                np.max(jitter_data)

                # Assess jitter quality
                if std_ms < 0.5 or std_ms < 1.0 or std_ms < 2.0:
                    pass
                else:
                    pass

        except Exception:
            pass  # Silent fail - don't break acquisition

    def _apply_baseline_correction(
        self, transmission: np.ndarray, degree: int = 2,
    ) -> np.ndarray:
        """Apply polynomial baseline correction for live transmission visualization.

        This flattens spectral tilt in transmission for better visualization.
        Uses the same algorithm as QC report for consistency.

        Args:
            transmission: Raw transmission spectrum (with LED correction already applied)
            degree: Polynomial degree (2=quadratic)

        Returns:
            Baseline-corrected transmission spectrum

        """
        try:
            # Create x-axis for polynomial fit (normalized 0-1)
            x = np.linspace(0, 1, len(transmission))

            # Fit polynomial to transmission
            coeffs = np.polyfit(x, transmission, degree)
            baseline = np.polyval(coeffs, x)

            # Avoid division by very small baseline values
            baseline = np.where(baseline < 1.0, 1.0, baseline)

            # Divide transmission by baseline to remove tilt
            corrected = transmission / baseline

            # Re-scale to maintain similar transmission range
            original_mean = np.nanmean(transmission)
            corrected_mean = np.nanmean(corrected)
            if corrected_mean > 0:
                corrected = corrected * (original_mean / corrected_mean)

            return corrected

        except Exception:
            # Silent fail - return uncorrected transmission
            return transmission

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

    def _process_and_emit_queue(self, channel: str) -> None:
        """Process queued spectra and emit immediately for smooth display.

        Processes spectra sequentially from queue (FIFO).
        All data points are preserved and emitted in order.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')

        """
        queue = self._spectrum_queue[channel]
        timestamps = self._queue_timestamps[channel]

        if len(queue) == 0:
            return

        # SIMPLIFIED ARCHITECTURE: Single source of truth
        # Raw spectrum → Process → Emit (3 steps, no redundant copies)

        for i, spectrum_data in enumerate(queue):
            try:
                # Step 1: Process spectrum (dark subtraction, transmission, peak finding)
                processed = self._process_spectrum(channel, spectrum_data)
                if not processed or "wavelength" not in processed:
                    continue

                # Step 2: Get timestamp
                timestamp = (
                    timestamps[i]
                    if i < len(timestamps)
                    else spectrum_data.get("timestamp", time.time())
                )

                # Step 3: Buffer and emit (single source of truth: processed['wavelength'])
                peak_wavelength = float(processed["wavelength"])

                self.channel_buffers[channel].append(peak_wavelength)
                self.time_buffers[channel].append(timestamp)

                # Step 4: Emit to UI
                data = {
                    "channel": channel,
                    "wavelength": peak_wavelength,  # SINGLE SOURCE OF TRUTH
                    "intensity": float(processed.get("intensity", 0.0)),
                    "raw_spectrum": processed.get("raw_spectrum"),
                    "transmission_spectrum": processed.get("transmission_spectrum"),
                    "wavelengths": self.calibration_data.wavelengths,
                    "timestamp": timestamp,
                    "is_preview": False,
                    "queue_processed": True,
                    "integration_time": self.calibration_data.integration_time,
                    "num_scans": self.calibration_data.num_scans,
                    "led_intensity": self.calibration_data.p_mode_intensities.get(
                        channel, 0,
                    ),
                }

                # DEBUG: Log wavelength emissions
                if not hasattr(self, "_emission_count"):
                    self._emission_count = {}
                if channel not in self._emission_count:
                    self._emission_count[channel] = 0

                self._emission_count[channel] += 1
                if (
                    self._emission_count[channel] % 10 == 0
                    or self._emission_count[channel] <= 3
                ):
                    pass

                with contextlib.suppress(queue.Full):
                    self._emission_queue.put_nowait(data)

            except Exception:
                continue

        # Clear queue buffers
        self._spectrum_queue[channel].clear()
        self._queue_timestamps[channel].clear()

    # ========================================================================
    # LAYER 4: PROCESSING (Dark Subtraction + Transmission Calculation)
    # ========================================================================
    # This layer matches calibration_6step.py Step 6 processing exactly:
    #   1. Dark subtraction using SpectrumPreprocessor.process_polarization_data()
    #   2. Transmission calculation using TransmissionProcessor.process_single_channel()
    # Same functions, same parameters as calibration = same results
    # ========================================================================

    def _process_spectrum(self, channel: str, spectrum_data: dict) -> dict:
        """LAYER 4: Process raw spectrum into transmission (matches calibration Step 6).

        This function uses the exact same processing as calibration Step 6:
        - SpectrumPreprocessor.process_polarization_data() for dark subtraction
        - TransmissionProcessor.process_single_channel() for transmission

        Args:
            channel: Channel name ('a', 'b', 'c', or 'd')
            spectrum_data: Dict with 'raw_spectrum' (numpy array) and 'wavelength' from Layer 3

        Returns:
            Dict with processed transmission data

        Note: Processing parameters (baseline_method, baseline_percentile, etc.)
              MUST match calibration exactly to ensure consistency.

        """
        # DIAGNOSTIC: Entry point logging
        if not hasattr(self, "_process_entry_count"):
            self._process_entry_count = {}
        if channel not in self._process_entry_count:
            self._process_entry_count[channel] = 0
        self._process_entry_count[channel] += 1

        if self._process_entry_count[channel] <= 3:
            pass

        try:
            # Get truly raw data from Layer 3 (hardware acquisition)
            wavelength = spectrum_data["wavelength"]
            raw_intensity = spectrum_data["raw_spectrum"]  # Truly raw from detector

            # GUARD: Validate raw spectrum before processing
            if raw_intensity is None:
                return None
            if len(raw_intensity) == 0:
                return None
            if np.count_nonzero(raw_intensity) == 0:
                return None

            # CRITICAL: Apply ROI mask to match calibration wavelengths
            # Raw spectrum is 3840 pixels, but calibration data is already sliced
            # We need to slice raw data to match the CALIBRATED size (wavelengths array)
            if hasattr(self.calibration_data, 'wavelengths') and len(self.calibration_data.wavelengths) < len(raw_intensity):
                # Slice from the center or use wave_min_index as starting point
                if hasattr(self.calibration_data, 'wave_min_index'):
                    start_idx = self.calibration_data.wave_min_index
                    end_idx = start_idx + len(self.calibration_data.wavelengths)
                    raw_intensity = raw_intensity[start_idx:end_idx]
                else:
                    # Fallback: slice to match wavelengths size from start
                    raw_intensity = raw_intensity[:len(self.calibration_data.wavelengths)]

            # LAYER 4: Apply dark subtraction using SpectrumPreprocessor (same as calibration)
            # CRITICAL: Use per-channel dark reference for P-pol with correct integration time
            # This ensures consistent preprocessing between calibration and live data

            # CRITICAL QC: Check if LED actually turned on
            # If LEDs are off, spectrum should be dark-level (~2000-3000 counts)
            # If LEDs are on, spectrum should be significantly higher (>10,000 counts for typical setup)
            raw_peak = np.max(raw_intensity)
            raw_mean = np.mean(raw_intensity)

            # Get dark level for comparison
            if (
                hasattr(self.calibration_data, "dark_p")
                and channel in self.calibration_data.dark_p
            ):
                dark_ref_check = self.calibration_data.dark_p[channel]
                # Note: dark_ref_check is already calibrated size, no slicing needed
                dark_peak = np.max(dark_ref_check) if dark_ref_check is not None else 3000
            else:
                dark_peak = 3000  # Typical dark level

            # LED ON should give at least 3X the dark level
            if raw_peak < dark_peak * 3.0:
                logger.warning(
                    f"[LED-OFF-DETECTED] Ch {channel}: Raw peak ({raw_peak:.0f}) is < 3X dark ({dark_peak:.0f}) "
                    f"- LED may not have turned on! Mean={raw_mean:.0f}"
                )
                # Don't return None - let it through for now to see the data
                # return None

            # DIAGNOSTIC: Track whether spectrum data is changing between acquisitions
            # This detects if acquisition is frozen (same data reprocessed) vs peak finding caching
            try:
                spectrum_hash = hash(raw_intensity.tobytes())
                if not hasattr(self, "_last_spectrum_hash"):
                    self._last_spectrum_hash = {}
                if channel in self._last_spectrum_hash:
                    if self._last_spectrum_hash[channel] == spectrum_hash:
                        pass
                    # else:
                    #     print(f"   [SPECTRUM-FRESH] Ch {channel}: ✓ New spectrum data received")
                self._last_spectrum_hash[channel] = spectrum_hash
            except Exception:
                pass

            # Get per-channel P-pol dark if available, otherwise fall back to legacy dark_noise
            if (
                hasattr(self.calibration_data, "dark_p")
                and channel in self.calibration_data.dark_p
            ):
                dark_ref = self.calibration_data.dark_p[channel]
                # Note: dark_ref is already calibrated size, no slicing needed
            else:
                # Fallback to legacy dark_noise (backward compatibility)
                dark_ref = (
                    self.calibration_data.dark_noise
                    if hasattr(self.calibration_data, "dark_noise")
                    else None
                )
                # Legacy dark_noise needs slicing to match calibration size
                if dark_ref is not None and hasattr(self.calibration_data, 'wavelengths'):
                    if len(dark_ref) > len(self.calibration_data.wavelengths):
                        if hasattr(self.calibration_data, 'wave_min_index'):
                            start_idx = self.calibration_data.wave_min_index
                            end_idx = start_idx + len(self.calibration_data.wavelengths)
                            dark_ref = dark_ref[start_idx:end_idx]
                        else:
                            dark_ref = dark_ref[:len(self.calibration_data.wavelengths)]

            clean_spectrum = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=raw_intensity,
                dark_noise=dark_ref,
                channel_name=channel,
                verbose=False,  # Suppress logging for performance
            )

            # GUARD: Validate clean spectrum after preprocessing
            if clean_spectrum is None:
                return None
            if len(clean_spectrum) == 0:
                return None

            # Store clean spectrum (dark-corrected)
            raw_spectrum = clean_spectrum  # Ready for transmission calculation
            intensity = clean_spectrum  # For peak finding

            # LAYER 4: Calculate transmission spectrum using TransmissionProcessor (same as calibration)
            # This ensures consistent processing between calibration and live data
            transmission_spectrum = None

            # DIAGNOSTIC: Log s_pol_ref dictionary state on first call per channel
            if not hasattr(self, "_spol_ref_logged"):
                self._spol_ref_logged = set()

            if channel not in self._spol_ref_logged:
                self._spol_ref_logged.add(channel)
                list(
                    self.calibration_data.s_pol_ref.keys(),
                ) if self.calibration_data.s_pol_ref else []
                if (
                    self.calibration_data.s_pol_ref
                    and channel in self.calibration_data.s_pol_ref
                ):
                    self.calibration_data.s_pol_ref[channel]

            if (
                channel in self.calibration_data.s_pol_ref
                and self.calibration_data.s_pol_ref[channel] is not None
            ):
                try:
                    ref_spectrum = self.calibration_data.s_pol_ref[channel]
                    # Note: ref_spectrum is already calibrated size from calibration, no slicing needed

                    # GUARD: Validate ref_spectrum and array alignment
                    if (
                        ref_spectrum is None
                        or len(ref_spectrum) == 0
                        or len(clean_spectrum) != len(ref_spectrum)
                    ):
                        logger.warning(f"[RANK] Channel {channel} array size mismatch: clean={len(clean_spectrum)}, ref={len(ref_spectrum)}")
                        transmission_spectrum = None
                    else:
                        # CRITICAL DIAGNOSTIC: Log reference spectrum values
                        if not hasattr(self, "_ref_spectrum_logged"):
                            self._ref_spectrum_logged = set()

                        if channel not in self._ref_spectrum_logged:
                            self._ref_spectrum_logged.add(channel)
                            if np.count_nonzero(ref_spectrum) == 0:
                                pass

                        # Arrays are valid and aligned - proceed with calculation
                        # Get LED intensities
                        p_led = self.calibration_data.p_mode_intensities.get(
                            channel, 255,
                        )
                        s_led = self.calibration_data.s_mode_intensities.get(
                            channel, 200,
                        )

                        # Calculate transmission using unified processor (same as calibration Part C)
                        # clean_spectrum is now dark-corrected (processed by SpectrumPreprocessor above)

                        # DEBUG: Log first transmission calculation inputs
                        if not hasattr(self, "_first_trans_calc"):
                            # CRITICAL DEBUG: Check if arrays are aligned
                            if len(clean_spectrum) != len(ref_spectrum):
                                pass

                            if len(clean_spectrum) != len(
                                self.calibration_data.wavelengths,
                            ):
                                pass

                            self._first_trans_calc = True

                        transmission_spectrum = TransmissionProcessor.process_single_channel(
                            p_pol_clean=clean_spectrum,  # Clean spectrum from SpectrumPreprocessor
                            s_pol_ref=ref_spectrum,  # Clean S-pol reference from calibration
                            led_intensity_s=s_led,
                            led_intensity_p=p_led,
                            wavelengths=self.calibration_data.wavelengths,
                            apply_sg_filter=True,  # ENABLED: SG smoothing for peak finding (window=11, poly=3)
                            baseline_method="percentile",  # Same as calibration
                            baseline_percentile=95.0,  # Same as calibration
                            verbose=(
                                not hasattr(self, "_first_trans_calc")
                            ),  # Enable verbose for first calculation only
                        )

                        # GUARD: Validate transmission result
                        if transmission_spectrum is None:
                            pass
                        elif len(transmission_spectrum) == 0:
                            transmission_spectrum = None
                        elif np.count_nonzero(transmission_spectrum) == 0:
                            pass
                        elif np.isnan(transmission_spectrum).all():
                            transmission_spectrum = None

                    # DEBUG: Log first 3 transmission results with full detail
                    if not hasattr(self, "_trans_result_count"):
                        self._trans_result_count = 0

                    if self._trans_result_count < 3:
                        if transmission_spectrum is not None:
                            np.count_nonzero(transmission_spectrum) == 0

                            # DIAGNOSTIC: Check where minimum is found
                            min_idx = np.argmin(transmission_spectrum)
                            wavelength[min_idx]

                            # Check SPR region (620-680nm)
                            spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
                            if np.any(spr_mask):
                                spr_trans = transmission_spectrum[spr_mask]
                                wavelength[spr_mask]
                                np.argmin(spr_trans)

                                # Show transmission values at key wavelengths to diagnose slope
                                for test_wl in [620, 630, 640, 650, 660, 670, 680]:
                                    wl_idx = np.argmin(np.abs(wavelength - test_wl))
                                    if wl_idx < len(transmission_spectrum):
                                        pass
                        else:
                            pass
                        self._trans_result_count += 1

                    # Debug log LED correction (throttled)
                    if not hasattr(self, "_transmission_debug_counter"):
                        self._transmission_debug_counter = 0
                    self._transmission_debug_counter += 1
                    # Disabled for performance - print every 100th instead of 50th
                    # if self._transmission_debug_counter % 100 == 1:
                    #     print(f"[PROCESS] Ch {channel}: Using TransmissionProcessor with S={s_led}, P={p_led}")

                except Exception:
                    with contextlib.suppress(builtins.BaseException):
                        pass
                    transmission_spectrum = None
            else:
                # Channel NOT in s_pol_ref dictionary - log why
                if self.calibration_data.s_pol_ref:
                    pass
                else:
                    pass
                transmission_spectrum = None

            # ═══════════════════════════════════════════════════════════════════════════
            # PEAK FINDING: Fourier Transform Method
            # ═══════════════════════════════════════════════════════════════════════════

            # CRITICAL VERIFICATION: Peak finding uses THE EXACT SAME transmission_spectrum
            # that gets sent to the sidebar. No copies, no modifications - same object reference.
            # peak_input = transmission_spectrum (if valid) → same numpy array in memory
            # This guarantees 100% identical data between peak finding and sidebar display.

            # Guard: if transmission_spectrum is invalid (all-zero or all-NaN), fall back to intensity
            # CRITICAL: This prevents peak finding from receiving empty/invalid arrays
            peak_input = (
                transmission_spectrum
                if transmission_spectrum is not None
                else intensity
            )
            fallback_reason = None
            try:
                if transmission_spectrum is not None:
                    if len(transmission_spectrum) == 0:
                        peak_input = intensity
                        fallback_reason = "empty array"
                    elif np.isnan(transmission_spectrum).all():
                        peak_input = intensity
                        fallback_reason = "all NaN"
                    elif np.count_nonzero(transmission_spectrum) == 0:
                        peak_input = intensity
                        fallback_reason = "all zeros"
                else:
                    fallback_reason = "None returned"

                # Log fallback only for first few occurrences
                if fallback_reason and not hasattr(self, "_fallback_logged"):
                    self._fallback_logged = True
            except Exception:
                # If not numpy array yet, keep fallback behavior
                pass

            # Calculate minimum hint from smoothed transmission to guide Fourier method
            # CRITICAL: Only search in SPR-relevant region (620-680nm) to avoid edge artifacts
            minimum_hint_nm = None
            if (
                transmission_spectrum is not None
                and len(transmission_spectrum) > 0
                and len(wavelength) == len(transmission_spectrum)
            ):
                # Find indices for SPR region (tightened from 600-690 to avoid edges)
                spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
                if np.any(spr_mask):
                    # Find minimum ONLY within SPR region (ignores edge curvature)
                    spr_transmission = transmission_spectrum[spr_mask]
                    spr_wavelengths = wavelength[spr_mask]
                    min_idx_in_region = np.argmin(spr_transmission)
                    minimum_hint_nm = spr_wavelengths[min_idx_in_region]

            # GUARD: Final validation before peak finding
            # CRITICAL: Verify dimensions match for batch processing integrity
            if (
                peak_input is None
                or len(peak_input) == 0
                or len(wavelength) != len(peak_input)
            ):
                peak_wavelength = 650.0
            else:
                # DIMENSION VERIFICATION: Log first 3 to verify batch processing preserves dimensions
                if not hasattr(self, "_dimension_verify_count"):
                    self._dimension_verify_count = 0

                if self._dimension_verify_count < 3:
                    if minimum_hint_nm:
                        # Verify hint is within wavelength range
                        wavelength[0] <= minimum_hint_nm <= wavelength[-1]
                    self._dimension_verify_count += 1

                # Arrays are valid - proceed with DIRECT Fourier peak finding (no pipeline wrapper)
                peak_wavelength = self._fourier_peak_finding(
                    wavelength, peak_input, channel, minimum_hint_nm=minimum_hint_nm,
                )

                # DIAGNOSTIC: Log first few peak findings with calibration QC validation
                if not hasattr(self, "_peak_find_count"):
                    self._peak_find_count = 0
                    self._calibration_peak_validated = False

                if self._peak_find_count < 3:
                    # Get expected peak from calibration QC (if available)
                    expected_peak = None
                    if self.calibration_data and hasattr(
                        self.calibration_data, "transmission_validation",
                    ):
                        validation = self.calibration_data.transmission_validation.get(
                            channel, {},
                        )
                        qc_metrics = validation.get("qc_metrics", {})
                        expected_peak = qc_metrics.get("dip_wavelength")

                    # Validate against calibration QC on first result
                    if expected_peak and not self._calibration_peak_validated:
                        abs(peak_wavelength - expected_peak)
                        if minimum_hint_nm:
                            pass
                        self._calibration_peak_validated = True
                    else:
                        pass

                    self._peak_find_count += 1

            # ═══════════════════════════════════════════════════════════════════════════
            # QUALITY CONTROL: Independent validation (runs for every spectrum)
            # ═══════════════════════════════════════════════════════════════════════════

            # Calculate FWHM and quality metrics (does NOT affect peak position)
            if len(peak_input) > 0 and len(wavelength) == len(peak_input):
                qc_result = self._find_validated_peak(
                    wavelength, peak_input, channel, minimum_hint_nm=minimum_hint_nm,
                )
                fwhm_nm = qc_result["fwhm"]
                qc_quality = qc_result["quality"]
                qc_warning = qc_result.get("warning")
            else:
                fwhm_nm = None
                qc_quality = 0.0
                qc_warning = None

            # ✨ SENSOR IQ: Classify data quality based on wavelength range and FWHM
            try:
                from affilabs.utils.sensor_iq import (
                    SensorIQLevel,
                    classify_spr_quality,
                    log_sensor_iq,
                )
            except ImportError:
                from affilabs.utils.sensor_iq import (  # legacy path fallback
                    SensorIQLevel,
                    classify_spr_quality,
                    log_sensor_iq,
                )
            sensor_iq = classify_spr_quality(peak_wavelength, fwhm_nm, channel)

            # Log warnings for poor quality data (CRITICAL, POOR levels only)
            if sensor_iq.iq_level in [SensorIQLevel.CRITICAL, SensorIQLevel.POOR]:
                log_sensor_iq(sensor_iq, channel)

            # QC warnings available in result but not printed (performance)
            # if qc_warning:
            #     print(f"[QC] Channel {channel}: {qc_warning}")

            # VERIFICATION: Log object identity on first 3 spectra to prove peak finding
            # and sidebar see THE EXACT SAME transmission data (same memory address)
            if not hasattr(self, "_identity_verify_count"):
                self._identity_verify_count = 0

            if self._identity_verify_count < 3 and transmission_spectrum is not None:
                if id(transmission_spectrum) == id(peak_input):
                    pass
                else:
                    pass
                self._identity_verify_count += 1

            return {
                "wavelength": peak_wavelength,  # Fourier transform result
                "intensity": intensity[np.argmin(intensity)]
                if len(intensity) > 0
                else 0.0,
                "full_spectrum": raw_spectrum,
                "raw_spectrum": raw_spectrum,
                "transmission_spectrum": transmission_spectrum,  # Already baseline-corrected and SG-filtered
                "fwhm": fwhm_nm,  # QC pipeline result
                "qc_quality": qc_quality,  # QC pipeline quality score
                "qc_warning": qc_warning,  # QC pipeline warning message
                "minimum_hint_nm": minimum_hint_nm,  # Hint from smoothed transmission (for diagnostics)
                "sensor_iq": sensor_iq,  # ✨ Quality classification
                "integration_time": self.calibration_data.integration_time,
                "num_scans": self.calibration_data.num_scans,
                "led_intensity": self.calibration_data.p_mode_intensities.get(
                    channel, 0,
                ),
            }

        except Exception:
            with contextlib.suppress(builtins.BaseException):
                pass
            # Return minimal error structure
            return {
                "wavelength": 650.0,
                "intensity": 0.0,
                "full_spectrum": np.array([]),
                "raw_spectrum": np.array([]),
                "integration_time": self.calibration_data.integration_time
                if self.calibration_data
                else 0.0,
                "num_scans": self.calibration_data.num_scans
                if self.calibration_data
                else 1,
                "led_intensity": 0,
            }

    def _find_validated_peak(
        self,
        wavelength: np.ndarray,
        spectrum: np.ndarray,
        channel: str,
        minimum_hint_nm: float | None = None,
    ) -> dict:
        """Find and validate SPR peak using FWHM quality control with optional minimum hint.

        Strategy:
        1. If minimum_hint_nm provided: prioritize candidates near the hint
        2. Find ALL local minima in extended SPR region (590-750nm)
        3. Calculate FWHM for each candidate
        4. Reject candidates with invalid FWHM (too narrow/wide)
        5. Apply wavelength range validation:
           - Normal range: 590-670nm (preferred)
           - Extended range: 670-750nm (allowed during gradual shifts)
           - First peak >670nm = FLAG (potential issue)
        6. FWHM quality thresholds:
           - <30nm: Excellent
           - 30-60nm: Good
           - 60-80nm: Poor (warning)
           - >80nm: Problem (strong penalty)
        7. Select best candidate based on:
           - Proximity to hint (if provided - strong preference)
           - FWHM quality (primary factor)
           - Depth (stronger signal preferred)
           - Wavelength range (prefer 590-670nm)
           - Continuity (gradual shifts OK, jumps penalized)

        Args:
            wavelength: Wavelength array (nm)
            spectrum: Transmission spectrum (P/S ratio %)
            channel: Channel identifier for tracking history
            minimum_hint_nm: Optional hint from smoothed transmission minimum (nm)

        Returns:
            dict with:
                - 'wavelength': Best validated peak wavelength (nm)
                - 'fwhm': FWHM of validated peak (nm)
                - 'quality': Quality score (0-1)
                - 'candidates_found': Number of candidates evaluated
                - 'warning': Optional warning message

        """
        from scipy.signal import find_peaks

        try:
            from settings import FWHM_EXCELLENT_THRESHOLD_NM, FWHM_GOOD_THRESHOLD_NM
        except Exception:
            # Fallback defaults if settings constants are missing
            FWHM_EXCELLENT_THRESHOLD_NM = 30.0
            FWHM_GOOD_THRESHOLD_NM = 60.0

        # Default fallback
        default_result = {
            "wavelength": 650.0,
            "fwhm": None,
            "quality": 0.0,
            "candidates_found": 0,
            "warning": None,
        }

        try:
            # Extended SPR region: 590-750nm (covers normal + drift range)
            spr_mask = (wavelength >= 590) & (wavelength <= 750)
            wl_spr = wavelength[spr_mask]
            spec_spr = spectrum[spr_mask]

            if len(wl_spr) < 20:
                return default_result

            # Find ALL local minima (potential SPR dips)
            # Use inverted spectrum to find minima as peaks
            minima_indices, _properties = find_peaks(-spec_spr, prominence=1.0, width=3)

            if len(minima_indices) == 0:
                # No clear minima found, use minimum_hint_nm if available, else absolute minimum
                if minimum_hint_nm is not None and 600.0 <= minimum_hint_nm <= 690.0:
                    # Use the hint calculated from smoothed transmission in SPR region
                    peak_wl = minimum_hint_nm
                    logger.debug(
                        f"QC: No minima found, using minimum_hint_nm={peak_wl:.1f}nm",
                    )
                else:
                    # Fallback: find minimum in CORE SPR region (600-690nm)
                    core_spr_mask = (wl_spr >= 600.0) & (wl_spr <= 690.0)
                    if np.any(core_spr_mask):
                        core_spec = spec_spr[core_spr_mask]
                        core_wl = wl_spr[core_spr_mask]
                        min_idx = np.argmin(core_spec)
                        peak_wl = core_wl[min_idx]
                        logger.debug(
                            f"QC: No minima found, using minimum in core SPR region: {peak_wl:.1f}nm",
                        )
                    else:
                        min_idx = np.argmin(spec_spr)
                        peak_wl = wl_spr[min_idx]

                fwhm = self._calculate_fwhm(wl_spr, spec_spr, peak_wl)

                warning = None
                if peak_wl > 670.0:
                    warning = (
                        f"Peak at {peak_wl:.1f}nm (>670nm) with no clear dip structure"
                    )

                return {
                    "wavelength": peak_wl,
                    "fwhm": fwhm,
                    "quality": 0.3,  # Low quality - no clear dip structure
                    "candidates_found": 0,
                    "warning": warning,
                }

            # Check if first peak found is >670nm (potential issue flag)
            first_peak_flag = False
            if channel not in self._last_peak_wavelength:
                # First acquisition for this channel
                first_candidate_wl = wl_spr[minima_indices[0]]
                if first_candidate_wl > 670.0:
                    first_peak_flag = True
                    logger.warning(
                        f"Channel {channel}: First peak detected at {first_candidate_wl:.1f}nm (>670nm) - potential calibration issue",
                    )

            # Evaluate each candidate minimum
            candidates = []
            for idx in minima_indices:
                candidate_wl = wl_spr[idx]
                candidate_val = spec_spr[idx]

                # Calculate FWHM for this candidate
                fwhm = self._calculate_fwhm(wl_spr, spec_spr, candidate_wl)

                # Skip if FWHM calculation failed
                if fwhm is None or np.isnan(fwhm):
                    continue

                # FWHM quality criteria with your thresholds:
                # <30nm = Excellent
                # 30-60nm = Good
                # 60-80nm = Poor (warning)
                # >80nm = Problem (strong rejection)
                if fwhm < 5.0:
                    continue  # Too narrow = noise spike or artifact
                if fwhm > 120.0:
                    continue  # Way too wide = not a resonance

                # Calculate quality score
                depth = abs(candidate_val)  # Transmission dip depth

                # FWHM scoring with updated thresholds
                if fwhm < FWHM_EXCELLENT_THRESHOLD_NM:  # <30nm
                    fwhm_score = 1.0  # Excellent
                elif fwhm < FWHM_GOOD_THRESHOLD_NM:  # 30-60nm
                    fwhm_score = 0.8  # Good
                elif fwhm < 80.0:  # 60-80nm
                    fwhm_score = 0.4  # Poor (warning level)
                else:  # >80nm
                    fwhm_score = 0.1  # Problem (strong penalty)

                # Wavelength range scoring
                # Prefer 590-670nm, allow 670-750nm with penalty
                if 590.0 <= candidate_wl <= 670.0:
                    wl_score = 1.0  # Normal range - no penalty
                elif 670.0 < candidate_wl <= 750.0:
                    # Extended range - allow but penalize
                    # Check if it's a gradual shift from previous peak
                    if channel in self._last_peak_wavelength:
                        prev_wl = self._last_peak_wavelength[channel]
                        shift = candidate_wl - prev_wl
                        if shift > 0 and shift < 15.0:
                            wl_score = 0.85  # Gradual shift - mild penalty
                        else:
                            wl_score = 0.6  # Jump or large shift - moderate penalty
                    else:
                        wl_score = 0.5  # First peak >670nm - strong penalty
                else:
                    wl_score = 0.3  # Outside expected range

                # Proximity to hint bonus (if hint provided)
                # This guides peak finding to the smoothed transmission minimum
                hint_bonus = 0.0
                if minimum_hint_nm is not None:
                    distance_to_hint = abs(candidate_wl - minimum_hint_nm)
                    if distance_to_hint < 5.0:  # Within 5nm of hint
                        hint_bonus = 0.3  # Strong preference
                    elif distance_to_hint < 10.0:  # Within 10nm of hint
                        hint_bonus = 0.15  # Moderate preference
                    elif distance_to_hint < 20.0:  # Within 20nm of hint
                        hint_bonus = 0.05  # Mild preference

                # Combine: FWHM (50%), depth (30%), wavelength range (20%) + hint bonus
                # FWHM is most important for validity, hint guides initial selection
                quality = (
                    0.5 * fwhm_score
                    + 0.3 * min(depth / 50.0, 1.0)
                    + 0.2 * wl_score
                    + hint_bonus
                )

                # Continuity checking - prevent sudden jumps
                if channel in self._last_peak_wavelength:
                    prev_wl = self._last_peak_wavelength[channel]
                    wl_diff = abs(candidate_wl - prev_wl)

                    # Penalize sudden jumps (gradual shifts are OK)
                    if wl_diff > 30.0:
                        quality *= 0.3  # Very strong penalty for large jump
                    elif wl_diff > 20.0:
                        quality *= 0.5  # Strong penalty
                    elif wl_diff > 15.0:
                        quality *= 0.7  # Moderate penalty
                    # wl_diff < 15nm = no penalty (gradual shift OK)

                candidates.append(
                    {
                        "wavelength": candidate_wl,
                        "fwhm": fwhm,
                        "quality": quality,
                        "depth": depth,
                        "fwhm_score": fwhm_score,
                        "wl_score": wl_score,
                    },
                )

            # Select best candidate
            warning = None
            if len(candidates) == 0:
                # All candidates rejected, use minimum_hint_nm if available, else absolute minimum
                if minimum_hint_nm is not None and 600.0 <= minimum_hint_nm <= 690.0:
                    # Use the hint calculated from smoothed transmission in SPR region
                    peak_wl = minimum_hint_nm
                    logger.debug(
                        f"QC: All candidates rejected, using minimum_hint_nm={peak_wl:.1f}nm",
                    )
                else:
                    # Fallback: find absolute minimum in CORE SPR region (600-690nm, not 590-750nm)
                    core_spr_mask = (wl_spr >= 600.0) & (wl_spr <= 690.0)
                    if np.any(core_spr_mask):
                        core_spec = spec_spr[core_spr_mask]
                        core_wl = wl_spr[core_spr_mask]
                        min_idx = np.argmin(core_spec)
                        peak_wl = core_wl[min_idx]
                        logger.debug(
                            f"QC: Using minimum in core SPR region (600-690nm): {peak_wl:.1f}nm",
                        )
                    else:
                        min_idx = np.argmin(spec_spr)
                        peak_wl = wl_spr[min_idx]
                        logger.debug(f"QC: Using absolute minimum: {peak_wl:.1f}nm")

                fwhm = self._calculate_fwhm(wl_spr, spec_spr, peak_wl)

                # Generate warning based on issue
                if fwhm is not None and fwhm > 80.0:
                    warning = f"PROBLEM: FWHM={fwhm:.1f}nm (>80nm) - poor coupling or air bubble"
                elif peak_wl > 670.0:
                    warning = (
                        f"Peak at {peak_wl:.1f}nm (>670nm) - all candidates rejected"
                    )

                result = {
                    "wavelength": peak_wl,
                    "fwhm": fwhm,
                    "quality": 0.2,
                    "candidates_found": len(minima_indices),
                    "warning": warning,
                }
            else:
                # Choose highest quality candidate
                best = max(candidates, key=lambda c: c["quality"])

                # Generate warnings for problematic conditions
                if best["fwhm"] > 80.0:
                    warning = f"PROBLEM: FWHM={best['fwhm']:.1f}nm (>80nm) - poor coupling detected"
                elif best["fwhm"] > 60.0:
                    warning = f"Warning: FWHM={best['fwhm']:.1f}nm (60-80nm) - coupling quality poor"
                elif first_peak_flag and best["wavelength"] > 670.0:
                    warning = f"FLAG: First peak at {best['wavelength']:.1f}nm (>670nm) - verify sensor condition"
                elif best["wavelength"] > 700.0:
                    # Check if gradual shift
                    if channel in self._last_peak_wavelength:
                        prev_wl = self._last_peak_wavelength[channel]
                        shift = best["wavelength"] - prev_wl
                        if shift > 15.0:
                            warning = f"Large shift: {prev_wl:.1f}nm → {best['wavelength']:.1f}nm (+{shift:.1f}nm)"
                    else:
                        warning = f"Peak at {best['wavelength']:.1f}nm (>700nm) - extended range"

                result = {
                    "wavelength": best["wavelength"],
                    "fwhm": best["fwhm"],
                    "quality": best["quality"],
                    "candidates_found": len(candidates),
                    "warning": warning,
                }

            # Update tracking history
            self._last_peak_wavelength[channel] = result["wavelength"]
            self._fwhm_values[channel] = result["fwhm"]

            # Log warnings if present
            if warning:
                logger.warning(f"Channel {channel}: {warning}")

            return result

        except Exception as e:
            logger.warning(f"Peak validation failed for channel {channel}: {e}")
            return default_result

    def _fourier_peak_finding(
        self,
        wavelength: np.ndarray,
        spectrum: np.ndarray,
        channel: str,
        minimum_hint_nm: float | None = None,
    ) -> float:
        """STREAMLINED: Direct Fourier transform peak finding - NO PIPELINE WRAPPERS.

        This is the ONLY peak finding method used in production. All other pipeline
        dispatcher/registry/wrapper layers have been REMOVED for simplicity.

        Algorithm:
        1. Extract SPR region (620-680nm) to avoid edge artifacts
        2. Apply SNR-aware weighting based on S-pol reference intensity
        3. Compute Fourier coefficients using DST with denoising weights
        4. Calculate derivative using IDCT
        5. Find zero-crossing near minimum hint
        6. Refine position using linear regression

        Args:
            wavelength: Wavelength array (nm)
            spectrum: Transmission spectrum (P/S ratio %) - already SG-filtered
            channel: Channel identifier
            minimum_hint_nm: Pre-calculated minimum position hint (optional)

        Returns:
            Resonance wavelength in nm

        """
        from scipy.fftpack import dst, idct
        from scipy.stats import linregress

        from affilabs.settings.settings import FOURIER_ALPHA

        # DIAGNOSTIC: Track inputs to detect if function receives fresh data
        try:
            spectrum_hash = hash(spectrum.tobytes())
            if not hasattr(self, "_peak_input_hash"):
                self._peak_input_hash = {}
            if channel in self._peak_input_hash:
                if self._peak_input_hash[channel] == spectrum_hash:
                    pass
            self._peak_input_hash[channel] = spectrum_hash
        except Exception:
            pass

        try:
            # ═══════════════════════════════════════════════════════════════════════
            # STEP 1: Extract SPR region (620-680nm) to avoid edge artifacts
            # ═══════════════════════════════════════════════════════════════════════
            spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
            if not np.any(spr_mask):
                return minimum_hint_nm if minimum_hint_nm else 650.0

            spr_wavelengths = wavelength[spr_mask]
            spr_transmission = spectrum[spr_mask]

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 2: Apply SNR-aware weighting (CRITICAL for noise suppression)
            # ═══════════════════════════════════════════════════════════════════════
            s_ref = None
            if self.calibration_data and self.calibration_data.s_pol_ref:
                s_ref = self.calibration_data.s_pol_ref.get(channel)

            if s_ref is not None and len(s_ref) == len(spectrum):
                spr_s_reference = s_ref[spr_mask]
                # Calculate SNR weights: higher S-pol intensity → better signal quality
                s_min, s_max = np.min(spr_s_reference), np.max(spr_s_reference)
                if s_max > s_min:
                    normalized_s = (spr_s_reference - s_min) / (s_max - s_min)
                    snr_weights = 1.0 + 0.3 * normalized_s  # 30% adjustment strength
                    snr_weights = snr_weights / np.mean(
                        snr_weights,
                    )  # Normalize to mean=1.0
                    weighted_spectrum = spr_transmission * snr_weights
                else:
                    weighted_spectrum = spr_transmission
            else:
                weighted_spectrum = spr_transmission

            # Find minimum hint within SPR region
            hint_index = np.argmin(weighted_spectrum)

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 3: Calculate Fourier coefficients with denoising weights
            # ═══════════════════════════════════════════════════════════════════════
            n = len(weighted_spectrum)
            n_inner = n - 1

            # Fourier denoising weights: alpha=9000 (original 2nm baseline performance)
            phi = np.pi / n_inner * np.arange(1, n_inner)
            phi2 = phi**2
            fourier_weights = phi / (1 + FOURIER_ALPHA * phi2 * (1 + phi2))

            # Calculate Fourier coefficients
            fourier_coeff = np.zeros_like(weighted_spectrum)
            fourier_coeff[0] = 2 * (weighted_spectrum[-1] - weighted_spectrum[0])

            # Apply DST with linear detrending
            detrended = (
                weighted_spectrum[1:-1]
                - np.linspace(
                    weighted_spectrum[0],
                    weighted_spectrum[-1],
                    n,
                )[1:-1]
            )
            fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 4: Calculate derivative using IDCT
            # ═══════════════════════════════════════════════════════════════════════
            derivative = idct(fourier_coeff, 1)

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 5: Find zero-crossing near minimum hint
            # ═══════════════════════════════════════════════════════════════════════
            search_window = 50  # Tightened from 200 to ±50 points for local focus
            search_start = max(0, hint_index - search_window)
            search_end = min(len(derivative), hint_index + search_window)

            derivative_window = derivative[search_start:search_end]
            zero_local = derivative_window.searchsorted(0)
            zero = search_start + zero_local

            # ═══════════════════════════════════════════════════════════════════════
            # STEP 6: Refine position using linear regression
            # ═══════════════════════════════════════════════════════════════════════
            # Window size matches Step 5 for consistent local focus
            window_size = 50  # Tightened to ±50 points for local regression
            start = max(zero - window_size, 0)
            end = min(zero + window_size, n - 1)

            line = linregress(spr_wavelengths[start:end], derivative[start:end])
            peak_wavelength = -line.intercept / line.slope

            # DIAGNOSTIC: Log detailed Fourier algorithm internals for first 5 acquisitions
            if not hasattr(self, "_fourier_debug_count"):
                self._fourier_debug_count = {}
            if channel not in self._fourier_debug_count:
                self._fourier_debug_count[channel] = 0
            self._fourier_debug_count[channel] += 1

            if self._fourier_debug_count[channel] <= 5:
                pass

            # Validate result is within SPR region
            if (
                peak_wavelength < 620.0
                or peak_wavelength > 680.0
                or np.isnan(peak_wavelength)
            ):
                # Fourier failed - use hint
                if minimum_hint_nm and 620.0 <= minimum_hint_nm <= 680.0:
                    peak_wavelength = minimum_hint_nm
                else:
                    # Final fallback: use weighted spectrum minimum from Step 2
                    peak_wavelength = spr_wavelengths[hint_index]

            # Track last peak value for internal diagnostics
            if not hasattr(self, "_last_peak_value"):
                self._last_peak_value = {}
            self._last_peak_value[channel] = peak_wavelength

            # DEBUG: Log results periodically
            if not hasattr(self, "_peak_log_count"):
                self._peak_log_count = {}
            if channel not in self._peak_log_count:
                self._peak_log_count[channel] = 0
            self._peak_log_count[channel] += 1

            if (
                self._peak_log_count[channel] <= 3
                or self._peak_log_count[channel] % 10 == 0
            ):
                pass

            return float(peak_wavelength)

        except Exception:
            import traceback

            traceback.print_exc()
            # Fallback
            if minimum_hint_nm:
                return float(minimum_hint_nm)
            return 650.0

    def _calculate_fwhm(
        self, wavelengths: np.ndarray, transmission: np.ndarray, peak_wl: float,
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

    def _compute_spectral_correction(self) -> None:
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

            from affilabs.utils.device_integration import (
                get_device_optical_calibration_path,
            )
            from settings import (
                AFTERGLOW_AUTO_MODE,
                AFTERGLOW_FAST_THRESHOLD_MS,
                AFTERGLOW_SLOW_THRESHOLD_MS,
                LED_DELAY,
                LED_POST_DELAY,
            )

            optical_cal_path = get_device_optical_calibration_path()

            if optical_cal_path and optical_cal_path.exists():
                self.afterglow_correction = AfterglowCorrection(optical_cal_path)

                # Generate afterglow curves for QC report (at LED_DELAY timing)
                if (
                    self.calibration_data
                    and self.calibration_data.wavelengths is not None
                    and len(self.calibration_data.wavelengths) > 0
                    and self.calibration_data.s_pol_ref
                ):
                    ch_list = list(self.calibration_data.s_pol_ref.keys())
                    self.afterglow_curves = {}
                    for i, ch in enumerate(ch_list):
                        if i > 0:  # First channel has no previous channel
                            prev_ch = ch_list[i - 1]
                            try:
                                # Calculate scalar afterglow correction value
                                correction_value = self.afterglow_correction.calculate_correction(
                                    previous_channel=prev_ch,
                                    integration_time_ms=float(
                                        self.calibration_data.s_mode_integration_time,
                                    ),
                                    delay_ms=LED_DELAY * 1000,  # Convert to ms
                                )
                                # Create flat array (afterglow is uniform across wavelengths)
                                self.afterglow_curves[ch] = np.full_like(
                                    self.calibration_data.wavelengths,
                                    correction_value,
                                    dtype=float,
                                )
                                logger.debug(
                                    f"Afterglow for ch {ch.upper()} from {prev_ch.upper()}: {correction_value:.1f} counts",
                                )
                            except Exception as e:
                                logger.debug(
                                    f"Could not calculate afterglow for ch {ch}: {e}",
                                )
                                self.afterglow_curves[ch] = np.zeros_like(
                                    self.calibration_data.wavelengths,
                                )
                        else:
                            # First channel has no previous channel - no afterglow
                            self.afterglow_curves[ch] = np.zeros_like(
                                self.calibration_data.wavelengths,
                            )
                    logger.info("✅ Afterglow curves generated for QC report")

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

    def _update_calibration_intelligence(self, calibration_data: dict) -> None:
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
        self, channel: str, wavelength: float, snr: float, transmission_quality: float,
    ) -> None:
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

    def clear_buffers(self) -> None:
        """Clear all data buffers."""
        for ch in ["a", "b", "c", "d"]:
            self.channel_buffers[ch].clear()
            self.time_buffers[ch].clear()
        logger.info("Data buffers cleared")
