"""Spectrum Processing Service

Pure business logic for spectrum processing operations.
NO Qt dependencies - fully testable.
"""

import logging

import numpy as np
from scipy import signal
from scipy.ndimage import gaussian_filter1d

logger = logging.getLogger(__name__)


class SpectrumProcessor:
    """General spectrum processing operations.

    This service provides:
    - Smoothing (Savitzky-Golay, moving average, Gaussian)
    - Peak detection
    - Derivative calculation
    - Spectral interpolation
    - ROI extraction
    """

    def smooth_savgol(
        self,
        spectrum: np.ndarray,
        window_length: int = 11,
        polyorder: int = 2,
    ) -> np.ndarray:
        """Apply Savitzky-Golay smoothing filter.

        Args:
            spectrum: Input spectrum
            window_length: Filter window size (must be odd, >= polyorder + 2)
            polyorder: Polynomial order

        Returns:
            Smoothed spectrum

        """
        if len(spectrum) < window_length:
            logger.warning(
                f"Spectrum too short for window {window_length}, using {len(spectrum)}",
            )
            window_length = len(spectrum) if len(spectrum) % 2 == 1 else len(spectrum) - 1

        if window_length < polyorder + 2:
            polyorder = window_length - 2
            logger.warning(f"Adjusted polyorder to {polyorder}")

        return signal.savgol_filter(spectrum, window_length, polyorder, mode="nearest")

    def smooth_moving_average(
        self,
        spectrum: np.ndarray,
        window_size: int = 5,
    ) -> np.ndarray:
        """Apply moving average smoothing.

        Args:
            spectrum: Input spectrum
            window_size: Averaging window size

        Returns:
            Smoothed spectrum

        """
        kernel = np.ones(window_size) / window_size
        return np.convolve(spectrum, kernel, mode="same")

    def smooth_gaussian(
        self,
        spectrum: np.ndarray,
        sigma: float = 2.0,
    ) -> np.ndarray:
        """Apply Gaussian smoothing.

        Args:
            spectrum: Input spectrum
            sigma: Standard deviation of Gaussian kernel

        Returns:
            Smoothed spectrum

        """
        return gaussian_filter1d(spectrum, sigma, mode="nearest")

    def find_peaks(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
        prominence: float | None = None,
        distance: int | None = None,
    ) -> tuple[np.ndarray, dict]:
        """Find peaks in spectrum.

        Args:
            spectrum: Input spectrum
            wavelengths: Wavelength array (optional)
            prominence: Minimum peak prominence
            distance: Minimum distance between peaks (in points)

        Returns:
            Tuple of (peak_indices, peak_properties)

        """
        # Auto-determine prominence if not provided
        if prominence is None:
            prominence = 0.05 * (np.max(spectrum) - np.min(spectrum))

        # Find peaks
        peak_indices, properties = signal.find_peaks(
            spectrum,
            prominence=prominence,
            distance=distance,
        )

        # Add wavelength info if available
        if wavelengths is not None and len(wavelengths) == len(spectrum):
            properties["wavelengths"] = wavelengths[peak_indices]

        # Add intensities
        properties["intensities"] = spectrum[peak_indices]

        return peak_indices, properties

    def calculate_derivative(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray | None = None,
        order: int = 1,
    ) -> np.ndarray:
        """Calculate spectrum derivative.

        Args:
            spectrum: Input spectrum
            wavelengths: Wavelength array for proper scaling
            order: Derivative order (1 or 2)

        Returns:
            Derivative spectrum

        """
        if wavelengths is not None and len(wavelengths) == len(spectrum):
            dx = np.gradient(wavelengths)
        else:
            dx = 1.0

        if order == 1:
            return np.gradient(spectrum, dx)
        if order == 2:
            first_deriv = np.gradient(spectrum, dx)
            return np.gradient(first_deriv, dx)
        raise ValueError(f"Unsupported derivative order: {order}")

    def interpolate(
        self,
        spectrum: np.ndarray,
        old_wavelengths: np.ndarray,
        new_wavelengths: np.ndarray,
        kind: str = "linear",
    ) -> np.ndarray:
        """Interpolate spectrum to new wavelength grid.

        Args:
            spectrum: Input spectrum
            old_wavelengths: Original wavelength array
            new_wavelengths: Target wavelength array
            kind: Interpolation method ('linear', 'cubic')

        Returns:
            Interpolated spectrum

        """
        from scipy.interpolate import interp1d

        f = interp1d(
            old_wavelengths,
            spectrum,
            kind=kind,
            bounds_error=False,
            fill_value="extrapolate",
        )
        return f(new_wavelengths)

    def extract_roi(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray,
        roi_start: float,
        roi_end: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extract region of interest from spectrum.

        Args:
            spectrum: Input spectrum
            wavelengths: Wavelength array
            roi_start: ROI start wavelength (nm)
            roi_end: ROI end wavelength (nm)

        Returns:
            Tuple of (roi_spectrum, roi_wavelengths)

        """
        mask = (wavelengths >= roi_start) & (wavelengths <= roi_end)
        return spectrum[mask], wavelengths[mask]

    def calculate_centroid(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray,
        roi_start: float | None = None,
        roi_end: float | None = None,
    ) -> float:
        """Calculate spectral centroid (weighted mean wavelength).

        Args:
            spectrum: Input spectrum
            wavelengths: Wavelength array
            roi_start: ROI start wavelength (optional)
            roi_end: ROI end wavelength (optional)

        Returns:
            Centroid wavelength (nm)

        """
        # Extract ROI if specified
        if roi_start is not None and roi_end is not None:
            spectrum, wavelengths = self.extract_roi(
                spectrum,
                wavelengths,
                roi_start,
                roi_end,
            )

        # Calculate weighted mean
        if np.sum(spectrum) == 0:
            return float(np.mean(wavelengths))

        centroid = np.sum(wavelengths * spectrum) / np.sum(spectrum)
        return float(centroid)

    def calculate_fwhm(
        self,
        spectrum: np.ndarray,
        wavelengths: np.ndarray,
        peak_index: int | None = None,
    ) -> tuple[float, float, float]:
        """Calculate Full Width at Half Maximum of a peak.

        Args:
            spectrum: Input spectrum
            wavelengths: Wavelength array
            peak_index: Index of peak (if None, uses global maximum)

        Returns:
            Tuple of (fwhm, left_wavelength, right_wavelength)

        """
        if peak_index is None:
            peak_index = np.argmax(spectrum)

        peak_value = spectrum[peak_index]
        half_max = peak_value / 2.0

        # Find left crossing
        left_indices = np.where(
            (spectrum[:peak_index] <= half_max) & (np.diff(spectrum[: peak_index + 1]) > 0),
        )[0]
        left_index = left_indices[-1] if len(left_indices) > 0 else 0

        # Find right crossing
        right_indices = np.where(
            (spectrum[peak_index:] <= half_max) & (np.diff(spectrum[peak_index:]) < 0),
        )[0]
        right_index = peak_index + right_indices[0] if len(right_indices) > 0 else len(spectrum) - 1

        fwhm = wavelengths[right_index] - wavelengths[left_index]

        return (
            float(fwhm),
            float(wavelengths[left_index]),
            float(wavelengths[right_index]),
        )

    def normalize(
        self,
        spectrum: np.ndarray,
        method: str = "minmax",
    ) -> np.ndarray:
        """Normalize spectrum.

        Args:
            spectrum: Input spectrum
            method: Normalization method ('minmax', 'zscore', 'max')

        Returns:
            Normalized spectrum

        """
        if method == "minmax":
            # Scale to [0, 1]
            min_val = np.min(spectrum)
            max_val = np.max(spectrum)
            if max_val == min_val:
                return np.ones_like(spectrum)
            return (spectrum - min_val) / (max_val - min_val)

        if method == "zscore":
            # Z-score normalization
            mean = np.mean(spectrum)
            std = np.std(spectrum)
            if std == 0:
                return np.zeros_like(spectrum)
            return (spectrum - mean) / std

        if method == "max":
            # Scale by maximum value
            max_val = np.max(spectrum)
            if max_val == 0:
                return np.zeros_like(spectrum)
            return spectrum / max_val

        raise ValueError(f"Unknown normalization method: {method}")
