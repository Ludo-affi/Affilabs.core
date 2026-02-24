# EDITS_UI_BUILDERS_FRS.md

**Feature Requirement Specification: Edits Tab UI Layout**
Document Status: ✅ Code-verified
Last Updated: February 24, 2026
Source File: `affilabs/tabs/edits/_ui_builders.py`

---

## §1. Purpose

`UIBuildersMixin` is the pure UI construction layer for EditsTab. Contains every method that creates widgets and layouts. All event logic lives in other mixins — this mixin only builds the view hierarchy.

Widget references created here are stored as `self.*` on EditsTab and accessed by all other mixins.

---

## §2. Layout Architecture

```
EditsTab (QWidget)
└─ create_content() → QFrame (content_widget, bg #F8F9FA)
     └─ outer_layout (QHBoxLayout)
          └─ main_splitter (QSplitter, Horizontal, initial [500, 500])
               ├─ LEFT PANEL (QWidget)
               │    └─ left_splitter (QSplitter, Vertical, initial [400, 150])
               │         ├─ table_panel         ← _create_table_panel()
               │         └─ metadata_panel      ← _create_metadata_panel()
               └─ RIGHT PANEL (QWidget)
                    └─ graphs_splitter (QSplitter, Vertical, initial [400, 150])
                         ├─ selection_widget    ← _create_active_selection()
                         └─ bottom_tabs         ← QTabWidget
                              ├─ Tab 0: ΔSPR    ← _create_delta_spr_barchart()
                              └─ Tab 1: Binding ← (BindingPlotMixin)
```

**Removed from layout (Feb 24 2026):**
- `alignment_panel` — removed; controls replaced by graph-embedded interactions
- `details_tab_widget` (Flags/Notes QTabWidget) — replaced by plain notes panel inline in metadata

**Retained as invisible stubs** (via `_create_alignment_stubs()`):
`alignment_panel`, `alignment_title`, `alignment_flags_display`, `alignment_ref_combo`,
`alignment_shift_input`, `alignment_shift_slider`, plus the `_AlignChannelProxy` wrapper.
These satisfy `hasattr()` guards in `_alignment_mixin.py` without a visible panel.

---

## §3. Graph Header — Start/End Time Labels

Start and end time of the selected cycle are shown **inline in the Active Selection graph header** (not in a separate panel):

```python
self.alignment_start_time = QLabel("")   # e.g. "▶ 1140 s"
self.alignment_end_time   = QLabel("")   # e.g. "◼ 1440 s"
```

- Initially hidden; shown/hidden by `_edits_cycle_mixin._on_cycle_selected_in_table()`
- Format: `f"▶ {start:.0f} s"` / `f"◼ {end:.0f} s"`
- Style: 11px, `#86868B`, transparent background
- Positioned left of `cycle_context_label` in the graph header row

---

## §4. _create_table_panel()

**Returns:** `QFrame` (white, border-radius 12px, shadow)

### Layout

```
table_panel
└─ QVBoxLayout
     ├─ controls_row (QHBoxLayout)
     │    ├─ load_btn       (folder SVG icon, "Load")
     │    ├─ history_btn    ("History" → switches to Notes tab or opens ExperimentBrowserDialog)
     │    ├─ filter_combo   (cycle type filter)
     │    ├─ search_box     (🔍 placeholder, 150px)
     │    └─ columns_btn    ("☰", 28×28)
     ├─ empty_state_widget  (shown when no data)
     └─ cycle_data_table    (QTableWidget, 5 columns)
```

### cycle_data_table Columns

| Index | Header | Width | Notes |
|-------|--------|-------|-------|
| 0 | Export | 50px fixed | Checkbox |
| 1 | Type | 55px fixed | Cycle type badge |
| 2 | Time | Stretch | Duration (e.g. "10 min") |
| 3 | Conc. | Stretch | Concentration; **hidden by default** |
| 4 | ΔSPR | Stretch | Calculated delta SPR |

- `SelectionBehavior`: SelectRows; `SelectionMode`: ExtendedSelection
- Row height: 22px; `alternatingRowColors(True)`
- `col 2 + 3 + 4`: `setSectionResizeMode(Stretch)`

**Signals connected:**
```python
table.itemSelectionChanged → _on_cycle_selected_in_table
table.itemSelectionChanged → _update_export_sidebar_stats
table.itemSelectionChanged → _update_details_panel
table.itemSelectionChanged → _reset_delta_spr_lock
```

---

## §5. _create_metadata_panel()

**Returns:** `QFrame` (white, border-radius 12px, shadow)

The left-bottom panel. Always visible (not hidden on deselect).

### Grid Rows

