"""Timeline Domain Model — Unified Temporal Event Framework

Provides a cohesive model for all time-based events in a recording session:
- Injection flags
- Wash markers  
- Auto-calculated deadlines
- Cycle boundaries
- User annotations

Single source of truth for:
- When events occur (relative to recording start)
- What type of event it is
- Which context (live acquisition vs. post-processing edits)
- Associated metadata (channel, confidence, etc.)

This replaces scattered handling of flags, cycles, and events across managers.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from affilabs.utils.logger import logger


class EventContext(Enum):
    """Where was this event created?"""
    LIVE = "live"  # During actual acquisition
    EDITS = "edits"  # During post-processing/manual editing


class EventType(Enum):
    """Categorize timeline events by purpose."""
    INJECTION = "injection"
    WASH = "wash"
    SPIKE = "spike"
    CYCLE_BOUNDARY = "cycle_boundary"
    AUTO_MARKER = "auto_marker"
    USER_ANNOTATION = "user_annotation"


@dataclass
class TimelineContext:
    """Global timeline reference frame for a recording session.
    
    All events use recording-relative time (seconds from start).
    TimelineContext handles conversion between:
    - Absolute timestamps (Unix time)
    - Recording-relative time (0 = recording start)
    """
    
    recording_start_time: float  # Unix timestamp when recording began
    recording_start_offset: float  # Elapsed time when recording started (for pause/resume)
    
    def normalize_time(self, absolute_time: float) -> float:
        """Convert absolute Unix timestamp to recording-relative time.
        
        Args:
            absolute_time: Unix timestamp
        
        Returns:
            Seconds from start of recording
        """
        return absolute_time - self.recording_start_offset
    
    def denormalize_time(self, relative_time: float) -> float:
        """Convert recording-relative time back to absolute Unix timestamp.
        
        Args:
            relative_time: Seconds from start of recording
        
        Returns:
            Unix timestamp
        """
        return relative_time + self.recording_start_offset
    
    def __repr__(self) -> str:
        """Human-readable timeline context."""
        start_dt = datetime.fromtimestamp(self.recording_start_time)
        offset_str = f"+{self.recording_start_offset:.1f}s" if self.recording_start_offset else "0s"
        return f"TimelineContext(started={start_dt.isoformat()}, offset={offset_str})"


@dataclass
class TimelineEvent:
    """Base class for all timeline events.
    
    All times are relative to recording start (0 = recording started).
    Use TimelineContext.normalize_time() / denormalize_time() to convert
    between absolute timestamps and relative times.
    """
    
    event_type: EventType = field(default=EventType.INJECTION, init=False)
    time: float  # Recording-relative time (seconds from start)
    channel: str  # 'A', 'B', 'C', 'D'
    context: EventContext  # 'live' or 'edits'
    created_at: datetime  # When this event was created
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event."""
        if self.channel.upper() not in ['A', 'B', 'C', 'D']:
            raise ValueError(f"Invalid channel: {self.channel}")
        if self.time < 0:
            logger.warning(f"Event with negative time: {self.time}s (will be clamped to 0)")
            self.time = 0.0
    
    def with_context(self, context: TimelineContext) -> tuple[float, float]:
        """Get event position in absolute time.
        
        Args:
            context: TimelineContext to use for conversion
        
        Returns:
            (relative_time, absolute_time) tuple
        """
        absolute_time = context.denormalize_time(self.time)
        return (self.time, absolute_time)
    
    def __lt__(self, other: TimelineEvent) -> bool:
        """Sort events by time."""
        if not isinstance(other, TimelineEvent):
            return NotImplemented
        return self.time < other.time
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"time={self.time:.2f}s, "
            f"channel={self.channel}, "
            f"context={self.context.value})"
        )


@dataclass
class InjectionFlag(TimelineEvent):
    """Injection event detected or marked.
    
    During live acquisition: Placed when injection is auto-detected.
    During edits: Manually placed by user with optional time shift.
    """
    
    spr_value: float = 0.0  # SPR wavelength (nm) at injection time
    confidence: float = 1.0  # Detection confidence (0.0 to 1.0)
    is_reference: bool = False  # Is this the first injection (alignment reference)?
    time_shift: float = 0.0  # Time delta from reference injection (for alignment)
    
    def __post_init__(self):
        """Validate injection flag."""
        super().__post_init__()
        self.event_type = EventType.INJECTION
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class WashFlag(TimelineEvent):
    """Wash/buffer replacement event."""
    
    wash_type: str = "buffer_change"  # or 'regeneration', 'rinsing', etc.
    description: str = ""
    
    def __post_init__(self):
        """Validate wash flag."""
        super().__post_init__()
        self.event_type = EventType.WASH


@dataclass
class SpikeFlag(TimelineEvent):
    """Signal anomaly or spike marker."""
    
    description: str = ""
    severity: str = "info"  # 'info', 'warning', 'critical'
    
    def __post_init__(self):
        """Validate spike flag."""
        super().__post_init__()
        self.event_type = EventType.SPIKE
        if self.severity not in ['info', 'warning', 'critical']:
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass
class CycleMarker(TimelineEvent):
    """Cycle start or end boundary marker."""
    
    cycle_id: str = ""  # Unique cycle identifier
    cycle_type: str = ""  # e.g., 'Baseline', 'Kinetics', 'Regeneration'
    is_start: bool = True  # True = start, False = end
    duration: float = 0.0  # Total duration if this is start marker
    
    def __post_init__(self):
        """Validate cycle marker."""
        super().__post_init__()
        self.event_type = EventType.CYCLE_BOUNDARY


