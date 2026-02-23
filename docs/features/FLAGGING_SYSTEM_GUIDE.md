# FlagManager FRS

**Feature Requirement Specification: Flag & Marker Management System**  
Document Status: ✅ Code-verified  
Last Updated: February 19, 2026  
Source File: `affilabs/managers/flag_manager.py` (1291 lines)

> **NOTE:** This document replaces the legacy "Channel-Specific Flagging System" guide which described a now-removed per-widget storage approach. The current system uses a centralized `FlagManager` class as the single source of truth.

---

## §1. Purpose & Context

**What This Is:**  
`FlagManager` is the single source of truth for all flag markers and timeline annotations in the application. It manages two separate contexts:

1. **Live context (`context='live'`)** — Flags placed by SOFTWARE during acquisition (injection detection, cycle events). Users CANNOT manually add flags on the live graph.
2. **Edits context (`context='edits'`)** — Flags placed by USER in the Edits tab. User can add, move (arrow-key nudge with data-point snap), and delete flags.

**Design Principle:**  
Separation of annotation from acquisition. During live acquisition, the user's focus stays on the experiment, not annotation. Precise flag placement happens in the Edits tab post-acquisition.

**Architecture Layer:** Manager (Business Logic) — `affilabs/managers/flag_manager.py`

---

## §2. Domain Models

### 2.1 Flag Domain Model

**File:** `affilabs/domain/flag.py`

**Base class:** `Flag` (dataclass)  
**Subclasses:** `InjectionFlag`, `WashFlag`, `SpikeFlag`

**Created via factory:** `create_flag(flag_type, channel, time, spr, is_reference=False)`

**Common Flag attributes:**
```python
@dataclass
class Flag:
    flag_type: str          # 'injection', 'wash', 'spike'
    channel: str            # 'A', 'B', 'C', 'D' (uppercase)
    time: float             # Timeline position (seconds)
    spr: float              # SPR value at flag position (RU)
    context: str            # 'live' or 'edits'
    marker_symbol: str      # PyQtGraph symbol ('t', 's', 'star', etc.)
    marker_size: int        # Visual size in pixels
    marker_color: str       # Hex color string
    marker: any             # PyQtGraph ScatterPlotItem reference
    is_reference: bool      # True if this is the injection reference (first injection)
```

**Flag type visual mapping:**

| Flag Type | Symbol | Color | Size |
|-----------|--------|-------|------|
| injection | `'t'` (triangle) | Red | 14 |
| wash | `'s'` (square) | Blue | 12 |
| spike | `'star'` | Orange | 16 |

### 2.2 AutoMarker Dataclass

**Purpose:** System-calculated markers (wash_deadline, injection_deadline, etc.) that appear on the cycle graph but are NOT user-placed flags.

```python
@dataclass
class AutoMarker:
    marker_type: str    # 'wash_deadline', 'injection_deadline', etc.
    time: float         # Position on timeline (seconds)
    label: str          # Display label (e.g., '⏱ Wash Due')
    color: str          # Color code (e.g., '#FF9500')
    marker: any         # PyQtGraph InfiniteLine reference (dashed vertical)
    is_selectable: bool # Whether user can select/move this marker (default True)
```

---

## §3. FlagManager State

```python
class FlagManager:
    # Internal storage
    _flag_markers: list[Flag]          # All flags (live + edits)
    _auto_markers: list[AutoMarker]    # System-calculated timeline markers
    
    # Selection state (keyboard movement)
    _selected_marker_type: str | None  # 'flag' or 'auto_marker'
    _selected_marker_idx: int | None   # Index into _flag_markers or _auto_markers
    _flag_highlight_ring: pg.ScatterPlotItem | None  # Yellow ring on selected flag
    _selected_flag_channel: str        # Default 'a'
    
    # Injection alignment state
    _injection_reference_time: float | None
    _injection_reference_channel: str | None
    _injection_alignment_line: pg.InfiniteLine | None  # Red dashed vertical line
    _injection_snap_tolerance: float = 10.0  # seconds
    
    # Contact timer overlay
    _contact_timer_overlay: pg.TextItem | None
    _contact_timer_start_time: float | None
    _contact_timer_duration: float | None
    _contact_timer_position: tuple = (20, 20)  # Pixel position, saved across drags
    
    # Edits-context state
    _edits_highlight_ring: pg.ScatterPlotItem | None
    _edits_keyboard_filter: QObject | None
```

