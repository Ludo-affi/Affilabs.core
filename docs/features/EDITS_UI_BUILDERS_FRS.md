# EDITS_UI_BUILDERS_FRS.md

**Feature Requirement Specification: Edits Tab UI Builders**  
Document Status: ✅ Code-verified  
Last Updated: February 19, 2026  
Source File: `affilabs/tabs/edits/_ui_builders.py` (1048 lines)

---

## §1. Purpose & Context

**What This Is:**  
`UIBuildersMixin` is the pure UI construction layer for EditsTab. It contains every method that creates widgets, layouts, and pyqtgraph plots. All event-handling logic (`_on_cycle_selected_in_table`, `_apply_cycle_filter`, etc.) lives in other mixins — `UIBuildersMixin` is responsible only for building the view hierarchy.

**Mixin Structure:**  
EditsTab assembles its UI from 4 mixin classes:
- `UIBuildersMixin` — **Widget construction** (this document)
- `DataLoaderMixin` — Cycle data loading and table population
- `InteractionMixin` — User event handlers (table clicks, filter changes, etc.)
- `ExportMixin` — Excel/CSV export logic

**Widget references created here are stored as `self.*` on EditsTab** and accessed by other mixins. The calling convention is `content_widget = self.create_content()` from `EditsTab.__init__()`.

---

## §2. Layout Architecture

### Top-Level Structure

```
EditsTab (QWidget)
└─ create_content() → QFrame (content_widget)
     └─ outer_layout (QHBoxLayout)
          ├─ export_sidebar (QWidget, collapsible left panel, initially hidden)
          └─ main_splitter (QSplitter, Horizontal)
               ├─ left_panel (50% initial width)
               │    └─ left_splitter (QSplitter, Vertical)
               │         ├─ table_details_widget (70% initial)
               │         │    └─ QVBoxLayout
               │         │         ├─ table_panel        ← _create_table_panel()
               │         │         └─ details_tab_widget  (Flags / Notes tabs)
               │         └─ bottom_left_widget (30% initial)
               │              └─ QHBoxLayout
               │                   ├─ metadata_panel     ← _create_metadata_panel()
               │                   └─ alignment_panel    ← _create_alignment_panel()
               └─ right_panel (50% initial width)
                    └─ graphs_splitter (QSplitter, Vertical)
                         ├─ selection_widget (70% initial) ← _create_active_selection()
                         └─ barchart_widget (30% initial) ← _create_delta_spr_barchart()
```

**Alternative compact view**: `_apply_compact_view_initial()` collapses `bottom_left_widget` (sets size hint to 60px) when window width < 1400px. Called immediately after `create_content()`.

---

## §3. create_content()

**Signature:** `create_content() → QFrame`

Creates and returns the complete layout hierarchy. Called once from `EditsTab.__init__()`:
```python
self.content_widget = self.create_content()
self._main_layout.addWidget(self.content_widget)
```

**Background:** `#F8F9FA` (light gray page background)  
**Splitter sizes:** main_splitter → `[500, 500]`; left_splitter → `[400, 150]`; graphs_splitter → `[400, 150]`

### pyqtgraph Plots Created in create_content()

Two pyqtgraph plots are instantiated in `create_content()` before being passed to sub-builders:

| Widget | Type | Purpose |
|--------|------|---------|
| `self.edits_timeline_graph` | `pg.PlotWidget` | Full timeline view (all loaded cycles) |
| `self.edits_primary_graph` | `pg.PlotWidget` | Active selection view (one cycle detail) |

Both are created before calling `_create_active_selection()` because the selection panel reuses `edits_primary_graph` (not create a new one).

### Details Tab Widget (below table)

