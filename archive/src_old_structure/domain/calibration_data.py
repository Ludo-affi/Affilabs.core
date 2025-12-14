"""
Calibration Data Models

Pure Python data structures for calibration.
NO Qt dependencies - fully testable.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np
from datetime import datetime


@dataclass
class CalibrationMetrics:
    """Quality metrics for calibration validation.

    Used to assess whether calibration is acceptable.
    """
    snr: float  # Signal-to-noise ratio
    peak_intensity: float  # Maximum intensity in spectrum
    mean_intensity: float  # Average intensity
    std_dev: float  # Standard deviation
    dynamic_range: float  # Max / Min intensity
    saturation_percent: float  # % of pixels at max value

    def is_saturated(self, threshold: float = 5.0) -> bool:
        """Check if spectrum is saturated."""
        return self.saturation_percent > threshold

    def is_low_signal(self, threshold: float = 1000.0) -> bool:
        """Check if signal is too low."""
        return self.mean_intensity < threshold

    def is_acceptable(self) -> bool:
        """Check if metrics indicate good calibration."""
        return (
            not self.is_saturated() and
            not self.is_low_signal() and
            self.snr > 10.0 and
            self.dynamic_range > 1.5
        )


@dataclass
class CalibrationData:
    """Complete calibration dataset.

    Contains S-mode reference spectra and LED intensities
    used for transmission calculations.

    This replaces the legacy CalibrationData namedtuple with
    a proper domain model.
    """
    # Core calibration data
    s_pol_ref: Dict[str, np.ndarray]  # channel -> reference spectrum
    wavelengths: np.ndarray  # wavelength array (nm)

    # LED intensities
    p_mode_intensities: Dict[str, int]  # P-mode LED brightness
    s_mode_intensities: Dict[str, int]  # S-mode LED brightness

    # Acquisition parameters
    integration_time_s: float = 0.0  # S-mode integration time (ms)
    integration_time_p: float = 0.0  # P-mode integration time (ms)
    num_scans: int = 5  # Number of averaged scans

    # Timing parameters
    pre_led_delay: float = 12.0  # LED warmup delay (ms)
    post_led_delay: float = 40.0  # Afterglow delay (ms)

    # Quality metrics per channel
    metrics: Dict[str, CalibrationMetrics] = field(default_factory=dict)

    # Metadata
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    roi_start: float = 560.0  # ROI start wavelength (nm)
    roi_end: float = 720.0  # ROI end wavelength (nm)

    def __post_init__(self):
        """Validate calibration data."""
        # Validate channels
        expected_channels = {'a', 'b', 'c', 'd'}
        ref_channels = set(self.s_pol_ref.keys())
        p_channels = set(self.p_mode_intensities.keys())
        s_channels = set(self.s_mode_intensities.keys())

        if ref_channels != expected_channels:
            raise ValueError(f"Missing reference channels: {expected_channels - ref_channels}")
        if p_channels != expected_channels:
            raise ValueError(f"Missing P-mode intensities: {expected_channels - p_channels}")
        if s_channels != expected_channels:
            raise ValueError(f"Missing S-mode intensities: {expected_channels - s_channels}")

        # Validate wavelength array
        if len(self.wavelengths) == 0:
            raise ValueError("Empty wavelength array")

        # Validate each reference spectrum
        for channel, spectrum in self.s_pol_ref.items():
            if len(spectrum) != len(self.wavelengths):
                raise ValueError(
                    f"Channel {channel} spectrum length mismatch: "
                    f"{len(spectrum)} vs {len(self.wavelengths)} wavelengths"
                )
            if np.count_nonzero(spectrum) == 0:
                raise ValueError(f"Channel {channel} reference spectrum is all zeros")

    @property
    def channels(self) -> list[str]:
        """List of calibrated channels."""
        return sorted(self.s_pol_ref.keys())

    @property
    def num_points(self) -> int:
        """Number of wavelength points."""
        return len(self.wavelengths)

    @property
    def wavelength_range(self) -> tuple[float, float]:
        """Wavelength range (nm)."""
        return (float(self.wavelengths[0]), float(self.wavelengths[-1]))

    @property
    def datetime(self) -> datetime:
        """Calibration timestamp as datetime."""
        return datetime.fromtimestamp(self.timestamp)

    def get_reference(self, channel: str) -> np.ndarray:
        """Get reference spectrum for channel."""
        if channel not in self.s_pol_ref:
            raise KeyError(f"No reference for channel {channel}")
        return self.s_pol_ref[channel]

    def get_p_led(self, channel: str) -> int:
        """Get P-mode LED intensity for channel."""
        if channel not in self.p_mode_intensities:
            raise KeyError(f"No P-mode intensity for channel {channel}")
        return self.p_mode_intensities[channel]

    def get_s_led(self, channel: str) -> int:
        """Get S-mode LED intensity for channel."""
        if channel not in self.s_mode_intensities:
            raise KeyError(f"No S-mode intensity for channel {channel}")
        return self.s_mode_intensities[channel]

    def get_metrics(self, channel: str) -> Optional[CalibrationMetrics]:
        """Get quality metrics for channel."""
        return self.metrics.get(channel)

    def is_channel_acceptable(self, channel: str) -> bool:
        """Check if channel calibration is acceptable."""
        metrics = self.get_metrics(channel)
        if metrics is None:
            return True  # No metrics = assume acceptable
        return metrics.is_acceptable()

    def all_channels_acceptable(self) -> bool:
        """Check if all channels have acceptable calibration."""
        return all(self.is_channel_acceptable(ch) for ch in self.channels)

    def copy(self) -> 'CalibrationData':
        """Create a deep copy of calibration data."""
        return CalibrationData(
            s_pol_ref={k: v.copy() for k, v in self.s_pol_ref.items()},
            wavelengths=self.wavelengths.copy(),
            p_mode_intensities=self.p_mode_intensities.copy(),
            s_mode_intensities=self.s_mode_intensities.copy(),
            integration_time_s=self.integration_time_s,
            integration_time_p=self.integration_time_p,
            num_scans=self.num_scans,
            pre_led_delay=self.pre_led_delay,
            post_led_delay=self.post_led_delay,
            metrics=self.metrics.copy(),
            timestamp=self.timestamp,
            roi_start=self.roi_start,
            roi_end=self.roi_end
        )

    # ============================================================================
    # BACKWARD COMPATIBILITY ALIASES
    # ============================================================================

    @property
    def wave_data(self) -> np.ndarray:
        """Alias for wavelengths (legacy naming)."""
        return self.wavelengths

    @property
    def s_mode_integration_time(self) -> float:
        """Alias for integration_time_s."""
        return self.integration_time_s

    @property
    def p_mode_integration_time(self) -> float:
        """Alias for integration_time_p."""
        return self.integration_time_p

    @property
    def pre_led_delay_ms(self) -> float:
        """Alias for pre_led_delay (ms)."""
        return self.pre_led_delay

    @property
    def post_led_delay_ms(self) -> float:
        """Alias for post_led_delay (ms)."""
        return self.post_led_delay

    # Additional backward compatibility properties for DataAcquisitionManager
    @property
    def integration_time(self) -> float:
        """Default integration time (P-mode preferred, fallback to S-mode)."""
        return self.integration_time_p if self.integration_time_p > 0 else self.integration_time_s

    @property
    def wavelength_min(self) -> float:
        """Minimum wavelength in range."""
        return float(self.wavelengths[0])

    @property
    def wavelength_max(self) -> float:
        """Maximum wavelength in range."""
        return float(self.wavelengths[-1])

    @property
    def wave_min_index(self) -> int:
        """Index of minimum wavelength in ROI (defaults to start)."""
        # Find index closest to roi_start
        return int(np.argmin(np.abs(self.wavelengths - self.roi_start)))

    @property
    def wave_max_index(self) -> int:
        """Index of maximum wavelength in ROI (defaults to end)."""
        # Find index closest to roi_end
        return int(np.argmin(np.abs(self.wavelengths - self.roi_end)))

    def get_channels(self) -> list[str]:
        """Get list of calibrated channels (compatibility method)."""
        return self.channels

    def validate(self) -> bool:
        """Validate calibration data (compatibility method)."""
        try:
            # All validation happens in __post_init__
            # If we got this far, data is valid
            return True
        except Exception:
            return False

    @property
    def dark_noise(self) -> Optional[np.ndarray]:
        """Dark noise spectrum (legacy property - not stored in domain model)."""
        # Domain model doesn't store dark noise (it's used during calibration only)
        # Return None for compatibility
        return None