---

## §4. Core Flag Operations

### 4.1 add_flag_marker() — Software-Placed Live Flag

**Called by:** InjectionCoordinator, CycleCoordinator, AcquisitionEventCoordinator  
**Context:** `'live'` — Software places during acquisition, users CANNOT call this manually

```python
def add_flag_marker(
    self,
    channel: str,      # 'a', 'b', 'c', 'd'
    time_val: float,   # Seconds
    spr_val: float,    # RU value
    flag_type: str,    # 'injection', 'wash', 'spike'
)
```

**Injection alignment behavior (special logic for `flag_type='injection'`):**

```
First injection flag:
├─ Sets _injection_reference_time = time_val
├─ Sets _injection_reference_channel = channel
├─ Creates red dashed InfiniteLine on cycle graph
└─ Logs "Injection started at t=X.Xs (Channel X)"

Subsequent injection flags (different channel):
├─ Calculates time_diff = time_val - _injection_reference_time
├─ Sets shift_amount = -time_diff  (negative = shift left)
├─ Stores in app._channel_time_shifts[channel] = shift_amount
├─ Exports shift to recording_mgr.update_metadata()
├─ Triggers _update_cycle_of_interest_graph()
└─ SNAPS flag marker to reference position (time_val = _injection_reference_time)
```

**Visual creation:**
```python
# ScatterPlotItem with white outline for contrast
marker = pg.ScatterPlotItem(
    [flag.time], [flag.spr],
    symbol=flag.marker_symbol,
    size=flag.marker_size,
    brush=pg.mkBrush(flag.marker_color),
    pen=pg.mkPen("#FFFFFF", width=3),  # White outline
)
self.app.main_window.cycle_of_interest_graph.addItem(marker)
```

**Export:** If `recording_mgr.is_recording`, exports to recording via `add_flag(flag_export_dict)` with datetime timestamp

**Target graph:** `cycle_of_interest_graph` ONLY — never `full_timeline_graph`

### 4.2 add_edits_flag() — User-Placed Edits Flag

**Called by:** EditsTab right-click context menu  
**Context:** `'edits'` — User can add, move, delete

**Behavior:** Identical visual creation to `add_flag_marker()`, but:
- Uses `context='edits'` on the Flag instance
- Added to `edits_primary_graph` (not cycle_of_interest_graph)
- Not filtered out by `clear_all_flags()` or `clear_flags_for_new_cycle()`

### 4.3 remove_flag_near_click() — Remove Live Flag

```python
def remove_flag_near_click(self, time_clicked: float, spr_clicked: float)
```

**Algorithm:**
1. For each flag in `_flag_markers`, compute normalized 2D distance:
   ```python
   time_dist = abs(flag.time - time_clicked) / view_range_x
   spr_dist = abs(flag.spr - spr_clicked) / view_range_y
   distance = sqrt(time_dist² + spr_dist²)
   ```
2. If `min_distance < 0.02` (2% of screen diagonal) → remove closest flag
3. Removes visual marker from cycle graph
4. If removed flag is currently selected → clears highlight ring + deselects
5. If removed flag was `InjectionFlag` and no more injections remain → clears alignment line + resets `_injection_reference_time`

### 4.4 show_flag_type_menu() — Flag Type Context Menu

Called on right-click in live graph. Shows Qt popup menu:
- "▲ Injection" → `add_flag_marker(channel, time, spr, 'injection')`
- "■ Wash" → `add_flag_marker(channel, time, spr, 'wash')`
- "★ Spike" → `add_flag_marker(channel, time, spr, 'spike')`

---

## §5. Flag Selection & Keyboard Movement

### 5.1 Keyboard Event Filter

`FlagManager.__init__()` installs a `KeyboardEventFilter` on `main_window`:

```python
class KeyboardEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if self.flag_mgr._selected_marker_idx is not None:
                if key == Qt.Key.Key_Left:
                    self.flag_mgr.move_selected_flag(-1)
                    return True  # Consume event
                elif key == Qt.Key.Key_Right:
                    self.flag_mgr.move_selected_flag(1)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self.flag_mgr.deselect_flag()
                    return True
```

