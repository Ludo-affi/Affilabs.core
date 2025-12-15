"""Backward compatibility wrapper for existing code

This module provides drop-in replacements for the old processing functions
that now use the pipeline system internally. This allows existing code to
work without modification while benefiting from the new architecture.
"""

import numpy as np

from utils.logger import logger
from utils.processing_pipeline import get_pipeline_registry


def calculate_transmission(intensity: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Calculate transmission using active pipeline

    Backward compatible wrapper for existing code.

    Args:
        intensity: Measured intensity (after dark subtraction)
        reference: Reference spectrum

    Returns:
        Transmission spectrum

    """
    try:
        registry = get_pipeline_registry()
        pipeline = registry.get_active_pipeline()
        return pipeline.calculate_transmission(intensity, reference)
    except Exception as e:
        logger.error(f"Transmission calculation failed: {e}")
        # Fallback to simple calculation
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = (intensity / reference) * 100
            transmission = np.where(reference == 0, 0, transmission)
        return transmission


def find_resonance_wavelength_fourier(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    fourier_weights: np.ndarray = None,
    window_size: int = 165,
) -> float:
    """Find resonance wavelength using active pipeline

    Backward compatible wrapper for existing code.

    Args:
        transmission_spectrum: Transmission data
        wavelengths: Wavelength array
        fourier_weights: Fourier weights (for Fourier pipeline compatibility)
        window_size: Window size (for Fourier pipeline compatibility)

    Returns:
        Resonance wavelength in nm, or np.nan if not found

    """
    try:
        registry = get_pipeline_registry()
        pipeline = registry.get_active_pipeline()

        # Pass pipeline-specific kwargs
        kwargs = {}
        if fourier_weights is not None:
            kwargs["fourier_weights"] = fourier_weights
        if window_size:
            kwargs["window_size"] = window_size

        return pipeline.find_resonance_wavelength(
            transmission_spectrum,
            wavelengths,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"Resonance finding failed: {e}")
        return np.nan


def apply_centered_median_filter(
    values: np.ndarray,
    current_index: int,
    window_size: int,
) -> float:
    """Apply median filter (unchanged - not part of pipeline)

    This function operates on lambda values over time, not on spectra,
    so it remains outside the processing pipeline.

    Args:
        values: Array of lambda values
        current_index: Current position in array
        window_size: Median filter window size

    Returns:
        Filtered value at current position

    """
    # Determine window for median filter
    half_window = window_size // 2
    start = max(0, current_index - half_window)
    end = min(len(values), current_index + half_window + 1)

    # Extract window
    window = values[start:end]

    # Apply median filter
    if len(window) >= 3:
        filtered = float(np.median(window))
    else:
        filtered = float(values[current_index])

    return filtered


def calculate_fourier_weights(n: int, alpha: float = 2e3) -> np.ndarray:
    """Calculate Fourier weights for denoising

    This is used by the Fourier pipeline and remains available for
    backward compatibility.

    Args:
        n: Length of spectrum
        alpha: Weight parameter

    Returns:
        Weight array for Fourier coefficients

    """
    n_inner = n - 1
    phi = np.pi / n_inner * np.arange(1, n_inner)
    phi2 = phi**2
    weights = phi / (1 + alpha * phi2 * (1 + phi2))
    return weights
