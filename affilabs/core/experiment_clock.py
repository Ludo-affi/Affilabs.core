"""ExperimentClock — Single source of truth for all experiment time conversions.

ARCHITECTURE LAYER: Core (shared by all layers)

The application uses three coordinate systems for time:
  - RAW_ELAPSED : seconds since experiment start, minus pauses.
                  Used by DataBufferManager (timeline_data, cycle_data).
  - DISPLAY     : what appears on the Live Sensorgram X-axis.
                  display = raw - display_offset  (offset ≈ 0.25 s, set once)
  - RECORDING   : what's written to Excel "Raw Data" sheet.
                  recording = raw - recording_offset  (offset = raw elapsed at record-start)

Rules:
  1. Internal storage (buffers, Cycle model) always uses RAW_ELAPSED.
  2. All conversions go through this class — no manual offset math elsewhere.
  3. display_offset is set ONCE (on second data point) then frozen.
  4. Converting between any two bases is a single ``convert()`` call.
"""

from __future__ import annotations

import time
from enum import Enum, auto


class TimeBase(Enum):
    """Coordinate systems used across the application."""

    RAW_ELAPSED = auto()  # Seconds since experiment start (minus pauses)
    DISPLAY = auto()  # Live Sensorgram X-axis (raw - display_offset)
    RECORDING = auto()  # Excel Raw Data (raw - recording_offset, t=0 at record-start)


class ExperimentClock:
    """Single source of truth for experiment time and coordinate conversion.

    Lifecycle:
        1. ``__init__()`` — created once at app startup
        2. ``start_experiment(ts)`` — called when first spectrum arrives
        3. ``lock_display_offset(raw)`` — called once after 2nd data point
        4. ``start_recording()`` — called when user clicks Record
        5. ``reset()`` — called on Clear Graphs

    Thread-safety note: offsets are written on well-defined lifecycle events
    (not per-frame), so no locking is needed.
    """

    def __init__(self) -> None:
        self._experiment_start_unix: float | None = None
        self._display_offset: float = 0.0
        self._display_offset_locked: bool = False
        self._recording_offset: float = 0.0
        self._total_paused: float = 0.0
        self._pause_start: float | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_experiment(self, first_timestamp: float) -> None:
        """Called once when the first spectrum arrives.

        Args:
            first_timestamp: Unix epoch timestamp of first acquired spectrum.
        """
        self._experiment_start_unix = first_timestamp
        self._display_offset = 0.0
        self._display_offset_locked = False
        self._recording_offset = 0.0
        self._total_paused = 0.0
        self._pause_start = None

    @property
    def experiment_started(self) -> bool:
        """Whether ``start_experiment`` has been called."""
        return self._experiment_start_unix is not None

    def lock_display_offset(self, raw_elapsed: float) -> None:
        """Freeze the display offset (call once with the 2nd data point's raw time).

        After this call the offset is immutable until ``reset()``.
        """
        if not self._display_offset_locked:
            self._display_offset = raw_elapsed
            self._display_offset_locked = True

    def start_recording(self) -> None:
        """Capture current raw-elapsed as recording t=0."""
        self._recording_offset = self.raw_elapsed_now()

    def start_recording_at(self, raw_elapsed: float) -> None:
        """Set recording offset to a specific raw-elapsed value.

        Useful when the caller has already computed the elapsed time.
        """
        self._recording_offset = raw_elapsed

    def pause(self) -> None:
        """Begin a pause interval."""
        if self._pause_start is None:
            self._pause_start = time.time()

    def resume(self) -> None:
        """End the current pause interval."""
        if self._pause_start is not None:
            self._total_paused += time.time() - self._pause_start
            self._pause_start = None

    @property
    def total_paused(self) -> float:
        """Total seconds spent paused (including current pause if active)."""
        extra = 0.0
        if self._pause_start is not None:
            extra = time.time() - self._pause_start
        return self._total_paused + extra

    def reset(self) -> None:
        """Full reset — equivalent to a new experiment.

        Called on "Clear Graphs" or power-cycle.
        """
        self._experiment_start_unix = None
        self._display_offset = 0.0
        self._display_offset_locked = False
        self._recording_offset = 0.0
        self._total_paused = 0.0
        self._pause_start = None

    # ------------------------------------------------------------------
    # Core conversions
    # ------------------------------------------------------------------

    def raw_elapsed_now(self) -> float:
        """Current raw-elapsed time (seconds since experiment start, minus pauses)."""
        if self._experiment_start_unix is None:
            return 0.0
        paused = self._total_paused
        if self._pause_start is not None:
            paused += time.time() - self._pause_start
        return time.time() - self._experiment_start_unix - paused

    def timestamp_to_raw(self, unix_timestamp: float) -> float:
        """Convert a Unix epoch timestamp to raw-elapsed seconds."""
        if self._experiment_start_unix is None:
            return 0.0
        return unix_timestamp - self._experiment_start_unix - self._total_paused

    def convert(self, value: float, from_base: TimeBase, to_base: TimeBase) -> float:
        """Convert a time value between any two coordinate systems.

        All conversions route through RAW_ELAPSED as the canonical hub.
        """
        if from_base is to_base:
            return value
        raw = self._to_raw(value, from_base)
        return self._from_raw(raw, to_base)

    # ------------------------------------------------------------------
    # Read-only properties (for logging / diagnostics)
    # ------------------------------------------------------------------

    @property
    def display_offset(self) -> float:
        """Current display offset (raw → display)."""
        return self._display_offset

    @property
    def display_offset_locked(self) -> bool:
        """Whether the display offset has been frozen."""
        return self._display_offset_locked

    @property
    def recording_offset(self) -> float:
        """Current recording offset (raw → recording)."""
        return self._recording_offset

    @property
    def experiment_start_unix(self) -> float | None:
        """Unix timestamp of experiment start (first spectrum)."""
        return self._experiment_start_unix

    # ------------------------------------------------------------------
    # Backward-compatibility shims (temporary, for incremental migration)
    # ------------------------------------------------------------------

    @property
    def experiment_start_time(self) -> float | None:
        """Alias for ``experiment_start_unix`` — matches legacy ``app.experiment_start_time``."""
        return self._experiment_start_unix

    @experiment_start_time.setter
    def experiment_start_time(self, value: float | None) -> None:
        if value is None:
            self.reset()
        else:
            self.start_experiment(value)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_raw(self, value: float, base: TimeBase) -> float:
        if base is TimeBase.RAW_ELAPSED:
            return value
        if base is TimeBase.DISPLAY:
            return value + self._display_offset
        if base is TimeBase.RECORDING:
            return value + self._recording_offset
        raise ValueError(f"Unknown TimeBase: {base}")

    def _from_raw(self, raw: float, base: TimeBase) -> float:
        if base is TimeBase.RAW_ELAPSED:
            return raw
        if base is TimeBase.DISPLAY:
            return raw - self._display_offset
        if base is TimeBase.RECORDING:
            return raw - self._recording_offset
        raise ValueError(f"Unknown TimeBase: {base}")

    def __repr__(self) -> str:
        started = self._experiment_start_unix is not None
        return (
            f"ExperimentClock(started={started}, "
            f"display_offset={self._display_offset:.4f}, "
            f"display_locked={self._display_offset_locked}, "
            f"recording_offset={self._recording_offset:.4f}, "
            f"total_paused={self._total_paused:.4f})"
        )
