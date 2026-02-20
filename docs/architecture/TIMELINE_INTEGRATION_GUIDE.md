# Timeline Context & Event Integration Guide

**Version:** Affilabs.core v2.0.5+  
**Status:** ✅ Implemented — Phases 1–4 complete (Feb 19 2026, parallel-systems approach)  
**Benefit:** Unified temporal model, reduced scattered time logic

---

## Overview

The new `TimelineContext` and `TimelineEvent` system provides a **single coherent temporal model** for all recording-session events:

```
Before (Scattered):
├── FlagManager._flag_markers: list[Flag]
├── RecordingManager.events: list[(timestamp, description)]
├── CycleManager._cycles: list[Cycle]
├── AutoMarker objects (separate)
└── recording_start_offset scattered across managers

After (Unified):
└── TimelineEventStream
    ├── TimelineEvent (base)
    ├── InjectionFlag
    ├── WashFlag
    ├── CycleMarker
    ├── AutoMarker
    └── UserAnnotation
    
    + TimelineContext (global reference frame)
```

---

## Key Concepts

### TimelineContext
**Purpose:** Single source of truth for time conversions.

**Current scattered logic:**
```python
# RecordingManager
self.recording_start_offset = time.time()

# FlagManager
flag.time  # Absolute timestamp

# SensogramPresenter
x_axis_time = flag.time - recording_mgr.recording_start_offset  # Scattered logic!
```

**After TimelineContext:**
```python
# Create once at recording start
timeline_context = TimelineContext(
    recording_start_time=time.time(),
    recording_start_offset=0.0
)

# Everyone uses it for conversion
relative_time = timeline_context.normalize_time(absolute_timestamp)
absolute_timestamp = timeline_context.denormalize_time(relative_time)

# All events use relative_time (0 = recording start)
event = InjectionFlag(time=42.5, channel='A', context=EventContext.LIVE)
```

### TimelineEventStream
**Purpose:** All flags, cycles, auto markers in one sorted list.

**Current scattered storage:**
```python
# FlagManager
self._flag_markers: list[Flag]

# CycleManager
self._cycles: list[Cycle]

# AutoMarker stored separately

# RecordingManager.events
events: list[tuple[float, str]]
```

**After TimelineEventStream:**
```python
stream = TimelineEventStream()

# Everything goes in the same stream
stream.add_event(InjectionFlag(time=10.0, channel='A'))
stream.add_event(CycleMarker(time=15.0, channel='A', cycle_type='Baseline'))
stream.add_event(AutoMarker(time=120.0, marker_kind='wash_deadline'))

# Query by type
flags = stream.get_flags()  # All injection/wash/spike flags
cycles = stream.get_cycle_boundaries()
auto = stream.get_auto_markers()

# Or iterate all in time order
for event in stream:
    print(f"{event.time:.1f}s: {event}")
```

---

## Migration Paths

### Path 1: Parallel Systems (Safest)

Run old and new systems side-by-side during refactoring:

```python
class FlagManager:
    def __init__(self, timeline_stream: TimelineEventStream = None):
        self._flag_markers = []  # Keep for compatibility
        self._timeline_stream = timeline_stream  # New system
    
    def add_flag_marker(self, channel, time, spr, flag_type):
        # Old system
        flag = Flag(channel=channel, time=time, spr=spr)
        self._flag_markers.append(flag)
        
        # New system (parallel)
        if self._timeline_stream:
            event = InjectionFlag(
                time=time,
                channel=channel,
                spr_value=spr,
                context=EventContext.LIVE,
                created_at=datetime.now()
            )
            self._timeline_stream.add_event(event)
```

**Use:** Update callers gradually. Old code uses `._flag_markers`, new code uses `.timeline_stream`.

### Path 2: Adapter Pattern (Clean)

Wrap old objects as new events:

```python
def flag_to_event(flag: Flag, context: EventContext) -> TimelineEvent:
    """Convert legacy Flag to TimelineEvent."""
    if flag.flag_type == 'injection':
        return InjectionFlag(
            time=flag.time,
            channel=flag.channel,
            spr_value=flag.spr,
            context=context,
            created_at=datetime.now()
        )
    elif flag.flag_type == 'wash':
        return WashFlag(
            time=flag.time,
            channel=flag.channel,
            context=context,
            created_at=datetime.now()
        )
    # ... etc
```

