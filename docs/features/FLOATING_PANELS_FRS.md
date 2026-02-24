# Floating Panels FRS — Affilabs.core v2.0.5

> **Status**: Implemented (v2.0.5)
> **Source files**:
> - [`affilabs/widgets/spectrum_bubble.py`](../../affilabs/widgets/spectrum_bubble.py)
> - [`affilabs/widgets/rail_timer_popup.py`](../../affilabs/widgets/rail_timer_popup.py)
> - [`affilabs/widgets/live_context_panel.py`](../../affilabs/widgets/live_context_panel.py)
> - [`affilabs/widgets/live_right_panel.py`](../../affilabs/widgets/live_right_panel.py)

---

## Overview

Four floating/overlay panel widgets introduced in v2.0.5 as part of the sidebar redesign. All are independent `QWidget`/`QFrame` subclasses — none consume splitter space from the main layout.

| Widget | Toggle source | Position | Purpose |
|--------|--------------|----------|--------|
| `SpectrumBubble` | IconRail spectrum button | Bottom-left of main window | Floating spectroscopy view (transmission + raw) |
| `RailTimerPopup` | IconRail timer button | Right of rail, beside timer button | Standalone countdown timer |
| `LiveContextPanel` | Phase 3 sidebar redesign (v2.1) | Left panel on Live page | Inline spectroscopy alongside sensorgram |
| `LiveRightPanel` | Acquisition signals (v2.1) | Right panel on Live page | Active cycle card + queue + elapsed time |

---

## SpectrumBubble

**File**: `affilabs/widgets/spectrum_bubble.py`
**Class**: `SpectrumBubble(QFrame)`
**Size**: 310 × 380px (fixed)
**Position**: Bottom-left of parent window, `_MARGIN_LEFT=16px`, `_MARGIN_BOTTOM=52px` (clears transport bar)
**Default**: Hidden

### Structure

```
┌─────────────────────────────┐
│  Spectroscopy            ✕  │  ← drag handle header (44px)
├─────────────────────────────┴
│  [Transmission]  [Raw]      │  ← pill tab row
├─────────────────────────────┴
│  pyqtgraph plot (220px)     │  ← QStackedWidget, one plot per tab
├─────────────────────────────┴
│  [Capture 5-Min Baseline]   │  ← baseline capture button
└─────────────────────────────┘
```

### Public Attributes

| Attribute | Type | Purpose |
|-----------|------|--------|
| `transmission_plot` | `pyqtgraph.PlotWidget` | Transmission spectrum |
| `transmission_curves` | `list[PlotDataItem]` | 4 channel curves (A–D) |
| `raw_data_plot` | `pyqtgraph.PlotWidget` | Raw detector counts |
| `raw_data_curves` | `list[PlotDataItem]` | 4 channel curves (A–D) |
| `baseline_capture_btn` | `QPushButton` | Trigger 5-min baseline capture |

These are aliased to `main_window` after construction so `SpectroscopyPresenter` can find them at the same attribute names as the old Settings sidebar plots.

### API

```python
bubble.toggle()       # show/hide; on show: repositions then raises
bubble.reposition()   # snap to bottom-left of parent — call from resizeEvent
```

### Dragging

Header has `SizeAllCursor`. `mousePressEvent` + `mouseMoveEvent` on the header implement drag by tracking `_drag_offset = globalPos - frameGeometry().topLeft()`.

### Close Button

`✕` button calls `_close_and_uncheck()` — hides self and sets `parent.spectrum_toggle_btn.setChecked(False)`.

### Drop Shadow

`QGraphicsDropShadowEffect`: blur 32px, offset (0, 6), `rgba(0,0,0,55)`.

---

## RailTimerPopup

**File**: `affilabs/widgets/rail_timer_popup.py`
**Class**: `RailTimerPopup(QFrame)`
**Size**: 240 × 250px (fixed)
**Window flags**: `Qt.Tool | Qt.FramelessWindowHint` (top-level, no taskbar entry)
**Default**: Hidden

### Structure

```
┌──────────────────────────┐
│  Timer               ✕   │  ← drag handle (42px)
├──────────────────────────┴
│         05:00            │  ← 44px monospace countdown
│   [1m][2m][5m][10m][15m] │  ← preset chips
│  [   Start / Pause   ][↺]│  ← controls row
└──────────────────────────┘
```

