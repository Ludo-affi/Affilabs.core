# EXPERIMENT_BROWSER_FRS — Experiment History Browser Dialog

**Planned source:** `affilabs/dialogs/experiment_browser_dialog.py`  
**Trigger widget:** `history_btn` (QPushButton) in `UIBuildersMixin._create_table_panel()`  
**Reads from:** `ExperimentIndex` → `~/Documents/Affilabs Data/experiment_index.json`  
**Opens files via:** `QDesktopServices.openUrl()`  
**Status:** Implemented (v2.0.5 beta)  
**Version:** Affilabs.core v2.0.5+

---

## 1. Purpose

Replace the need to navigate `~/Documents/Affilabs Data/` in Windows Explorer after every experiment. The dialog gives users a searchable, time-grouped list of all past recording sessions — visible metadata (chip, user, duration, cycles) without opening any file.

**Primary use case:** User finishes an experiment, opens Edits tab, wants to load a recording from last week. Clicks "History", scans the list, double-clicks the row → file loads directly into the Edits tab without a separate file picker.

---

## 2. Entry Point

### Trigger button location

`UIBuildersMixin._create_table_panel()` — `controls_layout`, immediately after the existing `load_btn`:

```python
history_btn = QPushButton("🕐 History")
history_btn.setFixedHeight(28)
# Same style as load_btn
history_btn.clicked.connect(self._open_experiment_browser)
controls_layout.addWidget(history_btn)  # inserted after load_btn
```

`self._open_experiment_browser()` is implemented in `DataLoaderMixin` (or `DataMixin` — whichever owns `_load_data_from_excel_with_path_tracking`):

```python
def _open_experiment_browser(self):
    from affilabs.dialogs.experiment_browser_dialog import ExperimentBrowserDialog
    dlg = ExperimentBrowserDialog(
        parent=self.main_window,
        user_manager=self.user_manager,
    )
    dlg.file_selected.connect(self._load_data_from_path)
    dlg.exec()
```

`file_selected` carries the absolute `Path` to the `.xlsx` file. `_load_data_from_path(path)` is a thin wrapper that calls the existing Excel-load pipeline with the given path instead of showing a file picker.

---

## 3. Dialog Specification

### Window properties

| Property | Value |
|---|---|
| Type | `QDialog` (modal) |
| Title | `"Experiment History"` |
| Size | `680 × 540 px` (fixed minimum; resizable) |
| Background | `Colors.BACKGROUND_LIGHT` (`#F5F5F7`) |

### Signal

```python
file_selected = Signal(Path)  # Emitted on double-click or "Load" button
```

---

## 4. Layout

```
QDialog (680 × 540)
├── Header bar (QFrame, white, bottom border 1px #E5E5EA)
│   ├── QLabel "Experiment History"  [16px bold, #1D1D1F]
│   └── [×] close button (right-aligned)
│
├── Filter bar (QFrame, white, padding 8px 12px)
│   ├── QLineEdit  🔍 "Search user, chip, notes…"  [flex]
│   ├── QPushButton "All"   [pill, selected=blue]
│   ├── QPushButton "Mine"  [pill]
│   ├── QPushButton "7d"    [pill]
│   └── QPushButton "30d"   [pill]
│
├── QScrollArea  (flex, #F5F5F7 background)
│   └── QWidget (entries container, QVBoxLayout, spacing=0)
│       ├── Section header "Today"        [12px, #86868B, 28px height]
│       ├── ExperimentRowWidget           [white card, 56px]
│       ├── ExperimentRowWidget
│       ├── Section header "This week"
│       ├── ExperimentRowWidget
│       ├── …
│       └── Empty-state label (shown when no entries match)
│
└── Footer bar (QFrame, white, top border 1px #E5E5EA, 48px)
    ├── QLabel  "N experiments"  [#86868B, 11px]
    └── QPushButton "Load Selected"  [primary button, disabled until row selected]
```

---

## 5. ExperimentRowWidget

Each row is a `QFrame` (not a `QTableWidget` row) — this allows custom hover/selection styling not achievable with `QTableWidget`.

### Visual states

| State | Background | Border |
|---|---|---|
| Default | `#FFFFFF` | none |
| Hover | `#F0F4FF` | none |
| Selected | `#E3EDFF` | `1px solid #007AFF` (left accent: `3px solid #007AFF`) |

### Row layout (56px height, 12px horizontal padding)

```
[📄 icon 20px] [left block: flex]                    [Open ↗ btn 60px]
                ├── filename (13px bold #1D1D1F) 
                └── user · chip · Xmin · Y cycles   (11px #86868B)
```

