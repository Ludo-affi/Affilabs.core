# Transmission LED Boost Correction - Critical Bug Fix

**Date:** November 25, 2025
**Issue:** Transmission calculation was not accounting for different LED intensities in P-mode vs S-mode
**Impact:** Transmission values artificially inflated by LED boost factor (2-3x typical)
**Status:** ✅ FIXED

---

## The Problem

### Original (WRONG) Implementation:
```python
# spr_signal_processing.py (OLD)
def calculate_transmission(intensity, reference):
    transmission = (intensity / reference) * 100
    return transmission
```

### Why This Was Wrong:

During calibration:
- **S-mode (reference)**: LED intensity = 80 → measures ~52,000 counts
- **P-mode (live data)**: LED intensity = 220 (boosted 2.75x) → measures variable counts

**Example calculation (WRONG):**
```
P-mode counts: 45,000 (with LED=220)
S-mode counts: 40,000 (with LED=80)
Transmission = 45,000 / 40,000 × 100 = 112.5%  ❌ TOO HIGH!
```

The problem: **LED brightness boost artificially inflates the P/S ratio!**

---

## The Physics

### What We're Actually Measuring:

**S-mode reference (calibration):**
```
S_counts = LED_S × Detector_response × S_pol_transmission
         = 80 × Detector × S_trans
```

**P-mode live data:**
```
P_counts = LED_P × Detector_response × P_pol_transmission
         = 220 × Detector × P_trans
```

### The Correct Formula:

To get **optical transmission** (independent of LED brightness):
```
Transmission = (P_counts / LED_P) / (S_counts / LED_S) × 100
             = (P_counts × LED_S) / (S_counts × LED_P) × 100
```

This formula:
1. Normalizes P-mode by its LED brightness (P_counts / LED_P)
2. Normalizes S-mode by its LED brightness (S_counts / LED_S)
3. Takes the ratio → **pure optical transmission**
4. Multiplies by 100 for percentage

---

## The Fix

### Updated Implementation:

**File:** `utils/spr_signal_processing.py`
```python
def calculate_transmission(
    intensity: np.ndarray,
    reference: np.ndarray,
    p_led_intensity: float = None,  # NEW parameter
    s_led_intensity: float = None   # NEW parameter
) -> np.ndarray:
    """Calculate transmission with LED intensity correction."""

    # Calculate raw ratio
    transmission = (intensity / reference) * 100

    # Apply LED correction if provided
    if p_led_intensity is not None and s_led_intensity is not None:
        led_correction_factor = s_led_intensity / p_led_intensity
        transmission = transmission * led_correction_factor

    return transmission
```

**File:** `core/data_acquisition_manager.py`
```python
# Get LED intensities for this channel
p_led = self.leds_calibrated.get(channel)  # P-mode LED (e.g., 220)
s_led = self.ref_intensity.get(channel)    # S-mode LED (e.g., 80)

# Calculate transmission with LED correction
transmission_spectrum = calculate_transmission(
    raw_spectrum, ref_spectrum,
    p_led_intensity=p_led,
    s_led_intensity=s_led  # ← Pass LED values
)
```

---

## Example Calculation (CORRECTED)

### Scenario:
- Channel A: S-mode LED = 80, P-mode LED = 220
- S-mode reference: 40,000 counts
- P-mode live: 45,000 counts

### Calculation:
```python
# Step 1: Raw ratio
raw_transmission = (45000 / 40000) × 100 = 112.5%

# Step 2: LED correction factor
led_correction = 80 / 220 = 0.364

# Step 3: Corrected transmission
corrected_transmission = 112.5% × 0.364 = 40.9%  ✅ CORRECT!
```

### Physical Interpretation:
- **40.9%** means P-polarized light has 40.9% of the intensity of S-polarized light
- This is **pure optical transmission** through the SPR sensor
- Typical range: 10-70% (10% = deep SPR dip, 70% = no resonance)

---

## Impact on Data

### Before Fix (Per-Channel LED Boost):
| Channel | S-LED | P-LED | Boost Factor | Error |
|---------|-------|-------|--------------|-------|
| A       | 80    | 220   | 2.75×        | +175% |
| B       | 95    | 235   | 2.47×        | +147% |
| C       | 110   | 250   | 2.27×        | +127% |
| D       | 125   | 255   | 2.04×        | +104% |