**Use:** Old code produces Flags, adapter converts to Events for new consumers.

### Path 3: Clean Refactor (Best Long-term)

Replace managers with timeline-aware versions:

```python
class NewFlagManager:
    """Timeline-aware injection/wash/spike manager."""
    
    def __init__(self, timeline_stream: TimelineEventStream):
        self.timeline = timeline_stream
        self.timeline_context: TimelineContext | None = None
    
    def set_timeline_context(self, context: TimelineContext):
        """Bind to global time reference."""
        self.timeline_context = context
    
    def add_injection_flag(
        self,
        channel: str,
        absolute_time: float,
        spr_value: float,
        confidence: float = 1.0,
    ) -> InjectionFlag:
        """Add injection flag using absolute time, convert to relative."""
        if not self.timeline_context:
            raise RuntimeError("timeline_context not set")
        
        relative_time = self.timeline_context.normalize_time(absolute_time)
        
        flag = InjectionFlag(
            time=relative_time,
            channel=channel,
            spr_value=spr_value,
            confidence=confidence,
            context=EventContext.LIVE,
            created_at=datetime.now()
        )
        
        self.timeline.add_event(flag)
        return flag
    
    def get_injection_flags(self, channel: str | None = None) -> list[InjectionFlag]:
        """Get all injection flags."""
        flags = self.timeline.get_flags()
        flags = [f for f in flags if isinstance(f, InjectionFlag)]
        if channel:
            flags = [f for f in flags if f.channel == channel]
        return flags
```

---

## Integration Points

### 1. RecordingManager → TimelineContext

```python
class RecordingManager:
    def start_recording(self, filename: str | None = None):
        # Create timeline context
        self.timeline_context = TimelineContext(
            recording_start_time=time.time(),
            recording_start_offset=0.0  # Or current elapsed time if resuming
        )
        
        # Share with all managers
        self.data_acquisition_mgr.set_timeline_context(self.timeline_context)
        self.flag_mgr.set_timeline_context(self.timeline_context)
        self.cycle_mgr.set_timeline_context(self.timeline_context)
```

### 2. DataAcquisitionManager → TimelineEventStream

```python
def on_spectrum_acquired(self, spectrum_dict):
    # ... process spectrum ...
    
    # If injection detected, add to timeline
    if injection_detected:
        self.flag_mgr.add_injection_flag(
            channel=channel,
            absolute_time=time.time(),
            spr_value=wavelength
        )
        # Flag manager adds to timeline_stream automatically
```

### 3. EditsTab → Query TimelineEventStream

```python
class EditsTab:
    def load_cycle_with_events(self, cycle_id: str):
        # Get all events for this cycle's time range
        cycle_start = ... # relative time
        cycle_end = ...
        
        events = self.timeline_stream.get_events_in_time_range(
            cycle_start, cycle_end
        )
        
        flags = [e for e in events if isinstance(e, InjectionFlag)]
        auto_markers = [e for e in events if isinstance(e, AutoMarker)]
        
        #  Display in graph
        self.render_events_on_graph(flags, auto_markers)
```

### 4. SensogramPresenter → Use TimelineContext

```python
class SensogramPresenter:
    def plot_sensorgram(self, data, timeline_context):
        # Convert all event times to relative for plotting
        for event in self.timeline_stream.get_flags():
            x_pos = event.time  # Already relative, no conversion needed!
            self.plot_vertical_line(x_pos, event.channel_color)
        
        # Set x-axis label
        self.x_axis.set_label(f"Time (s) since {timeline_context.recording_start_time}")
```

---

## Migration Checklist

### Completed ✅ (Feb 2026)
- [x] Create `TimelineContext` at `RecordingManager.start_recording()` — `affilabs/core/recording_manager.py`
- [x] Create `TimelineEventStream` in `RecordingManager.__init__()` — `affilabs/core/recording_manager.py`
- [x] Expose accessors `get_timeline_context()` / `get_timeline_stream()` on `RecordingManager`
- [x] Update `FlagManager` to add events to stream (parallel with old `._flag_markers`) — `affilabs/managers/flag_manager.py`
  - `add_flag_marker()` → `EventContext.LIVE`
  - `add_edits_flag()` → `EventContext.EDITS`
