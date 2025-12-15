"""Baseline Correction Service

Pure business logic for baseline correction of transmission spectra.
NO Qt dependencies - fully testable.
"""

import logging

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d

logger = logging.getLogger(__name__)


class BaselineCorrector:
    """Removes baseline drift from transmission spectra.

    This service implements baseline correction methods:
    - Polynomial fitting (default: linear)
    - Moving minimum baseline
    - Asymmetric least squares (ALS)
    """

    def __init__(self, method: str = "polynomial", poly_order: int = 1):
        """Initialize baseline corrector.

        Args:
            method: Correction method ('polynomial', 'moving_min', 'als')
            poly_order: Polynomial order for polynomial method (1=linear, 2=quadratic)

        """
        self.method = method
        self.poly_order = poly_order

    def correct(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> np.ndarray:
        """Apply baseline correction to transmission spectrum.

        Args:
            transmission: Transmission spectrum (%)
            wavelengths: Wavelength array (nm), optional

        Returns:
            Baseline-corrected transmission (%)

        """
        if len(transmission) == 0:
            raise ValueError("Empty transmission spectrum")

        if not np.isfinite(transmission).all():
            raise ValueError("Transmission contains non-finite values")

        # Choose correction method
        if self.method == "polynomial":
            return self._polynomial_correction(transmission, wavelengths)
        if self.method == "moving_min":
            return self._moving_min_correction(transmission)
        if self.method == "als":
            return self._als_correction(transmission)
        logger.warning(f"Unknown method '{self.method}', using polynomial")
        return self._polynomial_correction(transmission, wavelengths)

    def correct_baseline(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compatibility shim: some UI layers expect `correct_baseline`.

        Delegates to `correct` with the same signature.
        """
        return self.correct(transmission, wavelengths)

    def correct_batch(
        self,
        transmissions: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> np.ndarray:
        """Apply baseline correction to multiple spectra.

        Args:
            transmissions: Array of transmission spectra (N x wavelengths)
            wavelengths: Wavelength array (nm), optional

        Returns:
            Array of corrected transmissions (N x wavelengths)

        """
        corrected = np.zeros_like(transmissions)
        for i, transmission in enumerate(transmissions):
            corrected[i] = self.correct(transmission, wavelengths)
        return corrected

    def _polynomial_correction(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> np.ndarray:
        """Polynomial baseline correction (linear or higher order).

        Fits a polynomial to the transmission and subtracts it.
        """
        # Use wavelengths as x-axis if provided, otherwise use indices
        if wavelengths is not None and len(wavelengths) == len(transmission):
            x = wavelengths
        else:
            x = np.arange(len(transmission))

        # Fit polynomial
        coeffs = np.polyfit(x, transmission, self.poly_order)
        baseline = np.polyval(coeffs, x)

        # Subtract baseline (shift to mean instead of zero)
        corrected = transmission - baseline + np.mean(transmission)

        logger.debug(
            f"Polynomial baseline correction (order={self.poly_order}): " f"coefficients={coeffs}",
        )

        return corrected

    def _moving_min_correction(
        self,
        transmission: np.ndarray,
        window_size: int | None = None,
    ) -> np.ndarray:
        """Moving minimum baseline correction.

        Uses a moving minimum filter to estimate baseline.
        """
        if window_size is None:
            # Default to ~5% of spectrum length, minimum 5, maximum 101
            window_size = max(5, min(101, len(transmission) // 20))
            # Ensure odd window size
            if window_size % 2 == 0:
                window_size += 1

        # Apply minimum filter (baseline estimation)
        baseline = minimum_filter1d(transmission, size=window_size, mode="nearest")

        # Smooth the baseline
        baseline = signal.savgol_filter(
            baseline,
            window_size,
            polyorder=2,
            mode="nearest",
        )

        # Subtract baseline
        corrected = transmission - baseline + np.mean(transmission)

        logger.debug(f"Moving minimum baseline correction: window_size={window_size}")

        return corrected

    def _als_correction(
        self,
        transmission: np.ndarray,
        lam: float = 1e5,
        p: float = 0.01,
        max_iter: int = 10,
    ) -> np.ndarray:
        """Asymmetric Least Squares (ALS) baseline correction.

        Args:
            lam: Smoothness parameter (larger = smoother)
            p: Asymmetry parameter (0.001-0.1, smaller = more asymmetric)
            max_iter: Maximum iterations

        """
        L = len(transmission)
        D = np.diff(np.eye(L), 2, axis=0)
        w = np.ones(L)

        for _ in range(max_iter):
            W = np.diag(w)
            Z = W + lam * (D.T @ D)
            z = np.linalg.solve(Z, w * transmission)
            w = p * (transmission > z) + (1 - p) * (transmission < z)

        baseline = z
        corrected = transmission - baseline + np.mean(transmission)

        logger.debug(f"ALS baseline correction: lam={lam}, p={p}")

        return corrected

    def estimate_baseline(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Estimate baseline without applying correction.

        Args:
            transmission: Transmission spectrum (%)
            wavelengths: Wavelength array (nm), optional

        Returns:
            Tuple of (baseline, corrected_transmission)

        """
        if wavelengths is not None and len(wavelengths) == len(transmission):
            x = wavelengths
        else:
            x = np.arange(len(transmission))

        # Fit polynomial to estimate baseline
        coeffs = np.polyfit(x, transmission, self.poly_order)
        baseline = np.polyval(coeffs, x)

        corrected = transmission - baseline + np.mean(transmission)

        return baseline, corrected

    def get_correction_info(self, transmission: np.ndarray) -> dict:
        """Get information about baseline correction.

        Args:
            transmission: Transmission spectrum (%)

        Returns:
            Dictionary with correction info (method, params, baseline shift)

        """
        baseline, corrected = self.estimate_baseline(transmission)

        return {
            "method": self.method,
            "poly_order": self.poly_order if self.method == "polynomial" else None,
            "baseline_mean": float(np.mean(baseline)),
            "baseline_range": float(np.max(baseline) - np.min(baseline)),
            "shift": float(np.mean(transmission) - np.mean(corrected)),
        }
