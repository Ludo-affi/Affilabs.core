# UI State Machine — Affilabs.core v2.0.5

> **Purpose**: Every application state, every transition, and exactly what UI changes at each one.
> **Source files**: [`affilabs/ui_mixins/_device_status_mixin.py`](../../affilabs/ui_mixins/_device_status_mixin.py), [`mixins/_acquisition_mixin.py`](../../mixins/_acquisition_mixin.py), [`mixins/_calibration_mixin.py`](../../mixins/_calibration_mixin.py), [`affilabs/app_state.py`](../../affilabs/app_state.py)

---

## State Overview

The application has two independent but interacting state axes:

```
HARDWARE STATE          ACQUISITION STATE
─────────────           ─────────────────
disconnected            idle
  │                       │
  ▼                       ▼
searching               acquiring
  │                       │
  ▼                       ▼
connected               paused
  │
  ▼
calibrated  ──────────► recording (overlays acquiring)
```

These are not exclusive: calibrated + idle, calibrated + acquiring, calibrated + acquiring + recording, etc. Each combination produces a distinct UI configuration.

---

## State 1 — DISCONNECTED

**Entry**: App launch, user confirms power-off, hardware scan fails, unexpected disconnect
**Power button**: Red (`#FF3B30`), tooltip "Red = Idle, Click to Connect"
**`powerState` property**: `"disconnected"`

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Power button | Enabled, red | Clicking starts scan → SEARCHING |
| Record button | Disabled | |
| Pause button | Disabled | |
| Subunit indicators (Sensor / Optics / Fluidics) | Gray "Not Ready" | `_reset_subunit_status()` |
| Device labels (P4SPR / P4PRO etc.) | Hidden | `hw_device_labels` all hidden |
| "No devices" message | Visible | `hw_no_devices.setVisible(True)` |
| "Add Hardware" button | Hidden | `add_hardware_btn.setVisible(False)` |
| Static mode indicator | Unavailable | `set_operation_mode_availability(False, False)` |
| Flow mode indicator | Unavailable | |
| Sidebar Settings tab | Enabled | User can change settings while disconnected |
| Sidebar Export tab | Enabled | User can configure export while disconnected |
| Sidebar Flow/Method tabs | Accessible (no live controls) | |

### Transition: DISCONNECTED → SEARCHING

**Trigger**: User clicks power button (from `disconnected` state)
**Handler**: `_handle_power_click()` in `_device_status_mixin.py`

**UI changes (immediate, before hardware search begins)**:
- Power button property → `"searching"`, style → yellow (`#FFCC00`)
- Power button tooltip → "Searching for Device... Click to CANCEL search"
- Connecting indicator shown (`show_connecting_indicator(True)`)
- `QCoreApplication.processEvents()` called to force immediate repaint

---

## State 2 — SEARCHING

**Entry**: User clicked Power button from disconnected state
**Power button**: Yellow (`#FFCC00`)
**`powerState` property**: `"searching"`

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Power button | Disabled for cancel | Clicking does nothing — no cancel implemented (`return` in handler) |
| Record button | Disabled | |
| Pause button | Disabled | |
| Subunit indicators | Gray "Not Ready" | Same as DISCONNECTED |
| Connecting indicator | Visible | Animated or visible spinner |

### Transition: SEARCHING → CONNECTED

**Trigger**: `HardwareManager.hardware_connected` signal → `_on_hardware_connected(status: dict)`
**Handler**: `set_power_state("connected")` in `_device_status_mixin.py` + `update_hardware_status(status)`

**UI changes**:
- Power button property → `"connected"`, style → green (`#34C759`)
- Power button tooltip → "Green = Device Connected, Click to power off"
- Connecting indicator hidden (`show_connecting_indicator(False)`)
- `_reset_subunit_status()` NOT called (stays gray until subunits verified)
- `update_hardware_status(status)` fires:
  - Device labels populated from `status["ctrl_type"]` via `CONTROLLER_DISPLAY_NAMES` map
  - AffiPump label shown only if `pump_connected=True` and NOT P4PROPLUS
  - "No devices" message hidden
  - "Add Hardware" button shown (`bool(ctrl_type)`)
  - Subunit readiness updated from `status` keys: `sensor_ready`, `optics_ready`, `fluidics_ready`
  - Fluidics subunit row: visible only if `fluidics_ready` key present (P4PRO/PROPLUS), hidden for P4SPR
  - Operation mode availability updated: static = `sensor_ready AND optics_ready`; flow = `flow_calibrated` (False until calibration)

### Transition: SEARCHING → DISCONNECTED (search failed)

**Trigger**: `HardwareManager.hardware_disconnected` signal or scan timeout
**UI changes**: Same as power-off: `set_power_state("disconnected")` → red button + `_reset_subunit_status()`

---

## State 3 — CONNECTED (not calibrated)