```python
self.details_tab_widget = QTabWidget()
self.details_tab_widget.setTabPosition(QTabWidget.South)
self.details_tab_widget.setStyleSheet(...)

# Tab 1: Flags
flags_page = QWidget()
self.flags_list = QListWidget()
self.details_tab_widget.addTab(flags_page, "🚩 Flags")

# Tab 2: Notes
notes_page = QWidget()
self.cycle_notes_edit = QTextEdit()
self.cycle_notes_edit.setPlaceholderText("Add notes for this cycle...")
self.cycle_notes_edit.textChanged.connect(self._on_cycle_notes_changed)
self.details_tab_widget.addTab(notes_page, "📝 Notes")
```

### Widget References Stored on Self

After `create_content()`, the following attributes exist on `self`:
- `self.edits_timeline_graph` — Timeline graph (PlotWidget)
- `self.edits_primary_graph` — Selection graph (PlotWidget)
- `self.details_tab_widget` — Flags/Notes tab widget
- `self.flags_list` — QListWidget for cycle flags display
- `self.cycle_notes_edit` — QTextEdit for cycle notes
- Plus all attributes from each sub-builder (see §4-§8)

---

## §4. _create_table_panel()

**Returns:** `QFrame` (white, rounded corners)

Creates the cycle table panel occupying the upper-left area.

### Layout Within Panel

```
table_panel (QFrame, white, border-radius 12px, shadow)
└─ QVBoxLayout
     ├─ controls_row (QHBoxLayout)
     │    ├─ load_btn            "📂 Load Data"
     │    ├─ filter_combo        Cycle type filter
     │    ├─ search_box          Text search (150px)
     │    └─ columns_btn         "☰" column visibility
     ├─ empty_state_widget       (shown when no cycles loaded)
     └─ cycle_data_table         QTableWidget (5 columns)
```

### cycle_data_table (QTableWidget)

The primary data table showing loaded cycles.

**Column definition:**

| Index | Header | Width | Description |
|-------|--------|-------|-------------|
| 0 | Export | 50px | Checkbox column, centered |
| 1 | Type | 55px | Cycle type badge (e.g., "Baseline") |
| 2 | Time | Stretch | Duration (e.g., "10 min") |
| 3 | Conc. | Stretch | Concentration (e.g., "100 nM") |
| 4 | ΔSPR | Stretch | Calculated delta SPR value |

**Table settings:**
```python
table.setSelectionBehavior(QAbstractItemView.SelectRows)
table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Ctrl+click multi-select
table.verticalHeader().setVisible(False)                    # No row numbers
table.verticalHeader().setDefaultSectionSize(22)            # 22px row height
table.setAlternatingRowColors(True)                         # Zebra stripes
table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Time stretches
table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # Conc. stretches
table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # ΔSPR stretches
```

**Signals connected:**
```python
table.itemSelectionChanged.connect(self._on_cycle_selected_in_table)
table.itemSelectionChanged.connect(self._update_export_sidebar_stats)
table.itemSelectionChanged.connect(self._update_details_panel)
table.itemSelectionChanged.connect(self._reset_delta_spr_lock)
```

### Empty State Widget

Shown when no cycles are loaded; hidden when table has data:
```python
empty_state_widget = QWidget()  # Stored as self.empty_state_widget
# Contains: 📊 icon (48px) + "No cycles to display" + 
#           "Start a recording or load data to begin"
```

### Filter & Search Controls

```python
self.filter_combo = QComboBox()
# Items populated at runtime by DataLoaderMixin
# Signal: currentTextChanged → self._apply_cycle_filter

self.search_box = QLineEdit()
self.search_box.setPlaceholderText("Search cycles...")
self.search_box.setFixedWidth(150)
# Signal: textChanged → self._apply_search_filter

self.columns_btn = QPushButton("☰")
self.columns_btn.setFixedSize(28, 28)
# Signal: clicked → self._show_column_visibility_menu
```

---

## §5. _create_metadata_panel()

**Returns:** `QFrame` (white, rounded corners, fixed width ~260px)

Shows metadata for the currently selected cycle(s). Hidden when nothing is selected (toggled by `InteractionMixin._update_selection_panels()`).

### Layout

