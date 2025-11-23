"""SPR signal processing utilities.

This module provides signal processing functions for Surface Plasmon Resonance (SPR)
data analysis, including transmission calculation, resonance peak detection using
Fourier transform methods, and median filtering.
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress
from utils.logger import logger


def calculate_transmission(intensity: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Calculate transmission percentage from intensity and reference signals.

    Transmission = (Intensity / Reference) * 100

    Args:
        intensity: Measured intensity spectrum (after dark noise subtraction)
        reference: Reference spectrum (S-mode calibration)

    Returns:
        np.ndarray: Transmission spectrum as percentage (0-100%)

    Raises:
        ValueError: If arrays have incompatible shapes
    """
    if intensity.shape != reference.shape:
        raise ValueError(f"Shape mismatch: intensity {intensity.shape} vs reference {reference.shape}")

    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        transmission = (intensity / reference) * 100
        transmission = np.where(reference == 0, 0, transmission)

    return transmission


def find_resonance_wavelength_fourier(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    fourier_weights: np.ndarray,
    window_size: int = 165
) -> float:
    """Find SPR resonance wavelength using Fourier transform method.

    This method uses Discrete Sine Transform (DST) and Inverse Discrete Cosine
    Transform (IDCT) to find the derivative zero-crossing point, which corresponds
    to the resonance dip minimum.

    Algorithm:
    1. Compute Fourier coefficients using DST
    2. Calculate derivative using IDCT
    3. Find zero-crossing of derivative
    4. Refine position using linear regression in window around zero-crossing

    Args:
        transmission_spectrum: Transmission data (%)
        wavelengths: Wavelength array corresponding to spectrum
        fourier_weights: Pre-calculated Fourier weights for denoising
        window_size: Window size around zero-crossing for refinement (default: 165)

    Returns:
        float: Resonance wavelength in nm, or np.nan if not found
    """
    try:
        spectrum = transmission_spectrum

        # Calculate Fourier coefficients with denoising
        fourier_coeff = np.zeros_like(spectrum)
        fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

        # Apply DST with linear detrending and Fourier weights
        fourier_coeff[1:-1] = fourier_weights * dst(
            spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], len(spectrum))[1:-1],
            1,
        )

        # Calculate derivative using IDCT
        derivative = idct(fourier_coeff, 1)

        # Find zero-crossing (resonance minimum)
        zero = derivative.searchsorted(0)

        # Define window around zero-crossing
        start = max(zero - window_size, 0)
        end = min(zero + window_size, len(spectrum) - 1)

        # Refine position using linear regression
        line = linregress(wavelengths[start:end], derivative[start:end])

        # Calculate resonance wavelength from line intercept
        fit_lambda = -line.intercept / line.slope

        return float(fit_lambda)

    except Exception as e:
        logger.debug(f"Error finding resonance wavelength: {e}")
        return np.nan


def apply_centered_median_filter(
    values: np.ndarray,
    current_index: int,
    window_size: int
) -> float:
    """Apply centered median filter at a specific index.

    Uses a centered window around the current point for better temporal accuracy.
    For points near the beginning where a full centered window isn't available,
    uses all available data up to that point.

    Args:
        values: Array of values to filter (may contain NaN)
        current_index: Index of point to filter
        window_size: Median filter window size (should be odd)

    Returns:
        float: Filtered value (median of window), or np.nan if input is NaN
    """
    # If current value is NaN, return NaN
    if current_index >= len(values):
        return np.nan

    if np.isnan(values[current_index]):
        return np.nan

    # Not enough data for filtering yet
    if len(values) <= window_size:
        # Use all available data for initial values
        return float(np.nanmedian(values[:current_index + 1]))

    # Center the window on current point
    half_win = window_size // 2
    start_idx = max(0, current_index - half_win)
    end_idx = min(len(values), current_index + half_win + 1)

    window_data = values[start_idx:end_idx]

    return float(np.nanmedian(window_data))


def calculate_fourier_weights(num_points: int, alpha: float = 2e3) -> np.ndarray:
    """Calculate Fourier weights for signal denoising.

    These weights are used in the Fourier-based peak finding algorithm to
    suppress high-frequency noise while preserving the resonance dip feature.

    Args:
        num_points: Number of points in spectrum
        alpha: Regularization parameter (higher = more smoothing, default: 2e3)

    Returns:
        np.ndarray: Fourier weights array of length (num_points - 1)
    """
    n = num_points - 1
    phi = np.pi / n * np.arange(1, n)
    phi2 = phi**2
    weights = phi / (1 + alpha * phi2 * (1 + phi2))

    return weights
