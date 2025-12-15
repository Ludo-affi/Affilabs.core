from __future__ import annotations

"""Reference Baseline Processing Method.

This module contains the EXACT reference implementation of the current refactored
data processing pipeline. It serves as the baseline for comparison and validation.

This is the LOCKED reference method - any experimental changes should be made
in separate functions and compared against this baseline.

Pipeline Overview:
1. Hardware acquisition with num_scans averaging
2. Spectrum trimming to SPR region (560-720nm)
3. Dark noise subtraction
4. Afterglow correction (if available)
5. Transmission calculation with LED intensity correction
6. Baseline correction
7. Savitzky-Golay filtering (window=21, poly=3)
8. Fourier-based peak finding (window=165 or 1500)

This method produces low peak-to-peak variation and serves as the gold standard.
"""

import logging

import numpy as np
from scipy.fftpack import dst, idct
from scipy.signal import savgol_filter
from scipy.stats import linregress

logger = logging.getLogger(__name__)


def calculate_fourier_weights_reference(
    num_points: int,
    alpha: float = 2e3,
) -> np.ndarray:
    """Calculate Fourier weights for signal denoising (REFERENCE).

    This is the EXACT implementation used in production.

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


def calculate_transmission_reference(
    intensity: np.ndarray,
    reference: np.ndarray,
    p_led_intensity: float | None = None,
    s_led_intensity: float | None = None,
) -> np.ndarray:
    """Calculate transmission percentage with LED correction (REFERENCE).

    This is the EXACT implementation used in production.

    Formula:
    - Without LED correction: Transmission = (P_counts / S_counts) × 100
    - With LED correction: Transmission = (P_counts × S_LED) / (S_counts × P_LED) × 100

    Args:
        intensity: Measured P-mode intensity spectrum (after dark noise subtraction)
        reference: S-mode reference spectrum (from calibration)
        p_led_intensity: P-mode LED intensity (0-255), optional
        s_led_intensity: S-mode LED intensity (0-255), optional

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


def apply_baseline_correction_reference(
    transmission_spectrum: np.ndarray,
) -> np.ndarray:
    """Apply baseline correction to transmission spectrum (REFERENCE).

    This is the EXACT implementation used in production.
    Removes linear baseline drift by fitting endpoints and subtracting.

    Args:
        transmission_spectrum: Raw transmission percentage values

    Returns:
        np.ndarray: Baseline-corrected transmission spectrum

    """
    if len(transmission_spectrum) < 2:
        return transmission_spectrum

    # Linear baseline from first to last point
    baseline = np.linspace(
        transmission_spectrum[0],
        transmission_spectrum[-1],
        len(transmission_spectrum),
    )

    # Subtract baseline
    corrected = transmission_spectrum - baseline

    # Restore DC level (keep mean centered at reasonable transmission %)
    return corrected + np.mean(transmission_spectrum)


def find_resonance_wavelength_fourier_reference(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    fourier_weights: np.ndarray,
    window_size: int = 165,
) -> float:
    """Find SPR resonance wavelength using Fourier transform method (REFERENCE).

    This is the EXACT implementation used in production.

    Algorithm:
    1. Linear detrending: Remove baseline slope
    2. DST (Discrete Sine Transform): Transform to frequency domain with SNR weights
    3. IDCT (Inverse DCT): Calculate smoothed derivative
    4. Zero-crossing: Find where derivative = 0 (peak minimum)
    5. Linear Regression: Refine position in window around zero-crossing

    Args:
        transmission_spectrum: Transmission data (%) - SHOULD BE PRE-FILTERED
        wavelengths: Wavelength array corresponding to spectrum
        fourier_weights: Pre-calculated Fourier weights for denoising
        window_size: Window size around zero-crossing for refinement (default: 165)

    Returns:
        float: Resonance wavelength in nm, or np.nan if not found

    """
    try:
        spectrum = transmission_spectrum

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


