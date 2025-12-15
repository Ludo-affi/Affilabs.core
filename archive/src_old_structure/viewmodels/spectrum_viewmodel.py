"""Spectrum View Model

Manages spectrum processing and display state.
Bridges spectrum processing services with Qt UI.
"""

import logging

import numpy as np
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SpectrumViewModel(QObject):
    """View model for spectrum acquisition and processing.

    Responsibilities:
    - Process raw spectra through services pipeline
    - Manage spectrum display state (smoothing, baseline correction)
    - Emit signals for plot updates
    - Track latest spectrum data

    Signals emitted:
    - spectrum_updated: New spectrum data ready (channel, wavelengths, transmission)
    - raw_spectrum_updated: Raw spectrum data (channel, wavelengths, intensities)
    - processing_error: Processing failed (error_message)
    - statistics_updated: Spectrum statistics (channel, stats_dict)
    """

    # Signals
    spectrum_updated = Signal(str, object, object)  # channel, wavelengths, transmission
    raw_spectrum_updated = Signal(
        str,
        object,
        object,
    )  # channel, wavelengths, intensities
    processing_error = Signal(str)  # error_message
    statistics_updated = Signal(str, dict)  # channel, stats

    def __init__(self):
        super().__init__()

        # Processing state
        self._smoothing_enabled = True
        self._smoothing_window = 11
        self._smoothing_polyorder = 2
        self._baseline_correction_enabled = True
        self._baseline_method = "polynomial"
        self._baseline_order = 1

        # Latest data cache
        self._latest_spectra = {}  # channel -> (wavelengths, transmission)
        self._latest_raw = {}  # channel -> (wavelengths, intensities)

        # Services (injected via dependency injection)
        self._transmission_calculator = None
        self._baseline_corrector = None
        self._spectrum_processor = None

    def set_services(
        self,
        transmission_calculator,
        baseline_corrector,
        spectrum_processor,
    ):
        """Inject service dependencies.

        Args:
            transmission_calculator: TransmissionCalculator instance
            baseline_corrector: BaselineCorrector instance
            spectrum_processor: SpectrumProcessor instance

        """
        from services import (
            BaselineCorrector,
            SpectrumProcessor,
            TransmissionCalculator,
        )

        if not isinstance(transmission_calculator, TransmissionCalculator):
            raise TypeError(
                f"Expected TransmissionCalculator, got {type(transmission_calculator)}",
            )
        if not isinstance(baseline_corrector, BaselineCorrector):
            raise TypeError(
                f"Expected BaselineCorrector, got {type(baseline_corrector)}",
            )
        if not isinstance(spectrum_processor, SpectrumProcessor):
            raise TypeError(
                f"Expected SpectrumProcessor, got {type(spectrum_processor)}",
            )

        self._transmission_calculator = transmission_calculator
        self._baseline_corrector = baseline_corrector
        self._spectrum_processor = spectrum_processor

        logger.debug("Spectrum processing services injected")

    def set_smoothing_enabled(self, enabled: bool):
        """Enable/disable spectrum smoothing."""
        self._smoothing_enabled = enabled
        logger.debug(f"Smoothing {'enabled' if enabled else 'disabled'}")

    def set_smoothing_parameters(self, window: int, polyorder: int):
        """Set Savitzky-Golay smoothing parameters.

        Args:
            window: Window length (must be odd)
            polyorder: Polynomial order

        """
        if window % 2 == 0:
            window += 1  # Ensure odd
        if polyorder >= window:
            polyorder = window - 1

        self._smoothing_window = window
        self._smoothing_polyorder = polyorder
        logger.debug(f"Smoothing parameters: window={window}, polyorder={polyorder}")

    def set_baseline_correction_enabled(self, enabled: bool):
        """Enable/disable baseline correction."""
        self._baseline_correction_enabled = enabled
        logger.debug(f"Baseline correction {'enabled' if enabled else 'disabled'}")

    def set_baseline_method(self, method: str, poly_order: int = 1):
        """Set baseline correction method.

        Args:
            method: 'polynomial', 'moving_min', or 'als'
            poly_order: Polynomial order (for polynomial method)

        """
        self._baseline_method = method
        self._baseline_order = poly_order
        logger.debug(f"Baseline method: {method}, order={poly_order}")

    def process_raw_spectrum(
        self,
        channel: str,
        wavelengths: np.ndarray,
        p_spectrum: np.ndarray,
        s_reference: np.ndarray,
        p_led_intensity: int | None = None,
        s_led_intensity: int | None = None,
    ):
        """Process raw P-mode spectrum through services pipeline.

        Pipeline: Calculate transmission → Baseline correction → Smoothing

        Args:
            channel: Channel identifier
            wavelengths: Wavelength array
            p_spectrum: Raw P-mode intensities
            s_reference: S-mode reference
            p_led_intensity: P-mode LED brightness
            s_led_intensity: S-mode LED brightness

        """
        if self._transmission_calculator is None:
            logger.error("Services not injected")
            self.processing_error.emit("Services not initialized")
            return

        try:
            # Store raw data
            self._latest_raw[channel] = (wavelengths.copy(), p_spectrum.copy())
            self.raw_spectrum_updated.emit(channel, wavelengths, p_spectrum)

            # Calculate transmission
            transmission = self._transmission_calculator.calculate(
                p_spectrum=p_spectrum,
                s_reference=s_reference,
                p_led_intensity=p_led_intensity,
                s_led_intensity=s_led_intensity,
            )

            # Apply baseline correction if enabled
            if self._baseline_correction_enabled:
                corrector = self._baseline_corrector
                corrector.method = self._baseline_method
                corrector.poly_order = self._baseline_order
                transmission = corrector.correct(transmission, wavelengths)

            # Apply smoothing if enabled
            if self._smoothing_enabled:
                transmission = self._spectrum_processor.smooth_savgol(
                    transmission,
                    window_length=self._smoothing_window,
                    polyorder=self._smoothing_polyorder,
                )

            # Store processed data
            self._latest_spectra[channel] = (wavelengths.copy(), transmission.copy())

            # Emit update signal
            self.spectrum_updated.emit(channel, wavelengths, transmission)

            # Calculate and emit statistics
            stats = self._transmission_calculator.get_statistics(transmission)
            self.statistics_updated.emit(channel, stats)

            logger.debug(
                f"Processed spectrum for channel {channel}: "
                f"mean={stats['mean']:.1f}%, range={stats['range']:.1f}%",
            )

        except Exception as e:
            error_msg = f"Failed to process spectrum for channel {channel}: {e}"
            logger.exception(error_msg)
            self.processing_error.emit(error_msg)

    def process_batch(
        self,
        channel: str,
        wavelengths: np.ndarray,
        p_spectra: np.ndarray,
        s_references: np.ndarray,
        p_led_intensities: np.ndarray | None = None,
        s_led_intensities: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """Process batch of spectra (vectorized).

        Args:
            channel: Channel identifier
            wavelengths: Wavelength array
            p_spectra: Batch of P-mode spectra (N × wavelengths)
            s_references: Batch of S-mode references (N × wavelengths)
            p_led_intensities: P-mode LED intensities (N,)
            s_led_intensities: S-mode LED intensities (N,)

        Returns:
            Processed transmission spectra (N × wavelengths)

        """
        if self._transmission_calculator is None:
            logger.error("Services not injected")
            return None

        try:
            # Calculate batch transmission
            transmissions = self._transmission_calculator.calculate_batch(
                p_spectra=p_spectra,
                s_references=s_references,
                p_led_intensities=p_led_intensities,
                s_led_intensities=s_led_intensities,
            )

            # Apply baseline correction if enabled
            if self._baseline_correction_enabled:
                corrector = self._baseline_corrector
                corrector.method = self._baseline_method
                corrector.poly_order = self._baseline_order
                transmissions = corrector.correct_batch(transmissions, wavelengths)

            # Apply smoothing if enabled
            if self._smoothing_enabled:
                for i in range(len(transmissions)):
                    transmissions[i] = self._spectrum_processor.smooth_savgol(
                        transmissions[i],
                        window_length=self._smoothing_window,
                        polyorder=self._smoothing_polyorder,
                    )

            logger.debug(
                f"Processed batch of {len(transmissions)} spectra for channel {channel}",
            )
            return transmissions

        except Exception as e:
            logger.exception(f"Batch processing failed: {e}")
            self.processing_error.emit(f"Batch processing failed: {e}")
            return None

    def get_latest_spectrum(self, channel: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get latest processed spectrum for channel.

        Args:
            channel: Channel identifier

        Returns:
            Tuple of (wavelengths, transmission) or None

        """
        return self._latest_spectra.get(channel)

    def get_latest_raw(self, channel: str) -> tuple[np.ndarray, np.ndarray] | None:
        """Get latest raw spectrum for channel.

        Args:
            channel: Channel identifier

        Returns:
            Tuple of (wavelengths, intensities) or None

        """
        return self._latest_raw.get(channel)

    def find_peaks(
        self,
        channel: str,
        prominence: float = 2.0,
    ) -> tuple[np.ndarray, dict] | None:
        """Find peaks in latest processed spectrum.

        Args:
            channel: Channel identifier
            prominence: Minimum peak prominence

        Returns:
            Tuple of (peak_indices, properties) or None

        """
        spectrum_data = self._latest_spectra.get(channel)
        if spectrum_data is None or self._spectrum_processor is None:
            return None

        wavelengths, transmission = spectrum_data

        try:
            peak_indices, props = self._spectrum_processor.find_peaks(
                transmission,
                wavelengths,
                prominence=prominence,
            )
            logger.debug(f"Found {len(peak_indices)} peaks in channel {channel}")
            return peak_indices, props
        except Exception as e:
            logger.exception(f"Peak finding failed: {e}")
            return None

    def calculate_centroid(self, channel: str) -> float | None:
        """Calculate spectral centroid for latest spectrum.

        Args:
            channel: Channel identifier

        Returns:
            Centroid wavelength (nm) or None

        """
        spectrum_data = self._latest_spectra.get(channel)
        if spectrum_data is None or self._spectrum_processor is None:
            return None

        wavelengths, transmission = spectrum_data

        try:
            centroid = self._spectrum_processor.calculate_centroid(
                transmission,
                wavelengths,
            )
            return centroid
        except Exception as e:
            logger.exception(f"Centroid calculation failed: {e}")
            return None

    def clear_cache(self):
        """Clear cached spectrum data."""
        self._latest_spectra.clear()
        self._latest_raw.clear()
        logger.debug("Spectrum cache cleared")
