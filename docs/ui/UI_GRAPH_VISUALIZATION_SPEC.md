# Graph & Data Visualization Spec — Affilabs.core v2.0.5

> **Purpose**: Authoritative reference for every graph in the app — axes, colors, units, update rules, and interaction behavior.
> **Source files**: [`affilabs/widgets/graphs.py`](../../affilabs/widgets/graphs.py), [`affilabs/presenters/sensogram_presenter.py`](../../affilabs/presenters/sensogram_presenter.py), [`affilabs/ui_mixins/_panel_builder_mixin.py`](../../affilabs/ui_mixins/_panel_builder_mixin.py), [`settings/settings.py`](../../settings/settings.py)

---

## Channel Color Palettes

Two palettes exist. The active palette is `ACTIVE_GRAPH_COLORS` in `settings.py`, toggled by the Colorblind Mode checkbox in the Graphic Control sidebar tab.

### Standard Palette (default)

| Channel | Color | Value |
|---------|-------|-------|
| A | Black | `"k"` (pyqtgraph shorthand) |
| B | Red/Pink | `rgb(255, 0, 81)` |
| C | Blue | `rgb(0, 174, 255)` |
| D | Green | `rgb(0, 230, 65)` |

### Colorblind-Friendly Palette (PuOr divergent)

| Channel | Color | Hex |
|---------|-------|-----|
| A | Dark Orange | `#e66101` → `rgb(230, 97, 1)` |
| B | Light Orange | `#fdb863` → `rgb(253, 184, 99)` |
| C | Light Purple | `#b2abd2` → `rgb(178, 171, 210)` |
| D | Dark Purple | `#5e3c99` → `rgb(94, 60, 153)` |

> **Note**: Sensorgram curve colors (above) differ from bar chart/table channel colors (`ui_constants.ChannelColors`). See [UI_DESIGN_SYSTEM.md §2](./UI_DESIGN_SYSTEM.md) for the distinction.

**Toggling**: When user checks "Colorblind mode" in Graphic Control tab, all 4 active curve pens must be updated immediately. `ACTIVE_GRAPH_COLORS` is module-level — update it AND update all existing `PlotDataItem` pens.

---

## Graph 1 — Full Timeline (Sensorgram)

**Widget**: `graphs.py` → main `Graph` class
**Location**: Live page (content_stack index 0), top pane
**Presenter**: `SensogramPresenter`

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Time` | `s` (seconds) |
| Y (left) | `λ` (lambda) | `nm` or `RU` (user-selectable via `UNIT_LIST`) |

Default unit: `RU` (set by `UNIT = "RU"` in `settings.py`). `UNIT_LIST = {"nm": 1, "RU": 355}` — the value is the conversion factor from nm to RU.

### Global PyQtGraph config (set once at startup)

```python
setConfigOptions(antialias=True, useNumba=False, exitCleanup=True, enableExperimental=False)
```

### Visual config

| Property | Value |
|----------|-------|
| Background | White (`#FFFFFF`) |
| Grid | Off by default (`showGrid(x=False, y=False)`) |
| Grid when enabled | `alpha=0.3`, x and y |
| Line width | 2px per channel curve |
| Axis label widths | Left axis: 55px; Bottom axis: 45px |
| Legend | Not shown inline — channel identity via color + checkbox labels above graph |

### Curves

4 `PlotDataItem` curves, one per channel (A, B, C, D), using pens from `ACTIVE_GRAPH_COLORS`. Curve visibility toggled by channel checkboxes above the graph. Performance flags on each curve: `clipToView=True`, `autoDownsample=True`, `skipFiniteCheck=True`, `connect='finite'`.

### Graph header controls (`_create_graph_header()`)

Row above the plot area containing: **Channel toggles A/B/C/D** (with Signal IQ dots), **Baseline stability badge** (`stability_badge`), **Live Data** toggle, **Clear Graph** button.

The stability badge transitions: hidden → grey "Stabilizing…" → green "Ready to inject ✓". It uses a 30-sample rolling buffer of peak wavelengths per channel; all active channels must have p2p ≤ 0.15 nm for at least 20 samples before turning green. Updated via `AL_UIUpdateCoordinator.queue_stability_update()` on the 500ms timer.

