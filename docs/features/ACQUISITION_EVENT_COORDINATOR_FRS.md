# Acquisition Event Coordinator — Feature Reference Specification

**Source:** `affilabs/coordinators/acquisition_event_coordinator.py`
**Status:** Implemented (v2.0.5)
**Layer:** Layer 3 — Orchestration / Coordinators
**Depends on:** `DataAcquisitionManager`, `HardwareManager`, `AffilabsMainWindow`

---

## 1. Purpose

Pure coordinator — no business logic. Bridges user actions (Start/Stop buttons, Pause/Resume) to `DataAcquisitionManager` and updates UI state accordingly. Handles acquisition errors and maps them to user-friendly dialogs.

---

## 2. Class: `AcquisitionEventCoordinator`

```python
AcquisitionEventCoordinator(
    data_mgr: DataAcquisitionManager,
    hardware_mgr: HardwareManager,
    main_window: AffilabsMainWindow,
    app,   # Application instance — access to other coordinators/managers
)
```

---

## 3. Public Methods (event handlers)

| Method | Trigger | What it does |
|--------|---------|-------------|
| `on_start_button_clicked()` | User clicks Start | Validates hardware → configures hardware → starts acquisition thread → updates UI |
| `on_acquisition_started()` | `DataAcquisitionManager.acquisition_started` signal | Enables record/pause buttons, resets experiment clock, clears data buffers, clears pause markers |
| `on_acquisition_stopped()` | `DataAcquisitionManager.acquisition_stopped` signal | Disables record/pause buttons, unchecks them, stops recording if active |
| `on_acquisition_pause_requested(pause: bool)` | Pause button toggle | Calls `data_mgr.pause_acquisition()` or `resume_acquisition()` |
| `on_acquisition_error(error: str)` | `DataAcquisitionManager.acquisition_error` signal | Shows error dialog; triggers `hardware_mgr.disconnect()` on USB disconnect |
| `on_detector_wait_changed(value: int)` | Detector wait slider | Updates `data_mgr.detector_wait_ms` |

---

## 4. Start Acquisition Sequence (3 phases)

```
Phase 1 — _validate_hardware()
  └── Checks hardware_mgr.ctrl (controller) and hardware_mgr.usb (spectrometer)
  └── Logs status; proceeds even if hardware not found (bypass mode)

Phase 2 — _configure_hardware()
  ├── _configure_polarizer()   → ctrl.set_mode("p") + POLARIZER_SETTLE_MS delay
  ├── _configure_integration_time() → usb.set_integration(time_ms)
  └── _configure_led_intensities()  → ctrl.set_intensity(ch, val) for each channel
  └── Uses calibration_data.p_integration_time and p_mode_intensities if calibrated
  └── Falls back to defaults (40ms integration, fixed intensities) if uncalibrated

Phase 3 — _start_acquisition()
  └── data_mgr.start_acquisition()
  └── On success: _update_ui_after_start() → enable_controls() → on_acquisition_started()
  └── On failure: show error dialog, return False
```

---

## 5. UI State Changes

### On acquisition start
- `main_window.enable_controls()` — enables record + pause buttons
- Spectroscopy status indicator → "Running" (green `#34C759`)
- `app.clock.reset()` — experiment elapsed timer resets to 0
- `app.buffer_mgr.clear_all()` — clears ring buffers for all channels
- Pause markers cleared from timeline graph (via `QTimer.singleShot(200, ...)`)

### On acquisition stop
- `record_btn` + `pause_btn` → disabled and unchecked
- Spectroscopy status indicator → "Stopped" (grey `#86868B`)
- If recording is active: `recording_mgr.stop_recording()` called automatically

---

## 6. Error Handling

| Error condition | Detection | Action |
|----------------|-----------|--------|
| USB disconnect during acquisition | `"disconnected"` in error string | `hardware_mgr.disconnect()` + warning dialog |
| Hardware communication lost | `"Hardware communication lost"` in error | `main_window.set_power_state("error")` + error dialog |
| Start acquisition failure | Exception in `data_mgr.start_acquisition()` | Error message dialog; acquisition not started |

---

## 7. Configuration Constants

| Constant | Source | Default | Purpose |
|----------|--------|---------|---------|
| `POLARIZER_SETTLE_MS` | `settings.py` | 400 | Wait time after polarizer mode change |
| Integration time | `CalibrationData.p_integration_time` | 40ms | Integration time from last calibration |
| LED intensities | `CalibrationData.p_mode_intensities` | `{a:255, b:150, c:150, d:255}` | Per-channel LED intensities |

---

## 8. Architecture Notes

- This coordinator is instantiated in `affilabs_core_ui.py` and wired to signals from `DataAcquisitionManager` in `main.py` at initialization.
- The `app` parameter gives access to `app.clock`, `app.buffer_mgr`, `app.recording_mgr` — these are shared application-level objects, not owned by this coordinator.
- `on_acquisition_started()` and `on_acquisition_stopped()` are **also** connected directly to `DataAcquisitionManager` Qt signals (not just called from `on_start_button_clicked`) — both paths must remain consistent.
- No business logic lives here — decisions about whether calibration is required, whether to allow acquisition, etc. are made upstream by the hardware state machine.
