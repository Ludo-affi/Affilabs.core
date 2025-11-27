"""Direct Argmin Pipeline - Simple and Fast Peak Detection

This pipeline implements the simplest possible peak detection method:
find the minimum transmission value within the expected SPR wavelength range.

Method (from commit 6732a6b comparison):
1. Mask wavelength array to search range (e.g., 600-720nm)
2. Find argmin of transmission spectrum in that range
3. Return corresponding wavelength

This is the baseline method that all others are compared against.
Proven to be one of the top 2 optimal methods in the peak comparison study.

Author: Extracted from commit 6732a6b
Date: November 26, 2025
"""

import numpy as np

from utils.processing_pipeline import ProcessingPipeline, PipelineMetadata
from utils.logger import logger


class DirectArgminPipeline(ProcessingPipeline):
    """Direct argmin pipeline - simplest peak detection method

    This pipeline finds the SPR peak by simply locating the minimum
    transmission value within the expected wavelength range.

    Advantages:
    - Extremely fast (<0.1ms)
    - No assumptions about peak shape
    - Robust to noise (when peak is clear)
    - One of top 2 methods in comparison study

    Disadvantages:
    - No sub-pixel interpolation
    - Sensitive to noise spikes
    - No smoothing
    """

    def __init__(self, config=None):
        super().__init__(config)

        # Search range parameters
        self.search_min = self.config.get('search_min', 600.0)  # nm
        self.search_max = self.config.get('search_max', 720.0)  # nm

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="Direct Argmin (Simple & Fast)",
            description="Simple argmin within expected range. One of top 2 optimal methods from comparison study.",
            version="1.0",
            author="Extracted from commit 6732a6b",
            parameters={
                'search_min': self.search_min,
                'search_max': self.search_max,
                'method': 'Direct argmin (no interpolation)'
            }
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray
    ) -> np.ndarray:
        """Calculate transmission spectrum

        Transmission = (Intensity / Reference) * 100
        """
        if len(intensity) != len(reference):
            logger.error(f"Shape mismatch: intensity({len(intensity)}) vs reference({len(reference)})")
            return np.full_like(intensity, 50.0)

        # Avoid division by zero
        ref_safe = np.where(reference > 0, reference, 1)
        transmission = (intensity / ref_safe) * 100.0

        # Clip to valid range
        transmission = np.clip(transmission, 0, 100)

        return transmission

    def find_resonance_wavelength(
        self,
        transmission_spectrum: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs
    ) -> float:
        """Find resonance wavelength using direct argmin method

        This is the EXACT method from commit 6732a6b comparison study.

        Algorithm:
        1. Mask wavelengths to search range
        2. Find minimum transmission in masked region
        3. Return corresponding wavelength

        Args:
            transmission_spectrum: Transmission spectrum (%)
            wavelengths: Wavelength array (nm)

        Returns:
            Peak wavelength in nm
        """
        try:
            # Create mask for search range
            mask = (wavelengths >= self.search_min) & (wavelengths <= self.search_max)

            # Extract region
            region = transmission_spectrum[mask]
            wl_region = wavelengths[mask]

            # Validate region
            if len(wl_region) == 0:
                logger.warning(f"No wavelengths in search range ({self.search_min}, {self.search_max})")
                # Fallback to full spectrum minimum
                min_idx = np.argmin(transmission_spectrum)
                return float(wavelengths[min_idx])

            # Find minimum in region (direct argmin)
            min_idx = np.argmin(region)
            peak_wavelength = wl_region[min_idx]

            return float(peak_wavelength)

        except Exception as e:
            logger.error(f"Direct argmin pipeline error: {e}")
            # Final fallback: minimum of full spectrum
            min_idx = np.argmin(transmission_spectrum)
            return float(wavelengths[min_idx])