**Only active when `_selected_marker_idx is not None`** — event filter is always installed but only consumes events when a marker is selected.

### 5.2 try_select_flag_for_movement()

Called on left-click on cycle graph. Searches both `_flag_markers` and `_auto_markers`:
- For flags: normalized 2D distance
- For auto-markers: only time distance (vertical lines)
- Tolerance: `< 0.03` (3% of screen diagonal)
- Shows yellow ring highlight on selection

### 5.3 move_selected_flag()

**For AutoMarker:** Moves ±1 second per arrow press, clamp to t≥0

**For user Flag:** Data-point snapping — steps through actual data array:
```python
# Get display time array from buffer_mgr
cycle_time_raw = app.buffer_mgr.cycle_data[channel].time
start_cursor_raw = clock.convert(start_cursor_display, DISPLAY, RAW_ELAPSED)
cycle_time_display = cycle_time_raw - start_cursor_raw

# Find current index in data array
current_idx = argmin(abs(cycle_time_display - flag.time))

# Move to adjacent data point
new_idx = clamp(current_idx + direction, 0, len(cycle_time_display) - 1)
new_time = cycle_time_display[new_idx]
new_spr = cycle_spr_display[new_idx]
```

**Injection flag re-alignment:** If moved flag is non-reference injection, recalculates `_channel_time_shifts[channel]` and triggers graph update. If moved flag IS the reference, updates `_injection_reference_time` and repositions alignment line.

### 5.4 deselect_flag()

Removes yellow highlight ring, clears `_selected_marker_type` and `_selected_marker_idx`.

---

## §6. AutoMarker System

### 6.1 create_auto_marker()

```python
def create_auto_marker(
    self,
    marker_type: str,   # 'wash_deadline', 'injection_deadline'
    time: float,        # Seconds
    label: str,         # '⏱ Wash Due'
    color: str,         # '#FF9500'
) -> AutoMarker | None
```

Creates `pg.InfiniteLine` (vertical dashed) on `cycle_of_interest_graph`:
```python
visual_marker = pg.InfiniteLine(
    pos=time,
    angle=90,
    pen=pg.mkPen(color=color, width=2, style=Qt.PenStyle.DashLine),
    label=label,
    labelOpts={"color": color, "fill": (*hex_to_rgb(color), 100)},
)
```

Wrapped in `AutoMarker` dataclass, appended to `_auto_markers`.

### 6.2 clear_auto_markers()

Removes all InefiniteLines from cycle graph, clears `_auto_markers` list. Called by `clear_all_flags()` and `clear_flags_for_new_cycle()`.

---

## §7. Contact Timer Overlay

### 7.1 create_contact_timer_overlay()

```python
def create_contact_timer_overlay(self, duration: float)
```

Creates `pg.TextItem` on `cycle_of_interest_graph`:
- Text: `"⏱ 0s / {duration:.0f}s"`
- Font: Monospace, 14pt, Bold
- Background: Semi-transparent light yellow (255, 255, 200, 200)
- Position: Stored `_contact_timer_position` (top-left by default)

### 7.2 update_contact_timer_display()

Updates text to `"⏱ {elapsed:.0f}s / {duration:.0f}s"`. Called every second by acquisition timer during contact time. Caps elapsed at duration.

### 7.3 clear_contact_timer_overlay()

Removes TextItem from graph, resets all `_contact_timer_*` state.

### 7.4 make_timer_draggable()

Installs `DraggableTimerHandler` on the timer TextItem's `mouseDragEvent`. On drag finish, saves new `_contact_timer_position` (persists within session).

---

## §8. Lifecycle: Clear Operations

### 8.1 clear_all_flags()

**Trigger:** User clicks "Clear Flags" button  
**Scope:** LIVE flags only (preserves edits-context flags)

1. Filters `_flag_markers` to only live flags (`f.context == 'live'`)
2. Removes each live flag's visual marker from cycle_of_interest_graph
3. Removes from `_flag_markers` list
4. Clears highlight ring + deselects
5. Calls `clear_auto_markers()`
6. Clears injection alignment line and references
7. Resets `app._channel_time_shifts = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0}`

