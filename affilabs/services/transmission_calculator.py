"""Transmission Calculator Service

Pure business logic for calculating transmission spectra.
NO Qt dependencies - fully testable.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class TransmissionCalculator:
    """Calculates transmission from raw P-mode and S-mode reference spectra.

    This service implements the core transmission calculation:
        Transmission (%) = 100 * (P_raw / S_ref) * (S_LED / P_LED)

    Where LED correction accounts for different LED intensities between modes.
    """

    def __init__(self, apply_led_correction: bool = True):
        """Initialize transmission calculator.

        Args:
            apply_led_correction: Whether to apply LED intensity correction

        """
        self.apply_led_correction = apply_led_correction

    def calculate_transmission(
        self,
        p_spectrum: np.ndarray,
        s_reference: np.ndarray,
        p_led_intensity: int | None = None,
        s_led_intensity: int | None = None,
    ) -> np.ndarray:
        """Alias for calculate() to maintain compatibility with SpectrumViewModel.

        This method exists for duck-typing compatibility where code expects
        calculate_transmission() instead of calculate().
        """
        return self.calculate(p_spectrum, s_reference, p_led_intensity, s_led_intensity)

    def calculate(
        self,
        p_spectrum: np.ndarray,
        s_reference: np.ndarray,
        p_led_intensity: int | None = None,
        s_led_intensity: int | None = None,
    ) -> np.ndarray:
        """Calculate transmission spectrum.

        Args:
            p_spectrum: Raw P-mode spectrum (counts)
            s_reference: S-mode reference spectrum (counts)
            p_led_intensity: P-mode LED brightness (0-255), optional
            s_led_intensity: S-mode LED brightness (0-255), optional

        Returns:
            Transmission spectrum (%)

        Raises:
            ValueError: If arrays have different lengths or contain invalid data

        """
        # Validate inputs
        self._validate_inputs(p_spectrum, s_reference, p_led_intensity, s_led_intensity)

        # Calculate raw transmission (element-wise division)
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = np.divide(
                p_spectrum,
                s_reference,
                out=np.zeros_like(p_spectrum, dtype=float),
                where=s_reference != 0,
            )

        # Apply LED intensity correction if requested and available
        if (
            self.apply_led_correction
            and p_led_intensity is not None
            and s_led_intensity is not None
        ):
            led_correction = s_led_intensity / p_led_intensity
            transmission *= led_correction
            logger.debug(
                f"Applied LED correction factor: {led_correction:.3f} (S={s_led_intensity}, P={p_led_intensity})",
            )

        # Convert to percentage
        transmission *= 100.0

        # Clamp to reasonable range (0-200%)
        transmission = np.clip(transmission, 0.0, 200.0)

        return transmission

    def calculate_batch(
        self,
        p_spectra: np.ndarray,
        s_references: np.ndarray,
        p_led_intensities: np.ndarray | None = None,
        s_led_intensities: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calculate transmission for multiple spectra (batch processing).

        Args:
            p_spectra: Array of P-mode spectra (N x wavelengths)
            s_references: Array of S-mode references (N x wavelengths)
            p_led_intensities: P-mode LED intensities (N,), optional
            s_led_intensities: S-mode LED intensities (N,), optional

        Returns:
            Array of transmission spectra (N x wavelengths)

        """
        if p_spectra.shape != s_references.shape:
            raise ValueError(
                f"Shape mismatch: {p_spectra.shape} vs {s_references.shape}",
            )

        # Vectorized calculation
        with np.errstate(divide="ignore", invalid="ignore"):
            transmission = np.divide(
                p_spectra,
                s_references,
                out=np.zeros_like(p_spectra, dtype=float),
                where=s_references != 0,
            )

        # Apply LED correction if available
        if (
            self.apply_led_correction
            and p_led_intensities is not None
            and s_led_intensities is not None
        ):
            led_correction = s_led_intensities / p_led_intensities
            # Broadcast correction factor across wavelengths
            transmission *= led_correction[:, np.newaxis]

        # Convert to percentage and clamp
        transmission *= 100.0
        transmission = np.clip(transmission, 0.0, 200.0)

        return transmission

    def calculate_with_noise_floor(
        self,
        p_spectrum: np.ndarray,
        s_reference: np.ndarray,
        noise_floor: float = 100.0,
        **kwargs,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Calculate transmission and identify low-signal regions.

        Args:
            p_spectrum: Raw P-mode spectrum (counts)
            s_reference: S-mode reference spectrum (counts)
            noise_floor: Minimum signal threshold (counts)
            **kwargs: Additional arguments for calculate()

        Returns:
            Tuple of (transmission, valid_mask) where valid_mask indicates
            regions above noise floor

        """
        transmission = self.calculate(p_spectrum, s_reference, **kwargs)

        # Create mask for regions above noise floor
        valid_mask = (p_spectrum > noise_floor) & (s_reference > noise_floor)

        return transmission, valid_mask

    def _validate_inputs(
        self,
        p_spectrum: np.ndarray,
        s_reference: np.ndarray,
        p_led_intensity: int | None,
        s_led_intensity: int | None,
    ) -> None:
        """Validate calculation inputs.

        Raises:
            ValueError: If inputs are invalid

        """
        if len(p_spectrum) != len(s_reference):
            raise ValueError(
                f"Spectrum length mismatch: P={len(p_spectrum)}, S={len(s_reference)}",
            )

        if len(p_spectrum) == 0:
            raise ValueError("Empty spectra")

        if not np.isfinite(p_spectrum).all():
            raise ValueError("P-spectrum contains non-finite values")

        if not np.isfinite(s_reference).all():
            raise ValueError("S-reference contains non-finite values")

        if np.all(s_reference == 0):
            raise ValueError("S-reference is all zeros")

        # Validate LED intensities if provided
        if p_led_intensity is not None:
            if not (0 <= p_led_intensity <= 255):
                raise ValueError(f"Invalid P-LED intensity: {p_led_intensity}")
            if p_led_intensity == 0:
                raise ValueError("P-LED intensity cannot be zero")

        if s_led_intensity is not None:
            if not (0 <= s_led_intensity <= 255):
                raise ValueError(f"Invalid S-LED intensity: {s_led_intensity}")
            if s_led_intensity == 0:
                raise ValueError("S-LED intensity cannot be zero")

    def get_statistics(self, transmission: np.ndarray) -> dict:
        """Calculate transmission statistics.

        Args:
            transmission: Transmission spectrum (%)

        Returns:
            Dictionary with statistics (min, max, mean, std, median)

        """
        return {
            "min": float(np.min(transmission)),
            "max": float(np.max(transmission)),
            "mean": float(np.mean(transmission)),
            "std": float(np.std(transmission)),
            "median": float(np.median(transmission)),
            "range": float(np.max(transmission) - np.min(transmission)),
        }
