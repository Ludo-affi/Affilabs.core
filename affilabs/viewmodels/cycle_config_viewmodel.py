"""Cycle Configuration ViewModel

Represents the state of a cycle configuration, separated from UI widgets.
This enables clean separation between data (model) and presentation (view).

Part of MVVM architecture refactoring for sidebar components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CycleConfigViewModel:
    """View model for cycle configuration settings.

    This class represents the user's cycle configuration choices,
    independent of how they're displayed in the UI.

    Attributes:
        cycle_type: Type of experiment (Auto-read, Baseline, Immobilization, Binding, Kinetic)
        cycle_length_min: Duration in minutes (2, 5, 15, 30, 60)
        note: User notes with optional channel tags (max 250 chars)
        units: Concentration units (M, mM, µM, nM, pM, mg/mL, µg/mL, ng/mL)
        timestamp: When configuration was created
        metadata: Additional key-value pairs for extensibility

    """

    # Core configuration
    cycle_type: str = "Auto-read"
    cycle_length_min: int = 5
    note: str = ""
    units: str = "nM"

    # Metadata
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def validate(self) -> list[str]:
        """Validate configuration and return list of error messages.

        Returns:
            List of validation error messages (empty if valid)

        """
        errors = []

        # Validate cycle type
        valid_types = ["Auto-read", "Baseline", "Immobilization", "Binding", "Kinetic"]
        if self.cycle_type not in valid_types:
            errors.append(
                f"Invalid cycle type: {self.cycle_type}. Must be one of {valid_types}",
            )

        # Validate cycle length
        valid_lengths = [2, 5, 15, 30, 60]
        if self.cycle_length_min not in valid_lengths:
            errors.append(
                f"Invalid cycle length: {self.cycle_length_min} min. Must be one of {valid_lengths}",
            )

        # Validate note length
        if len(self.note) > 250:
            errors.append(f"Note too long: {len(self.note)} chars (max 250)")

        # Validate units
        valid_units = ["M", "mM", "µM", "nM", "pM", "mg/mL", "µg/mL", "ng/mL"]
        # Extract unit prefix before parentheses (e.g., "nM" from "nM (Nanomolar)")
        unit_prefix = self.units.split()[0] if self.units else ""
        if unit_prefix not in valid_units:
            errors.append(f"Invalid concentration unit: {self.units}")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid.

        Returns:
            True if configuration passes all validation checks

        """
        return len(self.validate()) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of configuration

        """
        return {
            "cycle_type": self.cycle_type,
            "cycle_length_min": self.cycle_length_min,
            "note": self.note,
            "units": self.units,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CycleConfigViewModel":
        """Create instance from dictionary.

        Args:
            data: Dictionary with configuration data

        Returns:
            CycleConfigViewModel instance

        """
        timestamp = data.get("timestamp")
        if timestamp and isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            cycle_type=data.get("cycle_type", "Auto-read"),
            cycle_length_min=data.get("cycle_length_min", 5),
            note=data.get("note", ""),
            units=data.get("units", "nM"),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )

    def extract_channel_tags(self) -> dict[str, float | None]:
        """Extract channel concentration tags from note.

        Parses tags like [A:10], [B:50], [ALL:20] from note text.

        Returns:
            Dictionary mapping channel ('a', 'b', 'c', 'd') to concentration value
            None value indicates channel tagged without concentration

        """
        import re

        tags = {}

        # Match [A:10], [B:50.5], etc. (with concentration)
        conc_pattern = r"\[([ABCD]|ALL):(\d+\.?\d*)\]"
        for match in re.finditer(conc_pattern, self.note):
            channel = match.group(1).lower()
            concentration = float(match.group(2))

            if channel == "all":
                # Apply to all channels
                for ch in ["a", "b", "c", "d"]:
                    tags[ch] = concentration
            else:
                tags[channel] = concentration

        # Match [A], [B], etc. (without concentration)
        tag_pattern = (
            r"\[([ABCD]|ALL)\](?!:)"  # Negative lookahead to avoid matching [A:10]
        )
        for match in re.finditer(tag_pattern, self.note):
            channel = match.group(1).lower()

            if channel == "all":
                # Mark all channels (if not already set with concentration)
                for ch in ["a", "b", "c", "d"]:
                    if ch not in tags:
                        tags[ch] = None
            elif channel not in tags:
                tags[channel] = None

        return tags

    def get_units_display_name(self) -> str:
        """Get full display name for units.

        Returns:
            Full unit name with description (e.g., "nM (Nanomolar)")

        """
        unit_names = {
            "M": "M (Molar)",
            "mM": "mM (Millimolar)",
            "µM": "µM (Micromolar)",
            "nM": "nM (Nanomolar)",
            "pM": "pM (Picomolar)",
            "mg/mL": "mg/mL",
            "µg/mL": "µg/mL",
            "ng/mL": "ng/mL",
        }
        return unit_names.get(self.units, self.units)

    def copy(self) -> "CycleConfigViewModel":
        """Create a deep copy of this configuration.

        Returns:
            New CycleConfigViewModel instance with same values

        """
        return CycleConfigViewModel(
            cycle_type=self.cycle_type,
            cycle_length_min=self.cycle_length_min,
            note=self.note,
            units=self.units,
            timestamp=self.timestamp,
            metadata=self.metadata.copy(),
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"CycleConfigViewModel(type={self.cycle_type}, "
            f"length={self.cycle_length_min}min, "
            f"units={self.units}, note='{self.note[:30]}...')"
        )