### 8.2 clear_flags_for_new_cycle()

**Trigger:** Called automatically when a cycle ends (CycleCoordinator)  
**Scope:** Same as `clear_all_flags()` + also calls `clear_contact_timer_overlay()`

Does NOT reset `_channel_time_shifts` (times persist across cycles within a session).

### 8.3 clear_edits_flags()

**Trigger:** EditsTab clears its annotations  
**Scope:** EDITS flags only

Removes edits-context flags from `edits_primary_graph`.

---

## §9. Export & Integration

### 9.1 Export to RecordingManager

On each `add_flag_marker()` call, if `recording_mgr.is_recording`:
```python
flag_export_data = flag.to_export_dict()
flag_export_data["timestamp"] = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
app.recording_mgr.add_flag(flag_export_data)
```

**to_export_dict() schema:**
```python
{
    "flag_type": "injection",
    "channel": "A",
    "time": 45.2,
    "spr": 612.3,
    "context": "live",
    "is_reference": True,
}
```

### 9.2 Channel Time Shifts Export

Injection alignment time shifts exported to recording metadata:
```python
recording_mgr.update_metadata(f"channel_{channel}_time_shift", shift_amount)
```

On each arrow-key flag movement that causes realignment, metadata is updated with the new shift value.

---

## §10. What the Legacy Guide Got Wrong

The previous guide described an implementation that no longer exists:

| Legacy (removed) | Current |
|------------------|---------|
| `plot_widget.flag_markers` (per-widget dict list) | `FlagManager._flag_markers` (centralized list of Flag instances) |
| `InfiniteLine + TextItem` for flag visuals | `ScatterPlotItem` (triangles, squares, stars) |
| `_on_curve_clicked`, `_on_plot_clicked` as flag API | `add_flag_marker()`, `show_flag_type_menu()`, `try_select_flag_for_movement()` |
| No injection alignment | Full alignment: first injection = reference, subsequent channels shift |
| No keyboard movement | Arrow keys with data-point snapping |
| No context separation | Live vs Edits context, cleared independently |
| No AutoMarker system | `create_auto_marker()` for system-calculated timeline events |
| No contact timer | `create_contact_timer_overlay()` + drag support |
| Manual flag placement on live graph | Live flags are SOFTWARE-ONLY; user annotates in Edits tab |

---

