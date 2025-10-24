# Calibration Target Strategy - Design Note

**Date**: October 22, 2025
**Status**: ✅ CURRENT IMPLEMENTATION CORRECT - Documentation for clarity

---

## Question from User

> "In the initial calibration step 5, is the 50% detector saturation a hard stop value or a minimum threshold? Because, the weakest LED should always be at 255 to find the lowest integration time and maximum counts possible for that optical set."

---

## Current Implementation Analysis

### ✅ Current Strategy is CORRECT

**File**: `utils/spr_calibrator.py` - Step 3 (Integration Time Calibration)

**What it does NOW**:

1. **Identifies weakest channel** (Step 3.1)
   - Tests all channels at standard LED=168
   - Finds channel with lowest signal
   - **Stores as `self.state.weakest_channel`**

2. **Sets weakest channel to LED=255** (Step 3.2, line 2738)
   ```python
   # CRITICAL: Set weakest channel to MAXIMUM LED intensity
   intensities_dict = {weakest_ch: MAX_LED_INTENSITY}  # 255
   self._activate_channel_batch([weakest_ch], intensities_dict)
   ```

3. **Optimizes integration time** (Step 3.2)
   - Adjusts integration time UP or DOWN
   - Target: 76% detector saturation (~50,000 counts out of 65,535)
   - Weakest channel stays at LED=255 throughout
   - Integration time finds **minimum time needed** for weakest channel @ 255 to hit target

4. **Locks integration time** (Step 3.3)
   - Integration time is now FIXED for all channels
   - Weakest channel locked at LED=255

5. **Adjusts other channels' LEDs DOWN** (Step 4 - LED Calibration)
   - Brighter channels get reduced LED (e.g., 180, 140, 200)
   - All channels now match weakest channel's signal level
   - Weakest channel remains at 255

---

## Target Value: 76% vs 50%

**Current Setting**: `TARGET_INTENSITY_PERCENT = 76`
**Location**: `settings/settings.py` line 143

### Why 76% and not 50%?

**76% is BETTER** for your use case:

| Metric | 50% Target | 76% Target (Current) |
|--------|-----------|---------------------|
| Signal Level | ~32,768 counts | ~50,000 counts |
| SNR | Lower | **Higher (1.5× better)** |
| Dynamic Range | More headroom | Sufficient headroom |
| Saturation Risk | Very low | Low (24% buffer) |
| Integration Time | **Shorter** | Longer |
| Temporal Resolution | **Faster** | Adequate |

**Recommendation**: **KEEP 76%**
- Gives better SNR for SPR detection
- 24% headroom is sufficient (saturation at >85% in live mode)
- Weakest channel still at LED=255 (correct!)
- Only reduces integration time if optical coupling improves

---

## Is 76% a "Hard Stop" or "Minimum Threshold"?

**Answer**: It's a **TARGET with tolerance**, not a hard constraint.

### Implementation Details:

```python
# Line 2754: Calculate target
S_COUNT_TARGET = int(TARGET_INTENSITY_PERCENT / 100 * detector_max)
# For 65535 max: 0.76 × 65535 = 49,807 counts

# Line 2817: Acceptance window
if S_COUNT_TARGET * 0.95 <= current_count <= S_COUNT_TARGET * 1.05:
    # Within ±5% of target → ACCEPT
```

**Tolerance**: 95%-105% of target (±5%)
- **Lower bound**: 72.2% of detector max (~47,317 counts)
- **Upper bound**: 79.8% of detector max (~52,297 counts)

### What if Weakest Channel Can't Reach Target?

**Line 2834-2840**: Graceful handling
```python
if current_count < S_COUNT_TARGET:
    logger.warning(
        f"⚠️ Weakest channel could not reach target even at LED=255
           and {integration_time:.1f}ms"
    )
    logger.warning(f"   Achieved: {current_count:.0f} counts")
    # CONTINUES anyway - uses best achievable signal
```

