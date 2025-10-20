# Phase 1B: LED Fire-and-Forget Optimization

## Implementation Summary

**Date**: 2025-10-20  
**Status**: ✅ IMPLEMENTED - Ready for testing  
**Expected Impact**: 400ms savings per cycle (1704ms → 1304ms)

## What Was Changed

### File Modified: `utils/hal/pico_p4spr_hal.py`

**Method**: `activate_channel()`  
**Lines**: ~156-195

### Before (Phase 1A - Baseline)
```python
def activate_channel(self, channel: ChannelID) -> bool:
    cmd = f"l{channel.value}\n"
    success = self._send_command_with_response(cmd, expected_response=b"1")
    # ^^^ This waits ~100ms for hardware confirmation!
    if success:
        self.status.active_channel = channel
    return success
```

**Time**: 105ms per channel × 4 = **420ms per cycle**

### After (Phase 1B - Optimized)
```python
def activate_channel(self, channel: ChannelID) -> bool:
    cmd = f"l{channel.value}\n"
    # ✨ Fire-and-forget: Send command without waiting
    self._device.write(cmd.encode())
    time.sleep(0.002)  # 2ms for serial transmission
    self.status.active_channel = channel
    return True
```

**Time**: 2ms per channel × 4 = **8ms per cycle**  
**Savings**: 420ms - 8ms = **412ms per cycle!**

## Why This is Safe

### The LED Settle Delay Safety Net

After LED activation, the code waits 100ms before spectrum acquisition:

```python
# From spr_data_acquisition.py _read_channel_data()
self._activate_channel_batch(ch)  # Now takes 2ms instead of 105ms
t_led_on = perf_counter()

# LED settle delay
if self.led_delay > 0:
    time.sleep(self.led_delay)  # 100ms delay
t_led_settle = perf_counter()

# By this point, hardware has had 100ms to complete the LED activation
# More than enough time for:
# - Polarizer motors to move (~50-80ms)
# - LED PWM to stabilize (~10ms)
```

**Key Insight**: We already wait 100ms for LED stabilization, so we don't need to wait for the serial confirmation. The hardware completes during the settle delay.

## Expected Results

### Timing Predictions

| Component | Phase 1A (Before) | Phase 1B (After) | Improvement |
|-----------|-------------------|------------------|-------------|
| **LED_on** | **105ms** | **2ms** | **-103ms** per channel |
| LED_settle | 100ms | 100ms | (unchanged) |
| scan | 190ms | 190ms | (unchanged) |
| dark | 0-7ms | 0-7ms | (unchanged) |
| trans | 0ms | 0ms | (unchanged) |
| peak | 0-1ms | 0-1ms | (unchanged) |
| **Channel total** | **~400ms** | **~297ms** | **-103ms** |
| | | | |
| **4 channels** | **1600ms** | **1188ms** | **-412ms** |
| **Emit** | 115ms | 115ms | (unchanged) |
| **Cycle total** | **1704ms** | **~1292ms** | **-412ms** ⭐ |
| **Update rate** | **0.59 Hz** | **0.77 Hz** | **+31%** ⭐ |

### Performance Milestones

```
✅ Phase 1A Baseline:     1704ms (0.59 Hz)
⬇️ Phase 1B (current):    ~1292ms (0.77 Hz) [PREDICTED]
🎯 Phase 1C target:       ~1232ms (0.81 Hz) [with GUI throttle]
🏆 Final target:          ~1100ms (0.91 Hz) [matching old software]
```

**Gap remaining after Phase 1B**: 1292ms - 1100ms = 192ms
- Can close with Phase 1C (GUI throttle): 60ms
- Remaining: ~132ms (within acceptable margin)

## Testing Protocol

### Step 1: Basic Functionality Test (5 minutes)
1. Run application: `python run_app.py`
2. Wait for calibration to complete
3. Check console for timing logs
4. **Verify**: 
   - ✅ LEDs actually activate (watch hardware)
   - ✅ Sensorgram displays data
   - ✅ No error messages

### Step 2: Timing Validation (10 minutes)
1. Let run for 20-30 cycles
2. Watch timing logs for:
   ```
   ⏱️ TIMING ch=a: LED_on=2ms, ...  ← Should be ~2ms (not 105ms!)
   ⏱️ TIMING ch=b: LED_on=2ms, ...
   ⏱️ TIMING ch=c: LED_on=2ms, ...
   ⏱️ TIMING ch=d: LED_on=2ms, ...
   ⏱️ CYCLE #10: total=1292ms, ...  ← Should be ~1292ms (not 1704ms!)
   📊 TIMING STATS: avg=1292ms, rate=0.77 Hz
   ```