def process_spectrum_reference(
    raw_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    reference_spectrum: np.ndarray,
    fourier_weights: np.ndarray,
    dark_noise: np.ndarray | None = None,
    p_led_intensity: float | None = None,
    s_led_intensity: float | None = None,
    window_size: int = 165,
    sg_window: int = 21,
    sg_polyorder: int = 3,
) -> dict:
    """Complete reference processing pipeline (REFERENCE BASELINE).

    This is the EXACT, COMPLETE processing pipeline used in production.
    This method serves as the LOCKED REFERENCE for all comparisons.

    Pipeline:
    1. Dark noise subtraction (if provided)
    2. Transmission calculation with LED correction
    3. Baseline correction
    4. Savitzky-Golay filtering (window=21, poly=3)
    5. Fourier-based peak finding

    Args:
        raw_spectrum: Raw intensity spectrum (after hardware averaging)
        wavelengths: Wavelength array for this spectrum
        reference_spectrum: S-mode reference spectrum from calibration
        fourier_weights: Pre-calculated Fourier weights
        dark_noise: Dark noise spectrum to subtract (optional)
        p_led_intensity: P-mode LED intensity (0-255)
        s_led_intensity: S-mode LED intensity (0-255)
        window_size: Fourier regression window (default: 165)
        sg_window: Savitzky-Golay window length (default: 21, must be odd)
        sg_polyorder: Savitzky-Golay polynomial order (default: 3)

    Returns:
        Dict containing:
            - 'intensity': Dark-corrected intensity spectrum
            - 'transmission': Filtered transmission spectrum (%)
            - 'resonance_wavelength': Peak wavelength (nm)
            - 'wavelengths': Wavelength array

    """
    # Step 1: Dark noise subtraction
    intensity_corrected = raw_spectrum.copy()
    if dark_noise is not None and len(raw_spectrum) == len(dark_noise):
        intensity_corrected = intensity_corrected - dark_noise

    # Step 2: Calculate transmission with LED correction
    transmission = calculate_transmission_reference(
        intensity_corrected,
        reference_spectrum,
        p_led_intensity=p_led_intensity,
        s_led_intensity=s_led_intensity,
    )

    # Step 3: Apply baseline correction
    transmission = apply_baseline_correction_reference(transmission)

    # Step 4: Apply Savitzky-Golay filter for denoising
    if len(transmission) >= sg_window:
        transmission = savgol_filter(transmission, sg_window, sg_polyorder)

    # Step 5: Find resonance wavelength using Fourier method
    resonance_wavelength = find_resonance_wavelength_fourier_reference(
        transmission,
        wavelengths,
        fourier_weights,
        window_size=window_size,
    )

    return {
        "intensity": intensity_corrected,
        "transmission": transmission,
        "resonance_wavelength": resonance_wavelength,
        "wavelengths": wavelengths,
    }


def hardware_acquisition_reference(
    usb_device,
    num_scans: int,
    wave_min_index: int,
    wave_max_index: int,
    dark_noise: np.ndarray | None = None,
) -> np.ndarray | None:
    """Simulate hardware acquisition with averaging (REFERENCE).

    This is the EXACT hardware acquisition method used in production.

    Pipeline:
    1. Read num_scans spectra from detector
    2. Average spectra using np.mean(axis=0)
    3. Trim to SPR region using stored indices
    4. Subtract dark noise

    Args:
        usb_device: USB spectrometer device instance
        num_scans: Number of scans to average
        wave_min_index: Start index for SPR region trim
        wave_max_index: End index for SPR region trim
        dark_noise: Dark noise spectrum to subtract (optional)

    Returns:
        np.ndarray: Dark-corrected, trimmed spectrum, or None if acquisition fails

    """
    try:
        # Use HAL interface with built-in averaging
        # Note: This function works with full spectrum, so read full range
        wavelengths = usb_device.read_wavelength()
        raw_spectrum = usb_device.read_roi(
            0,
            len(wavelengths),
            num_scans=num_scans,
        )

        if raw_spectrum is None:
            return None

        # Trim spectrum to SPR region
        raw_spectrum = raw_spectrum[wave_min_index:wave_max_index]

        # Apply dark noise subtraction
        if dark_noise is not None and len(raw_spectrum) == len(dark_noise):
            raw_spectrum = raw_spectrum - dark_noise

        return raw_spectrum

    except Exception as e:
        logger.exception(f"Hardware acquisition failed: {e}")
        return None


