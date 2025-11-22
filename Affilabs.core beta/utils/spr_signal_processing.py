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


def calculate_snr_aware_fourier_weights(
    ref_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    alpha: float = 2e3,
    snr_weight_strength: float = 0.5
) -> np.ndarray:
    """Calculate SNR-aware Fourier weights from LED reference spectrum.

    Instead of flattening the spectrum (which creates artifacts when S-mode
    and P-mode have different LED profiles), use the S-ref spectrum as metadata
    to guide peak finding toward high-SNR regions.

    Key insights:
    - S-ref shows LED spectral strength per wavelength (proxy for SNR)
    - Higher LED intensity = higher SNR = more reliable peak data
    - Lower wavelengths (blue) have lower noise than red end
    - Weight peak finding to trust high-SNR regions more

    Algorithm:
    1. Calculate base Fourier denoising weights (frequency domain)
    2. Calculate SNR weights from ref_spectrum (spatial domain)
    3. Combine: weights = base_weights * (1 + snr_strength * snr_weights)

    Args:
        ref_spectrum: S-mode reference spectrum (LED profile, dark-subtracted)
        wavelengths: Wavelength array corresponding to spectrum
        alpha: Fourier regularization parameter (default: 2e3)
        snr_weight_strength: How much to weight toward high-SNR regions (0-1, default: 0.5)
                           0 = uniform weighting, 1 = full SNR weighting

    Returns:
        np.ndarray: Combined Fourier weights (length = num_points - 1)

    Example:
        >>> ref_spectrum = np.array([1000, 1500, 2000, 1800, 1200, 800, 500])  # LED profile
        >>> wavelengths = np.linspace(550, 700, 7)
        >>> weights = calculate_snr_aware_fourier_weights(ref_spectrum, wavelengths)
        >>> # weights will favor the 600-650nm region (peak LED intensity)
    """
    n = len(ref_spectrum) - 1

    # 1. Calculate base Fourier weights (frequency-domain denoising)
    phi = np.pi / n * np.arange(1, n)
    phi2 = phi**2
    base_weights = phi / (1 + alpha * phi2 * (1 + phi2))

    # 2. Calculate SNR weights from LED profile
    # Higher LED intensity = higher SNR = more reliable data
    # Normalize ref_spectrum to 0-1 range
    ref_normalized = ref_spectrum.copy()
    ref_min = np.min(ref_normalized)
    ref_max = np.max(ref_normalized)

    if ref_max > ref_min:
        ref_normalized = (ref_normalized - ref_min) / (ref_max - ref_min)
    else:
        ref_normalized = np.ones_like(ref_normalized)

    # SNR weights: higher where LED is strong
    # Apply to interior points (matching Fourier coefficient indexing)
    snr_weights = ref_normalized[1:-1]

    # 3. Combine base weights with SNR guidance
    # snr_weight_strength controls how much to favor high-SNR regions
    # 0 = uniform (base weights only), 1 = full SNR weighting
    combined_weights = base_weights * (1.0 + snr_weight_strength * snr_weights)

    return combined_weights


def validate_sp_orientation(
    p_spectrum: np.ndarray,
    s_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    window_px: int = 200
) -> dict:
    """Validate S/P mode orientation by checking transmission peak shape.
    
    For proper SPR transmission (P/S ratio), the resonance should appear as a DIP
    (valley, minimum). If we see a PEAK (hill, maximum), S and P are swapped.
    
    Method: Find peak position, sample ±200px, check if peak is higher than sides.
    
    Args:
        p_spectrum: P-mode intensity spectrum
        s_spectrum: S-mode reference spectrum  
        wavelengths: Wavelength array
        window_px: Number of pixels to sample on each side of peak (default 200)
        
    Returns:
        dict with:
            - 'orientation_correct': bool - True if peak is a dip (correct), False if inverted
            - 'peak_idx': int - Index of peak/dip
            - 'peak_wl': float - Wavelength of peak/dip  
            - 'peak_value': float - Transmission value at peak
            - 'left_value': float - Mean transmission 200px left of peak
            - 'right_value': float - Mean transmission 200px right of peak
            - 'is_flat': bool - True if spectrum is flat (saturation or dark)
            - 'confidence': float - Confidence score (0-1) based on peak prominence
    """
    # Calculate transmission
    transmission = calculate_transmission(p_spectrum, s_spectrum)
    
    # Find peak (could be min or max depending on orientation)
    min_idx = np.argmin(transmission)
    max_idx = np.argmax(transmission)
    
    min_val = transmission[min_idx]
    max_val = transmission[max_idx]
    
    # Determine which is more prominent
    spectrum_range = np.ptp(transmission)  # peak-to-peak amplitude
    
    # Check if flat (saturation or dark signal)
    is_flat = spectrum_range < 5.0  # Less than 5% variation = flat
    
    if is_flat:
        logger.warning(f"⚠️ S/P validation: Flat transmission spectrum (range={spectrum_range:.2f}%) - possible saturation or dark signal")
        return {
            'orientation_correct': None,  # Cannot determine
            'peak_idx': min_idx,
            'peak_wl': wavelengths[min_idx],
            'peak_value': min_val,
            'left_value': 0,
            'right_value': 0,
            'is_flat': True,
            'confidence': 0.0
        }
    
    # Use the more prominent feature (larger deviation from mean)
    mean_val = np.mean(transmission)
    min_prominence = abs(min_val - mean_val)
    max_prominence = abs(max_val - mean_val)
    
    if min_prominence > max_prominence:
        # Dip is more prominent - this is CORRECT orientation
        peak_idx = min_idx
        peak_val = min_val
        orientation_correct = True
    else:
        # Peak is more prominent - INVERTED orientation  
        peak_idx = max_idx
        peak_val = max_val
        orientation_correct = False
    
    # Sample regions ±window_px from peak
    left_start = max(0, peak_idx - window_px)
    left_end = peak_idx
    right_start = peak_idx + 1
    right_end = min(len(transmission), peak_idx + window_px + 1)
    
    left_mean = np.mean(transmission[left_start:left_end]) if left_end > left_start else peak_val
    right_mean = np.mean(transmission[right_start:right_end]) if right_end > right_start else peak_val
    
    # Calculate confidence based on how much peak differs from sides
    side_mean = (left_mean + right_mean) / 2
    confidence = min(1.0, abs(peak_val - side_mean) / (spectrum_range + 1e-6))
    
    return {
        'orientation_correct': orientation_correct,
        'peak_idx': peak_idx,
        'peak_wl': wavelengths[peak_idx],
        'peak_value': peak_val,
        'left_value': left_mean,
        'right_value': right_mean,
        'is_flat': False,
        'confidence': confidence
    }

