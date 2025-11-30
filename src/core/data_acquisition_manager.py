"""Data Acquisition Manager - Handles spectrum acquisition and processing.

ARCHITECTURE OVERVIEW (Matches Calibration Exactly):
====================================================

This module follows the same 4-layer architecture as calibration_6step.py:

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

from PySide6.QtCore import QObject, Signal, QTimer
from utils.logger import logger
from typing import Optional, Dict
import threading
import gc

# Calibration data model
from core.calibration_data import CalibrationData
from core.spectrum_preprocessor import SpectrumPreprocessor
from core.transmission_processor import TransmissionProcessor

# ✅ OPTIMIZATION: Disable automatic GC to eliminate random 10-50ms pauses
# Manual GC will be called periodically during safe times
gc.disable()
import time
import numpy as np
import queue

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
    spectrum_acquired = Signal(dict)  # {channel: str, wavelength: float, intensity: float, timestamp: float}
    # CALIBRATION SIGNALS REMOVED - handled by CalibrationManager
    # calibration_started = Signal()
    # calibration_complete = Signal(dict)
    # calibration_failed = Signal(str)
    # calibration_progress = Signal(str)
    acquisition_error = Signal(str)  # Error message
    acquisition_started = Signal()  # Emitted when acquisition loop starts
    acquisition_stopped = Signal()  # Emitted when acquisition loop stops

    def __init__(self, hardware_mgr):
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

        # Derived/computed data (not part of calibration)
        self.fourier_weights = {}  # {channel: weights_array} - computed from calibration
        self.spectral_correction = {}  # {channel: correction_weights} - computed

        # Runtime state (acquisition-specific, not calibration)
        self.ch_error_list = []  # Failed channels from calibration

        # LED timing (from device config, can override calibration_data)
        self._pre_led_delay_ms = None  # PRE LED delay (device-specific, loaded from config)
        self._post_led_delay_ms = None  # POST LED delay (device-specific, loaded from config)
        self._led_overlap_active = False  # Track if LED is already ON from previous overlap
        self._led_overlap_channel = None  # Track which LED is ON from overlap
        self._led_overlap_start_time = None  # Track when overlap LED was turned ON

        # Timing jitter tracking for SNR optimization
        self._timing_jitter_stats = {ch: [] for ch in ['a', 'b', 'c', 'd']}
        self._jitter_window_size = 100  # Track last 100 measurements per channel
        self._last_jitter_report = 0  # Time of last jitter statistics report

        # S/P orientation validation tracking
        self._sp_validation_results = {}  # {channel: {orientation_correct, confidence, peak_wl, timestamp}}
        self._sp_orientation_validated = set()  # Set of channels validated during runtime

        # FWHM tracking for quality control
        self._fwhm_values = {}  # {channel: fwhm_nm}
        self._last_peak_wavelength = {}  # {channel: wavelength_nm} for continuity checking

        # Batched acquisition settings (from settings.py)
        from settings import BATCH_SIZE
        from collections import deque
        self.batch_size = BATCH_SIZE  # Minimum raw spectra to buffer before processing (reduces USB overhead)
        # ✅ OPTIMIZATION: Use deque for O(1) append without reallocation (saves 1-2ms per batch)
        self._spectrum_batch = {
            'a': deque(maxlen=BATCH_SIZE * 2),
            'b': deque(maxlen=BATCH_SIZE * 2),
            'c': deque(maxlen=BATCH_SIZE * 2),
            'd': deque(maxlen=BATCH_SIZE * 2)
        }
        self._batch_timestamps = {
            'a': deque(maxlen=BATCH_SIZE * 2),
            'b': deque(maxlen=BATCH_SIZE * 2),
            'c': deque(maxlen=BATCH_SIZE * 2),
            'd': deque(maxlen=BATCH_SIZE * 2)
        }

        # Load LED timing delays from device config (device-specific, persisted)
        self._load_led_delays_from_config()

        # Thread-safe queue for worker → main thread communication
        self._spectrum_queue = queue.Queue(maxsize=1000)  # Buffer up to 1000 spectrum events

        # QTimer to process queue in main thread (initialized here to ensure main thread ownership)
        self._queue_timer = QTimer()
        self._queue_timer.timeout.connect(self._process_spectrum_queue)

        # Acquisition state
        self._acquiring = False
        self._acquisition_thread = None
        self._stop_acquisition = threading.Event()
        self._pause_acquisition = threading.Event()  # Pause flag (set=paused, clear=running)

        # Data buffers (using channel manager pattern)
        self.channel_buffers = {ch: [] for ch in ['a', 'b', 'c', 'd']}
        self.time_buffers = {ch: [] for ch in ['a', 'b', 'c', 'd']}

        # Spectrum processor (will be imported when needed)
        self.spectrum_processor = None

        logger.debug("DataAcquisitionManager initialized")

    def _load_led_delays_from_config(self):
        """Load PRE/POST LED delays from device configuration.

        This is called during initialization to set initial defaults.
        These values will be overridden by apply_calibration() with the
        actual delays used during calibration (single source of truth).

        Falls back to hard-coded defaults (45ms/5ms) if config not available.

        Note: Uses silent loading to avoid verbose logging at startup.
        Device config summary will be logged when hardware is powered on.
        """
        try:
            from utils.device_configuration import DeviceConfiguration
            device_serial = getattr(self.hardware_mgr.usb, 'serial_number', None) if self.hardware_mgr.usb else None

            # Silent load - don't trigger verbose config summary at startup
            device_config = DeviceConfiguration(device_serial=device_serial, silent_load=True)

            self._pre_led_delay_ms = device_config.get_pre_led_delay_ms()
            self._post_led_delay_ms = device_config.get_post_led_delay_ms()

            logger.debug(f"Loaded LED timing delays from device config: PRE={self._pre_led_delay_ms}ms, POST={self._post_led_delay_ms}ms")
        except Exception as e:
            # Fall back to defaults if config loading fails
            self._pre_led_delay_ms = 45.0
            self._post_led_delay_ms = 5.0
            logger.debug(f"Using default LED delays: PRE=45ms, POST=5ms")

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
                raise ValueError("calibration_data cannot be None")

            # Validate calibration data integrity
            if not calibration_data.validate():
                raise ValueError("Calibration data validation failed")

            # Store calibration data (single source of truth)
            self.calibration_data = calibration_data

            # Log key parameters
            logger.info(f"  Integration Time: {calibration_data.integration_time}ms")
            logger.info(f"  Scans per Spectrum: {calibration_data.num_scans}")
            logger.info(f"  Calibrated Channels: {calibration_data.get_channels()}")
            logger.info(f"  Wavelength Range: {calibration_data.wavelength_min:.1f}-{calibration_data.wavelength_max:.1f}nm")
            logger.info(f"  SPR Range Indices: {calibration_data.wave_min_index}-{calibration_data.wave_max_index}")

            # 🔍 CRITICAL DEBUG: Check LED intensities
            print("\n🔍 CRITICAL DEBUG - CALIBRATION DATA CHECK:")
            print(f"  S-mode integration time: {calibration_data.s_mode_integration_time}ms")
            print(f"  P-mode integration time: {calibration_data.p_integration_time}ms")
            print(f"  S-mode LED intensities: {calibration_data.s_mode_intensities}")
            print(f"  P-mode LED intensities: {calibration_data.p_mode_intensities}")
            print(f"  Dark noise: {np.mean(calibration_data.dark_noise) if calibration_data.dark_noise is not None else 'None':.1f} (mean)")
            print(f"  Number of scans: {calibration_data.num_scans}")
            print()

            # Compute Fourier weights for each channel (derived from ref_sig)
            logger.info("Computing Fourier weights for peak finding...")
            self.fourier_weights = {}
            for ch in calibration_data.get_channels():
                ref_spectrum = calibration_data.s_pol_ref.get(ch)
                if ref_spectrum is not None:
                    try:
                        # Use SPR region for Fourier analysis
                        spr_spectrum = ref_spectrum[calibration_data.wave_min_index:calibration_data.wave_max_index]
                        weights = np.fft.rfft(spr_spectrum)
                        self.fourier_weights[ch] = np.abs(weights)
                        logger.debug(f"  Channel {ch}: Fourier weights computed (shape={weights.shape})")
                    except Exception as e:
                        logger.warning(f"  Channel {ch}: Failed to compute Fourier weights: {e}")
                        self.fourier_weights[ch] = None

            # Compute spectral correction weights (normalize LED profiles)
            logger.info("Computing spectral correction weights...")
            self.spectral_correction = {}
            for ch in calibration_data.get_channels():
                ref_spectrum = calibration_data.s_pol_ref.get(ch)
                if ref_spectrum is not None:
                    try:
                        # Normalize to mean=1 for correction
                        spr_spectrum = ref_spectrum[calibration_data.wave_min_index:calibration_data.wave_max_index]
                        mean_intensity = np.mean(spr_spectrum)
                        if mean_intensity > 0:
                            correction = spr_spectrum / mean_intensity
                            self.spectral_correction[ch] = correction
                            logger.debug(f"  Channel {ch}: Spectral correction computed")
                        else:
                            logger.warning(f"  Channel {ch}: Zero mean intensity, skipping correction")
                            self.spectral_correction[ch] = None
                    except Exception as e:
                        logger.warning(f"  Channel {ch}: Failed to compute spectral correction: {e}")
                        self.spectral_correction[ch] = None

            # Update LED timing delays from calibration data (single source of truth)
            # These are the delays that were actually used during calibration
            self._pre_led_delay_ms = calibration_data.pre_led_delay_ms
            self._post_led_delay_ms = calibration_data.post_led_delay_ms
            logger.info(f"✅ LED timing updated: PRE={self._pre_led_delay_ms}ms, POST={self._post_led_delay_ms}ms")

            # Mark as calibrated (enables start_acquisition)
            self.calibrated = True

            logger.info("✅ Calibration data applied successfully")
            logger.info(f"✅ Acquisition manager ready for live measurements")
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
    # ========================================================================

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
            if not self.calibration_data:
                logger.error("❌ FATAL: calibration_data is None - cannot start acquisition")
                self.acquisition_error.emit("Calibration data missing. Please recalibrate.")
                return

            if not self.calibration_data.s_pol_ref or len(self.calibration_data.s_pol_ref) == 0:
                logger.error("❌ FATAL: S-pol reference spectra are empty - cannot start acquisition")
                self.acquisition_error.emit("S-pol reference data missing. Please recalibrate.")
                return

            if self.calibration_data.wavelengths is None or len(self.calibration_data.wavelengths) == 0:
                logger.error("❌ FATAL: wavelength data is empty - cannot start acquisition")
                self.acquisition_error.emit("Wavelength calibration missing. Please recalibrate.")
                return

            # Validate ref_sig shapes match wavelength data
            invalid_channels = []
            for ch, ref_spectrum in self.calibration_data.s_pol_ref.items():
                if ref_spectrum is None or len(ref_spectrum) != len(self.calibration_data.wavelengths):
                    invalid_channels.append(ch)
                    logger.error(f"❌ Channel {ch}: Invalid ref_sig (len={len(ref_spectrum) if ref_spectrum is not None else 'None'} vs wave={len(self.calibration_data.wavelengths)})")

            if invalid_channels:
                logger.error(f"❌ FATAL: Invalid calibration data for channels: {invalid_channels}")
                self.acquisition_error.emit(f"Calibration corrupted for channels {invalid_channels}. Please recalibrate.")
                return

            logger.info("✅ Calibration data validation passed")

            if self._acquiring:
                logger.warning("Acquisition already running")
                return

            logger.info("=" * 80)
            logger.info("🚀 STARTING LIVE ACQUISITION")
            logger.info("=" * 80)
            logger.info("Using calibration parameters (method-agnostic):")
            logger.info(f"  Integration Time: {self.calibration_data.integration_time}ms")
            logger.info(f"  Scans per Spectrum: {self.calibration_data.num_scans}")
            logger.info(f"  P-mode LED Intensities: {self.calibration_data.p_mode_intensities}")
            logger.info(f"  S-mode LED Intensities: {self.calibration_data.s_mode_intensities}")
            logger.info("")
            logger.info("CONSISTENCY GUARANTEE: Live data will match calibration QC")
            logger.info("=" * 80)
            logger.info("")

            # Ensure any previous acquisition thread is fully stopped
            if self._acquisition_thread and self._acquisition_thread.is_alive():
                logger.warning("Previous acquisition thread still running - waiting for cleanup...")
                self._stop_acquisition.set()
                self._acquisition_thread.join(timeout=3.0)
                if self._acquisition_thread.is_alive():
                    logger.error("Failed to stop previous acquisition thread - forcing new start")

            # ✨ CRITICAL: Switch polarizer to P-mode ONCE before starting acquisition
            # S-ref and dark were already measured during calibration and are reused
            try:
                ctrl = self.hardware_mgr.ctrl
                if ctrl and hasattr(ctrl, 'set_mode'):
                    logger.info("🔄 Switching polarizer to P-mode for live measurements...")
                    ctrl.set_mode('p')
                    time.sleep(0.4)  # Wait for servo to settle
                    logger.info("✅ Polarizer in P-mode - using calibrated S-ref and dark")
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer: {e}")

            # Clear batch buffers for fresh start
            for ch in ['a', 'b', 'c', 'd']:
                self._spectrum_batch[ch].clear()
                self._batch_timestamps[ch].clear()

            # Defer thread start to event loop to ensure all UI updates
            # from calibration completion have finished on main thread.
            self._acquiring = True
            self._stop_acquisition.clear()
            self._pause_acquisition.clear()

            # Start queue processing timer (runs in main thread)
            logger.info("Starting queue processing timer...")
            self._queue_timer.start(10)  # Process queue every 10ms

            # Diagnostic: verify calibration data is present
            logger.info(f"[ACQ] Starting acquisition with: wave_data={'present' if self.calibration_data and self.calibration_data.wavelengths is not None else 'MISSING'}, ref_sig={'present' if self.calibration_data and self.calibration_data.s_pol_ref else 'MISSING'}")

            def _launch_worker():
                try:
                    if not self._acquiring or self._stop_acquisition.is_set():
                        logger.debug("[DAQ] Acquisition canceled before worker launch")
                        return
                    logger.info("🚀 [DAQ] Launching acquisition worker thread")

                    # Emit signal BEFORE starting worker thread (safer)
                    self.acquisition_started.emit()
                    logger.info("✅ [DAQ] Acquisition started signal emitted")

                    self._acquisition_thread = threading.Thread(target=self._acquisition_worker, daemon=True, name="AcquisitionWorker")
                    self._acquisition_thread.start()
                    logger.info("✅ [DAQ] Acquisition worker thread launched")
                except Exception as e:
                    logger.error(f"❌ CRASH in _launch_worker: {e}", exc_info=True)
                    import traceback
                    try:
                        print(traceback.format_exc())
                    except:
                        print(f"Error: {e}")

            logger.info("Scheduling worker launch in 50ms...")
            QTimer.singleShot(50, _launch_worker)  # Small delay for UI thread to finish calibration updates
            logger.info("✅ start_acquisition completed successfully")
        except Exception as e:
            logger.error(f"❌ CRASH in start_acquisition: {e}", exc_info=True)
            import traceback
            try:
                print(traceback.format_exc())
            except:
                print(f"Error: {e}")

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

        # Emergency shutdown all LEDs (V1.1+ firmware)
        try:
            ctrl = self.hardware_mgr.ctrl
            if ctrl and hasattr(ctrl, 'emergency_shutdown'):
                ctrl.emergency_shutdown()
                logger.info("✅ Emergency shutdown - all LEDs off")
        except Exception as e:
            logger.debug(f"Emergency shutdown failed (non-critical): {e}")

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

        Dynamic throughput adjustment:
        - Batch processing outputs 3 spectra/channel every ~2.4s (12 total)
        - UI updates at 10ms intervals (100 Hz)
        - Processes up to 50 items/tick to prevent queue accumulation
        - With 12 spectra every 2.4s = 5 Hz input rate
        - 100 Hz × 50 items = 5000 Hz output capacity >> 5 Hz input
        """
        try:
            # Dynamic processing based on queue depth
            queue_depth = self._spectrum_queue.qsize()

            # Adaptive batch size: process more items when queue is filling up
            if queue_depth > 500:  # Queue >50% full - URGENT
                max_items = 100  # Process 100 items/tick (aggressive drain)
            elif queue_depth > 200:  # Queue >20% full - WARNING
                max_items = 50  # Process 50 items/tick (fast drain)
            elif queue_depth > 50:  # Queue building up
                max_items = 30  # Process 30 items/tick (moderate)
            else:  # Normal operation
                max_items = 20  # Process 20 items/tick (smooth display)

            items_processed = 0

            while items_processed < max_items:
                try:
                    data = self._spectrum_queue.get_nowait()

                    # Check if this is an error message (special key '_error')
                    if isinstance(data, dict) and '_error' in data:
                        self.acquisition_error.emit(data['_error'])
                    else:
                        # Regular spectrum data
                        self.spectrum_acquired.emit(data)

                    items_processed += 1
                except queue.Empty:
                    break  # Queue empty, done for this tick

            # Log queue depth if accumulating (debug)
            if queue_depth > 100 and items_processed > 0:
                print(f"[QUEUE] Depth={queue_depth}, processed={items_processed}, remaining={self._spectrum_queue.qsize()}")

        except Exception as e:
            logger.error(f"Error processing spectrum queue: {e}")


    # ========================================================================
    # LAYER 2: COORDINATOR (_acquisition_worker)
    # ========================================================================
    # Orchestrates the acquisition loop:
    #   1. Pre-arm integration time (once before loop)
    #   2. Loop through channels
    #   3. Call Layer 3 (_acquire_raw_spectrum) for hardware acquisition
    #   4. Call Layer 4 (_process_spectrum) for processing
    #   5. Queue results for UI (Layer 1)
    # ========================================================================

    def _acquisition_worker(self):
        """LAYER 2: Main acquisition coordinator (background thread).

        Coordinates acquisition flow:
        1. Pre-arm detector (set integration time once)
        2. Loop through channels calling _acquire_raw_spectrum (Layer 3)
        3. Process spectra using _process_spectrum (Layer 4)
        4. Queue results for UI update

        Optimizations:
        - Pre-arm integration time (saves 21ms per cycle)
        - Batch LED commands (15x faster)
        - LED overlap strategy (saves 40ms per transition)
        """
        print("\n" + "="*70)
        print("ACQUISITION WORKER THREAD ENTERED - BATCH MODE")
        print("="*70)

        try:
            print("[Worker] Starting batched acquisition (12 spectra/batch)")

            print("\n" + "="*70)
            print("ACQUISITION WORKER STARTED")
            print("="*70)

            channels = ['a', 'b', 'c', 'd']
            consecutive_errors = 0
            max_consecutive_errors = 5
            cycle_count = 0
            BATCH_SIZE = 12  # 3 complete 4-channel cycles

            # Pre-flight check
            print(f"[Worker] Hardware check: ctrl={self.hardware_mgr.ctrl is not None}, usb={self.hardware_mgr.usb is not None}")
            print(f"[Worker] Calibration check: calibration_data={'present' if self.calibration_data else 'MISSING'}, channels={len(self.calibration_data.p_mode_intensities) if self.calibration_data else 0}")
            print(f"[Worker] Batch size: {BATCH_SIZE} spectra (3 cycles × 4 channels)")
            print(f"[Worker] TIMING JITTER OPTIMIZATION: Pre-armed integration, high-res timestamps, batch LEDs")

            # Prepare LED intensities for batch command
            led_a = self.calibration_data.p_mode_intensities.get('a', 0)
            led_b = self.calibration_data.p_mode_intensities.get('b', 0)
            led_c = self.calibration_data.p_mode_intensities.get('c', 0)
            led_d = self.calibration_data.p_mode_intensities.get('d', 0)
            print(f"[Worker] LED intensities: A={led_a}, B={led_b}, C={led_c}, D={led_d}")

            # ===================================================================
            # SMART PARAMETER ANALYSIS: Detect what's common across channels
            # ===================================================================
            # Integration time analysis
            integration_time = self.calibration_data.p_integration_time
            if not integration_time or integration_time <= 0:
                print(f"[Worker] Warning: P-mode integration time invalid ({integration_time}ms), falling back to S-mode")
                integration_time = self.calibration_data.s_mode_integration_time

            # Check if we have per-channel integration times (alternative mode)
            per_channel_integration = bool(self.calibration_data.channel_integration_times)
            if per_channel_integration:
                print(f"[Worker] ⚡ SMART MODE: Per-channel integration times detected")
                print(f"  Channel times: {self.calibration_data.channel_integration_times}")
            else:
                # Standard mode: Pre-arm integration time ONCE (optimization)
                print(f"[Worker] ⚡ SMART MODE: Common integration time detected ({integration_time}ms)")
                print(f"  Optimization: Pre-arming detector for all channels")
                try:
                    usb = self.hardware_mgr.usb
                    if usb:
                        usb.set_integration(integration_time)
                        print(f"  ✅ Pre-armed: Saves ~7ms per channel (21ms per cycle)")
                except Exception as e:
                    print(f"  ⚠️ Could not pre-arm: {e}")

            # Common parameters (same for all channels)
            num_scans = self.calibration_data.num_scans if self.calibration_data.num_scans and self.calibration_data.num_scans > 0 else 1
            pre_led_delay = self.calibration_data.pre_led_delay_ms if self.calibration_data.pre_led_delay_ms else self._pre_led_delay_ms
            post_led_delay = self.calibration_data.post_led_delay_ms if self.calibration_data.post_led_delay_ms else self._post_led_delay_ms

            print(f"[Worker] Common parameters:")
            print(f"  Number of scans: {num_scans}")
            print(f"  PRE LED delay: {pre_led_delay}ms")
            print(f"  POST LED delay: {post_led_delay}ms")
            print(f"[Worker] ⚡ Smart acquisition ready - mode-agnostic with auto-optimization")

            while not self._stop_acquisition.is_set():
                cycle_count += 1

                # Manual GC every 100 cycles (during safe time, not critical path)
                if cycle_count % 100 == 0:
                    gc.collect(generation=0)

                if cycle_count % 10 == 1:
                    print(f"[Worker] Batch cycle {cycle_count}")

                    # Periodic LED verification (V1.1+ firmware)
                    if self.hardware_mgr and self.hardware_mgr.ctrl and hasattr(self.hardware_mgr.ctrl, 'verify_led_state'):
                        try:
                            # Verify all LEDs are off between batches
                            expected_off = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            if not self.hardware_mgr.ctrl.verify_led_state(expected_off, tolerance=10):
                                print(f"[LED-STATUS] Warning: LEDs not fully off between batches")
                        except Exception:
                            pass

                try:
                    # Check if paused
                    if self._pause_acquisition.is_set():
                        time.sleep(0.1)
                        continue

                    batch_success = False
                    spectra_acquired = 0

                    # Acquire 12 spectra (3 complete cycles)
                    for batch_idx in range(3):  # 3 cycles of 4 channels = 12 spectra
                        if self._stop_acquisition.is_set():
                            break

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
                                    next_led_int = self.calibration_data.p_mode_intensities.get(next_ch)

                                # SMART: Get integration time (per-channel if available, else common)
                                ch_integration_time = integration_time
                                if per_channel_integration:
                                    ch_integration_time = self.calibration_data.channel_integration_times.get(ch, integration_time)

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
                                    pre_armed=not per_channel_integration  # Optimization flag
                                )

                                if raw_spectrum is not None:
                                    # Package data for processing
                                    spectrum_data = {
                                        'raw_spectrum': raw_spectrum,
                                        'wavelength': self.calibration_data.wavelengths.copy(),
                                        'timestamp': time.time()
                                    }

                                    timestamp = time.time()
                                    batch_success = True
                                    spectra_acquired += 1

                                    # Add to batch buffer
                                    self._spectrum_batch[ch].append(spectrum_data)
                                    self._batch_timestamps[ch].append(timestamp)

                            except Exception as e:
                                print(f"   [ERROR] Ch {ch} batch {batch_idx}: {e}")

                    # Process all accumulated spectra for each channel
                    if spectra_acquired >= 8:  # At least 2 cycles successful
                        for ch in channels:
                            if len(self._spectrum_batch[ch]) >= 3:  # Process if we have at least 3 spectra
                                try:
                                    self._process_and_emit_batch(ch)
                                    if cycle_count % 10 == 1:
                                        print(f"   [BATCH] Ch {ch}: Processed {len(self._spectrum_batch[ch])} spectra")
                                except Exception as e:
                                    print(f"   [ERROR] Ch {ch} batch processing: {e}")
                                    self._spectrum_batch[ch].clear()
                                    self._batch_timestamps[ch].clear()

                    if cycle_count % 10 == 1:
                        print(f"   [CYCLE] Acquired {spectra_acquired}/{BATCH_SIZE} spectra")

                    # Reset error counter if successful
                    if batch_success:
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                        print(f"[Worker] Batch {cycle_count}: FAILED - consecutive_errors={consecutive_errors}/{max_consecutive_errors}")

                        if consecutive_errors >= max_consecutive_errors:
                            print(f"[Worker] ❌ STOPPING: {max_consecutive_errors} consecutive failed batches")
                            try:
                                self._spectrum_queue.put_nowait({'_error': "Hardware communication lost - stopping acquisition"})
                            except queue.Full:
                                pass
                            self._stop_acquisition.set()
                            break

                    # Minimal delay between batch cycles for timing precision
                    # Old: 10ms (blocked acquisition for no reason)
                    # New: 1ms (allows faster batch processing, better jitter)
                    time.sleep(0.001)

                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        try:
                            self._spectrum_queue.put_nowait({'_error': f"Too many errors: {e}"})
                        except queue.Full:
                            pass
                        self._stop_acquisition.set()
                        break
                    time.sleep(0.5)

        except Exception as e:
            # Top-level exception handler - catch ANY uncaught exception
            import traceback
            error_msg = f"FATAL: Acquisition worker crashed: {e}\n{traceback.format_exc()}"
            print(error_msg)  # Print to console
            try:
                self._spectrum_queue.put_nowait({'_error': error_msg})
            except:
                pass

    def _check_hardware(self) -> bool:
        """Check if required hardware is connected."""
        return (
            self.hardware_mgr.ctrl is not None and
            self.hardware_mgr.usb is not None
        )

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
        for spectrum_data, timestamp in zip(batch, timestamps):
            try:
                # Process spectrum (filtering, peak finding)
                processed = self._process_spectrum(channel, spectrum_data)

                # Buffer the data
                self.channel_buffers[channel].append(processed['wavelength'])
                self.time_buffers[channel].append(timestamp)

                # Put processed data in queue instead of emitting directly
                data = {
                    'channel': channel,
                    'wavelength': processed['wavelength'],
                    'intensity': processed['intensity'],
                    'full_spectrum': processed.get('full_spectrum'),
                    'raw_spectrum': processed.get('raw_spectrum'),  # P-mode spectrum for transmission calc
                    'transmission_spectrum': processed.get('transmission_spectrum'),  # P/S ratio
                    'timestamp': timestamp,
                    'is_preview': False  # Real processed data
                }

                try:
                    self._spectrum_queue.put_nowait(data)
                except queue.Full:
                    pass  # Queue full, drop this data point

            except Exception as e:
                # Removed logger.error to prevent Qt threading issues
                pass  # Silent failure to avoid Qt threading crashes

        # Clear the batch buffers
        self._spectrum_batch[channel].clear()
        self._batch_timestamps[channel].clear()

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

    def _acquire_raw_spectrum(
        self,
        channel: str,
        led_intensity: int,
        integration_time_ms: float,
        num_scans: int,
        pre_led_delay_ms: float,
        post_led_delay_ms: float,
        next_channel: Optional[str] = None,
        next_led_intensity: Optional[int] = None,
        pre_armed: bool = False
    ) -> Optional[np.ndarray]:
        """LAYER 3: Acquire raw spectrum from detector (hardware only, no processing).

        SMART ACQUISITION with AUTO-OPTIMIZATION:
        - Automatically detects when all channels share the same integration time
        - Uses pre-arm optimization (skip set_integration) when possible
        - Falls back to per-channel integration time setting when needed
        - Coordinator analyzes calibration data and sets 'pre_armed' flag

        MODE-AGNOSTIC DESIGN:
        All parameters are passed explicitly to support different calibration modes
        (standard, alternative, fast-track, etc.) with potentially different:
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
            # - Fast-track mode: Optimized integration times
            if not pre_armed:
                # Per-channel mode: Set integration time each time
                try:
                    usb.set_integration(integration_time_ms)
                except Exception as e:
                    return None
            # else: Integration time already pre-armed (optimization - saves ~7ms)

            # ===================================================================
            # STEP 1: Set LED Intensity (Batch Command - matches calibration)
            # ===================================================================
            led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
            led_values[channel] = led_intensity

            # LED Overlap Optimization: Check if LED already ON from previous channel
            led_on_time = None
            led_already_on = False

            from settings import LED_OVERLAP_MS

            if self._led_overlap_active and self._led_overlap_channel == channel and LED_OVERLAP_MS > 0:
                # LED was turned ON during previous channel's POST delay
                led_already_on = True
                led_on_time = self._led_overlap_start_time

                # Reset overlap tracking
                self._led_overlap_active = False
                self._led_overlap_channel = None
            else:
                # Normal flow: Turn on LED now
                try:
                    success = ctrl.set_batch_intensities(
                        a=led_values['a'],
                        b=led_values['b'],
                        c=led_values['c'],
                        d=led_values['d']
                    )

                    led_on_time = time.perf_counter()

                    if not success:
                        return None

                except Exception as e:
                    return None

            # ===================================================================
            # STEP 2: Wait for LED Stabilization (PRE_LED_DELAY_MS)
            # ===================================================================
            # Use delay passed as parameter (mode-specific or device-specific)
            if led_already_on and led_on_time:
                # LED already on from overlap - calculate remaining PRE delay
                elapsed_pre_ms = (time.perf_counter() - led_on_time) * 1000.0
                remaining_pre_ms = max(0, pre_led_delay_ms - elapsed_pre_ms)
                if remaining_pre_ms > 0:
                    time.sleep(remaining_pre_ms / 1000.0)
            else:
                # Standard PRE delay
                time.sleep(pre_led_delay_ms / 1000.0)

            # ===================================================================
            # STEP 3: Read Spectrum from Detector (with averaging if num_scans > 1)
            # ===================================================================
            # Use num_scans passed as parameter (mode-specific averaging strategy)
            detector_read_start = time.perf_counter()

            try:
                if num_scans > 1:
                    spectra = []
                    for _ in range(num_scans):
                        spectrum = usb.read_intensity()
                        if spectrum is not None:
                            spectra.append(spectrum)
                    if len(spectra) == 0:
                        return None
                    raw_spectrum = np.mean(spectra, axis=0)
                else:
                    raw_spectrum = usb.read_intensity()

            except ConnectionError:
                self.acquisition_error.emit("Spectrometer disconnected. Please reconnect and restart.")
                self.stop_acquisition()
                return None
            except Exception as e:
                return None

            if raw_spectrum is None:
                return None

            # Track timing jitter for SNR analysis
            if led_on_time is not None:
                led_to_detector_ms = (detector_read_start - led_on_time) * 1000.0
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
                if self.calibration_data.wave_min_index and self.calibration_data.wave_max_index:
                    raw_spectrum = raw_spectrum[self.calibration_data.wave_min_index:self.calibration_data.wave_max_index]
                else:
                    raw_spectrum = raw_spectrum[:len(self.calibration_data.wavelengths)]

            # ===================================================================
            # STEP 4: Wait for Afterglow Decay (POST_LED_DELAY_MS)
            # ===================================================================
            # Use delay passed as parameter (mode-specific or device-specific)
            # Turn off LED first
            try:
                ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            except Exception:
                pass

            # LED Overlap Strategy: Turn on next LED during POST delay
            if next_channel and next_led_intensity and LED_OVERLAP_MS > 0:
                # Wait for initial overlap period (afterglow decay)
                time.sleep(LED_OVERLAP_MS / 1000.0)

                # Turn on next LED (stabilizes during remaining POST time)
                if next_led_intensity > 0:
                    try:
                        next_led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                        next_led_values[next_channel] = next_led_intensity
                        ctrl.set_batch_intensities(**next_led_values)

                        # Track overlap state
                        self._led_overlap_active = True
                        self._led_overlap_channel = next_channel
                        self._led_overlap_start_time = time.perf_counter()
                    except Exception:
                        self._led_overlap_active = False
                        self._led_overlap_channel = None

                # Wait for remaining POST delay
                remaining_post_ms = post_led_delay_ms - LED_OVERLAP_MS
                if remaining_post_ms > 0:
                    time.sleep(remaining_post_ms / 1000.0)
            else:
                # Standard POST delay (no overlap)
                time.sleep(post_led_delay_ms / 1000.0)
                self._led_overlap_active = False
                self._led_overlap_channel = None

            # ===================================================================
            # Return RAW spectrum (NO processing - matches calibration pattern)
            # ===================================================================
            return raw_spectrum

        except Exception as e:
            return None

    def _report_timing_jitter(self):
        """Report LED-to-detector timing jitter statistics for SNR analysis.

        Lower jitter = better SNR due to more consistent LED illumination timing.
        Target: <1ms std dev for optimal spectroscopy performance.
        """
        try:
            print("\n" + "="*70)
            print("LED-TO-DETECTOR TIMING JITTER STATISTICS (SNR Analysis)")
            print("="*70)

            for ch in ['a', 'b', 'c', 'd']:
                jitter_data = self._timing_jitter_stats[ch]
                if len(jitter_data) < 10:  # Need at least 10 samples
                    continue

                import numpy as np
                mean_ms = np.mean(jitter_data)
                std_ms = np.std(jitter_data)
                min_ms = np.min(jitter_data)
                max_ms = np.max(jitter_data)

                # Assess jitter quality
                if std_ms < 0.5:
                    quality = "EXCELLENT"
                elif std_ms < 1.0:
                    quality = "GOOD"
                elif std_ms < 2.0:
                    quality = "ACCEPTABLE"
                else:
                    quality = "POOR - CHECK TIMING"

                print(f"Ch {ch.upper()}: {mean_ms:.2f}ms ± {std_ms:.2f}ms (min={min_ms:.2f}, max={max_ms:.2f}) [{quality}]")

            print("="*70)
            print("Target: <1ms std dev for optimal SNR")
            print("Lower jitter = more consistent LED timing = better spectroscopy")
            print("="*70 + "\n")

        except Exception as e:
            pass  # Silent fail - don't break acquisition

    def _apply_baseline_correction(self, transmission: np.ndarray, degree: int = 2) -> np.ndarray:
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

        except Exception as e:
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
        logger.info(f"LED delays updated: PRE={self._pre_led_delay_ms:.1f}ms, POST={self._post_led_delay_ms:.1f}ms")

    def _process_and_emit_batch(self, channel: str) -> None:
        """Process batch of spectra with vectorized operations and emit sequentially.

        Applies Savitzky-Golay filtering to entire batch for superior smoothing
        while preserving peak shapes. Emits points sequentially for smooth display.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
        """
        import numpy as np
        from scipy.signal import savgol_filter

        batch = self._spectrum_batch[channel]
        timestamps = self._batch_timestamps[channel]

        if len(batch) == 0:
            return

        # Process each spectrum in batch (vectorized where possible)
        wavelengths = []
        intensities = []
        processed_results = []  # Store full processed results

        for spectrum_data in batch:
            try:
                processed = self._process_spectrum(channel, spectrum_data)
                wavelengths.append(processed['wavelength'])
                intensities.append(processed['intensity'])
                processed_results.append(processed)  # Store for reuse
            except Exception as e:
                print(f"   [BATCH ERROR] Channel {channel}: Spectrum processing failed - {e}")
                continue

        if len(wavelengths) == 0:
            self._spectrum_batch[channel].clear()
            self._batch_timestamps[channel].clear()
            return

        # Convert to numpy array for vectorized filtering
        wavelength_array = np.array(wavelengths)  # Shape: (batch_size,)

        # Apply Savitzky-Golay filter if batch is large enough
        # SG filter requires window_length <= data length and odd
        if len(wavelength_array) >= 5:
            try:
                # Savitzky-Golay: polynomial smoothing that preserves peak shapes
                # window_length=5, polyorder=2 gives excellent smoothing without distortion
                filtered_wavelengths = savgol_filter(wavelength_array, window_length=5, polyorder=2)
            except Exception as e:
                print(f"   [SG FILTER FAILED] Channel {channel}: {e}, using raw data")
                filtered_wavelengths = wavelength_array
        else:
            # Batch too small for SG filter, use raw data
            filtered_wavelengths = wavelength_array

        # Emit each point sequentially for smooth display
        for i, (wl, timestamp) in enumerate(zip(filtered_wavelengths, timestamps)):
            # Buffer the data
            self.channel_buffers[channel].append(wl)
            self.time_buffers[channel].append(timestamp)

            # Get pre-calculated transmission and raw spectrum from processed results
            # This avoids redundant calculation (already done in _process_spectrum)
            if i < len(processed_results):
                transmission_spectrum = processed_results[i].get('transmission_spectrum')
                raw_spectrum = processed_results[i].get('raw_spectrum')
            else:
                transmission_spectrum = None
                raw_spectrum = None

            # Queue for UI emission
            data = {
                'channel': channel,
                'wavelength': float(wl),
                'intensity': float(intensities[i]) if i < len(intensities) else 0.0,
                'full_spectrum': raw_spectrum,
                'raw_spectrum': raw_spectrum,
                'transmission_spectrum': transmission_spectrum,  # Reused from _process_spectrum
                'wavelengths': self.calibration_data.wavelengths,
                'timestamp': timestamp,
                'is_preview': False,
                'batch_filtered': True  # Mark as batch-filtered
            }

            try:
                self._spectrum_queue.put_nowait(data)
            except queue.Full:
                pass  # Queue full, skip this point

        # Clear batch buffers
        self._spectrum_batch[channel].clear()
        self._batch_timestamps[channel].clear()

    # ========================================================================
    # LAYER 4: PROCESSING (Dark Subtraction + Transmission Calculation)
    # ========================================================================
    # This layer matches calibration_6step.py Step 6 processing exactly:
    #   1. Dark subtraction using SpectrumPreprocessor.process_polarization_data()
    #   2. Transmission calculation using TransmissionProcessor.process_single_channel()
    # Same functions, same parameters as calibration = same results
    # ========================================================================

    def _process_spectrum(self, channel: str, spectrum_data: Dict) -> Dict:
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
        try:
            # Get truly raw data from Layer 3 (hardware acquisition)
            wavelength = spectrum_data['wavelength']
            raw_intensity = spectrum_data['raw_spectrum']  # Truly raw from detector

            # LAYER 4: Apply dark subtraction using SpectrumPreprocessor (same as calibration)
            # This ensures consistent preprocessing between calibration and live data
            clean_spectrum = SpectrumPreprocessor.process_polarization_data(
                raw_spectrum=raw_intensity,
                dark_noise=self.calibration_data.dark_noise,
                channel_name=channel,
                verbose=False  # Suppress logging for performance
            )

            # Store clean spectrum (dark-corrected)
            raw_spectrum = clean_spectrum  # Ready for transmission calculation
            intensity = clean_spectrum  # For peak finding

            # LAYER 4: Calculate transmission spectrum using TransmissionProcessor (same as calibration)
            # This ensures consistent processing between calibration and live data
            transmission_spectrum = None
            if channel in self.calibration_data.s_pol_ref and self.calibration_data.s_pol_ref[channel] is not None:
                try:
                    ref_spectrum = self.calibration_data.s_pol_ref[channel]

                    # Get LED intensities
                    p_led = self.calibration_data.p_mode_intensities.get(channel, 255)
                    s_led = self.calibration_data.s_mode_intensities.get(channel, 200)

                    # Calculate transmission using unified processor (same as calibration Part C)
                    # clean_spectrum is now dark-corrected (processed by SpectrumPreprocessor above)
                    transmission_spectrum = TransmissionProcessor.process_single_channel(
                        p_pol_clean=clean_spectrum,  # Clean spectrum from SpectrumPreprocessor
                        s_pol_ref=ref_spectrum,      # Clean S-pol reference from calibration
                        led_intensity_s=s_led,
                        led_intensity_p=p_led,
                        wavelengths=self.calibration_data.wavelengths,
                        apply_sg_filter=True,
                        baseline_method='percentile',  # Same as calibration
                        baseline_percentile=95.0,      # Same as calibration
                        verbose=False  # No logging for live acquisition (performance)
                    )

                    # Debug log LED correction (throttled)
                    if hasattr(self, '_transmission_debug_counter'):
                        self._transmission_debug_counter += 1
                    else:
                        self._transmission_debug_counter = 1
                    if self._transmission_debug_counter % 50 == 1:
                        print(f"[PROCESS] Ch {channel}: Using TransmissionProcessor with S={s_led}, P={p_led}")
                    if hasattr(self, '_transmission_debug_counter'):
                        self._transmission_debug_counter += 1
                    else:
                        self._transmission_debug_counter = 1
                    if self._transmission_debug_counter % 50 == 1:
                        print(f"[PROCESS] Ch {channel}: Using TransmissionProcessor with S={s_led}, P={p_led}")

                except Exception as e:
                    print(f"[PROCESS] Transmission calc failed: {e}")
                    import traceback
                    try:
                        print(traceback.format_exc())
                    except:
                        pass
                    transmission_spectrum = None

            # ═══════════════════════════════════════════════════════════════════════════
            # PEAK FINDING: Fourier Transform Method
            # ═══════════════════════════════════════════════════════════════════════════

            peak_input = transmission_spectrum if transmission_spectrum is not None else intensity

            # Calculate minimum hint from smoothed transmission to guide Fourier method
            # CRITICAL: Only search in SPR-relevant region (600-690nm) to avoid edge artifacts
            minimum_hint_nm = None
            if transmission_spectrum is not None and len(transmission_spectrum) > 0 and len(wavelength) == len(transmission_spectrum):
                # Find indices for SPR region
                spr_mask = (wavelength >= 600.0) & (wavelength <= 690.0)
                if np.any(spr_mask):
                    # Find minimum ONLY within SPR region (ignores edge curvature)
                    spr_transmission = transmission_spectrum[spr_mask]
                    spr_wavelengths = wavelength[spr_mask]
                    min_idx_in_region = np.argmin(spr_transmission)
                    minimum_hint_nm = spr_wavelengths[min_idx_in_region]

            # Find peak using selected pipeline method (Fourier/Centroid/Polynomial/etc.)
            if len(peak_input) > 0 and len(wavelength) == len(peak_input):
                peak_wavelength = self._find_resonance_peak(wavelength, peak_input, channel,
                                                           minimum_hint_nm=minimum_hint_nm)
            else:
                peak_wavelength = 650.0  # Default fallback

            # ═══════════════════════════════════════════════════════════════════════════
            # QUALITY CONTROL: Independent validation (runs for every spectrum)
            # ═══════════════════════════════════════════════════════════════════════════

            # Calculate FWHM and quality metrics (does NOT affect peak position)
            if len(peak_input) > 0 and len(wavelength) == len(peak_input):
                qc_result = self._find_validated_peak(wavelength, peak_input, channel,
                                                      minimum_hint_nm=minimum_hint_nm)
                fwhm_nm = qc_result['fwhm']
                qc_quality = qc_result['quality']
                qc_warning = qc_result.get('warning')
            else:
                fwhm_nm = None
                qc_quality = 0.0
                qc_warning = None

            # ✨ SENSOR IQ: Classify data quality based on wavelength range and FWHM
            from utils.sensor_iq import classify_spr_quality, log_sensor_iq, SensorIQLevel
            sensor_iq = classify_spr_quality(peak_wavelength, fwhm_nm, channel)

            # Log warnings for poor quality data (CRITICAL, POOR levels only)
            if sensor_iq.iq_level in [SensorIQLevel.CRITICAL, SensorIQLevel.POOR]:
                log_sensor_iq(sensor_iq, channel)

            # Log QC warnings if present
            if qc_warning:
                print(f"[QC] Channel {channel}: {qc_warning}")

            return {
                'wavelength': peak_wavelength,  # Fourier transform result
                'intensity': intensity[np.argmin(intensity)] if len(intensity) > 0 else 0.0,
                'full_spectrum': raw_spectrum,
                'raw_spectrum': raw_spectrum,
                'transmission_spectrum': transmission_spectrum,  # Already baseline-corrected and SG-filtered
                'fwhm': fwhm_nm,  # QC pipeline result
                'qc_quality': qc_quality,  # QC pipeline quality score
                'qc_warning': qc_warning,  # QC pipeline warning message
                'minimum_hint_nm': minimum_hint_nm,  # Hint from smoothed transmission (for diagnostics)
                'sensor_iq': sensor_iq  # ✨ Quality classification
            }

        except Exception as e:
            print(f"[PROCESS] ERROR in _process_spectrum: {e}")
            import traceback
            try:
                print(traceback.format_exc())
            except:
                pass
            # Return raw data on error
            return {
                'wavelength': 650.0,
                'intensity': 0.0,
                'full_spectrum': spectrum_data['intensity'],
                'raw_spectrum': spectrum_data['intensity']
            }

    def _find_validated_peak(self, wavelength: np.ndarray, spectrum: np.ndarray, channel: str,
                            minimum_hint_nm: float = None) -> dict:
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
        from settings import FWHM_EXCELLENT_THRESHOLD_NM, FWHM_GOOD_THRESHOLD_NM

        # Default fallback
        default_result = {
            'wavelength': 650.0,
            'fwhm': None,
            'quality': 0.0,
            'candidates_found': 0,
            'warning': None
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
            minima_indices, properties = find_peaks(-spec_spr, prominence=1.0, width=3)

            if len(minima_indices) == 0:
                # No clear minima found, use minimum_hint_nm if available, else absolute minimum
                if minimum_hint_nm is not None and 600.0 <= minimum_hint_nm <= 690.0:
                    # Use the hint calculated from smoothed transmission in SPR region
                    peak_wl = minimum_hint_nm
                    logger.debug(f"QC: No minima found, using minimum_hint_nm={peak_wl:.1f}nm")
                else:
                    # Fallback: find minimum in CORE SPR region (600-690nm)
                    core_spr_mask = (wl_spr >= 600.0) & (wl_spr <= 690.0)
                    if np.any(core_spr_mask):
                        core_spec = spec_spr[core_spr_mask]
                        core_wl = wl_spr[core_spr_mask]
                        min_idx = np.argmin(core_spec)
                        peak_wl = core_wl[min_idx]
                        logger.debug(f"QC: No minima found, using minimum in core SPR region: {peak_wl:.1f}nm")
                    else:
                        min_idx = np.argmin(spec_spr)
                        peak_wl = wl_spr[min_idx]

                fwhm = self._calculate_fwhm(wl_spr, spec_spr, peak_wl)

                warning = None
                if peak_wl > 670.0:
                    warning = f"Peak at {peak_wl:.1f}nm (>670nm) with no clear dip structure"

                return {
                    'wavelength': peak_wl,
                    'fwhm': fwhm,
                    'quality': 0.3,  # Low quality - no clear dip structure
                    'candidates_found': 0,
                    'warning': warning
                }

            # Check if first peak found is >670nm (potential issue flag)
            first_peak_flag = False
            if channel not in self._last_peak_wavelength:
                # First acquisition for this channel
                first_candidate_wl = wl_spr[minima_indices[0]]
                if first_candidate_wl > 670.0:
                    first_peak_flag = True
                    logger.warning(f"Channel {channel}: First peak detected at {first_candidate_wl:.1f}nm (>670nm) - potential calibration issue")

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
                quality = 0.5 * fwhm_score + 0.3 * min(depth / 50.0, 1.0) + 0.2 * wl_score + hint_bonus

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

                candidates.append({
                    'wavelength': candidate_wl,
                    'fwhm': fwhm,
                    'quality': quality,
                    'depth': depth,
                    'fwhm_score': fwhm_score,
                    'wl_score': wl_score
                })

            # Select best candidate
            warning = None
            if len(candidates) == 0:
                # All candidates rejected, use minimum_hint_nm if available, else absolute minimum
                if minimum_hint_nm is not None and 600.0 <= minimum_hint_nm <= 690.0:
                    # Use the hint calculated from smoothed transmission in SPR region
                    peak_wl = minimum_hint_nm
                    logger.debug(f"QC: All candidates rejected, using minimum_hint_nm={peak_wl:.1f}nm")
                else:
                    # Fallback: find absolute minimum in CORE SPR region (600-690nm, not 590-750nm)
                    core_spr_mask = (wl_spr >= 600.0) & (wl_spr <= 690.0)
                    if np.any(core_spr_mask):
                        core_spec = spec_spr[core_spr_mask]
                        core_wl = wl_spr[core_spr_mask]
                        min_idx = np.argmin(core_spec)
                        peak_wl = core_wl[min_idx]
                        logger.debug(f"QC: Using minimum in core SPR region (600-690nm): {peak_wl:.1f}nm")
                    else:
                        min_idx = np.argmin(spec_spr)
                        peak_wl = wl_spr[min_idx]
                        logger.debug(f"QC: Using absolute minimum: {peak_wl:.1f}nm")

                fwhm = self._calculate_fwhm(wl_spr, spec_spr, peak_wl)

                # Generate warning based on issue
                if fwhm is not None and fwhm > 80.0:
                    warning = f"PROBLEM: FWHM={fwhm:.1f}nm (>80nm) - poor coupling or air bubble"
                elif peak_wl > 670.0:
                    warning = f"Peak at {peak_wl:.1f}nm (>670nm) - all candidates rejected"

                result = {
                    'wavelength': peak_wl,
                    'fwhm': fwhm,
                    'quality': 0.2,
                    'candidates_found': len(minima_indices),
                    'warning': warning
                }
            else:
                # Choose highest quality candidate
                best = max(candidates, key=lambda c: c['quality'])

                # Generate warnings for problematic conditions
                if best['fwhm'] > 80.0:
                    warning = f"PROBLEM: FWHM={best['fwhm']:.1f}nm (>80nm) - poor coupling detected"
                elif best['fwhm'] > 60.0:
                    warning = f"Warning: FWHM={best['fwhm']:.1f}nm (60-80nm) - coupling quality poor"
                elif first_peak_flag and best['wavelength'] > 670.0:
                    warning = f"FLAG: First peak at {best['wavelength']:.1f}nm (>670nm) - verify sensor condition"
                elif best['wavelength'] > 700.0:
                    # Check if gradual shift
                    if channel in self._last_peak_wavelength:
                        prev_wl = self._last_peak_wavelength[channel]
                        shift = best['wavelength'] - prev_wl
                        if shift > 15.0:
                            warning = f"Large shift: {prev_wl:.1f}nm → {best['wavelength']:.1f}nm (+{shift:.1f}nm)"
                    else:
                        warning = f"Peak at {best['wavelength']:.1f}nm (>700nm) - extended range"

                result = {
                    'wavelength': best['wavelength'],
                    'fwhm': best['fwhm'],
                    'quality': best['quality'],
                    'candidates_found': len(candidates),
                    'warning': warning
                }

            # Update tracking history
            self._last_peak_wavelength[channel] = result['wavelength']
            self._fwhm_values[channel] = result['fwhm']

            # Log warnings if present
            if warning:
                logger.warning(f"Channel {channel}: {warning}")

            return result

        except Exception as e:
            logger.warning(f"Peak validation failed for channel {channel}: {e}")
            return default_result

    def _find_resonance_peak(self, wavelength: np.ndarray, spectrum: np.ndarray, channel: str,
                            minimum_hint_nm: float = None) -> float:
        """Find resonance peak wavelength using selected pipeline method.

        Dispatches to the active pipeline method selected in UI:
        - Fourier Transform (default): DST → IDCT → Zero-crossing
        - Centroid: Center of mass calculation with double filtering
        - Polynomial: Curve fitting with analytical minimum
        - Adaptive Multi-Feature: Advanced multi-parameter analysis
        - Consensus: Multi-method voting

        Args:
            wavelength: Wavelength array
            spectrum: Transmission spectrum (P/S ratio %) - already SG-filtered
            channel: Channel identifier for accessing channel-specific weights
            minimum_hint_nm: Pre-calculated minimum position hint (optional)

        Returns:
            Resonance wavelength in nm
        """
        try:
            from utils.processing_pipeline import get_pipeline_registry

            # Get active pipeline from registry (selected in UI)
            registry = get_pipeline_registry()
            active_pipeline_id = registry.active_pipeline_id

            # Dispatch to selected pipeline
            if active_pipeline_id == 'centroid':
                # Centroid method: Center of mass with double filtering
                from utils.pipelines.centroid_pipeline import CentroidPipeline
                pipeline = CentroidPipeline()
                peak_wavelength = pipeline.find_resonance_wavelength(
                    transmission=spectrum,
                    wavelengths=wavelength,
                    minimum_hint_nm=minimum_hint_nm  # Pass hint for fast path
                )

            elif active_pipeline_id == 'polynomial':
                # Polynomial fitting method
                from utils.pipelines.polynomial_pipeline import PolynomialPipeline
                pipeline = PolynomialPipeline()
                peak_wavelength = pipeline.find_resonance_wavelength(
                    transmission=spectrum,
                    wavelengths=wavelength,
                    minimum_hint_nm=minimum_hint_nm
                )

            elif active_pipeline_id == 'adaptive':
                # Adaptive multi-feature method with temporal filtering
                from utils.pipelines.adaptive_multifeature_pipeline import AdaptiveMultiFeaturePipeline
                pipeline = AdaptiveMultiFeaturePipeline()
                import time
                peak_wavelength, metadata = pipeline.find_resonance_wavelength(
                    transmission=spectrum,
                    wavelengths=wavelength,
                    timestamp=time.time(),  # Pass timestamp for Kalman filtering
                    minimum_hint_nm=minimum_hint_nm  # Pass hint for fast path
                )
                # Note: metadata contains FWHM, depth, confidence, jitter_flag, slopes, etc.

            elif active_pipeline_id == 'consensus':
                # Consensus method (multi-algorithm voting)
                from utils.pipelines.consensus_pipeline import ConsensusPipeline
                pipeline = ConsensusPipeline()
                peak_wavelength = pipeline.find_resonance_wavelength(
                    transmission=spectrum,
                    wavelengths=wavelength,
                    minimum_hint_nm=minimum_hint_nm
                )

            else:
                # Default: Fourier Transform (active_pipeline_id == 'fourier' or unknown)
                from utils.pipelines.fourier_pipeline import FourierPipeline
                from settings.settings import FOURIER_ALPHA, FOURIER_WINDOW_SIZE, EMA_ENABLED, EMA_ALPHA

                # Use FourierPipeline with EMA pre-smoothing and optimized parameters
                pipeline = FourierPipeline(config={
                    'alpha': FOURIER_ALPHA,  # 9000 = original 2nm baseline performance
                    'window_size': FOURIER_WINDOW_SIZE,  # 165 points
                    'ema_enabled': EMA_ENABLED,  # Cascaded filtering stage 1
                    'ema_alpha': EMA_ALPHA,  # 0.1 = 13.3% noise reduction
                })
                peak_wavelength = pipeline.find_resonance_wavelength(
                    transmission=spectrum,
                    wavelengths=wavelength,
                    fourier_weights=self.fourier_weights.get(channel) if isinstance(self.fourier_weights, dict) else self.fourier_weights
                )

                # Validate result - must be within SPR region (600-690nm) to avoid edge artifacts
                if np.isnan(peak_wavelength) or peak_wavelength < 600.0 or peak_wavelength > 690.0:
                    # Fourier failed or found edge artifact, use hint or minimum in SPR region
                    if minimum_hint_nm is not None and 600.0 <= minimum_hint_nm <= 690.0:
                        peak_wavelength = minimum_hint_nm
                    else:
                        # Find minimum in SPR region only
                        spr_mask = (wavelength >= 600.0) & (wavelength <= 690.0)
                        if np.any(spr_mask):
                            spr_spectrum = spectrum[spr_mask]
                            spr_wavelengths = wavelength[spr_mask]
                            peak_wavelength = spr_wavelengths[np.argmin(spr_spectrum)]
                        else:
                            peak_wavelength = 650.0  # Fallback to center

            # Final validation
            if np.isnan(peak_wavelength) or peak_wavelength < wavelength[0] or peak_wavelength > wavelength[-1]:
                # All methods failed, use hint or minimum
                peak_wavelength = minimum_hint_nm if minimum_hint_nm is not None else wavelength[np.argmin(spectrum)]

            return float(peak_wavelength)

        except Exception as e:
            # Fallback on any error
            if minimum_hint_nm is not None:
                return float(minimum_hint_nm)
            peak_idx = np.argmin(spectrum) if len(spectrum) > 0 else 0
            return float(wavelength[peak_idx]) if len(wavelength) > peak_idx else 650.0

    def _calculate_fwhm(self, wavelengths: np.ndarray, transmission: np.ndarray, peak_wl: float) -> float:
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
                right_wl = wl[min_idx + right_crossing_idx[-1]]  # Last crossing after minimum

            # FWHM is the distance between crossings
            fwhm = right_wl - left_wl

            # Sanity check: FWHM should be reasonable (5-200nm)
            if 5 <= fwhm <= 200:
                return float(fwhm)
            else:
                return np.nan

        except Exception as e:
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
        logger.info("Spectral correction disabled - using SNR-aware peak finding instead")
        return

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
            from utils.device_integration import get_device_optical_calibration_path
            from settings import (
                AFTERGLOW_AUTO_MODE,
                AFTERGLOW_FAST_THRESHOLD_MS,
                AFTERGLOW_SLOW_THRESHOLD_MS,
                LED_DELAY,
                LED_POST_DELAY
            )

            optical_cal_path = get_device_optical_calibration_path()

            if optical_cal_path and optical_cal_path.exists():
                self.afterglow_correction = AfterglowCorrection(optical_cal_path)

                # Generate afterglow curves for QC report (at LED_DELAY timing)
                if (self.calibration_data and
                    self.calibration_data.wavelengths is not None and
                    len(self.calibration_data.wavelengths) > 0 and
                    self.calibration_data.s_pol_ref):

                    ch_list = list(self.calibration_data.s_pol_ref.keys())
                    self.afterglow_curves = {}
                    for i, ch in enumerate(ch_list):
                        if i > 0:  # First channel has no previous channel
                            prev_ch = ch_list[i - 1]
                            try:
                                # Calculate scalar afterglow correction value
                                correction_value = self.afterglow_correction.calculate_correction(
                                    previous_channel=prev_ch,
                                    integration_time_ms=float(self.calibration_data.s_mode_integration_time),
                                    delay_ms=LED_DELAY * 1000,  # Convert to ms
                                )
                                # Create flat array (afterglow is uniform across wavelengths)
                                self.afterglow_curves[ch] = np.full_like(self.calibration_data.wavelengths, correction_value, dtype=float)
                                logger.debug(f"Afterglow for ch {ch.upper()} from {prev_ch.upper()}: {correction_value:.1f} counts")
                            except Exception as e:
                                logger.debug(f"Could not calculate afterglow for ch {ch}: {e}")
                                self.afterglow_curves[ch] = np.zeros_like(self.calibration_data.wavelengths)
                        else:
                            # First channel has no previous channel - no afterglow
                            self.afterglow_curves[ch] = np.zeros_like(self.calibration_data.wavelengths)
                    logger.info(f"✅ Afterglow curves generated for QC report")

                # Determine afterglow mode based on total acquisition delay
                if AFTERGLOW_AUTO_MODE:
                    # Calculate total delay (pre + post)
                    total_delay_ms = (LED_DELAY * 1000) + (LED_POST_DELAY * 1000)

                    if total_delay_ms < AFTERGLOW_FAST_THRESHOLD_MS:
                        self.afterglow_mode = 'fast'
                        self.afterglow_enabled = True
                        logger.info(f"✅ Optical correction loaded: {optical_cal_path.name}")
                        logger.info(f"   Mode: FAST (total delay {total_delay_ms:.1f}ms < {AFTERGLOW_FAST_THRESHOLD_MS}ms)")
                        logger.info(f"   High-speed acquisition: Afterglow correction enabled for 2x faster operation")
                    elif total_delay_ms <= AFTERGLOW_SLOW_THRESHOLD_MS:
                        self.afterglow_mode = 'normal'
                        self.afterglow_enabled = True
                        logger.info(f"✅ Optical correction loaded: {optical_cal_path.name}")
                        logger.info(f"   Mode: NORMAL (total delay {total_delay_ms:.1f}ms, optimal range)")
                        logger.info(f"   Standard operation: Afterglow correction enabled for better stability")
                    else:
                        self.afterglow_mode = 'slow'
                        self.afterglow_enabled = False
                        logger.info(f"✅ Optical correction loaded: {optical_cal_path.name}")
                        logger.info(f"   Mode: SLOW (total delay {total_delay_ms:.1f}ms > {AFTERGLOW_SLOW_THRESHOLD_MS}ms)")
                        logger.info(f"   Afterglow negligible (<0.2% of signal), correction disabled")
                else:
                    # Manual mode - always enable if calibration exists
                    self.afterglow_mode = 'manual'
                    self.afterglow_enabled = True
                    logger.info(f"✅ Optical correction loaded: {optical_cal_path.name}")
                    logger.info(f"   Mode: MANUAL (auto mode disabled, correction always enabled)")

                # Calculate optimal LED delay if enabled
                try:
                    from settings import USE_DYNAMIC_LED_DELAY, LED_DELAY_TARGET_RESIDUAL
                    if USE_DYNAMIC_LED_DELAY and self.integration_time:
                        optimal_delay = self.afterglow_correction.get_optimal_led_delay(
                            integration_time_ms=float(self.integration_time),
                            target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL)
                        )
                        # Convert to ms and validate range (5ms - 200ms)
                        optimal_delay_ms = optimal_delay * 1000
                        if 5.0 <= optimal_delay_ms <= 200.0:
                            self._led_delay_ms = optimal_delay_ms
                            logger.info(f"   Optimal LED delay: {self._led_delay_ms:.1f} ms")
                except Exception as e:
                    logger.debug(f"Dynamic LED delay calculation skipped: {e}")
                return True
            else:
                # Normal for legacy devices - not an error condition
                logger.debug("No optical calibration file found (normal for legacy devices)")
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

    def _update_calibration_intelligence(self, calibration_data: Dict):
        """Update system intelligence with calibration metrics.

        Args:
            calibration_data: Dict containing calibration results including channel_performance
        """
        si = get_system_intelligence()

        # Calculate per-channel quality scores from S-ref QC results
        quality_scores = {}
        failed_channels = []

        if 's_ref_qc_results' in calibration_data:
            for ch, qc_data in calibration_data['s_ref_qc_results'].items():
                # QC score combines multiple factors (intensity, noise, etc.)
                # Higher is better, range 0-1
                quality_score = qc_data.get('quality_score', 0.0)
                quality_scores[ch] = quality_score

                if qc_data.get('failed', False):
                    failed_channels.append(ch)

        # If no QC results, estimate quality from error list
        if not quality_scores:
            for ch in ['a', 'b', 'c', 'd']:
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
            failed_channels=failed_channels if not success else None
        )

        # Update LED health from calibrated intensities
        for ch, intensity in self.leds_calibrated.items():
            # Target is typically 30000 counts
            target = 30000
            si.update_led_health(
                channel=ch,
                intensity=intensity,
                target=target
            )

        # NEW: Update channel performance characteristics for ML guidance
        # These metrics inform peak tracking sensitivity and noise models
        if 'channel_performance' in calibration_data:
            for ch, perf in calibration_data['channel_performance'].items():
                # Store per-channel characteristics
                si.update_channel_characteristics(
                    channel=ch,
                    max_signal=perf.get('max_counts', 0),
                    utilization_pct=perf.get('utilization_pct', 0),
                    boost_ratio=perf.get('boost_ratio', 1.0),
                    optical_limit_reached=perf.get('optical_limit_reached', False),
                    hit_saturation=perf.get('hit_saturation', False)
                )

    def _update_signal_intelligence(self, channel: str, wavelength: float,
                                   snr: float, transmission_quality: float):
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
            transmission_quality=transmission_quality
        )

    def clear_buffers(self):
        """Clear all data buffers."""
        for ch in ['a', 'b', 'c', 'd']:
            self.channel_buffers[ch].clear()
            self.time_buffers[ch].clear()
        logger.info("Data buffers cleared")
