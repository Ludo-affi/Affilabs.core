# Internal Pump UI Synchronization Issues - Audit Report

## Critical Issues Found

### 1. **INJECT SEQUENCE STARTS PUMPS WITHOUT UPDATING STATE FLAGS** ❌
**Location:** `main.py:4311-4313` (inject handler)

```python
# Start BOTH pumps at FLUSH rate first
success_p1 = ctrl.pump_start(rate_ul_min=flush_p1, ch=1)
success_p2 = ctrl.pump_start(rate_ul_min=flush_p2, ch=2)
success = bool(success_p1 and success_p2)
```

**Problem:** The inject sequence starts Pump 1 and Pump 2 but **NEVER sets the state flags**:
- `self._pump1_running` is NOT set to True
- `self._pump2_running` is NOT set to True
- `self._synced_pumps_running` is NOT set to True

**Impact:**
- UI pump toggle buttons show "▶ Start" even though pumps ARE running
- Status bar shows correct info but button states are wrong
- User can click "Start" button again, causing double-start command
- When user clicks "Stop", the callback checks the flag and thinks pumps aren't running

---

### 2. **NO UI BUTTON STATE UPDATE AFTER INJECT STARTS PUMPS** ❌
**Location:** Same as above

**Problem:** After starting pumps for injection:
- Individual pump toggle buttons (Pump 1, Pump 2) are NOT updated
- Synced toggle button is NOT updated
- Buttons still show "▶ Start" even though pumps are running

**Expected Behavior:**
```python
# Should update buttons after pump start
if hasattr(self.main_window.sidebar, 'pump1_toggle_btn'):
    btn = self.main_window.sidebar.pump1_toggle_btn
    btn.blockSignals(True)
    btn.setChecked(True)
    btn.setText("■ Stop")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    btn.blockSignals(False)

# Same for pump2_toggle_btn and synced_toggle_btn
```

---

### 3. **ASYNC PUMP START CALLBACKS DON'T SYNC WITH INJECT SEQUENCE** ⚠️
**Location:** `main.py:4009-4012`, `main.py:4126-4128`

**Problem:** Individual pump toggles use async tasks with callbacks:
```python
def on_start_complete(success):
    if success:
        self._pump1_running = True  # Track state
    else:
        self._pump1_running = False
```

But inject sequence starts pumps **synchronously** with **no callback** and **no state update**.

**Conflict:** If user:
1. Starts inject (pumps running, but flags = False)
2. Clicks individual pump toggle button
3. Code checks `self._pump1_running` (False) and tries to START again
4. Sends duplicate start command to hardware

---

### 4. **COUNTDOWN TIMER CONFLICTS WITH PUMP STATE** ⚠️
**Location:** `main.py:4494-4523` (countdown update)

**Problem:** Countdown timer updates status bar, but doesn't check if pumps are supposed to be running:
```python
self._update_internal_pump_status(
    f"VALVE OPEN ({channel_text}) - {remaining:.1f}s",
    running=True,  # Says running but doesn't verify actual pump state
)
```

If pumps fail to start during inject, countdown shows "running" but hardware is idle.

---

### 5. **VALVE CLOSE DOESN'T STOP PUMPS BUT BUTTON STATE SUGGESTS IT DOES** ⚠️
**Location:** `main.py:4444` (close valve handler)

**Current Behavior:**
```python
# After valve closes (30s contact time expires)
self._update_internal_pump_status("Pumps running (contact complete)", running=True)
# Inject button re-enabled
btn.setEnabled(True)
btn.setProperty("injection_state", "ready")
```

**Problem:** 
- Valve closes, pumps KEEP RUNNING (correct)
- Status says "Pumps running" (correct)
- Inject button goes back to "💉 Inject" ready state (MISLEADING)
- But pump toggle buttons still show "▶ Start" because flags were never set

**User Confusion:**
- Can't tell which pumps are running
- Inject button says "ready" but pumps are already running
- Must stop pumps manually but buttons don't reflect state

---

### 6. **MANUAL MODE VALVE TOGGLE DOESN'T CHECK PUMP STATE** ⚠️
**Location:** `main.py:4193-4245` (manual mode valve toggle)

**Problem:** Manual mode opens/closes valve but:
- Doesn't check if pumps are running
- Doesn't prevent inject if pumps are already running
- Doesn't update pump state flags
- User could open valve with no pumps running (useless)
- Or open valve when pumps already running from previous inject

---

## State Tracking Summary

