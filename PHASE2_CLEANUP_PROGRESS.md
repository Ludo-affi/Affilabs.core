# Phase 2 Progress: Redundant Code Removal

## Date
October 7, 2025

## Summary
Phase 2 in progress: Removing redundant code from main.py and replacing with KineticManager calls.

## Changes Completed

### 1. Valve Control Methods Updated ✅

**Location:** Lines ~2184-2211

**Before (30 lines):**
```python
def three_way(self: Self, ch: str, state: object) -> None:
    """Switch a three-way valve."""
    if self.knx is not None:
        try:
            self._s_stop.set()
            if ch == "CH1":
                if self.synced:
                    self.knx.knx_three(state, 3)
                else:
                    self.knx.knx_three(state, 1)
            elif ch == "CH2":
                self.knx.knx_three(state, 2)
            self._s_stop.clear()
        except Exception as e:
            logger.exception(f"Error setting 3-way valve: {e}")
```

**After (13 lines):**
```python
def three_way(self: Self, ch: str, state: object) -> None:
    """Switch a three-way valve using kinetic manager."""
    if self.kinetic_manager is not None:
        try:
            self._s_stop.set()
            position = int(state)
            success = self.kinetic_manager.set_three_way_valve(ch, position)
            if not success:
                logger.warning(f"Failed to set 3-way valve {ch} to position {position}")
            self._s_stop.clear()
        except Exception as e:
            logger.exception(f"Error setting 3-way valve: {e}")
            self._s_stop.clear()
```

**Same pattern for `six_port()` method**

**Lines Saved:** ~17 lines (from 30 to 13 per method, x2 methods)

### 2. Sensor Reading Thread Rewritten ✅

**Location:** Lines ~2586-2676 (was ~210 lines, now ~90 lines)

**Major Changes:**
- Removed direct `self.knx.knx_status()` calls → Use `kinetic_manager.read_sensor()`
- Removed manual buffer management (flow_buf_1/2, temp_buf_1/2) → KineticManager handles internally
- Removed manual averaging calculations → Use `kinetic_manager.get_averaged_sensor_reading()`
- Removed manual logging to log_ch1/log_ch2 → KineticManager handles internally
- Removed obsolete flow rate references
- Simplified device temperature reading → Use `kinetic_manager.read_device_temp()`
- Used calibration constants (TEMP_CHECK_MIN, TEMP_AVG_WINDOW, etc.)

**Lines Saved:** ~120 lines (from ~210 to ~90)

### 3. Buffer Variables Commented Out ✅

**Location:** Lines ~256-273

**Changes:**
- Kept `self.log_ch1` and `self.log_ch2` temporarily for backward compatibility with log export
- Added deprecation comments
- Removed flow_buf_1, flow_buf_2, temp_buf_1, temp_buf_2 declarations (commented)

**Lines Saved:** ~4 lines (buffer declarations removed)

## Code Quality Improvements

1. **Used Calibration Constants:**
   - `TEMP_CHECK_MIN` (5°C) instead of hardcoded 5
   - `TEMP_CHECK_MAX` (75°C) instead of hardcoded 75
   - `TEMP_AVG_WINDOW` (5) instead of hardcoded 5

2. **Cleaner Error Handling:**
   - More specific error messages
   - Proper cleanup in exception handlers

3. **Better Code Organization:**
   - Separated concerns (sensor reading vs. logging)
   - Removed duplicate logic

## Issues Found

### Code Corruption at Line ~2151
Found unexpected class definition in the middle of `stop_pump()` method:
```python
class PicoKNX2:
    version = "Stub"
    def open(self): return False
```

This appears to be corrupted code that needs investigation. It's breaking the flow of the `stop_pump()` method.

**Action Required:** This needs to be fixed before proceeding further.

## Lines Removed So Far

| Category | Before | After | Reduction |
|----------|--------|-------|-----------|
| Valve methods | 30 | 13 | -17 lines |
| Sensor thread | 210 | 90 | -120 lines |
| Buffer vars | 4 | 0 | -4 lines |
| **TOTAL** | **244** | **103** | **-141 lines** |

## Remaining Work (Phase 2)

### ⏭️ Fix Code Corruption
- Investigate and fix corrupted `stop_pump()` method
- Check for any other corruption

### ⏭️ Update Logging Calls
- Find all manual `self.log_ch1[...].append()` calls
- Replace with `kinetic_manager.log_event()` 
- Estimated: ~40-60 lines to update

### ⏭️ Update Log Export Methods
- Update methods that read from `self.log_ch1` and `self.log_ch2`
- Use `kinetic_manager.get_log_dict()` instead
- Estimated: ~10-20 lines to update

### ⏭️ Remove Obsolete clear_sensor_reading_buffers()
- Method likely clears the old buffers
- No longer needed with KineticManager
- Estimated: ~10 lines to remove

### ⏭️ Update inject/cancel_injection
- Replace direct `knx.knx_six()` calls
- Use `kinetic_manager.start_injection()` and `end_injection()`
- Estimated: ~10 lines to update

### ⏭️ Verify valve_state_check()
- Determine if still needed or if KineticManager handles it
- Update or remove as appropriate

## Testing Required

After Phase 2 completion:
1. Test valve control (3-way and 6-port)
2. Test sensor reading and averaging
3. Test temperature display
4. Test injection sequences
5. Test log export functionality
6. Verify synchronized mode still works
7. Test with actual hardware

## Risk Assessment

**Current Status: Medium Risk**
- Code corruption found (needs immediate attention)
- Major rewrite of sensor thread (needs thorough testing)
- Log export compatibility not yet verified

**Mitigation:**
- Fix corruption before proceeding
- Test sensor reading thoroughly
- Verify log export still works
- Keep backup of original code

## Next Steps

1. **URGENT:** Fix code corruption at line 2151
2. Continue updating manual logging calls
3. Update log export methods
4. Test thoroughly with hardware

## Files Modified

- `main/main.py` - All changes in this file

## Backup Recommendation

Before proceeding further, create a backup:
```powershell
Copy-Item "main\main.py" "main\main.py.phase2backup"
```

## Notes

- Kept log_ch1/log_ch2 temporarily to avoid breaking log export
- Will need to update log export to use kinetic_manager.get_log_dict()
- Flow rate completely removed (obsolete feature)
- Using calibration constants for better maintainability
