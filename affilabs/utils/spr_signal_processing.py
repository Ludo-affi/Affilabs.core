from __future__ import annotations

"""SPR signal processing utilities.

This module provides signal processing functions for Surface Plasmon Resonance (SPR)
data analysis, including transmission calculation, resonance peak detection using
Fourier transform methods, and median filtering.
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.signal import savgol_filter
from scipy.stats import linregress

from affilabs.utils.logger import logger


def calculate_transmission(
    intensity: np.ndarray,
    reference: np.ndarray,
    p_led_intensity: float | None = None,
    s_led_intensity: float | None = None,
) -> np.ndarray:
    """Calculate transmission percentage from intensity and reference signals.

    Accounts for different LED intensities used in P-mode (live data) vs S-mode (calibration).

    Formula:
    - Without LED correction: Transmission = (P_counts / S_counts) × 100  [WRONG if LEDs differ]
    - With LED correction: Transmission = (P_counts / P_LED) / (S_counts / S_LED) × 100
                                        = (P_counts × S_LED) / (S_counts × P_LED) × 100

    Why this matters:
    - S-mode calibration: LED=80, detector sees 52k counts
    - P-mode live data: LED=220 (boosted 2.75x), detector sees variable counts
    - Raw P/S ratio would be artificially inflated by 2.75x!
    - Correction: multiply by (S_LED / P_LED) = (80 / 220) ≈ 0.36 to normalize

    Args:
        intensity: Measured P-mode intensity spectrum (after dark noise subtraction)
        reference: S-mode reference spectrum (from calibration)
        p_led_intensity: P-mode LED intensity (0-255), optional for backward compatibility
        s_led_intensity: S-mode LED intensity (0-255), optional for backward compatibility

    Returns:
        np.ndarray: Transmission spectrum as percentage (typically 10-70% for SPR)

    Raises:
        ValueError: If arrays have incompatible shapes

    """
    if intensity.shape != reference.shape:
        msg = f"Shape mismatch: intensity {intensity.shape} vs reference {reference.shape}"
        raise ValueError(msg)

    # Avoid division by zero
    with np.errstate(divide="ignore", invalid="ignore"):
        # Calculate raw ratio
        transmission = (intensity / reference) * 100

        # Apply LED intensity correction if provided
        if (
            p_led_intensity is not None
            and s_led_intensity is not None
            and p_led_intensity > 0
        ):
            led_correction_factor = s_led_intensity / p_led_intensity
            transmission = transmission * led_correction_factor

        # Handle division by zero
        return np.where(reference == 0, 0, transmission)


def find_resonance_wavelength_fourier(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    fourier_weights: np.ndarray,
    window_size: int = 165,
    apply_sg_filter: bool = False,  # Changed to False - SG applied in pipeline before this
    sg_window: int = 21,
    sg_polyorder: int = 3,
    s_reference: np.ndarray = None,  # SNR-aware weighting
    snr_strength: float = 0.3,
) -> float:
    """Find SPR resonance wavelength using Fourier transform method.

    This method uses Discrete Sine Transform (DST) and Inverse Discrete Cosine
    Transform (IDCT) to find the derivative zero-crossing point, which corresponds
    to the resonance dip minimum.

    NOTE: The input transmission_spectrum should already be SG-filtered in the
    data processing pipeline. The apply_sg_filter parameter is provided for
    backward compatibility or special cases where additional smoothing is needed.

    Algorithm:
    1. (Optional) Apply additional Savitzky-Golay filter if requested
    2. (Optional) Apply SNR-aware weighting based on S-reference intensity
    3. Linear detrending: Remove baseline slope
    4. DST (Discrete Sine Transform): Transform to frequency domain with Fourier weights
    5. IDCT (Inverse DCT): Calculate smoothed derivative
    6. Zero-crossing: Find where derivative = 0 (peak minimum)
    7. Linear Regression: Refine position in window around zero-crossing

    Args:
        transmission_spectrum: Transmission data (%) - SHOULD BE PRE-FILTERED
        wavelengths: Wavelength array corresponding to spectrum
        fourier_weights: Pre-calculated Fourier weights for denoising
        window_size: Window size around zero-crossing for refinement (default: 165)
        apply_sg_filter: Apply additional SG filter (default: False, already done in pipeline)
        sg_window: Savitzky-Golay window length (default: 21, must be odd)
        sg_polyorder: Savitzky-Golay polynomial order (default: 3)
        s_reference: S-pol reference spectrum for SNR-aware weighting (optional)
        snr_strength: Strength of SNR weighting, 0-1 (default: 0.3)

    Returns:
        float: Resonance wavelength in nm, or np.nan if not found

    """
    try:
        spectrum = transmission_spectrum

        # OPTIONAL: Apply additional Savitzky-Golay filter if requested
        # Note: Transmission should already be SG-filtered in the main pipeline
        if apply_sg_filter and len(spectrum) >= sg_window:
            spectrum = savgol_filter(spectrum, sg_window, sg_polyorder)

        # Apply SNR-aware weighting if S-reference is provided
        if s_reference is not None and len(s_reference) == len(spectrum):
            # Normalize S-reference to 0-1 range
            s_min = np.min(s_reference)
            s_max = np.max(s_reference)
            if s_max > s_min:
                normalized_s_ref = (s_reference - s_min) / (s_max - s_min)
            else:
                normalized_s_ref = np.ones_like(s_reference)

            # Calculate SNR weights: high S-pol intensity = more weight (better SNR)
            snr_weights = 1.0 + snr_strength * normalized_s_ref

            # Normalize to mean ~1.0
            mean_weight = np.mean(snr_weights)
            if mean_weight > 0:
                snr_weights = snr_weights / mean_weight

            # Apply weights to transmission
            spectrum = spectrum * snr_weights

        # Linear detrending: Remove baseline slope
        fourier_coeff = np.zeros_like(spectrum)
        fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

        # Apply DST with linear detrending and Fourier weights
        fourier_coeff[1:-1] = fourier_weights * dst(
            spectrum[1:-1]
            - np.linspace(spectrum[0], spectrum[-1], len(spectrum))[1:-1],
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
    window_size: int,
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
        return float(np.nanmedian(values[: current_index + 1]))

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
    return phi / (1 + alpha * phi2 * (1 + phi2))


def calculate_snr_aware_fourier_weights(
    ref_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    alpha: float = 2e3,
    snr_weight_strength: float = 0.5,
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
    return base_weights * (1.0 + snr_weight_strength * snr_weights)


def validate_sp_orientation(
    p_spectrum: np.ndarray,
    s_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    window_px: int = 200,
) -> dict:
    """Validate S/P polarizer orientation by analyzing transmission spectrum ONLY.

    IMPORTANT: This function analyzes the TRANSMISSION SPECTRUM (P/S ratio) to detect
    polarizer orientation. Raw P vs S intensity comparison is NOT used here - that's
    only done during servo/polarizer calibration to find optimal positions.

    DETECTION METHOD:
    Analyze transmission spectrum (P/S ratio) for:
    - Peak shape (dip vs hill)
    - Peak depth (transmission reduction at SPR wavelength)
    - Peak width (FWHM characteristics)
    - Triangulation (peak vs edges comparison)

    For correct orientation:
    - Transmission shows a DIP (valley, minimum) due to SPR absorption
    - Peak value is LOWER than surrounding edge baselines
    - Dip depth indicates SPR coupling strength

    For inverted orientation (swapped S/P positions):
    - Transmission shows a PEAK (hill, maximum) instead of dip
    - Peak value is HIGHER than surrounding edge baselines
    - No SPR absorption visible (high transmission at resonance wavelength)

    Key insight: With weak SPR coupling (marginal water contact), the dip may be
    very shallow or barely visible. We need to distinguish between:
    - Shallow dip (correct orientation, weak coupling)
    - Actual peak/hill (inverted orientation)

    Method:
    1. Calculate transmission = P/S ratio
    2. Find local min/max in SPR region (600-750nm)
    3. Compare peak vs edge baselines
    4. Determine if structure is dip (correct) or peak (inverted)

    Args:
        p_spectrum: P-mode intensity spectrum
        s_spectrum: S-mode reference spectrum
        wavelengths: Wavelength array
        window_px: Number of pixels to sample on each side of peak (default 200)

    Returns:
        dict with:
            - 'orientation_correct': bool - True if dip detected (correct), False if peak (inverted)
            - 'peak_idx': int - Index of peak/dip
            - 'peak_wl': float - Wavelength of peak/dip
            - 'peak_value': float - Transmission value at peak
            - 'left_value': float - Mean transmission left of peak
            - 'right_value': float - Mean transmission right of peak
            - 'is_flat': bool - True if spectrum is flat (saturation or dark)
            - 'confidence': float - Confidence score (0-1) based on peak prominence

    """
    # Calculate transmission
    transmission = calculate_transmission(p_spectrum, s_spectrum)

    # Find peak (could be min or max depending on orientation)
    min_idx = np.argmin(transmission)
    max_idx = np.argmax(transmission)

    min_val = transmission[min_idx]
    transmission[max_idx]

    # Determine which is more prominent
    spectrum_range = np.ptp(transmission)  # peak-to-peak amplitude

    # Check if flat (saturation or dark signal)
    is_flat = spectrum_range < 5.0  # Less than 5% variation = flat

    if is_flat:
        logger.warning(
            f"[WARN] S/P validation: Flat transmission spectrum (range={spectrum_range:.2f}%) - possible saturation or dark signal",
        )
        return {
            "orientation_correct": None,  # Cannot determine
            "peak_idx": min_idx,
            "peak_wl": wavelengths[min_idx],
            "peak_value": min_val,
            "left_value": 0,
            "right_value": 0,
            "is_flat": True,
            "confidence": 0.0,
        }

    # NEW APPROACH: Check for local structure in SPR region (600-750nm) first
    # This is more robust than global min/max for weak coupling cases
    spr_region_start = np.searchsorted(wavelengths, 600)
    spr_region_end = np.searchsorted(wavelengths, 750)

    # Initialize edge values (will be overwritten if SPR region is valid)
    left_edge_mean = transmission[0] if len(transmission) > 0 else 0
    right_edge_mean = transmission[-1] if len(transmission) > 0 else 0

    # Initialize confidence (will be calculated based on structure prominence)
    confidence = 0.5  # Default moderate confidence

    if spr_region_end > spr_region_start:
        spr_transmission = transmission[spr_region_start:spr_region_end]
        spr_wavelengths = wavelengths[spr_region_start:spr_region_end]

        # Find local minimum in SPR region
        local_min_idx = np.argmin(spr_transmission)
        local_max_idx = np.argmax(spr_transmission)

        local_min_val = spr_transmission[local_min_idx]
        local_max_val = spr_transmission[local_max_idx]

        # Check structure: compare center vs edges of SPR region
        edge_width = min(50, len(spr_transmission) // 4)
        left_edge_mean = np.mean(spr_transmission[:edge_width])
        right_edge_mean = np.mean(spr_transmission[-edge_width:])
        edge_mean = (left_edge_mean + right_edge_mean) / 2

        # Calculate how much the min and max differ from edges
        min_deviation = local_min_val - edge_mean
        max_deviation = local_max_val - edge_mean

        logger.debug("   S/P validation in 600-750nm region:")
        logger.debug(
            f"     Min at {spr_wavelengths[local_min_idx]:.1f}nm: {local_min_val:.1f}% (deviation: {min_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Max at {spr_wavelengths[local_max_idx]:.1f}nm: {local_max_val:.1f}% (deviation: {max_deviation:+.1f}%)",
        )
        logger.debug(
            f"     Edges: left={left_edge_mean:.1f}%, right={right_edge_mean:.1f}%",
        )

        # Decision logic:
        # - If min is BELOW edges: correct orientation (has a dip)
        # - If max is ABOVE edges MORE than min is below: inverted (has a peak instead)
        # - Allow some tolerance for weak coupling (±5% is acceptable noise)

        if min_deviation < -5:  # Clear dip present
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                1.0,
                abs(min_deviation) / 30.0,
            )  # Scale: 30% deviation = 100% confidence
            logger.debug(
                f"   ✓ SPR DIP detected: {min_deviation:.1f}% below edges - CORRECT orientation",
            )
        elif max_deviation > 10:  # Clear peak present (inverted)
            orientation_correct = False
            peak_idx = spr_region_start + local_max_idx
            peak_val = local_max_val
            confidence = min(1.0, max_deviation / 30.0)
            logger.debug(
                f"   ✗ SPR PEAK detected: {max_deviation:+.1f}% above edges - INVERTED orientation",
            )
        elif abs(min_deviation) > abs(
            max_deviation,
        ):  # Subtle dip more prominent than peak
            orientation_correct = True
            peak_idx = spr_region_start + local_min_idx
            peak_val = local_min_val
            confidence = min(
                0.7,
                abs(min_deviation) / 30.0,
            )  # Lower confidence for weak signal
            logger.debug(
                f"   ✓ Subtle SPR dip detected (weak coupling): {min_deviation:.1f}% - CORRECT orientation",
            )
        else:  # Weak structure, cannot reliably determine orientation
            logger.warning(
                "   [WARN] Weak SPR structure in 600-750nm - cannot determine orientation",
            )
            # Return None (indeterminate) rather than guessing
            orientation_correct = None  # Cannot determine with confidence
            peak_idx = min_idx
            peak_val = min_val
            confidence = 0.1  # Very low confidence for indeterminate
    else:
        # No valid SPR region - cannot determine orientation
        logger.warning("   [WARN] Invalid wavelength range for SPR analysis")
        orientation_correct = None  # Cannot determine without valid SPR region
        peak_idx = min_idx
        peak_val = min_val
        confidence = 0.0  # Zero confidence for invalid range

    return {
        "orientation_correct": orientation_correct,
        "peak_idx": peak_idx,
        "peak_wl": wavelengths[peak_idx],
        "peak_value": peak_val,
        "left_value": left_edge_mean,
        "right_value": right_edge_mean,
        "is_flat": False,
        "confidence": confidence,
    }
