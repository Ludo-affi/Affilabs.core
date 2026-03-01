# Accessibility Panel — Feature Reference Specification

**Component:** `affilabs/widgets/accessibility_panel.py`
**Launched from:** Icon rail — eye button (top group, between User and Timer buttons)
**Registered on:** `AffilabsCoreUI` as `self.accessibility_panel`
**Version introduced:** v2.0.5-beta

---

## 1. Overview

`AccessibilityPanel` is a fixed-width (380 px) `QFrame` injected into the main horizontal layout immediately to the right of the icon rail. Hidden by default, toggled by the eye button. Mutually exclusive with the User panel — opening one closes the other. Opening the panel also collapses the main sidebar via `AffilabsCoreUI.collapse_sidebar()`.

**Four control sections, each propagating to all graphs in real time:**

| Section | Controls | Signal emitted |
|---------|----------|----------------|
| Colour Palette | 7 named palette card buttons | `palette_changed(str, list[str])` |
| Line Style | 3 style cards (Solid / Dashed / Dotted) | `line_style_changed(str, Qt.PenStyle)` |
| Appearance | Active Cycle Dark Mode pill toggle | `dark_mode_changed(bool)` |
| Appearance | Large Text pill toggle | `large_text_changed(bool)` |

**Graphs affected by palette and line style:**
- Full Timeline live sensorgram (`SensorgramGraph`)
- Active Cycle graph (`SegmentGraph`)
- All open `DataWindow` sensorgram and SOI graphs
- `AnalysisTab` overlay graph curves
- **Edits tab**: primary graph curves, channel-end labels, A/B/C/D toggle buttons, delta-SPR bar chart — via `update_barchart_colors(hex_colors=)` — palette only

**Graphs NOT affected (intentional):**
- Spectroscopy / transmission graph
- Any static preview graphs

---

## 2. Colour Palettes

Seven palettes defined in `PALETTES` (module-level `list[tuple[str, str, str, list[str]]]`). Each entry: `(id, display_name, description, [hex_A, hex_B, hex_C, hex_D])`.

| ID | Name | A | B | C | D | Notes |
|----|------|---|---|---|---|-------|
| `default` | Default | `#1D1D1F` | `#FF3B30` | `#007AFF` | `#34C759` | Standard high-contrast |
| `puor` | PuOr (CB-safe) | `#E66101` | `#FDB863` | `#B2ABD2` | `#5E3C99` | Matches `GRAPH_COLORS_COLORBLIND` |
| `wong` | Wong (CB-safe) | `#E69F00` | `#56B4E9` | `#009E73` | `#CC79A7` | Deuteranopia & protanopia safe |
| `tol` | Tol Bright (CB-safe) | `#4477AA` | `#EE6677` | `#228833` | `#CCBB44` | Paul Tol bright — all types |
| `okabe` | Okabe-Ito (CB-safe) | `#0072B2` | `#D55E00` | `#F0E442` | `#000000` | Widely recommended |
| `ibm` | IBM (CB-safe) | `#648FFF` | `#785EF0` | `#DC267F` | `#FE6100` | IBM Design Language |
| `pastel` | Pastel | `#6BAED6` | `#FC8D59` | `#78C679` | `#9E9AC8` | Low-glare displays |

### Palette card UI
- Fixed height 52 px, full-width card, 8 px rounded corners
- Left: 4 × 16 px coloured rounded squares (A B C D) via `_swatch_pixmap()`
- Right: palette name (12 px, 600 weight) + description (10 px, `#86868B`)
- Selected: `rgba(0,122,255,0.08)` bg + 1.5 px `#007AFF` border
- Inactive: `#F5F5F7` bg + transparent border
- Inner layout uses `WA_TransparentForMouseEvents` child widget so entire card is one `QPushButton`
- No tooltip (removed v2.0.5)

### Propagation on selection
`AffilabsCoreUI._on_palette_changed(palette_id, hex_colors)` — called first for edits (fast), then propagates outward (slower `findChildren` walk):

