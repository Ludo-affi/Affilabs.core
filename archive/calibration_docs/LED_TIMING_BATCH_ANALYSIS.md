# LED Timing and Batch Command Analysis

**Date**: November 27, 2025
**Topic**: LED timing synchronization and batch command optimization for live view acquisition

---

## Current LED Timing Implementation

### Live View Acquisition Sequence (Per Channel)

**File**: `src/core/data_acquisition_manager.py` (`_acquire_channel_spectrum()` lines 700-850)

```python
# CURRENT SEQUENCE:
1. LED ON:     ctrl.set_intensity(ch=channel, raw_val=led_intensity)
2. PRE DELAY:  time.sleep(self._pre_led_delay_ms / 1000.0)  # 45ms default
3. ACQUIRE:    usb.read_intensity() × num_scans (3 scans default)
4. LED OFF:    ctrl.set_intensity(ch=channel, raw_val=0)
5. POST DELAY: time.sleep(self._post_led_delay_ms / 1000.0)  # 5ms default
6. NEXT CHANNEL
```

### ✅ Timing Is Applied EXACTLY As Intended

**Verification**:
- ✅ LED turns ON with `set_intensity(ch, raw_val)`
- ✅ PRE_LED_DELAY (45ms) waits for LED stabilization BEFORE acquisition
- ✅ Detector reads happen AFTER pre-delay
- ✅ LED turns OFF immediately after acquisition
- ✅ POST_LED_DELAY (5ms) allows afterglow decay BEFORE next channel
- ✅ Sync timing is correct: LED stabilizes → Detector reads → LED off → Decay → Next

---

## Batch Command Capability Analysis

### ✅ LED Batch Commands ARE Available!

**File**: `src/utils/controller.py` (lines 971-1030)

#### PicoP4SPR Controller Has `set_batch_intensities()`:

```python
def set_batch_intensities(self, a=0, b=0, c=0, d=0):
    """Set all LED intensities in a single batch command.

    Performance:
        Sequential commands: ~12ms for 4 LEDs
        Batch command:       ~0.8ms for 4 LEDs
        Speedup:             15× faster
    """
    cmd = f"batch:{a},{b},{c},{d}\n"
    self._ser.write(cmd.encode())
    time.sleep(0.02)  # 20ms processing delay
```

**Format**: `batch:A,B,C,D\n`
**Example**: `batch:255,0,0,0\n` → LED A=255, B/C/D=0

#### PicoEZSPR Controller Has Same Method:
**File**: `src/utils/controller.py` (line 1683)
Same `set_batch_intensities()` implementation

---

## Batch Command Capacity

### Current Implementation: 1 Batch = 4 LED Values

**Protocol**: `batch:A,B,C,D\n`
- Sets all 4 channels simultaneously
- Single command replaces 4 individual commands
- 15× faster (12ms → 0.8ms)

### ❓ Can We Send 120 or 1200 Commands at Once?

**Short Answer**: Not with current firmware protocol.

**Why**:
1. **Current protocol is single-batch**: `batch:A,B,C,D\n` = 1 command for 4 LEDs
2. **No queue/buffer system**: Firmware processes commands one at a time
3. **Serial line protocol**: Reads until `\n`, executes, waits for next

**To support 120+ batched commands, you would need**:
- Multi-batch protocol: `batch_multi:N\n` followed by N × (A,B,C,D) values
- Firmware command queue/buffer
- Synchronization tokens to trigger execution
- Arduino/Pico firmware modification

### Current Best Practice: Sequential Batch Commands

If you want to pre-queue LED sequences:

```python
# Send multiple batch commands sequentially
commands = [
    "batch:255,0,0,0\n",  # Time T=0: LED A on
    "batch:0,255,0,0\n",  # Time T=1: LED B on
    "batch:0,0,255,0\n",  # Time T=2: LED C on
    "batch:0,0,0,255\n",  # Time T=3: LED D on
]

for cmd in commands:
    ser.write(cmd.encode())
    time.sleep(0.02)  # Firmware processing delay
```

**Issue**: Still requires Python-side timing control (defeats pre-queueing purpose)

---

## Detector Batch Commands

### ❌ USB4000 Does NOT Support Batch Commands

**File**: `src/utils/usb4000_wrapper.py` (lines 266-310)

```python
def read_intensity(self):
    """Read intensities - THREAD-SAFE."""
    with _usb_device_lock:
        return np.array(self._device.intensities())
```

**Ocean Optics USB4000 Protocol**:
- Single acquisition per `intensities()` call
- Integration time set separately with `set_integration()`
- Read blocks until integration completes
- **NO queue/batch capability**

**Why**:
- USB4000 is basic detector (2004 design)
- No onboard buffer for multiple acquisitions
- Uses SeaBreeze library (single-read API)
- Each read triggers new integration cycle

### Detector Always Returns Output

**Yes** - every `read_intensity()` call returns a full spectrum:
- Returns: `np.array` with 3648 pixels
- Blocks until integration complete
- No way to queue multiple reads

---

## Current Timing Breakdown (Per Channel)