```
metadata_panel (QFrame, white, border-radius 12px, shadow)
└─ QVBoxLayout
     ├─ title: "Cycle Details"
     ├─ grid (QGridLayout, 2 col)
     │    ├─ Row 0: "Method:"    self.meta_method
     │    ├─ Row 1: "Cycles:"    self.meta_cycles
     │    ├─ Row 2: "Types:"     self.meta_types
     │    ├─ Row 3: "Conc.:"     self.meta_conc_range
     │    ├─ Row 4: "Date:"      self.meta_date
     │    ├─ Row 5: "Operator:"  self.meta_operator
     │    └─ Row 6: "Device:"    self.meta_device
     ├─ divider (QFrame::HLine, #E5E5EA)
     ├─ "Sensor type:"
     └─ self.sensor_input (QLineEdit, placeholder "Enter sensor type...")
```

### Widget References Created

| Attribute | Type | Content |
|-----------|------|---------|
| `self.meta_method` | QLabel | Method name (e.g., "5-point titration") |
| `self.meta_cycles` | QLabel | Cycle count (e.g., "7 cycles") |
| `self.meta_types` | QLabel | Cycle types (e.g., "Baseline, Binding") |
| `self.meta_conc_range` | QLabel | Concentration range (e.g., "10–1000 nM") |
| `self.meta_date` | QLabel | Recording date |
| `self.meta_operator` | QLabel | Operator name from user profile |
| `self.meta_device` | QLabel | Device identifier |
| `self.sensor_input` | QLineEdit | User-entered sensor type; persisted per session |

**All `meta_*` labels** are styled `#86868B` (gray) with 12px font. Labels (keys) are `#1D1D1F` bold.

---

## §6. _create_alignment_panel()

**Returns:** `QFrame` (info panel, initially **hidden** via `panel.hide()`)

Shows cycle-specific timing details and provides alignment/reference controls for the selected cycle. Shown by `InteractionMixin._update_selection_panels()` when a cycle is selected.

### Layout Sections

**Section 1: Timing Info Grid**
```
"Start:"   self.alignment_start_time  (QLabel, e.g., "0.00 s")
"End:"     self.alignment_end_time    (QLabel, e.g., "600.00 s")
"Flags:"   self.alignment_flags_display (QLabel, styled green "#34C759")
```

**Section 2: Reference Subtraction**
```
"Ref:"   self.alignment_ref_combo  (QComboBox)
```
`alignment_ref_combo` items:
- `"Global"` — Use toolbar global reference setting
- `"None"` — Disable reference subtraction for this cycle
- `"Ch A"`, `"Ch B"`, `"Ch C"`, `"Ch D"` — Use specific channel as reference

Signal: `currentTextChanged → self._on_cycle_ref_changed`

**Section 3: Channel Alignment**
```
"Channel:"   self.alignment_channel_combo  (QComboBox: All, A, B, C, D)
"Shift:"     self.alignment_shift_input    (QLineEdit, 80px, shows seconds)
             self.alignment_shift_slider   (QSlider, -200 to +200 = -20s to +20s)
```
Signals:
- `alignment_shift_input.textChanged → self._on_shift_input_changed`
- `alignment_shift_slider.valueChanged → self._on_shift_slider_changed`

**Slider range:** ±200 ticks at 0.1s/tick = ±20.0s for fine alignment

---

## §7. _create_active_selection()

**Returns:** `QFrame` (white, border-radius 12px, drop shadow)

The dominant right panel. Contains channel toggle buttons, `edits_primary_graph`, and Delta SPR measurement cursors.

### Layout

```
selection_widget (QFrame, white, shadow)
└─ QVBoxLayout
     ├─ header (QHBoxLayout)
     │    ├─ "Active Selection View" title
     │    ├─ Ch A button (checkable, black #1D1D1F)
     │    ├─ Ch B button (checkable, red #FF3B30)
     │    ├─ Ch C button (checkable, blue #007AFF)
     │    ├─ Ch D button (checkable, green #34C759)
     │    └─ "⟲ Reset" button → edits_primary_graph.autoRange()
     └─ edits_primary_graph (PyQtGraph PlotWidget, white bg, grid)
```