## §11. Method Inventory

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__()` | ~55 | Initialize state, install keyboard filter |
| `_setup_keyboard_event_filter()` | ~20 | Install KeyboardEventFilter on main_window |
| `show_flag_type_menu()` | ~20 | Right-click context menu for flag type |
| `select_flag_channel_visual()` | ~8 | Select channel, update UI highlight |
| `add_flag_marker()` | ~70 | Software-placed live flag + injection alignment |
| `remove_flag_near_click()` | ~50 | Remove closest flag by 2D proximity |
| `try_select_flag_for_movement()` | ~50 | Left-click selects flag or auto-marker |
| `_highlight_selected_flag()` | ~12 | Yellow ring on selected flag |
| `_highlight_selected_marker()` | ~15 | Brighten selected auto-marker InfiniteLine |
| `move_selected_flag()` | ~80 | Arrow-key movement with data-point snap |
| `deselect_flag()` | ~8 | Clear selection + yellow ring |
| `create_auto_marker()` | ~35 | Create dashed InfiniteLine system marker |
| `clear_auto_markers()` | ~12 | Remove all auto-markers from graph |
| `create_contact_timer_overlay()` | ~40 | Create draggable timer TextItem |
| `update_contact_timer_display()` | ~15 | Update timer elapsed/remaining text |
| `clear_contact_timer_overlay()` | ~10 | Remove timer, reset state |
| `make_timer_draggable()` | ~25 | Install drag handler on timer TextItem |
| `clear_all_flags()` | ~35 | Clear live flags + alignment (user button) |
| `clear_flags_for_new_cycle()` | ~35 | Clear live flags + timer (cycle end) |
| `clear_edits_flags()` | ~15 | Clear edits-context flags only |
| `add_edits_flag()` | ~20 | User-placed flag in EditsTab |

**Total:** ~650 functional lines (1291 total including class, docstrings, imports)

---

## §12. Known Issues

1. **`_selected_flag_idx` vs `_selected_marker_idx` naming inconsistency** — Two attribute names exist internally (`_selected_flag_idx` used in some movement logic, `_selected_marker_idx` elsewhere). Potential IndexError if one is set and other is None during movement.

2. **Edits flags not exported to recording** — `add_edits_flag()` does not call `recording_mgr.add_flag()`. If user places flags in Edits tab while recording, they won't appear in Excel export under Flags sheet.

3. **`to_export_dict()` missing edits alignment shift** — When flag is moved with arrow keys and realignment occurs, the flag's new time position is updated but `recording_mgr.add_flag()` is not called again with the updated position.

4. **Contact timer not cleared on recording stop** — If user stops recording without completing the contact time window, `_contact_timer_overlay` may persist on the graph until next `clear_flags_for_new_cycle()` call.

5. **make_timer_draggable() uses monkey-patching** — Sets `timer_item.mouseDragEvent = handler.mouseDragEvent` directly on the pg.TextItem. This may break if pyqtgraph updates its event handling model.

6. **`injection_completed` signal timing with contact_time** — (Fixed Feb 22 2026) Previously, `injection_completed` emitted when the ManualInjectionDialog finalized detection (~20-30s), even when contact_time was set (e.g. 300s). This caused downstream listeners (cycle progression, recording markers) to see the injection as "done" long before the user finished the contact+wash cycle. **Fix:** When `contact_time` is set, `_on_dialog_complete` no longer sets `done_event`. The BG thread stays blocked until `_on_bar_done` fires (all channels washed). Timeout is now `95 + contact_time + 120s` margin. See `injection_coordinator.py` lines 413-425.

7. **No wash flag from WashMonitor detection** — When `_WashMonitor.wash_detected` fires, only `bar.set_channel_wash(ch)` is called (visual update). No injection flag is placed on the Active Cycle graph for the wash event. Wash flags come only from `_place_automatic_wash_flags()` in `_timer_mixin`, which fires on contact timer expiry — not on actual wash detection. If a user washes early, there is no graph flag. (Known gap, not yet fixed.)

---

## §13. Document Metadata

**Created:** February 19, 2026 (complete rewrite of legacy guide)  
**Codebase Version:** Affilabs.core v2.0.5 beta  
**Lines Reviewed:** 1291 (flag_manager.py, full)  
**Next Review:** When edits-context flag export is implemented

## How It Works

### 1. Select a Channel for Flagging
**Action**: Left-click on any channel line (A, B, C, or D) in the Cycle of Interest graph

**Result**:
- Selected channel line becomes thicker (4px width)
- Other channel lines remain normal (2px width)
- Console message: "Channel X selected for flagging"
- Flagging mode is now active for that channel

### 2. Add a Flag
**Action**: Right-click anywhere on the graph

**Result**:
- Red dashed vertical line appears at the clicked x-position
- Flag label "🚩 ChX" appears at the top
- Flag is stored with coordinates (x, y) and associated with the selected channel
- Console message: "Flag added to Channel X at x=..., y=..."

### 3. Remove a Flag
**Action**: Ctrl+Right-click near an existing flag

**Result**:
- Flag marker is removed from the graph
- Flag is removed from internal storage
- Console message: "Removed N flag(s) from Channel X near x=..."
- Tolerance: 5.0 units (flags within this range are removed)

### 4. Switch Channels
**Action**: Left-click on a different channel line

**Result**:
- New channel becomes selected (thick line)
- Previous channel returns to normal (thin line)
- Future flags will be added to the newly selected channel
- Existing flags remain on their original channels

## Visual Elements

### Flag Marker Components
```
🚩 ChB              ← Text label (red, showing channel)
     ┆              ← Dashed vertical line (red)
     ┆
     ┆
─────●──────        ← Flagged point on channel curve
     ┆
     ┆