1. Updates `settings.ACTIVE_GRAPH_COLORS` (`{'a': hex, 'b': hex, 'c': hex, 'd': hex}`)
2. Re-styles live sensorgram channel toggle buttons via `get_channel_button_style()`
3. Redraws Full Timeline curves — width 2, current `ACTIVE_LINE_STYLE`
4. Redraws Active Cycle curves — width 2 (4 for selected channel), current line style — **skipped if dark mode active**
5. Refreshes `InteractiveSPRLegend` via `update_colors()` if visible
6. **Edits tab first** — `update_barchart_colors(hex_colors=)`: repaints edits primary graph curves, channel-end labels, A/B/C/D toggle buttons (respecting ref-channel dotted border), and delta-SPR bar chart bars
7. `_propagate_to_datawindow_graphs()` — all live `DataWindow` SOI + sensorgram curves + header toggle buttons
8. `_propagate_to_analysis_tab(hex_colors=)` — `AnalysisTab.overlay_graph_curves`

`plot_helpers._active_channel_colors()` reads `ACTIVE_GRAPH_COLORS` at call time — any graph built with `add_channel_curves()` after a palette change automatically picks up the current palette.

---

## 3. Line Styles

| ID | Label | `Qt.PenStyle` | `.value` |
|----|-------|---------------|----------|
| `solid` | Solid | `SolidLine` | 1 |
| `dashed` | Dashed | `DashLine` | 2 |
| `dotted` | Dotted | `DotLine` | 3 |

Each card: 100 × 56 px. Content: 72 × 14 px line preview pixmap (`_line_preview_pixmap()`) above centred text label.

### Persistence
`settings.ACTIVE_LINE_STYLE` (int). Stored via `pen_style.value` — **not** `int(pen_style)` (raises `TypeError` in PySide6). Graphs initialised after the style change reconstruct with `Qt.PenStyle(settings.ACTIVE_LINE_STYLE)`.

### Propagation on selection
`AffilabsCoreUI._on_line_style_changed(style_id, pen_style)`:
1. Writes `settings.ACTIVE_LINE_STYLE = pen_style.value`
2. Redraws Full Timeline curves — `ACTIVE_GRAPH_COLORS`, width 2, new style
3. Redraws Active Cycle curves — neon colours if dark mode, else `ACTIVE_GRAPH_COLORS`; width 2 (4 for selected channel)
4. `_propagate_line_style_to_datawindow_graphs(pen_style)`
5. `_propagate_to_analysis_tab(pen_style=pen_style)`

Note: edits primary graph and bar chart are **not** updated on line style change — only palette changes touch the edits tab currently.

---

## 4. Active Cycle Dark Mode

Pill toggle (○ off / ● on, 44 × 26 px, checkable `QPushButton`). Emits `dark_mode_changed(bool)`.

**Scope:** Active Cycle graph (`cycle_of_interest_graph`) only.

**Neon colours** (`AffilabsCoreUI._NEON_COLORS`):

| Channel | Colour | Hex |
|---------|--------|-----|
| A | Matrix green | `#00FF41` |
| B | Neon red | `#FF3B30` |
| C | Electric cyan | `#00C8FF` |
| D | Neon yellow | `#FFD60A` |

`AffilabsCoreUI._on_dark_mode_toggled(enabled)`:

**On:** `setBackground(#0D0D0D)`, axis pens → `#444444`, text pens → `#888888`, curves → neon + `ACTIVE_LINE_STYLE`

**Off:** `setBackground(#FFFFFF)`, axis pens → `#000000`, curves → `ACTIVE_GRAPH_COLORS` + `ACTIVE_LINE_STYLE`

**Interaction rules while dark is active:**
- Palette changes update `ACTIVE_GRAPH_COLORS` but do **not** repaint Active Cycle curves (neon takes precedence)
- Line style changes repaint Active Cycle using neon + new style
- Turning dark off restores `ACTIVE_GRAPH_COLORS` + `ACTIVE_LINE_STYLE` correctly

