"""Acquisition Configuration Models

Pure Python data structures for acquisition parameters.
NO Qt dependencies - fully testable.
"""

from dataclasses import dataclass, field
from enum import Enum


class AcquisitionMode(Enum):
    """Acquisition mode enumeration."""

    CALIBRATION = "calibration"  # Full calibration (S-mode + P-mode)
    LIVE = "live"  # P-only live acquisition (reuse S-ref)
    SINGLE = "single"  # Single spectrum acquisition


class PolarizerMode(Enum):
    """Polarizer position."""

    S_MODE = "s"  # S-polarizer (reference)
    P_MODE = "p"  # P-polarizer (sample)


@dataclass
class LEDConfig:
    """LED intensity configuration per channel.

    Brightness values: 0-255 (8-bit)
    """

    a: int = 0
    b: int = 0
    c: int = 0
    d: int = 0

    def __post_init__(self):
        """Validate LED intensities."""
        for channel in ["a", "b", "c", "d"]:
            value = getattr(self, channel)
            if not (0 <= value <= 255):
                raise ValueError(f"LED {channel} intensity out of range: {value}")

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {"a": self.a, "b": self.b, "c": self.c, "d": self.d}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "LEDConfig":
        """Create from dictionary."""
        return cls(
            a=data.get("a", 0),
            b=data.get("b", 0),
            c=data.get("c", 0),
            d=data.get("d", 0),
        )

    def get(self, channel: str) -> int:
        """Get LED intensity for channel."""
        if channel not in ["a", "b", "c", "d"]:
            raise KeyError(f"Invalid channel: {channel}")
        return getattr(self, channel)

    def set(self, channel: str, value: int):
        """Set LED intensity for channel."""
        if channel not in ["a", "b", "c", "d"]:
            raise KeyError(f"Invalid channel: {channel}")
        if not (0 <= value <= 255):
            raise ValueError(f"LED intensity out of range: {value}")
        setattr(self, channel, value)


@dataclass
class TimingConfig:
    """Timing parameters for acquisition.

    All values in milliseconds.
    """

    pre_led_delay: float = 12.0  # LED warmup time
    post_led_delay: float = 40.0  # Afterglow settling time
    servo_movement_delay: float = 150.0  # Polarizer rotation time
    integration_time: float = 63.0  # Detector integration time

    def __post_init__(self):
        """Validate timing parameters."""
        if self.pre_led_delay < 0:
            raise ValueError(f"Invalid pre_led_delay: {self.pre_led_delay}")
        if self.post_led_delay < 0:
            raise ValueError(f"Invalid post_led_delay: {self.post_led_delay}")
        if self.servo_movement_delay < 0:
            raise ValueError(
                f"Invalid servo_movement_delay: {self.servo_movement_delay}",
            )
        if not (3.0 <= self.integration_time <= 10000.0):
            raise ValueError(f"Integration time out of range: {self.integration_time}")

    @property
    def total_cycle_time(self) -> float:
        """Estimated time for one complete acquisition cycle (ms)."""
        return self.pre_led_delay + self.integration_time + self.post_led_delay


@dataclass
class AcquisitionConfig:
    """Complete acquisition configuration.

    Defines all parameters needed for data acquisition.
    """

    mode: AcquisitionMode = AcquisitionMode.LIVE

    # Integration parameters
    integration_time_s: float = 66.0  # S-mode integration time (ms)
    integration_time_p: float = 63.0  # P-mode integration time (ms)
    per_channel_integration: bool = False  # Different time per channel?

    # Averaging
    num_scans: int = 5  # Number of scans to average

    # LED configurations
    s_mode_leds: LEDConfig = field(
        default_factory=lambda: LEDConfig(255, 255, 255, 255),
    )
    p_mode_leds: LEDConfig = field(default_factory=lambda: LEDConfig(204, 81, 58, 170))

    # Timing
    timing: TimingConfig = field(default_factory=TimingConfig)

    # ROI (Region of Interest)
    roi_start: float = 560.0  # Start wavelength (nm)
    roi_end: float = 720.0  # End wavelength (nm)

    # Polarizer
    polarizer_mode: PolarizerMode = PolarizerMode.P_MODE

    # Processing options
    apply_baseline_correction: bool = True
    apply_smoothing: bool = False
    smoothing_window: int = 11  # Savitzky-Golay window size

    def __post_init__(self):
        """Validate configuration."""
        if self.num_scans < 1:
            raise ValueError(f"Invalid num_scans: {self.num_scans}")
        if not (3.0 <= self.integration_time_s <= 10000.0):
            raise ValueError(
                f"S-mode integration time out of range: {self.integration_time_s}",
            )
        if not (3.0 <= self.integration_time_p <= 10000.0):
            raise ValueError(
                f"P-mode integration time out of range: {self.integration_time_p}",
            )
        if self.roi_start >= self.roi_end:
            raise ValueError(f"Invalid ROI: {self.roi_start} >= {self.roi_end}")
        if self.smoothing_window < 3 or self.smoothing_window % 2 == 0:
            raise ValueError(
                f"Smoothing window must be odd and >= 3: {self.smoothing_window}",
            )

    @property
    def channels(self) -> list[str]:
        """Active channels."""
        return ["a", "b", "c", "d"]

    @property
    def estimated_cycle_time(self) -> float:
        """Estimated time for full 4-channel cycle (seconds)."""
        single_channel = self.timing.total_cycle_time * self.num_scans
        total_ms = single_channel * len(self.channels)

        # Add servo movement time if calibration mode
        if self.mode == AcquisitionMode.CALIBRATION:
            total_ms += self.timing.servo_movement_delay

        return total_ms / 1000.0  # Convert to seconds

    def get_led_intensity(self, channel: str, polarizer: PolarizerMode) -> int:
        """Get LED intensity for channel and polarizer mode."""
        if polarizer == PolarizerMode.S_MODE:
            return self.s_mode_leds.get(channel)
        return self.p_mode_leds.get(channel)

    def copy(self) -> "AcquisitionConfig":
        """Create a deep copy of configuration."""
        return AcquisitionConfig(
            mode=self.mode,
            integration_time_s=self.integration_time_s,
            integration_time_p=self.integration_time_p,
            per_channel_integration=self.per_channel_integration,
            num_scans=self.num_scans,
            s_mode_leds=LEDConfig.from_dict(self.s_mode_leds.to_dict()),
            p_mode_leds=LEDConfig.from_dict(self.p_mode_leds.to_dict()),
            timing=TimingConfig(
                pre_led_delay=self.timing.pre_led_delay,
                post_led_delay=self.timing.post_led_delay,
                servo_movement_delay=self.timing.servo_movement_delay,
                integration_time=self.timing.integration_time,
            ),
            roi_start=self.roi_start,
            roi_end=self.roi_end,
            polarizer_mode=self.polarizer_mode,
            apply_baseline_correction=self.apply_baseline_correction,
            apply_smoothing=self.apply_smoothing,
            smoothing_window=self.smoothing_window,
        )
