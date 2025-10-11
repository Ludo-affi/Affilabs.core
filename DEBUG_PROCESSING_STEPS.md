# Debug Processing Steps - Post-Processing Visualization

**Status:** ✅ Complete and Active
**Date:** October 10, 2025

## Overview

The SPR control system now automatically saves intermediate data at each processing step during live acquisition. This allows you to inspect the raw spectrum and see exactly how it's transformed through each calibration and processing stage.

## Saved Data Steps

For each acquisition cycle, the system saves 4 data files:

### 1. **Raw Spectrum** (`1_raw_spectrum`)
- **Description:** Pure detector output before any processing
- **Units:** Counts
- **What it shows:** Unmodified spectrum from USB4000 detector
- **Size:** 3648 pixels (full detector) OR 1591 pixels (if spectral filtering applied)

### 2. **After Dark Noise Correction** (`2_after_dark_correction`)
- **Description:** P-polarization spectrum with dark noise subtracted
- **Units:** Counts (dark-corrected)
- **Processing:** `Raw - Dark_Noise`
- **What it shows:** Clean P-pol signal ready for calibration

### 3. **S-Mode Reference (Corrected)** (`3_s_reference_corrected`)
- **Description:** S-polarization calibration reference
- **Units:** Counts (dark-corrected)
- **Processing:** `S_Reference - Dark_Noise`
- **What it shows:** What the P-pol data is divided by to get transmittance

### 4. **Final Transmittance** (`4_final_transmittance`)
- **Description:** Complete processed spectrum (what you see in the GUI)
- **Units:** Transmittance (%)
- **Processing:**
  ```
  1. (P - Dark) / (S - Dark) × 100%
  2. Savitzky-Golay denoising (11-point window, cubic)
  ```
- **What it shows:** Final SPR transmittance spectrum ready for peak finding

## File Format

Files are saved as compressed NumPy archives (`.npz`):

```
Filename format: ch{channel}_{step_name}_{timestamp}_{counter:04d}.npz

Example: cha_4_final_transmittance_20251010_182530_0042.npz
```

Each file contains:
- `wavelengths`: Wavelength array (nm)
- `spectrum`: Intensity/transmittance data
- `channel`: Channel ID ('a', 'b', 'c', 'd')
- `step`: Processing step name
- `timestamp`: When data was acquired
- `counter`: Sequential counter for matching related files

## Storage Location

```
control-3.2.9/
└── generated-files/
    └── debug_processing_steps/
        ├── cha_1_raw_spectrum_20251010_182530_0042.npz
        ├── cha_2_after_dark_correction_20251010_182530_0042.npz
        ├── cha_3_s_reference_corrected_20251010_182530_0042.npz
        └── cha_4_final_transmittance_20251010_182530_0042.npz
```

## Viewing Debug Data

### Quick View Script

Run the viewer to see the most recent processing steps:

```bash
python view_debug_steps.py [channel]
```

**Examples:**
```bash
python view_debug_steps.py        # View channel A (default)
python view_debug_steps.py c      # View channel C
```

### Manual Loading

Load data in Python:

```python
import numpy as np

# Load specific file
data = np.load('generated-files/debug_processing_steps/cha_1_raw_spectrum_20251010_182530_0042.npz')

wavelengths = data['wavelengths']
spectrum = data['spectrum']
channel = str(data['channel'])
step = str(data['step'])
```

## Enable/Disable Debug Saving

Edit `utils/spr_data_acquisition.py`:

```python
# Line 19
SAVE_DEBUG_DATA = True   # Enable (default)
SAVE_DEBUG_DATA = False  # Disable
```

## Use Cases

### 1. **Verify Calibration Quality**
Compare raw spectrum to S-reference to ensure proper LED intensity and clean baseline.

### 2. **Diagnose Noise Issues**
Check if noise is in raw data, introduced by dark correction, or amplified in transmittance calculation.

### 3. **Validate Denoising**
See before/after effect of Savitzky-Golay filter on transmittance spectrum.

### 4. **Troubleshoot Odd Spectra**
When spectrum "looks odd", trace back through processing steps to find where issue originates.

### 5. **Algorithm Development**
Test new processing algorithms by loading saved raw data and comparing outputs.

## Processing Pipeline

```
┌─────────────────────┐
│  USB4000 Detector   │
│  (3648 pixels)      │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ Spectral     │  (Optional: 3648 → 1591 pixels)
    │ Filtering    │  Filter to 580-720 nm SPR range
    └──────┬───────┘
           │
           ▼
    [1. RAW SPECTRUM] ◄─── SAVED
           │
           ▼
    ┌──────────────┐
    │ Dark Noise   │  Subtract detector dark current
    │ Subtraction  │  P_corrected = P_raw - Dark
    └──────┬───────┘
           │
           ▼
    [2. AFTER DARK CORRECTION] ◄─── SAVED
           │
           ├──────────────────────┐
           │                      │
           ▼                      ▼
    ┌──────────────┐      [3. S-REFERENCE] ◄─── SAVED
    │ Transmittance│      (S_corrected = S_raw - Dark)
    │ Calculation  │
    │ T = P / S    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Savitzky-    │  11-point window, cubic polynomial
    │ Golay Filter │  Denoise transmittance spectrum
    └──────┬───────┘
           │
           ▼
    [4. FINAL TRANSMITTANCE] ◄─── SAVED
           │
           ▼
    ┌──────────────┐
    │ Peak Finding │  Derivative method, find λ_SPR
    │ & Sensorgram │
    └──────────────┘
```

## Performance Impact

- **Minimal:** File I/O is asynchronous and takes ~5-10ms per save
- **Storage:** ~100 KB per complete cycle (4 files)
- **No impact on acquisition rate:** Saving happens after data is already processed

## Data Retention

Debug files accumulate over time. To manage storage:

```bash
# View total size
dir generated-files\debug_processing_steps

# Clean old debug files (keep last 100 cycles)
# Manual cleanup - delete older files as needed
```

## Example Analysis Workflow

1. **Start acquisition** - Debug files saved automatically
2. **Notice odd spectrum** in GUI
3. **Stop acquisition**
4. **Run viewer:**
   ```bash
   python view_debug_steps.py a
   ```
5. **Inspect each step:**
   - Is raw spectrum noisy? → Check detector/LED
   - Is dark correction too aggressive? → Recalibrate dark noise
   - Is S-reference stable? → Check S-mode calibration
   - Does denoising help? → Adjust window size if needed

## Technical Notes

- **Thread-safe:** Saving uses file locking (implicit via `.npz`)
- **Counter synchronization:** All 4 files for same cycle share same counter
- **Memory efficient:** Data copied only for save, no extra RAM usage
- **Error handling:** Save failures logged but don't interrupt acquisition

## Future Enhancements

Possible additions:
- [ ] Automatic cleanup of old debug files (keep last N)
- [ ] Real-time plotting during acquisition
- [ ] Export to CSV for external analysis
- [ ] Comparison mode (overlay multiple cycles)
- [ ] Statistics across multiple cycles

---

**Implementation Location:**
- Saving logic: `utils/spr_data_acquisition.py` (lines 120-150, 355-390)
- Viewer script: `view_debug_steps.py`
- Enable flag: `SAVE_DEBUG_DATA` (line 19 of spr_data_acquisition.py)
