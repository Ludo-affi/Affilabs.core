"""Original Hybrid Peak Finding Pipeline - First Attempt (8.82 RU).

This pipeline represents the first hybrid approach combining Fourier transform
derivative analysis with aggressive multi-stage filtering. While it achieved
51% noise reduction over standard production, further optimization led to the
improved version with 90% noise reduction.

Performance (vs Standard Production):
- Baseline Noise: 8.82 RU (51% improvement from 17.98 RU)
- Position Error: 0.47 nm (46% worse than 0.32 nm)
- DC Offset: +4.20 RU (wavelength-dependent bias)

Issues Identified:
------------------
1. **Wavelength-Dependent DC Bias**: Offset varies by 11.58 RU across spectrum
2. **Excessive Position Error**: Over-aggressive filtering reduces signal fidelity
3. **Over-Complex**: Quadratic regression and Gaussian refinement add overhead

Historical Configuration:
-------------------------
HYBRID_FOURIER_ALPHA = 2000
HYBRID_SG_POLY = 5 (too aggressive)
HYBRID_GAUSSIAN_SIGMA = 1.5 (over-smoothed)
HYBRID_REGRESSION_WINDOW = 50
HYBRID_USE_QUADRATIC = True (removed in v2)
HYBRID_GAUSSIAN_REFINEMENT = True (removed in v2)

Status: Superseded by Optimized Hybrid (1.81 RU)
Date: December 3, 2025
See: data_processing_analysis/HYBRID_OPTIMIZATION_RESULTS.md
"""

import logging
from typing import Any

import numpy as np
from scipy.fft import dst, idct
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

from affilabs.utils.processing_pipeline import (
    PipelineMetadata,
    ProcessingPipeline,
    ProcessingResult,
)

logger = logging.getLogger(__name__)


