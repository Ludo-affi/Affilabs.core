"""Hardware Abstraction Layer interfaces.

Defines small Protocols for the capabilities AcquisitionService depends on.
These allow adapters to wrap current device objects without changing behavior.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np


class LEDCommand:
    """Represents a single LED operation for batch execution"""

    def __init__(
        self,
        action: str,
        channel: str | None = None,
        intensity: int | None = None,
        mode: str | None = None,
    ):
        self.action = action  # 'on', 'off', 'intensity', 'mode'
        self.channel = channel
        self.intensity = intensity
        self.mode = mode

    def __repr__(self):
        return f"LEDCommand({self.action}, ch={self.channel}, int={self.intensity}, mode={self.mode})"


class LEDController(Protocol):
    def turn_on_channel(self, ch: str) -> None: ...
    def turn_off_channels(self) -> None: ...
    def set_intensity(self, ch: str, raw_val: int) -> None: ...
    def set_mode(self, mode: str) -> None: ...
    def execute_batch(self, commands: list[LEDCommand]) -> bool: ...
    def get_capabilities(self) -> dict[str, Any]: ...


class SpectrometerInfo(Protocol):
    @property
    def serial_number(self) -> str | None: ...


class Spectrometer(Protocol):
    def read_roi(
        self,
        wave_min_index: int,
        wave_max_index: int,
        num_scans: int = 1,
    ) -> np.ndarray | None: ...
    def read_wavelength(self) -> np.ndarray: ...
    def set_integration(self, integration_ms: int) -> None: ...

    @property
    def min_integration(self) -> float: ...

    @property
    def serial_number(self) -> str | None: ...