**Entry**: Hardware found and handshake complete
**Power button**: Green
**`powerState` property**: `"connected"`

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Power button | Enabled, green | Clicking shows confirm dialog → DISCONNECTED |
| Record button | **Disabled** | Not enabled until calibration completes |
| Pause button | **Disabled** | Not enabled until calibration completes |
| Subunit indicators | Per status dict | Sensor ✅/❌, Optics ✅/❌, Fluidics ✅/❌ or hidden |
| Calibrate button (sidebar) | Enabled | Starts calibration flow |
| Integration time input | Enabled | Hardware params editable pre-calibration |

### Transition: CONNECTED → SEARCHING (user power-off then back)

**Trigger**: User clicks green power button → confirm dialog → Yes
**UI changes**:
- Power button property → `"disconnected"` (immediately, before confirm dialog returns)
- `_reset_subunit_status()` called
- `power_off_requested` signal emitted → Application disconnects hardware

### Transition: CONNECTED → CALIBRATED

**Trigger**: `CalibrationService.calibration_complete` → `_on_calibration_complete_status_update(calibration_data)`
**Handler**: `mixins/_calibration_mixin.py` + `enable_controls()` in `_device_status_mixin.py`

**UI changes**:
- `enable_controls()` called:
  - `record_btn.setEnabled(True)` + tooltip "Start Recording"
  - `pause_btn.setEnabled(True)` + tooltip "Pause Live Acquisition"
- `CalibrationQCDialog` shown **modally** (`exec()`) — blocks UI until user dismisses
- After QC dialog closes: LEDs turned off, graph cleared
- Live spectrum updates resumed (`set_transmission_updates_enabled(True)`)
- LED intensities set from `calibration_data.p_mode_intensities`
- Settings panel repopulated (`_load_current_settings`)
- `flow_calibrated` flag set → operation mode availability updated (flow now enabled if pump present)

---

## State 4 — CALIBRATED (idle)

**Entry**: Calibration completes and QC dialog dismissed
**Record and Pause**: Both enabled

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Record button | Enabled | Click → RECORDING starts, acquisition begins |
| Pause button | Enabled | Click → PAUSED (only meaningful during acquisition) |
| Integration time input | **Disabled** | Locked during calibrated state (hardware set) |
| Detector profile selector | **Disabled** | Locked post-calibration |
| Servo position inputs | **Disabled** | Locked post-calibration |
| Method tab "Start" button | Enabled (if queue non-empty) | |
| Cycle queue | Editable | Can add/remove/reorder cycles |

### Transition: CALIBRATED → ACQUIRING

**Trigger**: User clicks Record button (or Method tab Start)
**Handler**: `_on_acquisition_started()` in `mixins/_acquisition_mixin.py`

**UI changes**:
- Spectroscopy subunit indicator → green, text "Running"
- Data buffers cleared (`buffer_mgr.clear_all()`)
- Pause markers from previous run cleared (via `QTimer.singleShot`)
- `experiment_start_time` reset to None (set on first spectrum)

---

## State 5 — ACQUIRING

**Entry**: Acquisition started (with or without recording)
**Spectroscopy status**: Green "Running"

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Record button | Enabled, toggleable | Click → starts RECORDING overlay |
| Pause button | Enabled | Click → PAUSED |
| Live graphs | Updating at UI timer rate (10 Hz max) | Full timeline + cycle-of-interest |
| Integration time input | Locked | |
| Hardware params | Locked | |
| Method tab Start | Disabled if cycle running | |
| Method tab Stop | Enabled | |

### Transition: ACQUIRING → RECORDING (overlay)

**Trigger**: User clicks Record button while acquiring
**Handler**: `_on_recording_started(filename)` in `mixins/_acquisition_mixin.py`

**UI changes**:
- Record button checked state = True
- Event marker "Recording Started" added to timeline graph at `t=elapsed`
- Recording metadata populated: device_id, operator, method_name, sensor_type
- Existing completed cycles and flags backfilled into recording

### Transition: ACQUIRING → PAUSED

**Trigger**: User clicks Pause button (toggles)
**Handler**: `acquisition_pause_requested.emit(True)` → `DataAcquisitionManager.pause_acquisition()`

**UI changes**:
- Pause button checked state = True
- Pause marker line added to full timeline graph
- Acquisition status label → "⏸️ Paused"

### Transition: ACQUIRING → CALIBRATED (acquisition stopped)

**Trigger**: `DataAcquisitionManager.acquisition_stopped` signal → `_on_acquisition_stopped()`
**Handler**: `mixins/_acquisition_mixin.py:264`

**UI changes**:
- `record_btn.setChecked(False)` + tooltip reset
- `pause_btn.setChecked(False)` + tooltip reset
- Spectroscopy subunit status → gray "Stopped"
- If recording was active: `recording_mgr.stop_recording()` called automatically

---

## State 6 — PAUSED

**Entry**: User clicked Pause during acquisition
**Power button**: Green (unchanged)

### UI at this state

| Element | State | Notes |
|---------|-------|-------|
| Pause button | Checked (shows "Resume" intent) | Click → resumes |
| Live graphs | Frozen (no new data) | Existing data visible |
| Record button | Enabled | Can start/stop recording while paused |