### Channel Toggle Buttons

```python
self.edits_channel_buttons = {}  # dict: 'A'/'B'/'C'/'D' → QPushButton

# Colors update when colorblind mode toggled (global setting check at build time)
colorblind_enabled = (
    hasattr(self.main_window, 'colorblind_check') and 
    self.main_window.colorblind_check.isChecked()
)
bar_colors = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS
```

**Toggle signal:** `btn.toggled → lambda checked, idx: self._toggle_channel(idx, checked)`

**Unchecked style:** Background `rgba(0,0,0,0.06)`, text `#86868B` — channel grayed out visually in graph.

### Delta SPR Cursors

Two movable `pg.InfiniteLine` cursors added to `edits_primary_graph`:

```python
self.delta_spr_start_cursor = pg.InfiniteLine(
    pos=0, angle=90, movable=True,
    pen=pg.mkPen(color='#34C759', width=2, style=Qt.DashLine),
    label='Start',
    labelOpts={'position': 0.85, 'color': '#34C759'}
)
self.delta_spr_stop_cursor = pg.InfiniteLine(
    pos=100, angle=90, movable=True,
    pen=pg.mkPen(color='#FF3B30', width=2, style=Qt.DashLine),
    label='Stop',
    labelOpts={'position': 0.85, 'color': '#FF3B30'}
)
```

Signals: both `sigPositionChanged → self._update_delta_spr_barchart` — dragging cursors live-updates the bar chart.

---

## §8. _create_delta_spr_barchart()

**Returns:** `QFrame` (white, border-radius 12px, drop shadow)

The lower-right panel. Shows channel responses (ΔSPR in RU) between the Start and Stop cursors as a bar chart.

### Layout

```
barchart_widget (QFrame, white, shadow)
└─ QVBoxLayout
     ├─ header (QHBoxLayout)
     │    ├─ "ΔSPR (RU) - Response Between Cursors" title
     │    ├─ self.delta_spr_lock_btn  "🔓 Unlock" (checkable toggle)
     │    └─ "⟲" reset button → delta_spr_barchart.autoRange()
     └─ self.delta_spr_barchart (pg.PlotWidget, fixed height 220px)
```

### delta_spr_barchart (pg.PlotWidget)

- **Y axis:** `setLabel('left', 'ΔSPR (RU)')`; initial `setYRange(0, 100)`
- **X axis:** Custom ticks: `[(0,'Ch A'), (1,'Ch B'), (2,'Ch C'), (3,'Ch D')]`
- **Grid:** `showGrid(y=True, alpha=0.2)`
- **Context menu:** `setMenuEnabled(True)` — right-click to export chart data

### Bar Items

One `pg.BarGraphItem` per channel (A/B/C/D) — colors match sensorgram curve colors:
```python
self.delta_spr_bars = []  # list[pg.BarGraphItem], indices 0-3

# Colors: CHANNEL_COLORS or CHANNEL_COLORS_COLORBLIND from plot_helpers
for i, color in enumerate(bar_colors):
    bar = pg.BarGraphItem(x=[i], height=[0], width=0.6, brush=pg.mkColor(color))
    self.delta_spr_barchart.addItem(bar)
    self.delta_spr_bars.append(bar)
```

### Value Labels

One `pg.TextItem` per channel, positioned above each bar:
```python
self.delta_spr_labels = []  # list[pg.TextItem], indices 0-3

for i in range(4):
    text = pg.TextItem(text='0.0', anchor=(0.5, 1.2), color='#1D1D1F')
    text.setFont(QFont('-apple-system', 10, QFont.Bold))
    self.delta_spr_barchart.addItem(text)
    self.delta_spr_labels.append(text)
```

Bars and labels updated together by `_update_delta_spr_barchart()` (in `InteractionMixin`).

### Lock Button

`self.delta_spr_lock_btn` — Checkable button. When checked (locked):
- Positions cursors at `contact_time + 10%` relative to cycle start
- Prevents manual cursor dragging
- Label changes: `"🔓 Unlock"` → `"🔒 Locked"`

