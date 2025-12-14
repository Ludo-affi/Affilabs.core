# Dark Noise Measurement and Application in SPR System

**Date:** October 10, 2025
**Topic:** How dark noise is measured once and applied to both S and P spectra

---

## Overview

The SPR system measures **dark noise once** during calibration (Step 5) and applies the **same dark noise correction** to both S-mode and P-mode measurements. This is correct because dark noise is independent of LED state and polarization - it's purely detector-based noise.

---

## 📊 Calibration Sequence (9 Steps)

```
Step 1: Wavelength Range Calibration
Step 2: Auto-Polarization (optional)
Step 3: Integration Time Optimization (S-mode, all channels)
Step 4: LED Intensity Calibration (S-mode, adaptive)
Step 5: 🌑 DARK NOISE MEASUREMENT ← Measured once here
Step 6: Reference Signal Measurement (S-mode)
Step 7: Switch to P-mode
Step 8: LED Intensity Calibration (P-mode, S-based)
Step 9: Validation
```

**Key Point:** Dark noise is measured **after S-mode LED calibration** but **before reference signals**. It's measured with **all LEDs OFF**, making it independent of mode (S or P).

---

## 🌑 Dark Noise Measurement (Step 5)

### Location
**File:** `utils/spr_calibrator.py`
**Method:** `measure_dark_noise()` (lines 1618-1718)
**Called:** Step 5 of `run_full_calibration()` (line 2481)

### Process

#### 1. Turn Off All LEDs
```python
self.ctrl.turn_off_channels()  # All 4 channels OFF
time.sleep(LED_DELAY)           # Wait for LEDs to stabilize (100ms)
```

**Why:** Dark noise is the signal the detector produces when **no light** is present. This includes:
- Electronic noise from the detector
- Thermal noise (dark current)
- Read noise from the spectrometer
- Background ambient light (minimal, but possible)

#### 2. Determine Scan Count
```python
if self.state.integration < 50ms:
    dark_scans = 30  # DARK_NOISE_SCANS
else:
    dark_scans = 15  # Fewer scans for longer integration
```

**Why adaptive?**
- Longer integration times → better SNR per scan → fewer scans needed
- Shorter integration times → more noise → need more averaging

#### 3. Acquire Full Spectrum Dark Noise
```python
dark_noise_sum = np.zeros(full_spectrum_length)  # e.g., 3648 pixels for USB4000

for scan in range(dark_scans):
    intensity = usb.read_intensity()  # Read FULL spectrum
    dark_noise_sum += intensity

full_spectrum_dark_noise = dark_noise_sum / dark_scans  # Average
```

**Key Points:**
- Measures **full spectrum** (all 3648 pixels)
- **Averages** 15-30 scans to reduce noise
- Uses the **same integration time** as data acquisition will use
- No wavelength cropping yet

#### 4. Store Full Spectrum for Resampling
```python
self.state.full_spectrum_dark_noise = full_spectrum_dark_noise
```

This allows universal resampling later if needed.

#### 5. Resample to Target Wavelength Range
```python
# Option A: Universal resampling (preferred)
from scipy.interpolate import interp1d

target_indices = np.linspace(wave_min_index, wave_max_index - 1,
                             len(target_wavelengths))
interpolator = interp1d(source_indices, full_spectrum_dark_noise,
                        kind='linear', bounds_error=False,
                        fill_value='extrapolate')
resampled_dark_noise = interpolator(target_indices)

self.state.dark_noise = resampled_dark_noise

# Option B: Simple cropping (fallback)
cropped_dark_noise = full_spectrum_dark_noise[wave_min_index:wave_max_index]
self.state.dark_noise = cropped_dark_noise
```

**Result:** `self.state.dark_noise` now matches the size of data acquisition arrays.

---

## 📦 Dark Noise Storage

### CalibrationState Object
```python
class CalibrationState:
    def __init__(self):
        self.dark_noise: np.ndarray = np.array([])                # Resampled for data acquisition
        self.full_spectrum_dark_noise: np.ndarray = np.array([])  # Full spectrum backup
```

### Saved to Calibration Profile
```json
{
  "profile_name": "auto_save_20251010_120843",
  "integration": 0.032,  // 32ms - same integration time used for dark measurement
  "dark_noise": [120.5, 118.3, 121.7, ...],  // Saved but not typically reloaded
  "full_spectrum_dark_noise": [...]            // Full spectrum backup
}
```

**Note:** Dark noise is typically measured fresh for each session because:
- It depends on integration time (which may change)
- It depends on detector temperature (which varies)
- It's quick to measure (15-30 scans × 32ms = 0.5-1 second)

---

## 🔬 Dark Noise Application to S and P Spectra

### When is Dark Noise Applied?

Dark noise correction happens during **real-time data acquisition**, not during calibration.

