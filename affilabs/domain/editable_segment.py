"""EditableSegment - Domain model for user-created analysis segments.

ARCHITECTURE LAYER: Domain Model (Phase 1.1)

This module defines the EditableSegment domain model for post-processing analysis.
Unlike Cycle (recorded during live experiment), EditableSegment is created in Edits tab.

FEATURES:
- Combine multiple cycles
- Blend channels from different cycles
- Apply transformations (baseline, smoothing, alignment)
- Export for downstream analysis (TraceDrawer, Excel, etc.)

USAGE:
    # Create segment from single cycle
    segment = EditableSegment(
        name="Concentration 1",
        source_cycles=[1],
        time_range=(100.0, 400.0)
    )

    # Apply baseline correction
    segment.baseline_offsets['a'] = -5.2

    # Export to TraceDrawer
    segment.export_to_tracedrawer_csv("output.csv", time_data, spr_data)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass
class EditableSegment:
    """User-created segment for post-processing analysis.

    Unlike Cycle (which is recorded during live experiment), EditableSegment
    is created in the Edits tab for post-processing. Users can:
    - Combine multiple cycles
    - Blend channels from different cycles
    - Apply transformations (baseline, smoothing, etc.)
    - Export for downstream analysis

    Attributes:
        name: User-friendly name for segment
        source_cycles: List of cycle numbers this segment pulls from
        time_range: (start_time, end_time) in sensorgram seconds
        channel_sources: Which cycle each channel comes from {'a': 1, 'b': 3}
        baseline_offsets: Per-channel baseline correction (nm)
        smoothing_window: Savitzky-Golay window size (0 = no smoothing)
        time_shifts: Per-channel time alignment (seconds)
        association_shift: Calculated delta SPR during association (nm)
        dissociation_shift: Calculated delta SPR during dissociation (nm)
        ka: Association rate constant (if calculated)
        kd: Dissociation rate constant (if calculated)
        notes: User notes
    """

    # Required fields
    name: str
    source_cycles: list[int]  # Cycle numbers this segment pulls from
    time_range: tuple[float, float]  # (start_time, end_time) in sensorgram seconds

    # Channel data configuration
    channel_sources: dict[str, int] = field(default_factory=dict)  # {'a': cycle_1, 'b': cycle_3}

    # Transformations applied
    baseline_offsets: dict[str, float] = field(
        default_factory=dict
    )  # Per-channel baseline correction
    smoothing_window: int = 0  # Savitzky-Golay window size (0 = no smoothing)
    time_shifts: dict[str, float] = field(default_factory=dict)  # Per-channel time alignment

    # Analysis results
    association_shift: float | None = None  # Delta SPR during association
    dissociation_shift: float | None = None  # Delta SPR during dissociation
    ka: float | None = None  # Association rate constant
    kd: float | None = None  # Dissociation rate constant

    notes: str = ""

    def apply_transformations(self, raw_data: dict[str, "np.ndarray"]) -> dict[str, "np.ndarray"]:
        """Apply all transformations to raw data and return processed data.

        Args:
            raw_data: Dictionary of raw channel data {'a': array, 'b': array, ...}

        Returns:
            Dictionary of processed channel data
        """
        import numpy as np

        processed = {}

        for ch in ["a", "b", "c", "d"]:
            if ch not in raw_data:
                continue

            data = raw_data[ch].copy()

            # Apply baseline offset
            if ch in self.baseline_offsets:
                data = data + self.baseline_offsets[ch]

            # Apply smoothing
            if self.smoothing_window > 0 and len(data) > self.smoothing_window:
                try:
                    from scipy.signal import savgol_filter

                    # Window must be odd and >= polyorder + 2
                    window = self.smoothing_window
                    if window % 2 == 0:
                        window += 1
                    polyorder = min(3, window - 2)
                    data = savgol_filter(data, window, polyorder)
                except Exception:
                    # Fall back to simple moving average
                    kernel = np.ones(self.smoothing_window) / self.smoothing_window
                    data = np.convolve(data, kernel, mode="same")

            processed[ch] = data

        return processed

    def to_export_dict(self) -> dict:
        """Export for saving to Excel/JSON.

        Returns:
            Dictionary with all segment data
        """
        return {
            "name": self.name,
            "source_cycles": self.source_cycles,
            "time_range": list(self.time_range),
            "channel_sources": self.channel_sources,
            "baseline_offsets": self.baseline_offsets,
            "smoothing_window": self.smoothing_window,
            "time_shifts": self.time_shifts,
            "association_shift": self.association_shift,
            "dissociation_shift": self.dissociation_shift,
            "ka": self.ka,
            "kd": self.kd,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EditableSegment:
        """Create EditableSegment from dictionary.

        Args:
            data: Dictionary with segment fields

        Returns:
            EditableSegment instance
        """
        return cls(
            name=data.get("name", "Untitled Segment"),
            source_cycles=data.get("source_cycles", []),
            time_range=tuple(data.get("time_range", (0.0, 0.0))),
            channel_sources=data.get("channel_sources", {}),
            baseline_offsets=data.get("baseline_offsets", {}),
            smoothing_window=data.get("smoothing_window", 0),
            time_shifts=data.get("time_shifts", {}),
            association_shift=data.get("association_shift"),
            dissociation_shift=data.get("dissociation_shift"),
            ka=data.get("ka"),
            kd=data.get("kd"),
            notes=data.get("notes", ""),
        )

    def export_to_tracedrawer_csv(
        self, filepath: str, time_data: "np.ndarray", spr_data: dict[str, "np.ndarray"]
    ) -> None:
        """Export segment in TraceDrawer-compatible CSV format.

        Args:
            filepath: Path to save CSV file
            time_data: Time array (seconds)
            spr_data: Dictionary of SPR data {'a': array, 'b': array, ...}
        """
        import pandas as pd

        # Apply transformations
        processed = self.apply_transformations(spr_data)

        # Create DataFrame
        df_data = {"Time (s)": time_data}
        for ch in ["a", "b", "c", "d"]:
            if ch in processed:
                df_data[f"Ch{ch.upper()} (nm)"] = processed[ch]

        df = pd.DataFrame(df_data)
        df.to_csv(filepath, index=False)

    def __str__(self) -> str:
        """String representation for logging."""
        cycles_str = ",".join(map(str, self.source_cycles))
        return f"EditableSegment(name={self.name}, cycles=[{cycles_str}], time={self.time_range[0]:.1f}-{self.time_range[1]:.1f}s)"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"EditableSegment(name={self.name!r}, source_cycles={self.source_cycles}, "
            f"time_range={self.time_range}, smoothing={self.smoothing_window})"
        )
