"""Spectrum Data Models

Pure Python data structures for spectroscopy data.
NO Qt dependencies - fully testable.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class SpectrumData:
    """Base spectrum data structure.

    Represents a single spectrum measurement from one channel.
    """

    wavelengths: np.ndarray
    intensities: np.ndarray
    channel: str  # 'a', 'b', 'c', 'd'
    timestamp: float  # Unix timestamp
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate data integrity."""
        if len(self.wavelengths) != len(self.intensities):
            raise ValueError(
                f"Wavelength and intensity arrays must have same length: "
                f"{len(self.wavelengths)} vs {len(self.intensities)}",
            )
        if self.channel not in ["a", "b", "c", "d"]:
            raise ValueError(f"Invalid channel: {self.channel}")
        if len(self.wavelengths) == 0:
            raise ValueError("Empty spectrum data")

    @property
    def num_points(self) -> int:
        """Number of data points in spectrum."""
        return len(self.wavelengths)

    @property
    def wavelength_range(self) -> tuple[float, float]:
        """Min and max wavelengths (nm)."""
        return (float(self.wavelengths[0]), float(self.wavelengths[-1]))

    @property
    def intensity_range(self) -> tuple[float, float]:
        """Min and max intensities."""
        return (float(np.min(self.intensities)), float(np.max(self.intensities)))

    @property
    def mean_intensity(self) -> float:
        """Mean intensity across spectrum."""
        return float(np.mean(self.intensities))

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.timestamp)

    def has_data(self) -> bool:
        """Check if spectrum contains non-zero data."""
        return np.count_nonzero(self.intensities) > 0

    def copy(self) -> "SpectrumData":
        """Create a deep copy of this spectrum."""
        return SpectrumData(
            wavelengths=self.wavelengths.copy(),
            intensities=self.intensities.copy(),
            channel=self.channel,
            timestamp=self.timestamp,
            metadata=self.metadata.copy(),
        )


@dataclass
class RawSpectrumData(SpectrumData):
    """Raw spectrum from detector (P-mode).

    Represents unprocessed spectrum directly from hardware.
    Used during acquisition before calibration is applied.
    """

    integration_time: float = 0.0  # ms
    num_scans: int = 1  # Number of averaged scans
    led_intensity: int = 0  # LED brightness (0-255)

    def __post_init__(self):
        """Validate raw spectrum data."""
        super().__post_init__()
        if self.integration_time < 0:
            raise ValueError(f"Invalid integration time: {self.integration_time}")
        if self.num_scans < 1:
            raise ValueError(f"Invalid num_scans: {self.num_scans}")
        if not (0 <= self.led_intensity <= 255):
            raise ValueError(f"Invalid LED intensity: {self.led_intensity}")


@dataclass
class ProcessedSpectrumData(SpectrumData):
    """Processed transmission spectrum.

    Result of calibration: raw P-mode divided by S-mode reference.
    This is what gets displayed in live view and saved to files.
    """

    transmission_percent: np.ndarray = field(default_factory=lambda: np.array([]))
    reference_spectrum: np.ndarray | None = None
    baseline_corrected: bool = False

    def __post_init__(self):
        """Validate processed spectrum data."""
        super().__post_init__()
        # Transmission is the main "intensities" for processed spectra
        if len(self.transmission_percent) == 0:
            self.transmission_percent = self.intensities.copy()
        elif len(self.transmission_percent) != len(self.intensities):
            raise ValueError(
                f"Transmission and wavelength arrays must match: "
                f"{len(self.transmission_percent)} vs {len(self.wavelengths)}",
            )

    @property
    def transmission_range(self) -> tuple[float, float]:
        """Min and max transmission (%)."""
        return (
            float(np.min(self.transmission_percent)),
            float(np.max(self.transmission_percent)),
        )

    @property
    def mean_transmission(self) -> float:
        """Mean transmission across spectrum (%)."""
        return float(np.mean(self.transmission_percent))

    def has_reference(self) -> bool:
        """Check if reference spectrum is available."""
        return self.reference_spectrum is not None and len(self.reference_spectrum) > 0


@dataclass
class SpectrumBatch:
    """Collection of spectra for batch processing.

    Used to accumulate multiple spectra before applying
    operations like Savitzky-Golay filtering or averaging.
    """

    spectra: list[SpectrumData] = field(default_factory=list)
    channel: str = ""
    max_size: int = 10

    def add(self, spectrum: SpectrumData):
        """Add spectrum to batch."""
        if self.channel == "":
            self.channel = spectrum.channel
        elif self.channel != spectrum.channel:
            raise ValueError(
                f"Channel mismatch: expected {self.channel}, got {spectrum.channel}",
            )

        self.spectra.append(spectrum)

        # Keep only most recent spectra
        if len(self.spectra) > self.max_size:
            self.spectra = self.spectra[-self.max_size :]

    def is_ready(self, min_spectra: int = 3) -> bool:
        """Check if batch has enough spectra for processing."""
        return len(self.spectra) >= min_spectra

    def clear(self):
        """Clear all spectra from batch."""
        self.spectra.clear()

    @property
    def size(self) -> int:
        """Number of spectra in batch."""
        return len(self.spectra)

    def get_latest(self) -> SpectrumData | None:
        """Get most recent spectrum."""
        return self.spectra[-1] if self.spectra else None

    def get_wavelengths(self) -> np.ndarray | None:
        """Get wavelengths (assumes all spectra have same wavelengths)."""
        if not self.spectra:
            return None
        return self.spectra[0].wavelengths

    def get_intensities_array(self) -> np.ndarray | None:
        """Get 2D array of intensities (spectra × wavelengths)."""
        if not self.spectra:
            return None
        return np.array([s.intensities for s in self.spectra])