### Update rate

| Graph | Rate | Timer |
|-------|------|-------|
| Live sensorgram (full timeline + cycle-of-interest) | **2 Hz** (500ms) from main loop | `QTimer` in `AL_UIUpdateCoordinator` |
| Spectroscopy/transmission popup graphs | **2 Hz** (500ms) | `SETTINGS_SIDEBAR_UPDATE_RATE = 500` in coordinator |

Acquisition may produce data faster than 2 Hz, but the graph only redraws at most 2× per second. Pending updates overwrite — latest data wins, intermediate frames skipped.

**Implementation**: `UIState.pending_graph_updates` dict holds latest (time, spr) per channel. Timer drains and calls `curve.setData()`.

### Max data points

`TIMELINE_MAX_DISPLAY_POINTS = 20000` (≈5.5 hours at 1 Hz). At this limit, oldest data is dropped from the display buffer (not from recording).

Downsampling kicks in above `GRAPH_SUBSAMPLE_THRESHOLD = 10000` points.

### Cursors (cycle-of-interest selection)

Two `InfiniteLine` cursors: **start** and **stop**. Type: `pg.InfiniteLine(angle=90, movable=True)`.

- Dragging start cursor → fires `sigPositionChanged` → `_on_start_cursor_moved()`
- Dragging stop cursor → fires `sigPositionChanged` → `_on_stop_cursor_moved()`
- Cursor positions define the time window shown in the Cycle-of-Interest graph
- `UIState.has_stop_cursor` is cached — check this before accessing the stop cursor object

**Cursor style**: `CYCLE_MARKER_STYLE = "cursors"` (default). Alternatively `"lines"` for vertical markers without drag.

### Y-axis scaling

- Default range: **580–660 nm** (the SPR-active window center)
- **Auto-fit uses 95th percentile** — outlier spikes are ignored for range calculation, not simple `min/max`
- During an active cycle: Y-range is locked (no constant rescaling while cycle runs)
- Downsampling: historical data 1:2500 ratio for navigation; live/recent data gentler (301 pts → 150 pts threshold)

### Cycle shading regions

`pg.LinearRegionItem` drawn behind curves (Z-value −10) for each completed cycle. Color: **light blue** `QColor(100, 100, 255, 70)`. A **warning region** (yellow `QColor(255, 200, 0, 100)`) overlays the last 60 seconds or last 10% of cycle, whichever is smaller, to alert approaching cycle end. Non-movable.

### Event markers

Vertical colored lines for logged events ("Recording Started", pause/resume). Color `#00C853` for Recording Started. Added via `add_event_marker(elapsed_time, label, color)`.

### Injection flags

Vertical markers at the detected injection point per channel. Color matches channel color. Added by `InjectionCoordinator` via `injection_flag_requested` signal → `SensogramPresenter`.

On placement, each new flag marker is briefly animated: size pulses from `size × 2.5` → `size × 1.8` → `size` in 120ms steps (via `_flash_timer` stored on the flag object in `FlagManager.add_flag_marker`).

### Baseline hint label

`_baseline_hint_label`: `QLabel` overlaid on the `full_timeline_graph` widget, positioned bottom-right, transparent to mouse events (`WA_TransparentForMouseEvents`). Text: *"Flat baseline = instrument ready for injection"*. Style: italic, muted grey, 11px.

- **Shown**: on acquisition start (`_on_acquisition_started`)
- **Hidden**: when first injection flag is placed (`flag_manager.add_flag_marker`), or when acquisition stops

### Optics warning state

If optics leak detected: graph background changes to indicate warning (non-white). Restored to `#FFFFFF` when optics cleared. Implemented in `_device_status_mixin.py`.

---

### Cursors

Two `InfiniteLine` objects (angle=90°, movable=True). **Hidden by default** in v2.0.5 (deprecated for live sensorgram; still active in Cycle Review dialog). When visible:
- Normal: 3px thick, dark gray `#333333`
- Hover: 5px thick, lighter gray `#666666`
- Start cursor label: 4% from left, offset above line; white background `rgba(255,255,255,220)`
- Stop cursor label: 95% from right, offset to right