@dataclass
class AutoMarker(TimelineEvent):
    """System-generated marker (deadline, auto-calculated event, etc.).
    
    Not user-placed, but calculated from experiment parameters.
    Examples:
    - Wash deadline (e.g., "must wash by 15:30")
    - Injection deadline
    - Contact time expiry
    """
    
    marker_kind: str = ""  # 'wash_deadline', 'injection_deadline', 'contact_expiry', etc.
    label: str = ""  # Display label (e.g., '⏱ Wash Due')
    is_selectable: bool = True  # Can user select/move this marker?
    
    def __post_init__(self):
        """Validate auto marker."""
        super().__post_init__()
        self.event_type = EventType.AUTO_MARKER


@dataclass
class UserAnnotation(TimelineEvent):
    """User-added textual annotation (note, comment, question)."""
    
    text: str = ""  # The annotation text
    
    def __post_init__(self):
        """Validate annotation."""
        super().__post_init__()
        self.event_type = EventType.USER_ANNOTATION


class TimelineEventStream:
    """Ordered collection of timeline events.
    
    Provides:
    - Sorted insertion and retrieval
    - Type-based filtering
    - Time-range queries
    - Deduplication by event type/channel/time
    """
    
    def __init__(self):
        """Initialize empty event stream."""
        self._events: list[TimelineEvent] = []
        self._by_type: dict[EventType, list[TimelineEvent]] = {}
        self._lock = threading.RLock()  # Reentrant lock: acquisition thread writes, UI thread reads
    
    def add_event(self, event: TimelineEvent, deduplicate: bool = True) -> bool:
        """Add event to stream in sorted order.
        
        Args:
            event: TimelineEvent to add
            deduplicate: If True, don't add duplicate (same type/channel/time)
        
        Returns:
            True if added, False if skipped (duplicate)
        """
        with self._lock:
            if deduplicate and self._is_duplicate(event):
                logger.warning(f"Skipping duplicate event: {event}")
                return False
            
            self._events.append(event)
            self._events.sort()  # Keep sorted by time
            
            # Update type index
            event_type = event.event_type
            if event_type not in self._by_type:
                self._by_type[event_type] = []
            self._by_type[event_type].append(event)
            
            logger.debug(f"Added event: {event}")
            return True
    
    def _is_duplicate(self, event: TimelineEvent) -> bool:
        """Check if event is duplicate of existing event. Caller must hold _lock."""
        for existing in self._events:
            if (
                type(existing) == type(event)
                and existing.time == event.time
                and existing.channel == event.channel
            ):
                return True
        return False
    
    def get_events_by_type(self, event_type: EventType) -> list[TimelineEvent]:
        """Get all events of a specific type."""
        with self._lock:
            return list(self._by_type.get(event_type, []))
    
    def get_events_in_time_range(
        self, start_time: float, end_time: float
    ) -> list[TimelineEvent]:
        """Get all events within a time range (inclusive)."""
        with self._lock:
            return [e for e in self._events if start_time <= e.time <= end_time]
    
    def get_events_for_channel(self, channel: str) -> list[TimelineEvent]:
        """Get all events on a specific channel."""
        with self._lock:
            return [e for e in self._events if e.channel.upper() == channel.upper()]
    
    def get_flags(self) -> list[InjectionFlag | WashFlag | SpikeFlag]:
        """Get all flag-type events (injections, washes, spikes)."""
        with self._lock:
            flags = []
            for event_type in [EventType.INJECTION, EventType.WASH, EventType.SPIKE]:
                flags.extend(self._by_type.get(event_type, []))
            return sorted(flags)
    
    def get_cycle_boundaries(self) -> list[CycleMarker]:
        """Get all cycle boundary markers."""
        with self._lock:
            return list(self._by_type.get(EventType.CYCLE_BOUNDARY, []))
    
    def get_auto_markers(self) -> list[AutoMarker]:
        """Get all auto-generated markers."""
        with self._lock:
            return list(self._by_type.get(EventType.AUTO_MARKER, []))
    
    def remove_event(self, event: TimelineEvent) -> bool:
        """Remove a specific event from the stream.

        Args:
            event: The event to remove (matched by equality)

        Returns:
            True if found and removed, False if not present
        """
        with self._lock:
            try:
                self._events.remove(event)
                # Also remove from type index
                type_list = self._by_type.get(event.event_type)
                if type_list:
                    try:
                        type_list.remove(event)
                    except ValueError:
                        pass
                logger.debug(f"Removed event: {event}")
                return True
            except ValueError:
                return False

    def update_event_time(self, event: TimelineEvent, new_time: float) -> bool:
        """Update the time of an existing event while maintaining sort order.

        Useful for manual relocation of a mis-placed flag or marker.

        Args:
            event: The event to update (must be present in the stream)
            new_time: New recording-relative time in seconds (clamped to >= 0)

        Returns:
            True if updated, False if event not found
        """
        with self._lock:
            if event not in self._events:
                return False
            event.time = max(0.0, new_time)
            self._events.sort()  # Re-sort after time change
            logger.debug(f"Updated event time to {new_time:.2f}s: {event}")
            return True

    def clear(self):
        """Remove all events."""
        with self._lock:
            self._events.clear()
            self._by_type.clear()
    
    def __len__(self) -> int:
        """Total event count."""
        with self._lock:
            return len(self._events)
    
    def __iter__(self):
        """Iterate events in time order (snapshot copy — safe across threads)."""
        with self._lock:
            return iter(list(self._events))
    
    def __repr__(self) -> str:
        counts = {k.value: len(v) for k, v in self._by_type.items()}
        return f"TimelineEventStream({len(self._events)} events: {counts})"
