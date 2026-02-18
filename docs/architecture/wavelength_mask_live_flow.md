# Wavelength Mask Application in Live Data - Complete Flow

## Overview
This document explains **exactly** how the wavelength mask (570-720nm for Phase Photonics, 560-720nm for Ocean Optics) is applied during live data acquisition, processing, and display.

---

## 1. DETECTOR INITIALIZATION (Startup)

### 1.1 Hardware Detection
**Location**: [main.py](main.py#L2690-L2720)

```python
# Get detector serial number from hardware
detector = self.hardware_mgr.usb
detector_serial = getattr(detector, 'serial_number', None)  # e.g., "ST00012" for Phase Photonics
```

**Phase Photonics Detection**:
- Serial starts with `"ST"` → `detector_type = "PhasePhotonics"`
- Example: `ST00012` = Phase Photonics ST series

**Ocean Optics Detection**:
- Serial contains `"USB4"` or `"FLMT"` → `detector_type = "USB4000"`
- Example: `USB4H14526` = Ocean Optics USB4000

---

### 1.2 Propagate Detector Info to Processing Components

**Spectrum Processor** ([spectrum_viewmodel.py](affilabs/viewmodels/spectrum_viewmodel.py)):
```python
# Update spectrum processor with detector info for peak finding
vm._spectrum_processor.set_detector_info(detector_serial=detector_serial)
```

**Spectroscopy Presenter** ([spectroscopy_presenter.py](affilabs/presenters/spectroscopy_presenter.py)):
```python
# Update presenter with detector info for plot filtering
self.spectroscopy_presenter.set_detector_info(detector_serial)
```

**Result**: Both components now know:
- `detector_serial = "ST00012"` (Phase Photonics)
- `detector_type = "PhasePhotonics"`

---

## 2. WAVELENGTH CALIBRATION (From EEPROM)

**Location**: Detector EEPROM stores wavelength calibration coefficients

**Phase Photonics ST00012**:
- **Pixels**: 1848
- **ADC**: 12-bit (0-4095 counts)
- **Wavelength range**: 563.0 - 720.0 nm (full detector range)
- **Resolution**: 0.085 nm/pixel

**Wavelength Array** (full detector):
```
wavelengths[0] = 563.0 nm      (noisy, unusable)
wavelengths[500] = 605.5 nm    (start of valid data)
wavelengths[1000] = 648.0 nm   (mid-range)
wavelengths[1847] = 720.0 nm   (end)
```

**Critical**: At this point, the wavelength array contains **ALL pixels** including the noisy region below 570nm.

---

## 3. LIVE DATA ACQUISITION (1 Hz Loop)

### 3.1 Raw Spectrum Capture
**Location**: [data_acquisition_manager.py](affilabs/core/data_acquisition_manager.py#L715-L1100)

```python
# Acquire raw spectrum from detector (FULL wavelength range, 1848 pixels)
raw_spectrum = detector.get_spectrum()  # Shape: (1848,)
```

**Data at this point**:
- `wavelengths`: [563.0, 563.085, 563.17, ..., 720.0] nm (1848 points)
- `raw_spectrum`: [120, 115, 98, ..., 3200] counts (includes noisy region < 570nm)

---

### 3.2 Dark Subtraction
**Location**: [spectrum_preprocessor.py](affilabs/core/spectrum_preprocessor.py#L34-L104)

```python
# Remove dark noise (BEFORE wavelength filtering)
clean_spectrum = raw_spectrum - dark_noise  # Still full wavelength range
```

**Result**: Dark-subtracted but still contains all wavelengths (563-720nm).

---

### 3.3 Transmission Calculation
**Location**: [spectrum_viewmodel.py](affilabs/viewmodels/spectrum_viewmodel.py#L142-L170)

```python
# Calculate transmission: 100 × (P_clean / S_ref)
transmission = self._transmission_calculator.calculate(
    p_spectrum=p_spectrum_clean,  # Shape: (1848,)
    s_reference=s_reference,      # Shape: (1848,)
    p_led_intensity=p_led_intensity,
    s_led_intensity=s_led_intensity,
)
```

**Result**: Transmission spectrum (still full 1848 points, 563-720nm).

---

## 4. WAVELENGTH FILTERING FOR PEAK FINDING

### 4.1 Get Valid SPR Range
**Location**: [detector_config.py](affilabs/utils/detector_config.py#L100-L124)

```python
def get_spr_wavelength_range(detector_serial, detector_type):
    """
    Returns detector-specific valid wavelength range:
    - Phase Photonics (ST*): 570.0 - 720.0 nm
    - Ocean Optics (USB4*): 560.0 - 720.0 nm
    """
    if detector_serial and detector_serial.startswith("ST"):
        return (570.0, 720.0)  # Phase Photonics
    elif "PHASE" in str(detector_type).upper() or "ST" in str(detector_type).upper():
        return (570.0, 720.0)
    else:
        return (560.0, 720.0)  # Ocean Optics default
```

**For Phase Photonics ST00012**:
- `spr_min = 570.0 nm`
- `spr_max = 720.0 nm`

---

### 4.2 Apply Mask in Fourier Pipeline
**Location**: [fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py#L126-L150)

```python
# CRITICAL: Work ONLY on SPR region - detector-specific range
spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)

# Create boolean mask
spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)

# Extract SPR region only (FILTERS OUT <570nm data)
spr_wavelengths = wavelengths[spr_mask]      # [570.0, 570.085, ..., 720.0]
spr_transmission = transmission[spr_mask]     # ~1765 points (filtered from 1848)
spr_s_reference = s_reference[spr_mask]       # Match filtered region
```

**Before Filtering**:
```
wavelengths: [563.0, 563.085, ..., 569.915, 570.0, ..., 720.0]  (1848 pts)
             └──────────────────┘ └──────────────────────────┘
                  NOISY (83 pts)        VALID (1765 pts)
```

**After Filtering**:
```
spr_wavelengths: [570.0, 570.085, ..., 720.0]  (1765 pts)
                 └──────────────────────────┘
                      VALID ONLY
```

---

### 4.3 Peak Finding on Filtered Data
**Location**: [fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py#L152-L276)

```python
# 1. Apply SNR weighting (using filtered S-reference)
snr_weights = self._calculate_snr_weights(spr_s_reference, snr_strength=0.3)
spectrum = spr_transmission * snr_weights

# 2. Find minimum hint
hint_index = np.argmin(spectrum)  # Within filtered region only

# 3. Apply Fourier transform
D_k = dst(spectrum * fourier_weights, type=1)  # Discrete Sine Transform

# 4. Zero-crossing detection
derivative = idct(k * D_k, type=1)  # Inverse Cosine Transform
zero_idx = find_zero_crossing(derivative, hint_index)

# 5. Linear regression refinement (CRITICAL: uses window_size=85 for Phase Photonics)
peak_wavelength = refine_with_linear_regression(
    spr_wavelengths,  # FILTERED wavelengths only
    spectrum,
    zero_idx,
    window_size=85  # 85 × 0.085 nm = 7.2 nm physical window
)
```

**Result**: Peak wavelength from **FILTERED data only** (570-720nm).

**Example Output**:
```
resonance_wavelength = 632.45 nm  (within valid 570-720nm range)
```

---

## 5. WAVELENGTH FILTERING FOR DISPLAY

### 5.1 Filter Before Plotting (Live Spectroscopy Tab)
**Location**: [spectroscopy_presenter.py](affilabs/presenters/spectroscopy_presenter.py#L125-L135)

```python
# CRITICAL: Filter out invalid wavelength data BEFORE plotting
filtered_wavelengths, filtered_transmission = filter_valid_wavelength_data(
    wavelengths,      # [563.0, ..., 720.0] (1848 pts)
    transmission,     # Full transmission array
    detector_serial=self._detector_serial,  # "ST00012"
    detector_type=self._detector_type,      # "PhasePhotonics"
)

# Update plot with FILTERED data only
self.main_window.transmission_curves[channel_idx].setData(
    filtered_wavelengths,   # [570.0, ..., 720.0] (1765 pts)
    filtered_transmission,  # Filtered transmission
)
```

---

### 5.2 Filter Implementation
**Location**: [detector_config.py](affilabs/utils/detector_config.py#L125-L160)

```python
def filter_valid_wavelength_data(wavelengths, data, detector_serial=None, detector_type=None):
    """
    Filter wavelength data to valid SPR region.

    Phase Photonics: wavelengths >= 570.0 nm (noisy below this)
    Ocean Optics: wavelengths >= 560.0 nm
    """
    # Get valid wavelength range
    valid_min, valid_max = get_spr_wavelength_range(detector_serial, detector_type)

    # Create boolean mask (Phase Photonics: wavelengths >= 570.0)
    valid_mask = wavelengths >= valid_min

    # Return filtered arrays
    return wavelengths[valid_mask], data[valid_mask]
```

**Example for Phase Photonics**:
```python
# Input
wavelengths = [563.0, 563.085, ..., 569.915, 570.0, ..., 720.0]  # 1848 points
transmission = [2.5, 3.1, ..., 8.2, 12.4, ..., 95.3]  # Full transmission

# Mask creation
valid_min = 570.0  # Phase Photonics threshold
valid_mask = wavelengths >= 570.0  # Boolean: [False, False, ..., False, True, ..., True]

# Output
filtered_wavelengths = [570.0, 570.085, ..., 720.0]  # 1765 points
filtered_transmission = [12.4, 12.5, ..., 95.3]      # Filtered transmission
```

---

## 6. COMPLETE DATA FLOW SUMMARY

### Live Acquisition Flow (Phase Photonics ST00012):

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. HARDWARE ACQUISITION (1 Hz)                                   │
│    Detector → Raw spectrum (1848 pixels, 563-720nm)              │
│    wavelengths: [563.0, ..., 720.0]                              │
│    raw_spectrum: [120, ..., 3200] counts                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. DARK SUBTRACTION (spectrum_preprocessor.py)                   │
│    clean_spectrum = raw_spectrum - dark_noise                    │
│    Still full range: 1848 points (563-720nm)                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. TRANSMISSION CALCULATION (spectrum_viewmodel.py)              │
│    transmission = 100 × (P_clean / S_ref)                        │
│    Still full range: 1848 points (563-720nm)                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ├──────────────────┬─────────────────┐
                             ▼                  ▼                 ▼
┌──────────────────────┐ ┌──────────────────────────────┐ ┌────────────────────┐
│ 4A. PEAK FINDING     │ │ 4B. LIVE PLOT (Spectroscopy) │ │ 4C. RAW SPECTRUM   │
│ (fourier_pipeline.py)│ │ (spectroscopy_presenter.py)  │ │ (spectroscopy      │
│                      │ │                              │ │  _presenter.py)    │
├──────────────────────┤ ├──────────────────────────────┤ ├────────────────────┤
│ ✓ Get SPR range:     │ │ ✓ Get SPR range:             │ │ ✓ Get SPR range:   │
│   570.0-720.0 nm     │ │   570.0-720.0 nm             │ │   570.0-720.0 nm   │
│                      │ │                              │ │                    │
│ ✓ Create mask:       │ │ ✓ Create mask:               │ │ ✓ Create mask:     │
│   wavelengths ≥ 570  │ │   wavelengths ≥ 570          │ │   wavelengths ≥ 570│
│                      │ │                              │ │                    │
│ ✓ Filter data:       │ │ ✓ Filter data:               │ │ ✓ Filter data:     │
│   1765 pts (filtered)│ │   1765 pts (filtered)        │ │   1765 pts         │
│                      │ │                              │ │                    │
│ ✓ Fourier transform  │ │ ✓ Plot filtered data         │ │ ✓ Plot filtered    │
│   on filtered data   │ │   [570-720nm only]           │ │   raw intensities  │
│                      │ │                              │ │   [570-720nm only] │
│ ✓ Find peak:         │ │                              │ │                    │
│   632.45 nm          │ │                              │ │                    │
└──────────────────────┘ └──────────────────────────────┘ └────────────────────┘
```

---

## 7. KEY DIFFERENCES: FULL vs FILTERED DATA

### Phase Photonics ST00012 Example:

| Stage | Wavelength Range | Points | Notes |
|-------|------------------|--------|-------|
| **Hardware Read** | 563.0 - 720.0 nm | 1848 | Full detector range |
| **Dark Subtraction** | 563.0 - 720.0 nm | 1848 | Still unfiltered |
| **Transmission Calc** | 563.0 - 720.0 nm | 1848 | Still unfiltered |
| **Peak Finding Input** | 563.0 - 720.0 nm | 1848 | **Before filter** |
| **Peak Finding Processing** | **570.0 - 720.0 nm** | **1765** | **✓ FILTERED** |
| **Live Plot Display** | **570.0 - 720.0 nm** | **1765** | **✓ FILTERED** |
| **Raw Plot Display** | **570.0 - 720.0 nm** | **1765** | **✓ FILTERED** |

**CRITICAL**: The 563-570nm region (83 pixels) is:
1. ✓ Acquired from hardware
2. ✓ Dark-subtracted
3. ✓ Used in transmission calculation
4. ✗ **EXCLUDED from peak finding** (Fourier pipeline filters it out)
5. ✗ **EXCLUDED from live plots** (spectroscopy_presenter filters it out)

---

## 8. WHY FILTER AT 570nm for Phase Photonics?

### Problem: Noisy Data Below 570nm

**Phase Photonics ST00012 characteristics**:
- 12-bit ADC (0-4095 counts)
- Lower light intensity at shorter wavelengths
- Noisy signal below 570nm

**Example Data (563-570nm region)**:
```
Wavelength (nm)  |  Raw Counts  |  S-ref  |  Transmission
─────────────────┼──────────────┼─────────┼──────────────
563.0            |     120      |   450   |    26.7%
565.0            |     115      |   480   |    24.0%
567.0            |     98       |   490   |    20.0%
569.0            |     105      |   510   |    20.6%
570.0            |     380      |  1200   |    31.7%   ← Valid data starts
572.0            |     420      |  1350   |    31.1%
```

**Impact if NOT filtered**:
- Fourier transform sees artificial edges at 563nm boundary
- False peaks detected in noisy region
- Peak finding fails or gives incorrect wavelength
- Plots show unreliable data (confuses user)

---

## 9. COMPARISON: QC Dialog vs Live Spectroscopy Tab

### QC Dialog (Calibration Quality Check)
**Location**: [calibration_qc_dialog.py](affilabs/ui/calibration_qc_dialog.py#L1589-L1680)

**Data Source**:
```python
# Uses CALIBRATION data (saved during calibration)
wavelengths = result.wavelengths  # From calibration result
s_ref = result.s_ref[channel]     # S-pol reference from calibration
p_data = result.p_data[channel]   # P-pol data from calibration
```

**Filtering**:
```python
# Same filtering function, same detector detection
filtered_wavelengths, filtered_s_ref = filter_valid_wavelength_data(
    wavelengths,
    s_ref,
    detector_serial=result.detector_serial,  # From calibration metadata
    detector_type=None
)
```

**Purpose**: Show calibration quality (static data from calibration session).

---

### Live Spectroscopy Tab
**Location**: [spectroscopy_presenter.py](affilabs/presenters/spectroscopy_presenter.py#L125-L135)

**Data Source**:
```python
# Uses LIVE acquisition data (real-time from detector)
wavelengths = current_wavelengths  # From live detector read
transmission = current_transmission  # From live P/S calculation
```

**Filtering**:
```python
# Same filtering function, detector info from main.py
filtered_wavelengths, filtered_transmission = filter_valid_wavelength_data(
    wavelengths,
    transmission,
    detector_serial=self._detector_serial,  # Set during initialization
    detector_type=self._detector_type
)
```

**Purpose**: Show live real-time data (dynamic, updates at 1 Hz).

---

### Key Difference

| Aspect | QC Dialog | Live Spectroscopy Tab |
|--------|-----------|----------------------|
| **Data Source** | Calibration result (saved) | Live acquisition (real-time) |
| **Update Rate** | Static (once) | Dynamic (1 Hz) |
| **Detector Info** | From calibration metadata | From hardware manager |
| **Filtering** | Same function (`filter_valid_wavelength_data`) | Same function |
| **Wavelength Range** | Same (570-720nm for Phase Photonics) | Same (570-720nm) |

**Filtering is identical** - difference is only the data source (calibration vs live).

---

## 10. VALIDATION: How to Verify Filtering

### Test 1: Check Live Plot Range
```python
# In spectroscopy_presenter.py, enable debug logging:
logger.info(f"Before filter: {len(wavelengths)} pts, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm")
# Output: Before filter: 1848 pts, 563.0-720.0nm

logger.info(f"After filter: {len(filtered_wavelengths)} pts, {filtered_wavelengths[0]:.1f}-{filtered_wavelengths[-1]:.1f}nm")
# Output: After filter: 1765 pts, 570.0-720.0nm
```

---

### Test 2: Check Peak Finding Range
```python
# In fourier_pipeline.py, check SPR mask:
spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)
logger.info(f"SPR range: {spr_min}-{spr_max}nm for detector {detector_serial}")
# Output: SPR range: 570.0-720.0nm for detector ST00012

logger.info(f"Filtered to {len(spr_wavelengths)} points from {len(wavelengths)}")
# Output: Filtered to 1765 points from 1848
```

---

### Test 3: Compare Excel Data vs Live Display
```python
# Excel file: baseline_recording_20260126_235959.xlsx
# Contains FULL wavelength range (all 1848 points, 563-720nm)

# Live plot: Should show only 570-720nm (1765 points)

import pandas as pd
df = pd.read_excel("baseline_recording_20260126_235959.xlsx", sheet_name="Ch_D_P")
print(f"Excel wavelengths: {df.columns[0]}-{df.columns[-1]} nm, {len(df.columns)} points")
# Output: Excel wavelengths: 563.0-720.0 nm, 1848 points

# Live plot x-axis should show: 570.0-720.0 nm
```

---

## 11. SUMMARY: Wavelength Mask Application Points

### WHERE filtering happens:

1. **Peak Finding** ([fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py#L126-L150))
   - ✓ Filters to SPR range (570-720nm for Phase Photonics)
   - ✓ Applies mask BEFORE Fourier transform
   - ✓ Prevents noisy data from affecting peak detection

2. **Live Transmission Plot** ([spectroscopy_presenter.py](affilabs/presenters/spectroscopy_presenter.py#L125-L135))
   - ✓ Filters BEFORE plotting
   - ✓ Only shows valid wavelength range
   - ✓ Prevents confusing user with noisy data

3. **Live Raw Spectrum Plot** ([spectroscopy_presenter.py](affilabs/presenters/spectroscopy_presenter.py#L189-L195))
   - ✓ Filters BEFORE plotting
   - ✓ Only shows valid wavelength range
   - ✓ Consistent with transmission plot

4. **QC Dialog Plots** ([calibration_qc_dialog.py](affilabs/ui/calibration_qc_dialog.py#L1589-L1680))
   - ✓ Filters calibration data BEFORE plotting
   - ✓ Same wavelength range as live plots
   - ✓ Shows calibration quality without artifacts

---

### WHEN filtering happens:

```
Acquisition (1 Hz) → Dark Sub → Transmission Calc → FILTER → Peak Finding
                                                   ↓
                                                   └─→ FILTER → Live Plots
```

**CRITICAL**: Filtering happens **AFTER** transmission calculation but **BEFORE** peak finding and display.

---

### WHY Phase Photonics needs 570nm cutoff:

- 12-bit ADC (vs 16-bit Ocean Optics)
- Lower signal below 570nm
- Noisy data causes artifacts
- **Solution**: Filter to valid range (570-720nm)

---

## 12. DETECTOR-SPECIFIC RANGES

| Detector | Serial Pattern | Valid Range | Pixels (filtered) | Resolution |
|----------|----------------|-------------|-------------------|------------|
| Phase Photonics ST | `ST*` | **570.0 - 720.0 nm** | ~1765 / 1848 | 0.085 nm/px |
| Ocean Optics USB4000 | `USB4*`, `FLMT*` | **560.0 - 720.0 nm** | ~3636 / 3648 | 0.044 nm/px |

**Auto-detection**: Based on serial number prefix (`ST*` = Phase Photonics).

---

## END OF DOCUMENT

**Author**: Affilabs.core Team
**Date**: 2025-01-27
**Detector**: Phase Photonics ST00012
**Valid Wavelength Range**: 570.0 - 720.0 nm
