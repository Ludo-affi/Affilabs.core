# Fresh Calibration Data Guarantee

**Date:** October 11, 2025
**Issue:** Ensure new S-mode and P-mode reference values are used after dark noise fix
**Status:** ✅ **IMPLEMENTED**

---

## 🎯 Problem

After fixing the dark noise LED issue, we need to ensure that:
1. **New dark noise** (with LEDs properly OFF) is measured fresh
2. **New S-mode references** are captured using the correct dark noise
3. **No legacy data** from previous (buggy) calibration is used
4. **Data acquisition** uses the fresh calibration values

---

## ✅ Solution Implemented

### 1. **State Reset at Calibration Start**

**File:** `utils/spr_calibrator.py`
**Method:** `run_full_calibration()`
**Lines:** ~2080-2090

Added explicit state reset before calibration begins:

```python
# 🔄 RESET CALIBRATION STATE - Ensure fresh start with no legacy data
if not use_previous_data:
    logger.info("🔄 Resetting calibration state for fresh measurement...")
    # Clear all previous calibration data to ensure new S-ref and dark use new values
    self.state.dark_noise = np.array([])
    self.state.full_spectrum_dark_noise = np.array([])
    self.state.ref_sig = dict.fromkeys(CH_LIST)
    self.state.leds_calibrated = dict.fromkeys(CH_LIST, 0)
    self.state.ref_intensity = dict.fromkeys(CH_LIST, 0)
    self.state.is_calibrated = False
    logger.info("✅ State reset complete - all legacy data cleared")
```

**What this does:**
- Clears all dark noise arrays
- Clears all S-mode reference signals
- Resets LED calibration values
- Sets `is_calibrated = False`

### 2. **Shared State Architecture**

**How it works:**
```
SPRStateMachine
    ↓
    Creates: CalibrationState() [SHARED]
    ↓
    ├─→ SPRCalibrator(calib_state=shared_state)
    │       ↓
    │       Writes fresh data:
    │       - dark_noise (LEDs OFF ✅)
    │       - ref_sig[ch] (using correct dark)
    │       - leds_calibrated[ch]
    │
    └─→ DataAcquisitionWrapper(calib_state=shared_state)
            ↓
            Reads same data:
            - self.dark_noise = calib_state.dark_noise
            - self.ref_sig = calib_state.ref_sig
            - Uses fresh values automatically ✅
```

**Key Point:** Both calibrator and acquisition share the **same object in memory** - no copying, no stale data!

### 3. **Legacy Loading Disabled by Default**

**File:** `utils/spr_calibrator.py`
**Line:** ~2071

```python
def run_full_calibration(
    self,
    auto_polarize: bool = False,
    auto_polarize_callback: Callable[[], None] | None = None,
    use_previous_data: bool = False,  # ✅ DISABLED by default
    auto_save: bool = True,
) -> tuple[bool, str]:
```

**Why this matters:**
- `use_previous_data=False` means calibration **always starts fresh**
- No old dark noise or S-ref values are loaded
- State reset (above) ensures any accidentally cached data is cleared

---

## 🔍 Verification

### Expected Calibration Flow (After Fix)

**Step 0: State Reset**
```
🔄 Resetting calibration state for fresh measurement...
✅ State reset complete - all legacy data cleared
```

**Step 5: Dark Noise Measurement (NEW)**
```
🔦 Forcing ALL LEDs OFF for dark noise measurement...
   ✓ Sent 'lx' command to turn off all LEDs
✅ All LEDs OFF; waited 500ms for hardware to settle
✅ Dark noise measurement complete:
  • Mean dark noise: 120.0 counts  ← LOW (correct!)
  • 💾 Saved to: calibration_data/dark_noise_20251011_HHMMSS.npy
```

**Step 6: S-mode Reference Measurement (NEW)**
```
📊 Reference signal averaging: 30 scans
Channel a reference signal: max=48000.0 counts
💾 S-ref[a] saved: calibration_data/s_ref_a_20251011_HHMMSS.npy
```

**S-ref Calculation (uses NEW dark):**
```python
# In measure_reference_signals():
ref_data_single = filtered_val - self.state.dark_noise  # ✅ Uses FRESH dark (LEDs OFF)
```