class HybridOriginalPipeline(ProcessingPipeline):
    """Original hybrid pipeline: Fourier + Aggressive Multi-stage filtering."""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize original hybrid pipeline.

        Args:
            config: Optional configuration dict. If not provided, uses original defaults.

        """
        super().__init__(config)
        self.name = "Hybrid Original"
        self.description = (
            "Fourier + Aggressive filtering (51% noise reduction, first attempt)"
        )

        # Load configuration or use original defaults
        cfg = config or {}

        # Original parameters (before optimization)
        self.alpha = cfg.get("fourier_alpha", 2000)
        self.sg_window = cfg.get("sg_window", 11)
        self.sg_poly = cfg.get("sg_poly", 5)  # More aggressive than standard
        self.gaussian_sigma = cfg.get("gaussian_sigma", 1.5)  # Stronger smoothing
        self.regression_window = cfg.get("regression_window", 50)
        self.use_quadratic = cfg.get("use_quadratic", True)  # Added complexity
        self.gaussian_refinement = cfg.get("gaussian_refinement", True)  # Extra step

        logger.debug(
            f"Initialized {self.name}: alpha={self.alpha}, sg_poly={self.sg_poly}, "
            f"gaussian_sigma={self.gaussian_sigma}, quadratic={self.use_quadratic}",
        )

    def get_metadata(self) -> PipelineMetadata:
        """Return pipeline metadata."""
        return PipelineMetadata(
            name=self.name,
            description=self.description,
            version="1.0",
            author="ezControl Team",
            parameters={
                "alpha": self.alpha,
                "sg_window": self.sg_window,
                "sg_poly": self.sg_poly,
                "gaussian_sigma": self.gaussian_sigma,
                "regression_window": self.regression_window,
                "use_quadratic": self.use_quadratic,
            },
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Standard transmission calculation."""
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = (intensity / reference) * 100
            transmission = np.where(reference == 0, 0, transmission)
        return transmission

    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs,
    ) -> float:
        """Find resonance wavelength using hybrid method."""
        result = self._find_peak_hybrid(wavelengths, transmission)
        return result.resonance_wavelength if result.success else np.nan

    def _find_peak_hybrid(
        self,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
    ) -> ProcessingResult:
        """Internal processing method using original aggressive hybrid method.

        Args:
            wavelengths: Wavelength array (nm)
            transmission: Transmission values (0-1 or percentage)

        Returns:
            ProcessingResult with peak position and metadata

        """
        try:
            # Validate inputs
            if len(wavelengths) != len(transmission):
                raise ValueError(
                    "Wavelength and transmission arrays must have same length",
                )
            if len(wavelengths) < self.regression_window:
                raise ValueError(
                    f"Data length {len(wavelengths)} < regression window {self.regression_window}",
                )

            # Stage 1: Savitzky-Golay smoothing (aggressive poly=5)
            smoothed = savgol_filter(transmission, self.sg_window, self.sg_poly)

            # Stage 2: Fourier transform derivative estimation
            spectrum_dst = dst(smoothed, type=1)
            derivative_spectrum = spectrum_dst * np.arange(1, len(spectrum_dst) + 1)
            derivative_spectrum *= self.alpha
            derivative_idct = idct(derivative_spectrum, type=1) / (2 * len(smoothed))

            # Stage 3: Gaussian filtering (strong sigma=1.5)
            derivative_filtered = gaussian_filter1d(
                derivative_idct,
                sigma=self.gaussian_sigma,
            )

            # Stage 4: Find zero crossing (peak location)
            sign_changes = np.diff(np.sign(derivative_filtered))
            zero_crossings = np.where(sign_changes != 0)[0]

            if len(zero_crossings) == 0:
                return ProcessingResult(
                    transmission=transmission,
                    resonance_wavelength=np.nan,
                    metadata={
                        "error": "No zero crossings found in derivative",
                        "method": self.name,
                    },
                    success=False,
                    error_message="No zero crossings found in derivative",
                )

            # Find crossing nearest to center
            center_idx = len(wavelengths) // 2
            distances = np.abs(zero_crossings - center_idx)
            peak_idx = zero_crossings[np.argmin(distances)]
            logger.debug(
                f"[HYBRID-ORIG] Initial peak_idx from zero-crossing: {peak_idx}, wavelength: {wavelengths[peak_idx]:.2f}nm",
            )

            # Stage 5: Quadratic regression refinement (if enabled)
            if self.use_quadratic:
                half_window = self.regression_window // 2
                start_idx = max(0, peak_idx - half_window)
                end_idx = min(len(wavelengths), peak_idx + half_window)

                # Quadratic fit: y = ax^2 + bx + c
                x_window = np.arange(start_idx, end_idx)
                y_window = derivative_filtered[start_idx:end_idx]

                if len(x_window) >= 3:  # Need at least 3 points for quadratic
                    try:
                        coeffs = np.polyfit(x_window, y_window, deg=2)
                        # Find vertex of parabola: x = -b/(2a)
                        if abs(coeffs[0]) > 1e-10:
                            refined_idx = -coeffs[1] / (2 * coeffs[0])
                            logger.debug(
                                f"[HYBRID-ORIG] Quadratic refinement: refined_idx={refined_idx:.2f}, bounds=[0, {len(wavelengths)})",
                            )
                            # Validate refined index is within full array bounds
                            if 0 <= refined_idx < len(wavelengths):
                                peak_idx = int(refined_idx)
                                logger.debug(
                                    f"[HYBRID-ORIG] Accepted refined peak_idx: {peak_idx}, wavelength: {wavelengths[peak_idx]:.2f}nm",
                                )
                            else:
                                logger.warning(
                                    f"[HYBRID-ORIG] Rejected out-of-bounds refined_idx={refined_idx:.2f}, keeping peak_idx={peak_idx}",
                                )
                    except np.linalg.LinAlgError:
                        logger.warning(
                            f"[HYBRID-ORIG] Quadratic fit failed, keeping peak_idx={peak_idx}",
                        )

            # Validate peak_idx is within bounds before using it
            peak_idx = max(0, min(peak_idx, len(wavelengths) - 1))
            logger.debug(
                f"[HYBRID-ORIG] Final clamped peak_idx: {peak_idx}, wavelength: {wavelengths[peak_idx]:.2f}nm",
            )

            # Stage 6: Gaussian refinement (if enabled)
            if self.gaussian_refinement:
                half_window = 10
                start_idx = max(0, peak_idx - half_window)
                end_idx = min(len(wavelengths), peak_idx + half_window + 1)

                x_window = wavelengths[start_idx:end_idx]
                y_window = transmission[start_idx:end_idx]

                # Invert to make peak a maximum
                y_inverted = 1.0 - y_window

                # Gaussian fit: y = A * exp(-(x-mu)^2 / (2*sigma^2))
                try:
                    from scipy.optimize import curve_fit

                    def gaussian(x, amplitude, center, width):
                        return amplitude * np.exp(-((x - center) ** 2) / (2 * width**2))

                    # Initial guess
                    p0 = [np.max(y_inverted), wavelengths[peak_idx], 1.0]

                    popt, _ = curve_fit(
                        gaussian,
                        x_window,
                        y_inverted,
                        p0=p0,
                        maxfev=1000,
                    )
                    refined_center = popt[1]

                    # Validate refined position is within window
                    if x_window[0] <= refined_center <= x_window[-1]:
                        peak_wavelength = refined_center
                        logger.debug(
                            f"[HYBRID-ORIG] Gaussian refinement: {wavelengths[peak_idx]:.2f} → {peak_wavelength:.2f}nm",
                        )
                    else:
                        peak_wavelength = wavelengths[peak_idx]
                        logger.warning(
                            f"[HYBRID-ORIG] Gaussian refinement out of window, using {peak_wavelength:.2f}nm",
                        )
                except Exception as e:
                    peak_wavelength = wavelengths[peak_idx]
                    logger.debug(
                        f"[HYBRID-ORIG] Gaussian fit failed: {e}, using {peak_wavelength:.2f}nm",
                    )
            else:
                peak_wavelength = wavelengths[peak_idx]
                logger.debug(
                    f"[HYBRID-ORIG] No Gaussian refinement, final wavelength: {peak_wavelength:.2f}nm",
                )

            return ProcessingResult(
                transmission=transmission,
                resonance_wavelength=peak_wavelength,
                metadata={
                    "method": self.name,
                    "alpha": self.alpha,
                    "sg_poly": self.sg_poly,
                    "gaussian_sigma": self.gaussian_sigma,
                    "quadratic_refinement": self.use_quadratic,
                    "gaussian_refinement": self.gaussian_refinement,
                    "note": "Original hybrid - superseded by optimized version",
                },
                success=True,
            )

        except Exception as e:
            logger.error(f"Original hybrid pipeline failed: {e}", exc_info=True)
            return ProcessingResult(
                transmission=transmission if transmission is not None else np.array([]),
                resonance_wavelength=np.nan,
                metadata={"error": str(e), "method": self.name},
                success=False,
                error_message=str(e),
            )
