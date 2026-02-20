# UI Design System — Affilabs.core v2.0.5

> **Authority**: This document defines the rules. When in doubt, follow this, not a legacy widget.
> **Source of truth for styles**: [`affilabs/ui_styles.py`](../../affilabs/ui_styles.py) — `Colors`, `Fonts`, `Dimensions`, `Spacing`, `Radius` classes.

---

## 1. Design Principles

| Principle | What it means in practice |
|-----------|--------------------------|
| **Data first** | Controls exist to serve the sensorgram. Never let chrome compete with data. |
| **State is visible** | Every interactive element must communicate its current state without ambiguity. |
| **Hardware feedback is immediate** | Status changes (connect, calibrate, record) must reflect in the UI within one UI timer tick (100ms). |
| **Sidebar is secondary** | The main content area (graphs) always has visual dominance. Sidebar is a control panel, not a page. |
| **Destructive actions require confirmation** | Deleting cycles, clearing data, regeneration — always confirm. Never fire on single click. |

---

## 2. Color Palette

All colors are defined in `Colors` class in [`affilabs/ui_styles.py`](../../affilabs/ui_styles.py). **Never hardcode hex values in widget files.**

### Base Colors

| Token | Value | Use |
|-------|-------|-----|
| `Colors.PRIMARY_TEXT` | `#1D1D1F` | Body text, labels, button text |
| `Colors.SECONDARY_TEXT` | `#86868B` | Captions, placeholders, disabled text |
| `Colors.BACKGROUND_WHITE` | `#FFFFFF` | Widget backgrounds, inputs |
| `Colors.BACKGROUND_LIGHT` | `#F5F5F7` | Page background, scroll areas |

### Semantic Colors

| Token | Value | Use |
|-------|-------|-----|
| `Colors.SUCCESS` | `#34C759` | Connected, calibrated, recording active |
| `Colors.WARNING` | `#FF9500` | Non-critical alerts, nearing limits |
| `Colors.ERROR` | `#FF3B30` | Errors, disconnected, failed calibration |
| `Colors.INFO` | `#007AFF` | Primary action, focused inputs, links |

### Button Colors

| Token | Value | Use |
|-------|-------|-----|
| `Colors.BUTTON_PRIMARY` | `#1D1D1F` | Primary action buttons (dark fill) |
| `Colors.BUTTON_PRIMARY_HOVER` | `#3A3A3C` | Hover state |
| `Colors.BUTTON_PRIMARY_PRESSED` | `#48484A` | Pressed state |
| `Colors.BUTTON_DISABLED` | `#86868B` | Disabled state text |

### Overlay Colors (for backgrounds and borders)

Use these instead of `rgba()` literals:

| Token | Opacity | Use |
|-------|---------|-----|
| `OVERLAY_LIGHT_3` | 3% | Subtle card backgrounds |
| `OVERLAY_LIGHT_6` | 6% | Hover backgrounds for secondary buttons |
| `OVERLAY_LIGHT_8` | 8% | Collapsible header hover |
| `OVERLAY_LIGHT_10` | 10% | Borders, dividers, groove tracks |
| `OVERLAY_LIGHT_20` | 20% | Input borders, scrollbar handles |
| `OVERLAY_LIGHT_30` | 30% | Stronger borders on hover |

### Channel Colors

Defined in both `ui_styles.py` (sensorgram curves) and `ui_constants.ChannelColors` (bar charts/tables).

| Channel | Sensorgram curve | Table/chart |
|---------|-----------------|------------|
| A | `rgb(0, 0, 0)` Black | `#007AFF` Blue |
| B | `rgb(255, 0, 81)` Red | `#FF9500` Orange |
| C | `rgb(0, 174, 255)` Blue | `#34C759` Green |
| D | `rgb(0, 150, 80)` Green | `#AF52DE` Purple |

> **Note**: Curve colors (black/red/blue/green) and chart colors differ intentionally — curves need high contrast on white graph backgrounds; charts use iOS system palette for semantic distinction.

---

## 3. Typography

All font families defined in `Fonts` class. Use the stylesheet builders in `ui_styles.py` instead of writing font CSS manually.

| Builder | Use |
|---------|-----|
| `title_style(font_size=20)` | Section titles, dialog headers — SF Pro Display, 600 weight |
| `section_header_style(font_size=11)` | Uppercase category headers — 700 weight, tracked |
| `label_style(font_size, color, weight)` | Body labels — SF Pro Text |
| `text_edit_log_style()` | Log output areas — monospace, 11px |

