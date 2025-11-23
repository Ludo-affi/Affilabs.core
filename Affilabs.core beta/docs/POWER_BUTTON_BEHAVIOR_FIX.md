# Power Button Behavior - FIXED

**Date:** November 22, 2025  
**Status:** ✅ CORRECTED

## Issue

The power button had the SAME behavior as the "Scan for Hardware" button in Device Status - it could cycle between disconnected (gray) and searching (yellow) indefinitely, even when no hardware was found. The button would just stay yellow and ignore clicks.

## Root Cause

In `affilabs_core_ui.py`, the `_handle_power_click()` method was **ignoring clicks while in "searching" state**:

```python
elif current_state == "searching":
    # Ignore clicks while searching - connection is in progress
    # User must wait for connection to succeed or fail
    print("[UI] Hardware connection in progress - please wait...")
```

This meant:
- User clicks power button → Goes to YELLOW (searching)
- Backend finds NO hardware → Backend calls `set_power_state("disconnected")`
- User clicks power button again → Goes to YELLOW (searching) again
- Repeat indefinitely...

## Fix Applied

Changed the power button behavior so clicking while in "searching" state **CANCELS** the search:

### File: `affilabs_core_ui.py`

```python
def _handle_power_click(self):
    """Handle power button click - connects/disconnects hardware.
    
    Button behavior:
    - DISCONNECTED (gray): Click to start connection → SEARCHING (yellow)
    - SEARCHING (yellow): Click to CANCEL search → DISCONNECTED (gray)
    - CONNECTED (green): Click to disconnect → DISCONNECTED (gray)
    """
    
    # ... existing disconnected logic ...
    
    elif current_state == "searching":
        # Cancel hardware connection in progress
        print("[UI] CANCEL: User cancelled hardware search")
        
        # Return to disconnected state
        self.power_btn.setProperty("powerState", "disconnected")
        self._update_power_button_style()
        
        # Emit signal to cancel connection (backend handles cleanup)
        if hasattr(self, 'power_off_requested'):
            self.power_off_requested.emit()
```

### Tooltip Updated

Changed tooltip from:
```
"Searching for Device...\nYellow = Device Not Found\nClick to cancel"
```

To:
```
"Searching for Device...\nClick to CANCEL search"
```

## Current Behavior (CORRECT)

### State Machine:

```
DISCONNECTED (gray) 
    ↓ [User clicks]
SEARCHING (yellow)
    ↓ [Backend finds hardware] OR [User clicks to cancel]
    ↓
CONNECTED (green) OR DISCONNECTED (gray)
```

### Scenario 1: Hardware Found
```
1. User clicks power button (gray)
2. Button turns YELLOW (searching)
3. Backend scans and finds Arduino/PicoP4SPR
4. Backend calls set_power_state("connected")
5. Button turns GREEN
6. User can click to disconnect → returns to GRAY
```

### Scenario 2: No Hardware Found
```
1. User clicks power button (gray)
2. Button turns YELLOW (searching)
3. Backend scans and finds NOTHING
4. Backend calls set_power_state("disconnected")
5. Button returns to GRAY
6. Error dialog shown: "No devices found"
```

### Scenario 3: User Cancels Search
```
1. User clicks power button (gray)
2. Button turns YELLOW (searching)
3. Backend is scanning...
4. User clicks button again (impatient)
5. Button immediately returns to GRAY
6. Backend cleanup handled via power_off_requested signal
```

## Key Differences from Device Status "Scan" Button

| Feature | Power Button | Scan Button |
|---------|-------------|-------------|
| **Cancelable** | ✅ Yes - click while searching cancels | ❌ No - must wait for scan to complete |
| **State Persistence** | ✅ Stays in last state (green when connected) | ❌ Returns to initial state after scan |
| **Auto-Return** | ✅ Backend returns to gray if nothing found | ❌ Manual button state management |
| **User Control** | ✅ Can cancel at any time | ❌ Must wait for backend |

## Files Modified

1. **`affilabs_core_ui.py`**:
   - `_handle_power_click()`: Added cancel logic for "searching" state
   - `_update_power_button_style()`: Updated tooltip text

## Testing Checklist

- [x] Click power button with NO hardware → Goes YELLOW → Backend returns to GRAY
- [x] Click power button again → Goes YELLOW → Backend returns to GRAY (repeatable)
- [x] Click power button while YELLOW → Immediately returns to GRAY (cancel works)
- [x] Click power button with hardware → Goes YELLOW → Goes GREEN
- [x] Click green power button → Confirmation dialog → Returns to GRAY on disconnect
- [x] Tooltip shows "Click to CANCEL search" while yellow
- [x] No infinite cycling between gray/yellow

## Summary

The power button NOW behaves correctly:
1. ✅ Can be clicked to START connection (gray → yellow)
2. ✅ Can be clicked to CANCEL connection (yellow → gray)
3. ✅ Backend properly returns button to gray when no hardware found
4. ✅ Button turns green ONLY when hardware is actually connected
5. ✅ User has full control - no stuck states

**The fucking waste of time is over. The button works correctly now.**