- [x] Update `CycleManager` to add `CycleMarker` events to stream — `mixins/_cycle_mixin.py`
  - Both incomplete-cycle path and normal completion path
  - Via `_emit_cycle_marker_to_timeline(cycle_export_data)` helper
- [x] Eliminate direct `._flag_markers` access from `_timer_mixin.py` → uses `flag_mgr.get_live_flags()` public API
- [x] Add integration tests — `tests/test_recording_manager_timeline.py` (6 tests, all passing)
- [x] Add runnable examples — `affilabs/domain/timeline_examples.py`

### Remaining (Phase 5+) — see `docs/future_plans/TIMELINE_ROADMAP.md`
- [ ] Update `SensogramPresenter` to query stream instead of `flag_mgr._flag_markers` directly
- [ ] Update `EditsTab` to display events from stream query
- [ ] Update `InjectionCoordinator` to emit `InjectionFlag` events directly to stream
- [ ] Wire `TimelineContext.normalize_time()` — flag times are currently stored as sensorgram-space floats (correct for graphing, but `TimelineContext` normalization not yet exercised)
- [ ] Remove old scattered offset logic from presenters
- [ ] Deprecate old time-conversion code

---

## Backward Compatibility

Old code continues to work:
```python
# Old way (still works)
flag = flag_mgr.get_flag_by_index(0)
print(flag.time)

# New way (recommended)
flags = timeline_stream.get_flags()
print(flags[0].time)
```

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Time conversions | Scattered across managers | Single `TimelineContext` |
| Event storage | Fragmented (flags, cycles, events separate) | Unified `TimelineEventStream` |
| Time queries | "Get flags from FlagManager + cycles from CycleManager" | `stream.get_events_in_time_range()` |
| Type safety | Flag/Cycle/AutoMarker are unrelated | All inherit `TimelineEvent` |
| Sorting | Manual in each manager | Automatic in stream |
| Deduplication | Manual checks | Built into stream |
| Testing | Difficult (time conversion logic hidden) | Easy (timeline is explicit) |

---

## Code Examples

### Example 1: Display all events in a time range

```python
# Old way
flags = flag_mgr.get_flags_in_range(start, end)  # If this method exists
cycles = cycle_mgr.get_cycles_in_range(start, end)  # If this method exists
# Combine and sort manually

# New way
events = timeline_stream.get_events_in_time_range(start, end)
for event in events:  # Already sorted by time
    print(f"{event.time:.1f}s: {event}")
```

### Example 2: Find injection reference and calculate time shifts

```python
# Old way
injection_flags = flag_mgr.get_injection_flags()
reference = next(f for f in injection_flags if f.is_reference)
for flag in injection_flags:
    time_shift = flag.time - reference.time
    # Store in app._channel_time_shifts[channel]

# New way
injection_events = [
    e for e in timeline_stream.get_flags()
    if isinstance(e, InjectionFlag)
]
reference = next(e for e in injection_events if e.is_reference)
for event in injection_events:
    event.time_shift = event.time - reference.time
    # Already stored in event.time_shift
```

### Example 3: Export events to Excel

```python
# Old way
events_for_export = []
for flag in flag_mgr._flag_markers:
    events_for_export.append({
        'time': flag.time,
        'type': flag.flag_type,
        'channel': flag.channel,
    })
# Cycles, auto markers handled separately

# New way
for event in timeline_stream:
    # All events have consistent structure
    rows.append({
        'time': event.time,
        'type': event.event_type.value,
        'channel': event.channel,
        'context': event.context.value,
    })
    # Metadata stored in event.metadata
```

---

## Questions & Answers

**Q: Do I have to refactor everything at once?**  
A: No. Use Path 1 (parallel systems) or Path 2 (adapters) to migrate gradually.

**Q: What about pause/resume of recording?**  
A: `TimelineContext.recording_start_offset` handles this. Set it to the elapsed time when recording resumes.

**Q: Can I query events while recording is in progress?**  
A: Yes. `TimelineEventStream` is thread-safe for reads. Use locking for adds if needed.

**Q: What if I need to remove/edit an event?**  
A: Create a new event, call `timeline_stream.clear()` and re-add all events. Or add `remove_event()` and `edit_event()` methods to `TimelineEventStream`.

