# Timeline System — Quick Start Integration Guide

**Status:** ✅ Integrated — Phases 1–4 complete (Feb 19 2026)  
**Location:** `affilabs/domain/timeline.py`  
**Examples:** `affilabs/domain/timeline_examples.py` (run with `python -m affilabs.domain.timeline_examples`)
**Roadmap:** `docs/future_plans/TIMELINE_ROADMAP.md`

---

## What You Get

A **unified event system** that replaces scattered time logic:

```python
# Old way (scattered)
flag_markers = []  # in FlagManager
cycle_table = []   # in CycleManager
auto_markers = {}  # in some coordinator

# New way (unified)
timeline_stream = TimelineEventStream()  # Single source of truth
timeline_context = TimelineContext(...)  # Shared time reference
```

---

## Core Classes

### TimelineContext
Converts between absolute and relative time. Used by all components.

```python
from affilabs.domain.timeline import TimelineContext

# At recording start
timeline = TimelineContext(
    recording_start_time=time.time(),
    recording_start_offset=0.0
)

# Later: convert times
relative_time = timeline.normalize_time(absolute_timestamp)
absolute_time = timeline.denormalize_time(relative_time)
```

### TimelineEventStream
Stores sorted events. Provides queries.

```python
from affilabs.domain.timeline import TimelineEventStream, InjectionFlag, EventContext
from datetime import datetime

stream = TimelineEventStream()

# Add event
stream.add_event(InjectionFlag(
    time=5.0,  # relative time
    channel='A',
    context=EventContext.LIVE,  # or EventContext.EDITS
    created_at=datetime.now(),
    spr_value=645.0,
    confidence=0.95
))

# Query
flags = stream.get_flags()  # All InjectionFlag + WashFlag + SpikeFlag
events_in_range = stream.get_events_in_time_range(0, 60)  # Between 0-60s
channel_a_events = stream.get_events_for_channel('A')
cycle_starts = stream.get_cycle_boundaries()  # All markers with is_start=True
```

### Event Types

```python
from affilabs.domain.timeline import (
    InjectionFlag,      # Binding event
    WashFlag,           # Buffer change
    SpikeFlag,          # Anomaly
    CycleMarker,        # Cycle start/end
    AutoMarker,         # System-generated (wash deadline, etc.)
    UserAnnotation,     # User text note
)
```

---

## Integration Path: Three Options

### Option 1: Parallel Systems (Recommended for now)
Keep old code working, add new timeline alongside

```python
# In RecordingManager.__init__()
from affilabs.domain.timeline import TimelineContext, TimelineEventStream

self._timeline_context = None
self._timeline_stream = TimelineEventStream()

# In start_recording()
import time
self._timeline_context = TimelineContext(
    recording_start_time=time.time(),
    recording_start_offset=0.0
)

# In FlagManager.add_flag_marker()
# Keep existing ._flag_markers
# Also add to timeline:
timeline_event = InjectionFlag(
    time=some_time,
    channel=channel,
    context=EventContext.LIVE,
    created_at=datetime.now(),
    spr_value=spr_value,
    confidence=confidence
)
self._timeline_stream.add_event(timeline_event)
```

**Benefits:**
- No breaking changes
- Can test new system in parallel
- Old UI keeps working while new features migrate

### Option 2: Adapter Pattern
Wrap existing collections with TimelineEventStream interface

```python
class FlagStreamAdapter:
    """Provides TimelineEventStream API over existing ._flag_markers."""
    
    def __init__(self, flag_markers_list):
        self._flags = flag_markers_list
    
    def get_flags(self):
        return self._flags
    
    def get_events_for_channel(self, channel):
        return [f for f in self._flags if f.channel == channel]
```

**Use when:** Refactoring large sections but want to stage migration

### Option 3: Clean Refactor
Replace old system entirely. Use when:
- Single manager being refactored
- No other code depends on old API
- Safe to change in one shot

```python
# Before
class FlagManager:
    def __init__(self):
        self._flag_markers = []
        self._cycles = []

# After
class FlagManager:
    def __init__(self):
        self._timeline_stream = TimelineEventStream()
    
    def add_flag(self, flag):
        self._timeline_stream.add_event(flag)
    
    def get_flags(self):
        return self._timeline_stream.get_flags()
```

---

## Change Checklist

### Phase 1: RecordingManager — ✅ Complete
- [x] Import `TimelineContext, TimelineEventStream`
- [x] Create `_timeline_context` in `__init__()`
- [x] Create `_timeline_stream` in `__init__()`
- [x] Initialize context in `start_recording()`
- [x] Clear context/stream on `stop_recording()` / `_cleanup_recording()`
- [x] Expose `get_timeline_context()` and `get_timeline_stream()` accessors

