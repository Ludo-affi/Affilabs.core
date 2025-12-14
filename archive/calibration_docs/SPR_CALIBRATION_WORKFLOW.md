# SPR Calibration Workflow with Polarization
## Complete Guide to Polarization-Aware LED Calibration

### Overview

This workflow measures LED calibration separately at S and P polarization states, capturing the complete optical system including polarizer transmission. The result is a normalized calibration matrix suitable for SPR extinction measurements.

---

## Workflow Steps

### Step 1: Measure S-Polarization Calibration
**Time: ~5 minutes**

```bash
python measure_spr_calibration_with_polarization.py
```

**What it does:**
- Prompts you to set polarizer to S-polarization
- Measures 92 points (23 per LED) focused on SPR region (8k-22k counts)
- Integration times: 5, 7.5, 10, 12.5, 15, 20, 25ms
- Intensities: 40-255 (optimized for low-count SPR signals)
- Saves: `led_calibration_spr_S_polarization.json`

### Step 2: Measure P-Polarization Calibration
**Time: ~5 minutes**

**What it does:**
- Prompts you to rotate polarizer to P-polarization
- Measures same 92 points at P-polarization
- Captures polarization-dependent transmission
- Saves: `led_calibration_spr_P_polarization.json`

### Step 3: Measure Dark Current
**Time: ~1 minute**

**What it does:**
- Turns OFF all LEDs
- Measures dark current at 11 integration times (5-45ms)
- Characterizes detector noise floor
- Saves: `dark_signal_calibration.json`

### Step 4: Process and Normalize
**Time: <1 second**

```bash
python process_spr_calibration.py
```

**What it does:**
- Loads S, P, and dark measurements
- Applies dark correction to all data: `true_signal = measured - dark(time)`
- Builds 2D RBF interpolation models for S and P separately
- Validates model accuracy (target: <5% error)
- Calculates polarization transmission ratios
- Creates visualization comparing S vs P
- Saves: `led_calibration_spr_processed.json`

---

## Model Architecture

```
COMPLETE MODEL:
  counts(I, T, pol) = LED_signal(I, T, pol) + dark(T)

Where:
  - LED_signal(I, T, 'S'): 2D RBF model for S-polarization
  - LED_signal(I, T, 'P'): 2D RBF model for P-polarization
  - dark(T): Linear dark current (rate × time + offset)
```

### Why This Approach?

1. **Captures real optical system**: Polarizer is in place during calibration
2. **SPR-focused**: Dense sampling in 10k-20k counts region (not 80% saturation!)
3. **Dark-corrected**: Subtracts detector noise for accurate signal
4. **Polarization-aware**: Separate models for S and P states
5. **Physically meaningful**: Separates LED + polarizer from detector artifacts

---

## Calibration Coverage

### Current (High-Saturation) Calibration
- **Region**: 45k-53k counts (80% saturation)
- **Coverage in SPR**: Only 5-13% of points
- **Problem**: Extrapolating down 2.5-4x to SPR region

### New SPR-Focused Calibration
- **Region**: 8k-22k counts (SPR operating range)
- **Coverage in SPR**: 100% focused on target region
- **Integration times**: 5-25ms (shorter than before)
- **Intensities**: 40-255 (lower than before)
- **Points per LED per pol**: 23 × 2 = 46 measurements

---

## Expected Results

### Polarization Transmission
- **T_S**: ~0.45-0.50 (polarizer blocks ~50% of unpolarized LED light)
- **T_P**: ~0.45-0.50 (should be similar if LEDs unpolarized)
- **S/P Ratio**: 0.9-1.1 (if no SPR sample present)
- **S/P Ratio**: 1.2-2.0 (if SPR sample present during calibration)

### Model Accuracy
- **Target**: <2% error in SPR region (10k-20k counts)
- **Acceptable**: <5% error across full range
- **Warning**: >5% error suggests need for more calibration points

### Dark Current
- **Expected**: 5-10 counts/ms for Hamamatsu detectors
- **Impact at SPR levels**: 0.2-0.5% of signal
- **Linearity**: R² > 0.999 (dark should be perfectly linear with time)

---

## Usage in SPR Measurements

### Predict Counts for Target Settings