### Font Sizes (in pixels unless noted)

| Role | Size | Weight |
|------|------|--------|
| Section header (caps) | 11px | 700 |
| Body / control labels | 12–13px | 400–500 |
| Collapsible headers | 14px | 600 |
| Section titles | 20px | 600 |
| Table cells | 9pt (system) | 400 |
| Channel checkboxes | 9pt | bold |

### Rules
- **Never use px and pt in the same widget** — pick one and be consistent within a file.
- Default to **13px** for anything the user reads in the sidebar.
- Use `get_font(size, bold)` when setting `QFont` objects directly (returns Segoe UI on Windows).

---

## 4. Spacing & Layout

All spacing is based on an **8px grid**. Defined in `Spacing` class.

| Token | Value | Use |
|-------|-------|-----|
| `Spacing.XS` | 4px | Tight internal padding (icon + text gap) |
| `Spacing.SM` | 8px | Default widget spacing in `setSpacing()` |
| `Spacing.MD` | 12px | Section internal padding |
| `Spacing.LG` | 16px | Between sections, outer margins |
| `Spacing.XL` | 20px | Large group separators |
| `Spacing.XXL` | 24px | Dialog internal margins |

### Layout Rules

1. **Sidebar panels**: outer margin = `Spacing.LG` (16px), internal spacing = `Spacing.SM` (8px)
2. **Dialogs**: outer margin = `Spacing.XXL` (24px), button row spacing = `Spacing.SM`
3. **Never use `setContentsMargins(0, 0, 0, 0)` on visible panels** — always give at least SM padding
4. **`CollapsibleBox` sections**: 8px between boxes, 12px internal

---

## 5. Border Radius

Defined in `Radius` class.

| Token | Value | Use |
|-------|-------|-----|
| `Radius.SM` | 4px | Small badges, tight contexts |
| `Radius.MD` | 8px | Standard containers, cards, most buttons |
| `Radius.LG` | 12px | Large cards, dialog panels |
| `Radius.XL` | 20px | Pill buttons (channel toggles) |
| `Radius.FULL` | 9999 | Perfect circles |

**Rule**: Use `Radius.MD` (8px) for any new button or container unless there is a specific reason not to.

---

## 6. Button Variants

Use the stylesheet builders — never write button CSS from scratch.

| Builder | Appearance | Use |
|---------|-----------|-----|
| `primary_button_style()` | Dark fill, white text | Primary action per screen |
| `secondary_button_style()` | White fill, dark border | Secondary actions |
| `get_button_style("standard")` | Light gray fill | Toolbar/header utilities |
| `get_button_style("success")` | Green fill | Confirm, apply actions |
| `get_button_style("error")` | Red fill | Destructive confirm |
| `get_button_style("text")` | Transparent | Ghost/text-only actions |
| `get_clear_button_style("neutral")` | Subtle gray | Clear/reset actions |
| `get_clear_button_style("danger")` | Red tint | Clear flags, delete |
| `segmented_button_style(position)` | Grouped toggle | P-pol / S-pol, mode selectors |
| `get_channel_button_style(color)` | White + colored border | Channel A/B/C/D toggles |

### Button Height Rules

| Context | Height |
|---------|--------|
| Toolbar main buttons (Power, Record) | `Dimensions.HEIGHT_BUTTON_XL` = 40px |
| Standard sidebar actions | `Dimensions.HEIGHT_BUTTON_STD` = 32px |
| Compact table/queue actions | `Dimensions.HEIGHT_BUTTON_SM` = 24px |
| Input-adjacent buttons | Same height as input = 36px |

### Button State Rules

Every button must have explicit styles for: **default → hover → pressed → disabled**.
- **Never leave `:disabled` unstyled** — it defaults to OS grey, which breaks the design
- `setEnabled(False)` must visually communicate why (tooltip or adjacent label)

---

## 7. Input Fields

| Builder | Widget | Use |
|---------|--------|-----|
| `line_edit_style()` | `QLineEdit` | Text input, comments |
| `spinbox_style()` | `QSpinBox` / `QDoubleSpinBox` | Numeric inputs (integration time, intensity) |
| `combo_box_style()` | `QComboBox` | Dropdowns (cycle type, reference channel) |
| `slider_style()` | `QSlider` | EMA smoothing, range selectors |

### Input Rules