## Graph 2 — Cycle-of-Interest (Active Cycle Detail)

**Widget**: `graphs.py` → `CycleDetailGraph` or secondary `Graph` instance
**Location**: Live page, bottom pane
**Presenter**: `SensogramPresenter`

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Time` | `s` (relative to cycle start) |
| Y (left) | `λ` or `Δ SPR` | `nm` or `RU` |

### Behavior

- Shows only the time window between start and stop cursors on the full timeline graph
- Updates whenever cursor positions change or new data arrives within the cursor window
- X-axis padding: `CYCLE_AXIS_PADDING = 0.1` (10% padding on each side) — defined in `UIStyle`
- Default Y-range: **−5 to +10** (RU or nm) — minimum Y-span of 10 enforced to prevent over-zoomed views
- During active cycle: fixed window 0 → `cycle_duration × 1.1` (slight overshoot for context)
- Crosshair cursor: yellow dashed vertical + horizontal lines, coordinate label in upper-left corner
- Per-channel dissociation/association cursor lines (vertical, with labels) for phase marking
- Downsampling: threshold 1001 pts → 500 pts (gentler than full timeline — preserves kinetics detail)

### Channel visibility

Controlled by separate channel buttons above this graph (styled with `get_active_cycle_channel_button_style(color)` — less rounded, grayer inactive state). Each button shows only that channel's curve: `curve.setVisible(idx == selected_idx)`.

---

## Graph 3 — Spectroscopy / Transmission Spectrum

**Widget**: Popup window (opened from Graphic Control tab)
**Presenter**: `SpectroscopyPresenter`

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Wavelength` | `nm` |
| Y (left) | `Transmission` | `%` |

### What's plotted

P/S ratio spectrum per channel, after dark subtraction and normalization. Shows the SPR dip (minimum in transmission) in the 560–720 nm range.

### Update rule

Updates on each processed spectrum frame. Throttled same as sensorgram (10 Hz max). Both P-pol and S-pol spectra can be toggled for display.

---

## Graph 4 — Raw Spectrum

**Widget**: Same popup as transmission or separate popup
**Presenter**: `SpectroscopyPresenter`

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Wavelength` | `nm` |
| Y (left) | `Counts` | (raw ADC counts) |

### What's plotted

Raw detector counts (no dark subtraction) per LED channel and polarization. Used for diagnostics — shows saturation, LED intensity, dark noise level.

---

## Graph 5 — Edits Tab Primary Graph

**Widget**: `pg.PlotWidget()` created in `_panel_builder_mixin.py:113`
**Location**: Edits tab, right pane

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Time` | `s` |
| Y (left) | `Response` | `RU` |

### Visual config

```python
self.edits_primary_graph.setBackground('w')
self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.3)
self.edits_primary_graph.setLabel('left', 'Response (RU)')
self.edits_primary_graph.setLabel('bottom', 'Time (s)')
```

Grid is **always on** in Edits tab (unlike Live tab where it is user-toggled).

### What's plotted

Selected cycle(s) from the cycle table, overlaid. Multiple cycles can be shown at once (overlay mode). Reference traces occupy 3 dedicated slots. Time axis is relative to cycle start (not absolute experiment time).

### Reference subtraction

When ref subtraction is enabled (`ChannelState.ref_subtraction_enabled = True`), the selected reference channel data is subtracted from all others before display. Y-axis label changes to `Δ Response (RU)`.

---

## Graph 6 — Edits Tab Delta-SPR Bar Chart

**Widget**: Inline bar chart in Edits tab alignment panel
**Location**: Edits tab, below primary graph or in alignment section

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | Channel | A, B, C, D |
| Y (left) | `Δ SPR` | `nm` or `RU` |

### What's plotted

The SPR shift (Δλ) measured between alignment reference point and cursor position, per channel. Used to quantify binding signal.

### Colors

