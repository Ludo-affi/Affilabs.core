# Timeline System — Phase 5+ Roadmap

**Status:** Phases 1–4 implemented (Feb 19 2026). Improvements B, C, D implemented (Feb 20 2026). Improvements E, F implemented (Feb 20 2026). Improvement A deferred (not applicable to current event sources). This file tracks remaining proposed improvements for future implementation.  
**Context:** `docs/architecture/TIMELINE_QUICK_START.md` and `TIMELINE_INTEGRATION_GUIDE.md` describe the current state.  
**Domain model:** `affilabs/domain/timeline.py`

---

## What Is Already Live

| Phase | File Modified | What It Does |
|-------|--------------|-------------|
| 1 | `affilabs/core/recording_manager.py` | `TimelineContext` + `TimelineEventStream` created at recording start; exposed via `get_timeline_context()` / `get_timeline_stream()` |
| 2 | `affilabs/managers/flag_manager.py` | `add_flag_marker()` and `add_edits_flag()` write `TLInjectionFlag` / `TLWashFlag` / `TLSpikeFlag` to stream in parallel with old `_flag_markers` list |
| 3 | `mixins/_timer_mixin.py` | Replaced direct `flag_mgr._flag_markers` access with public `flag_mgr.get_live_flags()` API |
| 4 | `mixins/_cycle_mixin.py` | `_emit_cycle_marker_to_timeline()` emits `CycleMarker(is_start=False)` at both cycle-save call sites |
| B | `affilabs/domain/timeline.py` | Added `threading.RLock` to `TimelineEventStream`; all reads return list copies; `__iter__` returns snapshot |
| C | `main.py` | `CycleMarker(is_start=True)` emitted at cycle start (`_on_start_button_clicked` flow, ~line 2050) |
| D | `affilabs/ui_mixins/_timer_mixin.py` | `AutoMarker(marker_kind='wash_deadline')` emitted in `_place_automatic_wash_flags()` after wash flags are placed |
| E | `affilabs/services/excel_exporter.py` | `timeline_stream=None` param added to `export_to_excel()`; "Timeline Events" sheet (Sheet 9) written when stream provided |
| F | `affilabs/domain/timeline.py` | `remove_event()` and `update_event_time()` added to `TimelineEventStream` |

---

## Phase 5 — Presenter Queries from Stream

**Priority:** Medium  
**Effort:** ~2–3 hours  
**Impact:** Eliminates the last direct consumers of `flag_mgr._flag_markers` from presentation layer

### 5a: SensogramPresenter

`affilabs/presenters/sensogram_presenter.py` currently calls `flag_mgr.get_live_flags()` (the domain `Flag` objects) to render vertical lines on the sensorgram graph. Post-Phase-5, it should query the timeline stream instead.

```python
# Current (inferred from codebase)
flags = self.flag_mgr.get_live_flags()
for flag in flags:
    self._plot_flag(flag.time, flag.channel, flag.flag_type)

# Proposed
stream = self.recording_mgr.get_timeline_stream()
for event in stream.get_flags():
    self._plot_flag(event.time, event.channel, event.event_type.value)
```

**Gotcha:** `SensogramPresenter.flag_markers` is a *separate* list of pyqtgraph visual objects (`InfiniteLine + TextItem`) used for `removeItem()`. This is NOT the domain event list — do not confuse the two. Only the query source changes.

### 5b: EditsTab Event Display

`affilabs/tabs/edits/` currently reads flags from `FlagManager._flag_markers` for the Edits cycle graph. Should query stream for a given time window instead.

```python
# Proposed
stream = self.recording_mgr.get_timeline_stream()
cycle_flags = stream.get_events_in_time_range(cycle.start_time, cycle.end_time)
injection_flags = [e for e in cycle_flags if isinstance(e, TLInjectionFlag)]
```

**Prerequisite:** EditsTab must have a reference to `recording_mgr` or the stream passed in.

---

## Phase 6 — InjectionCoordinator Stream Integration

**Priority:** Low  
**Effort:** ~1 hour  
**File:** `affilabs/coordinators/` (injection-related coordinator)

Currently, auto-detected injections go through `FlagManager.add_flag_marker()`, which already writes to the stream (Phase 2). But the coordinator itself could emit higher-fidelity events directly:

```python
# Proposed addition to InjectionCoordinator
stream = self.recording_mgr.get_timeline_stream()
stream.add_event(InjectionFlag(
    time=detected_time,
    channel=channel,
    context=EventContext.LIVE,
    created_at=datetime.now(),
    spr_value=spr_value,
    confidence=confidence,  # Currently only stored in stream if emitted here
))
```

**Note:** Confidence is currently not preserved in the timeline stream because `FlagManager.add_flag_marker()` doesn't receive it. Emitting directly from the coordinator would preserve it.

---

## Phase 7 — Clean Refactor (Path 3)

**Priority:** Low (defer until stable)  
**Effort:** ~1 day  
**Risk:** Breaking changes to public APIs

Replace `FlagManager._flag_markers` (legacy `Flag` domain objects) entirely with stream-backed storage:

```python
# Proposed
class FlagManager:
    def add_flag_marker(self, channel, time_val, spr_val, flag_type):
        # Write only to stream — no _flag_markers list
        self._add_to_timeline_stream(channel, time_val, spr_val, flag_type)

    def get_live_flags(self):
        # Read from stream — no backing list
        stream = self.recording_mgr.get_timeline_stream()
        return stream.get_flags()
```

**Blocker:** All callers of `get_live_flags()` must be ready for `TimelineEvent` objects instead of `Flag` objects. Requires Phase 5 to be complete first.

---

## Proposed Improvements (Remaining)