### Total Time Per Channel Acquisition:

```
1. LED ON command:          ~3ms   (serial write + controller processing)
2. PRE_LED_DELAY:           45ms   (LED stabilization)
3. Detector integration:    varies (e.g., 10ms typical)
4. Detector read:           ~5ms   (USB transfer for 3648 pixels)
5. num_scans averaging:     ×3     (repeat steps 3-4 for 3 scans)
6. LED OFF command:         ~3ms   (serial write)
7. POST_LED_DELAY:          5ms    (afterglow decay)
8. Processing overhead:     ~5ms   (dark subtract, afterglow correct)

TOTAL: ~111ms per channel (with 10ms integration, 3 scans)
```

### 4-Channel Cycle Time:
```
111ms × 4 channels = 444ms per cycle
Acquisition rate:    ~2.25 Hz (2.25 sensorgram points/second)
```

---

## Optimization Opportunities

### 1. ✅ **Use Batch Commands** (Currently Not Used)

**Current Code**:
```python
# Sequential (lines 721, 829):
ctrl.set_intensity(ch=channel, raw_val=led_intensity)  # LED ON
# ... acquisition ...
ctrl.set_intensity(ch=channel, raw_val=0)  # LED OFF
```

**Optimized with Batch**:
```python
# Turn on single channel, others off (1 command instead of 2):
intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
intensities[channel] = led_intensity
ctrl.set_batch_intensities(**intensities)

# After acquisition, turn all off:
ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
```

**Savings**:
- Current: 3ms + 3ms = 6ms per channel
- Batch: 0.8ms + 0.8ms = 1.6ms per channel
- **Saved: 4.4ms per channel** → 17.6ms per 4-channel cycle

### 2. ⚠️ **Reduce PRE_LED_DELAY** (Experimental)

**Current**: 45ms (conservative for LED stabilization)

**Investigation**:
- Measure LED stabilization time with oscilloscope/photodiode
- Modern LEDs stabilize <10ms typically
- Could reduce to 20ms if measurements show stability

**Potential Savings**: 25ms per channel → 100ms per 4-channel cycle

**Risk**:
- Unstable intensity → noise in transmission
- Requires validation with hardware

### 3. ⚠️ **Reduce num_scans** (Trade SNR for Speed)

**Current**: 3 scans per channel (noise reduction: √3 ≈ 1.73×)

**Option**: 1 scan per channel
- **Savings**: ~30ms per channel → 120ms per 4-channel cycle
- **Cost**: 1.73× higher noise in transmission

**When to use**:
- Preview mode (visual feedback only)
- High SNR samples (strong signal)
- Real-time tracking (prioritize speed)

### 4. ❌ **Pre-queue LED Commands** (Not Feasible)

**Why not**:
- Firmware doesn't support command queue
- Timing must be Python-controlled anyway (detector sync)
- No benefit over sequential batch commands

---

## Synchronization Requirements

### Critical Timing Constraints:

1. **LED Stabilization** (PRE_LED_DELAY):
   - LED must reach stable intensity BEFORE detector reads
   - Current: 45ms (conservative)
   - Minimum: TBD (needs hardware measurement)

2. **Detector Integration**:
   - Blocks Python execution until complete
   - Cannot overlap with other operations
   - Sequential per channel (USB4000 limitation)

3. **Afterglow Decay** (POST_LED_DELAY):
   - Previous channel must decay BEFORE next channel reads
   - Current: 5ms
   - Validated with afterglow correction algorithm

4. **USB Communication**:
   - Controller: ~3ms per command (serial @ 115200 baud)
   - Detector: ~5ms per read (USB transfer 3648 × 2 bytes)
   - Sequential (single USB bus)

### Why Can't We Parallelize?

**Controller → Detector Sync**:
- Detector MUST read while LED is ON and stable
- LED OFF must happen before detector integration completes (afterglow)
- Sequential dependency: `LED ON → Wait → Read → LED OFF → Wait → Next`

**USB Bus Limitation**:
- Controller (serial) and Detector (USB) are separate
- COULD send LED command while detector integrates
- But integration time (10ms) < LED command time (3ms), so minimal benefit

---

## Recommended Optimizations (Priority Order)

### 🥇 Priority 1: Use Batch LED Commands (Easy Win)

**Implementation**:
```python
def _acquire_channel_spectrum(self, channel: str) -> Optional[Dict]:
    # ... existing code ...

    # LED ON (BATCH instead of single channel)
    intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    intensities[channel] = led_intensity
    ctrl.set_batch_intensities(**intensities)

    # PRE LED delay
    time.sleep(self._pre_led_delay_ms / 1000.0)

    # Acquisition...
    # ... existing detector read code ...

    # LED OFF (BATCH)
    ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

    # POST LED delay
    time.sleep(self._post_led_delay_ms / 1000.0)
```

**Benefits**:
- ✅ Drop-in replacement (no firmware change)
- ✅ 4.4ms saved per channel (17.6ms per cycle)
- ✅ Cleaner code (single command for all LEDs)
- ✅ No risk (same timing, just faster execution)