| Row | Label | Attribute | Content |
|-----|-------|-----------|---------|
| 0 | Method: | `meta_method` | Method name from metadata |
| 1 | Cycles: | `meta_total_cycles` | Count of visible rows (blue #007AFF) |
| 2 | Types: | `meta_cycle_types` | Comma-separated unique types |
| 3 | Conc. Range: | `meta_conc_range` | Min–max concentration |
| 4 | Date: | `meta_date` | Recording date/time |
| 5 | Operator: | `meta_operator` | User from metadata or user_manager |
| 6 | Device: | `meta_device` | Serial (FLMT prefix → AFFI masked) |
| 7 | Calibration: | `meta_calibration` | Startup calibration JSON filename |
| 8 | Baseline file: | `meta_transmission_file` | Transmission baseline recording name |
| 9 | Rating: | `meta_star_buttons[0..4]` | 5 × ★ QPushButton (grey/gold) |
| 10 | Tags: | `meta_tags_pills` + `meta_tag_input` | Blue pill labels + add-tag QLineEdit |

**Below grid — divider + sensor row:**
```python
self.sensor_input = QLineEdit()  # placeholder "Enter sensor type..."
```

### Rating Interaction

- Clicking star N → `_on_star_clicked(N)`
- If current rating == N: clears to 0 (toggle off)
- Saved to `ExperimentIndex.set_rating(entry_id, N)`
- Displayed: gold `#FF9500` for filled stars, grey `#D1D1D6` for empty

### Tags Interaction

- Existing tags shown as blue pills (`#E3F0FF` bg, `#007AFF` text) with `✕` to remove
- `meta_tag_input` QLineEdit: Enter or `+` button calls `_on_tag_added()`
- Remove: `_on_tag_removed(tag)` via pill `✕` click
- All ops go through `ExperimentIndex.add_tag()` / `.remove_tag()`

### ExperimentIndex Lookup

`_find_index_entry_for_file(file_path)` — matches loaded file against index entries by:
1. Relative path from `~/Documents/Affilabs Data/`
2. Absolute path fallback

Returns `None` if no match (new recording not yet in index, or index missing).

---

## §6. _create_active_selection()

**Returns:** `QFrame` (white, border-radius 12px, shadow)

### Layout

```
selection_widget
└─ QVBoxLayout
     ├─ header (QHBoxLayout)
     │    ├─ title "Active Selection View"
     │    ├─ alignment_start_time  QLabel (▶ NNN s, hidden by default)
     │    ├─ alignment_end_time    QLabel (◼ NNN s, hidden by default)
     │    ├─ spacing(8)
     │    ├─ cycle_context_label   QLabel (e.g. "Cycle 3 — Binding")
     │    ├─ [stretch]
     │    ├─ Ch A button  (checkable, #1D1D1F)
     │    ├─ Ch B button  (checkable, #FF3B30)
     │    ├─ Ch C button  (checkable, #007AFF)
     │    ├─ Ch D button  (checkable, #34C759)
     │    └─ "⟲ Reset" button
     └─ edits_primary_graph (pg.PlotWidget)
          ├─ InteractiveSPRLegend  (floating, top-right, QTimer.singleShot 200ms)
          ├─ delta_spr_start_cursor (green dashed InfiniteLine, movable)
          └─ delta_spr_stop_cursor  (red dashed InfiniteLine, movable)
```

### Channel Toggle Buttons

```python
self.edits_channel_buttons = {}  # 'A'/'B'/'C'/'D' → QPushButton
```

Colors: hardcoded hex `{"A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}` — NOT from `_active_channel_colors()` (which returns matplotlib shorthand `"k"` for A, invalid CSS).

**Ctrl+click** on a channel button → `_on_edits_channel_ref_ctrl_click(ch)` → set/clear reference channel.

### InteractiveSPRLegend

- Created with `setVisible(False)`; made visible in `_on_cycle_selected_in_table()` after graph data plotted
- Positioned via `QTimer.singleShot(200, self._position_edits_legend)` to allow layout to settle
- Repositioned on resize events via `_EditsEventFilter`
- Shows ΔSPR values per channel; updated by `_update_delta_spr_barchart()`

### Delta SPR Cursors

```python
delta_spr_start_cursor: pg.InfiniteLine  # green #34C759, dashed
delta_spr_stop_cursor:  pg.InfiniteLine  # red #FF3B30, dashed
```

Both: `sigPositionChanged → _update_delta_spr_barchart`

---

## §7. _create_delta_spr_barchart()

**Returns:** `QFrame` (white, border-radius 12px, shadow)

Lower-right panel (Tab 0 in bottom tabs).

### Layout

```
barchart_widget
└─ QVBoxLayout
     ├─ header
     │    ├─ "ΔSPR (RU) — Response Between Cursors"
     │    ├─ delta_spr_lock_btn  (checkable, "🔓 Unlock" / "🔒 Locked")
     │    └─ "⟲" reset
     └─ delta_spr_barchart (pg.PlotWidget, fixed height 220px)
          ├─ delta_spr_bars[0..3]   (pg.BarGraphItem per channel)
          └─ delta_spr_labels[0..3] (pg.TextItem value labels above bars)
```

- Y axis: `"ΔSPR (RU)"`, initial range `[0, 100]`
- X ticks: `[(0,'Ch A'), (1,'Ch B'), (2,'Ch C'), (3,'Ch D')]`
- Bar colors: `CHANNEL_COLORS` or `CHANNEL_COLORS_COLORBLIND`

---

## §8. _create_alignment_stubs()

Creates all alignment widgets as invisible, unparented dummies so mixin `hasattr()` guards pass without a visible panel:

```python
self.alignment_panel = QWidget()          # hide()/.show() calls are safe
self.alignment_title = QLabel()
self.alignment_flags_display = QLabel()
self.alignment_ref_combo = QComboBox()    # items: Global/None/Ch A/B/C/D
                                           # connected: _on_cycle_ref_changed
self.alignment_shift_input = QLineEdit("0.0")  # connected: _on_shift_input_changed
self.alignment_shift_slider = QSlider(Qt.Horizontal)  # range -200..200
                                                        # connected: _on_shift_slider_changed
# Plus _alignment_ch_btns dict and _AlignChannelProxy
```

---

## §9. Cycle Notes Panel

Replaced `QTabWidget` (Flags + Notes) with a plain `QFrame` notes panel:

```python
self.details_tab_widget = QFrame()        # reuses old name for compat
self.cycle_notes_edit = QTextEdit()       # read-only in current phase
self.cycle_notes_edit.setMaximumHeight(100)
```

- Hidden by default; shown in `_update_details_panel()` only when selected cycle has a non-empty note
- Flags tracking removed from UI

---

## §10. Widget Quick Reference

| Attribute | Type | Source |
|-----------|------|--------|
| `edits_timeline_graph` | pg.PlotWidget | create_content() |
| `edits_primary_graph` | pg.PlotWidget | create_content() |
| `details_tab_widget` | QFrame | create_content() (plain notes, not QTabWidget) |
| `cycle_notes_edit` | QTextEdit | create_content() |
| `empty_state_widget` | QWidget | _create_table_panel() |
| `cycle_data_table` | QTableWidget | _create_table_panel() |
| `filter_combo` | QComboBox | _create_table_panel() |
| `search_box` | QLineEdit | _create_table_panel() |
| `columns_btn` | QPushButton | _create_table_panel() |
| `meta_method` | QLabel | _create_metadata_panel() |
| `meta_total_cycles` | QLabel | _create_metadata_panel() |
| `meta_cycle_types` | QLabel | _create_metadata_panel() |
| `meta_conc_range` | QLabel | _create_metadata_panel() |
| `meta_date` | QLabel | _create_metadata_panel() |
| `meta_operator` | QLabel | _create_metadata_panel() |
| `meta_device` | QLabel | _create_metadata_panel() |
| `meta_calibration` | QLabel | _create_metadata_panel() |
| `meta_transmission_file` | QLabel | _create_metadata_panel() |
| `meta_star_buttons` | list[QPushButton] | _create_metadata_panel() |
| `meta_tags_pills` | QWidget | _create_metadata_panel() |
| `meta_tag_input` | QLineEdit | _create_metadata_panel() |
| `sensor_input` | QLineEdit | _create_metadata_panel() |
| `alignment_start_time` | QLabel | _create_active_selection() header |
| `alignment_end_time` | QLabel | _create_active_selection() header |
| `cycle_context_label` | QLabel | _create_active_selection() header |
| `edits_channel_buttons` | dict[str, QPushButton] | _create_active_selection() |
| `delta_spr_start_cursor` | pg.InfiniteLine | _create_active_selection() |
| `delta_spr_stop_cursor` | pg.InfiniteLine | _create_active_selection() |
| `delta_spr_lock_btn` | QPushButton | _create_delta_spr_barchart() |
| `delta_spr_barchart` | pg.PlotWidget | _create_delta_spr_barchart() |
| `delta_spr_bars` | list[pg.BarGraphItem] | _create_delta_spr_barchart() |
| `delta_spr_labels` | list[pg.TextItem] | _create_delta_spr_barchart() |
| `edits_smooth_label` | QLabel | _create_tools_panel() |
| `edits_smooth_slider` | QSlider | _create_tools_panel() |
| `alignment_panel` | QWidget (stub) | _create_alignment_stubs() |
| `alignment_ref_combo` | QComboBox (stub) | _create_alignment_stubs() |
| `alignment_shift_input` | QLineEdit (stub) | _create_alignment_stubs() |
| `alignment_shift_slider` | QSlider (stub) | _create_alignment_stubs() |

---

## §11. Key Gotchas

1. **Channel button colors**: Use hardcoded `{"A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}`. `_active_channel_colors()` returns `"k"` for Ch A (matplotlib shorthand) — invalid CSS.
2. **`edits_primary_graph` created in `create_content()`**, not in `_create_active_selection()` — passed in to avoid pyqtgraph ownership issues.
3. **InteractiveSPRLegend positioning**: Uses `QTimer.singleShot(200ms)` — immediate positioning fails because layout hasn't settled.
4. **Alignment panel removed but stubs required** — `_alignment_mixin.py` uses `hasattr()` guards but existing mixin code calls `.show()`, `.hide()`, `.addItems()`, `.setCurrentText()` on these widgets directly. Stubs must expose the same API.
5. **Rating/tags require a file to be loaded** — `_find_index_entry_for_file(None)` returns `None` immediately; star/tag UI shows default state (0 stars, no tags).

---

**Last Updated:** February 24, 2026
**Codebase Version:** Affilabs.core v2.0.5 beta
