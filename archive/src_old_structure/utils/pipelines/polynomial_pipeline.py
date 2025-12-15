"""Polynomial Fitting SPR Processing Pipeline

Alternative pipeline that uses polynomial curve fitting to find resonance wavelength.
Fits a polynomial around the transmission dip and finds its minimum analytically.
"""

import numpy as np

from utils.logger import logger
from utils.processing_pipeline import PipelineMetadata, ProcessingPipeline


class PolynomialPipeline(ProcessingPipeline):
    """Pipeline using polynomial fitting for peak detection

    This method fits a polynomial to the transmission dip region and
    finds the minimum analytically by taking the derivative.
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Default parameters
        self.poly_degree = self.config.get("poly_degree", 4)  # 4th degree polynomial
        self.fit_window = self.config.get("fit_window", 80)  # pixels around minimum
        self.use_weighted = self.config.get(
            "use_weighted",
            True,
        )  # Weight points near minimum

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Polynomial Fitting",
            description="Fits polynomial to dip and finds minimum analytically",
            version="1.0",
            author="ezControl Team",
            parameters={
                "poly_degree": self.poly_degree,
                "fit_window": self.fit_window,
                "use_weighted": self.use_weighted,
                "method": f"Polynomial (degree {self.poly_degree})",
            },
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """Standard transmission calculation

        Transmission = (Intensity / Reference) * 100
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
        **kwargs,
    ) -> float:
        """Find resonance using polynomial fitting with analytical minimum

        OPTIMIZED Algorithm (uses pre-calculated minimum hint):
        1. Use minimum_hint_nm if provided, else find approximate minimum
        2. Extract window around minimum
        3. Fit polynomial (degree 4) to window data with optional weighting
        4. Find polynomial minimum analytically (derivative = 0)

        Args:
            transmission: Transmission spectrum (already SG-filtered)
            wavelengths: Wavelength array
            **kwargs: Additional parameters:
                - minimum_hint_nm: Pre-calculated minimum position (optional, skips search)
                - poly_degree: Polynomial degree (default: 4)
                - fit_window: Window size around minimum (default: 80 pixels)
                - use_weighted: Weight points near minimum more heavily (default: True)

        """
        try:
            # Allow parameter overrides
            minimum_hint_nm = kwargs.get("minimum_hint_nm")
            poly_degree = kwargs.get("poly_degree", self.poly_degree)
            fit_window = kwargs.get("fit_window", self.fit_window)
            use_weighted = kwargs.get("use_weighted", self.use_weighted)

            # Use minimum hint if provided (FAST PATH)
            if minimum_hint_nm is not None:
                # Find index closest to hint
                min_idx = np.argmin(np.abs(wavelengths - minimum_hint_nm))
            else:
                # Fallback: Find approximate minimum (SLOW PATH)
                min_idx = np.argmin(transmission)

            # Define fitting window around minimum
            start_idx = max(0, min_idx - fit_window)
            end_idx = min(len(transmission), min_idx + fit_window)

            # Extract window
            window_wavelengths = wavelengths[start_idx:end_idx]
            window_transmission = transmission[start_idx:end_idx]

            # Check if window is large enough for polynomial fit
            if len(window_wavelengths) < poly_degree + 2:
                logger.debug(f"Window too small for poly fit (degree {poly_degree})")
                return float(wavelengths[min_idx])

            # Fit polynomial with optional distance-based weighting
            if use_weighted:
                # Weight points closer to minimum more heavily (Gaussian weighting)
                center_wl = wavelengths[min_idx]
                distances = np.abs(window_wavelengths - center_wl)
                weights = np.exp(-(distances**2) / (2 * (fit_window / 4) ** 2))
            else:
                weights = np.ones_like(window_wavelengths)

            # Fit polynomial with weights
            poly_coeffs = np.polyfit(
                window_wavelengths,
                window_transmission,
                poly_degree,
                w=weights,
            )

            # Find minimum analytically: solve polynomial derivative = 0
            # Take derivative of polynomial
            derivative_coeffs = np.polyder(poly_coeffs)

            # Find roots of derivative (critical points)
            critical_points = np.roots(derivative_coeffs)

            # Filter for real roots within window
            real_critical = critical_points[np.isreal(critical_points)].real
            valid_critical = real_critical[
                (real_critical >= window_wavelengths[0])
                & (real_critical <= window_wavelengths[-1])
            ]

            if len(valid_critical) == 0:
                # No valid critical point found, use approximate minimum
                logger.debug("No critical point in window, using hint/minimum")
                return float(wavelengths[min_idx])

            # Evaluate polynomial at critical points to find minimum
            poly_func = np.poly1d(poly_coeffs)
            values_at_critical = poly_func(valid_critical)
            min_critical_idx = np.argmin(values_at_critical)
            resonance_wavelength = valid_critical[min_critical_idx]

            return float(resonance_wavelength)

        except Exception as e:
            logger.debug(f"Polynomial pipeline error: {e}")
            return np.nan