1. Height: `Dimensions.HEIGHT_INPUT` = 36px for all standard inputs
2. Focus ring: `Colors.INFO` (#007AFF) border on focus — use `spinbox_style()` / `line_edit_style()` which include this
3. **Disabled inputs**: background → `OVERLAY_LIGHT_3`, text → `SECONDARY_TEXT`
4. **Validation**: show `Colors.ERROR` border inline; never show a popup for real-time validation
5. Numeric inputs adjacent to units (e.g., "ms", "mL/min"): put unit label to the right, same row

---

## 8. Cards & Containers

| Builder | Use |
|---------|-----|
| `card_style()` | Light gray card — status panels, info groups |
| `get_container_style(elevated=True)` | White surface with border — dialog sections |
| `group_box_style()` | Labeled group boxes — hardware diagnostic sections |
| `collapsible_header_style()` | Toggle buttons for `CollapsibleBox` headers |
| `create_card_shadow()` | Drop shadow effect — floating panels |

### Container Rules

1. **Never nest two `card_style()` containers** — use internal spacing instead
2. `CollapsibleBox` is the standard pattern for grouping related sidebar controls
3. Dialogs use `get_container_style(elevated=True)` for each logical section
4. No visible outer border on the sidebar itself — it uses background contrast

---

## 9. Status Indicators

| Pattern | How to implement |
|---------|-----------------|
| Hardware connected | Green dot (●) + label — use `status_indicator_style(Colors.SUCCESS)` |
| Hardware disconnected | Gray dot (●) — use `status_indicator_style(Colors.SECONDARY_TEXT)` |
| Error / failed | Red dot (●) — use `status_indicator_style(Colors.ERROR)` |
| Warning | Orange dot (●) — use `status_indicator_style(Colors.WARNING)` |
| In-progress / searching | Animated ellipsis in label text — no spinner widget |

### Power Button States

| State | Visual |
|-------|--------|
| `disconnected` | Red/gray, text = "Connect" |
| `searching` | Orange + animated "..." suffix |
| `connected` | Green, text = "Connected" |

---

## 10. Cycle Type Colors

Defined in `CycleTypeStyle.MAP` in [`affilabs/widgets/ui_constants.py`](../../affilabs/widgets/ui_constants.py). Used in queue tables and badge pills.

| Type | Abbrev | Color |
|------|--------|-------|
| Baseline | BL | `#007AFF` Blue |
| Association | AS | `#34C759` Green |
| Dissociation | DS | `#5856D6` Indigo |
| Immobilization | IM | `#AF52DE` Purple |
| Regeneration | RG | `#FF3B30` Red |
| Blocking | BK | `#FF2D55` Pink |
| Binding / Sample | BN/SM | `#FF9500` Orange |
| Wash | WS | `#00C7BE` Teal |
| Equilibration | EQ | `#86868B` Gray |
| Other / Custom | OT/CU | `#636366` Dark gray |

---

## 11. Dividers & Separators

| Builder | Use |
|---------|-----|
| `separator_style()` | 1px horizontal rule between sections (max-height: 1px) |
| `divider_style()` | Heavier divider for structural separation |

### Rules

- Use separators between logical groups within a panel, not between every item
- Prefer spacing (`addSpacing(8)`) over separator lines for close items
- Never add a separator at the very top or bottom of a panel

---

## 12. Scrollbars

Apply `scrollbar_style()` to any `QScrollArea`. Rules:
- Width: 10px, background: `BACKGROUND_LIGHT`
- Handle: `OVERLAY_LIGHT_20`, hover: `OVERLAY_LIGHT_30`
- No arrow buttons (height: 0px) — macOS-style scroll behavior

---

## 13. What NOT to Do

| Anti-pattern | Correct approach |
|-------------|-----------------|
| Hardcode `#007AFF` in a widget file | Import `Colors.INFO` from `ui_styles.py` |
| Write inline QSS longer than 10 lines | Use or add a builder function in `ui_styles.py` |
| Use a `QDialog` with `exec()` for non-blocking flows | Use `show()` with non-modal dialogs |
| Call `self.main_window.widget.setEnabled()` from a service | Emit a signal; let a presenter handle UI state |
| Add a new widget without defining all 4 button states | Always include `:hover`, `:pressed`, `:disabled` |
| Use `setFixedWidth()` on sidebar content | Use `setMaximumWidth()` — sidebar is resizable |
| Create a new color not in the palette | Add it to `Colors` with a name, then use the name |
| Use `QMessageBox` for status feedback during acquisition | Use the intelligence bar or status label — non-blocking |
