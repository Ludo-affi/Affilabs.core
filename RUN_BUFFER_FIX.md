# Run-Buffer False Jam Detection Fix

## Problem

When clicking "Home Pumps" or stopping buffer flow while the pumps are running, the system falsely reports:
```
[PUMP1] JAMMED - position barely changed (1000.0 → 996.0 µL)
[PUMP2] JAMMED - position barely changed (999.9 → 996.0 µL)
[FAIL] Pump failure detected (P1=True, P2=True)
```

**The pumps are NOT actually jammed** - they were simply stopped mid-operation.

## Root Cause

### Sequence of Events:
1. Buffer flow is running (pumps dispensing from ~1000µL)
2. User clicks "Home Pumps" button
3. System calls `emergency_stop()` → sends `/1TR` and `/2TR` (terminate commands)
4. Pumps stop almost immediately (1000µL → 996µL, only 4µL dispensed)
5. The `wait_until_both_ready()` check sees:
   - Pump finished very quickly (<0.5s)
   - Position barely changed (<10µL)
6. **False jam detection** - interprets this as a stuck/jammed pump

### The Logic Error:

The jam detection code in `affipump_controller.py` has two checks:
- **Time check**: If pump completes in <0.5s, it's jammed
- **Position check**: If pump moves <10µL, it's jammed

These checks are **correct for normal operations** but **fail when pump is terminated externally**.

## Solution

### Added `allow_early_termination` parameter

**Files Modified:**
1. [affipump/affipump_controller.py](affipump/affipump_controller.py#L620)
2. [affipump/\_\_init\_\_.py](affipump/__init__.py#L245)
3. [affilabs/managers/pump_manager.py](affilabs/managers/pump_manager.py#L777,L811)

### How It Works:

When `allow_early_termination=True`:
- **Skip time check** - Allow quick completion (pump was terminated)
- **Skip position check** - Don't expect significant movement (pump was stopped)
- **Still check errors** - Real errors (faults, initialization failures) are still caught

### Implementation:

```python
# In pump_manager.py run_buffer():
p1_ready, p2_ready, ... = await run_in_executor(
    None, 
    lambda: pump._pump.wait_until_both_ready(
        timeout_s=60.0,
        allow_early_termination=self._shutdown_requested  # Key: Check if user stopped
    )
)
```

When `self._shutdown_requested` is True (user clicked Stop/Home), the jam detection is disabled.

### Logic Flow:

```
Normal Operation:
  Pump completes → Check time & position → Report jam if suspicious ✅

User Stops Pump:
  Pump terminates → Skip time & position checks → Clean exit ✅
```

## Testing

### Before Fix:
```
User clicks Home → FALSE JAM → Error dialog → Requires restart
```

### After Fix:
```
User clicks Home → Clean termination → Pumps home successfully ✅
```

### Real Jam Detection Still Works:
```python
# If pump REALLY jams during normal operation:
pump.aspirate_both(1000, 24000)  # Command sent
# ... pump gets stuck ...
wait_until_both_ready(allow_early_termination=False)  # Still catches jam ✅
```

## Summary

**What Changed:**
- Added `allow_early_termination` parameter to jam detection logic
- Buffer flow operations now check `_shutdown_requested` flag before waiting
- When shutdown requested, jam detection is bypassed

**Impact:**
- ✅ No more false jam errors when stopping buffer flow
- ✅ Real jams still detected during normal operations
- ✅ Clean shutdown when user clicks Home or Stop buttons
- ✅ Backwards compatible (default behavior unchanged)

**Files Changed:**
- `affipump/affipump_controller.py` - Core jam detection logic
- `affipump/__init__.py` - Wrapper API
- `affilabs/managers/pump_manager.py` - Buffer flow implementation
- `affilabs/utils/oem_calibration_tool.py` - Polarizer auto-correction (unrelated fix)
