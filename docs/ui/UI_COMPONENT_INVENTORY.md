# UI Component Inventory & Interaction Rules — Affilabs.core v2.0.5

> **Purpose**: Single reference for every screen, tab, widget, and the rules that govern their behavior.
> **Design rules**: See [`UI_DESIGN_SYSTEM.md`](./UI_DESIGN_SYSTEM.md).
> **Architecture**: See [`../architecture/UI_ARCHITECTURE.md`](../architecture/UI_ARCHITECTURE.md).

---

## Table of Contents

1. [Application Shell](#1-application-shell)
2. [Main Content Pages](#2-main-content-pages)
3. [Sidebar Tabs](#3-sidebar-tabs)
4. [Reusable Widgets](#4-reusable-widgets)
5. [Dialogs](#5-dialogs)
6. [Presenters (View Coordination)](#6-presenters-view-coordination)
7. [Interaction State Rules](#7-interaction-state-rules)
8. [Adding New UI Components](#8-adding-new-ui-components)

---

## 1. Application Shell

### `AffilabsMainWindow`
**File**: [`affilabs/affilabs_core_ui.py`](../../affilabs/affilabs_core_ui.py) + mixins in [`affilabs/ui_mixins/`](../../affilabs/ui_mixins/)

**Layout**: `QMainWindow` → `QSplitter` → [Content Area | Sidebar]

#### 1.1 Toolbar Redesign — `TransportBar` (v2.1)

> **Replaces** the legacy `QToolBar` with a 56px horizontal strip widget at the top of the main window.
> **FRS**: [`docs/features/TRANSPORT_BAR_FRS.md`](../features/TRANSPORT_BAR_FRS.md)

**File**: [`affilabs/widgets/transport_bar.py`](../../affilabs/widgets/transport_bar.py)

**Layout zones** (left → right):

| Zone | Contents | Width |
|------|----------|-------|
| Logo | `AffiLabs` wordmark label | Fixed |
| Nav pills | Live / Edits / Analyze / Report | Stretch |
| Method button | Blue "Build Method" pill | Fixed |
| Stretch | — | Fills |
| Sparq toggle | Robot SVG icon button | Fixed |
| Pause | Checkable pause button | Fixed |
| Record | Checkable record button | Fixed |
| Power | Checkable connect button | Fixed |

**Button aliasing** — TransportBar wires all buttons directly onto `main_window.*` for backward compat:
- `main_window.power_btn` → TransportBar power button
- `main_window.record_btn` → TransportBar record button
- `main_window.pause_btn` → TransportBar pause button
- `main_window.spark_toggle_btn` → TransportBar Spark button

**Hidden compat widgets** (invisible, kept for signal wiring that still references them):
- `main_window.recording_indicator`, `main_window.rec_status_dot`
- `main_window.connecting_label`
- `main_window.timer_btn` (stub `TimerButton` — actual timer is in `RailTimerPopup`)

**States** (same as legacy toolbar — see §7):

| Element | States | Rule |
|---------|--------|------|
| Power | `disconnected` / `searching` / `connected` | Disabled during calibration |
| Record | enabled / disabled / recording | Disabled until calibration completes |
| Pause | enabled / disabled / paused | Disabled until acquisition starts |

#### 1.2 Icon Rail — `IconRail` (v2.1)

> **Replaces** the built-in `QTabBar` of `AffilabsSidebar` with a 48px vertical strip widget.
> **FRS**: [`docs/features/TRANSPORT_BAR_FRS.md`](../features/TRANSPORT_BAR_FRS.md)

**File**: [`affilabs/widgets/icon_rail.py`](../../affilabs/widgets/icon_rail.py)

**Layout zones** (top → bottom):

| Zone | Contents |
|------|----------|
| Top | `A` monogram logo button |
| Tab buttons | Device Status / Method / Flow / Export / Settings |
| Stretch | — |
| Utilities | Spectrum toggle, Timer toggle |

**Tab click logic**:

| State | Same tab clicked | Different tab clicked |
|-------|------------------|-----------------------|
| Sidebar collapsed | Expand + switch to tab | Expand + switch to tab |
| Sidebar expanded | Collapse sidebar | Switch to tab (stay expanded) |

**API**:
- `set_sidebar(sidebar)` — connects rail to `AffilabsSidebar` instance
- `show_flow_tab(visible: bool)` — shows/hides Flow tab button (hidden for P4SPR)

**Utility buttons**:
- **Spectrum** → toggles `SpectrumBubble` floating panel
- **Timer** → toggles `RailTimerPopup` floating panel

**Icon style**: 20px SVG icons; active tab = `#2E30E3` (accent blue); inactive = `#86868B` (muted grey); hover = `#1D1D1F` (dark text)

#### Status Bar

| Element | Purpose | Update trigger |
|---------|---------|----------------|
| Connection status label | Hardware link state | `HardwareManager.hardware_connected/disconnected` |
| Acquisition status label | "⚫ Idle" / "🔴 Acquiring..." / "⏸️ Paused" | `DataAcquisitionManager.acquisition_started/stopped` |

#### Splitter

- Left pane: content area (main graphs / tabs)
- Right pane: sidebar
- User can drag to resize — **never use `setFixedWidth()` on either pane**
- Minimum window: 1400 × 800

#### Sidebar Footer Strip

**Attribute**: `spark_hint` QFrame on `AffilabsSidebar`
**Location**: Fixed 36px strip below `tab_widget`, always visible
**Content**: `spark_hint_label` — "💬 Ask Spark AI — click the robot icon for help"
**Style**: `rgba(46, 48, 227, 0.06)` background; `border-top: 1px solid rgba(46,48,227,0.15)`; 11px font; `color: rgba(46,48,227,0.75)`
**Purpose**: Discovery hint so users know Spark exists even when the panel is closed

---

## 2. Main Content Pages

Managed by `QStackedWidget` (`content_stack`). Navigation via `NavigationPresenter`.

| Index | Name | Builder | Default visibility |
|-------|------|---------|-------------------|
| 0 | **Live** (Sensorgram) | `_create_sensorgram_placeholder()` | Visible at startup |
| 1 | **Edits** | `EditsTab.create_content()` | Accessible via nav |
| 2 | **Analyze** | `_create_analyze_content()` | Hidden (nav button disabled) |
| 3 | **Report** | `_create_report_content()` | Hidden (nav button disabled) |

### Page 0 — Live Sensorgram

**Components**:
- Full timeline graph (top) — all channels, full experiment duration
- Cycle-of-interest graph (bottom) — current active cycle, all channels

**Graph interaction rules**:
- Channel visibility toggled by checkboxes above each graph
- Cursor markers (start/stop) are draggable — drag fires `sigPositionChanged`
- Right-click → context menu (zoom reset, add flag, send to edits)
- Mouse click on cycle-of-interest graph → `scene().sigMouseClicked` → injection flag candidate
- **Never update graphs directly from a background thread** — always via signal → presenter → `curve.setData()`

**Conditional display**:
- Delta-SPR overlay (`DeltaSPROverlay`) appears only when alignment is set in Edits tab
- Injection flags render as vertical markers — added by `InjectionCoordinator`
- Cycle shading (colored background regions) — added by `SensogramPresenter`

**Display row** (below title bar; `timing_row` layout; only present in the Active Cycle graph pane, `show_delta_spr=True`):

| Widget | Attribute | Purpose | Visibility |
|--------|-----------|---------|------------|
| "Display:" label | — | Section label | Always |
| Channel toggles A/B/C/D | `channel_toggles[ch]` | Toggle visibility on both graphs | Always |
| Notes button | `cycle_note_btn` | Open cycle notes floating popup | **Always visible** (changed from v2.0.4 where it was hidden until a cycle started) |

**Active Cycle graph overlay widgets** (child `QWidget`s of `cycle_of_interest_graph` PlotWidget, positioned absolutely):

| Widget | Class | Attribute | Position | Visibility |
|--------|-------|-----------|----------|------------|
| IQ/value legend | `InteractiveSPRLegend` | `plot.interactive_spr_legend` | Top-left `(62, 10)` | Always visible; IQ `●` dots update live from `ui_update_coordinator._update_sensor_iq_displays()` |
| Cycle status | `CycleStatusOverlay` | `plot.cycle_status_overlay` | Top-right (auto right-anchored) | Hidden until cycle starts; `transparent_for_mouse_events=True` — does not block graph interaction |

`CycleStatusOverlay` shows: cycle type, cycle index (`N / total`), countdown `MM:SS` (turns orange at ≤10 s), and next-cycle label. Hidden by `_on_cycle_completed()`. Re-anchors to right edge on every 1-second tick to handle window resize.

**Graph header widgets** (row above `full_timeline_graph`, built by `_create_graph_header()`):

| Widget | Attribute | Purpose |
|--------|-----------|---------|
| Channel toggles A/B/C/D | `channel_toggles[ch]` | Show/hide channels; checkable |
| Baseline stability badge | `stability_badge` | Grey "Stabilizing…" → green "Ready to inject ✓" when all active channels p2p ≤ 0.15 nm for 30 samples; hidden when not acquiring |
| Live Data toggle | `live_data_btn` | Enables/disables auto-scroll of sensorgram cursor |
| Clear Graph button | `clear_graph_btn` | Resets all graph data |

> **Removed (v2.0.5)**: Signal IQ dots that were overlaid on the A/B/C/D channel toggle buttons (`sensor_iq_badges[ch]`). IQ quality is now shown via the colored `●` dots inside `InteractiveSPRLegend` in the Active Cycle graph.

**Baseline hint label** (`_baseline_hint_label`): `QLabel` overlaid on `full_timeline_graph`, bottom-right corner, transparent to mouse events. Text: "Flat baseline = instrument ready for injection". Shown on acquisition start, hidden on first injection flag placed.

---

### Page 1 — Edits Tab

**File**: [`affilabs/tabs/edits_tab.py`](../../affilabs/tabs/edits_tab.py) + mixins in [`affilabs/tabs/edits/`](../../affilabs/tabs/edits/)

**Layout**: Two-panel split — cycle table (left) + detail graph (right)

**Components**:
- `QTableWidget` — cycle list with type, duration, start/stop timestamps
- Detail graph — selected cycle overlay view
- Export toolbar (Excel, CSV)
- Alignment controls (`_alignment_mixin.py`)
- Segment creator

**Edits interaction rules**:
- Selecting a cycle in table → updates detail graph immediately
- Multi-select allowed — exports all selected cycles
- Cycle type is editable inline via delegate (`delegates.py`)
- Double-click cycle → opens `CycleTableDialog` for full metadata edit
- Alignment reference is set by clicking a point on the detail graph
- Edits tab data comes from `RecordingManager` — it does not read from hardware

---

## 3. Sidebar Tabs

**Container**: `AffilabsSidebar` ([`affilabs/affilabs_sidebar.py`](../../affilabs/affilabs_sidebar.py))
**Pattern**: Each tab is built by a dedicated `*Builder` class in [`affilabs/sidebar_tabs/`](../../affilabs/sidebar_tabs/)

### Tab 0 — Device Status
**Builder**: [`AL_device_status_builder.py`](../../affilabs/sidebar_tabs/AL_device_status_builder.py)

| Section | Content | Update source |
|---------|---------|--------------|
| Controller | Firmware version, COM port, LED state | `HardwareManager.status_dict` |
| Detector | Model, serial number, integration time | `HardwareManager.status_dict` |
| Pump | Type, connection, valve state | `HardwareManager.status_dict` |
| Subunit health | Sensor IQ / Optics / Fluidics ✅/❌ | `CalibrationService` + hardware events |

**Rules**:
- All indicators update via `_device_status_mixin.py` on `hardware_connected` signal
- Never directly poll hardware from this tab — read from the status dict
- Subunit indicators are read-only (display only, no controls)

---

### Tab 1 — Method
**Builder**: [`AL_method_builder.py`](../../affilabs/sidebar_tabs/AL_method_builder.py)

> **Note**: The "Graphic Control" tab was removed from the tab bar (content moved to Settings → Display Controls). Tab indices shifted: Method=1, Flow=2, Export=3, Settings=4.

**Layout top-to-bottom**:

| Section | Components | Visibility |
|---------|-----------|------------|
| **Build Method CTA** | Full-width 48px blue `QPushButton` ("Build Method"), icon + label | Always visible |
| **Active Cycle Card** | Blue-tinted card: cycle type badge, cycle index, countdown timer, next-cycle preview, total experiment time remaining | **Only when a cycle is running** |
| **Queue table** | `QueueSummaryWidget` — drag-to-reorder, highlights running cycle | Always |
| **Queue controls** | Start Run (green), Duplicate (orange), Next Cycle (blue) | Always; Next disabled when no cycle running |
| **Retrieve Method** | `↻ Retrieve Method` button | **Only after queue completes** |

**Active Cycle Card** (`sidebar.active_cycle_card`):

| Label | Attribute | Content |
|-------|-----------|---------|
| Cycle type badge | `active_cycle_type_label` | e.g. "Binding" — blue pill |
| Cycle index | `active_cycle_index_label` | e.g. "Cycle 1/4" — grey |
| Countdown | `active_cycle_countdown_label` | Remaining time MM:SS — blue; turns orange at <10s |
| Next cycle | `active_next_cycle_label` | e.g. "Next: Wash" — orange; hidden when queue empty |
| Experiment time | `active_experiment_time_label` | Total remaining across all queued cycles |

Update path: `_cycle_timer` (1s) → `_update_cycle_display()` → card labels
Show/hide: shown by `_update_cycle_display()` on first tick; hidden by `_on_cycle_completed()` when queue exhausted and by `_on_acquisition_stopped()`

**Rules**:
- "Build Method" button is the **first interactive element** in this tab — opens `MethodBuilderDialog` non-modally (`show()` not `exec()`)
- "Start Run" is disabled when: no cycles in queue, not calibrated, or acquisition already running
- "Next Cycle" skips to next cycle in queue immediately (no confirm)
- Drag reorder in `QueueSummaryWidget` updates queue order in `QueueManager`
- After calibration completes (QC dialog dismissed), sidebar **auto-switches** to this tab so "Build Method" is immediately visible
- Intel bar labels (`intel_status_label`, `intel_message_label`) still exist as **hidden** widgets for backward compat — they are not rendered

---

### Tab 2 — Flow
**Builder**: [`AL_flow_builder.py`](../../affilabs/sidebar_tabs/AL_flow_builder.py)

| Section | Components | Visibility |
|---------|-----------|------------|
| Pump controls | Flow rate, volume, prime button | Always visible |
| Valve controls | Load/Inject toggle (6-port), waste/load (3-way) | Only P4PRO / P4PROPLUS |
| Internal pump | On/Off, preset flow rate | Only P4PROPLUS |
| Queue | Same `QueueSummaryWidget` as Method tab | Always |

**Rules**:
- Internal pump UI toggled by `_update_internal_pump_visibility()` — checks `'p4proplus' in firmware_id`
- 6-port valve position changes must be confirmed if acquisition is active
- Flow rate field: minimum 5 µL/min, maximum 100 µL/min — validated on input, not on submit
- P4PROPLUS pump: minimum contact time = 180s at 25 µL/min (enforced by firmware; warn in UI before starting)
- AffiPump volume and flow rate fields are disabled when pump is not connected

---

### Tab 3 — Export
**Builder**: [`AL_export_builder.py`](../../affilabs/sidebar_tabs/AL_export_builder.py)

| Control | Widget | Rule |
|---------|--------|------|
| Format | Segmented (Excel / CSV / JSON) | Default: Excel |
| Channels | 4× `QCheckBox` A/B/C/D | At least 1 must be checked before export enabled |
| Export scope | Combo (All cycles / Selected / Current) | Disabled when Edits tab is not loaded |
| Destination | `QLineEdit` + Browse button | Path validated on browse; export disabled if path invalid |
| User profile | `QComboBox` | Populated from `UserProfileManager` |
| Export button | `QPushButton` | Disabled until: destination set + at least 1 channel + data exists |

**Rules**:
- Export runs in a background thread — button shows progress state during export
- Never block the UI during file write
- On success: show path in status bar; on failure: `StyledMessageDialog` with error detail

---

### Tab 4 — Settings
**Builder**: [`AL_settings_builder.py`](../../affilabs/sidebar_tabs/AL_settings_builder.py)

| Section | Controls |
|---------|---------|
| Detector | Profile selector (Flame-T / USB4000), integration time |
| Convergence | Target intensity range, iteration limits |
| Servo | P-pol / S-pol position (degrees), settle time |
| User profiles | List, Rename, Set Active, Create New |
| Advanced | Opens `AdvancedSettingsDialog` |

**Rules**:
- Integration time has a **minimum of 4.5ms** — enforced in settings and in `usb4000_wrapper.py`
- Servo position changes take effect immediately if hardware is connected
- User rename is inline — double-click to edit, Enter to confirm
- Active user is highlighted with ★ bold text
- Settings tab accessible during acquisition (no lockout) but hardware changes warn first

---

### Spark AI Panel
**Widget**: [`affilabs/widgets/spark_sidebar.py`](../../affilabs/widgets/spark_sidebar.py) → contains `SparkHelpWidget`

> **Not a sidebar tab** — Spark is a separate `QWidget` in the main `QSplitter` (left pane). It is toggled by the robot-icon button (`spark_toggle_btn`) in the nav bar.

| Element | Behavior |
|---------|---------|
| Conversation view | Scrollable Q&A bubble list |
| Input field | `QLineEdit`, Enter sends query |
| Voice toggle (🔊) | TTS on/off — **default: OFF** |
| Feedback buttons | 👍/👎 per answer — logged for improvement |

**Default state**: **Hidden** (`spark_toggle_btn.setChecked(False)` at startup). Users open on demand.

**Discovery**: Sidebar footer strip ("💬 Ask Spark AI — click the robot icon for help") is always visible at the bottom of the sidebar, pointing users to the nav bar toggle.

**Rules**:
- Answer generation is always on a background thread — UI never blocks
- If answer generation fails, show a graceful fallback: "I couldn't find an answer. Try rephrasing."
- TTS disabled by default (`spark_help_widget.py`)
- All Spark entry points wrapped in try/except — Spark failure must never crash the main app
- `switch_to_spark_tab()` on sidebar is a no-op stub kept for backward compat

---

## 4. Reusable Widgets

### Signal IQ Dots
**Attribute**: `sensor_iq_{ch}_diag` (e.g. `sensor_iq_a_diag`) on `AffilabsMainWindow`; also collected in `sensor_iq_badges` dict
**Location**: Overlaid bottom-right corner of each channel toggle button in the graph header
**Size**: 7×7px colored square (`border-radius: 3px`)
**Colors**: green (`#34C759`) = good, amber (`#FF9500`) = questionable, red (`#FF3B30`) = poor, neutral = no data yet
**Update path**: `main.py:_on_peak_updated` → `spectrum_helpers.classify_spr_quality` → `app._update_sensor_iq_display` → `ui_updates.queue_sensor_iq_update` → `AL_UIUpdateCoordinator._update_sensor_iq_displays` (500ms timer)
**Metrics used** (4-check cascade, worst result wins): wavelength zone → FWHM → dip depth → baseline noise (p2p)
**Rules**: Dot hidden when channel is toggled off. Tooltip shows full detail. No text on dot — color only.

### Baseline Stability Badge
**Attribute**: `stability_badge` on `AffilabsMainWindow`
**Location**: Graph header row, left of "Live Data" toggle
**States**: hidden (not acquiring) → grey "Stabilizing…" → green "Ready to inject ✓"
**Stability threshold**: all active channels have p2p ≤ 0.15 nm over last 30 peak values (~30s at 1 Hz)
**Minimum samples**: 20 samples required before judging (avoids premature green at startup)
**Update path**: `main.py:_on_peak_updated` → rolling buffer → `ui_updates.queue_stability_update` → `AL_UIUpdateCoordinator._update_stability_badge` (500ms timer)
**Reset**: hidden and buffers cleared on `_on_acquisition_stopped`

### `QueueSummaryWidget`
**File**: [`affilabs/widgets/queue_summary_widget.py`](../../affilabs/widgets/queue_summary_widget.py)

- Drag-to-reorder `QTableWidget`
- Columns: Type (colored badge), Duration, Comment
- Used in: Method tab, Flow tab (same widget class, different queue instance)
- Rules: Reorder fires `QueueManager.reorder()`; delete key removes selected rows with confirm

### `CollapsibleBox`
**File**: [`affilabs/widgets/collapsible_box.py`](../../affilabs/widgets/collapsible_box.py)

- Toggle button header + animated content area
- Header style: `collapsible_header_style()` from `ui_styles.py`
- Rules: Collapsed state persists within session (not across restarts). Default = expanded.

### `CycleControlsWidget`
**File**: [`affilabs/widgets/cycle_controls_widget.py`](../../affilabs/widgets/cycle_controls_widget.py)

- Cycle type selector + time selector
- Type combo populated from `CycleConfig.TYPES`
- Time dropdown enabled/disabled by `CycleConfig.is_time_enabled(type)`
- Rules: Changing type resets time to `CycleConfig.get_default_time(type)`

### `TimerButton`
**File**: [`affilabs/widgets/timer_button.py`](../../affilabs/widgets/timer_button.py)

- Shows countdown + cycle info
- Animated: `AnimatedTimerDisplay` widget for rolling numbers
- Rules: Timer starts when cycle starts, counts down to zero. On completion: fires cycle-end event.

### ~~`IntelligenceBar`~~ (removed from Method tab)
**File**: [`affilabs/widgets/intelligence_bar.py`](../../affilabs/widgets/intelligence_bar.py)

> **Deprecated in v2.0.5**: The inline intelligence bar in the Method tab was replaced by the **Active Cycle Card** (see Tab 1 — Method). The `intel_status_label` and `intel_message_label` attributes still exist on the sidebar as hidden widgets for backward compat with `_refresh_intelligence_bar()` in `affilabs_core_ui.py`, but they are not rendered.

### `DeltaSPROverlay`
**File**: [`affilabs/widgets/delta_spr_overlay.py`](../../affilabs/widgets/delta_spr_overlay.py)

- Real-time biosensing measurement display overlay on Live graph
- Visible only when alignment reference is set
- Shows current Δλ (nm) per channel

### `InteractiveSPRLegend`
**File**: [`affilabs/widgets/interactive_spr_legend.py`](../../affilabs/widgets/interactive_spr_legend.py)

- `QWidget` child of `cycle_of_interest_graph` PlotWidget; positioned top-left `(62, 10)` via `_position_active_cycle_legend()`
- Shows per-channel `●` IQ dot (live color from `ui_update_coordinator`) + Δ SPR value + click-to-toggle visibility
- Always visible (set on startup, not hidden at idle)
- `set_iq_color(channel, hex_color)` — called by coordinator on each IQ update
- `update_values(delta_values: dict)` — called by `_acquisition_mixin._update_delta_display()`

### `CycleStatusOverlay`
**File**: [`affilabs/widgets/cycle_status_overlay.py`](../../affilabs/widgets/cycle_status_overlay.py)

- `QWidget` child of `cycle_of_interest_graph` PlotWidget; positioned top-right (auto right-anchored with 10px margin on every `update_status()` call)
- `WA_TransparentForMouseEvents=True` — never blocks graph interaction
- **Hidden at startup**; shown on first `update_status()` call from `_update_cycle_display()`; hidden by `clear()` from `_on_cycle_completed()`
- Displays: cycle type label, "N / total" index, `MM:SS` countdown (blue → orange at ≤10 s), optional next-cycle name

### `SparkHelpWidget`
**File**: [`affilabs/widgets/spark_help_widget.py`](../../affilabs/widgets/spark_help_widget.py)

- Full Spark AI Q&A panel
- Embeds within `spark_sidebar.py`
- TTS toggle stored as `self.tts_enabled` (default: `False`)

### `PipelineSelector`
**File**: [`affilabs/widgets/pipeline_selector.py`](../../affilabs/widgets/pipeline_selector.py)

- Dropdown to select peak-finding algorithm: centroid / fourier / polynomial / hybrid / consensus
- Appears in settings or spectroscopy view
- Rules: Changes take effect on next processed frame — no retroactive reprocessing

### `CalibrationQCDialog`
**File**: [`affilabs/widgets/calibration_qc_dialog.py`](../../affilabs/widgets/calibration_qc_dialog.py)

- 4-graph layout: S-pol spectrum (top-left), P-pol spectrum (top-right), combined QC metrics table (bottom-left), notes panel (bottom-right)
- **QC metrics table**: per-channel rows — Dip Depth, Dip FWHM, Noise, Conv Iter — all in plain text (no color coding)
- **Notes panel**: 5 fixed reminders for the user:
  - ⚠ Dry sensor produces no usable data
  - ♻ Reused sensor chips often fail QC
  - ✗ Unused channels show poor metrics — expected, not a fault
  - ⊘ Dip depth < 50% on new chip → check fiber and flow cell seating
  - ~ QC pass ≠ stable data; watch baseline drift in first 5 min
- Opened automatically after calibration completes
- Non-modal — user can dismiss and continue
- **After dismissal**: sidebar auto-switches to Method tab so "Build Method" is immediately visible

### `DeviceStatus`
**File**: [`affilabs/widgets/device_status.py`](../../affilabs/widgets/device_status.py)

- Grayscale-themed hardware status panel
- Shows controller / detector / pump state with dot indicators
- Reads from `HardwareManager.status_dict`

---

### Floating / Overlay Panels (v2.1)

> **FRS**: [`docs/features/FLOATING_PANELS_FRS.md`](../features/FLOATING_PANELS_FRS.md)
> All floating panels are frameless child `QWidget`s or `QFrame`s parented to the main window. They overlay content without consuming layout space.

#### `SpectrumBubble`
**File**: [`affilabs/widgets/spectrum_bubble.py`](../../affilabs/widgets/spectrum_bubble.py)

- 310×380px floating spectroscopy panel — bottom-left of main window (above transport bar)
- Triggered by **Spectrum** button on `IconRail`
- Two tabs: **Transmission** (normalised P/S ratio) / **Raw** (raw counts)
- Draggable via header drag handle
- **Public attributes** (also aliased on `main_window`):
  - `transmission_plot` — pyqtgraph `PlotWidget`
  - `transmission_curves` — list of 4 `PlotDataItem` (one per channel)
  - `raw_data_plot` — pyqtgraph `PlotWidget`
  - `raw_data_curves` — list of 4 `PlotDataItem`
  - `baseline_capture_btn` — `QPushButton` ("Capture 5-Min Baseline")
- **API**: `toggle()`, `reposition()` (call from `resizeEvent`)
- Drop shadow: `blurRadius=32`, `offset=(0, 6)`, `alpha=55`
- Close button → hides panel + unchecks `main_window.spectrum_toggle_btn`

#### `RailTimerPopup`
**File**: [`affilabs/widgets/rail_timer_popup.py`](../../affilabs/widgets/rail_timer_popup.py)

- 240×250px countdown timer popup — bottom-left of main window, above `SpectrumBubble`
- Triggered by **Timer** button on `IconRail`
- Flags: `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- **Signals**: `timer_started`, `timer_finished(int elapsed_s)`
- **4-state machine**:

| State | Display | Controls |
|-------|---------|----------|
| `idle` | Time picker + preset chips (5 / 10 / 15 / 30 min) | Start button |
| `running` | `MM:SS` countdown, progress ring | Pause, Stop |
| `paused` | `MM:SS` frozen | Resume, Stop |
| `finished` | "Time's up!" — alert blink | Reset button |

- Alert on finish: title bar blinks `#FF3B30` (red) × 5 via `QTimer`
- Preset chips: quick-set 5 / 10 / 15 / 30 min
- Draggable via header; repositions on parent `resizeEvent`

#### `LiveContextPanel` *(v2.1 stub — not wired)*
**File**: [`affilabs/widgets/live_context_panel.py`](../../affilabs/widgets/live_context_panel.py)

- 230px left panel for the Live page — Phase 3 of sidebar redesign
- Will replace `SpectrumBubble` by moving spectroscopy plots inline into the Live page left rail
- Currently a minimal stub (`QFrame`, no plot widgets wired yet)
- **Do not wire signals or call `update_*` methods** until Phase 3 is implemented

#### `LiveRightPanel` *(v2.1 stub — not wired)*
**File**: [`affilabs/widgets/live_right_panel.py`](../../affilabs/widgets/live_right_panel.py)

- 220px right panel for the Live page — Phase 2 of sidebar redesign
- Shows: active cycle card, queue summary, elapsed time
- Currently a minimal stub with `add_widget_ref(name, widget)` API for future wiring
- **Do not wire signals or call `update_*` methods** until Phase 2 is implemented

---

## 5. Dialogs

All dialogs lazy-loaded (created on first access, then cached). Use `show()` for non-modal, `exec()` only for blocking flows (confirmations).

| Dialog | File | Modal | Trigger |
|--------|------|-------|---------|
| `MethodBuilderDialog` | `widgets/method_builder_dialog.py` | No | "Build Method" button in Method tab |
| `CycleTemplateDialog` | `widgets/cycle_template_dialog.py` | No | "Templates" button |
| `CycleTableDialog` | `widgets/cycle_table_dialog.py` | No | Double-click cycle in Edits tab |
| `CalibrationQCDialog` | `widgets/calibration_qc_dialog.py` | **Yes** (`exec()`) | Auto-shown after calibration |
| `QCHistoryDialog` | `widgets/qc_history_dialog.py` | No | "View History" in Device Status |
| `KaKdWizard` | `widgets/ka_kd_wizard.py` | No | Kinetics button in Analysis tab |
| `KdWizard` | `widgets/kd_wizard.py` | No | Dissociation fit button |
| `QueuePresetDialog` | `widgets/queue_preset_dialog.py` | No | "Presets" button in Method tab |
| `AdvancedSettingsDialog` | `widgets/advanced.py` | No | "Advanced" button in Settings tab |
| `PopoutTimerWindow` | `widgets/popout_timer_window.py` | No | Detach timer button |
| `LicenseDialog` | `widgets/license_dialog.py` | No | Help menu |
| `PrimePumpWidget` | `widgets/prime_pump_widget.py` | No | Prime button in Flow tab |
| `StyledMessageDialog` | `widgets/styled_message_dialog.py` | Yes (exec) | Errors, warnings, destructive confirms |
| `SettingsMenuDialog` | `widgets/settings_menu.py` | No | Settings gear icon |
| `AnalysisDialog` | `widgets/analysis.py` | No | Analysis button in Edits |

### Dialog Rules

1. **Non-modal by default** (`show()`) — instrument control must never be blocked by a dialog
2. **`exec()` only for**: destructive confirmations (delete, clear, overwrite) and blocking license/onboarding
3. Dialogs store `_instance` on parent — never create two instances of the same dialog
4. `closeEvent` must release any acquired resources (stop timers, disconnect signals)
5. Non-modal dialogs are resizable unless they contain a fixed-size form

---

## 6. Presenters (View Coordination)

Presenters are the only layer that touches widget state in response to business logic events. **No manager or service should call `widget.setEnabled()` directly.**

| Presenter | File | Owns |
|-----------|------|------|
| `SensogramPresenter` | `presenters/sensogram_presenter.py` | Timeline + cycle graph updates, cursors, flags, channel visibility |
| `SpectroscopyPresenter` | `presenters/spectroscopy_presenter.py` | Transmission + raw spectrum plot updates |
| `QueuePresenter` | `presenters/queue_presenter.py` | Queue table with undo/redo |
| `NavigationPresenter` | `presenters/navigation_presenter.py` | Nav bar buttons + page switching |
| `StatusPresenter` | `presenters/status_presenter.py` | Status bar and device status display |
| `BaselineRecordingPresenter` | `presenters/baseline_recording_presenter.py` | Baseline recording progress + state |
| `GuidanceCoordinator` | `coordinators/guidance_coordinator.py` | Adaptive contextual hints based on user experience level |

### `GuidanceCoordinator`
**File**: [`affilabs/coordinators/guidance_coordinator.py`](../../affilabs/coordinators/guidance_coordinator.py)
**FRS**: [`docs/features/GUIDANCE_COORDINATOR_FRS.md`](../features/GUIDANCE_COORDINATOR_FRS.md)

> Plain Python object (not `QObject`) — no Qt signals. Receives events from `main.py` signal handlers.

**Guidance levels** (set by experiment count):

| Level | Threshold | Hint density |
|-------|-----------|--------------|
| `full` | 0–4 experiments | All hints shown |
| `standard` | 5–19 experiments | Reduced set |
| `minimal` | 20+ experiments | Critical only |

**Entry points**: `on_hardware_connected()`, `on_calibration_complete()`, `on_acquisition_started()`, `on_injection_placed()`, `on_recording_started()`, `on_cycle_complete()`, `on_export_complete()`

**Pass A** (complete): logs hint decisions only — no widget calls
**Pass B** (pending): will call `SparkHelpWidget.push_hint()` and other widget APIs based on hint key

### Presenter Rules

1. Presenter methods are called from `main.py` signal handlers — always on the Qt main thread
2. Presenters must not import managers or services — they receive data through method arguments or signals
3. Graph updates go through `AL_UIUpdateCoordinator` which batches on a timer — never call `curve.setData()` more frequently than 10 Hz
4. A presenter owns a specific widget; two presenters must not write to the same widget

---

## 7. Interaction State Rules

These rules define when UI elements are enabled, disabled, visible, or hidden based on application state.

### Hardware Connection State

| State | Power btn | Record btn | Pause btn | Sidebar controls |
|-------|-----------|------------|-----------|-----------------|
| Disconnected | Enabled ("Connect") | Disabled | Disabled | Settings/Export enabled; others read-only |
| Searching | Disabled (spinner text) | Disabled | Disabled | All disabled |
| Connected (not calibrated) | Enabled ("Disconnect") | Disabled | Disabled | All enabled except Record-dependent |
| Calibrated | Enabled | Enabled | Disabled | All enabled |
| Acquiring | Enabled | Enabled (Recording) | Enabled | Most enabled; hardware params locked |
| Paused | Enabled | Enabled | Enabled (Resume) | Same as Acquiring |

### Calibration Gate

The following are **only available after successful calibration**:
- Record button
- Cycle start (Method tab)
- Injection controls (Flow tab pump actions)

### Acquisition Lock

The following are **locked during active acquisition** (disabled, not hidden):
- Integration time input
- Detector profile selector
- Polarizer position inputs
- Servo settle time

### Queue State Rules

| Queue state | "Start" button | "Stop" button | "Add to Queue" |
|-------------|---------------|--------------|----------------|
| Empty | Disabled | Disabled | Enabled |
| Has cycles, not running | Enabled | Disabled | Enabled |
| Running | Disabled | Enabled | Disabled |
| Paused mid-queue | Disabled | Enabled (stops) | Disabled |

### Export Enable Conditions

All three must be true for Export button to be enabled:
1. At least 1 channel checkbox checked
2. A valid destination directory is set
3. At least 1 recorded cycle exists in the session

---

## 8. Adding New UI Components

Follow this checklist when adding any new widget, tab, or dialog.

### New Widget

1. Create file in [`affilabs/widgets/`](../../affilabs/widgets/) — name: `descriptive_noun.py`
2. Class inherits from the narrowest appropriate Qt base (`QWidget`, `QFrame`, `QDialog`)
3. Apply styles from `ui_styles.py` — no inline hex values
4. Define all button/control states (default, hover, pressed, disabled)
5. Emit signals for user actions — do not call managers directly
6. If it needs data updates: accept data through a public method, not constructor args
7. Add to widget inventory in this document

### New Sidebar Tab

1. Create builder file: [`affilabs/sidebar_tabs/AL_<name>_builder.py`](../../affilabs/sidebar_tabs/)
2. Builder class has a single public method: `build(parent_widget) → QWidget`
3. Wire tab into `AffilabsSidebar.__init__()` using `self.tabs.addTab()`
4. Add tab entry to §3 of this document

### New Dialog

1. Create file in [`affilabs/widgets/<name>_dialog.py`](../../affilabs/widgets/)
2. Use `show()` unless a blocking confirm is genuinely required
3. Cache the instance on the parent window: `self._my_dialog = None` → lazy init
4. Add entry to §5 dialog table

### New Presenter

1. Create file in [`affilabs/presenters/<name>_presenter.py`](../../affilabs/presenters/)
2. Register in [`affilabs/presenters/__init__.py`](../../affilabs/presenters/__init__.py)
3. Wire signals in `main.py` — not in the presenter constructor
4. Add entry to §6 presenter table

### Checklist Before Merging UI Work

- [ ] No hardcoded hex colors — uses `Colors.*` tokens
- [ ] No hardcoded spacing values — uses `Spacing.*` or `Dimensions.*`
- [ ] Button has all 4 states styled (default, hover, pressed, disabled)
- [ ] Nothing calls `exec()` except destructive confirm dialogs
- [ ] No UI state updates called from background threads
- [ ] Widget added to the inventory table in §4 of this document
- [ ] Interaction state rules in §7 updated if new enable/disable conditions added
