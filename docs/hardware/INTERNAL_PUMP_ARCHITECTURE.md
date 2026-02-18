# Internal Pump Architecture (P4PRO+)

## Overview
P4PRO+ hardware (firmware V2.3+) has 3 internal peristaltic pumps controlled via serial commands.

## Hardware Channels
- **Channel 1**: Pump 1 (individual control)
- **Channel 2**: Pump 2 (individual control)
- **Channel 3**: Both pumps synchronized (same RPM)

## Serial Commands

### Start Pump
**Format**: `pr{ch}{rpm:04d}\n`
- **Examples**:
  - `pr10050\n` = Pump 1 at 50 RPM
  - `pr20100\n` = Pump 2 at 100 RPM
  - `pr30075\n` = Both pumps at 75 RPM
- **RPM Range**: 5-220 RPM (firmware enforced)
- **Response**: No response (firmware doesn't ACK pump commands)
- **Delay**: 150ms required between commands

### Stop Pump
**Format**: `ps{ch}\n`
- **Examples**:
  - `ps1\n` = Stop pump 1
  - `ps2\n` = Stop pump 2
  - `ps3\n` = Stop both pumps
- **Response**: No response
- **Delay**: 150ms required

### 6-Port Valve Control
**Format**: `v6{ch}{state}\n`
- **Channels**: 1 (KC1), 2 (KC2)
- **States**: 0 (LOAD/off), 1 (INJECT/on)
- **Response**: `b"1"` on success
- **Examples**:
  - `v611\n` = KC1 valve → INJECT
  - `v610\n` = KC1 valve → LOAD

## UI Controls Structure

### Individual Pump Mode
- **Pump 1 Toggle**: `_on_internal_pump1_toggle()`
  - Channel: **1** (always)
  - RPM: `pump1_rpm_spin.value() * pump1_correction_spin.value()`
  - Threading: Background QRunnable task
  
- **Pump 2 Toggle**: `_on_internal_pump2_toggle()`
  - Channel: **2** (always)
  - RPM: `pump2_rpm_spin.value() * pump2_correction_spin.value()`
  - Threading: Background QRunnable task

### Synced Pump Mode
- **Synced Toggle**: `_on_synced_pump_toggle()`
  - Channel: **3** (both pumps)
  - RPM: `synced_rpm_spin.value() * synced_correction_spin.value()`
  - Threading: Background QRunnable task

## Live RPM Update Handlers

### Purpose
Allow changing pump speed while pump is running (no need to stop/restart).

### Implementation
- **`_on_pump1_rpm_changed()`**: Updates pump 1 if running
- **`_on_pump2_rpm_changed()`**: Updates pump 2 if running
- **`_on_synced_rpm_changed()`**: Updates both pumps if running

### Logic
```python
if toggle_btn.isChecked():  # Only if pump running
    rpm_corrected = rpm * correction
    ctrl.pump_start(rate_ul_min=rpm_corrected, ch=channel)
```

## Signal Blocking Pattern

### Problem
Programmatically calling `setChecked(False)` triggers the `toggled` signal, creating loops.

### Solution
```python
btn.blockSignals(True)
btn.setChecked(False)
btn.blockSignals(False)
```

### Usage
- ✅ When controller not connected
- ✅ When internal pumps not available
- ✅ When hardware command fails

## Inject Sequence (30s Contact Time)

### Flow
1. **Start pumps** at configured RPM
2. **Open 6-port valve(s)** (KC1 or both if synced)
   - `knx_six(state=1, ch=1)` or `knx_six_both(state=1)`
3. **Wait 30 seconds** (contact time)
4. **Close 6-port valve(s)** (LOAD position)
   - `knx_six(state=0, ch=1)` or `knx_six_both(state=0)`
5. **Pumps continue running** (user stops manually with toggle button)

### Pump Selection
- **Synced mode ON**: Channel 3 (both pumps), use synced RPM
- **Synced mode OFF**: Channel 1 (pump 1), use pump1 RPM

## Threading Architecture

### Why Background Threading?
Serial commands (150ms delay) block UI if run on main thread.

### Pattern
```python
class PumpStartTask(QRunnable):
    def run(self):
        success = ctrl.pump_start(rate_ul_min=rpm, ch=ch)
        callback(success)

QThreadPool.globalInstance().start(task)
```

### UI Updates
- **Before hardware call**: Update button text/status (optimistic)
- **After hardware call**: Revert on failure (in callback)

## Controller API

### File: `affilabs/utils/controller.py`

#### `pump_start(rate_ul_min: float, ch: int) -> bool`
- **Parameter**: `rate_ul_min` expects RPM (name kept for compatibility)
- **Validation**: 5-220 RPM
- **Command**: `pr{ch}{rpm:04d}\n`
- **Delay**: 150ms
- **Return**: True (no firmware ACK)

#### `pump_stop(ch: int) -> bool`
- **Command**: `ps{ch}\n`
- **Delay**: 150ms
- **Return**: True (no firmware ACK)

#### `knx_six(state: int, ch: int, timeout_seconds: float = None) -> bool`
- **Command**: `v6{ch}{state}\n`
- **Response**: `b"1"` = success
- **Timeout**: Auto-return to LOAD after timeout
- **Return**: True if `b"1"` received

#### `knx_six_both(state: int, timeout_seconds: float = None) -> bool`
- Controls both valves simultaneously
- **Commands**: `v611\n` + `v621\n`

#### `has_internal_pumps() -> bool`
- Checks if `'p4proplus'` in `firmware_id.lower()`
- Used to enable/disable internal pump UI

## Device Detection

### Hardware Manager
**File**: `affilabs/core/hardware_manager.py`

#### `_get_controller_type() -> str`
```python
if device_type == "PicoP4PRO":
    if 'p4proplus' in firmware_id.lower():
        return "P4PROPLUS"  # Display as P4PRO+ in UI
    return "P4PRO"
```

### Device Status Widget
**File**: `affilabs/widgets/device_status.py`

#### Hardware List
- **P4PROPLUS**: Shows "• P4PROPLUS" (controller with internal pumps)
- **External Pump**: Shows "• AffiPump" (only if NO internal pumps)
- **Logic**: `if pump_connected and not has_internal_pumps`

#### Flow Mode Indicator
```python
FLOW_CONTROLLERS = ["PicoKNX2", "PicoEZSPR", "EZSPR", "P4PROPLUS"]
```
- P4PROPLUS enables Flow mode (green indicator)
- Internal pumps treated as flow-capable

## Signal Connections

### File: `main.py` lines 1552-1578

```python
# Toggle buttons
ui.sidebar.synced_toggle_btn.toggled.connect(self._on_synced_pump_toggle)
ui.sidebar.pump1_toggle_btn.toggled.connect(self._on_internal_pump1_toggle)
ui.sidebar.pump2_toggle_btn.toggled.connect(self._on_internal_pump2_toggle)

# RPM spinboxes (live updates)
ui.sidebar.synced_rpm_spin.valueChanged.connect(self._on_synced_rpm_changed)
ui.sidebar.pump1_rpm_spin.valueChanged.connect(self._on_pump1_rpm_changed)
ui.sidebar.pump2_rpm_spin.valueChanged.connect(self._on_pump2_rpm_changed)

# Inject button
ui.sidebar.internal_pump_inject_30s_btn.clicked.connect(self._on_internal_pump_inject_30s)
```

## Common Pitfalls Fixed

### ❌ WRONG: Pump1 using channel 3 in sync mode
```python
# OLD CODE (REMOVED)
is_synced = self.main_window.sidebar.internal_pump_sync_btn.isChecked()
channel = 3 if is_synced else 1
```
**Problem**: Individual pump buttons should ALWAYS use their own channel (1 or 2).

### ❌ WRONG: Synced toggle using synchronous commands
```python
# OLD CODE (REMOVED)
success = ctrl.pump_start(rate_ul_min=rpm, ch=3)
if success:
    update_ui()
```
**Problem**: Blocks UI thread for 150ms. Inconsistent with pump1/pump2.

### ❌ WRONG: Duplicate code in synced stop
```python
# OLD CODE (REMOVED)
if success:
    logger.info("✓ Stopped")
    update_ui()
# ... later ...
if success:  # DUPLICATE!
    logger.info("✓ Stopped")
```
**Problem**: Redundant logging and UI updates.

### ❌ WRONG: setChecked without blocking signals
```python
# OLD CODE (REMOVED)
self.pump1_toggle_btn.setChecked(False)  # Triggers toggled signal!
```
**Problem**: Triggers `_on_internal_pump1_toggle(False)`, creating infinite loop.

## Best Practices

### ✅ Always block signals when programmatically changing toggle state
```python
btn.blockSignals(True)
btn.setChecked(False)
btn.blockSignals(False)
```

### ✅ Use background threading for all hardware commands
```python
class PumpTask(QRunnable):
    def run(self):
        success = ctrl.pump_start(...)
        callback(success)
```

### ✅ Update UI optimistically (before hardware call)
```python
btn.setText("■ Stop")  # Immediate feedback
# ... then run hardware command in background
```

### ✅ Revert UI on failure (in callback)
```python
def on_complete(success):
    if not success:
        btn.setText("▶ Start")  # Revert
```

### ✅ Use correct channel for each control
- Pump1: **Channel 1** (never 3)
- Pump2: **Channel 2** (never 3)
- Synced: **Channel 3** (both pumps)

## Testing Checklist

- [ ] Pump 1 toggle starts/stops channel 1 only
- [ ] Pump 2 toggle starts/stops channel 2 only
- [ ] Synced toggle starts/stops both pumps (channel 3)
- [ ] RPM changes update running pump speed
- [ ] No UI lag when clicking toggles
- [ ] Toggle buttons don't get stuck
- [ ] Inject sequence opens/closes valve after 30s
- [ ] Pumps continue after inject contact time
- [ ] Flow mode indicator turns green for P4PROPLUS
- [ ] Device status shows "P4PROPLUS" not "P4PRO"
- [ ] No "AffiPump" shown when using internal pumps