```

### Flag Appearance
- **Line Style**: Dashed vertical line
- **Color**: Red (#FF3B30)
- **Width**: 2px
- **Label**: "🚩 ChX" where X is the channel letter (A, B, C, or D)
- **Position**: Label at the top of the graph, line extends through the flagged point

## Data Structure

### Internal Storage

#### Per-Graph Storage
```python
plot_widget.flag_markers = [
    {
        'channel': 1,           # Channel index (0=A, 1=B, 2=C, 3=D)
        'x': 25.3,             # X-coordinate (time in seconds)
        'y': 1234.5,           # Y-coordinate (sensor value)
        'note': 'Spike',       # Optional note (future feature)
        'line': <InfiniteLine>, # PyQtGraph line object
        'text': <TextItem>     # PyQtGraph text label
    },
    # ... more flags
]
```

#### Per-Channel Storage
```python
plot_widget.channel_flags = {
    0: [(10.5, 1200.0, ''), (45.2, 1350.0, '')],  # Channel A flags
    1: [(25.3, 1234.5, 'Spike')],                 # Channel B flags
    2: [],                                         # Channel C (no flags)
    3: [(30.0, 980.0, '')]                        # Channel D flags
}
```

### Table Integration
Flags are summarized in the **Flags** column of the cycle data table:
- Format: "ChA: 2, ChB: 1, ChD: 1"
- Shows flag count per channel
- Updated automatically when flags are added/removed

## Use Cases

### 1. Mark Injection Points
**Scenario**: User injects sample at specific time
```
1. Select Channel B (binding channel)
2. Right-click at injection time → Flag added
3. Note in table: "ChB: 1" in Flags column
4. Analysis: Compare pre/post injection response
```

### 2. Identify Anomalies
**Scenario**: Spike or artifact in Channel C data
```
1. Select Channel C
2. Right-click at each spike location → Multiple flags
3. Note in table: "ChC: 3" (3 anomalies marked)
4. Later: Review flagged points for QC
```

### 3. Compare Channel Responses
**Scenario**: Mark similar events across multiple channels
```
1. Select Channel A → Right-click at event time
2. Select Channel B → Right-click at event time
3. Select Channel C → Right-click at event time
4. Result: Same time point flagged on all channels
5. Analysis: Compare response magnitude across channels
```

### 4. Mark Analysis Regions
**Scenario**: Define regions for detailed analysis
```
1. Select Channel D
2. Right-click at region start
3. Right-click at region end
4. Result: Two flags define analysis window
5. Analysis: Extract data between flags for fitting
```

## API Methods

### User-Facing Methods (called internally)

#### `_on_curve_clicked(channel_idx)`
Selects a channel for flagging by clicking on its curve.

**Parameters**:
- `channel_idx` (int): Channel index 0-3

**Effects**:
- Highlights selected curve
- Stores `selected_channel_for_flagging`
- Enables flagging mode

#### `_on_plot_clicked(event, plot_widget)`
Handles right-clicks on the plot for adding/removing flags.

**Parameters**:
- `event`: Mouse click event
- `plot_widget`: The plot widget that was clicked

**Behavior**:
- Right-click: Add flag at cursor position
- Ctrl+Right-click: Remove flag near cursor

#### `_add_flag_to_point(channel_idx, x_pos, y_pos, note="")`
Adds a flag marker at specified coordinates.

**Parameters**:
- `channel_idx` (int): Channel index 0-3
- `x_pos` (float): X-coordinate in data units
- `y_pos` (float): Y-coordinate in data units
- `note` (str): Optional note text (future use)

**Returns**: None

#### `_remove_flag_at_position(channel_idx, x_pos, tolerance=5.0)`
Removes flags near the specified x position.

**Parameters**:
- `channel_idx` (int): Channel index 0-3
- `x_pos` (float): X-coordinate to search near
- `tolerance` (float): Search radius (default 5.0 units)

**Returns**: None

#### `_clear_all_flags(channel_idx=None)`
Clears all flags or flags for a specific channel.

**Parameters**:
- `channel_idx` (int, optional): Channel to clear, or None for all

**Returns**: None

#### `_update_flags_table()`
Updates the Flags column in the data table with current flag counts.

**Parameters**: None

**Returns**: None

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Left-click curve | Select channel for flagging |
| Right-click graph | Add flag at cursor position |
| Ctrl+Right-click | Remove flag near cursor |
| (Future) F | Toggle flagging mode on/off |
| (Future) Delete | Remove selected flag |
| (Future) Ctrl+Shift+F | Clear all flags |

## Future Enhancements

### Planned Features
1. **Flag Notes**: Add text notes to flags via dialog box
2. **Flag Colors**: Different colors for different flag types
3. **Flag Export**: Include flags in exported data files
4. **Flag Import**: Load flags from previous sessions
5. **Flag Filtering**: Show/hide flags by channel or type
6. **Flag Editing**: Modify flag position and notes after creation
7. **Flag Statistics**: Count flags by channel, time range, etc.
8. **Flag Grouping**: Group related flags (e.g., "baseline region")

### Advanced Features
1. **Auto-Flagging**: Automatically flag points based on criteria
   - Threshold crossings
   - Rate of change spikes
   - Statistical outliers
   - Pattern matching

2. **Flag Templates**: Pre-defined flag sets for common workflows
   - "Injection Protocol" (baseline, inject, wash, stabilize)
   - "QC Checkpoints" (start, mid, end)
   - "Calibration Points" (reference points)

3. **Flag-Based Analysis**: Use flags to define analysis regions
   - Calculate statistics between flags
   - Fit curves to flagged regions
   - Compare flagged points across runs

## Technical Notes

### PyQtGraph Elements Used
```python
# Vertical flag line
pg.InfiniteLine(
    pos=x_pos,
    angle=90,  # Vertical
    pen=pg.mkPen(color='#FF3B30', width=2, style=pg.QtCore.Qt.PenStyle.DashLine),
    movable=False
)

