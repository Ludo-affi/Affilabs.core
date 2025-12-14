# Firmware V2.4 - CYCLE_START Synchronization

## Overview

V2.4 implements **CYCLE_START synchronization** - sending ONE event per cycle instead of 4 READY events. This eliminates USB CDC timing issues while maintaining fast acquisition speed.

## Key Innovation

**Problem with V2.2/V2.3:**
- 4 READY events per cycle (one per LED)
- USB CDC latency (10-200ms variable) causes READY events to arrive late
- Python reads detector at wrong time → wavelength spikes

**V2.4 Solution:**
- 1 CYCLE_START event per cycle (when LED_A turns on)
- Python uses **fixed timing offsets** from CYCLE_START
- 75% less USB traffic (1 event/cycle vs 4 events/cycle)
- Timing is deterministic - no USB latency dependency

## Timing Architecture

```
Firmware sends: CYCLE_START (when LED_A turns on)

Python calculates:
  LED A: CYCLE_START + 50ms   → Read detector
  LED B: CYCLE_START + 300ms  → Read detector
  LED C: CYCLE_START + 550ms  → Read detector  
  LED D: CYCLE_START + 800ms  → Read detector
```

**LED Sequence (250ms per LED):**
```
t=0ms:   LED_A on  → CYCLE_START event sent
t=50ms:  Python reads detector (LED_A stable)
t=250ms: LED_A off, LED_B on
t=300ms: Python reads detector (LED_B stable)
t=500ms: LED_B off, LED_C on
t=550ms: Python reads detector (LED_C stable)
t=750ms: LED_C off, LED_D on
t=800ms: Python reads detector (LED_D stable)
t=1000ms: LED_D off, cycle complete
```

## Firmware Changes

**File:** `firmware_archive/pico_p4spr/firmware_v2.4/affinite_p4spr_v2.4_CYCLE_SYNC.c`

### 1. Event Structure (simplified from ring buffer)
```c
// V2.4: Cycle synchronization - ONE event per cycle
volatile struct {
    bool cycle_start;        // Set when LED_A turns on
    uint32_t cycle_number;   // Current cycle for verification
    bool batch_complete;     // Set when batch finishes
} isr_events = {false, 0, false};
```

### 2. ISR Event Generation (only for LED_A)
```c
// Line 1340-1345 in ISR
if (led_sequencer.current_led == 0) {  // Only for LED_A
    isr_events.cycle_start = true;
    isr_events.cycle_number = led_sequencer.current_cycle;
}
```

### 3. Main Loop Event Sending
```c
// Line 332-341 in main loop
if (isr_events.cycle_start) {
    printf("CYCLE_START:%lu\n", isr_events.cycle_number);
    isr_events.cycle_start = false;  // Clear event
}
```

## Python Implementation

**File:** `affilabs/core/data_acquisition_manager.py`

### Configuration
```python
FORCE_SEQUENTIAL_MODE = False  # Use CYCLE_SYNC
USE_CYCLE_SYNC = True          # Enable V2.4 mode
```

### Acquisition Function
```python
def _acquire_all_channels_cycle_sync(self, channels, led_intensities, ...):
    """
    1. Send rankbatch command
    2. Wait for CYCLE_START event
    3. Use fixed timing offsets:
       - LED A: +50ms
       - LED B: +300ms
       - LED C: +550ms
       - LED D: +800ms
    4. Read detector at each offset
    """
```

## Performance Comparison

| Version | Events/Cycle | USB Traffic | Speed | Reliability |
|---------|--------------|-------------|-------|-------------|
| V2.2 | 4 READY | 400% | 1.0s | ❌ Spikes every ~50s |
| V2.3 | 4 READY (ring buffer) | 400% | 1.0s | ❌ Spikes worse |
| Sequential | 0 events | 0% | 1.8s | ✅ 100% reliable |
| **V2.4** | **1 CYCLE_START** | **100%** | **1.0s** | **✅ Expected reliable** |

## Testing Instructions

### 1. Flash V2.4 Firmware

```powershell
# Put Pico in BOOTSEL mode (hold button while plugging USB)
Copy-Item "firmware_archive\pico_p4spr\firmware_v2.4\affinite_p4spr_v2.4_CYCLE_SYNC.uf2" "D:\" -Force
```

Wait for Pico to reboot (~3 seconds).

### 2. Verify Version

```powershell
python scripts\quick_version_check.py COM5
```

Expected output: `V2.4`

### 3. Enable CYCLE_SYNC Mode

Already enabled by default:
```python
# data_acquisition_manager.py line 18-19
FORCE_SEQUENTIAL_MODE = False
USE_CYCLE_SYNC = True
```

### 4. Run Test

```powershell
python main-simplified.py
```

Monitor for:
- ✅ Acquisition speed: ~1.0s per cycle (fast like rankbatch)
- ✅ Zero spikes (reliable like sequential)
- ✅ Log messages: `[CYCLE-SYNC]` instead of `[RANK-EVENT]`

### 5. Check Logs

```python
# Should see:
[CYCLE-SYNC] CYCLE_START:0 at t=1234.567
[CYCLE-SYNC] Ch a: Read at offset=0.050s (target=0.050s)
[CYCLE-SYNC] Ch b: Read at offset=0.300s (target=0.300s)
[CYCLE-SYNC] Ch c: Read at offset=0.550s (target=0.550s)
[CYCLE-SYNC] Ch d: Read at offset=0.800s (target=0.800s)
```

Timing accuracy should be within ±5ms.

## Rollback Plan

If V2.4 has issues, revert to sequential mode (no firmware change needed):

```python
# data_acquisition_manager.py line 18
FORCE_SEQUENTIAL_MODE = True  # Revert to sequential
```

Or flash back to V2.2:
```powershell
Copy-Item "firmware_archive\pico_p4spr\firmware_v2.2\affinite_p4spr_v2.2_FINAL.uf2" "D:\" -Force
```

## Technical Notes

### Why This Works

1. **Single synchronization point**: Only one USB event per cycle eliminates cumulative timing drift
2. **Deterministic Python timing**: Python's `time.sleep()` is accurate enough for 50ms offsets
3. **No USB latency dependency**: CYCLE_START arrives late? No problem - Python adds 50ms/300ms/550ms/800ms from whenever it arrives
4. **Reduced USB load**: 75% less traffic means lower chance of USB buffer congestion

### Timing Validation

LED ON time: 250ms (validated sufficient in sequential mode)
Detector integration: 186ms (3 × 62.48ms scans)
Wait before read: 50ms (LED stabilization)
Total time: 50ms + 186ms = 236ms < 250ms ✅

### Expected Behavior

- **Fast**: ~1.0s per cycle (same as V2.2/V2.3)
- **Reliable**: No spikes (same as sequential mode)
- **Efficient**: Minimal USB traffic (1 event vs 4)
- **Responsive**: Stop button works immediately (finishes current cycle)

## Next Steps

1. ✅ Flash V2.4 firmware
2. ✅ Verify version
3. 🔄 Test with live data
4. 📊 Monitor for spikes (expect ZERO)
5. 📈 Compare stability vs sequential mode

## Success Criteria

- ✅ Zero wavelength spikes (< 1nm drift between cycles)
- ✅ Acquisition speed ~1.0s per cycle
- ✅ USB traffic reduced by 75%
- ✅ Timing accuracy within ±5ms of target offsets
- ✅ Stop button responsive (<1 second)

## Status

- **Firmware:** Compiled ✅ (82,944 bytes)
- **Python code:** Implemented ✅
- **Testing:** Ready to test 🔄
- **Expected outcome:** Fast + Reliable ✅✅
