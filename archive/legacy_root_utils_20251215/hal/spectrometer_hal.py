"""Spectrometer Hardware Abstraction Layer

Provides a unified interface for spectrometer devices used in SPR measurements.
This is a placeholder implementation - full implementation would follow similar
patterns to SPRControllerHAL.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SpectrometerCapabilities:
    """Describes capabilities of a spectrometer."""

    # Wavelength range
    wavelength_range: tuple[float, float]  # (min, max) in nm
    wavelength_resolution: float  # nm

    # Integration time
    min_integration_time: float  # seconds
    max_integration_time: float  # seconds

    # Detection capabilities
    supports_dark_current_correction: bool
    supports_reference_correction: bool
    supports_averaging: bool
    max_averages: int

    # Data format
    pixel_count: int
    bit_depth: int

    # Connection
    connection_type: str
    device_model: str


class SpectrometerHAL(ABC):
    """Hardware Abstraction Layer for Spectrometers.

    This is a placeholder implementation demonstrating the interface
    pattern. Full implementation would provide device-agnostic access
    to spectrometer functionality.
    """

    def __init__(self, device_name: str) -> None:
        """Initialize spectrometer HAL."""
        self.device_name = device_name

    @abstractmethod
    def connect(self, **connection_params: Any) -> bool:
        """Connect to spectrometer."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from spectrometer."""

    @abstractmethod
    def capture_spectrum(
        self,
        integration_time: float,
        averages: int = 1,
    ) -> tuple[list[float], list[float]]:
        """Capture spectrum data.

        Returns:
            Tuple of (wavelengths, intensities)

        """

    @abstractmethod
    def get_wavelengths(self) -> list[float]:
        """Get wavelength calibration."""

    @abstractmethod
    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time."""

    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get spectrometer capabilities."""
        return self._define_capabilities()

    @abstractmethod
    def _define_capabilities(self) -> SpectrometerCapabilities:
        """Define capabilities for this spectrometer type."""
