# Sidebar Builders — Functional Requirements Specification

**Source:** `affilabs/sidebar_tabs/` (7 builder modules)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Sidebar tab builders construct the content of the left-sidebar tabs (accessed via Icon Rail). Each builder class follows the **Builder pattern**: takes a `sidebar` reference, has a `build(tab_layout)` entry point, and private `_build_*` section methods.

---

## 2. Builder Catalog

| File | Class | Lines | Purpose |
|------|-------|-------|---------|
| `AL_settings_builder.py` | `SettingsTabBuilder` | 1707 | Diagnostics, hardware config, calibration, display |
| `AL_flow_builder.py` | `FlowTabBuilder` | 2012 | Fluidics: pump control, valves, flow status |
| `AL_data_replay_builder.py` | `DataReplayTabBuilder` | 955 | Import + playback of historical experiment data |
| `AL_method_builder.py` | `MethodTabBuilder` | 803 | Assay builder: cycle config, queue, execution |
| `AL_graphic_control_builder.py` | `GraphicControlTabBuilder` | 755 | Graph display: filtering, axes, traces, accessibility |
| `AL_device_status_builder.py` | `DeviceStatusTabBuilder` | 552 | Instrument dashboard with LED indicators |
| `AL_export_builder.py` | `ExportTabBuilder` | 288 | Export format selection and file settings |

---

## 3. Common Pattern

```python
class XxxTabBuilder:
    def __init__(self, sidebar):
        self.sidebar = sidebar

    def build(self, tab_layout: QVBoxLayout):
        self._build_section_a(tab_layout)
        self._build_section_b(tab_layout)
        ...
```

All builders store widgets on `self.sidebar` for external access (e.g., `sidebar.transmission_plot`, `sidebar.pump_speed_combo`).

---

## 4. Settings Tab (`AL_settings_builder.py`)

**`SettingsTabBuilder`** — the largest sidebar tab (1707 lines). Contains:

| Section | Method | Content |
|---------|--------|---------|
| Hardware status | `_build_hardware_status_section` | Connection status readouts |
| About | `_build_about_section` | App version, about info |
| User management | `_build_user_management` | User profile CRUD |
| Spectroscopy plots | `_build_spectroscopy_plots` | Transmission + raw spectrum graphs |
| Intelligence bar | `_build_intelligence_bar` | Real-time system status |
| Hardware config | `_build_hardware_configuration` | Device-specific settings |
| Polarizer | `_build_polarizer_settings` | Servo polarizer controls |
| LED settings | `_build_led_settings` | LED intensity controls |
| Settings buttons | `_build_settings_buttons` | Apply / reset |
| Calibration | `_build_calibration_controls` | Calibration trigger controls |
| Display | `_build_display_controls_section` | Display options |
| Data filtering | `_build_data_filtering` | Smoothing / filter controls |
| Reference | `_build_reference_section` | Reference channel selection |
| Accessibility | `_build_visual_accessibility` | Colorblind palette toggle |

---

## 5. Flow Tab (`AL_flow_builder.py`)

**`FlowTabBuilder`** — fluidics control (2012 lines, largest file). Also defines `AdvancedFlowRatesDialog(QDialog)`.

| Section | Method | Content |
|---------|--------|---------|
| Intelligence bar | `_build_intelligence_bar` | System status |
| Flow status | `_build_flow_status_board` | Flow rate / pressure readouts |
| AffiPump | `_build_affipump_control` | External syringe pump controls |
| Internal pumps | `_build_internal_pump_control` | P4PROPLUS built-in pump controls |
| Valves | `_build_valve_control` | 6-port rotary valve |

---

## 6. Method Tab (`AL_method_builder.py`)

**`MethodTabBuilder`** — assay builder and queue display (803 lines).

| Section | Method | Content |
|---------|--------|---------|
| Active cycle card | `_build_active_cycle_card` | Current cycle display |
| Build Method CTA | `_build_build_method_cta` | "Build Method" button → opens `MethodBuilderDialog` |
| Cycle history/queue | `_build_cycle_history_queue` | Past and pending cycles |
| Summary table | `_build_summary_table` | Queue summary `QueueSummaryWidget` |

Helper: `_create_svg_icon(svg_string, icon_size=18)` — static SVG icon factory.

---

## 7. Graphic Control Tab (`AL_graphic_control_builder.py`)

**`GraphicControlTabBuilder`** — graph display settings (755 lines).

| Section | Method | Content |
|---------|--------|---------|
| Data filtering | `_build_data_filtering` | Smoothing controls |
| Live timeframe | `_build_live_cycle_timeframe` | X-axis time window |
| Reference | `_build_reference_section` | Reference channel selection |
| Graphic display | `_build_graphic_display` | Display options |
| Axis selector | `_build_axis_selector` | X/Y axis type |
| Axis scaling | `_build_axis_scaling` | Auto/manual scaling |
| Trace options | `_build_trace_options` | Line style, thickness, grid |
| Accessibility | `_build_visual_accessibility` | Colorblind palette toggle |

Constant: `COLORBLIND_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44"]`

---

## 8. Device Status Tab (`AL_device_status_builder.py`)

**`DeviceStatusTabBuilder`** — instrument dashboard (552 lines).

| Section | Method | Content |
|---------|--------|---------|
| Hardware | `_build_hardware_section` | Connection status |
| Components | `_build_components_section` | Detector, controller, pump status |
| Modes | `_build_modes_section` | Operating modes |
| Maintenance | `_build_maintenance_section` | Diagnostics info |
| Actions | `_build_actions_section` | Quick action buttons |

LED indicator constants: `_LED_GREEN`, `_LED_AMBER`, `_LED_RED`, `_LED_OFF` (+ glow variants).
Helpers: `_led_bar_style(color, glow, height=3)`, `_led_dot_style(color, glow, size=8)`.

---

## 9. Export Tab (`AL_export_builder.py`)

**`ExportTabBuilder`** — export configuration (288 lines).

| Section | Method | Content |
|---------|--------|---------|
| Format | `_build_export_format` | Format selector (CSV, Excel) |
| File settings | `_build_file_settings` | Output path, naming, options |

---

## 10. Data Replay Tab (`AL_data_replay_builder.py`)

**`DataReplayTabBuilder`** — historical data playback (955 lines). Maintains playback state: `loaded_data`, `cycles_df`, `is_playing`, `current_frame`, `total_frames`.

| Section | Method | Content |
|---------|--------|---------|
| Load | `_build_load_section` | Excel file picker |
| Playback | `_build_playback_section` | Play/pause, speed, scrubber |
| Cycle info | `_build_cycle_info_section` | Cycle navigation + metadata |
| Export | `_build_export_section` | GIF/PNG export controls |

---

## 11. Naming Convention

All sidebar builder files follow the `AL_*_builder.py` pattern (prefix `AL_` = AffiLabs).