```python
from process_spr_calibration import models_S, models_P

# For S-polarization
intensity = 100
time_ms = 15.0
led = 'A'

counts_S = models_S[led](np.array([[intensity, time_ms]]))[0]
counts_S_with_dark = counts_S + (dark_rate * time_ms + dark_offset)

# For P-polarization
counts_P = models_P[led](np.array([[intensity, time_ms]]))[0]
counts_P_with_dark = counts_P + (dark_rate * time_ms + dark_offset)

# SPR extinction
extinction = (counts_S_with_dark - counts_P_with_dark) / counts_S_with_dark
```

### Set LED for Target Counts

```python
from scipy.optimize import minimize_scalar

target_counts = 15000  # SPR mid-range
polarization = 'S'
time_ms = 15.0

model = models_S[led] if polarization == 'S' else models_P[led]

def objective(intensity):
    predicted = model(np.array([[intensity, time_ms]]))[0]
    predicted_with_dark = predicted + (dark_rate * time_ms + dark_offset)
    return abs(predicted_with_dark - target_counts)

result = minimize_scalar(objective, bounds=(40, 255), method='bounded')
optimal_intensity = int(round(result.x))
```

---

## Validation Checklist

After running calibration and processing:

- [ ] Dark current linear fit: R² > 0.999
- [ ] Dark rate: 5-15 counts/ms (typical range)
- [ ] S-pol model errors: Mean <2%, Max <10%
- [ ] P-pol model errors: Mean <2%, Max <10%
- [ ] S/P ratio consistency: Std dev <0.1 across LEDs
- [ ] SPR region coverage: 100% of points in 8k-22k range
- [ ] Visualizations look reasonable (no obvious outliers)

---

## Troubleshooting

### High S/P Extinction (>20%)
- **Cause**: SPR sample present during calibration
- **Effect**: Models include sample absorption
- **Solution**: Either remove sample or accept models characterize system+sample

### High Model Errors (>5%)
- **Cause**: Insufficient calibration points or measurement noise
- **Solution**: Add more points in regions with high error
- **Tool**: Use validation analysis to identify sparse regions

### Non-linear Dark Current
- **Cause**: LEDs not fully OFF or stray light
- **Check**: Measure counts at I=0 for all channels
- **Solution**: Ensure hardware fully turns off LEDs

### Inconsistent S/P Ratio Across LEDs
- **Cause**: Wavelength-dependent polarizer or partially polarized LEDs
- **Effect**: Need wavelength-specific corrections
- **Solution**: Acceptable if std dev <0.1, otherwise investigate polarizer

---

## Files Created

1. **led_calibration_spr_S_polarization.json**
   - S-polarization measurements (raw)
   - 92 points across 4 LEDs

2. **led_calibration_spr_P_polarization.json**
   - P-polarization measurements (raw)
   - 92 points across 4 LEDs

3. **dark_signal_calibration.json**
   - Dark current characterization
   - Linear fit parameters

4. **led_calibration_spr_processed.json**
   - Dark-corrected measurements
   - Ready for model building

5. **spr_calibration_comparison.png**
   - Visualization of S vs P calibration
   - 2×2 grid showing all 4 LEDs

---

## Total Time Investment

- **Measurement**: ~11 minutes (S + P + dark)
- **Processing**: <1 second
- **Validation**: ~2 minutes (review results)
- **Total**: ~13 minutes for production-ready SPR calibration

---

## Next Integration Steps

1. Update `LED2DCalibrationModel` class to support polarization parameter
2. Add methods: `get_optimal_settings_spr(target, time, pol)`
3. Integrate with SPR measurement workflow
4. Add temperature tracking for dark current compensation
5. Implement periodic re-calibration checks

---

## Key Differences from Previous Calibration

| Aspect | Old Calibration | New SPR Calibration |
|--------|----------------|---------------------|
| Target region | 45k-53k counts (80%) | 8k-22k counts (SPR) |
| Integration times | 25-45ms | 5-25ms |
| Intensities | High (target 80%) | Low (target 15%) |
| Polarization | Single model | Separate S & P |
| Dark correction | No | Yes |
| SPR coverage | 5-13% | 100% |
| Model type | 2D RBF | 2D RBF (S&P) + dark |

---

## Summary

This workflow creates a **polarization-aware, dark-corrected calibration** specifically optimized for **SPR extinction measurements** in the 10k-20k counts region. By measuring S and P separately with the polarizer in place, you capture the complete optical system and eliminate the need for separate polarizer transmission corrections.