Per-channel bars use `ChannelColors.MAP`: A=#007AFF, B=#FF9500, C=#34C759, D=#AF52DE (iOS palette, not the sensorgram curve palette).

---

## Graph 7 — Delta-SPR Overlay (Live Page)

**Widget**: `DeltaSPROverlay` ([`affilabs/widgets/delta_spr_overlay.py`](../../affilabs/widgets/delta_spr_overlay.py))
**Location**: Overlaid on Live page sensorgram
**Visibility**: Only when alignment reference is set in Edits tab

### Axes

| Axis | Label | Unit |
|------|-------|------|
| X (bottom) | `Time` | `s` |
| Y (left) | `Δ SPR` | `nm` or `RU` |

Shows real-time biosensing measurement: current Δλ per channel relative to alignment baseline. Updates on every processed frame.

---

## Standard Graph Setup Pattern

When creating any new graph in the app, follow this pattern:

```python
import pyqtgraph as pg

graph = pg.PlotWidget()
graph.setBackground('w')                          # Always white
graph.showGrid(x=True, y=True, alpha=0.3)         # Grid on for data graphs
graph.setLabel('left', 'Y Label', units='unit')   # Always label axes
graph.setLabel('bottom', 'X Label', units='unit')

# Channel curves
for ch, color in ACTIVE_GRAPH_COLORS.items():
    pen = pg.mkPen(color=color, width=2)
    curve = graph.plot([], [], pen=pen, name=f"Ch {ch.upper()}")
    curves[ch] = curve
```

**Rules**:
1. Background is always white — never dark theme
2. Axes must always have labels and units — never leave unlabeled
3. Legend is not used — channel identity is communicated via color + adjacent UI controls
4. Grid default: **off** for Live sensorgram (user toggleable), **on** for Edits and popup graphs
5. `ACTIVE_GRAPH_COLORS` not `GRAPH_COLORS` — respects colorblind toggle
6. Never call `curve.setData()` from a background thread — always via presenter on main thread

---

## Axis Units & Conversion

The app supports two Y-axis units:

| Unit | Display | Conversion |
|------|---------|-----------|
| `nm` | Raw resonance wavelength | 1:1 from pipeline output |
| `RU` | Resonance Units (scaled) | multiply nm by `355` |

`UNIT_LIST = {"nm": 1, "RU": 355}` in `settings.py`.

Default is `RU`. Unit selector is in the channel menu / sidebar. Changing units requires re-scaling all existing curve data — do not just change the label.

---

## Update Throttling Architecture

```
Spectrum arrives (background thread)
  │
  ▼
spectrum_acquired signal → QueuedConnection → main thread
  │
  ▼
_on_spectrum_acquired() → puts into _spectrum_queue (non-blocking)
  │
  ▼
Processing worker thread drains queue
  → SpectrumProcessor → pipeline → wavelength value
  │
  ▼
UIState.pending_graph_updates[channel] = (time_data, spr_data)
  │
  ▼
QTimer (500ms) → _process_pending_ui_updates()
  → curve.setData(time_data, spr_data)   ← ONLY here, ONLY main thread
```

**Key rules**:
- `curve.setData()` is the ONLY allowed graph write call — never `addItem`, `clear`, manual point manipulation
- The 100ms timer is the single choke point — no graph update may bypass it
- `UIState.skip_graph_updates = True` pauses all graph writes (used during calibration)

---

## What NOT to Do

| Anti-pattern | Correct approach |
|-------------|-----------------|
| Call `curve.setData()` from a background thread | Always via timer on main thread |
| Use `GRAPH_COLORS` directly | Use `ACTIVE_GRAPH_COLORS` (respects colorblind toggle) |
| Leave axes unlabeled | Always set left and bottom labels with units |
| Use dark background | `setBackground('w')` — always white |
| Update graph at acquisition rate (1+ Hz) | Batch through `pending_graph_updates`, drain at 2 Hz (500ms timer) |
| Set Y range without checking auto-range mode | Check `UIState.skip_graph_updates` / auto-range setting first |
| Use integers for channel colors | Use pyqtgraph pen objects (`pg.mkPen(color, width=2)`) |
