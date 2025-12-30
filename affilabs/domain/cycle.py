"""Cycle Domain Model - Type-safe cycle data structure.

ARCHITECTURE LAYER: Domain Model (Phase 1.1)

This module defines the Cycle domain model for experiment cycles.
Replaces dict-based cycle storage with type-safe dataclass.

BENEFITS:
- Type safety: IDE autocomplete, type checking
- Validation: Ensures required fields are present
- Default values: No missing key errors
- Serialization: Easy conversion to/from dict
- Documentation: Fields are self-documenting

USAGE:
    # Create a new cycle
    cycle = Cycle(
        type='Baseline',
        length_minutes=5.0,
        name='Baseline 1'
    )

    # Update cycle status
    cycle.status = 'running'
    cycle.cycle_num = 1

    # Export for recording
    export_dict = cycle.to_export_dict()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CycleStatus = Literal["pending", "running", "completed", "cancelled"]
CycleType = Literal["Baseline", "Association", "Dissociation", "Regeneration", "Custom"]


@dataclass
class Cycle:
    """Domain model for experiment cycle.

    Represents a timed segment of the experiment (e.g., Baseline, Association).
    Cycles are queued and executed in sequence.

    Attributes:
        type: Cycle type (Baseline, Association, Dissociation, etc.)
        length_minutes: Duration of cycle in minutes
        name: User-friendly name for the cycle
        note: Optional notes/comments
        cycle_num: Sequential cycle number (0 = not started)
        total_cycles: Total number of cycles in queue
        status: Current status (pending, running, completed, cancelled)
        sensorgram_time: Start time in sensorgram timeline (seconds)
        end_time_sensorgram: End time in sensorgram timeline (seconds)
    """

    # Required fields
    type: str
    length_minutes: float

    # Optional fields with defaults
    name: str = ""
    note: str = ""
    concentration_value: float | None = None
    concentration_units: str = "nM"  # Default to nM (use "ug/mL" for immobilization)

    # Runtime state (set when cycle starts)
    cycle_num: int = 0
    total_cycles: int = 0
    status: CycleStatus = "pending"

    # Timeline positions (set during execution)
    sensorgram_time: float | None = None
    end_time_sensorgram: float | None = None

    def __post_init__(self):
        """Validate cycle data after initialization."""
        # Ensure length_minutes is positive
        if self.length_minutes <= 0:
            raise ValueError(f"Cycle length must be positive, got {self.length_minutes}")

        # Set default name if not provided
        if not self.name:
            self.name = f"{self.type} Cycle"

    def to_dict(self) -> dict:
        """Convert to dictionary (for legacy compatibility).

        Returns:
            Dictionary with all cycle fields
        """
        return {
            "type": self.type,
            "length_minutes": self.length_minutes,
            "name": self.name,
            "note": self.note,
            "cycle_num": self.cycle_num,
            "total_cycles": self.total_cycles,
            "status": self.status,
            "sensorgram_time": self.sensorgram_time,
            "end_time_sensorgram": self.end_time_sensorgram,
        }

    def to_export_dict(self) -> dict:
        """Convert to export format for recording manager.

        Returns:
            Dictionary suitable for Excel export
        """
        return {
            "cycle_num": self.cycle_num,
            "type": self.type,
            "name": self.name,
            "start_time_sensorgram": self.sensorgram_time,
            "end_time_sensorgram": self.end_time_sensorgram,
            "duration_minutes": self.length_minutes,
            "concentration_value": self.concentration_value,
            "concentration_units": self.concentration_units,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Cycle:
        """Create Cycle from dictionary.

        Args:
            data: Dictionary with cycle fields

        Returns:
            Cycle instance
        """
        return cls(
            type=data.get("type", "Custom"),
            length_minutes=data.get("length_minutes", 1.0),
            name=data.get("name", ""),
            note=data.get("note", ""),
            concentration_value=data.get("concentration_value"),
            concentration_units=data.get("concentration_units", "nM"),
            cycle_num=data.get("cycle_num", 0),
            total_cycles=data.get("total_cycles", 0),
            status=data.get("status", "pending"),
            sensorgram_time=data.get("sensorgram_time"),
            end_time_sensorgram=data.get("end_time_sensorgram"),
        )

    def is_running(self) -> bool:
        """Check if cycle is currently running."""
        return self.status == "running"

    def is_completed(self) -> bool:
        """Check if cycle is completed."""
        return self.status == "completed"

    def is_pending(self) -> bool:
        """Check if cycle is pending."""
        return self.status == "pending"

    def start(self, cycle_num: int, total_cycles: int, sensorgram_time: float):
        """Mark cycle as started.

        Args:
            cycle_num: Sequential cycle number
            total_cycles: Total cycles in queue
            sensorgram_time: Start time in sensorgram timeline
        """
        self.cycle_num = cycle_num
        self.total_cycles = total_cycles
        self.status = "running"
        self.sensorgram_time = sensorgram_time

    def complete(self, end_time_sensorgram: float):
        """Mark cycle as completed.

        Args:
            end_time_sensorgram: End time in sensorgram timeline
        """
        self.status = "completed"
        self.end_time_sensorgram = end_time_sensorgram

    def cancel(self):
        """Mark cycle as cancelled."""
        self.status = "cancelled"

    def get_duration_seconds(self) -> float:
        """Get cycle duration in seconds."""
        return self.length_minutes * 60

    def __str__(self) -> str:
        """String representation for logging."""
        return f"Cycle(type={self.type}, length={self.length_minutes}min, status={self.status})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"Cycle(type={self.type!r}, length_minutes={self.length_minutes}, "
            f"name={self.name!r}, cycle_num={self.cycle_num}, status={self.status!r})"
        )
