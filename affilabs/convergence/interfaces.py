from __future__ import annotations

from typing import Protocol, Optional, Sequence, Mapping


class Logger(Protocol):
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class Spectrometer(Protocol):
    def acquire(
        self,
        *,
        integration_time_ms: float,
        num_scans: int,
        channel: str,
        led_intensity: int,
        use_batch_command: bool,
    ) -> Optional[Sequence[float]]: ...


class LEDActuator(Protocol):
    def set_many(self, mapping: Mapping[str, int]) -> bool: ...


class ROIExtractor(Protocol):
    def __call__(self, spectrum: Sequence[float], i_min: int, i_max: int) -> float: ...


class Scheduler(Protocol):
    def map_with_timeout(
        self,
        items: Sequence[str],
        fn: "Callable[[str], T]",  # type: ignore[name-defined]
        timeout_s: float,
    ) -> Mapping[str, "T"]:  # type: ignore[name-defined]
        ...