- **filename**: basename without extension, truncated with `…` if > 42 chars
- **metadata line**: `lucia  ·  FLMT09788  ·  47 min  ·  8 cycles` — missing fields shown as `—`
- **"Open ↗" button**: 60×24px, `#F5F5F7` bg, `#007AFF` text, `6px` radius. Triggers `QDesktopServices.openUrl()` (opens in Excel). Does **not** emit `file_selected` — that's for loading into Edits.

### Double-click behaviour

Double-clicking anywhere on the row (except the "Open ↗" button) is equivalent to clicking "Load Selected" — emits `file_selected` and closes the dialog.

---

## 6. Section Headers (Time Buckets)

Entries are grouped by recency of `date` field relative to today at dialog open time:

| Bucket | Condition |
|---|---|
| Today | `date == today` |
| This week | `today - 7d < date < today` |
| This month | `today - 30d < date ≤ today - 7d` |
| Earlier | `date ≤ today - 30d` |

Section header style: `QLabel`, 12px, `Colors.SECONDARY_TEXT` (`#86868B`), uppercase, `8px` top padding, `4px` bottom padding, left-padded 12px. Background matches scroll area (`#F5F5F7`).

Empty buckets are omitted entirely (no header shown if no entries in that bucket).

---

## 7. Search & Filter

### Search box

- `QLineEdit`, `textChanged` connected to `_apply_filter()` — **live, no button press needed**
- Matches case-insensitively against: `user`, `chip_serial`, `file` (basename only), `notes`
- Placeholder: `"Search user, chip, notes…"`
- Clears on Escape key

### Quick filter pills

Four `QPushButton` instances styled as pill toggles (single-select):

| Label | Filter logic |
|---|---|
| All | No date/user filter |
| Mine | `user == current_user` (from `user_manager.get_current_user()`) |
| 7d | `date >= today - 7d` |
| 30d | `date >= today - 30d` |

Active pill: `background: #007AFF; color: white; border: none`  
Inactive pill: `background: #E5E5EA; color: #1D1D1F; border: none`  
Height: 26px, radius: 13px (full-round), font: 11px

Pill filter and search box are ANDed.

### Empty state

When no entries match, show centered in the scroll area:

```
[🔬 large icon, 40px, #C7C7CC]
"No matching experiments"
"Try a different search or time range."
```
Both labels: `#86868B`, centered, 13px regular / 11px secondary.

No-index state (file doesn't exist yet):

```
[📋 icon]
"No experiments recorded yet"
"Your experiments will appear here after your first recording."
```

---

## 8. Footer: "Load Selected" button

- Disabled (greyed) when no row is selected
- Enabled on single row click/keyboard selection
- On click: emits `file_selected(resolved_absolute_path)`, closes dialog
- Label updates to `"Load  filename.xlsx"` (truncated) when a row is selected

---

## 9. File path resolution

Entries store paths relative to `~/Documents/Affilabs Data/`. Resolution at open/load time:

```python
base = Path.home() / "Documents" / "Affilabs Data"
abs_path = base / entry["file"]
```

If `abs_path` is absolute (fallback for files saved outside standard tree), use as-is.

If resolved path does not exist (`abs_path.exists()` is False):
- Row shown with `#86868B` dimmed text + strikethrough on filename
- "Open ↗" button disabled; tooltip: `"File not found: {abs_path}"`
- "Load Selected" button disabled for this row regardless

---

## 10. Keyboard navigation

| Key | Behaviour |
|---|---|
| `↑` / `↓` | Move selection between rows (skip section headers) |
| `Enter` | Equivalent to "Load Selected" |
| `Escape` | Close dialog without loading |
| `Ctrl+F` | Focus search box |

---

## 11. Style tokens used

All from `affilabs/ui_styles.py` — no inline hex values in implementation:

| Element | Token |
|---|---|
| Dialog background | `Colors.BACKGROUND_LIGHT` |
| Row background (default) | `Colors.BACKGROUND_WHITE` |
| Row background (hover) | `rgba(0,122,255,0.06)` → `Colors.OVERLAY_LIGHT_6` (blue tint) |
| Row background (selected) | `rgba(0,122,255,0.12)` → `Colors.OVERLAY_LIGHT_10` (blue tint approx) |
| Selected left accent | `Colors.INFO` (`#007AFF`), 3px |
| Section header text | `Colors.SECONDARY_TEXT` |
| Primary text | `Colors.PRIMARY_TEXT` |
| "Open ↗" button text | `Colors.INFO` |
| Footer border | `Colors.OVERLAY_LIGHT_10` |
| Disabled row text | `Colors.SECONDARY_TEXT` + strikethrough |

---

## 12. Out of scope for v1

- Editing `notes` field inline (future — double-click notes cell to edit)
- Deleting index entries from the dialog
- Sorting by column header (entries always newest-first)
- Bulk-open multiple files
- Thumbnail preview of sensorgram in a hover popover
