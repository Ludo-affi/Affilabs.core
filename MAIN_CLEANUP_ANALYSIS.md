# Main.py Redundant Code Analysis

## Summary

Analysis of main.py to identify code that is redundant or conflicting with the three managers:
1. **CavroPumpManager** (pump_manager) - Already integrated ✓
2. **KineticManager** (kinetic_manager) - NOT YET INTEGRATED ❌
3. **Calibration Logic** - Already refactored ✓

## Current Status

### ✅ CavroPumpManager - Integrated
- Import added: `from utils.cavro_pump_manager import CavroPumpManager, PumpAddress`
- Instance created: `self.pump_manager: CavroPumpManager | None = None`
- Initialized in `open_device()` (lines 397-411)
- Methods already using pump_manager:
  - `regenerate()` - line 472
  - `flush()` - line 510
  - `inject()` - line 558
  - `cancel_injection()` - line 588
  - `change_flow_rate()` - line 593
  - `initialize_pumps()` - line 636

**NO REDUNDANT PUMP CODE TO REMOVE** ✓

### ❌ KineticManager - NOT Integrated
KineticManager has been created but NOT yet integrated into main.py.

### ✅ Calibration Logic - Refactored
- Main `calibrate()` method refactored with 8 sub-methods (line 955)
- Clean, modular structure
- Progress reporting implemented

**NO REDUNDANT CALIBRATION CODE TO REMOVE** ✓

## Redundant Code Found

### 1. Valve Control Methods - REDUNDANT

**Location:** Lines 2113-2142

**Current Code:**
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

def six_port(self: Self, ch: str, state: object) -> None:
    """Change a six port valve."""
    if self.knx is not None:
        try:
            self._s_stop.set()
            if ch == "CH1":
                if self.synced:
                    self.knx.knx_six(state, 3)
                else:
                    self.knx.knx_six(state, 1)
            elif ch == "CH2":
                self.knx.knx_six(state, 2)
            self._s_stop.clear()
        except Exception as e:
            logger.exception(f"Error setting 6-port valve: {e}")
```

**Why Redundant:** These methods directly call `self.knx.knx_three()` and `self.knx.knx_six()`, which should be handled by KineticManager.

**Replacement:** Use `kinetic_manager.set_three_way_valve()` and `kinetic_manager.set_six_port_valve()`

### 2. Sensor Reading Thread - REDUNDANT

**Location:** Lines 2518-2650+

**Current Code:**
- Directly calls `self.knx.knx_status(1)` and `self.knx.knx_status(2)`
- Manual flow/temp buffer management (`self.flow_buf_1`, `self.temp_buf_1`, etc.)
- Manual averaging calculations
- Manual logging to `self.log_ch1` and `self.log_ch2`
- Device temperature reading with manual status parsing

**Why Redundant:** 
- KineticManager has `read_sensor()`, `update_sensor_buffers()`, `get_averaged_sensor_reading()`
- KineticManager handles logging with `log_sensor_reading()`
- KineticManager has device temperature methods

**Replacement:** Complete rewrite using KineticManager methods

### 3. Manual Sensor Buffers - REDUNDANT

**Location:** Lines 263-266 (__init__)

**Current Code:**
```python
self.flow_buf_1: list = []
self.temp_buf_1: list = []
self.flow_buf_2: list = []
self.temp_buf_2: list = []
```

**Why Redundant:** KineticManager maintains these buffers internally

**Action:** DELETE (but note: flow buffers are obsolete anyway)

### 4. Manual Kinetic Logs - REDUNDANT

**Location:** Lines 255-262 (__init__)

**Current Code:**
```python
self.log_ch1: dict[str, list] = {
    "timestamps": [], "times": [], "events": [], "flow": [], "temp": [], "dev": []
}
self.log_ch2: dict[str, list] = {
    "timestamps": [], "times": [], "events": [], "flow": [], "temp": [], "dev": []
}
```

**Why Redundant:** KineticManager has `KineticLog` dataclass for each channel

**Action:** DELETE and use `kinetic_manager.get_log()` instead

### 5. Manual Kinetic Logging Calls - REDUNDANT

**Location:** Multiple places (2075-2080, 2095-2106, 2553-2620, etc.)

**Current Code:**
```python
self.log_ch1["timestamps"].append(log_timestamp)
self.log_ch1["times"].append(log_time)
self.log_ch1["events"].append("...")
self.log_ch1["flow"].append(flow1_text)
self.log_ch1["temp"].append(temp1_text)
self.log_ch1["dev"].append("-")
```

**Why Redundant:** KineticManager has `log_event()`, `log_sensor_reading()`, `log_device_reading()`

**Action:** Replace with `kinetic_manager.log_event()` calls

### 6. Valve State Checking - POSSIBLY REDUNDANT

**Location:** Lines 2541, 2549 (in sensor_reading_thread)

**Current Code:**
```python
self.valve_state_check(update1, 1)
self.valve_state_check(update2, 2)
```

**Investigation Needed:** Check what `valve_state_check()` does - may need to keep if it updates UI

### 7. Direct KNX Valve Calls in inject() - REDUNDANT

**Location:** Lines 566-568, 587

**Current Code:**
```python
if self.inject_sw:
    self.knx.knx_six(state=1, ch=3)