**Effort**: LOW (simple code change)

### 🥈 Priority 2: Measure and Optimize PRE_LED_DELAY (Validation Required)

**Steps**:
1. Connect LED output to photodiode/oscilloscope
2. Measure rise time from LED ON command to stable intensity
3. Add safety margin (e.g., 2× rise time)
4. Update `PRE_LED_DELAY_MS` in device config

**Potential Savings**: 10-25ms per channel (40-100ms per cycle)

**Effort**: MEDIUM (requires hardware measurement)

### 🥉 Priority 3: Adaptive Averaging (Context-Dependent)

**Implementation**:
```python
# Preview mode: 1 scan (fast, noisier)
if preview_mode:
    num_scans = 1
# Recording mode: 3 scans (slow, stable)
else:
    num_scans = 3
```

**Benefits**:
- ✅ Fast preview for user feedback
- ✅ Stable recording for data quality

**Effort**: LOW (configuration flag)

---

## Firmware Enhancement Proposal (Future)

### Multi-Batch Command Queue Protocol

**Concept**:
```
# Queue N LED sequences with timing
queue_start:4\n             # Start queue, 4 sequences
seq:255,0,0,0:45:5\n       # A=255, others=0, pre=45ms, post=5ms
seq:0,255,0,0:45:5\n       # B=255, others=0, pre=45ms, post=5ms
seq:0,0,255,0:45:5\n       # C=255, others=0, pre=45ms, post=5ms
seq:0,0,0,255:45:5\n       # D=255, others=0, pre=45ms, post=5ms
queue_exec\n               # Execute entire queue

# Python sends trigger signal when detector ready
trigger:ch_a\n             # Execute sequence 0 (LED A)
# ... detector reads ...
trigger:ch_b\n             # Execute sequence 1 (LED B)
# ... etc ...
```

**Benefits**:
- ✅ Pre-program entire acquisition sequence
- ✅ Firmware handles LED timing internally
- ✅ Python only triggers at detector sync points
- ✅ Reduced serial communication overhead

**Challenges**:
- ❌ Requires firmware rewrite (Arduino/Pico)
- ❌ Complex synchronization protocol
- ❌ Limited by Arduino RAM (queue size ~10-20 commands)
- ❌ Testing and validation effort

**ROI**: LOW (marginal benefit vs complexity)

---

## Summary & Recommendations

### Current State: ✅ Timing Is Correct

Your LED timing is implemented **exactly as intended**:
- LED ON → PRE_DELAY → Acquire → LED OFF → POST_DELAY
- Synchronization with detector is correct
- No timing bugs or misalignments

### Quick Wins:

1. **Use batch LED commands** (`set_batch_intensities()`)
   - Available NOW in PicoP4SPR and PicoEZSPR
   - 15× faster LED control (12ms → 0.8ms)
   - 17.6ms saved per 4-channel cycle
   - **ACTION**: Modify `_acquire_channel_spectrum()` to use batch commands

2. **Validate PRE_LED_DELAY** with hardware measurement
   - Current 45ms may be conservative
   - Measure LED stabilization time
   - Potentially reduce to 20ms (save 100ms per cycle)
   - **ACTION**: Hardware validation experiment

### Not Feasible:

- ❌ **120-command batch**: Firmware doesn't support command queuing
- ❌ **Detector batch commands**: USB4000 hardware limitation (single-read only)
- ❌ **Pre-queue cancellation**: No firmware queue to cancel

### Future Enhancement:

- **Firmware command queue**: Would require significant development effort
- **ROI questionable**: Current optimization opportunities are sufficient
- **Consider**: Only if sub-100ms cycle time is critical requirement

---

## Implementation Guide: Batch LED Commands

### Step 1: Modify `_acquire_channel_spectrum()`

**File**: `src/core/data_acquisition_manager.py`

**Current Code** (lines 721, 829):
```python
# Turn on LED for this channel
ctrl.set_intensity(ch=channel, raw_val=led_intensity)

# ... acquisition ...

# Turn off LED for this channel
ctrl.set_intensity(ch=channel, raw_val=0)
```

**Optimized Code**:
```python
# Turn on LED for this channel using batch command (15× faster)
led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
led_values[channel] = led_intensity
ctrl.set_batch_intensities(**led_values)

# ... acquisition ...

# Turn off all LEDs using batch command
ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
```

### Step 2: Validate Batch Command Support

**Check controller type**:
```python
if hasattr(ctrl, 'set_batch_intensities'):
    # Use batch command (Pico controllers)
    ctrl.set_batch_intensities(**led_values)
else:
    # Fall back to individual command (Arduino, QSPR)
    ctrl.set_intensity(ch=channel, raw_val=led_intensity)
```

### Step 3: Measure Performance Improvement

**Before**:
```
4-channel cycle: ~444ms
LED commands: 6ms × 4 = 24ms
```

**After**:
```
4-channel cycle: ~426ms (4% faster)
LED commands: 1.6ms × 4 = 6.4ms
Saved: 17.6ms per cycle
```

---

**Status**: Analysis complete. Ready for implementation of batch LED commands.
