"""Centroid-based SPR Processing Pipeline

Alternative pipeline that uses centroid calculation to find resonance wavelength.
This method finds the center of mass of the inverted transmission dip.
"""

import numpy as np
from scipy.ndimage import gaussian_filter1d

from affilabs.utils.logger import logger
from affilabs.utils.processing_pipeline import PipelineMetadata, ProcessingPipeline


class CentroidPipeline(ProcessingPipeline):
    """Pipeline using centroid method for peak detection

    This method finds the resonance wavelength by calculating the centroid
    (center of mass) of the inverted transmission spectrum around the dip region.
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Default parameters
        self.smoothing_sigma = self.config.get("smoothing_sigma", 2.0)
        self.search_window = self.config.get(
            "search_window",
            100,
        )  # pixels around minimum
        self.min_dip_depth = self.config.get(
            "min_dip_depth",
            5.0,
        )  # % transmission drop

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Centroid Method",
            description="Finds resonance via center of mass of transmission dip",
            version="1.0",
            author="ezControl Team",
            parameters={
                "smoothing_sigma": self.smoothing_sigma,
                "search_window": self.search_window,
                "min_dip_depth": self.min_dip_depth,
                "method": "Centroid (Center of Mass)",
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
        """Find resonance using centroid method with double filtering

        OPTIMIZED Algorithm (uses pre-calculated minimum hint):
        1. SKIP Gaussian smoothing (transmission already SG-filtered)
        2. Apply light Gaussian filter (sigma=1.0) for centroid weight smoothing
        3. Use minimum_hint_nm if provided, else find minimum
        4. Extract window around minimum
        5. Invert spectrum to make dip a peak
        6. Calculate centroid (weighted average) of inverted region

        Args:
            transmission: Transmission spectrum (already SG-filtered in pipeline)
            wavelengths: Wavelength array
            **kwargs: Additional parameters:
                - minimum_hint_nm: Pre-calculated minimum position (optional, skips search)
                - smoothing_sigma: Gaussian sigma for centroid weights (default: 1.0)
                - search_window: Window size around minimum (default: 100 pixels)
                - min_dip_depth: Minimum dip depth threshold (default: 5.0%)

        """
        try:
            # Allow parameter overrides
            minimum_hint_nm = kwargs.get("minimum_hint_nm")
            smoothing_sigma = kwargs.get(
                "smoothing_sigma",
                1.0,
            )  # Light smoothing for weights
            search_window = kwargs.get("search_window", self.search_window)
            min_dip_depth = kwargs.get("min_dip_depth", self.min_dip_depth)

            # DOUBLE FILTERING: Apply light Gaussian to improve centroid weight distribution
            # This is AFTER SG filter (which preserved shape), now smooth weights for better center-of-mass
            smoothed = gaussian_filter1d(transmission, sigma=smoothing_sigma)

            # Use minimum hint if provided (FAST PATH)
            if minimum_hint_nm is not None:
                # Find index closest to hint
                min_idx = np.argmin(np.abs(wavelengths - minimum_hint_nm))
                min_value = smoothed[min_idx]
            else:
                # Fallback: Find global minimum (SLOW PATH)
                min_idx = np.argmin(smoothed)
                min_value = smoothed[min_idx]

            # Define search window around minimum
            start_idx = max(0, min_idx - search_window)
            end_idx = min(len(smoothed), min_idx + search_window)

            # Extract window
            window_spectrum = smoothed[start_idx:end_idx]
            window_wavelengths = wavelengths[start_idx:end_idx]

            # Check if dip is significant enough
            baseline = np.median(transmission)
            dip_depth = baseline - min_value

            if dip_depth < min_dip_depth:
                logger.debug(
                    f"Dip too shallow ({dip_depth:.1f}% < {min_dip_depth}%), using minimum",
                )
                return float(wavelengths[min_idx])

            # Invert spectrum (make dip into peak for centroid calculation)
            # This creates weights for center-of-mass calculation
            inverted = np.max(window_spectrum) - window_spectrum

            # Ensure non-negative weights
            inverted = np.maximum(inverted, 0)

            # Calculate centroid (weighted average): Σ(λ × weight) / Σ(weight)
            if np.sum(inverted) > 0:
                centroid_wavelength = np.sum(window_wavelengths * inverted) / np.sum(
                    inverted,
                )
            else:
                # Fallback to minimum position
                centroid_wavelength = wavelengths[min_idx]

            return float(centroid_wavelength)

        except Exception as e:
            logger.debug(f"Centroid pipeline error: {e}")
            return np.nan
