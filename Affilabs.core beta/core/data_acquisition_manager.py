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

from PySide6.QtCore import QObject, Signal, QTimer
from utils.logger import logger
from typing import Optional, Dict
import threading
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
    """Manages spectrum acquisition and processing."""

    # Signals for data updates
    spectrum_acquired = Signal(dict)  # {channel: str, wavelength: float, intensity: float, timestamp: float}
    calibration_started = Signal()
    calibration_complete = Signal(dict)  # {integration_time, num_scans, ref_intensity, leds_calibrated, ch_error_list}
    calibration_failed = Signal(str)  # Error message
    calibration_progress = Signal(str)  # Progress message
    acquisition_error = Signal(str)  # Error message

    def __init__(self, hardware_mgr):
        super().__init__()

        # Reference to hardware manager
        self.hardware_mgr = hardware_mgr

        # Calibration state
        self.calibrated = False
        self.integration_time = 15  # ms (global in standard method, max in alternative method)
        self.num_scans = 5
        self.ref_intensity = 255
        self.leds_calibrated = {}  # {channel: intensity}
        self.ch_error_list = []  # List of failed channels from calibration

        # Calibration method tracking
        self.calibration_method = 'standard'  # 'standard' or 'alternative'
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
        self._previous_channel = None  # Track previous channel for afterglow correction
        self._led_delay_ms = 45.0  # Default LED delay in milliseconds (PRE_LED_DELAY_MS)

        # Batched acquisition settings (from settings.py)
        from settings import BATCH_SIZE, ENABLE_INTERPOLATED_DISPLAY
        self.batch_size = BATCH_SIZE  # Minimum raw spectra to buffer before processing (reduces USB overhead)
        self._spectrum_batch = {'a': [], 'b': [], 'c': [], 'd': []}  # Batch buffers per channel
        self._batch_timestamps = {'a': [], 'b': [], 'c': [], 'd': []}  # Timestamp buffers

        # Display smoothing: emit partial updates during batch processing
        self.enable_interpolated_display = ENABLE_INTERPOLATED_DISPLAY
        self._last_emitted_wavelength = {'a': None, 'b': None, 'c': None, 'd': None}  # For interpolation

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

        if self._acquiring:
            logger.warning("Cannot calibrate while acquiring")
            self.calibration_failed.emit("Stop acquisition before calibrating")
            return

        logger.info("Starting calibration...")
        self.calibration_started.emit()

        # Run calibration in background thread
        thread = threading.Thread(target=self._calibration_worker, daemon=True)
        thread.start()

    def _calibration_worker(self):
        """Calibration routine running in background thread."""
        try:
            from utils.led_calibration import perform_full_led_calibration, perform_alternative_calibration
            from settings import INTEGRATION_STEP, MIN_WAVELENGTH, MAX_WAVELENGTH, USE_ALTERNATIVE_CALIBRATION

            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                raise Exception("Hardware not available")

            self.calibration_progress.emit("Initializing...")

            # Get wavelength calibration data
            logger.info("Reading wavelength calibration data...")
            wave_data = usb.read_wavelength()
            wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
            self.wave_data = wave_data[wave_min_index:wave_max_index]

            # Store indices for efficient trimming during live acquisition
            self.wave_min_index = wave_min_index
            self.wave_max_index = wave_max_index
            logger.info(f"Wavelength range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm (indices {wave_min_index}-{wave_max_index})")

            self.calibration_progress.emit("Calibrating system...")

            # Select calibration method based on configuration
            if USE_ALTERNATIVE_CALIBRATION:
                logger.info("Using ALTERNATIVE calibration method (Global LED Intensity)")
                cal_result = perform_alternative_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type='P4SPR',
                    single_mode=False,
                    single_ch='a',
                    stop_flag=None,
                    progress_callback=lambda msg: self.calibration_progress.emit(msg)
                )
            else:
                logger.info("Using STANDARD calibration method (Global Integration Time)")
                cal_result = perform_full_led_calibration(
                    usb=usb,
                    ctrl=ctrl,
                    device_type='P4SPR',
                    single_mode=False,
                    single_ch='a',
                    integration_step=INTEGRATION_STEP,
                    stop_flag=None,
                    progress_callback=lambda msg: self.calibration_progress.emit(msg)
                )

            # Check for complete failure (all channels failed or critical error)
            # Partial failures (some channels work) are allowed and handled in UI
            if cal_result.integration_time is None or cal_result.integration_time == 0:
                raise Exception("Critical calibration failure: Could not determine integration time")

            # Log partial failures but continue
            if len(cal_result.ch_error_list) > 0:
                logger.warning(f"⚠️ Partial calibration: {len(cal_result.ch_error_list)} channel(s) failed: {cal_result.ch_error_list}")

            self.calibration_progress.emit("Finalizing...")


            # Store calibration results
            self.integration_time = cal_result.integration_time
            self.num_scans = cal_result.num_scans
            self.ref_intensity = cal_result.ref_intensity
            self.leds_calibrated = cal_result.leds_calibrated
            self.dark_noise = cal_result.dark_noise

            # Store alternative method specific data (per-channel integration and dark noise)
            self.calibration_method = getattr(cal_result, 'calibration_method', 'standard')
            self.per_channel_integration = getattr(cal_result, 'per_channel_integration', {})
            self.per_channel_dark_noise = getattr(cal_result, 'per_channel_dark_noise', {})

            logger.info(f"📋 Stored calibration: method={self.calibration_method}, integration_time={self.integration_time}ms, num_scans={self.num_scans}")
            if self.calibration_method == 'alternative':
                logger.info(f"   Per-channel integration times: {self.per_channel_integration}")

            self.wave_data = cal_result.wave_data
            # Note: cal_result.fourier_weights is a base array, we'll compute per-channel weights below
            self.ref_sig = cal_result.ref_sig  # S-mode reference spectra
            self.ch_error_list = cal_result.ch_error_list.copy()
            self.s_ref_qc_results = getattr(cal_result, 's_ref_qc_results', {})  # Optical QC results

            # Store channel performance metrics for ML system intelligence
            self.channel_performance = getattr(cal_result, 'channel_performance', {})

            # Calculate SNR-aware Fourier weights from S-ref LED profiles
            # Uses LED profile as metadata to guide peak finding (not for flattening)
            # This will populate self.fourier_weights as a dict: {channel: weights_array}
            self._calculate_snr_aware_fourier_weights()

            # Mark as calibrated
            self.calibrated = True

            # Load afterglow correction if available
            self._load_afterglow_correction()

            # Emit calibration complete with settings and channel errors
            calibration_data = {
                'integration_time': self.integration_time,
                'num_scans': self.num_scans,
                'ref_intensity': self.ref_intensity,
                'leds_calibrated': self.leds_calibrated.copy(),
                'ch_error_list': self.ch_error_list.copy(),
                's_ref_qc_results': self.s_ref_qc_results,  # Include optical QC results
                'channel_performance': self.channel_performance,  # Per-channel metrics for ML
                'calibration_type': 'full'  # This is full LED calibration with afterglow
            }

            if len(self.ch_error_list) > 0:
                logger.warning(f"⚠️ Calibration complete with errors in channels: {self.ch_error_list}")
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
        if not self.calibrated:
            self.acquisition_error.emit("Calibrate before starting acquisition")
            return

        if not self._check_hardware():
            self.acquisition_error.emit("Hardware not connected")
            return

        if self._acquiring:
            logger.warning("Acquisition already running")
            return

        logger.info("Starting spectrum acquisition...")
        logger.info(f"📊 Calibrated settings: integration_time={self.integration_time}ms, num_scans={self.num_scans}")
        logger.info(f"📊 LED intensities: {self.leds_calibrated}")

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

        self._acquiring = True
        self._stop_acquisition.clear()

        # Start acquisition thread
        self._acquisition_thread = threading.Thread(target=self._acquisition_worker, daemon=True)
        self._acquisition_thread.start()

    def stop_acquisition(self):
        """Stop spectrum acquisition and flush remaining batches."""
        if not self._acquiring:
            return

        logger.info("Stopping spectrum acquisition...")

        # Flush any remaining batched spectra before stopping
        for ch in ['a', 'b', 'c', 'd']:
            if len(self._spectrum_batch[ch]) > 0:
                logger.info(f"Flushing {len(self._spectrum_batch[ch])} remaining spectra for channel {ch.upper()}")
                self._process_and_emit_batch(ch)

        self._stop_acquisition.set()
        self._acquiring = False

        # Wait for thread to finish (with timeout)
        if self._acquisition_thread:
            self._acquisition_thread.join(timeout=2.0)

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

    def _acquisition_worker(self):
        """Main acquisition loop running in background thread with batched processing."""
        channels = ['a', 'b', 'c', 'd']
        consecutive_errors = 0
        max_consecutive_errors = 5  # Stop after 5 consecutive failures

        logger.info(f"Acquisition worker started with batch_size={self.batch_size}")

        while not self._stop_acquisition.is_set():
            try:
                # Check if paused - sleep and skip acquisition cycle
                if self._pause_acquisition.is_set():
                    time.sleep(0.1)  # Sleep while paused
                    continue

                cycle_success = False

                # Acquire spectrum for each channel (raw acquisition phase)
                for ch in channels:
                    if self._stop_acquisition.is_set():
                        break

                    # Get raw spectrum from hardware (fast read)
                    spectrum_data = self._acquire_channel_spectrum(ch)

                    if spectrum_data:
                        # Buffer raw spectrum data (no processing yet)
                        timestamp = time.time()
                        self._spectrum_batch[ch].append(spectrum_data)
                        self._batch_timestamps[ch].append(timestamp)
                        cycle_success = True

                        # Emit interpolated preview for smooth display (if enabled)
                        # This provides visual feedback before batch processing completes
                        if self.enable_interpolated_display and self._last_emitted_wavelength[ch] is not None:
                            self._emit_interpolated_preview(ch, timestamp)

                        # Process batch when minimum size reached
                        if len(self._spectrum_batch[ch]) >= self.batch_size:
                            self._process_and_emit_batch(ch)

                # Reset error counter if we got at least one successful acquisition
                if cycle_success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    logger.warning(f"Acquisition cycle failed (consecutive errors: {consecutive_errors}/{max_consecutive_errors})")

                    # Stop if too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive acquisition errors - stopping acquisition")
                        self.acquisition_error.emit("Hardware communication lost - stopping acquisition")
                        self._stop_acquisition.set()
                        break

                # Small delay between acquisition cycles
                time.sleep(0.01)

            except Exception as e:
                logger.exception(f"Acquisition error: {e}")
                consecutive_errors += 1

                # Stop if too many errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors - stopping acquisition")
                    self.acquisition_error.emit(f"Hardware error - stopping acquisition: {e}")
                    self._stop_acquisition.set()
                    break

                self.acquisition_error.emit(str(e))
                time.sleep(0.5)  # Longer delay on error

    def _check_hardware(self) -> bool:
        """Check if required hardware is connected."""
        return (
            self.hardware_mgr.ctrl is not None and
            self.hardware_mgr.usb is not None
        )

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
                logger.warning("Cannot calculate SNR-aware weights: missing ref_sig or wave_data")
                return

            logger.info("Calculating SNR-aware Fourier weights from LED profiles...")

            for ch in ['a', 'b', 'c', 'd']:
                if ch in self.ref_sig and self.ref_sig[ch] is not None:
                    # Calculate weights that favor high-SNR regions of LED profile
                    self.fourier_weights[ch] = calculate_snr_aware_fourier_weights(
                        ref_spectrum=self.ref_sig[ch],
                        wavelengths=self.wave_data,
                        alpha=2e3,  # Standard Fourier denoising strength
                        snr_weight_strength=0.5  # 50% SNR weighting, 50% uniform
                    )
                    logger.info(f"✓ Ch {ch.upper()}: SNR-aware weights calculated")
                else:
                    logger.warning(f"Ch {ch.upper()}: No ref spectrum, using uniform weights")
                    self.fourier_weights[ch] = np.ones(len(self.wave_data) - 1)

        except Exception as e:
            logger.warning(f"Failed to calculate SNR-aware Fourier weights: {e}")
            logger.exception(e)  # Show full traceback for debugging
            # Fallback to uniform weights
            for ch in ['a', 'b', 'c', 'd']:
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

        logger.debug(f"Processing batch of {len(batch)} spectra for channel {channel.upper()}")

        # Process each spectrum in the batch
        for spectrum_data, timestamp in zip(batch, timestamps):
            try:
                # Process spectrum (filtering, peak finding)
                processed = self._process_spectrum(channel, spectrum_data)

                # Buffer the data
                self.channel_buffers[channel].append(processed['wavelength'])
                self.time_buffers[channel].append(timestamp)

                # Emit signal with processed data
                self.spectrum_acquired.emit({
                    'channel': channel,
                    'wavelength': processed['wavelength'],
                    'intensity': processed['intensity'],
                    'full_spectrum': processed.get('full_spectrum'),
                    'raw_spectrum': processed.get('raw_spectrum'),  # P-mode spectrum for transmission calc
                    'transmission_spectrum': processed.get('transmission_spectrum'),  # P/S ratio
                    'timestamp': timestamp,
                    'is_preview': False  # Real processed data
                })

                # Update last emitted wavelength for interpolation
                self._last_emitted_wavelength[channel] = processed['wavelength']

            except Exception as e:
                logger.error(f"Error processing spectrum in batch for channel {channel}: {e}")

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

            # Emit preview using last known wavelength
            # This maintains visual continuity until real data arrives
            self.spectrum_acquired.emit({
                'channel': channel,
                'wavelength': last_wavelength,  # Hold last value (simple interpolation)
                'intensity': 0.0,  # Placeholder
                'full_spectrum': None,
                'timestamp': timestamp,
                'is_preview': True  # Flag to indicate this is interpolated
            })

        except Exception as e:
            logger.debug(f"Error emitting interpolated preview for {channel}: {e}")

    def _acquire_channel_spectrum(self, channel: str) -> Optional[Dict]:
        """Acquire raw spectrum for a channel."""
        try:
            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                return None

            # Check if we have wave_data from calibration
            if self.wave_data is None or len(self.wave_data) == 0:
                logger.warning("No wavelength data available - skipping acquisition")
                return None

            # Turn on LED for channel (already in P-mode from start_acquisition)
            led_intensity = self.leds_calibrated.get(channel, 180)
            # NOTE: Polarizer is already in P-mode (set once at start_acquisition)
            # No need to call set_mode('p') here - that would cause unnecessary servo rotation
            ctrl.set_intensity(ch=channel, raw_val=led_intensity)

            # Use configured LED delay (default 45ms)
            time.sleep(self._led_delay_ms / 1000.0)  # Convert ms to seconds

            # Set integration time
            try:
                usb.set_integration(self.integration_time)
            except ConnectionError as e:
                logger.error(f"⚠️ Device disconnected while setting integration time: {e}")
                self.acquisition_error.emit("Spectrometer disconnected. Please reconnect and restart.")
                self.stop_acquisition()
                return None

            # Read spectrum intensities
            try:
                raw_spectrum = usb.read_intensity()
            except ConnectionError as e:
                logger.error(f"⚠️ Device disconnected while reading spectrum: {e}")
                self.acquisition_error.emit("Spectrometer disconnected. Please reconnect and restart.")
                self.stop_acquisition()
                return None

            if raw_spectrum is None:
                logger.error(f"Failed to read spectrum for channel {channel}")
                return None

            # Trim spectrum to match wave_data range using stored indices from calibration
            if len(raw_spectrum) != len(self.wave_data):
                # Use indices stored during calibration (eliminates expensive USB read)
                if hasattr(self, 'wave_min_index') and hasattr(self, 'wave_max_index'):
                    raw_spectrum = raw_spectrum[self.wave_min_index:self.wave_max_index]
                else:
                    # Fallback if indices not available (shouldn't happen after calibration)
                    logger.warning(f"No cached indices - trimming by length: {len(raw_spectrum)} -> {len(self.wave_data)}")
                    raw_spectrum = raw_spectrum[:len(self.wave_data)]

            return {
                'wavelength': self.wave_data.copy(),
                'intensity': raw_spectrum
            }

        except Exception as e:
            logger.error(f"Failed to acquire spectrum for channel {channel}: {e}")
            return None

    def _process_spectrum(self, channel: str, spectrum_data: Dict) -> Dict:
        """Process raw spectrum (filtering, afterglow correction, peak finding)."""
        try:
            wavelength = spectrum_data['wavelength']
            intensity = spectrum_data['intensity']

            # Subtract dark noise
            if self.dark_noise is not None:
                intensity = intensity - self.dark_noise

            # Apply afterglow correction if enabled and we have a previous channel
            # This removes previous channel's residual light and should apply to BOTH
            # transmission calculation and peak finding
            if self.afterglow_enabled and self.afterglow_correction is not None and self._previous_channel is not None:
                try:
                    # Calculate expected afterglow from previous channel
                    afterglow_correction = self.afterglow_correction.calculate_correction(
                        previous_channel=self._previous_channel,
                        integration_time_ms=float(self.integration_time),
                        delay_ms=self._led_delay_ms
                    )

                    # Apply correction (subtract afterglow)
                    intensity = intensity - afterglow_correction

                    logger.debug(
                        f"Afterglow correction applied: Ch {channel.upper()} "
                        f"(prev: {self._previous_channel.upper()}, "
                        f"correction: {afterglow_correction:.1f} counts)"
                    )
                except Exception as e:
                    logger.warning(f"Afterglow correction failed for channel {channel}: {e}")

            # Track this channel as previous for next measurement
            self._previous_channel = channel

            # Store raw spectrum (dark + afterglow corrected) for transmission calculation
            # Transmission needs P-mode vs S-mode in same basis:
            # - Both with dark subtracted
            # - Both with afterglow corrected
            # - NO spectral correction (LED profile cancels naturally in P/S ratio)
            raw_spectrum = intensity.copy()

            # Calculate transmission spectrum (P/S ratio) for peak finding
            # This is the proper input for resonance detection algorithms
            # LED profile cancels naturally in the ratio
            transmission_spectrum = None
            if channel in self.ref_sig and self.ref_sig[channel] is not None:
                try:
                    from utils.spr_signal_processing import calculate_transmission
                    # Calculate transmission percentage
                    transmission_spectrum = calculate_transmission(raw_spectrum, self.ref_sig[channel])
                except Exception as e:
                    logger.warning(f"Could not calculate transmission for peak finding: {e}")
                    transmission_spectrum = None
            else:
                logger.info(f"⚠️ Ch {channel.upper()}: No S-mode reference available - system needs calibration for transmission data (ref_sig keys: {list(self.ref_sig.keys())})")

            # Find resonance peak using SNR-aware Fourier analysis on transmission
            # If transmission not available, fall back to raw P-mode intensity
            # SNR-aware weights guide peak finding toward high-quality regions
            peak_input = transmission_spectrum if transmission_spectrum is not None else intensity
            peak_wavelength = self._find_resonance_peak(wavelength, peak_input, channel)

            return {
                'wavelength': peak_wavelength,
                'intensity': intensity[np.argmin(intensity)] if len(intensity) > 0 else 0.0,
                'full_spectrum': raw_spectrum,  # Raw P-mode spectrum (for visualization)
                'raw_spectrum': raw_spectrum,  # Raw P-mode spectrum (for transmission calculation)
                'transmission_spectrum': transmission_spectrum  # P/S ratio (for multi-parametric analysis)
            }

        except Exception as e:
            logger.error(f"Failed to process spectrum: {e}")
            logger.exception(e)  # Show full traceback
            # Return raw data on error
            return {
                'wavelength': 650.0,  # Default
                'intensity': 0.0,
                'full_spectrum': spectrum_data['intensity'],
                'raw_spectrum': spectrum_data['intensity']
            }

    def _find_resonance_peak(self, wavelength: np.ndarray, spectrum: np.ndarray, channel: str) -> float:
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
            weights = self.fourier_weights.get(channel) if isinstance(self.fourier_weights, dict) else self.fourier_weights

            if weights is not None and len(weights) > 0:
                # Use SNR-aware Fourier analysis (frequency-domain denoising + zero-finding)
                peak_wavelength = find_resonance_wavelength_fourier(
                    transmission_spectrum=spectrum,
                    wavelengths=wavelength,
                    fourier_weights=weights
                )

                # Validate result
                if not np.isnan(peak_wavelength) and wavelength[0] <= peak_wavelength <= wavelength[-1]:
                    return peak_wavelength
                else:
                    pass  # Fourier method failed, using fallback

            # Fallback to simple minimum finding (proven reliable main code pipeline)
            peak_idx = np.argmin(spectrum)
            peak_wavelength = wavelength[peak_idx]
            return peak_wavelength

        except Exception as e:
            logger.debug(f"Peak finding error for channel {channel}: {e}")
            # Final fallback
            peak_idx = np.argmin(spectrum) if len(spectrum) > 0 else 0
            return wavelength[peak_idx] if len(wavelength) > peak_idx else 650.0

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

    def _load_afterglow_correction(self):
        """Load device-specific afterglow correction calibration."""
        try:
            from afterglow_correction import AfterglowCorrection
            from utils.device_integration import get_device_optical_calibration_path

            optical_cal_path = get_device_optical_calibration_path()

            if optical_cal_path and optical_cal_path.exists():
                self.afterglow_correction = AfterglowCorrection(optical_cal_path)
                self.afterglow_enabled = True
                logger.info(f"✅ Device-specific afterglow correction loaded: {optical_cal_path.name}")

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
            else:
                logger.info("⚠️ No device-specific optical calibration found")
                logger.info("   Afterglow correction disabled (run OEM calibration from UI)")
                self.afterglow_enabled = False
        except Exception as e:
            logger.warning(f"AfterglowCorrection unavailable: {e}")
            self.afterglow_enabled = False

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