else:
    self.knx.knx_six(state=0, ch=3)
...
self.knx.knx_six(state=0, ch=3)
```

**Why Redundant:** These should use `kinetic_manager.start_injection()` and `kinetic_manager.end_injection()`

**Action:** Replace with KineticManager injection methods

### 8. Synced State Tracking - POSSIBLY REDUNDANT

**Location:** Need to find `self.synced` variable

**Investigation Needed:** KineticManager has its own `synced` state. May need to synchronize or remove main.py's version.

## Code That Should REMAIN

### 1. UI Update Methods
- Methods that update Qt widgets based on sensor/valve data
- Signal connections to UI elements
- User interaction handlers

### 2. Experiment Control Logic
- High-level experiment flow
- Data processing and analysis
- File I/O operations

### 3. Device Connection Management
- USB connection handling
- Device initialization
- Error recovery

### 4. Settings Management
- Configuration loading/saving
- User preferences

## Removal Plan

### Phase 1: Add KineticManager Integration
1. Import KineticManager
2. Create `self.kinetic_manager` instance in `__init__`
3. Initialize in `open_device()` with self.knx
4. Connect Qt signals

### Phase 2: Replace Valve Methods
1. Update `three_way()` method to use `kinetic_manager.set_three_way_valve()`
2. Update `six_port()` method to use `kinetic_manager.set_six_port_valve()`
3. Find and replace direct `self.knx.knx_three()` calls
4. Find and replace direct `self.knx.knx_six()` calls

### Phase 3: Replace Sensor Reading Thread
1. Rewrite `sensor_reading_thread()` to use KineticManager
2. Use `kinetic_manager.read_sensor()`
3. Use `kinetic_manager.get_averaged_sensor_reading()`
4. Update signal emissions

### Phase 4: Remove Redundant State Variables
1. Delete `self.flow_buf_1`, `self.flow_buf_2` (obsolete anyway)
2. Delete `self.temp_buf_1`, `self.temp_buf_2`
3. Delete `self.log_ch1`, `self.log_ch2`
4. Investigate `self.synced` - may need to sync with kinetic_manager.synced

### Phase 5: Update Logging Calls
1. Find all `self.log_ch1["..."].append()` calls
2. Replace with `kinetic_manager.log_event()` or `kinetic_manager.log_sensor_reading()`
3. Update log export methods to use `kinetic_manager.get_log_dict()`

### Phase 6: Clean Up Injection Methods
1. Update `inject()` to use `kinetic_manager.start_injection()`
2. Update `cancel_injection()` to use `kinetic_manager.end_injection()`
3. Remove direct valve calls

### Phase 7: Testing
1. Test valve control (3-way and 6-port)
2. Test sensor reading and averaging
3. Test injection sequences
4. Test logging functionality
5. Test synchronized mode
6. Verify no regressions

## Estimated Code Reduction

Based on analysis:

| Category | Current Lines | After Cleanup | Reduction |
|----------|--------------|---------------|-----------|
| Valve methods | ~30 | ~10 | -20 lines |
| Sensor thread | ~150 | ~40 | -110 lines |
| Manual buffers | ~4 | 0 | -4 lines |
| Manual logs | ~8 | 0 | -8 lines |
| Logging calls | ~60 | ~20 | -40 lines |
| Direct valve calls | ~20 | 0 | -20 lines |
| **TOTAL** | **~272 lines** | **~70 lines** | **~202 lines** |

**Expected reduction: ~200 lines of redundant KNX code**

## Files to Update

1. `main/main.py` - Remove redundant code, integrate KineticManager
2. Update any UI connection code if needed

## Files to Create

1. `MAIN_CLEANUP_SUMMARY.md` - Document all changes made

## Next Steps

1. ✅ Create this analysis document
2. ⏭️ Integrate KineticManager into main.py
3. ⏭️ Remove redundant valve methods
4. ⏭️ Rewrite sensor_reading_thread
5. ⏭️ Remove redundant state variables
6. ⏭️ Update all logging calls
7. ⏭️ Test thoroughly
8. ⏭️ Document changes

## Risk Assessment

**Low Risk:**
- Pump code (already done, working)
- Calibration code (already done, working)

**Medium Risk:**
- Valve control methods (straightforward replacement)
- Sensor reading (more complex, but well-defined)

**High Risk:**
- State synchronization between main.py and managers
- UI update signal connections
- Logging format changes (may affect data analysis)

**Mitigation:**
- Test each phase incrementally
- Keep backup of working code
- Document all changes
- Verify with hardware testing

## Dependencies

**Required for KineticManager integration:**
- KineticManager class must handle flow rate removal (already done ✓)
- Hardware documentation complete (already done ✓)
- Understanding of current valve/sensor logic (this document)

**Blocked by:**
- None - ready to proceed

## Notes

- Flow rate measurements removed from KineticManager (obsolete)
- Sensor thread only handles temperature now
- All "flow" references can be removed during cleanup
- PicoKNX/PicoKNX2 excluded from KineticManager (obsolete hardware)
