# Sensor Chip Metadata — FRS

## Overview

When a user loads a new sensor chip they need to record what kind of chip it is and optionally
run a quick optical recalibration. The Method Builder dialog captures this at experiment setup time
so the information flows automatically into every Excel export.

---

## UI — Method Builder Header Row 2

File: `affilabs/widgets/method_builder_dialog.py`

A second header row is inserted below the Method Name / Operator row:

```
🧬 Surface  [COOH ▾]   📦 [Lot # (optional)]       [⬡ New Sensor Chip]
```

| Widget | Variable | Type | Notes |
|--------|----------|------|-------|
| Surface chemistry | `self.chip_type_combo` | QComboBox | 7 options + auto-suggest |
| Lot number | `self.lot_number_input` | QLineEdit | Free text, optional |
| New Sensor button | `self.new_sensor_btn` | QPushButton | Triggers Simple LED Cal |

### Chemistry Options

`"— select —"`, `"Au bare"`, `"COOH"`, `"Streptavidin"`, `"NTA-His"`, `"Protein A"`, `"Other"`

To add a new chemistry type: add the string to the `addItems([...])` call in `__init__` (line ~862).

---

## Auto-Suggestion Logic

Method: `_update_chip_suggestion()` — called inside `_refresh_method_table()` (fires on every
cycle list change).

**Only auto-sets if the combo is still at the default `"— select —"`.** Never overrides a user
selection.

| Cycle types present | Suggested chemistry |
|--------------------|---------------------|
| Immobilization + Blocking | `COOH` (EDC/NHS amine coupling) |
| Immobilization only (no Blocking) | `NTA-His` (NTA or Biotin capture) |
| Binding only / no Immobilization | No suggestion (stays `"— select —"`) |

---

## New Sensor Chip Button

Method: `_on_new_sensor_chip()` — calls `self._app_ref._on_simple_led_calibration()`.

`_app_ref` is passed into `MethodBuilderDialog.__init__(app=self)` from `_pump_mixin.py`.
The Simple LED Calibration (S+P intensity adjustment) runs without closing the dialog.

If hardware is not connected, shows a `QMessageBox.warning`.

---

## Data Flow

```
MethodBuilderDialog._on_push_to_queue()
  → builds chip_info = {"chip_type": "COOH", "lot_number": "LOT-2026-001"}
  → sets cycle.chip_info = chip_info on every cycle before emit

_cycle_mixin._on_start_recording()
  → reads chip_info from segment_queue[0].chip_info
  → passes to recording_mgr.start_recording(chip_info=...)

RecordingManager.start_recording(chip_info=...)
  → calls data_collector.update_metadata("chip_type", "COOH")
  → calls data_collector.update_metadata("lot_number", "LOT-2026-001")

Excel export → "Metadata" sheet (already built, no changes needed)
  chip_type  │ COOH
  lot_number │ LOT-2026-001
```

---

## Files Modified

| File | Change |
|------|--------|
| `affilabs/widgets/method_builder_dialog.py` | Header row 2 (chip_type, lot, New Sensor btn); `_update_chip_suggestion()`; `_on_new_sensor_chip()`; chip_info attached in `_on_push_to_queue`; `app=None` constructor param |
| `affilabs/domain/cycle.py` | `chip_info: Dict[str, Any]` field added |
| `affilabs/core/recording_manager.py` | `chip_info` param added to `start_recording()` |
| `mixins/_cycle_mixin.py` | Reads `chip_info` from first queued cycle, passes to `start_recording()` |
| `mixins/_pump_mixin.py` | Passes `app=self` when constructing `MethodBuilderDialog` |

---

## Verification

1. Open Method Builder → select "Amine Coupling" template → Surface auto-fills `"COOH"`
2. Select "Binding" template → Surface stays `"— select —"`
3. Change Surface manually → select template → Surface does NOT reset (user selection is respected)
4. Enter lot number, click "New Sensor Chip" → Simple LED Calibration dialog opens
5. Push to queue → start recording → export Excel → "Metadata" sheet shows `chip_type` and `lot_number`
6. Push with no chip info selected → Metadata sheet has no chip rows (empty strings skipped)
