# 6-Port Valve Safety Timeout Feature

## Overview
The 6-port valve safety timeout provides a **fallback safety mechanism** for manual valve operations where no specific contact time is defined. For programmatic operations with calculated contact times (like prime pump, live data acquisition), valves stay open as needed without automatic shutoff.

## Key Principle

**Valves close automatically ONLY when there is NO calculated contact time specified.**

- ✅ **Programmatic operations** (prime pump, live data, calibration): Valves stay open for the calculated duration
- ⚠️ **Manual operations** (testing, debugging, no time defined): 5-minute safety timeout prevents indefinite operation

## Usage Modes

### 1. **Default: No Timeout (Programmatic Operations)**
When contact time is calculated or known, valves stay open without automatic shutoff:

```python
ctrl.knx_six(state=1, ch=1)  # Opens, stays open (no timeout)
ctrl.knx_six_both(state=1)    # Opens both, stay open (no timeout)
```

**Use case:** Prime pump, live data acquisition, calibration sequences
**Log output:**
```
✓ KC1 6-port valve → INJECT (cycle 1)
```

### 2. **Safety Timeout (Manual Operations)**
For manual control without calculated contact time, explicitly request 5-minute safety timeout:

```python
ctrl.knx_six(state=1, ch=1, timeout_seconds=300)  # 5-minute safety fallback
ctrl.knx_six_both(state=1, timeout_seconds=300)   # Both valves with safety timeout
```

**Use case:** Manual testing, debugging, unknown duration operations
**Log output:**
```
✓ KC1 6-port valve → INJECT (cycle 1) [Safety timeout: 300s]
```

### 3. **Custom Timeout (Quick Testing)**
Specify custom timeout for rapid testing:

```python
ctrl.knx_six(state=1, ch=1, timeout_seconds=30)  # 30-second test
```

**Log output:**
```
✓ KC1 6-port valve → INJECT (cycle 1) [Safety timeout: 30s]
```

### 4. **Automatic Timer Cancellation**
Closing a valve manually cancels any active timeout timer:

```python
ctrl.knx_six(state=1, ch=1, timeout_seconds=300)  # Opens with 5-minute timeout
time.sleep(60)
ctrl.knx_six(state=0, ch=1)  # Closes valve and cancels timer
```

## When to Use Safety Timeout

### ✅ Apply Timeout (timeout_seconds=300)
- **Manual valve control** via UI toggle
- **Testing/debugging** without defined duration
- **Emergency operations** without calculated contact time
- **Unknown duration** operations

### ❌ Don't Apply Timeout (timeout_seconds=None, default)
- **Prime pump operations** (calculated ~60-120s duration)
- **Live data acquisition** (known acquisition period)
- **Calibration sequences** (defined calibration duration)
- **Any programmatic operation** with calculated contact time

## Implementation Details

