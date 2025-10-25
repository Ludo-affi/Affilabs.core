# P-pol Data Flow and Diagnostic Visualization

## Summary

This document explains how calibration data is transferred to live mode and how to visualize the first P-pol measurements.

## Complete Data Pipeline

### 1. Calibration Step 4: LED Balancing
**Location**: `utils/spr_calibrator.py` lines 3920-4095

- Measures raw S-pol spectra with increasing LED intensities
- Finds LED values that achieve **49,151 counts** (75% detector max) in ROI 580-610nm
- Stores LED values in: `self.state.ref_intensity`
- **Syncs to live mode**: `self.state.leds_calibrated = self.state.ref_intensity.copy()` (line 3816)

### 2. Calibration Step 6: S-reference Measurement
**Location**: `utils/spr_calibrator.py` lines 4079-4087

- Measures S-pol with calibrated LEDs (polarizer at 0°)
- Subtracts dark noise
- Stores in: `self.data_acquisition.ref_sig[ch]`
- This becomes the **denominator** in P/S ratio

### 3. Live Mode Starts
**Location**: `utils/spr_data_acquisition.py` lines 943-944

```python
elif hasattr(self.state, 'leds_calibrated') and ch in self.state.leds_calibrated:
    intensity_array[idx] = self.state.leds_calibrated[ch]
```

- User clicks "Start" button → acquisition loop begins
- Each channel reads LED intensity from `self.state.leds_calibrated`
- LEDs are activated with calibrated intensities

### 4. P-pol Measurement (each cycle)
**Location**: `utils/spr_data_acquisition.py` line 1248

```python
p_corrected = averaged_intensity - dark_correction
```

- Turn on LED with calibrated intensity
- Rotate polarizer to 90° (P-mode)
- Acquire P-pol spectrum
- Subtract dark noise

### 5. Transmittance Calculation
**Location**: `utils/spr_data_acquisition.py` lines 1252-1258

```python
self.trans_data[ch] = (
    self.data_processor.calculate_transmission(
        p_pol_intensity=p_corrected,
        s_ref_intensity=ref_sig_adjusted,  # Already dark-corrected
        dark_noise=None,  # Don't subtract dark again!
        denoise=False,  # ✨ O2: Skip denoising for sensorgram speed
    )
)
```

- Calculate **P/S ratio**: `trans = p_corrected / s_ref`
- Result stored in: `self.trans_data[ch]`

### 6. Peak Extraction → Sensorgram
**Location**: `utils/spr_data_processor.py` (centroid/peak finding)

- Extract centroid/peak wavelength from transmittance spectrum
- Convert to resonance shift (RU)
- Update sensorgram time-series plot

## Key Variables

### Calibration → Live Mode Sync
| Variable | Description | Location |
|----------|-------------|----------|
| `state.ref_intensity` | LED values from Step 4 | Step 4 output |
| `state.leds_calibrated` | Copy for live mode | Line 3816 |
| `data_acquisition.ref_sig[ch]` | S-reference from Step 6 | Step 6 output |

### Live Mode Data Flow
| Variable | Description | Units |
|----------|-------------|-------|
| `int_data[ch]` | P-pol (dark-corrected) | counts |
| `ref_sig[ch]` | S-reference (from calibration) | counts |
| `trans_data[ch]` | P/S ratio (transmittance) | dimensionless |
| `lambda_values[ch]` | Resonance shift time-series | RU (nm) |

## Creating P-pol Diagnostic Plot

### Method 1: From Running Application (Recommended)

After calibration completes and live mode starts:

1. Wait for first full cycle (1-2 seconds)
2. In Python console or debug mode:
   ```python
   app.data_acquisition.create_ppol_diagnostic_plot()
   ```
3. Plot saved to: `generated-files/diagnostics/ppol_live_diagnostic_[timestamp].png`

### Method 2: Manual Integration

Add this code to your application after the first P-pol cycle completes:

```python
# In main application after first live cycle
if self.data_acquisition.cycle_count == 1:  # First cycle only
    self.data_acquisition.create_ppol_diagnostic_plot()
```

## Diagnostic Plot Contents

The P-pol diagnostic plot shows 4 panels:

### Panel 1: P-pol Spectra (Dark-Corrected)
- Shows P-pol intensity for all channels
- Labels indicate LED values used
- This is the **numerator** in P/S calculation

### Panel 2: S-reference Spectra
- Shows S-ref from calibration Step 6
- This is the **denominator** in P/S calculation
- Same S-ref used throughout entire live session

### Panel 3: Transmittance (P/S Ratio)
- Shows final P/S ratio spectrum
- This is what peak finding operates on
- Peak extraction → resonance shift → sensorgram

### Panel 4: ROI Statistics
- Mean intensities in 580-610nm ROI
- Shows P-pol, S-ref, and P/S values
- These are the counts used for measurements

## Example Output

```
LIVE MODE P-POL DIAGNOSTIC
═══════════════════════════════════════════

Integration Time: 33.7 ms

ROI Statistics (580-610nm):

   Channel A (LED=103):
      P-pol:        40,335 counts
      S-ref:        46,151 counts
      P/S ratio:    0.8740

   Channel B (LED=255):
      P-pol:        53,607 counts
      S-ref:        49,151 counts
      P/S ratio:    1.0906

   Channel C (LED=32):
      P-pol:        48,203 counts
      S-ref:        49,151 counts
      P/S ratio:    0.9807

   Channel D (LED=33):
      P-pol:        46,458 counts
      S-ref:        49,151 counts
      P/S ratio:    0.9452
```

## Troubleshooting

### P-pol values are negative
- Check jitter correction is disabled (should be False for all measurements)
- Verify dark noise is correct (should be ~3,000 counts @ 36ms)

### S-ref values are too low
- May indicate incomplete LED turn-off during Step 5 dark measurement
- Check Step 5 QC logs for LED verification

### P/S ratio looks wrong
- Verify P-pol and S-ref have same wavelength array length
- Check that S-ref has dark subtracted (should be done in Step 6)
- Ensure no "double dark subtraction" (P-pol: subtract once, S-ref: already subtracted)

## Related Documentation

- `CALIBRATION_S_REF_QC_SYSTEM.md` - Step 4-6 QC checks
- `ACTION_PLAN.md` - Overall calibration improvements
- `COMPLETE_OPTIMIZATION_ANALYSIS.md` - Performance optimization

## Code Locations

### Calibration
- **Step 4 LED Balancing**: `utils/spr_calibrator.py` lines 3920-4095
- **Step 4 Diagnostic Plot**: `utils/spr_calibrator.py` lines 2882-3050
- **Step 6 S-reference**: `utils/spr_calibrator.py` lines 4079-4323
- **Data Sync**: `utils/spr_calibrator.py` line 3816

### Live Acquisition
- **LED Intensity Read**: `utils/spr_data_acquisition.py` lines 943-944
- **P-pol Acquisition**: `utils/spr_data_acquisition.py` lines 1100-1250
- **Transmittance Calc**: `utils/spr_data_acquisition.py` lines 1252-1258
- **P-pol Diagnostic**: `utils/spr_data_acquisition.py` lines 527-690

## Status

✅ **Complete**:
- Data sync mechanism implemented (line 3816)
- P-pol diagnostic function created
- Documentation complete

🔄 **Next Steps**:
1. Test with hardware after application restart
2. Generate P-pol diagnostic after first live cycle
3. Validate P/S ratio calculation with known samples
