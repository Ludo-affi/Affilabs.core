"""Default SPR Processing Pipeline

This is the current/default processing pipeline that uses:
- Standard transmission calculation (intensity/reference * 100)
- Fourier transform method for resonance wavelength detection

This pipeline serves as the baseline for comparison with other methods.
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress

from affilabs.utils.logger import logger
from affilabs.utils.processing_pipeline import PipelineMetadata, ProcessingPipeline


class FourierPipeline(ProcessingPipeline):
    """Default pipeline using Fourier transform for peak detection

    This is the established method that has been used in the application.
    It uses DST/IDCT to find the derivative zero-crossing point.
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Default parameters
        # CRITICAL: window_size controls linear regression refinement window around zero-crossing
        # Too large (1500) causes it to fit the edge of the peak instead of the tip
        # Reduced to 100 for tight localization around the true minimum
        self.window_size = self.config.get(
            "window_size",
            100,
        )  # Reduced from 1500 for better accuracy
        # CRITICAL: alpha=9000 achieves 2nm baseline (4.5x more smoothing than previous 2000)
        # Original implementation used 9000, providing excellent noise suppression
        self.alpha = self.config.get(
            "alpha",
            9e3,
        )  # Fourier weight parameter (9000 = original)

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Fourier Transform (Default)",
            description="Uses DST/IDCT with SNR-aware weighting to find resonance dip via derivative zero-crossing",
            version="1.0",
            author="ezControl Team",
            parameters={
                "window_size": self.window_size,
                "alpha": self.alpha,
                "method": "DST + SNR weighting + Zero-crossing",
            },
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Standard transmission calculation

        Simple transmission: (Intensity / Reference) * 100

        Note: Smoothing and baseline correction should be applied externally
        before passing to peak finding, not inside the pipeline.
        """
        if intensity.shape != reference.shape:
            raise ValueError(
                f"Shape mismatch: intensity {intensity.shape} vs reference {reference.shape}",
            )

        # Avoid division by zero
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = (intensity / reference) * 100
            transmission = np.where(reference == 0, 0, transmission)

        return transmission

    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        fourier_weights: np.ndarray = None,
        s_reference: np.ndarray = None,
        **kwargs,
    ) -> float:
        """Find resonance using Fourier transform method with SNR-aware weighting

        Algorithm:
        1. Compute Fourier coefficients using DST
        2. Apply SNR-aware weighting based on S-reference intensity (REQUIRED)
        3. Calculate derivative using IDCT
        4. Find zero-crossing of derivative
        5. Refine position using linear regression

        Args:
            transmission: Transmission spectrum
            wavelengths: Wavelength array
            fourier_weights: Pre-calculated Fourier weights
            s_reference: S-pol reference spectrum for SNR weighting (REQUIRED - critical for noise suppression)
            **kwargs: Additional parameters (window_size override, snr_strength)

        """
        try:
            # CRITICAL: Work ONLY on SPR region (560-720nm) - full calibration range
            # Must match calibration wavelength range to detect all valid peaks
            spr_mask = (wavelengths >= 560.0) & (wavelengths <= 720.0)
            if not np.any(spr_mask):
                logger.warning("No SPR region (560-720nm) in wavelength array")
                return np.nan

            # Extract SPR region only
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission[spr_mask]

            # CRITICAL: Apply SNR weighting - REQUIRED for optimal peak finding
            # S-reference tells us which wavelength regions have better signal quality
            if s_reference is None or len(s_reference) != len(transmission):
                logger.error(
                    "CRITICAL: S-reference is REQUIRED for SNR-aware peak finding!",
                )
                raise ValueError(
                    "S-reference must be provided for Fourier peak finding",
                )

            spr_s_reference = s_reference[spr_mask]
            snr_strength = kwargs.get("snr_strength", 0.3)
            snr_weights = self._calculate_snr_weights(spr_s_reference, snr_strength)
            spectrum = spr_transmission * snr_weights
            logger.debug(
                f"Applied SNR weighting (strength={snr_strength:.2f}) to SPR region",
            )

            # Find minimum hint within SPR region
            # Use simple minimum - no triangulation needed as spectrum is already baseline-corrected
            # in TransmissionProcessor before being passed to pipeline
            hint_index = np.argmin(spectrum)

            # DEBUG: Log minimum position (first few times)
            if not hasattr(self, "_debug_count"):
                self._debug_count = 0
            if self._debug_count < 3:
                print(f"\n[FOURIER-MINIMUM-HINT #{self._debug_count+1}]")
                print(
                    f"  SPR region: {spr_wavelengths[0]:.1f}-{spr_wavelengths[-1]:.1f}nm ({len(spectrum)} points)",
                )
                print(
                    f"  Minimum at index {hint_index}/{len(spectrum)}: {spr_wavelengths[hint_index]:.1f}nm",
                )
                print(f"  Transmission at minimum: {spectrum[hint_index]:.1f}%")

            # Allow window_size override
            window_size = kwargs.get("window_size", self.window_size)

            # Calculate Fourier weights for SPR region size
            fourier_weights = self._calculate_fourier_weights(len(spectrum))

            # Calculate Fourier coefficients with denoising
            fourier_coeff = np.zeros_like(spectrum)
            fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

            # Apply DST with linear detrending and Fourier weights
            detrended = (
                spectrum[1:-1]
                - np.linspace(spectrum[0], spectrum[-1], len(spectrum))[1:-1]
            )
            fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)

            # Calculate derivative using IDCT
            derivative = idct(fourier_coeff, 1)

            # Find zero-crossing near the triangulated hint position
            # Instead of searching full derivative, focus on region around hint
            search_window = min(
                200,
                len(derivative) // 4,
            )  # Search within ±200 points of hint
            search_start = max(0, hint_index - search_window)
            search_end = min(len(derivative), hint_index + search_window)

            # Find zero-crossing within search window
            derivative_window = derivative[search_start:search_end]
            zero_local = derivative_window.searchsorted(0)
            zero = search_start + zero_local

            # Define window around zero-crossing for refinement
            start = max(zero - window_size, 0)
            end = min(zero + window_size, len(spectrum) - 1)

            # Refine position using linear regression on SPR wavelengths
            line = linregress(spr_wavelengths[start:end], derivative[start:end])

            # Calculate resonance wavelength from line intercept
            fit_lambda = -line.intercept / line.slope

            # Validate result is within SPR region (should always be true now)
            # Expanded range to 560-720nm to match actual SPR calibration range
            if fit_lambda < 560.0 or fit_lambda > 720.0:
                # Should rarely happen since we're working only on SPR region
                logger.warning(
                    f"Fourier fit outside SPR region: {fit_lambda:.1f}nm - using triangulated hint",
                )
                fit_lambda = spr_wavelengths[hint_index]

            # DEBUG: Log final result (first few times)
            if hasattr(self, "_debug_count") and self._debug_count <= 3:
                print(
                    f"  Zero-crossing index: {zero}/{len(spectrum)} (searched around hint index {hint_index})",
                )
                print(
                    f"  Regression window: indices {start}-{end}, wavelengths {spr_wavelengths[start]:.1f}-{spr_wavelengths[end-1]:.1f}nm",
                )
                print(f"  RESULT: {fit_lambda:.2f}nm")
                print()
                self._debug_count += 1

            return float(fit_lambda)

        except Exception as e:
            logger.debug(f"Fourier pipeline error: {e}")
            return np.nan

    def _calculate_fourier_weights(self, n: int) -> np.ndarray:
        """Calculate Fourier weights for denoising

        Args:
            n: Length of spectrum

        Returns:
            Weight array for Fourier coefficients

        """
        n_inner = n - 1
        phi = np.pi / n_inner * np.arange(1, n_inner)
        phi2 = phi**2
        weights = phi / (1 + self.alpha * phi2 * (1 + phi2))
        return weights

    def _calculate_snr_weights(
        self,
        s_reference: np.ndarray,
        snr_strength: float = 0.3,
    ) -> np.ndarray:
        """Calculate SNR-aware weights from S-reference spectrum

        CRITICAL: High S-reference intensity regions have better SNR and get more weight.
        This is a fundamental part of the Fourier peak finding algorithm - not optional.

        SNR weighting reduces jitter by focusing on high-quality wavelength regions where
        the LED output is strong and noise is minimal.

        Args:
            s_reference: S-pol reference spectrum (counts) - REQUIRED
            snr_strength: Strength of SNR weighting (0.3 = 30% adjustment, validated)

        Returns:
            SNR weight array (normalized, ~1.0 mean)

        """
        # Normalize S-reference to 0-1 range
        s_min = np.min(s_reference)
        s_max = np.max(s_reference)
        if s_max > s_min:
            normalized_s_ref = (s_reference - s_min) / (s_max - s_min)
        else:
            normalized_s_ref = np.ones_like(s_reference)

        # Calculate SNR weights: higher intensity -> higher weight
        # weights = 1 + snr_strength * normalized_S_ref
        snr_weights = 1.0 + snr_strength * normalized_s_ref

        # Normalize to maintain similar magnitude (mean ~1.0)
        mean_weight = np.mean(snr_weights)
        if mean_weight > 0:
            snr_weights = snr_weights / mean_weight

        return snr_weights