Signal: `toggled → self._toggle_delta_spr_lock`

---

## §9. _create_tools_panel()

**Returns:** `QFrame` (white, border-radius 12px, drop shadow)

Compact bottom bar with smoothing control and primary action buttons.

### Layout

```
tools_panel (QFrame, white, shadow)
└─ QHBoxLayout (horizontal, all on one row)
     ├─ "Smoothing:" label
     ├─ self.edits_smooth_label  (QLabel shows current value)
     ├─ self.edits_smooth_slider (QSlider 0-50, max width 200px)
     ├─ [stretch]
     ├─ create_processing_btn   "📊 Create Processing Cycle"
     └─ export_btn              "📥 Export"
```

### Smoothing Slider

```python
self.edits_smooth_slider = QSlider(Qt.Horizontal)
self.edits_smooth_slider.setRange(0, 50)  # Savitzky-Golay window size (0=off)
self.edits_smooth_slider.setValue(0)
self.edits_smooth_slider.setMaximumWidth(200)
# Signal:
self.edits_smooth_slider.valueChanged.connect(lambda v: (
    self.edits_smooth_label.setText(str(v)),
    self._update_selection_view()
))
```

Slider value = Savitzky-Golay window size passed to `_update_selection_view()` for live re-smoothing.

### Create Processing Cycle Button

