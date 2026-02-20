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

#### Toolbar

| Element | Widget | States | Rule |
|---------|--------|--------|------|
| **Power** | `QPushButton` (checkable) | `disconnected` / `searching` / `connected` | Disabled during calibration. Text and color change per state (see Design System §9). |
| **Record** | `QPushButton` (checkable) | enabled / disabled / recording | Disabled until calibration completes. Becomes "⏺ Recording" when active. |
| **Pause** | `QPushButton` (checkable) | enabled / disabled / paused | Disabled until acquisition starts. Toggle emits `acquisition_pause_requested(bool)`. |

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

### Tab 1 — Graphic Control
**Builder**: [`AL_graphic_control_builder.py`](../../affilabs/sidebar_tabs/AL_graphic_control_builder.py)

| Control | Widget | Effect |
|---------|--------|--------|
| Y-axis mode | Segmented (Auto / Manual) | Switches `enableAutoRange()` on/off |
| Y min / Y max | `QDoubleSpinBox` × 2 | Sets `setYRange()` on sensorgram graphs |
| EMA filter | Segmented (None / Light / Medium / Heavy) | Sets EMA alpha in `SensogramPresenter` |
| Colorblind mode | `QCheckBox` | Switches channel colors to Tol bright palette |
| Grid | `QCheckBox` | Calls `showGrid()` on graphs |
| Show raw spectrum | `QPushButton` | Opens spectroscopy popup window |
| Show transmission | `QPushButton` | Opens transmission spectrum popup |

**Rules**:
- Y-axis controls are disabled when "Auto" is selected
- Filter changes take effect on the next graph update cycle — no retroactive smoothing
- Colorblind toggle must update all 4 channel curves immediately

---

### Tab 2 — Method
**Builder**: [`AL_method_builder.py`](../../affilabs/sidebar_tabs/AL_method_builder.py)

| Section | Components |
|---------|-----------|
| Queue summary | `QueueSummaryWidget` — drag-to-reorder table of queued cycles |
| Cycle editor | Type dropdown (`CycleConfig.TYPES`), duration, comment field |
| Actions | Add to Queue, Start, Stop, Clear buttons |
| Templates | Browse / Save / Load via `CycleTemplateDialog` |
| Spark | "Build with Spark" button → `MethodBuilderDialog` |

**Rules**:
- "Start" is disabled when: no cycles in queue, not calibrated, or acquisition already running
- "Stop" terminates the current cycle immediately — confirm dialog before firing
- Drag reorder in `QueueSummaryWidget` updates queue order in `QueueManager`
- Cycle comment is optional (can be empty)
- Time dropdown (`CycleConfig.TIME_OPTIONS`) is enabled only for Flow and Static types
- "Build Method" button opens `MethodBuilderDialog` non-modally (`show()` not `exec()`)

---

### Tab 3 — Flow
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

### Tab 4 — Export
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

### Tab 5 — Settings
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

### Tab 6 — Data Replay
**Builder**: [`AL_data_replay_builder.py`](../../affilabs/sidebar_tabs/AL_data_replay_builder.py)

| Control | Purpose |
|---------|---------|
| File picker | Load a `.json` / `.xlsx` session file |
| Playback controls | Play / Pause / Rewind / Speed multiplier |
| Channel selector | Which channels to replay |

**Rules**:
- Replay mode disables hardware controls (Power, Record, Pause toolbar buttons)
- Replay data populates the same sensorgram graphs as live mode
- Exiting replay mode restores hardware controls to their pre-replay state

---

### Tab 7 — Spark AI
**Widget**: [`affilabs/widgets/spark_sidebar.py`](../../affilabs/widgets/spark_sidebar.py) → contains `SparkHelpWidget`

| Element | Behavior |
|---------|---------|
| Conversation view | Scrollable Q&A bubble list |
| Input field | `QLineEdit`, Enter sends query |
| Voice toggle (🔊) | TTS on/off — **default: OFF** |
| Feedback buttons | 👍/👎 per answer — logged for improvement |

**Rules**:
- Answer generation is always on a background thread — UI never blocks
- If answer generation fails, show a graceful fallback: "I couldn't find an answer. Try rephrasing."
- TTS disabled by default (`spark_help_widget.py:387`)
- All Spark entry points wrapped in try/except — Spark failure must never crash the main app

---

## 4. Reusable Widgets

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

### `IntelligenceBar`
**File**: [`affilabs/widgets/intelligence_bar.py`](../../affilabs/widgets/intelligence_bar.py)

- Horizontal status bar showing acquisition / calibration system state
- Updates on every acquisition tick
- Rules: Never show errors here — use status bar for errors. Bar shows operational state only.

### `DeltaSPROverlay`
**File**: [`affilabs/widgets/delta_spr_overlay.py`](../../affilabs/widgets/delta_spr_overlay.py)

- Real-time biosensing measurement display overlay on Live graph
- Visible only when alignment reference is set
- Shows current Δλ (nm) per channel

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

- 4-graph QC view: S-pol, P-pol, dark spectrum, transmission
- Opened after calibration completes
- Non-modal — user can dismiss and continue

### `DeviceStatus`
**File**: [`affilabs/widgets/device_status.py`](../../affilabs/widgets/device_status.py)

- Grayscale-themed hardware status panel
- Shows controller / detector / pump state with dot indicators
- Reads from `HardwareManager.status_dict`

---

## 5. Dialogs

All dialogs lazy-loaded (created on first access, then cached). Use `show()` for non-modal, `exec()` only for blocking flows (confirmations).

| Dialog | File | Modal | Trigger |
|--------|------|-------|---------|
| `MethodBuilderDialog` | `widgets/method_builder_dialog.py` | No | "Build Method" button in Method tab |
| `CycleTemplateDialog` | `widgets/cycle_template_dialog.py` | No | "Templates" button |
| `CycleTableDialog` | `widgets/cycle_table_dialog.py` | No | Double-click cycle in Edits tab |
| `CalibrationQCDialog` | `widgets/calibration_qc_dialog.py` | No | Auto-shown after calibration |
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
