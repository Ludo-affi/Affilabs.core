# Affilabs.core — Shutdown Sequence

## Overview

There are three shutdown paths. All converge on `ResourceHelpers.cleanup_resources()`.

| Path | Trigger | `emergency` flag |
|------|---------|-----------------|
| **Graceful** | User clicks ✕ window button | `False` |
| **Emergency** | Process exit without normal close (`atexit`) | `True` |
| **Destructor** | `Application.__del__` called without prior `close()` | `True` |

---

## Graceful Shutdown — Step by Step

```
User clicks ✕
    │
    ▼
MainWindow.closeEvent()                         [affilabs_core_ui.py ~L3834]
    │  Snapshot connected device names (before cleanup nulls references)
    │  Call app_instance.close()
    │  Show "Unplug devices" QMessageBox if hardware was connected
    │  super().closeEvent(event)  ← Qt destroys the window
    │
    ▼
Application.close()                             [main.py ~L3585]
    │  Guard: if self.closing → return (prevents double-cleanup)
    │  self.closing = True
    │  _cleanup_resources(emergency=False)
    │  super().close()
    │  QApplication.quit()  ← forces event loop to drain and exit
    │
    ▼
ResourceHelpers.cleanup_resources(emergency=False)   [resource_helpers.py ~L30]
    │
    ├─ 1. STOP QT TIMERS  (must be first — they keep app.exec() alive)
    │       _ui_update_timer.stop()
    │       _profiling_timer.stop()
    │       _cycle_timer.stop()
    │       _cycle_end_timer.stop()
    │       _plunger_poll_timer.stop()
    │       _valve_poll_timer.stop()
    │
    ├─ 2. PRINT PROFILING STATS  (if PROFILING_ENABLED)
    │
    ├─ 3. STOP PROCESSING THREAD
    │       app._stop_processing_thread()
    │       (drains _spectrum_queue, joins worker thread)
    │
    ├─ 4. STOP DATA ACQUISITION
    │       data_mgr.stop_acquisition()
    │       (signals DAQ loop to exit, joins DAQ thread)
    │
    ├─ 5. STOP RECORDING
    │       recording_mgr.stop_recording()  (only if is_recording)
    │       (flushes pending data, closes HDF5/CSV files)
    │
    ├─ 6. STOP PUMPS
    │       kinetic_mgr.stop_all_pumps()
    │
    ├─ 7. HOME PUMPS (AffiPump only)
    │       pump_mgr.home_pumps()  (async, run in new event loop)
    │       (returns plunger to zero before disconnecting)
    │
    ├─ 8. DISCONNECT HARDWARE
    │       hardware_mgr.disconnect_all()
    │           → turn_off_channels()   ("lx" command — LEDs off)
    │           → close serial port     (controller)
    │           → usb.close()           (spectrometer)
    │
    └─ 9. CLOSE KINETICS CONTROLLER
            kinetic_mgr.kinetics_controller.close()
```

After `cleanup_resources` returns:

```
app.exec() returns exit_code               [main.py ~L3764]
    │
    ▼
sys.stderr / sys.stdout restored
    │
    ▼
sys.exit(exit_code)
```

---

## Emergency Shutdown

Triggered by `atexit` when the process exits without a normal `closeEvent` (e.g. `sys.exit()` called directly, crash after exception hook, or Ctrl+C handled by the exception hook):

```
atexit fires → Application._emergency_cleanup()        [main.py ~L3599]
    │  Guard: if self.closing → return (normal close already ran)
    │  Guard: if _intentional_disconnect → return
    │
    ▼
ResourceHelpers.cleanup_resources(emergency=True)
    │
    ├─ 1. STOP QT TIMERS  (same as graceful)
    │
    ├─ 2–5. SKIPPED  (no profiling, no thread joins, no pump homing)
    │
    ├─ 6. DISCONNECT HARDWARE  (fallback path — no disconnect_all())
    │       ctrl.turn_off_channels()
    │       _ctrl_raw.close()
    │       usb.close()
    │
    └─ 7. CLOSE KINETICS CONTROLLER
```

A second `atexit` handler (`emergency_silence`) fires after everything else and redirects `stdout`/`stderr` to a `NullWriter` to suppress I/O errors during interpreter teardown.

---

## Qt Timer Inventory

These timers are created during app initialization and **must** be stopped before the event loop can exit:

| Timer | Interval | Purpose |
|-------|----------|---------|
| `_ui_update_timer` | 500 ms | Drains pending UI update queue (2 Hz) |
| `_profiling_timer` | configurable | Prints profiling stats to console |
| `_cycle_timer` | 1 000 ms | Updates cycle elapsed-time display |
| `_cycle_end_timer` | one-shot | Fires when cycle duration expires |
| `_plunger_poll_timer` | 5 000 ms | Polls pump plunger position |
| `_valve_poll_timer` | 3 000 ms | Polls 6-port valve position |

Timers are stopped via the loop in `cleanup_resources` step 1. Each stop is guarded with `getattr` + `try/except` so a missing or already-stopped timer never raises.

---

## Active Injection During Close

If the user closes the window while a manual injection is in progress, the `ManualInjectionExec` daemon thread is blocked on `done_event.wait(timeout=70)` inside `injection_coordinator.execute_injection()`. Because it is a **daemon thread**, it does not prevent process exit — it will be forcibly killed by the OS when the main thread exits. The 70-second timeout is irrelevant at shutdown.

There is no explicit signal sent to `done_event` during shutdown. The hardware disconnect in step 8 will cause any in-progress pump command to fail with a serial I/O error, which the injection coordinator catches and handles.

---

## Key Source Files

| File | Role |
|------|------|
| `affilabs/affilabs_core_ui.py` | `closeEvent` — entry point for ✕ button |
| `main.py` | `Application.close()`, `_emergency_cleanup()`, `__del__` |
| `affilabs/utils/resource_helpers.py` | `ResourceHelpers.cleanup_resources()` — all shutdown logic |
| `affilabs/coordinators/injection_coordinator.py` | `execute_injection()` — injection thread that may be live at close |
