# Guidance Coordinator FRS — Affilabs.core v2.0.5

> **Status**: Pass A complete (signal wiring + hint logic). Pass B (widget calls) pending.
> **Source file**: [`affilabs/coordinators/guidance_coordinator.py`](../../affilabs/coordinators/guidance_coordinator.py)
> **Plan**: [`docs/future_plans/ADAPTIVE_GUIDANCE_PLAN.md`](../future_plans/ADAPTIVE_GUIDANCE_PLAN.md)

---

## Overview

`GuidanceCoordinator` provides adaptive per-stage UI guidance based on the active user's experience level. Novice users see inline hints at each experiment stage; experienced users see a clean, hint-free UI.

This is a **plain Python object** — not a `QObject`. Signal wiring is done in `main.py` via lambda wrappers. This keeps `UserProfileManager` free of Qt dependencies.

---

## Guidance Levels

Derived from `UserProfileManager.get_guidance_level()`, which reads the active user's experiment count:

| Level | Trigger | Hints shown |
|-------|---------|-------------|
| `full` | 0–4 experiments (Novice) | All 6 stage hints, until each is dismissed |
| `standard` | 5–19 experiments (Operator) | Connect + Calibrate hints suppressed; others shown once |
| `minimal` | 20+ experiments (Specialist / Expert / Master) | No hints — clean UI |

The level is evaluated once at launch and refreshed whenever the active user changes.

---

## Hint Keys

One hint key per experiment stage:

| Constant | Value | Stage |
|----------|-------|-------|
| `HINT_CONNECT` | `"hint_connect_shown"` | Hardware connected |
| `HINT_CALIBRATE` | `"hint_calibrate_shown"` | Calibration complete |
| `HINT_ACQUIRE` | `"hint_acquire_shown"` | Acquisition started |
| `HINT_INJECT` | `"hint_inject_shown"` | Injection flag placed |
| `HINT_RECORD` | `"hint_record_shown"` | Recording started |
| `HINT_EXPORT` | `"hint_export_shown"` | (Not yet wired) |

Shown state is persisted via `UserProfileManager.mark_hint_shown(key)` and read back via `is_hint_shown(key)` — so hints only appear once per user account even across sessions.

---

## Public Entry Points

Called from signal wrappers in `main.py`:

| Method | Connected to |
|--------|-------------|
| `on_hardware_connected(*args)` | `HardwareManager.hardware_connected` |
| `on_calibration_complete(*args)` | `CalibrationService.calibration_complete` |
| `on_acquisition_started(*args)` | `DataAcquisitionManager.acquisition_started` |
| `on_injection_flag(*args)` | `InjectionCoordinator.injection_flag_requested` |
| `on_recording_started(*args)` | `RecordingManager.recording_started` |

Each method checks `_should_show(hint_key)` before doing anything.

---

## Show Logic (`_should_show`)

```python
def _should_show(self, hint_key: str) -> bool:
    if self._guidance_level == "minimal":
        return False
    if self._guidance_level == "standard" and hint_key in (HINT_CONNECT, HINT_CALIBRATE):
        return False
    return not self._um.is_hint_shown(hint_key)
```

---

## User Change Handling

`GuidanceCoordinator` registers `_on_user_changed` as `UserProfileManager.on_user_changed`. This callback fires immediately after a user switch and:

1. Refreshes `_guidance_level` for the new user
2. Syncs the Export tab user profile card (`_update_progression_display()`)
3. Syncs `sidebar.user_combo` selection without re-triggering the signal (`blockSignals`)

---

## Implementation Status

### Pass A — Complete
- Signal wiring infrastructure
- Hint level logic (`_should_show`)
- User change callback
- `mark_hint_shown` persistence
- Logging for all hint firings

### Pass B — Pending (v2.1)
`_apply_hint()` currently only logs. Pass B will route each hint key to a specific widget call:

| Hint key | Planned widget action |
|----------|-----------------------|
| `HINT_CONNECT` | Highlight calibration button; show inline "Run startup calibration" label |
| `HINT_CALIBRATE` | Highlight "Build Method" button; show inline "Design your first method" label |
| `HINT_ACQUIRE` | Show "Watching for baseline stability" badge |
| `HINT_INJECT` | Show "Mark your injection point" tooltip near timeline |
| `HINT_RECORD` | Show "Recording — data is being saved" status |

Pass B widget calls will use `main_window` references stored at construction time. No new coordinator signals needed.

---

## Construction

```python
# In main.py or AffilabsApp.__init__:
self.guidance_coordinator = GuidanceCoordinator(app=self)

# Signal wiring (lambda wrappers avoid QObject dependency):
hardware_mgr.hardware_connected.connect(
    lambda status: self.guidance_coordinator.on_hardware_connected(status)
)
calibration_service.calibration_complete.connect(
    lambda data: self.guidance_coordinator.on_calibration_complete(data)
)
# ... etc
```