**All transmission values were 2-3× too high!**

### After Fix:
✅ Transmission values now represent **true optical transmission**
✅ Typical SPR dip: 20-40% (was incorrectly showing 50-110%)
✅ Baseline transmission: 50-70% (was incorrectly showing 120-200%)
✅ Peak finding still works (uses relative minimum, unaffected by scaling)

---

## Backward Compatibility

The fix is **backward compatible**:
- If `p_led_intensity` and `s_led_intensity` are not provided → behaves like old code
- If provided → applies correction
- All new calibrations automatically use corrected formula
- Old code calling `calculate_transmission(intensity, reference)` still works

---

## Testing Verification

### Expected Changes After Fix:
1. **Transmission graphs**: Values will drop by ~50-65% (LED correction factor)
2. **Peak wavelength**: UNCHANGED (relative minimum position same)
3. **Sensorgram trends**: UNCHANGED (shape preserved, only Y-axis scaled)
4. **SPR dip visibility**: IMPROVED (more realistic percentage range)

### Debug Logging:
The system now logs LED correction factors:
```
[PROCESS] Ch a: LED correction S=80, P=220, factor=0.364
[PROCESS] Ch b: LED correction S=95, P=235, factor=0.404
```

This appears every 50th acquisition (throttled to avoid log spam).

---

## Why This Wasn't Caught Earlier

1. **Peak finding works regardless**: Fourier analysis finds *relative* minimum, so absolute scale doesn't matter
2. **Visual appearance similar**: Transmission curves had correct *shape*, just wrong *scale*
3. **No absolute reference**: Without known SPR transmission standards, high values weren't obviously wrong
4. **Worked for relative tracking**: Sensorgram (change over time) was unaffected by constant scaling

**The bug was silent but systematic** - affecting all channels equally.

---

## Related Files Modified

1. ✅ `utils/spr_signal_processing.py` - Updated `calculate_transmission()` function
2. ✅ `core/data_acquisition_manager.py` - Pass LED intensities to transmission calculation
3. ✅ `LIVE_DATA_FLOW_WALKTHROUGH.md` - Updated Step 3 documentation

---

## Commit Message

```
Fix: Add LED intensity correction to transmission calculation

CRITICAL BUG FIX: Transmission values were artificially inflated by
LED boost factor (2-3x) because P-mode and S-mode use different LED
intensities.

Physics:
- S-ref measured at LED=80 (calibration)
- P-pol measured at LED=220 (live data, boosted 2.75x)
- Raw P/S ratio includes LED boost → must normalize

Solution:
- Add p_led_intensity and s_led_intensity parameters
- Apply correction: transmission × (S_LED / P_LED)
- Result: True optical transmission percentage (10-70% typical)

Impact:
- All transmission values drop by 50-65% (now physically correct)
- Peak wavelength unchanged (relative minimum preserved)
- Sensorgram trends unchanged (scale factor cancels in derivatives)

Files modified:
- utils/spr_signal_processing.py: calculate_transmission()
- core/data_acquisition_manager.py: _process_spectrum()
- LIVE_DATA_FLOW_WALKTHROUGH.md: Updated documentation
```

---

## Future Considerations

### Alternative Approaches (NOT IMPLEMENTED):
1. **Normalize S-ref during calibration**: Scale S-ref by (P_LED/S_LED) once
   - Pro: Simpler runtime calculation
   - Con: Loses information about actual calibration conditions

2. **Measure S-ref at same LED as P-mode**: Use LED=220 for both
   - Pro: No correction needed
   - Con: S-ref might saturate, wastes LED headroom

### Current Approach (IMPLEMENTED):
3. **Runtime LED correction**: Calculate correction factor per acquisition
   - Pro: Preserves calibration fidelity, clear what's happening
   - Con: Slightly more computation (negligible ~0.1ms)
   - **✅ CHOSEN**: Most transparent and maintainable

---

## Summary

**Before:** Transmission = (P_counts / S_counts) × 100 → **WRONG**
**After:** Transmission = (P_counts × S_LED) / (S_counts × P_LED) × 100 → **CORRECT** ✅

The fix ensures transmission values represent **true optical transmission** through the SPR sensor, independent of LED intensity settings. Peak finding and sensorgram tracking are unaffected, but absolute transmission values are now physically accurate.