### Thread-Safe Design
- Uses `threading.Lock()` for safe timer management
- Each valve (ch=1, ch=2) has independent timer tracking
- Timers are daemon threads (won't block program exit)

### Auto-Shutoff Behavior
When a timeout expires:
1. Valve is forced to LOAD position (state=0)
2. Warning logged: `⚠️ SAFETY TIMEOUT: 6-port valve X auto-shutoff after 300s`
3. Confirmation logged: `✓ KCX 6-port valve auto-closed (LOAD position)`

### Error Handling
- Errors during auto-shutoff are logged but don't raise exceptions
- Failed auto-shutoff attempts are logged for debugging

## Usage Examples

### Example 1: Prime Pump Operation (No Timeout)
```python
# Prime pump has calculated duration (~60-120s)
# Valves stay open for the calculated contact time
ctrl.knx_six_both(state=1)  # NO timeout - programmatic operation
time.sleep(60)  # Calculated contact time
ctrl.knx_six_both(state=0)  # Manual close after calculated duration
```

### Example 2: Manual Valve Testing (With Timeout)
```python
# Manual testing without calculated duration
# Apply safety timeout as fallback
ctrl.knx_six(state=1, ch=1, timeout_seconds=300)  # 5-minute safety fallback
# Valve auto-closes after 5 minutes if not manually closed
```

### Example 3: Live Data Acquisition (No Timeout)
```python
# Acquisition has defined duration (e.g., 10 minutes)
# Valves stay open for acquisition period
ctrl.knx_six_both(state=1)  # NO timeout - known acquisition duration
# ... 10 minutes of data acquisition ...
ctrl.knx_six_both(state=0)  # Close when acquisition completes
```

### Example 4: Quick Manual Test (Short Timeout)
```python
# Quick manual test with short safety timeout
ctrl.knx_six(state=1, ch=1, timeout_seconds=30)  # 30-second test timeout
# Valve auto-closes after 30 seconds
```

## Configuration

### Timeout Constant
The default timeout is defined as a class constant:

```python
class PicoEZSPR(FlowController):
    VALVE_SAFETY_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes
```

To change the default timeout globally, modify this value in `affilabs/utils/controller.py`.

### Recommended Timeout Values

| Use Case | Recommended Setting | Rationale |
|----------|---------------------|-----------|
| Prime pump | No timeout (default) | Calculated contact time ~60-120s |
| Live data acquisition | No timeout (default) | Known acquisition duration |
| Calibration | No timeout (default) | Defined calibration sequence duration |
| Manual UI toggle | `timeout_seconds=300` | No calculated time - safety fallback |
| Testing/debugging | `timeout_seconds=30-300` | Safety fallback for unknown duration |
| Emergency override | `timeout_seconds=300` | Safety fallback when time unknown |

## Safety Considerations

### ✅ Safe Practices
- **Use default (no timeout)** for all programmatic operations with calculated contact times
- **Apply timeout_seconds=300** for manual operations without defined duration
- **Monitor logs** for safety timeout warnings
- **Close valves programmatically** when operation completes

### ⚠️ Design Philosophy
The safety timeout is a **fallback mechanism**, not the primary control method:
1. **Primary control:** Programmatic close after calculated contact time
2. **Fallback safety:** Automatic timeout only when no time is defined
3. **Manual operations:** Explicitly request timeout for safety

### ❌ Unsafe Practices
- Relying on timeout for normal operation (should close programmatically)
- Using very long timeouts (>30 minutes) for manual operations
- Ignoring safety timeout warnings in logs
- Not defining contact times for automated sequences

## Testing

Run the test script to verify safety timeout behavior:

```bash
python test-valve-safety.py
```

This script demonstrates:
1. Default 5-minute timeout
2. Custom 10-second timeout (auto-shutoff visible)
3. No timeout (timeout=0)
4. Both valves with custom timeout

## Troubleshooting

### Issue: Valve closes unexpectedly
**Cause:** Safety timeout expired during long operation
**Solution:** Increase `timeout_seconds` parameter

### Issue: Valve doesn't auto-close
**Cause:** Timer not started or `timeout_seconds=0` used
**Solution:** Check logs for timer start confirmation, verify timeout parameter

### Issue: Multiple auto-shutoff warnings
**Cause:** Valve being re-opened without closing first
**Solution:** Always close valve before re-opening, or timer will reset

## Backward Compatibility

**✅ Existing code continues to work** - the behavior is now correct by default:

```python
# Programmatic operations (NO timeout by default - correct behavior)
ctrl.knx_six(state=1, ch=1)  # Stays open, no automatic timeout
ctrl.knx_six_both(state=1)   # Stays open, no automatic timeout

# Manual operations (ADD timeout for safety)
ctrl.knx_six(state=1, ch=1, timeout_seconds=300)  # 5-minute safety fallback
ctrl.knx_six_both(state=1, timeout_seconds=300)   # Both valves with safety
```

**Migration Notes:**
- Prime pump, calibration, live data: Already correct (no timeout needed)
- Manual UI controls: **Add `timeout_seconds=300`** for safety fallback
- Testing scripts: **Add `timeout_seconds=30-60`** for quick safety

## Log Messages

### Normal Operation (No Timeout)
```
✓ KC1 6-port valve → INJECT (cycle 1)
✓ 6-port valves both set to INJECT (cycles: V1=1, V2=1)
✓ KC1 6-port valve → LOAD (cycle 1)
```

### With Safety Timeout
```
✓ KC1 6-port valve → INJECT (cycle 1) [Safety timeout: 300s]
✓ 6-port valves both set to INJECT (cycles: V1=1, V2=1) [Safety timeout: 300s]
```

### Safety Timeout Triggered
```
⚠️ SAFETY TIMEOUT: 6-port valve 1 auto-shutoff after 300s
✓ KC1 6-port valve auto-closed (LOAD position)
```

### Debug Messages
```
Started 300s safety timer for 6-port valve 1
Cancelled safety timer for 6-port valve 1
```

Enable debug logging to see timer management details:
```python
logging.getLogger('affilabs.utils.controller').setLevel(logging.DEBUG)
```