### Signals

| Signal | Payload | When |
|--------|---------|------|
| `timer_started` | `int` (total seconds) | User clicks Start from idle |
| `timer_finished` | — | Countdown reaches zero |

### State Machine

```
idle → running → paused → running → ... → finished → idle
```

| State | Start button label | Display color |
|-------|--------------------|---------------|
| `idle` | “Start” (blue fill) | `#1D1D1F` |
| `running` | “Pause” (blue outline) | `#1D1D1F` |
| `paused` | “Resume” (orange outline) | `#1D1D1F` |
| `finished` | “Dismiss” (orange fill) | Blinks orange/black at 600ms |

### Presets

`[1m][2m][5m][10m][15m]` — selecting a preset resets the timer to that duration. Active preset chip is blue-filled.

### Alert

On `finished`: `QApplication.beep()` + `_alert_timer` at 600ms blinks the countdown display orange. Clicking “Dismiss” or ↺ stops the alert.

### Positioning

`IconRail._on_timer_click()` positions the popup right of the rail:
```python
popup_x = rail.mapToGlobal(rail.rect().topRight()).x() + 4
popup_y = btn_center.y() - popup.height() // 2
```

---

## LiveContextPanel

**File**: `affilabs/widgets/live_context_panel.py`
**Class**: `LiveContextPanel(QFrame)`
**Fixed width**: 230px
**Status**: Stub — Phase 3 of sidebar redesign (v2.1, not yet wired into main layout)

### Purpose

Moves transmission + raw spectroscopy plots from the Settings sidebar into the main Live page view, keeping them visible during live acquisition without needing the sidebar open.

### Structure

```
SPECTROSCOPY  ← section label

Transmission (%):
[pyqtgraph transmission plot — 160px tall]
[REC] Capture 5-Min Baseline

Raw Signal (counts):
[pyqtgraph raw data plot — 160px tall]
```

### Public Attributes

| Attribute | Type | Purpose |
|-----------|------|--------|
| `transmission_plot` | `PlotWidget` | Transmission spectrum |
| `transmission_curves` | `list` | 4 channel curves (A–D) |
| `raw_data_plot` | `PlotWidget` | Raw counts |
| `raw_data_curves` | `list` | 4 channel curves (A–D) |
| `baseline_capture_btn` | `QPushButton` | 5-min baseline capture |

### Integration (v2.1)

Will be inserted as the leftmost panel in the Live page `QSplitter`, between `IconRail` and the sensorgram graphs. Controlled by acquisition signals — shown on `acquisition_started`, hidden on `acquisition_stopped`.

---

## LiveRightPanel

**File**: `affilabs/widgets/live_right_panel.py`
**Class**: `LiveRightPanel(QFrame)`
**Fixed width**: 220px
**Status**: Stub — Phase 2 of sidebar redesign (v2.1, not yet wired into main layout)

### Purpose

Consolidates acquisition-time information (active cycle card, queue summary, elapsed time) into a dedicated right panel on the Live page, freeing the sidebar from having to stay open during runs.

### Public Attributes / API

| Method / Attribute | Purpose |
|-------------------|--------|
| `active_cycle_card` | Reference to pre-built active cycle card widget |
| `summary_table` | Reference to pre-built `QueueSummaryWidget` |
| `elapsed_time_label` | `QLabel` showing “Elapsed: MM:SS” |
| `add_widget_ref(widget, name)` | Add pre-built widgets by reference — avoids recreating them |
| `set_elapsed_time(str)` | Update elapsed display |
| `reset()` | Reset elapsed to `"--:--"` for next run |

### Integration (v2.1)

Will be inserted as the rightmost panel in the Live page `QSplitter`. Visibility toggled by `acquisition_started` / `acquisition_stopped` signals.

---

## Design Consistency

All four panels share the same visual language:

| Token | Value |
|-------|-------|
| Background | `#FFFFFF` (bubble/popup) / `#F5F5F7` (panel) |
| Header background | `#F5F5F7` |
| Border | `1px solid #E5E5EA` |
| Border radius | 14px (bubble/popup) |
| Drop shadow | blur 28–32px, `rgba(0,0,0,55)`, offset (0,6) or (4,4) |
| Accent | `#2E30E3` |
| Muted text | `#86868B` |
| Font | `-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif` |