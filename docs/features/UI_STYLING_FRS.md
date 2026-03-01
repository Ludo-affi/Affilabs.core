# UI Styling System — Functional Requirements Specification

**Source:** `affilabs/ui_styles.py` (1287 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Centralized design system for the entire application UI. Apple-inspired aesthetic (SF Pro typography, system colors, rounded corners). **Light mode only** — no dark mode implementation yet.

---

## 2. Design Token Classes

### 2.1 `Colors`

| Token | Value | Usage |
|-------|-------|-------|
| `PRIMARY_TEXT` | `#1D1D1F` | Main text |
| `SECONDARY_TEXT` | `#6E6E73` | Secondary text |
| `TERTIARY_TEXT` | `#86868B` | Subtle text |
| `BACKGROUND_WHITE` | `#FFFFFF` | Light backgrounds |
| `BACKGROUND_LIGHT` | `#F5F5F7` | Subtle backgrounds |
| `BORDER_DEFAULT` | `#D2D2D7` | Default borders |
| `BORDER_LIGHT` | `#E5E5EA` | Light borders |
| `SUCCESS` | `#34C759` | Green status |
| `WARNING` | `#FF9500` | Amber status |
| `ERROR` | `#FF3B30` | Red status |
| `INFO` | `#007AFF` | Blue accent |
| `BUTTON_PRIMARY` | `#1D1D1F` | Dark button background |

### 2.2 `Fonts`

| Token | Value |
|-------|-------|
| `SYSTEM` | `"SF Pro Display", "Segoe UI", system-ui` |
| `DISPLAY` | `"SF Pro Display", "Segoe UI", sans-serif` |
| `MONOSPACE` | `"SF Mono", "Cascadia Code", "Consolas", monospace` |

Font weights: `REGULAR = 400`, `MEDIUM = 500`, `SEMIBOLD = 600`, `BOLD = 700`

### 2.3 `Dimensions`

| Token | Value | Purpose |
|-------|-------|---------|
| `BORDER_RADIUS` | 10 px | Default card radius |
| `BORDER_RADIUS_SM` | 6 px | Small elements |
| `BUTTON_HEIGHT` | 32 px | Standard button |
| `BUTTON_HEIGHT_SM` | 28 px | Compact button |
| `MARGIN` | 16 px | Standard margin |
| `SPACING` | 8 px | Standard spacing |

### 2.4 `Spacing` (8px base unit)

| Token | Value |
|-------|-------|
| `XS` | 4 px |
| `SM` | 8 px |
| `MD` | 12 px |
| `LG` | 16 px |
| `XL` | 20 px |
| `XXL` | 24 px |

### 2.5 `Radius`

| Token | Value |
|-------|-------|
| `NONE` | 0 |
| `SM` | 4 px |
| `MD` | 8 px |
| `LG` | 12 px |
| `XL` | 16 px |
| `FULL` | 9999 px |

---

## 3. Stylesheet Builder Functions (26 total)

### 3.1 Core Styles

| Function | Parameters | Returns |
|----------|-----------|---------|
| `label_style` | `font_size, color, weight, font_family` | Label CSS |
| `section_header_style` | `font_size=12, uppercase=True` | Section header CSS |
| `title_style` | `font_size=20` | Title CSS |
| `card_style` | `background, radius` | Card/frame CSS |
| `separator_style` | — | Horizontal divider CSS |
| `divider_style` | — | Divider CSS |
| `scrollbar_style` | — | Scroll area + scrollbar CSS |

### 3.2 Button Styles

| Function | Parameters | Returns |
|----------|-----------|---------|
| `primary_button_style` | `height` | Dark primary button CSS |
| `secondary_button_style` | `height, align` | White bordered button CSS |
| `get_button_style` | `variant="standard"` | Multi-variant button factory |
| `get_clear_button_style` | `variant="neutral"` | Clear/reset button CSS |

### 3.3 Input Styles

| Function | Parameters | Returns |
|----------|-----------|---------|
| `checkbox_style` | — | Modern checkbox (base64 SVG checkmark) |
| `radio_button_style` | — | Modern radio CSS |
| `slider_style` | — | Horizontal slider CSS |
| `spinbox_style` | — | QSpinBox CSS |
| `combo_box_style` | `width=None` | QComboBox CSS |
| `line_edit_style` | — | QLineEdit CSS |
| `segmented_button_style` | `position` | Segmented control (left/middle/right) |

### 3.4 Container Styles

| Function | Parameters | Returns |
|----------|-----------|---------|
| `get_container_style` | `elevated=True` | Container/card CSS |
| `group_box_style` | — | QGroupBox CSS |
| `text_edit_log_style` | — | Log output area CSS |
| `collapsible_header_style` | — | Collapsible section header CSS |

### 3.5 Utility

| Function | Parameters | Returns |
|----------|-----------|---------|
| `hex_to_rgb` | `hex_color: str` | `(r, g, b)` tuple |
| `status_indicator_style` | `color` | Status dot CSS |
| `create_card_shadow` | — | `QGraphicsDropShadowEffect` (blur=8, offset=0,2) |

---

## 4. Channel-Specific Styles

| Function | Purpose |
|----------|---------|
| `get_channel_button_style(active_color)` | Channel toggle button |
| `get_channel_button_ref_style(active_color)` | Reference channel variant |
| `get_active_cycle_channel_button_style(active_color)` | Active cycle channel button |
| `get_live_checkbox_style()` | Live mode checkbox |
| `get_channel_checkbox_style(channel, inverted=False)` | Per-channel A/B/C/D colored checkbox |
| `apply_channel_checkbox_style(checkbox, channel, inverted=False)` | Apply channel style to existing widget |

### Channel Colors

| Channel | Color |
|---------|-------|
| A | `rgb(29, 29, 31)` (near-black) |
| B | `rgb(255, 0, 81)` (magenta) |
| C | `rgb(0, 174, 255)` (cyan) |
| D | `rgb(0, 150, 80)` (green) |

---

## 5. Font Utilities

| Function | Purpose |
|----------|---------|
| `get_font(size=9, bold=False, weight=-1)` | Create configured `QFont` |
| `get_segment_checkbox_font()` | 9pt bold font for channel checkboxes |

---

## 6. FontScale — Accessibility Font Scaling

**`FontScale`** class at line 1222 — 2-tier font scale (Normal / Large Text).

| Method | Purpose |
|--------|---------|
| `init()` | Load scale from `config/app_prefs.json` (call once at startup) |
| `px(base: int) -> int` | Scale pixel value (1.0× normal, 1.20× large) |
| `is_large() -> bool` | Check if Large Text is active |
| `save(large: bool)` | Persist preference (requires app restart) |

Persists to `config/app_prefs.json`. The `px()` method is used throughout the UI to scale font sizes and dimensions.

---

## 7. Dark Mode Status

**Not implemented.** The design system is light-mode only. All color tokens assume white/light backgrounds. A dark mode implementation would require:
- Dark variants of all `Colors` tokens
- Theme-switching mechanism in `FontScale` or a new `ThemeManager`
- Runtime stylesheet reload
- pyqtgraph plot background/foreground color switching
