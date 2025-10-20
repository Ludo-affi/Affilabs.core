# LED Control Bottleneck - Root Cause Found!

## Problem Summary

**Symptom**: LED activation takes 105ms per channel (420ms total per cycle)
**Expected**: <10ms per channel (<40ms total)
**Impact**: 380ms wasted per cycle (63% of performance gap!)

## Root Cause Identified

### Code Path Analysis

**File**: `utils/spr_data_acquisition.py` line 466
```python
self._activate_channel_batch(ch)  # Takes 105ms!
```

↓

**File**: `utils/spr_data_acquisition.py` lines 1024-1075
```python
def _activate_channel_batch(self, channel: str, intensity: int | None = None) -> bool:
    # Uses batch command OR falls back to sequential
    if not self._batch_led_available or not self.ctrl:
        self.ctrl.turn_on_channel(ch=channel)  # Fallback path
```

↓

**File**: `utils/hal/pico_p4spr_hal.py` lines 156-185
```python
def activate_channel(self, channel: ChannelID) -> bool:
    cmd = f"l{channel.value}\n"  # e.g., "la\n", "lb\n", "lc\n", "ld\n"
    success = self._send_command_with_response(cmd, expected_response=b"1")
    #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #         THIS IS THE BOTTLENECK! Waits for hardware response (~100ms)
```

### The Problem

The `_send_command_with_response()` method:
1. Sends serial command to hardware
2. **WAITS** for hardware to:
   - Move polarizer motors (if needed)
   - Adjust LED PWM
   - Send back confirmation "1"
3. This takes ~100-105ms per channel

**Total waste**: 4 channels × 105ms = **420ms per cycle**

## Why This is Slow

### Serial Communication Timeline
```
[Python sends "la\n"] → [Serial TX] → [Hardware receives] 
                                          ↓
                        [Motors move: ~50-80ms]
                                          ↓
                        [LED adjusts: ~10ms]
                                          ↓
[Python receives "1"] ← [Serial RX] ← [Hardware sends "1"]

TOTAL: ~100-105ms (dominated by motor movement + serial latency)
```

### Why Old Software is Faster

Looking at `Old software/main/main.py` lines 1600-1620:
- Old software likely **doesn't wait for confirmation**
- Sends command and immediately continues
- OR uses async/fire-and-forget serial commands
- OR hardware responds faster (different firmware?)

## Solution Options

### Option 1: Remove Response Wait (FASTEST - 400ms savings) ⭐⭐⭐⭐⭐

**Change**: Send LED command without waiting for confirmation

```python
# In pico_p4spr_hal.py
def activate_channel(self, channel: ChannelID) -> bool:
    cmd = f"l{channel.value}\n"
    # OLD: self._send_command_with_response(cmd, expected_response=b"1")
    # NEW: self._send_command_no_response(cmd)  # Fire and forget
    self._device.write(cmd.encode())
    time.sleep(0.001)  # 1ms for serial TX
    return True
```

**Pros**:
- **Immediate 400ms savings** (105ms → 5ms per channel)
- Gets us to ~1300ms cycle time (target 1100ms)
- Simple implementation

**Cons**:
- No confirmation that LED actually activated
- Could mask hardware failures
- Need to ensure commands complete before next operation

**Risk Mitigation**:
- LED settle delay (100ms) gives time for hardware to complete
- Can add validation in calibration/startup
- Monitor for LED failures via other signals

### Option 2: Async LED Control (MEDIUM - 200ms savings) ⭐⭐⭐

**Change**: Send all 4 channel commands, then wait for responses in parallel

```python
def activate_all_channels_async(self):
    # Send all commands first
    for ch in ['a', 'b', 'c', 'd']:
        self._device.write(f"l{ch}\n".encode())
    
    # Wait for all responses (100ms once, not 400ms total)
    time.sleep(0.1)
    
    # Read confirmations
    for _ in range(4):
        response = self._device.read_until(b"1")
```

**Pros**:
- Still gets confirmation
- ~200ms savings (400ms → 200ms for 4 channels)
- More reliable than Option 1

