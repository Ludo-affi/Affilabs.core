# Startup Calibration Dialog — Feature Reference Specification

**Source:** `affilabs/dialogs/startup_calib_dialog.py`
**Status:** Implemented (v2.0.5)
**Layer:** Layer 4 — UI / Dialogs
**Depends on:** PySide6, `affilabs/core/calibration_service.py` (via signals)

---

## 1. Purpose

Non-modal progress dialog for the startup calibration workflow. Displays calibration progress, step descriptions, and final result to the user. Exposes three buttons (Start, Retry, Continue Anyway) that emit signals to the calibration orchestrator.

**Non-modal** — the main window remains accessible during calibration (though hardware controls are disabled by the state machine).

---

## 2. Class: `StartupCalibProgressDialog`

```python
StartupCalibProgressDialog(
    parent: QWidget | None = None,
    title: str = "Processing",
    message: str = "Please wait...",
    show_start_button: bool = False,
)
```

Size: 460–520px wide, 240–540px tall. Centered on parent.

---

## 3. Signals (outbound — consumed by calibration orchestrator)

| Signal | When emitted | Handler |
|--------|-------------|---------|
| `start_clicked` | User clicks Start | Begins calibration sequence |
| `retry_clicked` | User clicks Retry after failure | Re-runs calibration |
| `continue_anyway_clicked` | User clicks Continue Anyway after failure | Dismisses dialog, proceeds without recalibration |

---

## 4. Internal Signals (thread-safe UI updates)

All calibration logic runs on a worker thread. The dialog exposes internal Qt signals for thread-safe dispatch to the UI thread:

| Internal signal | Parameters | Purpose |
|----------------|-----------|---------|
| `_update_title_signal` | `str` | Update dialog title |
| `_update_status_signal` | `str` | Update main status text |
| `_update_step_description_signal` | `str` | Update step detail text |
| `_set_progress_signal` | `(int value, int maximum)` | Update progress bar |
| `_hide_progress_signal` | — | Hide progress bar (on completion) |
| `_enable_start_signal` | — | Enable the Start button |
| `_close_signal` | — | Close the dialog from worker thread |

These are connected to slot methods in `__init__` via `Qt.QueuedConnection`. Worker threads call `dialog._update_status_signal.emit("...")` — never modify widgets directly.

---

## 5. Button States

| State | Start | Retry | Continue Anyway |
|-------|-------|-------|----------------|
| Initial (waiting) | Hidden or disabled | Hidden | Hidden |
| Ready to calibrate | Visible, enabled | Hidden | Hidden |
| Calibrating | Disabled | Hidden | Hidden |
| Calibration success | Hidden | Hidden | Hidden (dialog auto-closes) |
| Calibration failure | Hidden | Visible | Visible |

`show_start_button=True` is used when the dialog is shown at app launch before the user explicitly triggers calibration (i.e. the Start button is the trigger).

---

## 6. Layout

```
┌──────────────────────────────────────────┐
│ [Title label]                            │
│ [Status label — main message]            │
│ [Step description — secondary detail]    │
│ ─────────────────────────────────────── │
│ [Progress bar]                           │
│ ─────────────────────────────────────── │
│         [Start]  [Retry]  [Cont. Anyway] │
└──────────────────────────────────────────┘
```

Drop shadow effect applied to the dialog frame. Progress bar hidden when `_hide_progress_signal` is emitted.

---

## 7. Race Condition Guard

`self._is_closing: bool` flag prevents multiple close events from racing (worker thread emits `_close_signal` while user also closes the window). Checked at the start of the close handler.

---

## 8. Calibration Progress Messages

Calibration orchestrator (`CalibrationService`) emits `calibration_progress = Signal(str, int)` — message and percent. The dialog maps these to:

- `_update_status_signal.emit(message)` — step label
- `_set_progress_signal.emit(percent, 100)` — progress bar

On `calibration_complete` signal: dialog hides progress bar, shows success message, auto-closes after brief delay.

On `calibration_failed` signal: dialog shows failure message + triage text, enables Retry + Continue Anyway buttons.

---

## 9. Triage Text Integration

When calibration fails, `CalibrationService` appends a triage message to the error string based on device history (see `STARTUP_CALIBRATION_TROUBLESHOOTING.md`). This appears in the `_update_status_signal` message on failure — no additional parsing needed in the dialog.

---

## 10. Key Gotchas

- The dialog is **not** shown modally (`self.setModal(False)`) — don't assume it blocks execution. The calibration workflow is driven by signals, not by `exec_()` return value.
- All worker-thread → UI updates **must** go through the internal signals. Direct `setText()` from a worker thread will crash on Windows with Qt6.
- `continue_anyway_clicked` does not validate that calibration succeeded — the orchestrator must handle the uncalibrated state gracefully (bypass mode / demo fallback).
- `_close_signal` is the only safe way to close the dialog from a non-GUI thread. Never call `dialog.close()` directly from a worker thread.
