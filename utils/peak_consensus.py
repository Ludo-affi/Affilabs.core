"""
Peak Consensus Algorithm for SPR Peak Detection

Combines multiple complementary peak-finding methods to reduce noise and bias.
Uses continuous methods (centroid + parabolic) to avoid binary/stepped signals.

Key Principle: Each method has different sensitivities to peak characteristics:
- Centroid: Good for broad peaks, sensitive to peak width
- Parabolic: Good for narrow peaks, sensitive to local curvature
- Consensus: Weighted combination reduces systematic bias

Avoids discrete methods (polynomial derivative) that cause stepped/binary signals.
"""

import numpy as np
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def find_peak_parabolic(
    spectrum: np.ndarray,
    wavelengths: np.ndarray,
    search_range: tuple[float, float] = (600, 720),
) -> float:
    """Find SPR peak using 3-point parabolic interpolation.

    Fast and continuous (no discrete steps). Works well for narrow, symmetric peaks.

    Args:
        spectrum: Transmission spectrum (%)
        wavelengths: Wavelength array (nm)
        search_range: SPR wavelength range (min, max) in nm

    Returns:
        Peak wavelength in nm (sub-pixel via parabolic fit)
    """
    try:
        # Extract search region
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        wl_region = wavelengths[mask]
        spec_region = spectrum[mask]

        if len(wl_region) < 3:
            logger.warning(f"Parabolic: Insufficient points: {len(wl_region)}")
            return wl_region[np.argmin(spec_region)] if len(wl_region) > 0 else np.nan

        # Find discrete minimum
        min_idx = np.argmin(spec_region)

        # Parabolic interpolation (if not at edge)
        if 0 < min_idx < len(spec_region) - 1:
            x = wl_region[min_idx-1:min_idx+2]
            y = spec_region[min_idx-1:min_idx+2]

            # Analytical parabolic vertex: y = Ax² + Bx + C, minimum at x = -B/(2A)
            denom = (x[0] - x[1]) * (x[0] - x[2]) * (x[1] - x[2])
            if abs(denom) < 1e-10:
                return wl_region[min_idx]  # Degenerate case

            A = (x[2] * (y[1] - y[0]) + x[1] * (y[0] - y[2]) + x[0] * (y[2] - y[1])) / denom
            B = (x[2]**2 * (y[0] - y[1]) + x[1]**2 * (y[2] - y[0]) + x[0]**2 * (y[1] - y[2])) / denom

            peak_wl = -B / (2 * A) if A > 0 else wl_region[min_idx]

            # Sanity check: result should be near minimum
            if abs(peak_wl - wl_region[min_idx]) > 2.0:  # More than 2nm away
                logger.debug(f"Parabolic fit suspicious, using discrete min: {peak_wl:.3f} vs {wl_region[min_idx]:.3f}")
                return wl_region[min_idx]

            return float(peak_wl)
        else:
            # Edge case: use discrete minimum
            return wl_region[min_idx]

    except Exception as e:
        logger.error(f"Parabolic method failed: {e}")
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        return wavelengths[mask][np.argmin(spectrum[mask])]


def find_peak_centroid_adaptive(
    spectrum: np.ndarray,
    wavelengths: np.ndarray,
    search_range: tuple[float, float] = (600, 720),
) -> Tuple[float, Dict]:
    """Find SPR peak using adaptive centroid with variable threshold.

    Adapts threshold based on peak characteristics to maintain consistent
    number of pixels (~15-20) for robust noise averaging.

    Args:
        spectrum: Transmission spectrum (%)
        wavelengths: Wavelength array (nm)
        search_range: SPR wavelength range (min, max) in nm

    Returns:
        peak_wavelength: Centroid position (nm)
        diagnostics: Dict with threshold, n_points, etc.
    """
    try:
        # Extract search region
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        wl_region = wavelengths[mask]
        spec_region = spectrum[mask]

        if len(wl_region) < 3:
            logger.warning(f"Adaptive centroid: Insufficient points: {len(wl_region)}")
            return (wl_region[np.argmin(spec_region)] if len(wl_region) > 0 else np.nan), {}

        # Invert spectrum: SPR dip → peak
        inverted = 100.0 - spec_region
        max_signal = np.max(inverted)

        # Adaptive threshold to maintain ~15-20 pixels
        target_n_points = 15
        threshold = 0.5  # Start at 50%

        for threshold_test in [0.5, 0.4, 0.3, 0.6, 0.7]:
            threshold_value = max_signal * threshold_test
            significant_mask = inverted >= threshold_value
            n_points = np.sum(significant_mask)

            if 10 <= n_points <= 25:  # Good range for noise averaging
                threshold = threshold_test
                break

        # Apply final threshold
        threshold_value = max_signal * threshold
        significant_mask = inverted >= threshold_value

        if np.sum(significant_mask) < 3:
            # Fallback to lower threshold
            threshold = 0.3
            threshold_value = max_signal * threshold
            significant_mask = inverted >= threshold_value

        if np.sum(significant_mask) < 3:
            # Still too few, use simple minimum
            return wl_region[np.argmin(spec_region)], {"fallback": True}

        # Calculate weighted centroid
        weights = inverted[significant_mask]
        positions = wl_region[significant_mask]
        centroid = np.sum(weights * positions) / np.sum(weights)

        diagnostics = {
            "threshold": threshold,
            "n_points": np.sum(significant_mask),
            "max_signal": max_signal,
            "fallback": False,
        }

        logger.debug(
            f"Adaptive centroid: λ={centroid:.3f}nm, "
            f"threshold={threshold:.2f}, n_points={diagnostics['n_points']}"
        )

        return float(centroid), diagnostics

    except Exception as e:
        logger.error(f"Adaptive centroid failed: {e}")
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        return wavelengths[mask][np.argmin(spectrum[mask])], {"error": str(e)}


