# Reference Baseline - Quick Start Guide

**Purpose**: Fast reference for using the validated baseline processing method

---

## 🎯 What Is This?

The **reference baseline method** is your EXACT production code extracted into a reusable function. It serves as the gold standard for comparison when testing experimental methods.

✅ **Validated**: Matches production code perfectly
✅ **Low P2P**: Proven stable peak-to-peak variation
✅ **Locked**: Parameters fixed for reproducibility

---

## 🚀 Quick Usage

### Import

```python
from utils.reference_baseline_processing import (
    process_spectrum_reference,
    calculate_fourier_weights_reference,
    REFERENCE_PARAMETERS
)
```

### Process Single Spectrum

```python
import numpy as np

# Your data
wavelengths = np.linspace(560, 720, 650)  # ~650 pixels in SPR region
raw_intensity = ...  # Your P-mode raw data
s_reference = ...    # S-mode reference from calibration
dark_noise = ...     # Dark noise spectrum

# Calculate Fourier weights (once)
fourier_weights = calculate_fourier_weights_reference(len(wavelengths))

# Process spectrum
result = process_spectrum_reference(
    raw_spectrum=raw_intensity,
    wavelengths=wavelengths,
    reference_spectrum=s_reference,
    fourier_weights=fourier_weights,
    dark_noise=dark_noise,
    p_led_intensity=220,  # Your P-mode LED
    s_led_intensity=80,   # Your S-mode LED
)

# Get results
resonance_nm = result['resonance_wavelength']
transmission = result['transmission']

print(f"Resonance: {resonance_nm:.3f} nm")
```

---

## 📊 Compare With Experimental Method

```python
# Process with REFERENCE (baseline)
result_ref = process_spectrum_reference(
    raw_spectrum=raw_data,
    wavelengths=wavelengths,
    reference_spectrum=s_ref,
    fourier_weights=fourier_weights,
    dark_noise=dark_noise,
    p_led_intensity=220,
    s_led_intensity=80
)

# Process with YOUR EXPERIMENTAL method
result_exp = your_experimental_function(
    raw_spectrum=raw_data,
    # ... your parameters
)

# Compare
ref_nm = result_ref['resonance_wavelength']
exp_nm = result_exp['resonance_wavelength']
diff_nm = abs(ref_nm - exp_nm)

print(f"Reference:     {ref_nm:.3f} nm")
print(f"Experimental:  {exp_nm:.3f} nm")
print(f"Difference:    {diff_nm:.6f} nm")
```

---

## 🔧 Reference Parameters

**Don't guess - use the locked parameters:**

```python
from utils.reference_baseline_processing import REFERENCE_PARAMETERS

# Access parameters
num_scans = REFERENCE_PARAMETERS['num_scans']  # 3
sg_window = REFERENCE_PARAMETERS['sg_window']  # 21
sg_polyorder = REFERENCE_PARAMETERS['sg_polyorder']  # 3
fourier_window = REFERENCE_PARAMETERS['fourier_window']  # 165

# Use in processing
result = process_spectrum_reference(
    ...,
    window_size=fourier_window,
    sg_window=sg_window,
    sg_polyorder=sg_polyorder
)
```

---

## ✅ Validate Your Setup

Run the test suite to confirm everything works:

```bash
python test_reference_baseline.py
```

**Expected output:**
```
✅ SUCCESS: Reference baseline EXACTLY matches production code
```

---

## 📐 Pipeline Steps (For Reference)

1. **Hardware averaging**: 3 scans with np.mean()
2. **Spectrum trimming**: 560-720nm region
3. **Dark noise subtraction**: intensity - dark_noise
4. **Transmission calculation**: (P/S) × (S_LED/P_LED) × 100
5. **Baseline correction**: Remove linear drift
6. **Savitzky-Golay filter**: Window=21, poly=3
7. **Fourier peak finding**: DST→IDCT→linregress (window=165)

---

## 🚨 Critical Rules

### ✅ DO:
- Use reference method for baseline comparisons
- Create SEPARATE functions for experimental methods
- Lock reference parameters (use REFERENCE_PARAMETERS dict)
- Validate with test suite before deployment

### ❌ DON'T:
- Modify `reference_baseline_processing.py` functions
- Change REFERENCE_PARAMETERS values
- Skip LED intensity correction
- Use different num_scans between calibration and live data

---

## 🎯 Common Use Cases

### Case 1: Testing New Filter
```python
# Reference (baseline)
result_ref = process_spectrum_reference(...)

# Experimental with different filter
result_exp = process_spectrum_experimental(
    ...,
    sg_window=31,  # Testing larger window
    sg_polyorder=5  # Testing higher order
)

# Compare P2P variation over 100 measurements
ref_p2p = measure_p2p(process_spectrum_reference, ...)
exp_p2p = measure_p2p(process_spectrum_experimental, ...)
```

### Case 2: Testing New Peak Finding
```python
# Reference (Fourier method)
result_ref = process_spectrum_reference(...)

# Experimental (e.g., argmin method)
result_exp = process_spectrum_with_argmin(...)

# Compare accuracy and stability
accuracy_diff = abs(result_ref['resonance_wavelength'] -
                   result_exp['resonance_wavelength'])
```

### Case 3: Testing Window Size
```python
# Reference (window=165)
result_ref = process_spectrum_reference(
    ...,
    window_size=165
)

# Experimental (window=1500)
result_exp = process_spectrum_reference(
    ...,
    window_size=1500  # Optimized
)

# Compare stability
```

---

## 📚 Full Documentation

For complete details:
- **Implementation**: `src/utils/reference_baseline_processing.py`
- **Tests**: `test_reference_baseline.py`
- **Complete guide**: `REFERENCE_BASELINE_METHOD_COMPLETE.md`

---

## 🆘 Troubleshooting

### Reference doesn't match production?
1. Run `python test_reference_baseline.py`
2. Check Fourier weights calculation
3. Verify REFERENCE_PARAMETERS values

### High P2P variation?
1. Check num_scans ≥ 3
2. Verify dark noise quality
3. Check LED correction factors
4. Test reference spectrum stability

### Wrong resonance wavelength?
1. Verify LED intensities (P=220, S=80 typical)
2. Check wavelength calibration
3. Ensure spectrum trimming is correct
4. Validate Fourier weights calculation

---

## 💡 Quick Tips

- **Always calculate Fourier weights once** and reuse (expensive calculation)
- **Use same num_scans** for calibration and live data
- **LED correction is critical** - don't skip it!
- **Denoise AFTER transmission** calculation, not before
- **Window=165 is proven stable** - test 1500 for optimization

---

## 🎓 Key Insights

1. **P/S division cancels correlated noise** → Denoise after division
2. **LED correction normalizes intensity** → Transmission = (P/S) × (S_LED/P_LED) × 100
3. **Fourier method is industry standard** → Same algorithm as Phase Photonics
4. **Hardware averaging reduces noise by √N** → 3 scans = 1.73× reduction

---

**Ready to use? Import and go!**

```python
from utils.reference_baseline_processing import (
    process_spectrum_reference,
    REFERENCE_PARAMETERS
)

# Your code here...
```
