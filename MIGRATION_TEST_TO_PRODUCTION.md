# Migration: Test Code to Production

## Summary
Successfully migrated proven, battle-tested injection methods from `test_flow_sidebar_standalone.py` to production code in `affilabs/managers/pump_manager.py`.

**Date**: Migration completed after comprehensive testing and validation of robustness improvements.

---

## Migrated Methods

### 1. `inject_simple(assay_rate: float) -> bool`

**Source**: `test_flow_sidebar_standalone.py::inject_test()` (lines 169-363)  
**Destination**: `affilabs/managers/pump_manager.py::inject_simple()`

**Features**:
- Robust post-terminate readiness wait with `allow_early_termination=True`
- Uses `move_both_to_position(..., wait=True)` for P1000 fill (deterministic completion)
- Immediate 1s motion check after dispense start
- No-motion watchdog during contact time (10s accumulation threshold)
- No-motion watchdog during emptying (10s accumulation threshold)
- Proper valve control (6-port open during contact, closed during emptying)
- Progress signals for UI integration
- Error handling with detailed diagnostics

**Steps**:
1. Terminate any running commands and wait for readiness
2. Move to P1000 (inlet valve, wait for completion)
3. Start dispense at assay rate
4. Immediate motion check (1s)
5. Open 6-port valves
6. Contact time with position monitoring and stall watchdog
7. Close 6-port valves
8. Continue dispensing to empty with stall watchdog

---

### 2. `inject_partial_loop(assay_rate: float) -> bool`

**Source**: `test_flow_sidebar_standalone.py::inject_partial_loop_test()` (lines 365-730)  
**Destination**: `affilabs/managers/pump_manager.py::inject_partial_loop()`

**Features**:
- Comprehensive 14-step partial loop protocol
- Uses `move_both_to_position(..., wait=True)` for P900 and P1000 moves (deterministic completion)
- Volumetric dispenses for contact time and purge (replaces unreliable D0R continuous dispense)
- Safety clamps on requested volumes using live telemetry
- Immediate 1s motion checks after starting contact dispense and purge dispense
- No-motion watchdog during contact time (15s = 3 × 5s intervals)
- No-motion watchdog during purge (15s = 3 × 5s intervals)
- Proper valve sequencing (3-way open for contact, closed/WASTE for purge)
- Detailed diagnostics on stall: pump status, valve states
- Progress signals for UI integration (14 steps, 5% increments)

**Steps**:
1. Move to P900 (inlet valve, wait)
2. Open 3-way valves
3. Open 6-port valves (inject position)
4. Move to P1000 (outlet valve, wait) - pulls sample through loop
5. Close 6-port valves (load position)
6. Push 50 µL at 900 µL/min
7. Wait 10 seconds
8. Open 6-port valves (inject position)
9. Push 40 µL spike at 900 µL/min
10. Close 3-way valves
11. (Flow rate already at assay rate)
12. **Contact time dispense**: Open 3-way valves, volumetric dispense with immediate motion check and watchdog
13. Close 6-port valves after contact
14. **Purge to waste**: Route 3-way to WASTE, volumetric dispense with immediate motion check and watchdog

---

## Key Improvements in Migrated Code

### Robustness
- **Post-terminate readiness**: Wait for pumps to be idle before starting new sequences, avoiding "NOT AT ZERO" errors and race conditions
- **Deterministic completion**: `wait=True` on all `move_both_to_position()` calls replaces blind sleeps
- **Immediate motion checks**: Verify motion starts within 1s of dispense commands
- **No-motion watchdogs**: Detect stalls during long operations (10-15s accumulation threshold)
- **Safety clamps**: Never request more volume than available based on live telemetry

### Valve Handling
- **Step 12 fix**: Open 3-way valves before contact-time dispense (were closed from Step 10)
- **Purge routing**: Route to WASTE for post-contact purge (prevents backflow)
- **Explicit states**: All valve operations logged and verified

### Diagnostics
- Detailed logging of pump positions every 5s during long operations
- Pump status and error messages on stall detection
- Valve state readout on errors (if controller available)

### Integration
- Emits Qt signals: `operation_started`, `operation_progress`, `operation_completed`, `error_occurred`
- Respects `_shutdown_requested` flag for emergency stops
- Manages `_current_operation` state for UI feedback

---

## Controller Helper Used

Both methods rely on the robust `move_both_to_position()` helper added to `affipump_controller.py`:

```python
pump.move_both_to_position(
    target_position_ul,
    speed_ul_s,
    valve_policy='inlet'|'outlet'|'auto',
    wait=True,  # <-- Always True in production inject code
    wait_timeout_extra_s=10
)
```

**Valve policies**:
- `'inlet'`: IR (input route) for both pumps
- `'outlet'`: OR (output route) for both pumps
- `'auto'`: IR for positive delta (aspirate), OR for negative delta (dispense)

**Wait behavior**:
- When `wait=True`, calls `wait_until_both_ready()` and blocks until movement completes or times out
- Eliminates race conditions and ensures deterministic sequencing

---

## Readiness Check Fix

The `wait_until_both_ready()` method in `affipump_controller.py` was updated to support non-zero positions after terminate:

- **Initialization path** (`allow_early_termination=False`): Enforces position must be ~0 µL
- **Post-terminate idle** (`allow_early_termination=True`): Accepts any position (pumps may be at ~920 µL after stopping mid-dispense)

This prevents false "NOT AT ZERO" failures when stopping and restarting operations.

---

## Validation Status

✅ **Test code proven**: All features tested in `test_flow_sidebar_standalone.py` with real hardware  
✅ **Exit Code 0**: Recent test runs complete successfully  
✅ **No static errors**: Production code passes type checks and linting  
✅ **Controller refactor**: Per-pump µL moves replace unreliable broadcast absolute commands  
✅ **UI integration**: Signals wired for live UI feedback  
✅ **Thread cleanup**: QThread lifecycle managed properly  

---

## Next Steps

1. **Wire UI buttons**: Update UI inject button handlers to call `pump_manager.inject_simple()` or `pump_manager.inject_partial_loop()`
2. **Test with live UI**: Validate signal integration, progress updates, and error handling in full application
3. **Telemetry validation**: Monitor Pump1/Pump2 position readouts during Step 12 to confirm expected decrements
4. **Field testing**: Run complete injection cycles under production conditions

---

## Files Modified

- ✅ `affilabs/managers/pump_manager.py`: Added `inject_simple()` and `inject_partial_loop()` methods (migrated from test code)

## Files Previously Modified (Robustness Phase)

- ✅ `affipump/affipump_controller.py`: Added `move_both_to_position()` helper; fixed `wait_until_both_ready()` for non-zero positions
- ✅ `test_flow_sidebar_standalone.py`: Updated all inject methods to use `wait=True`; added watchdogs and motion checks
- ✅ `affilabs/widgets/datawindow.py`: Added `set_inject_callback()` API for UI inject button