### Data Flow During Measurement

```
User starts measurement
    ↓
SPRDataAcquisition.sensorgram_data()  // Real-time acquisition loop
    ↓
FOR EACH TIME POINT:
    ├─ S-mode measurement:
    │   ├─ Set controller to S-mode
    │   ├─ Acquire spectrum with S-mode LEDs
    │   ├─ Apply dark noise correction: S_corrected = S_raw - dark_noise
    │   └─ Store in ref_sig
    │
    ├─ P-mode measurement:
    │   ├─ Set controller to P-mode
    │   ├─ Acquire spectrum with P-mode LEDs
    │   ├─ Apply dark noise correction: P_corrected = P_raw - dark_noise
    │   └─ Store in p_pol_intensity
    │
    └─ Calculate transmittance:
        T = (P_corrected / S_corrected) × 100%
```

### Application in Real-Time Acquisition

**File:** `utils/spr_data_acquisition.py`
**Method:** `sensorgram_data()` (lines 150-300)

```python
# S-mode measurement
averaged_intensity = np.mean(s_mode_scans, axis=0)

# Apply dark noise correction with universal resampling
if self.dark_noise.shape == averaged_intensity.shape:
    dark_correction = self.dark_noise
else:
    # Resample dark noise to match data size
    dark_correction = resample_dark_noise(self.dark_noise, averaged_intensity.shape)

s_ref_corrected = averaged_intensity - dark_correction
ref_sig[ch] = s_ref_corrected

# P-mode measurement (later)
averaged_p_intensity = np.mean(p_mode_scans, axis=0)
p_pol_corrected = averaged_p_intensity - dark_correction  # SAME dark noise!

# Calculate transmittance
transmission = (p_pol_corrected / s_ref_corrected) × 100%
```

### Application in Transmittance Calculation

**File:** `utils/spr_data_processor.py`
**Method:** `calculate_transmission()` (lines 69-118)

```python
def calculate_transmission(self, p_pol_intensity, s_ref_intensity, dark_noise=None):
    """Calculate transmission: (P-pol / S-ref) × 100%"""

    if dark_noise is not None:
        # Apply SAME dark correction to BOTH P and S
        p_pol_corrected = self._apply_universal_dark_correction(p_pol_intensity, dark_noise)
        s_ref_corrected = self._apply_universal_dark_correction(s_ref_intensity, dark_noise)
    else:
        p_pol_corrected = p_pol_intensity
        s_ref_corrected = s_ref_intensity

    # Calculate transmittance
    transmission = (p_pol_corrected / s_ref_corrected) * 100.0

    return transmission
```

---

## 🧮 Mathematical Foundation

### Why One Dark Noise for Both S and P?

Dark noise is **detector-based**, not **source-based**:

```
Signal = (Light_from_sample + Dark_noise)

S-mode signal:
S_raw = S_light + Dark_noise
S_corrected = S_raw - Dark_noise = S_light ✓

P-mode signal:
P_raw = P_light + Dark_noise
P_corrected = P_raw - Dark_noise = P_light ✓

Transmittance:
T = P_corrected / S_corrected
  = P_light / S_light
  = True transmittance (no dark noise bias!) ✓
```

### Dark Noise Characteristics

| Property | Value | Note |
|----------|-------|------|
| **Origin** | Detector electronics | Not from LEDs or sample |
| **Wavelength-dependent?** | Yes, slightly | Different pixels have different dark current |
| **Integration-dependent?** | Yes, linear | Dark_noise ∝ Integration_time |
| **LED-dependent?** | No | Measured with LEDs OFF |
| **Polarization-dependent?** | No | Measured before polarizer effects |
| **Temperature-dependent?** | Yes | Higher temp → more dark current |

### Integration Time Scaling

**Important:** Dark noise **must be measured** at the same integration time used for data acquisition!

```
Dark_noise(T_int) = Dark_current × T_int

Example:
- Dark noise @ 32ms: 120 counts
- Dark noise @ 16ms: 60 counts (half)
- Dark noise @ 64ms: 240 counts (double)
```

**This is why we measure dark noise AFTER integration time calibration (Step 5 follows Step 3).**

---

## 🔄 Dark Noise Lifecycle

### During Calibration
```
1. Step 3: Integration time optimized → e.g., 32ms
2. Step 4: S-mode LEDs optimized
3. Step 5: 🌑 Dark noise measured at 32ms integration
            ├─ All LEDs OFF
            ├─ 15-30 scans averaged
            ├─ Full spectrum (3648 pixels)
            └─ Resampled to target range
4. Step 6: S-mode reference signals measured
            └─ Dark noise already available
5. Step 8: P-mode LED optimization
            └─ Uses same dark noise from Step 5
```