### Step 3: Signal Quality Validation (30 minutes)
1. Run for 100+ cycles
2. Monitor:
   - ✅ Sensorgram noise < 2 RU
   - ✅ Peak wavelength stable
   - ✅ No unexpected jumps/spikes
   - ✅ Spectroscopy data looks normal

### Step 4: Reliability Test (optional, 1 hour)
1. Run for 500+ cycles
2. Check for:
   - LED activation failures
   - Hardware errors
   - Signal degradation over time

## Rollback Plan (if needed)

If issues are detected:

### Option 1: Immediate Rollback
```python
# In pico_p4spr_hal.py activate_channel()
# Comment out new code, uncomment old code:

# NEW (fire-and-forget):
# self._device.write(cmd.encode())
# time.sleep(0.002)
# return True

# OLD (wait for response):
success = self._send_command_with_response(cmd, expected_response=b"1")
if success:
    self.status.active_channel = channel
return success
```

### Option 2: Configuration Flag
Add to `settings/__init__.py`:
```python
WAIT_FOR_LED_RESPONSE = True  # Set to False for fire-and-forget
```

Then modify code:
```python
if WAIT_FOR_LED_RESPONSE:
    success = self._send_command_with_response(cmd, expected_response=b"1")
else:
    self._device.write(cmd.encode())
    time.sleep(0.002)
    success = True
```

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LED doesn't activate | Very Low | High | LED settle delay gives 100ms; visual check |
| Motor doesn't complete | Very Low | Medium | 100ms is 2× typical motor time |
| Serial command lost | Very Low | Low | Serial protocol has error detection |
| Signal quality degrades | Low | Medium | Test extensively; rollback if needed |
| Hardware damage | Very Low | Very High | No risk - just timing change |

**Overall Risk**: **LOW** ✅
- LED settle delay provides ample time for hardware
- No hardware commands changed, only timing
- Easy rollback if issues detected

## Success Criteria

### Phase 1B is successful if:
- ✅ LED_on time drops to <10ms per channel
- ✅ Cycle time drops to <1350ms (target ~1292ms)
- ✅ Update rate increases to >0.74 Hz (target ~0.77 Hz)
- ✅ No LED activation failures over 100 cycles
- ✅ Signal quality maintained (noise <2 RU)
- ✅ No hardware errors or warnings

### Acceptance Thresholds:
- **Minimum acceptable**: 350ms improvement (1704ms → 1354ms)
- **Target**: 412ms improvement (1704ms → 1292ms)
- **Stretch goal**: 450ms improvement (1704ms → 1254ms)

## Alternative Solutions (if needed)

### If fire-and-forget shows issues:

**Option A: Async Batch Response** (200ms savings)
```python
# Send all 4 commands first
for ch in ['a', 'b', 'c', 'd']:
    self._device.write(f"l{ch}\n".encode())

# Wait once for all responses (100ms total, not 400ms)
time.sleep(0.1)

# Read confirmations
for _ in range(4):
    response = self._device.read_until(b"1")
```

**Option B: Hardware Batch Command** (400ms savings)
```python
# Single command for channel + polarizer + LED
cmd = f"lset {channel} {s_pos} {p_pos} {led_intensity}\n"
self._device.write(cmd.encode())
```
*(Requires firmware support - check PICOP4SPR docs)*

## Next Steps

1. **IMMEDIATE**: Test Phase 1B
   - Run application
   - Collect timing data (20+ cycles)
   - Verify LED_on < 10ms

2. **VALIDATE**: Signal quality
   - Run 100+ cycles
   - Check noise levels
   - Monitor for errors

3. **DOCUMENT**: Results
   - Update PHASE_1B_RESULTS.md
   - Add before/after comparison
   - Note any issues

4. **PROCEED**: Phase 1C (if successful)
   - Implement GUI throttling
   - Target: Additional 60ms savings
   - Final cycle time: ~1232ms

## Code Reference

### Old Code (kept in comments for reference)
The original code is preserved in comments within the `activate_channel()` method:
```python
# OLD CODE (kept for reference - 105ms per channel!):
# success = self._send_command_with_response(cmd, expected_response=b"1")
# if success:
#     self.status.active_channel = channel
#     logger.debug(f"Activated channel {channel.value}")
# else:
#     logger.warning(f"Failed to activate channel {channel.value}")
# return success
```

To revert, simply uncomment this block and remove the fire-and-forget code.

---

**Status**: ✅ Ready to test  
**Expected outcome**: 400ms cycle time improvement  
**Risk level**: Low (LED settle delay provides safety)  
**Test time needed**: 30 minutes  
**Rollback time**: 2 minutes
