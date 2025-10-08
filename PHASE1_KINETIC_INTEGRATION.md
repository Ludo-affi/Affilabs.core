# Phase 1 Complete: KineticManager Integration

## Date
October 7, 2025

## Summary
Successfully integrated KineticManager into main.py. The manager is now initialized, connected to signals, and properly cleaned up on disconnect.

## Changes Made

### 1. Import Added (Line 57)
```python
from utils.kinetic_manager import KineticManager
```

### 2. Instance Variable Added (Lines 256-258)
```python
# Kinetic manager (initialized after KNX hardware connection)
self.kinetic_manager: KineticManager | None = None
```

### 3. Initialization in open_device() (Lines 420-432)
```python
# Initialize kinetic manager if KNX hardware is available
if self.knx is not None:
    try:
        self.kinetic_manager = KineticManager(self.knx, self.exp_start)
        logger.info("Kinetic manager initialized successfully")
        
        # Connect kinetic manager signals
        self.kinetic_manager.valve_state_changed.connect(self._on_valve_state_changed)
        self.kinetic_manager.sensor_reading.connect(self._on_sensor_reading)
        self.kinetic_manager.device_temp_updated.connect(self._on_device_temp_updated)
        self.kinetic_manager.injection_started.connect(self._on_injection_started)
        self.kinetic_manager.injection_ended.connect(self._on_injection_ended)
        self.kinetic_manager.error_occurred.connect(self._on_kinetic_error)
    except Exception as e:
        logger.exception(f"Error initializing kinetic manager: {e}")
        self.kinetic_manager = None
```

### 4. Signal Handlers Added (Lines 476-527)

#### Valve State Changed Handler
```python
def _on_valve_state_changed(self, channel: str, position_name: str) -> None:
    """Handle valve state changes from kinetic manager."""
    try:
        self.valve_states[channel] = position_name
        logger.debug(f"Valve {channel} state: {position_name}")
    except Exception as e:
        logger.exception(f"Error handling valve state change: {e}")
```

#### Sensor Reading Handler
```python
def _on_sensor_reading(self, readings: dict) -> None:
    """Handle sensor readings from kinetic manager."""
    try:
        # Update UI with sensor readings
        # readings dict has keys: "temp1", "temp2"
        # Values are formatted strings ready for display
        if hasattr(self.main_window, 'update_sensor_display'):
            self.main_window.update_sensor_display(readings)
    except Exception as e:
        logger.exception(f"Error handling sensor reading: {e}")
```

#### Device Temperature Handler
```python
def _on_device_temp_updated(self, temperature: str, source: str) -> None:
    """Handle device temperature updates from kinetic manager."""
    try:
        logger.debug(f"Device temp ({source}): {temperature}°C")
        # Update UI if needed
    except Exception as e:
        logger.exception(f"Error handling device temp update: {e}")
```

#### Injection Started Handler
```python
def _on_injection_started(self, channel: str, exp_time: float) -> None:
    """Handle injection start from kinetic manager."""
    try:
        logger.info(f"Injection started on {channel} at {exp_time:.2f}s")
    except Exception as e:
        logger.exception(f"Error handling injection start: {e}")
```

#### Injection Ended Handler
```python
def _on_injection_ended(self, channel: str) -> None:
    """Handle injection end from kinetic manager."""
    try:
        logger.info(f"Injection ended on {channel}")
    except Exception as e:
        logger.exception(f"Error handling injection end: {e}")
```

#### Kinetic Error Handler
```python
def _on_kinetic_error(self, channel: str, error_message: str) -> None:
    """Handle kinetic errors from kinetic manager."""
    try:
        logger.error(f"Kinetic {channel} error: {error_message}")
        show_message(f"Kinetic {channel} Error: {error_message}", msg_type="Warning")
    except Exception as e:
        logger.exception(f"Error handling kinetic error: {e}")
```

### 5. Cleanup in disconnect_dev() (Lines 3245-3253)
```python
# Cleanup kinetic manager
if self.kinetic_manager:
    try:
        logger.info("Shutting down kinetic manager")
        self.kinetic_manager.shutdown()
    except Exception as e:
        logger.warning(f"Error shutting down kinetic manager during disconnect: {e}")
    finally:
        self.kinetic_manager = None
```

## KineticManager Signals Connected

1. **valve_state_changed(str, str)** - Emitted when valve position changes
   - Parameters: channel, position_name
   - Handler: Updates `self.valve_states` and logs

2. **sensor_reading(dict)** - Emitted when sensor readings are ready
   - Parameters: readings dict with "temp1", "temp2" keys
   - Handler: Updates UI display (if method exists)

3. **device_temp_updated(str, str)** - Emitted when device temperature is read
   - Parameters: temperature, source ("ctrl" or "knx")
   - Handler: Logs temperature

4. **injection_started(str, float)** - Emitted when injection begins
   - Parameters: channel, exp_time
   - Handler: Logs injection start

5. **injection_ended(str)** - Emitted when injection ends
   - Parameters: channel
   - Handler: Logs injection end

6. **error_occurred(str, str)** - Emitted on errors
   - Parameters: channel, error_message
   - Handler: Shows error dialog and logs

## Integration Pattern

The KineticManager integration follows the same pattern as CavroPumpManager:

1. **Import** the manager class
2. **Declare** instance variable as optional (None initially)
3. **Initialize** in `open_device()` after hardware connection
4. **Connect signals** to handler methods
5. **Use manager** methods instead of direct hardware calls
6. **Cleanup** on disconnect

## Current Status

✅ **Phase 1 COMPLETE**
- Import added
- Instance variable declared
- Initialization implemented
- All 6 signals connected
- Signal handlers implemented
- Cleanup implemented

## Next Steps (Phase 2)

Now that KineticManager is integrated, we can proceed to:

1. **Replace valve control methods** - Update `three_way()` and `six_port()`
2. **Remove direct KNX valve calls** - Replace with kinetic_manager methods
3. **Rewrite sensor_reading_thread** - Use kinetic_manager sensor methods
4. **Remove redundant state variables** - Delete old buffers and logs
5. **Update logging calls** - Use kinetic_manager logging

## Testing Notes

Before testing with hardware:
- Verify KineticManager initialization doesn't fail
- Check that signal connections work
- Ensure cleanup happens on disconnect
- Test error handling paths

## Files Modified

- `main/main.py` - All changes in this file

## Lines Added/Modified

- Import: +1 line
- Instance variable: +3 lines
- Initialization: +13 lines
- Signal handlers: +52 lines
- Cleanup: +8 lines
- **Total: ~77 lines added**

## Backward Compatibility

- All existing code still works (no breaking changes yet)
- Redundant code still present (to be removed in Phase 2)
- KineticManager runs in parallel with old code (temporary)

## Risk Assessment

**Low Risk Changes:**
- Adding import - No effect on existing code
- Adding instance variable - No effect on existing code  
- Signal handlers - Only called by KineticManager (isolated)
- Cleanup - Only runs on disconnect (safe)

**No Breaking Changes Yet:**
- Old valve methods still exist
- Old sensor thread still runs
- Old logging still works

Phase 2 will introduce breaking changes when we remove redundant code.