**Data Acquisition Sync:**
```
✅ Synced wavelengths: 1591 points
✅ Synced dark noise: 1591 points       ← NEW dark (LEDs OFF)
✅ Synced ref_sig[a]: 1591 points       ← NEW S-ref (correct dark subtracted)
✅ Synced ref_sig[b]: 1591 points
✅ Synced ref_sig[c]: 1591 points
✅ Synced ref_sig[d]: 1591 points
```

### Expected Transmittance Values (After Fix)

**Before fix (buggy dark):**
```
Dark noise: 10,000 counts  ← Inflated (LEDs were ON)
S-ref = Raw_S - 10,000     ← Too low (over-subtracted)
P-corrected = Raw_P - 120  ← Correct (after fix)
Transmittance = P / S = HIGH (dividing by small S-ref)
```

**After fix:**
```
Dark noise: 120 counts     ← Correct (LEDs properly OFF)
S-ref = Raw_S - 120        ← Correct
P-corrected = Raw_P - 120  ← Correct
Transmittance = P / S = CORRECT ✅
```

---

## 🧪 Testing Checklist

### After Running New Calibration:

- [ ] **Check logs for state reset:**
  ```
  🔄 Resetting calibration state for fresh measurement...
  ✅ State reset complete - all legacy data cleared
  ```

- [ ] **Verify LEDs OFF during dark:**
  - Visual: No LED light visible during Step 5
  - Log: "✓ Sent 'lx' command to turn off all LEDs"

- [ ] **Check dark noise values:**
  ```powershell
  .\.venv\Scripts\python.exe -c "import numpy as np; a=np.load('calibration_data/dark_noise_latest.npy'); print(f'Dark: mean={a.mean():.1f} max={a.max():.1f}')"
  ```
  - Expected: mean ~80-150 counts, NOT 10,000+

- [ ] **Check S-ref values:**
  ```powershell
  .\.venv\Scripts\python.exe -c "import numpy as np; a=np.load('calibration_data/s_ref_a_latest.npy'); print(f'S-ref[a]: mean={a.mean():.1f} max={a.max():.1f}')"
  ```
  - Expected: mean ~45,000-50,000 counts (high signal)

- [ ] **Check transmittance values:**
  - Open diagnostic viewer
  - Transmittance should be 0-100% range
  - Should NOT show >100% or negative values

- [ ] **Verify data acquisition sync:**
  ```
  ✅ Synced dark noise: 1591 points
  ✅ Synced ref_sig[a]: 1591 points
  ```
  - All channels should sync successfully

---

## 📊 Data Flow Guarantee

### Calibration Phase:
1. ✅ State reset clears all arrays
2. ✅ Dark measured with LEDs OFF → `state.dark_noise`
3. ✅ S-ref measured using correct dark → `state.ref_sig[ch]`
4. ✅ LED intensities stored → `state.leds_calibrated[ch]`

### Acquisition Phase:
1. ✅ Wrapper syncs: `self.dark_noise = calib_state.dark_noise`
2. ✅ Wrapper syncs: `self.ref_sig = calib_state.ref_sig`
3. ✅ Acquisition uses synced data for P/S calculation
4. ✅ Transmittance = (P - dark) / (S - dark) with correct values

**No legacy data possible!**

---

## 🔧 Manual Override (Not Recommended)

If you need to force loading of previous calibration (not recommended):

```python
# In your calibration call:
calibrator.run_full_calibration(use_previous_data=True)
```

**Warning:** This will:
- Skip state reset
- Load old dark noise (with LEDs ON bug)
- Load old S-ref (using buggy dark)
- Result in incorrect transmittance values

**Always use default `use_previous_data=False` for accurate measurements!**

---

## 🎯 Summary

✅ **State reset** clears all legacy data before calibration
✅ **Fresh dark noise** measured with LEDs properly OFF
✅ **Fresh S-mode references** calculated using correct dark
✅ **Shared state** ensures acquisition uses new values
✅ **No legacy loading** by default (use_previous_data=False)

**Result:** After recalibration, all data processing uses fresh, correct values with no possibility of legacy contamination.

---

## 🚀 Next Steps

1. **Run new calibration** - State will reset automatically
2. **Verify dark noise** is low (~120 counts)
3. **Check transmittance** looks reasonable (0-100%)
4. **Monitor diagnostic viewer** to confirm correct signal flow

---

*Implementation complete: October 11, 2025*
*Ready for testing with fresh calibration*