**Behavior**:
- If weakest channel @ LED=255 can't reach 76% even at MAX integration time (200ms)
- Calibration **accepts whatever signal was achieved**
- Warning logged for operator awareness
- System proceeds with best available performance

---

## Optimization Strategy: Correct by Design

### Current Logic (✅ Optimal):

```
1. Weakest channel → LED=255 (LOCKED)
2. Find minimum integration time for 76% target
3. Lock integration time
4. Adjust other channels' LEDs DOWN to match
```

### Why This is Correct:

✅ **Weakest channel gets maximum photons** (LED=255)
✅ **Integration time minimized** (only as long as needed for weakest)
✅ **Brighter channels dimmed** (prevents saturation)
✅ **All channels balanced** (equal signal levels)
✅ **Maximum temporal resolution** (shortest integration time possible)

### Alternative Strategy (❌ Suboptimal):

```
1. Test all channels at various LEDs
2. Optimize each channel independently
3. Use longest integration time needed
```

**Problems**:
- ❌ Slower (requires more time)
- ❌ May use unnecessarily long integration
- ❌ Doesn't guarantee balance between channels

---

## Recommended Actions

### No Code Changes Needed

The current implementation **already follows best practices**:

1. ✅ Weakest channel identified
2. ✅ Weakest channel set to LED=255
3. ✅ Integration time optimized for weakest @ 255
4. ✅ Target is 76% (good SNR, safe headroom)
5. ✅ Other channels dimmed to match
6. ✅ Graceful handling if target unreachable

### Optional Clarifications (Documentation Only):

**A. Make target behavior explicit in logs**

Current log (line 2766):
```python
logger.info(f"   Target: {S_COUNT_TARGET:.0f} counts ({TARGET_INTENSITY_PERCENT}%)")
```

Could add:
```python
logger.info(f"   Target: {S_COUNT_TARGET:.0f} counts ({TARGET_INTENSITY_PERCENT}%) "
           f"[Tolerance: ±5%, will accept {S_COUNT_TARGET*0.95:.0f}-{S_COUNT_TARGET*1.05:.0f}]")
```

**B. Add design rationale comment**

At line 2754, could add:
```python
# Target: 76% of detector max (not 50%)
# Rationale:
#   - Higher target = better SNR for SPR detection
#   - 24% headroom sufficient (live mode caps at 85%)
#   - Weakest channel @ LED=255 ensures minimum integration time
#   - Only reduces if optical coupling improves (desired behavior)
S_COUNT_TARGET = int(TARGET_INTENSITY_PERCENT / 100 * detector_max)
```

**C. Expose TARGET_INTENSITY_PERCENT in advanced settings UI**

Currently hardcoded at 76% in settings.py.
Could make user-adjustable if needed (50-85% range).

---

## Conclusion

**Current Implementation Status**: ✅ **OPTIMAL - No changes needed**

The calibration already does exactly what you described:
- Weakest channel at LED=255 (maximum photons)
- Integration time minimized for that channel
- Target is 76% (better than 50% for SNR)
- Other channels dimmed down to match

**User's Concern**: Addressed - the 76% target is NOT a constraint on the weakest channel. The weakest channel is ALWAYS at LED=255, and the integration time is optimized to get as close to 76% as possible. If the system can't reach 76% even at max LED and max integration time, it accepts whatever it achieves.

**Recommendation**: Keep current implementation, optionally add clarifying comments/logs as suggested above.

---

## Related Files

- `utils/spr_calibrator.py` - Lines 2650-2900 (Step 3: Integration time calibration)
- `settings/settings.py` - Line 143 (`TARGET_INTENSITY_PERCENT = 76`)
- `settings/settings.py` - Line 296 (`LIVE_MODE_TARGET_INTENSITY_PERCENT = 76`)

---

## Implementation Priority

**Priority**: 🟢 **LOW** - Current system optimal
**Estimated Effort**: 15 minutes (documentation/logging clarity only)
**Impact**: Clarity only - no functional improvement needed

---

## Update History

- **2025-10-22**: Initial design note created based on user question
- Current implementation analyzed and confirmed optimal
- No code changes required