### Transition: PAUSED → ACQUIRING (resume)

**Trigger**: User clicks Pause button again (toggles off)
**Handler**: `acquisition_pause_requested.emit(False)` → `DataAcquisitionManager.resume_acquisition()`

**UI changes**:
- Pause button unchecked
- Acquisition status label → "🔴 Acquiring..."

---

## State 7 — RECORDING (overlay on ACQUIRING)

Recording is not a standalone state — it overlays ACQUIRING or PAUSED.

### UI while recording

| Element | State |
|---------|-------|
| Record button | Checked, text may show "⏺ Recording" |
| Timeline | Shows "Recording Started" event marker |
| Status bar | May show recording filename |

### Transition: RECORDING → ACQUIRING (recording stopped, acquisition continues)

**Trigger**: User clicks Record button to stop
**Handler**: `_on_recording_stopped()` → `recording_events.on_recording_stopped()`

**UI changes**:
- Record button unchecked
- `recording_event_coordinator` fires → progression banner auto-refreshes

### Transition: RECORDING → CALIBRATED (acquisition + recording both stop)

**Trigger**: Acquisition stops while recording active
**Handler**: `_on_acquisition_stopped()` detects `recording_mgr.is_recording` → calls `stop_recording()`

**UI changes**: Same as ACQUIRING → CALIBRATED transition (above), plus recording cleanup

---

## Complete State Transition Table

| From | To | Trigger | Key UI changes |
|------|----|---------|----------------|
| DISCONNECTED | SEARCHING | Power btn click | Button → yellow, connecting indicator shown |
| SEARCHING | CONNECTED | `hardware_connected` signal | Button → green, device labels populated, subunits updated |
| SEARCHING | DISCONNECTED | Scan fail / timeout | Button → red, subunits reset |
| CONNECTED | DISCONNECTED | Power btn click + confirm | Button → red, subunits reset |
| CONNECTED | CALIBRATED | `calibration_complete` signal | Record/Pause enabled, QC dialog (modal), graph cleared |
| CALIBRATED | ACQUIRING | Record/Start clicked | Spectroscopy → "Running", buffers cleared |
| ACQUIRING | PAUSED | Pause btn | Pause btn checked, pause marker on graph |
| ACQUIRING | RECORDING | Record btn (while acquiring) | Record btn checked, event marker on graph |
| ACQUIRING | CALIBRATED | `acquisition_stopped` signal | Record/Pause unchecked, Spectroscopy → "Stopped" |
| PAUSED | ACQUIRING | Pause btn again | Pause btn unchecked |
| RECORDING | ACQUIRING | Record btn (stop recording) | Record btn unchecked |
| RECORDING | CALIBRATED | Acquisition stops | Record + Pause unchecked, Spectroscopy → "Stopped" |
| ANY → DISCONNECTED | Unexpected disconnect | `hardware_disconnected` signal | Same as user power-off |

---

## ApplicationState Dataclass Groups

Defined in [`affilabs/app_state.py`](../../affilabs/app_state.py). These track internal state separate from UI visual state.

| Group | Key fields | Purpose |
|-------|-----------|---------|
| `LifecycleState` | `closing`, `initial_connection_done`, `intentional_disconnect` | Startup/shutdown guards |
| `CalibrationState` | `completed`, `retry_count`, `qc_dialog` | Calibration gating |
| `ExperimentState` | `start_time`, `last_cycle_bounds`, `session_cycles_dir` | Session timing |
| `ChannelState` | `selected_axis`, `ref_subtraction_enabled`, `ref_channel` | Display channel config |
| `FilteringState` | `display_filter_method`, `display_filter_alpha`, `ema_state` | Live smoothing state |
| `UIState` | `pending_graph_updates`, `skip_graph_updates`, `has_stop_cursor` | Update batching |
| `PerformanceState` | `spectrum_queue`, `processing_thread`, `acquisition_counter` | Throughput tracking |

> **Note**: `ApplicationState` migration is **incomplete**. `main.py` still uses scattered `self.*` instance variables. Both coexist. Do not remove the `self.*` vars without verifying all references.

---

## Rules for New Features

1. **Never check hardware state by reading widget properties.** Read from `hardware_mgr.is_connected` or the status dict — not `power_btn.property("powerState")`.
2. **Never call `enable_controls()` or `_reset_subunit_status()` from outside a signal handler.** These are responses to hardware events, not something to call proactively.
3. **Integration time and servo inputs must be locked in any calibrated state.** Check `app_state.calibration.completed` before enabling them.
4. **Acquisition stop always stops recording.** Never leave recording running when acquisition ends — `_on_acquisition_stopped()` enforces this.
5. **The QC dialog is the only `exec()` call in the calibration flow.** It is intentionally modal. Do not convert it to non-modal.
6. **State transitions originate from signals, not from direct method calls.** The pattern is: user action → signal emitted → Application handler → state change + UI update.