- Label: `"📊 Create Processing Cycle"` (green #34C759)
- Signal: `clicked → self._create_processing_cycle`
- Purpose: Extract selected channels from multiple selected cycles → merge into single combined cycle

**Tooltip explains 3-step workflow:**
1. Select cycles in table
2. Set Channel filter per cycle (A/B/C/D or All)
3. Click to extract and merge

### Export Button

- Label: `"📥 Export"` (black #1D1D1F)
- Signal: `clicked → self._export_selection`
- Opens export dialog (ExportMixin handles implementation)

---

## §10. Column Visibility Menu

**Method:** `_show_column_visibility_menu()` — Called by `columns_btn` click

Creates a `QMenu` dynamically with `QAction(checkable=True)` entries for each table column. Users can show/hide individual columns:

```
☑ Type
☑ Time
☑ Conc.
☑ ΔSPR
```

Export column (0) is always visible (not toggleable). Menu appears at button position.

---

## §11. Compact View Initialization

**Method:** `_apply_compact_view_initial()`

Called immediately after `create_content()`. Checks window width:
```python
if self.main_window.width() < 1400:
    # Collapse bottom-left panel to minimal height
    self.bottom_left_widget.setMinimumHeight(60)
    self.bottom_left_widget.setMaximumHeight(60)
```

Users can still drag the splitter handle to expand it. The compact view is initial state only.

---

## §12. Export Sidebar

A collapsible left sidebar (initially hidden) toggled by an export action in the toolbar. Built inline in `create_content()`:

```python
self.export_sidebar = QWidget()
self.export_sidebar.hide()  # Initially hidden

# Contains:
# - Export format selector (Excel / CSV)
# - Channel checkboxes (A B C D)
# - Cycle type filter for export
# - selection stats labels
# - "Export Selected" primary action button
```

`InteractionMixin._update_export_sidebar_stats()` updates the stats labels whenever table selection changes.

---

## §13. Widget Quick Reference

All `self.*` attributes created by UIBuildersMixin:

| Attribute | Type | Created In | Purpose |
|-----------|------|-----------|---------|
| `edits_timeline_graph` | pg.PlotWidget | create_content() | Full timeline view |
| `edits_primary_graph` | pg.PlotWidget | create_content() | Selected cycle detail |
| `details_tab_widget` | QTabWidget | create_content() | Flags / Notes tabs |
| `flags_list` | QListWidget | create_content() | List cycle flags |
| `cycle_notes_edit` | QTextEdit | create_content() | Cycle notes entry |
| `empty_state_widget` | QWidget | _create_table_panel | No-data placeholder |
| `cycle_data_table` | QTableWidget | _create_table_panel | 5-col cycle list |
| `filter_combo` | QComboBox | _create_table_panel | Cycle type filter |
| `search_box` | QLineEdit | _create_table_panel | Text search |
| `columns_btn` | QPushButton | _create_table_panel | Column visibility |
| `meta_method` | QLabel | _create_metadata_panel | Method name |
| `meta_cycles` | QLabel | _create_metadata_panel | Cycle count |
| `meta_types` | QLabel | _create_metadata_panel | Cycle types |
| `meta_conc_range` | QLabel | _create_metadata_panel | Concentration range |
| `meta_date` | QLabel | _create_metadata_panel | Recording date |
| `meta_operator` | QLabel | _create_metadata_panel | Operator name |
| `meta_device` | QLabel | _create_metadata_panel | Device ID |
| `sensor_input` | QLineEdit | _create_metadata_panel | Sensor type entry |
| `alignment_start_time` | QLabel | _create_alignment_panel | Cycle start time |
| `alignment_end_time` | QLabel | _create_alignment_panel | Cycle end time |
| `alignment_flags_display` | QLabel | _create_alignment_panel | Flag count/summary |
| `alignment_ref_combo` | QComboBox | _create_alignment_panel | Reference channel |
| `alignment_channel_combo` | QComboBox | _create_alignment_panel | Channel to shift |
| `alignment_shift_input` | QLineEdit | _create_alignment_panel | Shift value (s) |
| `alignment_shift_slider` | QSlider | _create_alignment_panel | ±20s fine control |
| `edits_channel_buttons` | dict[str,QPushButton] | _create_active_selection | Ch A/B/C/D toggles |
| `delta_spr_start_cursor` | pg.InfiniteLine | _create_active_selection | Green start cursor |
| `delta_spr_stop_cursor` | pg.InfiniteLine | _create_active_selection | Red stop cursor |
| `delta_spr_lock_btn` | QPushButton | _create_delta_spr_barchart | Lock/unlock cursors |
| `delta_spr_barchart` | pg.PlotWidget | _create_delta_spr_barchart | Channel bar chart |
| `delta_spr_bars` | list[pg.BarGraphItem] | _create_delta_spr_barchart | 4 bar items |
| `delta_spr_labels` | list[pg.TextItem] | _create_delta_spr_barchart | Value labels above bars |
| `edits_smooth_label` | QLabel | _create_tools_panel | Shows slider value |
| `edits_smooth_slider` | QSlider | _create_tools_panel | Smoothing (0-50) |
| `export_sidebar` | QWidget | create_content() | Left export sidebar |

---

## §14. Design Notes

1. **`edits_primary_graph` is not created in `_create_active_selection()`** — It is created in `create_content()` and passed into the selection panel to avoid lifecycle issues with pyqtgraph ownership.

2. **Colors are applied at build time, not dynamically** — `edits_channel_buttons` and `delta_spr_bars` check `main_window.colorblind_check.isChecked()` ONCE during construction. Color mode changes require rebuild (handled by a settings signal in `InteractionMixin._rebuild_charts()`).

3. **Alignment panel is hidden by default** — `alignment_panel.hide()` is called in `_create_alignment_panel()`. It appears only when a cycle is selected. `metadata_panel` is always visible.

4. **Splitter state persistence** — `left_splitter`, `main_splitter`, `graphs_splitter` states are saved/restored in `EditsTab._save_layout_state()` / `_restore_layout_state()` using `QSettings`.

5. **`edits_timeline_graph` vs `edits_primary_graph`** — Timeline shows all loaded cycles overlaid; primary graph shows only the selected cycle(s). Both are separate PlotWidgets updated independently.

---

## §15. Document Metadata

**Created:** February 19, 2026  
**Codebase Version:** Affilabs.core v2.0.5 beta  
**Source Lines Reviewed:** All 1048 lines of `_ui_builders.py`  
**Next Review:** When new panels are added to EditsTab layout
