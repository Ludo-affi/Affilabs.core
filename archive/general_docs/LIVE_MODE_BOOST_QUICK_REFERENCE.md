# Live Mode Boost & Display Delay - Quick Reference

## 🎯 What Changed

### 1. Smart Boost Configuration (Conservative 20-40%)
- **Old**: Up to 2.5× boost (150% increase) - too aggressive
- **New**: Up to 1.4× boost (40% increase) - conservative, safe
- **Rationale**: P-pol has ~30-40% lower signal, so 40% boost compensates perfectly

### 2. LED Intensity Policy (Clarified)
- LED values from Step 6 are **FIXED**
- Never adjusted in live mode
- Integration time is the **only** parameter that changes

### 3. Display Delay (10 Seconds)
- First 10 seconds: Data collected but not displayed
- Allows multi-point processing to stabilize:
  - Temporal filter (5-point window)
  - Kalman filter convergence
  - Peak tracking algorithms
- Status message: "Stabilizing... Display in Xs"

### 4. Safety Constraints (Enforced)
- Saturation threshold: 92% detector (60,400 counts)
- Time budget: integration × scans ≤ 200ms per spectrum
- If boost would violate constraints, automatically capped

---

## 📋 Settings Changed

**File**: `settings/settings.py`

```python
# OLD
LIVE_MODE_MAX_BOOST_FACTOR = 2.5  # Too aggressive (150% increase)
LIVE_MODE_TARGET_INTENSITY_PERCENT = 75  # Too conservative

# NEW
LIVE_MODE_MAX_BOOST_FACTOR = 1.4  # Conservative 40% increase
LIVE_MODE_TARGET_INTENSITY_PERCENT = 90  # Maximizes signal safely
LIVE_MODE_SATURATION_THRESHOLD_PERCENT = 92  # Safety threshold
LIVE_MODE_DISPLAY_DELAY_SECONDS = 10.0  # Stabilization period
```

---

## 🧪 Expected Behavior

### Calibration (Step 6)
```
Integration time: 33.7ms
LED values: A=129, B=255, C=31, D=33
Target signal: 50% detector (~49,151 counts)
```

### Live Mode (After Boost)
```
Integration time: 47.2ms (33.7ms × 1.4)
LED values: A=129, B=255, C=31, D=33 ← SAME AS STEP 6
Expected signal: 90% detector target (~59,000 counts)
Actual signal (P-pol): ~48,000 counts (due to 30% P-pol dampening)
```

### Display Sequence
```
0-10s: "Stabilizing... Display in Xs" (data collected, not shown)
10s:   "✅ DISPLAY ENABLED - stabilization complete"
10s+:  Normal sensorgram display with stable peak tracking
```

---

## ✅ Validation Checklist

Before deploying to production:

- [ ] LED values in live mode match Step 6 exactly
- [ ] Boost factor between 1.0× and 1.4× (logged in console)
- [ ] No saturation warnings (all channels < 60,400 counts)
- [ ] Display hidden for first 10 seconds with status message
- [ ] Sensorgram appears automatically after 10s
- [ ] Peak tracking stable within ±1 RU after stabilization
- [ ] Update rate 3-5 Hz (4 channels × ~50ms + overhead)

---

## 🛠️ Tuning If Needed

**Signal too low** (< 40,000 counts):
```python
LIVE_MODE_MAX_BOOST_FACTOR = 1.6  # Increase to 60%
```

**Saturation detected** (> 60,400 counts):
```python
LIVE_MODE_TARGET_INTENSITY_PERCENT = 85  # Reduce target
# or
LIVE_MODE_MAX_BOOST_FACTOR = 1.2  # Reduce boost to 20%
```

**Processing unstable after 10s**:
```python
LIVE_MODE_DISPLAY_DELAY_SECONDS = 15.0  # Increase delay
```

---

## 📊 Performance Impact

**Before** (Old 2.5× boost):
- Risk of saturation on strong channels
- Aggressive boost could cause processing artifacts
- No stabilization period

**After** (New 1.4× boost + 10s delay):
- Conservative, safe operation
- Perfect compensation for P-pol dampening (30-40% lower → 40% boost)
- Processing algorithms fully stabilized before display
- User sees clean, reliable data from the start

---

## 📝 Files Modified

1. **`settings/settings.py`** - Boost configuration
2. **`utils/spr_state_machine.py`** - Smart boost logic
3. **`widgets/datawindow.py`** - Display delay implementation
4. **`LIVE_MODE_SMART_BOOST_IMPLEMENTATION.md`** - Full documentation

---

## 🎓 Key Principles

1. **LED Stability**: Step 6 values are frozen (never change)
2. **Conservative Boost**: 20-40% is safe and effective
3. **Safety First**: Enforce saturation and budget limits
4. **Let Filters Stabilize**: 10-second delay ensures clean data
5. **Transparency**: Log all decisions for debugging

**Bottom Line**: *Smart boost maximizes signal while maintaining safety and stability.*