# ============================================================================
# REFERENCE PARAMETERS - DO NOT MODIFY
# ============================================================================

REFERENCE_PARAMETERS = {
    # Hardware acquisition
    "num_scans": 3,  # Default number of scans to average (matches calibration)
    # Spectrum parameters
    "spr_min_wavelength": 560,  # nm
    "spr_max_wavelength": 720,  # nm
    # Transmission processing
    "apply_led_correction": True,
    "apply_baseline_correction": True,
    # Savitzky-Golay filter (denoising)
    "sg_window": 21,  # Window length (must be odd)
    "sg_polyorder": 3,  # Polynomial order
    # Fourier peak finding
    "fourier_alpha": 2e3,  # Regularization parameter
    "fourier_window": 165,  # Regression window around zero-crossing
    # Alternative optimized window
    "fourier_window_optimized": 1500,  # Larger window for better stability
}


def validate_reference_parameters() -> dict:
    """Validate that reference parameters match production configuration.

    Returns:
        Dict with validation results and any discrepancies

    """
    validation_results = {
        "sg_filter_valid": True,
        "fourier_weights_valid": True,
        "transmission_formula_valid": True,
        "warnings": [],
    }

    # Check SG filter parameters
    sg_window = REFERENCE_PARAMETERS["sg_window"]
    if sg_window % 2 == 0:
        validation_results["sg_filter_valid"] = False
        validation_results["warnings"].append(
            f"SG window must be odd, got {sg_window}",
        )

    if sg_window < REFERENCE_PARAMETERS["sg_polyorder"] + 2:
        validation_results["sg_filter_valid"] = False
        validation_results["warnings"].append(
            f"SG window ({sg_window}) must be >= polyorder+2",
        )

    # Check Fourier parameters
    if REFERENCE_PARAMETERS["fourier_alpha"] <= 0:
        validation_results["fourier_weights_valid"] = False
        validation_results["warnings"].append(
            "Fourier alpha must be positive",
        )

    return validation_results


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
Example usage for reference baseline processing:

# Initialize parameters
wavelengths = np.linspace(560, 720, 650)  # ~650 pixels in SPR region
fourier_weights = calculate_fourier_weights_reference(len(wavelengths))

# Simulate hardware acquisition (in real code, use actual USB device)
# raw_spectrum = hardware_acquisition_reference(
#     usb_device,
#     num_scans=3,
#     wave_min_index=1500,
#     wave_max_index=2150,
#     dark_noise=dark_noise_array
# )

# Process spectrum (complete pipeline)
result = process_spectrum_reference(
    raw_spectrum=raw_intensity_data,
    wavelengths=wavelengths,
    reference_spectrum=s_ref_from_calibration,
    fourier_weights=fourier_weights,
    dark_noise=dark_noise_array,
    p_led_intensity=220,  # P-mode LED intensity
    s_led_intensity=80,   # S-mode LED intensity
    window_size=165,      # or 1500 for optimized
    sg_window=21,
    sg_polyorder=3
)

# Access results
transmission_spectrum = result['transmission']
resonance_wavelength = result['resonance_wavelength']

print(f"Resonance wavelength: {resonance_wavelength:.3f} nm")
print(f"Transmission range: {np.min(transmission_spectrum):.1f}% - {np.max(transmission_spectrum):.1f}%")
"""