# Flag label
pg.TextItem(
    text=f"🚩 Ch{channel_letter}",
    color='#FF3B30',
    anchor=(0.5, 1)  # Center horizontal, bottom vertical
)
```

### Mouse Button Codes
- `1`: Left mouse button (curve selection)
- `2`: Right mouse button (flagging)
- `4`: Middle mouse button (not used)

### Coordinate Transformation
```python
# Convert screen coordinates to data coordinates
pos = event.scenePos()
mouse_point = plot_widget.getPlotItem().vb.mapSceneToView(pos)
x_pos = mouse_point.x()
y_pos = mouse_point.y()
```

## Troubleshooting

### Flag Not Appearing
**Problem**: Right-click but no flag appears

**Solutions**:
1. Ensure a channel is selected first (click on a curve line)
2. Check console for "Please select a channel first" message
3. Verify right-click (not left-click)
4. Try clicking on a different part of the graph

### Wrong Channel Flagged
**Problem**: Flag appears on wrong channel

**Solution**:
1. Check which channel is currently selected (thick line)
2. Click on the correct channel curve first
3. Then right-click to add flag

### Flag Can't Be Removed
**Problem**: Ctrl+Right-click doesn't remove flag

**Solutions**:
1. Ensure Ctrl key is held while right-clicking
2. Click closer to the flag (within 5.0 unit tolerance)
3. Check if flag belongs to currently selected channel
4. Try clearing all flags for that channel

### Flags Not in Table
**Problem**: Flags column doesn't show flag count

**Solution**:
1. Feature is simplified in current version
2. Check console output for flag count
3. Full table integration coming in future update

## Performance Considerations

### Flag Limits
- **Recommended**: <50 flags per channel
- **Maximum**: ~200 flags total (performance may degrade)
- Each flag adds 2 visual elements (line + text)

### Memory Usage
- Each flag: ~1 KB (PyQtGraph objects + metadata)
- 100 flags: ~100 KB (negligible)
- No significant impact on performance

### Update Speed
- Adding flag: <5ms (instantaneous)
- Removing flag: <10ms (search + remove)
- Clearing all: <20ms

## Best Practices

### Flagging Workflow
1. **Plan**: Decide what to flag before starting
2. **Select**: Choose the correct channel
3. **Mark**: Add flags at key points
4. **Review**: Check flags are in correct positions
5. **Document**: Add notes if needed (future feature)

### Flag Organization
- Use consistent flagging across experiments
- Flag similar events on multiple channels
- Remove obsolete flags regularly
- Export flag data for record-keeping (future)

### Analysis Integration
- Use flags to define analysis windows
- Compare responses between flagged points
- Calculate statistics for flagged regions
- Track flagged anomalies for QC

---

**Status**: ✅ IMPLEMENTED
**Version**: 1.0
**Feature**: Channel-Specific Flagging System
**Integration**: Cycle of Interest Graph + Data Table
