"""Numerical Derivative Peak Finding - EXACT OLD SOFTWARE METHOD

This is the EXACT algorithm from old software (line 1516-1539):
1. Linear baseline subtraction
2. Fourier-based derivative (DST → multiply by weights → IDCT)
3. Zero-crossing detection
4. Linear regression around zero-crossing (±165 pixel window)
5. Interpolation for sub-pixel precision

Key: Uses Fourier transform for smooth, noise-resistant derivative.

Author: Restored from old software
Date: 2025-10-21
"""

import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress

from utils.logger import logger


def find_peak_numerical_derivative(
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    search_range: tuple[float, float] = (600, 720),
    window: int = 165,
) -> float:
    """Find SPR peak using Fourier-based derivative method from old software.

    This is the EXACT method from old software that achieved <2 RU noise.

    Algorithm (from old software line 1516-1539):
    1. Extract search region
    2. Linear baseline: baseline = linspace(spectrum[0], spectrum[-1], len)
    3. Fourier coefficients:
       - fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
       - fourier_coeff[1:-1] = weights * DST(spectrum[1:-1] - baseline[1:-1])
    4. Derivative = IDCT(fourier_coeff, type=1)
    5. Zero-crossing: where derivative goes from - to +
    6. Linear regression: ±165 pixel window around zero-crossing
    7. Interpolate: peak = -intercept / slope

    Args:
        wavelengths: Wavelength array (nm)
        spectrum: Transmission spectrum
        search_range: SPR wavelength range (min, max) in nm
        window: Window size for linear regression (default 165 from old software)

    Returns:
        Peak wavelength in nm

    """
    try:
        # Step 1: Extract search region
        start_idx = np.searchsorted(wavelengths, search_range[0])
        end_idx = np.searchsorted(wavelengths, search_range[1])

        wl_region = wavelengths[start_idx:end_idx]
        spec_region = spectrum[start_idx:end_idx]

        if len(spec_region) < 10:
            logger.warning(f"Search region too small: {len(spec_region)} points")
            min_idx = np.argmin(spec_region)
            return float(wl_region[min_idx])

        # Step 2: Linear baseline (EXACT from old software)
        baseline = np.linspace(spec_region[0], spec_region[-1], len(spec_region))

        # Step 3: Calculate Fourier weights (EXACT from old software)
        # alpha = regularization parameter (default: 2000, adjustable in settings)
        # phi = pi/n * [1, 2, ..., n-1]
        # weights = phi / (1 + alpha * phi^2 * (1 + phi^2))
        from settings.settings import FOURIER_ALPHA

        alpha = FOURIER_ALPHA  # Get from settings (default: 2000)
        n = len(spec_region) - 1
        phi = np.pi / n * np.arange(1, n)
        phi2 = phi**2
        fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

        # Step 4: Fourier coefficients (EXACT from old software)
        fourier_coeff = np.zeros_like(spec_region)
        fourier_coeff[0] = 2 * (spec_region[-1] - spec_region[0])

        # DST of baseline-subtracted spectrum
        baseline_subtracted = spec_region[1:-1] - baseline[1:-1]
        fourier_coeff[1:-1] = fourier_weights * dst(baseline_subtracted, type=1)

        # Step 5: Derivative via IDCT (EXACT from old software)
        derivative = idct(fourier_coeff, type=1)

        # Step 6: Find zero-crossing (where derivative goes from - to +)
        zero_idx = derivative.searchsorted(0)

        # Validate zero-crossing
        if zero_idx < window or zero_idx > len(derivative) - window:
            logger.warning(
                f"Zero-crossing at edge (idx={zero_idx}/{len(derivative)}), using direct minimum",
            )
            min_idx = np.argmin(spec_region)
            return float(wl_region[min_idx])

        # Step 7: Linear regression around zero-crossing (±window pixels)
        start = max(zero_idx - window, 0)
        end = min(zero_idx + window, len(derivative))

        wl_fit = wl_region[start:end]
        deriv_fit = derivative[start:end]

        if len(wl_fit) < 10:
            logger.warning("Too few points for regression, using zero-crossing")
            return float(wl_region[zero_idx])

        # Linear fit: derivative = slope * wavelength + intercept
        result = linregress(wl_fit, deriv_fit)

        # Step 8: Interpolate exact wavelength where derivative = 0
        # 0 = slope * peak_wavelength + intercept
        # peak_wavelength = -intercept / slope
        if abs(result.slope) < 1e-10:
            logger.warning("Slope too small, using zero-crossing")
            return float(wl_region[zero_idx])

        peak_wavelength = -result.intercept / result.slope

        # Validate result is in reasonable range
        if not (search_range[0] <= peak_wavelength <= search_range[1]):
            logger.warning(
                f"Peak {peak_wavelength:.2f}nm outside range "
                f"({search_range[0]}, {search_range[1]}), using zero-crossing",
            )
            return float(wl_region[zero_idx])

        return float(peak_wavelength)

    except Exception as e:
        logger.error(f"Fourier derivative method failed: {e}")
        # Fallback to direct minimum
        try:
            min_idx = np.argmin(spec_region)
            return float(wl_region[min_idx])
        except Exception:
            return np.nan
        # SPR dip has negative slope before minimum, positive slope after
        zero_idx = derivative.searchsorted(0)

        # Validate zero-crossing is in reasonable range
        if zero_idx < window or zero_idx > len(derivative) - window:
            logger.warning(
                f"Zero-crossing at edge of search range (idx={zero_idx}/{len(derivative)}), "
                "using direct minimum",
            )
            min_idx = np.argmin(smoothed)
            return float(wl_region[min_idx])

        # Step 6: Linear regression around zero-crossing
        # This averages over many points (2*window) for sub-pixel precision
        start = max(zero_idx - window, 0)
        end = min(zero_idx + window, len(derivative))

        wl_fit = wl_region[start:end]
        deriv_fit = derivative[start:end]

        if len(wl_fit) < 10:
            logger.warning(
                "Too few points for linear regression, using zero-crossing index",
            )
            return float(wl_region[zero_idx])

        # Fit line: derivative = slope * wavelength + intercept
        result = linregress(wl_fit, deriv_fit)

        # Step 7: Find where derivative = 0
        # slope * lambda + intercept = 0
        # lambda = -intercept / slope
        if abs(result.slope) < 1e-10:
            logger.warning("Linear fit slope near zero, using zero-crossing index")
            return float(wl_region[zero_idx])

        peak_wavelength = -result.intercept / result.slope

        # Validate result is in search range
        if not (search_range[0] <= peak_wavelength <= search_range[1]):
            logger.warning(
                f"Peak wavelength {peak_wavelength:.2f}nm outside search range "
                f"{search_range}, using zero-crossing index",
            )
            return float(wl_region[zero_idx])

        logger.debug(
            f"Numerical derivative peak: λ={peak_wavelength:.3f}nm "
            f"(zero_idx={zero_idx}, window=±{window}, R²={result.rvalue**2:.4f})",
        )

        return float(peak_wavelength)

    except Exception as e:
        logger.error(f"Numerical derivative peak finding failed: {e}")
        # Final fallback: direct minimum in search range
        start_idx = np.searchsorted(wavelengths, search_range[0])
        end_idx = np.searchsorted(wavelengths, search_range[1])
        spec_region = spectrum[start_idx:end_idx]
        wl_region = wavelengths[start_idx:end_idx]
        min_idx = np.argmin(spec_region)
        return float(wl_region[min_idx])