### During Measurement
```
Continuous measurement loop:
├─ S-mode: Acquire → Apply dark correction → Store
├─ P-mode: Acquire → Apply dark correction → Store
└─ Calculate: T = P_corrected / S_corrected
```

### When Dark Noise Changes

Dark noise must be **re-measured** when:
- ✅ Integration time changes
- ✅ Detector temperature changes significantly
- ✅ New calibration is performed
- ❌ Not needed when: LED intensity changes
- ❌ Not needed when: Polarization mode changes
- ❌ Not needed when: Sample changes

---

## 🎯 Universal Dark Correction Method

The system uses "universal dark correction" which handles size mismatches:

```python
def _apply_universal_dark_correction(signal, dark_noise):
    """Apply dark correction even if sizes don't match"""

    if dark_noise.shape == signal.shape:
        # Perfect match
        return signal - dark_noise

    # Size mismatch - resample dark noise
    if len(dark_noise) == 1:
        # Single value - broadcast
        return signal - dark_noise[0]

    # Use linear interpolation
    interpolator = interp1d(source_indices, dark_noise, kind='linear')
    resampled_dark = interpolator(target_indices)
    return signal - resampled_dark
```

**Why this approach?**
- **Robust:** Handles legacy calibrations with different array sizes
- **Universal:** Works with any wavelength range configuration
- **Accurate:** Preserves dark noise spectral features through interpolation

---

## 📊 Example: Dark Noise in Your Calibration

### From auto_save_20251010_120843.json

```json
{
  "integration": 0.032,  // 32ms
  "dark_noise": [120, 118, 121, 119, 122, ...],  // ~120 counts average
}
```

**Analysis:**
```
Dark noise: ~120 counts @ 32ms integration
S-mode signal: ~48,000 counts
P-mode signal: ~40,000 counts (after integration adjustment)

Dark noise fraction:
- S-mode: 120 / 48,000 = 0.25% (negligible)
- P-mode: 120 / 40,000 = 0.30% (negligible)

Signal-to-Noise Ratio (SNR):
- S-mode: 48,000 / √48,000 ≈ 220:1 (excellent)
- P-mode: 40,000 / √40,000 ≈ 200:1 (excellent)
```

**Conclusion:** Dark noise is small compared to signal, but still important to subtract for accurate transmittance calculations.

---

## ❓ Common Questions

### Q1: Why not measure dark noise separately for S and P modes?

**A:** Because dark noise is **detector-based**, not **source-based**. It doesn't matter what mode the polarizer is in - the dark noise is the same. Measuring it twice would be redundant and waste time.

### Q2: What if S and P modes use different integration times?

**A:** Currently, the system uses the **same integration time** for both S and P modes. This is set in Step 3 (integration time calibration) and modified in Step 8 (P-mode calibration) to match signal levels. The dark noise is measured at the **final integration time** after Step 8 adjustments.

**Note:** If future versions use different integration times for S and P, then dark noise would need to scale:
```python
dark_noise_P = dark_noise_S × (integration_P / integration_S)
```

### Q3: Why measure dark noise AFTER LED calibration and not at the beginning?

**A:** Because:
1. Integration time isn't known until Step 3
2. Dark noise scales with integration time
3. Measuring it too early would require re-measurement

**Optimal position:** After integration time is finalized, before reference measurements.

### Q4: What happens if dark noise isn't applied?

**A:** Without dark correction:
```
T_uncorrected = (P_raw / S_raw) × 100%
              = (P_light + Dark) / (S_light + Dark) × 100%

If Dark = 120, P_light = 40,000, S_light = 48,000:
T_uncorrected = (40,120 / 48,120) × 100% = 83.38%
T_corrected   = (40,000 / 48,000) × 100% = 83.33%
Error = 0.05% (small but systematic)
```

For low signals, the error would be larger!

### Q5: Can we use old calibration's dark noise?

**A:** **Not recommended** because:
- Dark noise depends on integration time (which may have changed)
- Dark noise depends on detector temperature (ambient conditions)
- It's quick to measure fresh (~1 second)

However, the system does save it in calibration profiles for reference/debugging.

---

## 🔬 Summary

### Key Principle
**One dark noise measurement, applied to both S and P spectra**

### Justification
- Dark noise is detector-based (not polarization-dependent)
- Same integration time used for both S and P modes
- Efficient (no need to measure twice)
- Physically correct (dark noise doesn't change with polarization)

### Measurement Timing
```
Step 5 (Dark Noise):
- After integration time optimization
- After S-mode LED calibration
- Before S-mode reference measurement
- Before P-mode LED calibration

Result: One dark noise array used for all subsequent measurements
```

### Application
```
Real-time measurement:
FOR EACH time point:
    S_corrected = S_raw - dark_noise
    P_corrected = P_raw - dark_noise
    T = (P_corrected / S_corrected) × 100%
```

This approach is both **efficient** and **physically correct**! 🎯
