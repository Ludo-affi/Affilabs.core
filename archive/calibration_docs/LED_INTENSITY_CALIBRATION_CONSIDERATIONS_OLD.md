# LED Intensity and Optical System Calibration

**Question**: Does LED intensity affect optical system calibration validity?
**Answer**: For PicoP4SPR: **NO - intensity is fixed at 100%, so calibration is always at operating intensity** ✅

---

## TL;DR - Your System (PicoP4SPR)

✅ **Current calibration is VALID**

**Why**:
- PicoP4SPR has **fixed LED intensity** (ON = 100%, OFF = 0%)
- No PWM or current control available
- Calibration automatically performed at operating intensity
- All measurements use same intensity → correction is always accurate
- **No intensity-dependent calibration needed!**

---

## Theory: Intensity Effects on Afterglow

### What Changes with Intensity

| Parameter | Intensity Dependence | Impact on Calibration |
|-----------|---------------------|----------------------|
| **Afterglow Amplitude (A)** | ✅ Scales linearly with intensity | Need to calibrate at operating intensity |
| **Decay Constant (τ)** | ⚠️ Should be constant (material property) | Independent of intensity (in theory) |
| **Baseline** | ✅ Independent | No effect |

### Expected Behavior (Theory)

**Phosphor decay kinetics**:
```
Signal(t) = Baseline + Amplitude × exp(-t/τ)

- Amplitude ∝ LED intensity (brighter LED → stronger afterglow)
- τ = intrinsic phosphor property (should NOT depend on intensity)
- Baseline = dark signal (independent of LED)
```

**Example**:
```
50% intensity:  A = 100 counts, τ = 1.0ms
100% intensity: A = 200 counts, τ = 1.0ms  ← τ unchanged
```

### Potential Non-Linear Effects (Edge Cases)

**At very HIGH intensity** (near saturation):
1. **Phosphor saturation**: All phosphor sites occupied → altered kinetics
2. **Thermal effects**: LED heating → temperature-dependent decay
3. **Detector saturation**: Non-linear detector response near max counts

**At very LOW intensity** (near noise floor):
1. **Poor signal-to-noise**: Afterglow signal hard to measure
2. **Low R²**: Unreliable exponential fit

---

## Current Calibration Assessment

### Our Calibration Conditions

**Signal levels** (from calibration data):
- Channel A peak: 3088 counts (~5% of 65k max)
- Channel D peak: ~3800-4000 counts (~6% of max)
- Afterglow amplitudes: 150-750 counts
- Baseline: ~2900-3000 counts

**Quality**:
- ✅ Well below saturation (>90% headroom)
- ✅ Good signal-to-noise (R² > 0.95)
- ✅ Typical operating intensity (not artificially boosted)

### Hardware Capability: PicoP4SPR

**LED intensity control**: ❌ **NOT AVAILABLE**

From `pico_p4spr_hal.py`:
```python
def set_led_intensity(self, intensity: float) -> bool:
    """Set LED intensity (not supported by PicoP4SPR)."""
    # PicoP4SPR doesn't support variable LED intensity
    # LED is either on (when channel is active) or off
    logger.debug("LED intensity control not supported by PicoP4SPR")
    return True  # Handled by channel activation
```

**Implication**: ✅ **PERFECT FOR CALIBRATION**
- LEDs always at 100% when activated
- Calibration intensity = Operating intensity (always)
- No intensity variability to worry about
- Single-intensity calibration is sufficient

---

## Answer to Your Question

### Q: "If we were to do it at max intensity without saturation, would it make a difference?"

**A: For your system (PicoP4SPR), we ARE already at max intensity!**

**Explanation**:
1. Your hardware only supports ON/OFF (no dimming)
2. When we activate a channel, LED is at 100% (max intensity)
3. Our calibration WAS performed at max intensity
4. Signal levels (3000-4000 counts) are well below saturation (65k max)
5. Therefore: **Calibration intensity = Operating intensity = Max intensity** ✅

**Theoretical consideration**:
- If we could boost intensity higher (e.g., via hardware modification), would it matter?
- **Probably minimal effect** since:
  - τ is intrinsic material property (should be constant)
  - We're not near saturation or thermal limits
  - Signal-to-noise is already good