### A — TimelineContext.normalize_time() integration

**Status:** ⚠️ Deferred — not applicable to current event sources.

`time_val` passed to `add_flag_marker()` / `add_edits_flag()` / cycle markers is already in recording-relative seconds (sensorgram X axis). `TimelineContext.normalize_time()` expects an absolute Unix timestamp and subtracts `recording_start_offset` — applying it to already-relative floats would produce large negative numbers.

**When to revisit:** Only if InjectionCoordinator or other source emits events using `time.time()` directly (Phase 6). For now, all event sources produce sensorgram-space floats and this conversion step is skipped correctly.

### B — Thread Safety for add_event()

**Status:** `TimelineEventStream.add_event()` uses `bisect.insort()` on a plain Python list. Reads and writes from multiple threads (acquisition thread + UI thread) could race.

**Fix:**
```python
import threading

class TimelineEventStream:
    def __init__(self):
        self._events: list[TimelineEvent] = []
        self._lock = threading.RLock()

    def add_event(self, event: TimelineEvent) -> None:
        with self._lock:
            bisect.insort(self._events, event)

    def get_flags(self) -> list:
        with self._lock:
            return [e for e in self._events if isinstance(e, (InjectionFlag, WashFlag, SpikeFlag))]
```

**Priority:** Implement before Phase 5 (when UI thread reads from stream directly).

### C — CycleMarker START events

**Status:** Only END markers are emitted today (`is_start=False`). Start markers would enable duration calculation from the stream alone.

**Implementation:** In `mixins/_cycle_mixin.py`, find where `_current_cycle` is assigned a new `Cycle` object and emit `CycleMarker(is_start=True, time=cycle.sensorgram_time, ...)`.

### D — AutoMarker emission from wash deadline timer

**Status:** The contact timer in `_timer_mixin.py` / wash deadline logic is not yet wired to emit `AutoMarker` events to the timeline stream. Adding this would allow the UI to query all wash deadlines from one place.

**File:** `mixins/_timer_mixin.py` — find where wash deadline time is calculated and emit:
```python
stream.add_event(AutoMarker(
    time=wash_deadline_time,
    channel=channel,
    context=EventContext.LIVE,
    created_at=datetime.now(),
    marker_kind='wash_deadline',
    label='⏱ Wash Due',
))
```

### E — Timeline Export to Excel

**Status:** ✅ Implemented (Feb 20 2026).

`export_to_excel()` now accepts `timeline_stream: TimelineEventStream | None = None`. When provided, writes Sheet 9 "Timeline Events" with columns: `time_s`, `event_type`, `channel`, `context`, `label`, `details`, `created_at`. Type-specific `details` formatting for all event classes. Wrapped in try/except — non-critical.

### F — TimelineEventStream.remove_event() / update_event_time()

**Status:** ✅ Implemented (Feb 20 2026).

- `remove_event(event) -> bool`: Removes from both `_events` and `_by_type` index. Returns `True` if found. Thread-safe via `_lock`.
- `update_event_time(event, new_time) -> bool`: Updates `event.time` (clamped to >= 0) and re-sorts `_events` to maintain order. Returns `False` if event not in stream. Thread-safe via `_lock`.

---

### Known Correctness Notes

1. **Flag times are sensorgram-space floats** — `time_val` passed to `add_flag_marker()` and `add_edits_flag()` is already in recording-relative seconds (sensorgram X axis). `TimelineContext.normalize_time()` is not applied (see improvement A below). This is correct for current graphing use and matches what `SensogramPresenter` expects.

2. **CycleMarker coordinate spaces:** START markers use `RAW_ELAPSED` coords (`_cycle_start_raw`); END markers from `_cycle_mixin.py` use RECORDING-relative coords (after `clock.convert(RAW_ELAPSED → RECORDING)`). These will differ if there are recording pauses. **Future cleanup:** normalize both to the same coord space.

3. **CycleMarker cycle_id is stringified** — `str(cycle_export_data.get('cycle_id', ''))` because `cycle_id` may be an `int` or `str` depending on cycle origin. Stream stores it as `str`.

4. **FlagManager uses aliased imports** — `TLInjectionFlag`, `TLWashFlag`, `TLSpikeFlag` to avoid collision with `affilabs.domain.flag.InjectionFlag`. This is intentional — two separate domain classes coexist during the parallel-systems phase.

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Feb 20 2026 | B: Thread safety added to `TimelineEventStream` via `RLock`; reads return list copies; `__iter__` is snapshot | Required before Phase 5 (UI-thread reads) |
| Feb 20 2026 | C: `CycleMarker(is_start=True)` emitted in `main.py` on cycle start | Completes cycle tracking (both boundaries now present) |
| Feb 20 2026 | D: `AutoMarker(marker_kind='wash_deadline')` emitted in `_timer_mixin.py` at automatic wash placement | Wash timing now queryable from stream |
| Feb 20 2026 | E: `export_to_excel(timeline_stream=None)` param + Sheet 9 "Timeline Events" | Full event audit trail in Excel export |
| Feb 20 2026 | F: `remove_event()` + `update_event_time()` added to `TimelineEventStream` | Stream no longer append-only; enables flag correction |
| Feb 20 2026 | A: Deferred — `time_val` is already sensorgram-space; `normalize_time()` not applicable | Would produce wrong negative values if applied to existing sources |
| Feb 2026 | Parallel systems (Path 1) chosen over clean refactor | Zero risk to live codebase; allows gradual migration |
| Feb 2026 | FlagManager uses aliased TL* imports | Avoids naming collision with `domain.flag.InjectionFlag` |
| Feb 2026 | CycleMarker END emits only from `_cycle_mixin.py` | Sufficient for Phase 4 |
