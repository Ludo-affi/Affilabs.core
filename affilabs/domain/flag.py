"""Flag Domain Model - Type-safe flag data structures.

ARCHITECTURE LAYER: Domain Model (Phase 1.1)

This module defines the Flag domain models for experiment event markers.
Replaces dict-based flag storage with type-safe dataclass hierarchy.

FLAGS are user-placed markers on the cycle graph indicating important events:
- InjectionFlag: Sample injection point (used for channel time alignment)
- WashFlag: Wash/buffer change event
- SpikeFlag: Anomaly/artifact marker

BENEFITS:
- Type safety: Compile-time type checking, IDE autocomplete
- Polymorphism: Different behavior for different flag types
- Validation: Ensures required fields are present
- Self-documenting: Clear type hierarchy
- Testable: Unit test flag logic in isolation

USAGE:
    # Create injection flag (first one sets reference)
    flag = InjectionFlag(
        channel='A',
        time=150.5,
        spr=1200.0,
        is_reference=True
    )

    # Create wash flag
    wash = WashFlag(
        channel='B',
        time=300.0,
        spr=800.0
    )

    # Export for recording
    export_data = flag.to_export_dict()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

FlagType = Literal["injection", "wash", "spike"]
FlagContext = Literal["live", "edits"]


@dataclass
class Flag(ABC):
    """Abstract base class for all flag types.

    Flags are user-placed markers on the cycle graph indicating important events.
    Each flag has a position (channel, time, SPR value) and visual representation.

    Attributes:
        channel: Channel identifier (A, B, C, D)
        time: Time position in sensorgram (seconds)
        spr: SPR value at flag position (RU)
        marker: PyQtGraph ScatterPlotItem for visual representation (optional, set by UI)
    """

    channel: str
    time: float
    spr: float
    context: str = "live"  # 'live' (acquisition) or 'edits' (post-hoc)
    marker: Any = None  # PyQtGraph ScatterPlotItem (set by FlagManager)

    def __post_init__(self):
        """Validate flag data after initialization."""
        # Validate channel
        if self.channel not in ["A", "B", "C", "D"]:
            raise ValueError(f"Channel must be A, B, C, or D, got {self.channel}")

        # Validate time is non-negative
        if self.time < 0:
            raise ValueError(f"Time must be non-negative, got {self.time}")

    @property
    @abstractmethod
    def flag_type(self) -> FlagType:
        """Return the flag type identifier."""
        pass

    @property
    @abstractmethod
    def marker_symbol(self) -> str:
        """Return the PyQtGraph marker symbol for this flag type."""
        pass

    @property
    @abstractmethod
    def marker_color(self) -> str:
        """Return the marker color for this flag type."""
        pass

    @property
    def marker_size(self) -> int:
        """Return the marker size (can be overridden by subclasses)."""
        return 12

    def to_dict(self) -> dict:
        """Convert to dictionary (for legacy compatibility).

        Returns:
            Dictionary with all flag fields
        """
        return {
            "channel": self.channel,
            "time": self.time,
            "spr": self.spr,
            "type": self.flag_type,
            "marker": self.marker,
        }

    def to_export_dict(self) -> dict:
        """Convert to export format for recording manager.

        Returns:
            Dictionary suitable for Excel export
        """
        return {
            "type": self.flag_type,
            "channel": self.channel,
            "time": self.time,
            "spr": self.spr,
            "context": self.context,
        }

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"{self.__class__.__name__}(ch={self.channel}, t={self.time:.1f}s, spr={self.spr:.1f})"
        )

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}(channel={self.channel!r}, "
            f"time={self.time}, spr={self.spr})"
        )


@dataclass
class InjectionFlag(Flag):
    """Injection event flag.

    Marks sample injection points. The first injection flag on any channel
    becomes the reference point for channel time alignment. Subsequent injection
    flags auto-calculate the time shift needed to align channels.

    Attributes:
        channel: Channel identifier (A, B, C, D)
        time: Time position in sensorgram (seconds)
        spr: SPR value at flag position (RU)
        is_reference: Whether this is the reference injection for alignment
        marker: PyQtGraph ScatterPlotItem for visual representation
    """

    is_reference: bool = False

    @property
    def flag_type(self) -> FlagType:
        return "injection"

    @property
    def marker_symbol(self) -> str:
        return "t"  # Triangle pointing up

    @property
    def marker_color(self) -> str:
        return "#FF3B30"  # Vibrant red for injection (Apple System Red)

    @property
    def marker_size(self) -> int:
        return 14  # Consistent moderate size

    def to_export_dict(self) -> dict:
        """Include is_reference in export."""
        export = super().to_export_dict()
        export["is_reference"] = self.is_reference
        return export


@dataclass
class WashFlag(Flag):
    """Wash/buffer change event flag.

    Marks buffer exchange or wash steps in the experiment.

    Attributes:
        channel: Channel identifier (A, B, C, D)
        time: Time position in sensorgram (seconds)
        spr: SPR value at flag position (RU)
        marker: PyQtGraph ScatterPlotItem for visual representation
    """

    @property
    def flag_type(self) -> FlagType:
        return "wash"

    @property
    def marker_symbol(self) -> str:
        return "d"  # Diamond (more distinctive than square)

    @property
    def marker_color(self) -> str:
        return "#007AFF"  # Vibrant blue for wash (Apple System Blue)

    @property
    def marker_size(self) -> int:
        return 14  # Consistent moderate size


@dataclass
class SpikeFlag(Flag):
    """Spike/anomaly event flag.

    Marks anomalous data points, artifacts, or other events requiring attention.

    Attributes:
        channel: Channel identifier (A, B, C, D)
        time: Time position in sensorgram (seconds)
        spr: SPR value at flag position (RU)
        marker: PyQtGraph ScatterPlotItem for visual representation
    """

    @property
    def flag_type(self) -> FlagType:
        return "spike"

    @property
    def marker_symbol(self) -> str:
        return "star"  # Star

    @property
    def marker_color(self) -> str:
        return "#FF9500"  # Vibrant orange for spike/warning (Apple System Orange)

    @property
    def marker_size(self) -> int:
        return 14  # Consistent moderate size


def create_flag(flag_type: str, channel: str, time: float, spr: float, **kwargs) -> Flag:
    """Factory function to create appropriate flag instance.

    Args:
        flag_type: Type of flag ('injection', 'wash', 'spike')
        channel: Channel identifier (A, B, C, D)
        time: Time position in sensorgram (seconds)
        spr: SPR value at flag position (RU)
        **kwargs: Additional type-specific arguments (e.g., is_reference for injection)

    Returns:
        Flag instance of appropriate type

    Raises:
        ValueError: If flag_type is unknown
    """
    flag_classes = {
        "injection": InjectionFlag,
        "wash": WashFlag,
        "spike": SpikeFlag,
    }

    flag_class = flag_classes.get(flag_type.lower())
    if flag_class is None:
        raise ValueError(
            f"Unknown flag type: {flag_type}. Must be one of {list(flag_classes.keys())}"
        )

    # Filter kwargs to only include parameters accepted by the specific flag class
    # InjectionFlag accepts is_reference, others don't
    # Extract context if provided, default to 'live'
    context = kwargs.pop("context", "live")

    if flag_type.lower() == "injection":
        # Pass all kwargs to InjectionFlag (it accepts is_reference)
        return flag_class(channel=channel, time=time, spr=spr, context=context, **kwargs)
    else:
        # WashFlag and SpikeFlag don't accept extra kwargs beyond base Flag params
        # Filter out any kwargs like is_reference
        return flag_class(channel=channel, time=time, spr=spr, context=context)


def flag_from_dict(data: dict) -> Flag:
    """Create Flag instance from dictionary.

    Args:
        data: Dictionary with flag fields (type, channel, time, spr)

    Returns:
        Flag instance of appropriate type
    """
    flag_type = data.get("type", "injection")
    channel = data.get("channel", "A")
    time = data.get("time", 0.0)
    spr = data.get("spr", 0.0)
    context = data.get("context", "live")

    # Extract type-specific fields
    kwargs = {"context": context}
    if flag_type == "injection":
        kwargs["is_reference"] = data.get("is_reference", False)

    return create_flag(flag_type, channel, time, spr, **kwargs)
