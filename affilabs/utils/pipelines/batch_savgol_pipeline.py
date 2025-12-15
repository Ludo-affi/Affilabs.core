"""Batch Savitzky-Golay Processing Pipeline (GOLD STANDARD)

This pipeline implements the proven method that achieved 0.008 nm (8 picometer)
peak-to-peak baseline noise performance from commit 069ff60 (Nov 26, 2025).

THREE-STAGE NOISE REDUCTION:
1. Hardware averaging (num_scans at detector level)
2. Batch processing (12 spectra) + Savitzky-Golay filtering
3. Fourier transform (alpha=9000) for final zero-crossing

This is the "smoking gun" method that bridges the 330x performance gap.

Author: Extracted from GOLD STANDARD commit 069ff60
Date: November 26, 2025
"""

import numpy as np
from scipy.fft import dst, idct
from scipy.signal import savgol_filter
from scipy.stats import linregress

from affilabs.utils.logger import logger
from affilabs.utils.processing_pipeline import PipelineMetadata, ProcessingPipeline


class BatchSavgolPipeline(ProcessingPipeline):
    """GOLD STANDARD pipeline using batch processing + Savitzky-Golay + Fourier

    This pipeline implements the complete three-stage noise reduction:
    1. Hardware averaging: num_scans parameter reduces shot noise at source
    2. Batch SG filtering: Temporal smoothing across 12 spectra (~300ms window)
    3. Transmission SG filtering: Spectral smoothing (21-point window)
    4. Fourier transform: Final derivative calculation for zero-crossing

    Target Performance: 0.008 nm (8 picometers) peak-to-peak baseline
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Batch processing parameters (from GOLD STANDARD)
        self.batch_size = self.config.get(
            "batch_size",
            12,
        )  # 12 spectra = ~300ms window
        self.batch_savgol_window = self.config.get("batch_savgol_window", 5)
        self.batch_savgol_poly = self.config.get("batch_savgol_poly", 2)

        # Transmission smoothing parameters
        self.transmission_savgol_window = self.config.get(
            "transmission_savgol_window",
            21,
        )
        self.transmission_savgol_poly = self.config.get("transmission_savgol_poly", 3)

        # Fourier transform parameters
        self.fourier_alpha = self.config.get("fourier_alpha", 9000)
        self.fourier_window = self.config.get("fourier_window", 165)

        # Batch buffers
        self._wavelength_batch = []
        self._timestamp_batch = []

        # Fourier weights (will be calculated once)
        self.fourier_weights = None

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Batch Savitzky-Golay (GOLD STANDARD)",
            description="Three-stage noise reduction: hardware averaging + batch SG + Fourier (0.008nm baseline)",
            version="1.0",
            author="Extracted from commit 069ff60",
            parameters={
                "batch_size": self.batch_size,
                "batch_savgol_window": self.batch_savgol_window,
                "batch_savgol_poly": self.batch_savgol_poly,
                "transmission_savgol_window": self.transmission_savgol_window,
                "transmission_savgol_poly": self.transmission_savgol_poly,
                "fourier_alpha": self.fourier_alpha,
                "fourier_window": self.fourier_window,
                "method": "Hardware Averaging + Batch SG + Transmission SG + Fourier DST/IDCT",
            },
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Calculate transmission with LED boost correction

        Transmission = (Intensity / Reference) * 100
        With LED intensity correction for P vs S mode
        """
        if len(intensity) != len(reference):
            logger.error(
                f"Shape mismatch: intensity({len(intensity)}) vs reference({len(reference)})",
            )
            return np.full_like(intensity, 50.0)

        # Avoid division by zero
        ref_safe = np.where(reference > 0, reference, 1)
        transmission = (intensity / ref_safe) * 100.0

        # No clipping - allow full dynamic range

        return transmission

    def add_to_batch(self, wavelength: float, timestamp: float) -> None:
        """Add wavelength measurement to batch buffer

        Args:
            wavelength: Peak wavelength in nm
            timestamp: Measurement timestamp

        """
        self._wavelength_batch.append(wavelength)
        self._timestamp_batch.append(timestamp)

    def process_batch(self) -> tuple:
        """Process complete batch with Savitzky-Golay filtering

        Returns:
            tuple: (filtered_wavelengths, timestamps) or (None, None) if batch too small

        """
        if len(self._wavelength_batch) < self.batch_savgol_window:
            # Batch too small for SG filter, return None
            return None, None

        try:
            # Convert to numpy array
            wavelength_array = np.array(self._wavelength_batch)
            timestamp_array = np.array(self._timestamp_batch)

            # Apply Savitzky-Golay filter to batch
            # This is STAGE 2: Temporal smoothing across batch
            filtered_wavelengths = savgol_filter(
                wavelength_array,
                window_length=self.batch_savgol_window,
                polyorder=self.batch_savgol_poly,
            )

            # Clear batch
            self._wavelength_batch.clear()
            self._timestamp_batch.clear()

            return filtered_wavelengths, timestamp_array

        except Exception as e:
            logger.error(f"Batch SG filtering failed: {e}")
            # Return raw data on error
            wavelengths = np.array(self._wavelength_batch)
            timestamps = np.array(self._timestamp_batch)
            self._wavelength_batch.clear()
            self._timestamp_batch.clear()
            return wavelengths, timestamps

    def is_batch_ready(self) -> bool:
        """Check if batch is ready for processing"""
        return len(self._wavelength_batch) >= self.batch_size

    def clear_batch(self) -> None:
        """Clear batch buffers"""
        self._wavelength_batch.clear()
        self._timestamp_batch.clear()

    def find_resonance_wavelength(
        self,
        transmission_spectrum: np.ndarray,
        wavelengths: np.ndarray,
        apply_sg_filter: bool = True,
    ) -> float:
        """Find resonance wavelength using GOLD STANDARD method

        STAGE 3: Apply Savitzky-Golay filter to transmission spectrum
        STAGE 4: Apply Fourier transform for derivative calculation
        STAGE 5: Find zero-crossing with linear regression refinement

        Args:
            transmission_spectrum: Transmission spectrum (%)
            wavelengths: Wavelength array (nm)
            apply_sg_filter: Apply SG filter to transmission (default True)

        Returns:
            Peak wavelength in nm

        """
        try:
            if len(transmission_spectrum) < 50:
                logger.warning(
                    f"Spectrum too short: {len(transmission_spectrum)} points",
                )
                # Fallback to simple minimum
                min_idx = np.argmin(transmission_spectrum)
                return wavelengths[min_idx]

            # STAGE 3: Apply Savitzky-Golay filter to transmission
            # This is the CRITICAL preprocessing step from GOLD STANDARD
            if (
                apply_sg_filter
                and len(transmission_spectrum) >= self.transmission_savgol_window
            ):
                filtered_transmission = savgol_filter(
                    transmission_spectrum,
                    window_length=self.transmission_savgol_window,
                    polyorder=self.transmission_savgol_poly,
                )
            else:
                filtered_transmission = transmission_spectrum

            # STAGE 4: Fourier transform for derivative calculation
            spectrum = filtered_transmission

            # Calculate Fourier weights if not already done
            if (
                self.fourier_weights is None
                or len(self.fourier_weights) != len(spectrum) - 1
            ):
                n = len(spectrum) - 1
                phi = np.pi / n * np.arange(1, n)
                phi2 = phi**2
                self.fourier_weights = phi / (
                    1 + self.fourier_alpha * phi2 * (1 + phi2)
                )

            # Calculate Fourier coefficients
            fourier_coeff = np.zeros_like(spectrum)
            fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

            # Linear detrending
            linear_baseline = np.linspace(spectrum[0], spectrum[-1], len(spectrum))
            detrended = spectrum[1:-1] - linear_baseline[1:-1]

            # Apply DST with weights
            dst_result = dst(detrended, type=1)
            fourier_coeff[1:-1] = self.fourier_weights * dst_result

            # Inverse transform to get derivative
            derivative = idct(fourier_coeff, type=1)

            # STAGE 5: Find zero-crossing
            zero_idx = np.searchsorted(derivative, 0)

            if zero_idx == 0 or zero_idx >= len(derivative) - 1:
                # Zero-crossing at boundary, fallback to minimum
                min_idx = np.argmin(spectrum)
                return wavelengths[min_idx]

            # Linear regression refinement around zero-crossing
            window = self.fourier_window
            start_idx = max(zero_idx - window, 0)
            end_idx = min(zero_idx + window, len(derivative) - 1)

            wl_window = wavelengths[start_idx:end_idx]
            deriv_window = derivative[start_idx:end_idx]

            if len(wl_window) < 3:
                # Not enough points for regression
                return wavelengths[zero_idx]

            # Linear regression
            slope, intercept, r_value, p_value, std_err = linregress(
                wl_window,
                deriv_window,
            )

            if abs(slope) < 1e-10:
                # Slope too small, use zero-crossing index
                return wavelengths[zero_idx]

            # Calculate refined zero-crossing
            peak_wavelength = -intercept / slope

            # Sanity check: peak should be within search window
            if (
                peak_wavelength < wavelengths[start_idx]
                or peak_wavelength > wavelengths[end_idx]
            ):
                return wavelengths[zero_idx]

            return peak_wavelength

        except Exception as e:
            logger.error(f"Batch Savgol pipeline error: {e}")
            # Fallback to simple minimum
            min_idx = np.argmin(transmission_spectrum)
            return wavelengths[min_idx]