### Current State Flags:
- `self._pump1_running` - Set by individual pump toggle, **NOT by inject**
- `self._pump2_running` - Set by individual pump toggle, **NOT by inject**
- `self._synced_pumps_running` - Set by synced toggle, **NOT by inject**
- `self._injection_start_time` - Set by inject, tracks countdown timer
- `self._manual_valve_open` - Set by manual mode, tracks valve state

### What Sets Flags:
| Action | P1 Flag | P2 Flag | Synced Flag | UI Update |
|--------|---------|---------|-------------|-----------|
| Individual P1 toggle | ✅ Yes | ❌ No | ❌ No | ✅ Yes (P1 btn) |
| Individual P2 toggle | ❌ No | ✅ Yes | ❌ No | ✅ Yes (P2 btn) |
| Synced toggle | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes (Synced btn) |
| **INJECT SEQUENCE** | ❌ **NO** | ❌ **NO** | ❌ **NO** | ⚠️ Partial (inject btn only) |
| Valve close (after inject) | ❌ No | ❌ No | ❌ No | ⚠️ Partial (inject btn) |

---

## Recommended Fixes

### Fix 1: Update State Flags When Inject Starts Pumps
```python
# After successful pump start in inject sequence (line ~4314)
if success:
    logger.info(f"✓ Pumps started at FLUSH rate")
    self._pump1_running = True  # ADD THIS
    self._pump2_running = True  # ADD THIS
    self._synced_pumps_running = True  # ADD THIS if synced mode
    
    # Update inject button...
    # (existing code)
```

### Fix 2: Update Pump Toggle Buttons When Inject Starts
```python
# After setting state flags
if hasattr(self.main_window.sidebar, 'pump1_toggle_btn'):
    btn = self.main_window.sidebar.pump1_toggle_btn
    btn.blockSignals(True)
    btn.setChecked(True)
    btn.setText("■ Stop")
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    btn.blockSignals(False)

# Repeat for pump2_toggle_btn
# Repeat for synced_toggle_btn if valve sync enabled
```

### Fix 3: Disable Pump Toggles During Injection
```python
# While injection is active, disable individual pump controls
if hasattr(self.main_window.sidebar, 'pump1_toggle_btn'):
    self.main_window.sidebar.pump1_toggle_btn.setEnabled(False)
if hasattr(self.main_window.sidebar, 'pump2_toggle_btn'):
    self.main_window.sidebar.pump2_toggle_btn.setEnabled(False)
if hasattr(self.main_window.sidebar, 'synced_toggle_btn'):
    self.main_window.sidebar.synced_toggle_btn.setEnabled(False)
```

### Fix 4: Re-enable and Sync Buttons After Valve Closes
```python
# In _close_inject_valve() after valve closes
# Re-enable buttons
if hasattr(self.main_window.sidebar, 'pump1_toggle_btn'):
    self.main_window.sidebar.pump1_toggle_btn.setEnabled(True)
# (repeat for other buttons)

# Sync button states with actual running flags
self._sync_pump_button_states()
```

### Fix 5: Add Pump State Check to Manual Mode
```python
# Before allowing manual valve toggle
if self._pump1_running or self._pump2_running or self._synced_pumps_running:
    logger.warning("Cannot toggle valve manually while pumps are running")
    from affilabs.widgets.message import show_message
    show_message("Stop all pumps before manual valve control", "Warning")
    return
```

### Fix 6: Prevent Inject While Pumps Already Running
```python
# At start of inject handler
if self._synced_pumps_running or (self._pump1_running and self._pump2_running):
    logger.warning("Cannot start inject - pumps already running")
    from affilabs.widgets.message import show_message
    show_message("Pumps are already running. Stop them first.", "Warning")
    return
```

---

## Testing Checklist

After implementing fixes:

- [ ] Start inject sequence → verify pump buttons show "■ Stop"
- [ ] During injection → verify pump toggle buttons are disabled
- [ ] After valve closes → verify pump buttons still show "■ Stop"
- [ ] Click pump stop → verify pumps actually stop
- [ ] Inject while pumps running → verify error message appears
- [ ] Manual valve toggle while pumps running → verify error message
- [ ] Status bar countdown → verify updates every 100ms during injection
- [ ] After 6s flow reduction → verify countdown continues (not overwritten)
- [ ] Restart app while pumps running → verify button states sync on reconnect

---

## Priority

**CRITICAL:** Fix #1, #2 (state flags and button sync)
**HIGH:** Fix #3, #4 (disable buttons, re-enable after)
**MEDIUM:** Fix #5, #6 (safety checks)
