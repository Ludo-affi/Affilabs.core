"""Clean wavelength/pixel management for SPR spectroscopy.

This module provides a cleaner architecture for managing the relationship between:
- Full detector wavelengths (441-773nm, 3648 pixels)
- Filtered SPR range (580-720nm, ~1591 pixels)
- Pixel indices vs wavelength values

The goal is to eliminate confusion between "index into filtered array" vs
"wavelength value" vs "index into full spectrum".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from utils.logger import logger


@dataclass
class WavelengthRange:
    """Represents a wavelength range with associated data.

    This class cleanly separates:
    - Wavelength values (in nm)
    - Pixel/array indices
    - Full vs filtered data
    """

    # Wavelength boundaries (nm)
    min_wavelength: float
    max_wavelength: float

    # Wavelength array for this range
    wavelengths: np.ndarray

    # Original full detector wavelengths (for creating masks)
    full_wavelengths: np.ndarray | None = None

    @property
    def num_pixels(self) -> int:
        """Number of pixels in this range."""
        return len(self.wavelengths)

    @property
    def resolution(self) -> float:
        """Wavelength resolution in nm/pixel."""
        if len(self.wavelengths) < 2:
            return 0.0
        return (self.wavelengths[-1] - self.wavelengths[0]) / (
            len(self.wavelengths) - 1
        )

    def create_mask_for_spectrum(self, spectrum_wavelengths: np.ndarray) -> np.ndarray:
        """Create a boolean mask to filter a spectrum to this wavelength range.

        This is the clean way to filter - no indices, just wavelength boundaries.

        Args:
            spectrum_wavelengths: Full detector wavelength array

        Returns:
            Boolean mask where True = pixel is in range

        """
        return (spectrum_wavelengths >= self.min_wavelength) & (
            spectrum_wavelengths <= self.max_wavelength
        )

    def filter_spectrum(
        self,
        spectrum_wavelengths: np.ndarray,
        spectrum_data: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Filter a full spectrum to this wavelength range.

        Args:
            spectrum_wavelengths: Full detector wavelengths
            spectrum_data: Full detector intensity data

        Returns:
            (filtered_wavelengths, filtered_data) tuple

        """
        mask = self.create_mask_for_spectrum(spectrum_wavelengths)
        return spectrum_wavelengths[mask], spectrum_data[mask]

    def validate_data(self, data: np.ndarray) -> bool:
        """Check if data array matches expected size for this range.

        Args:
            data: Data array to validate

        Returns:
            True if size matches, False otherwise

        """
        return len(data) == self.num_pixels

    def __repr__(self) -> str:
        return (
            f"WavelengthRange({self.min_wavelength:.1f}-{self.max_wavelength:.1f} nm, "
            f"{self.num_pixels} pixels, {self.resolution:.3f} nm/px)"
        )


class SpectralFilter:
    """Manages spectral filtering for SPR measurements.

    This provides a clean API for:
    - Defining SPR-relevant wavelength range
    - Filtering full detector spectra
    - Validating data alignment
    - No confusion about indices vs wavelengths!
    """

    def __init__(self, min_wavelength: float = 580.0, max_wavelength: float = 720.0):
        """Initialize spectral filter.

        Args:
            min_wavelength: Minimum wavelength in nm (default: 580)
            max_wavelength: Maximum wavelength in nm (default: 720)

        """
        self.min_wavelength = min_wavelength
        self.max_wavelength = max_wavelength
        self.spr_range: WavelengthRange | None = None
        self.full_range: WavelengthRange | None = None

    def calibrate(self, full_detector_wavelengths: np.ndarray) -> WavelengthRange:
        """Calibrate the filter with full detector wavelength array.

        Args:
            full_detector_wavelengths: Wavelengths from detector (e.g., 3648 points)

        Returns:
            WavelengthRange object for the filtered SPR range

        """
        # Store full range
        self.full_range = WavelengthRange(
            min_wavelength=full_detector_wavelengths[0],
            max_wavelength=full_detector_wavelengths[-1],
            wavelengths=full_detector_wavelengths.copy(),
            full_wavelengths=full_detector_wavelengths.copy(),
        )

        # Create filtered range
        mask = (full_detector_wavelengths >= self.min_wavelength) & (
            full_detector_wavelengths <= self.max_wavelength
        )
        filtered_wavelengths = full_detector_wavelengths[mask]

        self.spr_range = WavelengthRange(
            min_wavelength=self.min_wavelength,
            max_wavelength=self.max_wavelength,
            wavelengths=filtered_wavelengths.copy(),
            full_wavelengths=full_detector_wavelengths.copy(),
        )

        logger.info("📊 Spectral filter calibrated:")
        logger.info(f"   Full detector: {self.full_range}")
        logger.info(f"   SPR range: {self.spr_range}")

        return self.spr_range

    def filter(
        self,
        full_spectrum: np.ndarray,
        full_wavelengths: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Filter a full detector spectrum to SPR range.

        Args:
            full_spectrum: Full detector intensity data
            full_wavelengths: Full detector wavelengths (uses calibrated if None)

        Returns:
            (filtered_wavelengths, filtered_spectrum) tuple

        """
        if full_wavelengths is None:
            if self.full_range is None:
                raise ValueError("Must calibrate filter before use")
            full_wavelengths = self.full_range.wavelengths

        # Trim wavelengths to match spectrum size if needed
        if len(full_wavelengths) != len(full_spectrum):
            logger.debug(
                f"Trimming wavelengths from {len(full_wavelengths)} to {len(full_spectrum)}",
            )
            full_wavelengths = full_wavelengths[: len(full_spectrum)]

        # Create mask and filter
        mask = (full_wavelengths >= self.min_wavelength) & (
            full_wavelengths <= self.max_wavelength
        )

        return full_wavelengths[mask], full_spectrum[mask]

    def validate_alignment(
        self,
        data1: np.ndarray,
        data2: np.ndarray,
        label1: str = "data1",
        label2: str = "data2",
    ) -> bool:
        """Validate that two filtered datasets are properly aligned.

        Args:
            data1: First filtered dataset
            data2: Second filtered dataset
            label1: Label for first dataset (for logging)
            label2: Label for second dataset (for logging)

        Returns:
            True if aligned, False otherwise

        """
        if len(data1) != len(data2):
            logger.error(
                f"❌ Data misalignment: {label1}={len(data1)} pixels, "
                f"{label2}={len(data2)} pixels",
            )
            return False

        if self.spr_range and not self.spr_range.validate_data(data1):
            logger.warning(
                f"⚠️ {label1} size ({len(data1)}) doesn't match "
                f"expected SPR range ({self.spr_range.num_pixels})",
            )
            return False

        logger.debug(
            f"✅ Data alignment OK: {label1} and {label2} both have {len(data1)} pixels",
        )
        return True


# Singleton instance for application-wide use
_global_filter: SpectralFilter | None = None


def get_spectral_filter(min_wl: float = 580.0, max_wl: float = 720.0) -> SpectralFilter:
    """Get the global spectral filter instance.

    Args:
        min_wl: Minimum wavelength (default: 580 nm)
        max_wl: Maximum wavelength (default: 720 nm)

    Returns:
        SpectralFilter instance

    """
    global _global_filter
    if _global_filter is None:
        _global_filter = SpectralFilter(min_wl, max_wl)
    return _global_filter
