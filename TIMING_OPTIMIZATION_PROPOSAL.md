# Timing Optimization Proposal - Target 1Hz (1000ms/cycle)

## Current Timing (Sequential, No Overlap)

**Per Channel:**
- PRE_LED: 45ms (LED stabilization)
- Integration: 70ms (optimal for 0.000nm peak precision)
- POST_LED: 100ms (3× tau = 95% afterglow decay)
- **Total: 215ms/channel**

**Full Cycle (4 channels):**
- 215ms × 4 = **860ms/cycle** ✅ Already under 1Hz!

---

## Proposed Optimization: LED Overlap Strategy

### Key Insight
**Afterglow decay happens in darkness** - it doesn't matter if another LED turns on during POST delay, as long as we don't start acquiring data until afterglow has decayed.

### Overlap Timing
```
Channel A: ├─PRE(40ms)─┼─ACQ(70ms)─┼─────POST(90ms)─────┤
Channel B:                          ├─PRE(40ms)─┼─ACQ(70ms)─┼─────POST(90ms)─────┤
                                    ↑ 50ms overlap
                                    (LED B turns ON while A in POST)
```

**Timing Breakdown:**
1. **Channel A (first):**
   - Turn ON LED A
   - Wait 40ms PRE (LED stabilization)
   - Acquire 70ms
   - Turn OFF LED A
   - Start 90ms POST delay
   - **After 50ms of POST:** Turn ON LED B (overlapping with A's POST)

2. **Channel B (and subsequent):**
   - LED B already ON for 50ms (during A's POST)
   - Wait remaining 40ms PRE (total 90ms since A finished = full POST delay)
   - Acquire 70ms
   - Turn OFF LED B
   - Start 90ms POST delay
   - **After 50ms of POST:** Turn ON LED C

**Net Time Per Channel (after first):**
- Acquisition: 70ms
- POST (minus overlap): 90ms - 50ms = 40ms
- **Total: 110ms/channel effective**

**Full Cycle:**
- First channel: 40ms (PRE) + 70ms (ACQ) + 40ms (POST effective) = 150ms
- Channels 2-4: 70ms (ACQ) + 40ms (POST effective) × 3 = 330ms
- **Total: 480ms/cycle** ✅ **52% faster! 520ms margin to 1Hz**

---

## Alternative: Reduce Integration Time

### Option A: 50ms Integration Time
**Trade-off Analysis:**
- Time saved: 20ms/channel × 4 = 80ms/cycle
- Peak precision impact: Need to test (70ms = 0.000nm, 50ms = ?)
- SNR impact: √(50/70) = 0.85× SNR (15% reduction)

**With overlap strategy:**
- 50ms ACQ + 40ms POST effective = 90ms/channel
- First channel: 40ms PRE + 50ms ACQ + 40ms = 130ms
- Channels 2-4: 90ms × 3 = 270ms
- **Total: 400ms/cycle** ✅ **600ms margin**

### Option B: Keep 70ms (Recommended)
- **Already hitting 480ms/cycle with overlap**
- Maintain 0.000nm peak precision (validated)
- 520ms margin sufficient for jitter/overhead
- Simpler implementation (no re-validation needed)

---

## Timing Parameter Update

### Current Settings (settings.py)
```python
PRE_LED_DELAY_MS = 45   # LED stabilization
POST_LED_DELAY_MS = 100 # 3× tau afterglow decay
```

### Proposed Settings
```python
PRE_LED_DELAY_MS = 40   # LED stabilization (LED stable in 10ms, 40ms = 4× safety)
POST_LED_DELAY_MS = 90  # Afterglow decay (2.5× tau = 92% decay)
LED_OVERLAP_MS = 50     # Turn on next LED after 50ms of POST delay
```

**Why 40ms PRE is safe:**
- LED test showed 10ms settling time
- 40ms = 4× safety factor
- 5ms reduction negligible vs validation overhead

**Why 90ms POST is acceptable:**
- Afterglow tau = 35ms average
- 90ms = 2.57× tau = 92% decay (vs 95% at 100ms)
- 8% residual afterglow = ~120 counts (vs 1450 baseline)
- Impact: 0.012% on 100k count signal (negligible)

---

## Implementation Strategy

### Phase 1: Update Timing Constants (LOW RISK)
**File:** `src/settings/settings.py`
```python
PRE_LED_DELAY_MS = 40   # Reduced from 45ms (5ms savings/channel)
POST_LED_DELAY_MS = 90  # Reduced from 100ms (10ms savings/channel)
LED_OVERLAP_MS = 50     # NEW: Overlap strategy parameter
```

**Expected improvement:**
- 15ms savings/channel × 4 = 60ms/cycle
- New cycle time: 860ms → 800ms (no overlap yet)

**Validation:**
- Run full calibration
- Verify peak precision still <0.1nm
- Check transmission QC passes

### Phase 2: Implement LED Overlap (MEDIUM RISK)
**File:** `src/core/data_acquisition_manager.py`

**Current flow (sequential):**
```python
def acquire_channel(channel):
    turn_on_led(channel)
    sleep(PRE_LED_DELAY_MS)
    spectrum = acquire()
    turn_off_led(channel)
    sleep(POST_LED_DELAY_MS)
    return spectrum
```

**New flow (overlapped):**
```python
def acquire_channel(channel, next_channel=None):
    # PRE delay (already running from previous overlap or explicit)
    if not led_already_on:
        turn_on_led(channel)
        sleep(PRE_LED_DELAY_MS)

    # Acquire
    spectrum = acquire()

    # POST delay with optional overlap
    turn_off_led(channel)
    if next_channel:
        sleep(LED_OVERLAP_MS)  # 50ms
        turn_on_led(next_channel)  # Next LED ON during POST
        sleep(POST_LED_DELAY_MS - LED_OVERLAP_MS)  # Remaining 40ms
    else:
        sleep(POST_LED_DELAY_MS)  # Full 90ms for last channel

    return spectrum
```

**Expected improvement:**
- 50ms overlap × 3 transitions = 150ms savings
- Total cycle time: 800ms → 650ms (Phase 1) → 480ms (Phase 2)

**Validation:**
- Check afterglow contamination between channels
- Verify peak wavelength stability
- Monitor channel-to-channel correlation

### Phase 3: Optional Integration Time Reduction (HIGH RISK)
**Only if Phase 1+2 insufficient**

Reduce from 70ms → 50ms:
- Additional 80ms savings (400ms total cycle time)
- **Requires re-validation:**
  - Peak precision testing
  - SNR measurement
  - Stability study

---

## Risk Assessment

| Change | Risk | Validation Effort | Time Savings |
|--------|------|-------------------|--------------|
| PRE 45→40ms | LOW | 1 hour | 20ms/cycle |
| POST 100→90ms | LOW | 1 hour | 40ms/cycle |
| LED overlap | MEDIUM | 4 hours | 150ms/cycle |
| Integration 70→50ms | HIGH | 8 hours | 80ms/cycle |

---

## Recommendation

### Immediate Action (LOW RISK, HIGH REWARD)
1. **Update timing constants:**
   - PRE_LED_DELAY_MS: 45 → 40ms
   - POST_LED_DELAY_MS: 100 → 90ms
   - **Total savings: 60ms/cycle**
   - **New cycle time: 800ms** ✅ Still under 1Hz

2. **Validate:**
   - Run calibration
   - Check peak precision
   - Verify QC passes

### Future Optimization (MEDIUM RISK, HIGH REWARD)
3. **Implement LED overlap strategy:**
   - Add LED_OVERLAP_MS = 50ms
   - Modify acquisition loop
   - **Additional savings: 150ms/cycle**
   - **Target cycle time: 650ms**

### If Still Needed (HIGH RISK, MODERATE REWARD)
4. **Reduce integration time:**
   - Test 50ms integration
   - Validate peak precision
   - **Additional savings: 80ms/cycle**
   - **Final cycle time: 570ms** (430ms margin)

---

## Current Status: Already Under 1Hz! ✅

**With current settings (45ms PRE, 100ms POST, 70ms integration):**
- Cycle time: 860ms
- **Already 140ms under your 1Hz target!**

**Question:** Do you need to hit 1Hz for:
- Real-time display (faster updates)?
- Higher data throughput (more experiments/hour)?
- Future expansion (more channels)?

**If not urgent:** Keep current conservative timing (validated, stable)
**If optimization desired:** Start with Phase 1 (low risk, quick wins)
