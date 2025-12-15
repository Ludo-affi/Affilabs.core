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

import threading
import time

import numpy as np
from PySide6.QtCore import QObject, Signal

from utils.logger import logger


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

    def __init__(self, hardware_mgr):
        super().__init__()

        # Reference to hardware manager
        self.hardware_mgr = hardware_mgr

        # Calibration state
        self.calibrated = False
        self.integration_time = 15  # ms
        self.num_scans = 5
        self.ref_intensity = 255
        self.leds_calibrated = {}  # {channel: intensity}
        self.ch_error_list = []  # List of failed channels from calibration

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
        self._led_delay_ms = (
            45.0  # Default LED delay in milliseconds (PRE_LED_DELAY_MS)
        )

        # Batched acquisition settings
        self.batch_size = (
            4  # Minimum raw spectra to buffer before processing (reduces USB overhead)
        )
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

        # Acquisition state
        self._acquiring = False
        self._acquisition_thread = None
        self._stop_acquisition = threading.Event()

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
            from settings import INTEGRATION_STEP, MAX_WAVELENGTH, MIN_WAVELENGTH
            from utils.led_calibration import perform_full_led_calibration

            ctrl = self.hardware_mgr.ctrl
            usb = self.hardware_mgr.usb

            if not ctrl or not usb:
                raise Exception("Hardware not available")

            self.calibration_progress.emit("Reading wavelength data...")

            # Get wavelength calibration data
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

            self.calibration_progress.emit("Calibrating LEDs...")

            # Perform full LED calibration using real hardware
            logger.info("Starting LED calibration...")
            cal_result = perform_full_led_calibration(
                usb=usb,
                ctrl=ctrl,
                device_type="P4SPR",  # Could read from hardware_mgr if needed
                single_mode=False,  # Calibrate all channels
                single_ch="a",  # Not used when single_mode=False
                integration_step=INTEGRATION_STEP,
                stop_flag=None,
            )

            if not cal_result.success:
                raise Exception(
                    f"LED calibration failed for channels: {cal_result.ch_error_list}",
                )

            # Store calibration results
            self.integration_time = cal_result.integration_time
            self.num_scans = cal_result.num_scans
            self.ref_intensity = cal_result.ref_intensity
            self.leds_calibrated = cal_result.leds_calibrated
            self.dark_noise = cal_result.dark_noise
            self.wave_data = cal_result.wave_data
            self.fourier_weights = cal_result.fourier_weights
            self.ref_sig = cal_result.ref_sig  # S-mode reference spectra
            self.ch_error_list = cal_result.ch_error_list.copy()

            # Compute spectral correction weights from LED profiles
            self._compute_spectral_correction()

            # Mark as calibrated
            self.calibrated = True

            # Load afterglow correction if available
            self._load_afterglow_correction()

            # Emit calibration complete with settings and channel errors
            calibration_data = {
                "integration_time": self.integration_time,
                "num_scans": self.num_scans,
                "ref_intensity": self.ref_intensity,
                "leds_calibrated": self.leds_calibrated.copy(),
                "ch_error_list": self.ch_error_list.copy(),
                "calibration_type": "full",  # This is full LED calibration with afterglow
            }

            if len(self.ch_error_list) > 0:
                logger.warning(
                    f"⚠️ Calibration complete with errors in channels: {self.ch_error_list}",
                )
            else:
                logger.info("✅ Calibration complete - all channels OK")

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
        self._acquiring = True
        self._stop_acquisition.clear()

        # Start acquisition thread
        self._acquisition_thread = threading.Thread(
            target=self._acquisition_worker,
            daemon=True,
        )
        self._acquisition_thread.start()

    def stop_acquisition(self):
        """Stop spectrum acquisition and flush remaining batches."""
        if not self._acquiring:
            return

        logger.info("Stopping spectrum acquisition...")

        # Flush any remaining batched spectra before stopping
        for ch in ["a", "b", "c", "d"]:
            if len(self._spectrum_batch[ch]) > 0:
                logger.info(
                    f"Flushing {len(self._spectrum_batch[ch])} remaining spectra for channel {ch.upper()}",
                )
                self._process_and_emit_batch(ch)

        self._stop_acquisition.set()
        self._acquiring = False

        # Wait for thread to finish (with timeout)
        if self._acquisition_thread:
            self._acquisition_thread.join(timeout=2.0)

    def _acquisition_worker(self):
        """Main acquisition loop running in background thread with batched processing."""
        channels = ["a", "b", "c", "d"]
        consecutive_errors = 0
        max_consecutive_errors = 5  # Stop after 5 consecutive failures

        logger.info(f"Acquisition worker started with batch_size={self.batch_size}")

        while not self._stop_acquisition.is_set():
            try:
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

                        # Process batch when minimum size reached
                        if len(self._spectrum_batch[ch]) >= self.batch_size:
                            self._process_and_emit_batch(ch)

                # Reset error counter if we got at least one successful acquisition
                if cycle_success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    logger.warning(
                        f"Acquisition cycle failed (consecutive errors: {consecutive_errors}/{max_consecutive_errors})",
                    )

                    # Stop if too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            "Too many consecutive acquisition errors - stopping acquisition",
                        )
                        self.acquisition_error.emit(
                            "Hardware communication lost - stopping acquisition",
                        )
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
                    self.acquisition_error.emit(
                        f"Hardware error - stopping acquisition: {e}",
                    )
                    self._stop_acquisition.set()
                    break

                self.acquisition_error.emit(str(e))
                time.sleep(0.5)  # Longer delay on error

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

    def _calculate_fourier_weights(self):
        """Calculate Fourier weights for peak finding."""
        try:
            logger.info("Calculating Fourier weights...")
            for ch in ["a", "b", "c", "d"]:
                # Placeholder - would use reference spectrum
                self.fourier_weights[ch] = np.ones(len(self.wave_data))

        except Exception as e:
            logger.warning(f"Failed to calculate Fourier weights: {e}")
            # Non-fatal - can use simple peak finding

    def _process_and_emit_batch(self, channel: str) -> None:
        """Process and emit a batch of spectra for a channel.

        Processes all buffered raw spectra and emits them individually to maintain
        compatibility with existing UI code while reducing acquisition overhead.
        """
        batch = self._spectrum_batch[channel]
        timestamps = self._batch_timestamps[channel]

        if not batch:
            return

        logger.debug(
            f"Processing batch of {len(batch)} spectra for channel {channel.upper()}",
        )

        # Process each spectrum in the batch
        for spectrum_data, timestamp in zip(batch, timestamps, strict=False):
            try:
                # Process spectrum (filtering, peak finding)
                processed = self._process_spectrum(channel, spectrum_data)

                # Buffer the data
                self.channel_buffers[channel].append(processed["wavelength"])
                self.time_buffers[channel].append(timestamp)

                # Emit signal with processed data
                self.spectrum_acquired.emit(
                    {
                        "channel": channel,
                        "wavelength": processed["wavelength"],
                        "intensity": processed["intensity"],
                        "full_spectrum": processed.get("full_spectrum"),
                        "timestamp": timestamp,
                    },
                )
            except Exception as e:
                logger.error(
                    f"Error processing spectrum in batch for channel {channel}: {e}",
                )

        # Clear the batch buffers
        self._spectrum_batch[channel].clear()
        self._batch_timestamps[channel].clear()

    def _acquire_channel_spectrum(self, channel: str) -> dict | None:
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

            # Turn on LED for channel in P-mode
            led_intensity = self.leds_calibrated.get(channel, 180)
            ctrl.set_mode("p")  # P-mode
            ctrl.set_intensity(ch=channel, raw_val=led_intensity)

            # Use configured LED delay (default 45ms)
            time.sleep(self._led_delay_ms / 1000.0)  # Convert ms to seconds

            # Set integration time
            usb.set_integration(self.integration_time)

            # Read spectrum intensities
            raw_spectrum = usb.read_intensity()

            if raw_spectrum is None:
                logger.error(f"Failed to read spectrum for channel {channel}")
                return None

            # Trim spectrum to match wave_data range using stored indices from calibration
            if len(raw_spectrum) != len(self.wave_data):
                # Use indices stored during calibration (eliminates expensive USB read)
                if hasattr(self, "wave_min_index") and hasattr(self, "wave_max_index"):
                    raw_spectrum = raw_spectrum[
                        self.wave_min_index : self.wave_max_index
                    ]
                    logger.debug(
                        f"Trimmed spectrum using cached indices: {len(raw_spectrum)} points",
                    )
                else:
                    # Fallback if indices not available (shouldn't happen after calibration)
                    logger.warning(
                        f"No cached indices - trimming by length: {len(raw_spectrum)} -> {len(self.wave_data)}",
                    )
                    raw_spectrum = raw_spectrum[: len(self.wave_data)]

            return {
                "wavelength": self.wave_data.copy(),
                "intensity": raw_spectrum,
            }

        except Exception as e:
            logger.error(f"Failed to acquire spectrum for channel {channel}: {e}")
            return None

    def _process_spectrum(self, channel: str, spectrum_data: dict) -> dict:
        """Process raw spectrum (filtering, afterglow correction, peak finding)."""
        try:
            wavelength = spectrum_data["wavelength"]
            intensity = spectrum_data["intensity"]

            # Subtract dark noise
            if self.dark_noise is not None:
                intensity = intensity - self.dark_noise

            # Apply spectral correction (normalize LED profile)
            if channel in self.spectral_correction:
                intensity = intensity * self.spectral_correction[channel]
                logger.debug(
                    f"Spectral correction applied for channel {channel.upper()}",
                )

            # Apply afterglow correction if enabled and we have a previous channel
            if (
                self.afterglow_enabled
                and self.afterglow_correction is not None
                and self._previous_channel is not None
            ):
                try:
                    # Calculate expected afterglow from previous channel
                    afterglow_correction = (
                        self.afterglow_correction.calculate_correction(
                            previous_channel=self._previous_channel,
                            integration_time_ms=float(self.integration_time),
                            delay_ms=self._led_delay_ms,
                        )
                    )

                    # Apply correction (subtract afterglow)
                    intensity = intensity - afterglow_correction

                    logger.debug(
                        f"Afterglow correction applied: Ch {channel.upper()} "
                        f"(prev: {self._previous_channel.upper()}, "
                        f"correction: {afterglow_correction:.1f} counts)",
                    )
                except Exception as e:
                    logger.warning(
                        f"Afterglow correction failed for channel {channel}: {e}",
                    )

            # Track this channel as previous for next measurement
            self._previous_channel = channel

            # Find resonance peak using weighted Fourier analysis
            peak_wavelength = self._find_resonance_peak(wavelength, intensity, channel)

            return {
                "wavelength": peak_wavelength,
                "intensity": intensity[np.argmin(intensity)]
                if len(intensity) > 0
                else 0.0,
                "full_spectrum": intensity,
            }

        except Exception as e:
            logger.error(f"Failed to process spectrum: {e}")
            # Return raw data on error
            return {
                "wavelength": 650.0,  # Default
                "intensity": 0.0,
                "full_spectrum": spectrum_data["intensity"],
            }

    def _find_resonance_peak(
        self,
        wavelength: np.ndarray,
        intensity: np.ndarray,
        channel: str,
    ) -> float:
        """Find resonance peak wavelength using weighted Fourier analysis.

        Uses the Fourier transform method with pre-calculated weights to find
        the resonance dip minimum. This accounts for signal shape and provides
        better accuracy than simple minimum finding.

        Args:
            wavelength: Wavelength array
            intensity: Intensity (or transmission) array
            channel: Channel identifier for accessing channel-specific Fourier weights

        Returns:
            Resonance wavelength in nm

        """
        try:
            from utils.spr_signal_processing import find_resonance_wavelength_fourier

            # Get channel-specific Fourier weights if available
            weights = (
                self.fourier_weights.get(channel)
                if isinstance(self.fourier_weights, dict)
                else self.fourier_weights
            )

            if weights is not None and len(weights) > 0:
                # Use weighted Fourier analysis (accounts for signal shape)
                peak_wavelength = find_resonance_wavelength_fourier(
                    transmission_spectrum=intensity,
                    wavelengths=wavelength,
                    fourier_weights=weights,
                )

                # Validate result
                if (
                    not np.isnan(peak_wavelength)
                    and wavelength[0] <= peak_wavelength <= wavelength[-1]
                ):
                    logger.debug(
                        f"Ch {channel.upper()}: Fourier peak at {peak_wavelength:.3f} nm",
                    )
                    return peak_wavelength
                logger.debug(
                    f"Ch {channel.upper()}: Fourier method failed, using fallback",
                )

            # Fallback to simple minimum finding
            peak_idx = np.argmin(intensity)
            peak_wavelength = wavelength[peak_idx]
            logger.debug(
                f"Ch {channel.upper()}: Simple minimum at {peak_wavelength:.3f} nm",
            )
            return peak_wavelength

        except Exception as e:
            logger.debug(f"Peak finding error for channel {channel}: {e}")
            # Final fallback
            peak_idx = np.argmin(intensity) if len(intensity) > 0 else 0
            return wavelength[peak_idx] if len(wavelength) > peak_idx else 650.0

    def _compute_spectral_correction(self):
        """Compute spectral correction weights from S-mode reference spectra.

        The S-mode reference spectrum (ref_sig) captured during calibration shows
        the LED spectral profile for each channel. Different LEDs have different
        spectral shapes (intensity distribution across wavelengths), which can
        bias peak finding.

        This method computes correction weights to normalize the spectral profiles:
        1. Invert reference spectrum (higher signal -> lower weight)
        2. Normalize to median = 1.0 (preserve count levels)
        3. Clip extremes to prevent noise amplification (0.1 to 10.0)

        After correction, all channels have similar spectral profiles,
        eliminating LED-specific biases in resonance wavelength detection.
        """
        if not self.ref_sig:
            logger.warning("No reference spectra available for spectral correction")
            return

        self.spectral_correction = {}

        try:
            for ch, ref_spectrum in self.ref_sig.items():
                if ref_spectrum is None or len(ref_spectrum) == 0:
                    logger.warning(f"No reference spectrum for channel {ch}")
                    continue

                # Compute correction weights (invert to correct)
                # Add epsilon to prevent division by zero
                epsilon = 1e-6
                weights = 1.0 / (ref_spectrum + epsilon)

                # Normalize weights so median correction is 1.0
                # This preserves count levels and dynamic range
                median_weight = np.median(weights)
                if median_weight > 0 and np.isfinite(median_weight):
                    weights = weights / median_weight
                else:
                    logger.warning(f"Invalid median weight for channel {ch}, skipping")
                    continue

                # Sanity check: clip extreme weights to prevent noise amplification
                # Allow 10× correction range (0.1 to 10.0)
                weights = np.clip(weights, 0.1, 10.0)

                self.spectral_correction[ch] = weights

                logger.info(f"Spectral correction computed for channel {ch}")
                logger.debug(
                    f"  Weight range: {weights.min():.3f} - {weights.max():.3f}",
                )
                logger.debug(f"  Median weight: {np.median(weights):.3f}")
                logger.debug(f"  Mean weight: {np.mean(weights):.3f}")

        except Exception as e:
            logger.exception(f"Error computing spectral correction: {e}")
            self.spectral_correction = {}  # Clear on error

    def _load_afterglow_correction(self):
        """Load device-specific afterglow correction calibration."""
        try:
            from afterglow_correction import AfterglowCorrection
            from utils.device_integration import get_device_optical_calibration_path

            optical_cal_path = get_device_optical_calibration_path()

            if optical_cal_path and optical_cal_path.exists():
                self.afterglow_correction = AfterglowCorrection(optical_cal_path)
                self.afterglow_enabled = True
                logger.info(
                    f"✅ Device-specific afterglow correction loaded: {optical_cal_path.name}",
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
            else:
                logger.info("⚠️ No device-specific optical calibration found")
                logger.info(
                    "   Afterglow correction disabled (run OEM calibration from UI)",
                )
                self.afterglow_enabled = False

        except Exception as e:
            logger.warning(f"AfterglowCorrection unavailable: {e}")
            self.afterglow_enabled = False

    def clear_buffers(self):
        """Clear all data buffers."""
        for ch in ["a", "b", "c", "d"]:
            self.channel_buffers[ch].clear()
            self.time_buffers[ch].clear()
        logger.info("Data buffers cleared")