---

## 5. Large Text (Font Scale)

Pill toggle (○ off / ● on, 44 × 26 px, checkable `QPushButton`) in the **Appearance** section, below Active Cycle Dark Mode. Emits `large_text_changed(bool)`. Adds a divider (`QFrame.HLine`) between the two appearance rows.

**Mechanism:** Global `FontScale` singleton in `affilabs/ui_styles.py`. All inline `font-size` values in key UI zones are written as `FontScale.px(base_int)` rather than literal strings.

| Scale | Factor | `FontScale.px(13)` → | `FontScale.px(21)` → |
|-------|--------|----------------------|----------------------|
| Normal (off) | 1.00 | 13 px | 21 px |
| Large (on) | 1.20 | 16 px | 25 px |

**Rules:**
- Scale is read **once at process start** (before `Application` is constructed) via `FontScale.init()` which reads `config/app_prefs.json`
- Toggling writes the new value to `config/app_prefs.json` immediately via `FontScale.save(large: bool)`
- **A restart is required to apply the change.** This is industry-standard behaviour for CSS-defined font sizes — `QApplication.setFont()` does not override explicit `font-size: Npx` strings in stylesheets
- On toggle, a Sparq bubble message appears: *"✓ Large Text enabled. Restart Affilabs.core to apply the change."* (or disabled equivalent)
- Toggle state is initialised from `FontScale.is_large()` at panel construction — reflects the _current active_ scale

**`FontScale` API (`affilabs/ui_styles.py`):**

| Method | Description |
|--------|-------------|
| `FontScale.init()` | Load `app_prefs.json` and set global scale. Call before widget creation. |
| `FontScale.px(base: int) → int` | Return `round(base × scale)`. No-op at Normal (returns base unchanged). |
| `FontScale.is_large() → bool` | True when scale > 1.0. |
| `FontScale.save(large: bool)` | Persist to `config/app_prefs.json`. Merge-writes; does not clobber other prefs. |

**Prefs file:** `config/app_prefs.json` — key `"large_text": true/false`. Created on first save. Other keys are preserved.

**Widget coverage — zones using `FontScale.px()`:**

| File | Elements scaled |
|------|-----------------|
| `affilabs/sidebar_tabs/AL_method_builder.py` | NOW RUNNING badge (13), cycle type badge (14), cycle index (14), countdown (21), next/experiment time labels (13), Build Method button (15), queue table rows (14), column headers (12), footer label (13), Retrieve Method button (13) |
| `affilabs/widgets/injection_action_bar.py` | Header (13), column headers (12), per-channel countdown (15), status labels (14), concentration labels (12), legend strip (13), upcoming injection labels (13), set_role_label_color inline calls (12), countdown lbl init/tick sizes (14) |
| `affilabs/ui_mixins/_panel_builder_mixin.py` | 6 section titles (Primary Cycle View, Processed Data, Goodness of Fit, Mathematical Model, Kinetic Results, Export Data) — all at 18 px |
| `affilabs/widgets/graph_components.py` | `GraphContainer` title label (18 px) |
| `affilabs/tabs/edits/_ui_builders.py` | Analysis title strip (16), Recorded Cycles title (16), empty-state heading (16) |

**Elements NOT scaled (intentional):**
- `AccessibilityPanel` internal chrome (header, section labels at 12–14 px) — avoids recursive dependency

---

## 6. Per-User Preferences

### Behaviour
Colour palette and font size preferences are **saved to and loaded from the active user profile**. Switching users (via the User sidebar panel) will apply that user's stored preferences on next panel open.

A dynamic note at the top of the panel reads:
> *💾 Saved to {username}'s profile — colour and font size are personal.*

If no user is active (edge case at startup), the note falls back to generic text.

### Implementation
- `_refresh_saved_note()` — called each time `toggle()` shows the panel. Reads `sidebar.user_profile_manager.get_current_user()` and updates `self._saved_note` (`QLabel`) text.
- The label is stored as `self._saved_note` (instance var) so it can be updated dynamically without rebuilding the panel.