- **BUT**: We can't test this since hardware doesn't support variable intensity

---

## Validation: Does Intensity Match SPR Measurements?

### Action Item: Verify Operating Intensity

During actual SPR measurement, check signal levels:

```python
# In SPR data acquisition
for channel in [ChannelID.A, B, C, D]:
    ctrl.activate_channel(channel)
    time.sleep(0.020)  # Stabilization

    spectrum = spec.intensities()
    mean_signal = np.mean(spectrum)
    peak_signal = np.max(spectrum)

    print(f"Channel {channel.name}:")
    print(f"  Mean: {mean_signal:.0f} counts")
    print(f"  Peak: {peak_signal:.0f} counts")
```

**Expected result**: Should match calibration levels (~3000-4000 counts)

**If significantly different**:
- ⚠️ Something changed in hardware/configuration
- May need to re-calibrate
- But this should NOT happen since intensity is hardware-fixed

---

## Recommendations

### For PicoP4SPR (Current System) ✅

**Current calibration is VALID and SUFFICIENT**

**No additional testing needed** because:
1. ✅ Intensity is hardware-fixed (no variability)
2. ✅ Calibrated at operating intensity (ON = 100%)
3. ✅ Well below saturation (plenty of headroom)
4. ✅ Good signal-to-noise (R² > 0.95)

**What to monitor**:
- Verify SPR measurement signal levels match calibration (~3000-4000 counts)
- If levels drift significantly (>50%), may indicate:
  - LED aging (re-calibrate annually)
  - Hardware change (re-calibrate required)
  - Integration time changed (already covered by our calibration)

### For Systems with Variable Intensity (Future Hardware)

**If future hardware supports LED dimming**:

**Option 1: Calibrate at typical operating intensity** (RECOMMENDED)
- Set LED to typical use intensity (e.g., 80% to avoid saturation)
- Run calibration
- Use correction only when operating at same intensity
- **Valid if**: Operating intensity is consistent (±20%)

**Option 2: Multi-intensity calibration** (ROBUST)
- Calibrate at 25%, 50%, 75%, 100% intensity
- Build 2D lookup table: τ(integration_time, intensity)
- Interpolate both dimensions during correction
- **Valid for**: Wide operating intensity range

**Option 3: Amplitude scaling** (SIMPLE APPROXIMATION)
- Calibrate at one intensity
- Scale amplitude linearly: `A_corrected = A_calibrated × (I_current / I_calibration)`
- Assume τ is intensity-independent
- **Valid if**: Linear phosphor response (usually true below saturation)

---

## Conclusion

### For Your System (PicoP4SPR)

✅ **Calibration is VALID - no intensity considerations needed**

**Reasons**:
1. Hardware has fixed intensity (ON = 100%, no control)
2. Calibration performed at operating intensity
3. Signal levels appropriate (not saturated, good SNR)
4. Intensity is constant across all measurements
5. No intensity-dependent effects to worry about

### General Best Practice

**Always calibrate at the intensity you'll use in production**

**Why**:
- Ensures correction accuracy at operating conditions
- Avoids extrapolation effects
- Captures any non-linear intensity-dependent behavior
- Simplest and most reliable approach

**For systems with variable intensity**:
- Calibrate at typical operating intensity
- Or use multi-intensity calibration for robustness
- Monitor signal levels to detect hardware changes

---

## Summary Table

| Scenario | Calibration Strategy | Valid for PicoP4SPR? |
|----------|---------------------|---------------------|
| **Fixed intensity hardware** | Single calibration at 100% | ✅ YES - Current system |
| Variable intensity, consistent use | Calibrate at typical intensity | N/A - No intensity control |
| Variable intensity, wide range | Multi-intensity calibration | N/A - No intensity control |
| Very high intensity (saturation risk) | Calibrate at safe intensity | ✅ Already safe (~5% of max) |
| Very low intensity (poor SNR) | Boost to adequate level | N/A - Hardware fixed |

**Bottom line**: Your current calibration is **perfect for your hardware** ✅

---

**Date**: October 11, 2025
**Hardware**: PicoP4SPR + FLMT09788 + luminus_cool_white + 200µm
**Calibration File**: `led_afterglow_integration_time_models_20251011_210859.json`
**Status**: ✅ VALID - No intensity-related concerns
