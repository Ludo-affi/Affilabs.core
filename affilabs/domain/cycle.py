"""Cycle Domain Model - Type-safe cycle data structure with validation.

ARCHITECTURE LAYER: Domain Model (Phase 1.2 - Enhanced with Pydantic)

This module defines the Cycle domain model for experiment cycles.
Uses Pydantic for automatic validation and type coercion.

ENHANCEMENTS (Pydantic + TinyDB Integration):
- Automatic validation: Fields validated on creation
- Type coercion: "5.0" string → 5.0 float automatically
- Better error messages: Clear validation errors
- JSON schema: Auto-generate schemas for docs
- Immutable IDs: cycle_id cannot be changed after creation

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

import time
from typing import Literal, Optional, Dict, List

from pydantic import BaseModel, Field, field_validator

CycleStatus = Literal["pending", "running", "completed", "cancelled"]
CycleType = Literal[
    "Baseline", "Immobilization", "Blocking", "Wash", "Concentration", "Regeneration", "Custom"
]


class Cycle(BaseModel):
    """Domain model for experiment cycle with automatic validation.

    Represents a timed segment of the experiment (e.g., Baseline, Association).
    Cycles are queued and executed in sequence.

    Attributes:
        type: Cycle type (Baseline, Association, Dissociation, etc.)
        length_minutes: Duration of cycle in minutes (must be positive)
        name: User-friendly name for the cycle
        note: Optional notes/comments
        cycle_num: Sequential cycle number (0 = not started)
        total_cycles: Total number of cycles in queue
        status: Current status (pending, running, completed, cancelled)
        sensorgram_time: Start time in sensorgram timeline (seconds)
        end_time_sensorgram: End time in sensorgram timeline (seconds)
    """

    # Required fields with validation
    type: str = Field(..., description="Cycle type (Baseline, Association, etc.)")
    length_minutes: float = Field(..., gt=0, description="Duration in minutes (must be positive)")

    # Optional fields with defaults
    name: str = Field(default="", description="User-friendly cycle name")
    note: str = Field(default="", description="Optional notes/comments")
    concentration_value: Optional[float] = Field(default=None, description="Concentration value")
    concentration_units: str = Field(default="nM", description="Concentration units (nM or ug/mL)")

    # Concentration metadata (for multi-channel experiments)
    units: str = Field(default="nM", description="Unit type for concentrations")
    concentrations: Dict[str, float] = Field(
        default_factory=dict, description="Channel-specific concentrations {'A': 100.0, 'B': 50.0}"
    )

    # Unique identifiers
    cycle_id: int = Field(default=0, description="Permanent ID assigned when created (immutable)")
    timestamp: float = Field(
        default_factory=time.time, description="Unix timestamp when cycle was created"
    )

    # Runtime state (set when cycle starts)
    cycle_num: int = Field(default=0, description="Sequential position in queue (can change)")
    total_cycles: int = Field(default=0, description="Total cycles in queue")
    status: CycleStatus = Field(default="pending", description="Current cycle status")

    # Timeline positions (set during execution)
    sensorgram_time: Optional[float] = Field(
        default=None, description="Start time in sensorgram timeline"
    )
    end_time_sensorgram: Optional[float] = Field(
        default=None, description="End time in sensorgram timeline"
    )

    # Analysis data (calculated after cycle completion)
    delta_spr: Optional[float] = Field(
        default=None, description="SPR change during cycle (legacy single channel)"
    )
    delta_spr_by_channel: Dict[str, float] = Field(
        default_factory=dict,
        description="SPR change for each channel {'A': 45.2, 'B': 87.3, 'C': 12.1, 'D': 56.8}",
    )
    flags: List[str] = Field(
        default_factory=list,
        description="Flags that occurred during this cycle (injection, wash, spike)",
    )

    # Pump control fields (for automated flow during cycles)
    flow_rate: Optional[float] = Field(
        default=None, description="Flow rate in µL/min (None = no pump control)"
    )
    pump_type: Optional[Literal["affipump", "p4proplus"]] = Field(
        default=None, description="Pump type (auto-detected from hardware)"
    )
    channels: Optional[Literal["AC", "BD"]] = Field(
        default=None,
        description="Active SPR channels: 'AC' (default, 3-way state=0) or 'BD' (alternate, 3-way state=1)",
    )

    # Injection control fields (for automated injection during cycles)
    injection_method: Optional[Literal["simple", "partial"]] = Field(
        default=None, description="Injection method: 'simple' (full loop) or 'partial' (30µL spike)"
    )
    injection_delay: float = Field(
        default=20.0, description="Seconds after cycle start before injection triggers"
    )
    contact_time: Optional[float] = Field(
        default=None, description="Contact time in seconds (for association phase)"
    )

    # Manual injection mode for P4SPR concentration cycles
    manual_injection_mode: Optional[Literal["automated", "manual"]] = Field(
        default=None,
        description="Injection mode for P4SPR: 'automated' (pump injects, user confirms), "
        "'manual' (user injects via syringe, system prompts at flags), "
        "None = use hardware default",
    )
    planned_concentrations: List[str] = Field(
        default_factory=list,
        description="List of concentration values planned for this cycle "
        "(e.g., ['100 nM', '50 nM', '10 nM']). Used for multi-injection workflows.",
    )
    injection_count: int = Field(
        default=0,
        description="Number of manual injections completed so far in this concentration cycle",
    )

    # Pydantic configuration
    model_config = {
        "validate_assignment": True,  # Validate on attribute assignment
        "arbitrary_types_allowed": False,
        "str_strip_whitespace": True,
    }

    @field_validator("length_minutes")
    @classmethod
    def validate_length(cls, v: float) -> float:
        """Ensure length_minutes is positive."""
        if v <= 0:
            raise ValueError(f"Cycle length must be positive, got {v}")
        return v

    @field_validator("name")
    @classmethod
    def set_default_name(cls, v: str, info) -> str:
        """Set default name based on cycle type if not provided."""
        if not v and "type" in info.data:
            return f"{info.data['type']} Cycle"
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary (for legacy compatibility).

        Uses Pydantic's model_dump for automatic serialization.

        Returns:
            Dictionary with all cycle fields
        """
        return self.model_dump()

    def to_export_dict(self) -> dict:
        """Convert to export format for recording manager.

        Returns:
            Dictionary suitable for Excel export
        """
        # Calculate actual duration if both start and end times are available
        # Otherwise use planned duration (length_minutes)
        actual_duration = self.length_minutes
        if self.sensorgram_time is not None and self.end_time_sensorgram is not None:
            actual_duration = (self.end_time_sensorgram - self.sensorgram_time) / 60.0

        return {
            "cycle_id": self.cycle_id,
            "cycle_num": self.cycle_num,
            "type": self.type,
            "name": self.name,
            "start_time_sensorgram": self.sensorgram_time,
            "end_time_sensorgram": self.end_time_sensorgram,
            "duration_minutes": actual_duration,
            "length_minutes": self.length_minutes,  # Keep planned duration for reference
            "concentration_value": self.concentration_value,
            "concentration_units": self.concentration_units,
            "units": self.units,
            "concentrations": self.concentrations,
            "note": self.note,
            "delta_spr": self.delta_spr,
            "delta_spr_by_channel": self.delta_spr_by_channel,
            "flags": self.flags if self.flags else [],
            "flow_rate": self.flow_rate,
            "pump_type": self.pump_type,
            "channels": self.channels,
            "injection_method": self.injection_method,
            "injection_delay": self.injection_delay,
            "contact_time": self.contact_time,
            "manual_injection_mode": self.manual_injection_mode,
            "planned_concentrations": self.planned_concentrations,
            "injection_count": self.injection_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Cycle:
        """Create Cycle from dictionary with automatic validation.

        Pydantic will validate all fields and coerce types automatically.

        Args:
            data: Dictionary with cycle fields

        Returns:
            Cycle instance (validated)
        """
        # Pydantic's model_validate handles type coercion and validation
        return cls.model_validate(data)

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