### Storage
Currently `config/app_prefs.json` is global (not per-user). The note reflects **intent** — per-user storage is the planned migration target. When `user_profile_manager` gains a `get_pref / set_pref` API, load/save calls in `FontScale` and palette selection should be routed through it keyed by `username`.
- `accessibility_panel.py` stylesheet text — same reason
- Spectroscopy / transmission graph axes — pyqtgraph labels, not Qt CSS
- Graph axis tick labels — also pyqtgraph
- Calibration QC dialog — modal, short-lived, not a daily-use surface
- Navigation rail / tab bar labels — compact by design; scaling would break fixed-width layout constraints

---

## 6. Public API

| Method | Returns | Description |
|--------|---------|-------------|
| `toggle()` | `bool` | Toggle visibility. `True` = now visible. |
| `get_active_palette()` | `list[str]` | 4-element hex list for current palette |
| `get_active_line_style()` | `Qt.PenStyle` | Current line style enum |
| `is_dark_mode()` | `bool` | Whether Active Cycle dark mode is on |
| `is_large_text()` | `bool` | Whether Large Text mode is currently active (reads live scale from `FontScale.is_large()`) |
| `set_sidebar(sidebar)` | — | Store sidebar reference (unused internally) |

Internal state: `_active_palette_id: str`, `_active_line_style_id: str`, `_dark_mode: bool`, `_large_text: bool`, `_palette_btns: dict[str, QPushButton]`, `_line_btns: dict[str, QPushButton]`.

---

## 7. Backwards Compatibility

`accessibility_panel.colorblind_check` is a `_DummyCheck` instance with no-op shims for `isChecked()`, `setChecked()`, `blockSignals()`, `toggled`, `stateChanged`. Replaces the removed `sidebar.colorblind_check` without breaking `main.py` connections.

---

## 8. Icon Rail Integration

| Property | Value |
|----------|-------|
| Icon | Eye SVG — rounded outline + iris circle + pupil dot |
| Position | Top group, between User and Timer buttons |
| Mutual exclusion | Opening closes User panel; icon rail tab clicks close both |
| State | Checkable `QPushButton`; active = `#007AFF` icon tint |

---

## 9. Key File References

| File | Role |
|------|------|
| `affilabs/widgets/accessibility_panel.py` | `AccessibilityPanel`, `PALETTES`, `LINE_STYLES`, `_DummyCheck` |
| `affilabs/ui_styles.py` | `FontScale` singleton — `init()`, `px()`, `is_large()`, `save()` |
| `affilabs/widgets/icon_rail.py` | Eye button, mutual exclusion wiring |
| `affilabs/affilabs_core_ui.py` | Signal wiring (lines ~507–512), `_on_palette_changed`, `_on_line_style_changed`, `_on_dark_mode_toggled`, `_on_large_text_changed`, `_NEON_COLORS` |
| `affilabs/plot_helpers.py` | `_active_channel_colors()`, `add_channel_curves()` — read `ACTIVE_GRAPH_COLORS` at call time |
| `affilabs/tabs/edits/_alignment_mixin.py` | `update_barchart_colors()` — edits graph curves, labels, channel buttons, bar chart |
| `affilabs/tabs/edits/_binding_plot_mixin.py` | `_ch_colors()` — reads `ACTIVE_GRAPH_COLORS` at plot time |
| `affilabs/widgets/graphs.py` | `SensorgramGraph` + `SegmentGraph` — `update_colors()`, `update_line_style()` |
| `affilabs/tabs/analysis_tab.py` | `overlay_graph_curves` via `_propagate_to_analysis_tab()` |
| `settings/settings.py` | `ACTIVE_GRAPH_COLORS` (dict), `ACTIVE_LINE_STYLE` (int) |
| `config/app_prefs.json` | Runtime prefs file — `{"large_text": true/false}`. Created on first Large Text toggle. |
| `main.py` | `FontScale.init()` called before `Application(sys.argv)` — before any widget is created |