def find_peak_consensus(
    spectrum: np.ndarray,
    wavelengths: np.ndarray,
    search_range: tuple[float, float] = (600, 720),
    method: str = 'weighted_average',
) -> Tuple[float, Dict]:
    """Find SPR peak using consensus of multiple methods.

    Combines centroid (adaptive) + parabolic methods to reduce systematic bias.
    Both methods are continuous (no discrete steps/binary signals).

    Consensus Methods:
    - 'weighted_average': 60% centroid + 40% parabolic (default)
    - 'median': Robust to outliers (use if one method unreliable)
    - 'centroid_only': Fallback to centroid only

    Args:
        spectrum: Transmission spectrum (%)
        wavelengths: Wavelength array (nm)
        search_range: SPR wavelength range (min, max) in nm
        method: Consensus combination method

    Returns:
        consensus_peak: Combined peak position (nm)
        diagnostics: Dict with individual results + agreement metrics
    """
    try:
        # Method 1: Adaptive centroid
        peak_centroid, centroid_diag = find_peak_centroid_adaptive(
            spectrum, wavelengths, search_range
        )

        # Method 2: Parabolic interpolation
        peak_parabolic = find_peak_parabolic(
            spectrum, wavelengths, search_range
        )

        # Check for NaN results
        if np.isnan(peak_centroid) or np.isnan(peak_parabolic):
            logger.warning("Consensus: One method returned NaN, using fallback")
            if not np.isnan(peak_centroid):
                return peak_centroid, {"method": "centroid_fallback"}
            elif not np.isnan(peak_parabolic):
                return peak_parabolic, {"method": "parabolic_fallback"}
            else:
                # Both failed, use simple minimum
                mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
                return wavelengths[mask][np.argmin(spectrum[mask])], {"method": "argmin_fallback"}

        # Calculate agreement
        agreement = abs(peak_centroid - peak_parabolic)

        # Consensus calculation
        if method == 'weighted_average':
            # Centroid gets more weight (more robust for broad peaks)
            consensus_peak = 0.6 * peak_centroid + 0.4 * peak_parabolic

        elif method == 'median':
            # Median of two values (robust but less precise)
            consensus_peak = np.median([peak_centroid, peak_parabolic])

        elif method == 'centroid_only':
            # Fallback to centroid only (ignore parabolic)
            consensus_peak = peak_centroid

        else:
            logger.warning(f"Unknown consensus method: {method}, using weighted_average")
            consensus_peak = 0.6 * peak_centroid + 0.4 * peak_parabolic

        # Diagnostics
        diagnostics = {
            "consensus_method": method,
            "peak_centroid": peak_centroid,
            "peak_parabolic": peak_parabolic,
            "agreement_nm": agreement,
            "centroid_n_points": centroid_diag.get("n_points", 0),
            "centroid_threshold": centroid_diag.get("threshold", 0),
            "good_agreement": agreement < 0.5,  # Methods agree within 0.5nm
        }

        logger.debug(
            f"Consensus: λ={consensus_peak:.3f}nm "
            f"(centroid={peak_centroid:.3f}, parabolic={peak_parabolic:.3f}, "
            f"Δ={agreement:.3f}nm)"
        )

        return float(consensus_peak), diagnostics

    except Exception as e:
        logger.error(f"Consensus method failed: {e}")
        # Final fallback: simple minimum
        mask = (wavelengths >= search_range[0]) & (wavelengths <= search_range[1])
        return wavelengths[mask][np.argmin(spectrum[mask])], {"error": str(e), "fallback": True}
