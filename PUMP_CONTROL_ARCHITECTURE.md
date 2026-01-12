# Pump Control Architecture

## Overview
Proper architecture for pump control with support for **stopping operations** and **changing flow rates on-the-fly**.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer (Sidebar Controls)                                │
│  - Start/Pause Button                                       │
│  - STOP Button (Emergency)                                  │
│  - Setup Flow Rate Spinner                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Application Layer (main.py)                                │
│  - _on_pump_start_pause_clicked()                          │
│  - _on_pump_stop_clicked()                                 │
│  - Event handlers & UI coordination                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Data Acquisition Manager                                   │
│  - start_pump_buffer()   ← Starts continuous flow          │
│  - stop_pump_buffer()    ← Stops via PumpManager API       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Pump Manager (HIGH-LEVEL API)                             │
│  PUBLIC METHODS:                                            │
│  - run_buffer(...)         ← Async pump operation          │
│  - stop_current_operation(immediate=True/False)             │
│  - change_flow_rate_on_the_fly(flow_rate_ul_min)          │
│                                                             │
│  STATE TRACKING:                                            │
│  - _current_operation: PumpOperation enum                   │
│  - _shutdown_requested: bool                                │
│  - _current_flow_rate: float                                │
│  - _current_aspirate_rate: float                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Hardware Manager → Affipump Controller                     │
│  - pump._pump.pump.send_command("/1TR")                    │
│  - pump._pump.pump.set_speed_on_the_fly(pump_num, speed)  │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. **Encapsulation**
✅ **DO:** Use public API methods
```python
# Correct - uses public API
self._pump_mgr.stop_current_operation(immediate=True)
success = self._pump_mgr.change_flow_rate_on_the_fly(50.0)
```

❌ **DON'T:** Access private state directly
```python
# Wrong - breaks encapsulation
self._pump_mgr._shutdown_requested = True  # BAD!
self._pump_mgr._current_operation = PumpOperation.IDLE  # BAD!
```

### 2. **State Management**
The `PumpManager` owns pump state:
- `_current_operation`: Tracks what pump is doing (IDLE, RUNNING_BUFFER, PRIMING, etc.)
- `_shutdown_requested`: Flag for graceful shutdown
- `_current_flow_rate`: Active dispense rate
- `_current_aspirate_rate`: Active aspirate rate

### 3. **Thread Safety**
- `run_buffer()` runs in background thread via asyncio
- `stop_current_operation()` is thread-safe (sets flag + sends hardware commands)
- `change_flow_rate_on_the_fly()` is thread-safe (direct hardware command)

## Control Flows

### STOP Button Flow
```
User clicks STOP
    ↓
_on_pump_stop_clicked()
    ↓
pump_mgr.stop_current_operation(immediate=True)
    ↓
├─ Sets _shutdown_requested = True
├─ Sends /1TR to pump 1
├─ Sends /2TR to pump 2  (hardware termination)
└─ Sets _current_operation = IDLE
    ↓
Pumps stop immediately
UI resets to "Start" state
```

### Flow Rate Change Flow
```
User changes Setup spinner
    ↓
on_setup_flowrate_changed(value)
    ↓
if pump is running:
    pump_mgr.change_flow_rate_on_the_fly(value)
        ↓
    ├─ Validates: 1 ≤ value ≤ 10000 µL/min
    ├─ Checks operation: RUNNING_BUFFER or PRIMING
    ├─ Converts to µL/s: speed = value / 60.0
    └─ pump.set_speed_on_the_fly(1, speed)
       pump.set_speed_on_the_fly(2, speed)
        ↓
    Flow rate changes immediately
    User sees confirmation tooltip
```

### Start Buffer Flow
```
User clicks Start/Pause
    ↓
_on_pump_start_pause_clicked(checked=True)
    ↓
data_mgr.start_pump_buffer()
    ↓
├─ Reads Setup flow rate from sidebar
├─ Creates background thread
└─ Launches pump_mgr.run_buffer(cycles=0, flow_rate=X)
    ↓
Continuous buffer flow starts
UI shows "Pause" button
```

## Error Handling

### Flow Rate Changes
- **Pump not available**: Returns False, shows warning tooltip
- **Wrong operation**: Only works during RUNNING_BUFFER or PRIMING
- **Invalid range**: Rejects values outside 1-10000 µL/min
- **Hardware error**: Logs error, returns False

### Stop Operations
- **Already idle**: Returns True immediately (no-op)
- **Hardware unavailable**: Sets flag only (graceful)
- **Immediate mode**: Sends terminate commands, returns success/fail
- **Graceful mode**: Sets flag, waits for checkpoint

## Safety Features

1. **Validation**: Flow rates validated (1-10000 µL/min)
2. **State checks**: Operations only allowed in valid states
3. **Error recovery**: All operations return bool success status
4. **Thread cleanup**: 2-second timeout for thread joins
5. **Hardware checks**: Verifies pump availability before commands
6. **Capability checks**: Confirms pump supports `set_speed_on_the_fly()`

## Testing Checklist

- [ ] Start pump → shows "Pause" button
- [ ] Pause pump → shows "Start" button, pumps stop
- [ ] STOP button → pumps terminate immediately, UI resets
- [ ] Change flow rate while running → rate changes, tooltip shows
- [ ] Change flow rate while idle → no action (expected)
- [ ] Invalid flow rate (0, 99999) → rejected
- [ ] Pump not connected → graceful error messages
- [ ] Multiple rapid stops → no crash
- [ ] Multiple rapid flow rate changes → last value wins

## File Locations

| Component | File |
|-----------|------|
| Pump Manager | `affilabs/managers/pump_manager.py` |
| Data Acquisition | `affilabs/core/data_acquisition_manager.py` |
| UI Controls | `affilabs/sidebar_tabs/AL_flow_builder.py` |
| Event Handlers | `main.py` |
| Hardware | `affipump/affipump_controller.py` |

## Recent Fixes (2026-01-07)

### Issues Fixed:
1. ✅ STOP button now sends immediate termination commands (`/1TR`, `/2TR`)
2. ✅ Flow rate changes use proper API instead of bypassing PumpManager
3. ✅ Removed direct access to `_shutdown_requested` and `_current_operation`
4. ✅ Added delays after termination for command processing
5. ✅ Fixed duplicate docstring parameters in `run_buffer()`
6. ✅ Added validation for flow rate range (1-10000 µL/min)
7. ✅ Added capability check for `set_speed_on_the_fly()` support
8. ✅ Improved user feedback with tooltips
9. ✅ Better thread cleanup in `stop_pump_buffer()`
10. ✅ Proper error handling throughout

### Architecture Improvements:
- **Clear separation of concerns**: UI → Application → Manager → Hardware
- **Proper encapsulation**: No direct state manipulation from outside
- **Thread-safe operations**: All public methods safe to call from any thread
- **Defensive programming**: Validates inputs, checks state, handles errors
- **User feedback**: Visual confirmation of operations via tooltips