### Phase 2: FlagManager — ✅ Complete
- [x] Import `EventContext, TLInjectionFlag, TLWashFlag, TLSpikeFlag` (aliased to avoid collision with `domain.flag`)
- [x] `add_flag_marker()` calls `_add_to_timeline_stream(..., context=EventContext.LIVE)` after existing append
- [x] `add_edits_flag()` calls `_add_to_timeline_stream(..., context=EventContext.EDITS)`
- [x] `_add_to_timeline_stream()` is try/except-wrapped — old system never breaks if timeline fails
- [x] Public accessor `get_live_flags()` used by `_timer_mixin.py` (no more `._flag_markers` direct access)

### Phase 3: _timer_mixin.py public API — ✅ Complete
- [x] `flag_mgr._flag_markers` replaced with `flag_mgr.get_live_flags()` in `mixins/_timer_mixin.py`

### Phase 4: CycleMarker emission — ✅ Complete
- [x] `CycleMarker, EventContext` imported in `mixins/_cycle_mixin.py`
- [x] `_emit_cycle_marker_to_timeline(cycle_export_data)` helper added (try/except-wrapped)
- [x] Called at incomplete-cycle save path (~line 342)
- [x] Called at normal cycle completion path (~line 803)
- [x] Emits `CycleMarker(is_start=False, ...)` with `cycle_id`, `cycle_type`, `duration`

### Phase 5+: Presenters / Clean Refactor — ⏳ Pending
> See `docs/future_plans/TIMELINE_ROADMAP.md` for full spec.
- [ ] SensogramPresenter: Query `timeline_stream.get_events_in_time_range()` instead of `flag_mgr._flag_markers`
- [ ] EditsTab: Use stream queries for event display
- [ ] InjectionCoordinator: Emit `InjectionFlag` events directly to timeline stream
- [ ] Remove manual time-offset calculations from presenters

---

## Common Operations

### Add an injection flag
```python
from affilabs.domain.timeline import InjectionFlag, EventContext
from datetime import datetime

event = InjectionFlag(
    time=elapsed_time,
    channel='A',
    context=EventContext.LIVE,
    created_at=datetime.now(),
    spr_value=645.2,
    confidence=0.95,
    is_reference=True
)
timeline_stream.add_event(event)
```

### Find all events in a time window
```python
# Get all events between 10s and 120s
window_events = timeline_stream.get_events_in_time_range(10.0, 120.0)
```

### Get all injections for alignment
```python
flags = timeline_stream.get_flags()
injections = [f for f in flags if isinstance(f, InjectionFlag)]
reference = next((i for i in injections if i.is_reference), None)
```

### Convert recorded time to absolute timestamp
```python
relative_time = 42.5  # seconds from recording start
absolute_time = timeline_context.denormalize_time(relative_time)
dt = datetime.fromtimestamp(absolute_time)
```

### Handle pause/resume
```python
# When pausing
elapsed_so_far = 10.5
timeline_context.recording_start_offset = elapsed_so_far

# Subsequent events use offset automatically
```

### Separate live from edits
```python
# Live (auto-detected)
live_events = [e for e in timeline_stream if e.context == EventContext.LIVE]

# Edits (user-adjusted)
edits_events = [e for e in timeline_stream if e.context == EventContext.EDITS]
```

---

## Testing

Run examples to verify implementation:
```bash
cd <workspace>
python -m affilabs.domain.timeline_examples
```

Expected output:
```
======================================================================
Example 1: Basic Timeline Setup
======================================================================
Timeline: TimelineContext(started=..., offset=0s)
Event stream: TimelineEventStream(3 events: {'injection': 2, 'wash': 1})
Total events: 3

All events (in time order):
  • injection            @ t=   5.0s ch=A spr=645.2
  • injection            @ t=   8.5s ch=B spr=643.8
  • wash                 @ t= 120.0s ch=A spr=N/A
```

---

## Next Steps

1. **Review** `affilabs/domain/timeline.py` (332 lines, production-ready)
2. **Run examples** to understand the API: `python -m affilabs.domain.timeline_examples`
3. **Read the roadmap** at `docs/future_plans/TIMELINE_ROADMAP.md` for Phase 5+ spec
4. **Start Phase 5** when ready — SensogramPresenter + EditsTab query from stream

---

## FAQ

**Q: Do I have to refactor everything at once?**  
A: No. Use parallel systems (Option 1) to migrate gradually.

**Q: What about backward compatibility?**  
A: Keep old APIs working during transition. New code queries stream, old code still uses `._flag_markers`, etc.

**Q: How do I handle pause/resume?**  
A: Set `timeline_context.recording_start_offset` to elapsed time before pause. Stream queries automatically account for offset.

**Q: Can events have custom fields?**  
A: Yes. Use the `metadata` dict field (available on all event types) for custom data.

**Q: What about events that happen outside of timeline?**  
A: Events must have a relative time. If you don't have one, it's not really a timeline event.

