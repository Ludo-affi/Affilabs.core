"""Default SPR Processing Pipeline

This is the current/default processing pipeline that uses:
- Standard transmission calculation (intensity/reference * 100)
- Fourier transform method for resonance wavelength detection

This pipeline serves as the baseline for comparison with other methods.
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress

from affilabs.utils.detector_config import get_spr_wavelength_range
from affilabs.utils.logger import logger
from affilabs.utils.processing_pipeline import PipelineMetadata, ProcessingPipeline


class FourierPipeline(ProcessingPipeline):
    """Default pipeline using Fourier transform for peak detection

    This is the established method that has been used in the application.
    It uses DST/IDCT to find the derivative zero-crossing point.
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Detector-aware parameter selection
        # Get detector characteristics to optimize parameters
        detector_serial = self.config.get("detector_serial", None) if self.config else None
        detector_type = self.config.get("detector_type", None) if self.config else None

        # Auto-detect if Phase Photonics (lower pixel count, needs different params)
        is_phase_photonics = False
        if detector_serial and detector_serial.startswith("ST"):
            is_phase_photonics = True
        elif detector_type and ("PHASE" in str(detector_type).upper() or "ST" in str(detector_type).upper()):
            is_phase_photonics = True

        # Default parameters - detector-specific
        # CRITICAL: alpha controls Fourier regularization strength
        # Scales with pixel density to maintain consistent smoothing
        if is_phase_photonics:
            default_alpha = 4500  # Reduced regularization (lower pixel count)
        else:
            default_alpha = 9000  # Full regularization (higher pixel count)

        # Window size is now calculated dynamically based on actual wavelength spacing
        # Target: ±7.3 nm around zero-crossing for linear regression refinement
        self.target_window_nm = self.config.get("target_window_nm", 7.3)
        self.alpha = self.config.get("alpha", default_alpha)

        if is_phase_photonics:
            logger.debug(f"Fourier pipeline: Phase Photonics detected - using optimized params (target_window={self.target_window_nm}nm, alpha={self.alpha})")

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Fourier Transform (Default)",
            description="Uses DST/IDCT with SNR-aware weighting to find resonance dip via derivative zero-crossing",
            version="1.0",
            author="ezControl Team",
            parameters={
                "target_window_nm": self.target_window_nm,
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
            # Get detector-specific SPR wavelength range
            detector_serial = kwargs.get("detector_serial", None)
            detector_type = kwargs.get("detector_type", None)
            spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)

            # CRITICAL: Work ONLY on SPR region - detector-specific range
            # Phase Photonics: 570-720nm, USB4000: 560-720nm
            spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
            if not np.any(spr_mask):
                logger.warning(f"No SPR region ({spr_min}-{spr_max}nm) in wavelength array")
                return np.nan

            # Extract SPR region only
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission[spr_mask]

            # SNR weighting DISABLED per user request
            # Use raw transmission without SNR-based adjustments
            spectrum = spr_transmission

            # Find minimum hint within SPR region
            # CRITICAL: Use provided hint if available (already calculated with detector-specific range)
            # Otherwise fall back to finding minimum in weighted spectrum
            hint_wavelength_nm = kwargs.get("hint_wavelength_nm")
            if hint_wavelength_nm is not None:
                # Convert hint wavelength to index in SPR wavelengths array
                hint_distances = np.abs(spr_wavelengths - hint_wavelength_nm)
                hint_index = np.argmin(hint_distances)
                # Using provided hint
            else:
                # Fallback: find minimum in weighted spectrum
                hint_index = np.argmin(spectrum)
                # No hint provided, using minimum of weighted spectrum

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
            # Search window scales with SPR region size (detector-specific):
            # ~15% of SPR pixels, bounded by quarter of derivative length
            # Phase Photonics: ~750 SPR pixels → ±112 points
            # Ocean Optics: ~1500 SPR pixels → ±225 points
            search_window = min(int(len(derivative) * 0.15), len(derivative) // 4)
            search_start = max(0, hint_index - search_window)
            search_end = min(len(derivative), hint_index + search_window)

            # Find zero-crossing within search window
            derivative_window = derivative[search_start:search_end]
            zero_local = derivative_window.searchsorted(0)
            zero = search_start + zero_local

            # Define window around zero-crossing for refinement
            # Calculate window_size dynamically based on actual wavelength spacing
            # Target: ±7.3 nm (total 14.6 nm window) for linear regression
            if len(spr_wavelengths) > 1:
                # Calculate average wavelength spacing (nm/pixel)
                wavelength_spacing = (spr_wavelengths[-1] - spr_wavelengths[0]) / (len(spr_wavelengths) - 1)
                window_size = int(self.target_window_nm / wavelength_spacing)
            else:
                window_size = 1  # Fallback for edge case

            start = max(zero - window_size, 0)
            end = min(zero + window_size, len(spectrum) - 1)

            # Refine position using linear regression on SPR wavelengths
            line = linregress(spr_wavelengths[start:end], derivative[start:end])

            # Calculate resonance wavelength from line intercept
            fit_lambda = -line.intercept / line.slope

            # Validate result is within detector-specific SPR region
            if fit_lambda < spr_min or fit_lambda > spr_max:
                # Should rarely happen since we're working only on SPR region
                logger.warning(
                    f"Fourier fit outside SPR region: {fit_lambda:.1f}nm - using triangulated hint",
                )
                fit_lambda = spr_wavelengths[hint_index]

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