**Cons**:
- More complex implementation
- Need to handle response ordering
- Still 200ms slower than optimal

### Option 3: Batch Command (BEST - 400ms savings) ⭐⭐⭐⭐⭐

**Change**: If hardware supports it, send single command for channel activation

```python
# Single command activates channel with LED
cmd = f"lset {channel} {s_pos} {p_pos} {led_intensity}\n"
self._device.write(cmd.encode())
time.sleep(0.001)  # 1ms for TX
```

**Pros**:
- **Best performance** (105ms → 5ms)
- Clean API
- Hardware handles everything atomically

**Cons**:
- Requires firmware support (check PICOP4SPR docs)
- Need to verify command exists
- May need firmware update

## Recommended Implementation Plan

### Phase 1B-Step1: Test Fire-and-Forget (1 hour) ⭐⭐⭐⭐⭐

**Quick test to validate hypothesis**:

1. Comment out response wait in `pico_p4spr_hal.py`:
   ```python
   def activate_channel(self, channel: ChannelID) -> bool:
       cmd = f"l{channel.value}\n"
       # OLD: success = self._send_command_with_response(cmd, expected_response=b"1")
       # TEMP TEST: Just send and don't wait
       self._device.write(cmd.encode())
       time.sleep(0.002)  # 2ms for serial transmission
       self.status.active_channel = channel
       return True
   ```

2. Re-run timing test
3. **Expected result**: LED_on drops from 105ms to <10ms
4. **Expected cycle time**: ~1300ms (vs current 1704ms)

### Phase 1B-Step2: Validate Reliability (30 min)

1. Run 100+ cycles
2. Check for LED failures/errors
3. Verify signal quality maintained
4. Monitor sensorgram stability

### Phase 1B-Step3: Production Implementation (2 hours)

1. If test successful:
   - Add configuration flag: `WAIT_FOR_LED_RESPONSE = False`
   - Keep response-wait code for debugging mode
   - Add startup validation to confirm LEDs working
   
2. If test shows issues:
   - Implement Option 2 (async) or Option 3 (batch)
   - Add proper error handling

## Expected Results

### Before (Current - Phase 1A data)
```
LED_on: 105ms/channel × 4 = 420ms
Total cycle: 1704ms
Rate: 0.59 Hz
```

### After (Phase 1B - fire-and-forget)
```
LED_on: 5ms/channel × 4 = 20ms
Total cycle: ~1304ms (1704 - 400 = 1304ms)
Rate: 0.77 Hz
```

### Final Target (with GUI throttle)
```
LED_on: 5ms/channel × 4 = 20ms
Emit: 50ms (vs 115ms with throttle)
Total cycle: ~1239ms
Rate: 0.81 Hz
```

## Hardware Verification Needed

### Check Firmware Documentation
- Does `l{channel}` command NEED confirmation?
- Is there a no-wait variant?
- Can we batch polarizer + LED in one command?

### Test Questions
1. What happens if we don't wait for "1" response?
2. Does hardware queue commands properly?
3. Is 100ms LED settle delay sufficient for motor movement?

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LED doesn't activate | Low | High | LED settle delay gives time; add validation |
| Command lost | Very Low | Medium | Serial protocol has checksums |
| Motor collision | Very Low | High | Commands are sequential, settle time prevents |
| Signal quality | Low | High | Test extensively before production |

## Success Criteria

✅ Phase 1B Success:
- LED_on time < 10ms per channel
- Cycle time < 1350ms
- No increase in noise levels
- No LED activation failures over 100 cycles

## Next Action

**IMMEDIATE**: Test Option 1 (fire-and-forget)
- Time investment: 30 minutes
- Potential savings: 400ms per cycle (70% of gap!)
- Low risk with LED settle delay

**File to modify**: `utils/hal/pico_p4spr_hal.py` line ~170
**Test command**: `python run_app.py` and watch timing logs

---

**Status**: 🔴 Bottleneck identified, fix ready to test
**Expected improvement**: 400ms per cycle (1704ms → 1304ms)
**Risk level**: Low (LED settle delay provides safety margin)
