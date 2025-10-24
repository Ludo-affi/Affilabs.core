# Full Device Dataset Collection - Quick Reference

## What Changed

### 1. ✅ Modified Afterglow Script
**File:** `led_afterglow_integration_time_model.py`

**New feature:** `--mode` argument to explicitly set polarizer position

**Usage:**
```bash
# S-mode afterglow
.\.venv312\Scripts\python.exe led_afterglow_integration_time_model.py --mode S

# P-mode afterglow
.\.venv312\Scripts\python.exe led_afterglow_integration_time_model.py --mode P
```

**Changes:**
- Added `argparse` for CLI argument parsing
- Added `--mode S|P` required argument
- Sets polarizer position explicitly via `ctrl.set_polarizer_mode()`
- Adds polarizer_mode to results metadata
- Updates output filename: `led_afterglow_integration_time_models_{MODE}mode_{TIMESTAMP}.json`

### 2. ✅ Recommended Collection Duration
**Changed from:** 5 minutes (1200 spectra @ 4 Hz)
**Changed to:** 15 minutes (3600 spectra @ 4 Hz)

**Rationale:**
- Better statistical coverage for ML training
- Captures thermal drift patterns
- Shows long-term stability characteristics
- Still manageable total time (60 min per mode)

**How to use:**
```bash
# 15 minute collection
.\.venv312\Scripts\python.exe collect_spectral_data.py --mode S --duration 900 --device-serial "demo P4SPR 2.0" --sensor-quality "used"
```

### 3. ✅ Batch Collection Script
**File:** `collect_full_device_dataset.bat`

**Automates complete device characterization:**
1. S-mode spectral data (15 min/channel = 60 min)
2. S-mode afterglow characterization (~45 min)
3. P-mode spectral data (15 min/channel = 60 min)
4. P-mode afterglow characterization (~45 min)

**Total time:** ~3.5 hours per device

**Usage:**
```bash
collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
```

**Features:**
- Sequential automated execution
- Error handling (stops on failure)
- Progress timestamps
- Completion summary

---

## Why Collect Afterglow in Both Modes?

### Physics Reasoning

**LED Afterglow:**
- Source: Phosphor decay (unpolarized emission)
- Time constant (τ): ~0.5-2 ms (physics of phosphor material)
- **τ should be same in S and P modes** (same LED, same phosphor)

**Polarizer Effect:**
- Blocks ~50% of unpolarized light in both primary signal AND afterglow
- S-mode: No sensor resonance → higher baseline signal
- P-mode: Sensor resonance → different signal amplitude

**Key Insight:**
- **Afterglow amplitude scales with signal level**
- Different signal levels in S vs P → different afterglow amplitudes
- **Need polarization-specific correction for accuracy!**

### Measurement Strategy

**Option 1: Full characterization (implemented)**
- Collect afterglow in both S and P modes
- ~45 min per mode
- Complete amplitude + τ data for each polarization state

**Option 2: Fast approximation (alternative)**
- Collect S-mode afterglow only
- Assume τ is polarization-independent (physics says yes)
- Scale amplitude based on S vs P signal ratio
- Faster (~45 min instead of 90 min) but less accurate

**Recommendation:** Use Option 1 (full characterization) for first device, then evaluate if Option 2 sufficient.

---

## Complete Workflow

### Current Status
Your S-mode collection is running (~280 spectra collected on Channel D at 4.0 Hz).

### Next Steps

**Option A: Complete current run, then full workflow**
1. ✅ Let current S-mode (5 min) finish
2. Run full batch script with 15 min duration for next dataset

**Option B: Restart with optimized workflow**
1. Stop current collection (Ctrl+C)
2. Run batch script immediately with 15 min duration

### Batch Script Execution

```bash
# Full automated collection
collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
```

**What happens:**
```
[00:00] Starting S-mode spectral collection...
[01:00] Channel A complete (3600 spectra @ 4 Hz)
[01:15] Channel B complete (3600 spectra @ 4 Hz)
[01:30] Channel C complete (3600 spectra @ 4 Hz)
[01:45] Channel D complete (3600 spectra @ 4 Hz)
[02:00] S-mode spectral collection complete

[02:00] Starting S-mode afterglow characterization...
[02:45] S-mode afterglow complete (20 measurements)

[02:45] Starting P-mode spectral collection...
[03:45] P-mode spectral collection complete

[03:45] Starting P-mode afterglow characterization...
[04:30] P-mode afterglow complete

[04:30] FULL DATASET COMPLETE!
```

---

## Expected Output Structure

```
spectral_training_data/
└── demo P4SPR 2.0/
    ├── s/
    │   └── used/
    │       └── 20251022_HHMMSS/
    │           ├── channel_A.npz (3600 spectra)
    │           ├── channel_B.npz (3600 spectra)
    │           ├── channel_C.npz (3600 spectra)
    │           ├── channel_D.npz (3600 spectra)
    │           ├── metadata.json
    │           └── summary.json
    │
    └── p/
        └── used/
            └── 20251022_HHMMSS/
                ├── channel_A.npz (3600 spectra)
                ├── channel_B.npz (3600 spectra)
                ├── channel_C.npz (3600 spectra)
                ├── channel_D.npz (3600 spectra)
                ├── metadata.json
                └── summary.json

generated-files/characterization/
├── led_afterglow_integration_time_models_Smode_20251022_HHMMSS.json
├── led_afterglow_integration_time_models_Pmode_20251022_HHMMSS.json
└── led_afterglow_integration_time_analysis.png
```

**Total data per device:** ~150-200 MB
- S-mode spectra: ~50 MB
- P-mode spectra: ~50 MB
- Afterglow data: ~2 MB
- Future physics/processing: ~50 MB

---

## After Collection

### Organize Data
Copy afterglow results into device folder:
```powershell
# Create structure
New-Item -ItemType Directory -Path "spectral_training_data\demo P4SPR 2.0\afterglow\s" -Force
New-Item -ItemType Directory -Path "spectral_training_data\demo P4SPR 2.0\afterglow\p" -Force

# Copy S-mode afterglow
Copy-Item "generated-files\characterization\*Smode*.json" "spectral_training_data\demo P4SPR 2.0\afterglow\s\"
Copy-Item "generated-files\characterization\*Smode*.png" "spectral_training_data\demo P4SPR 2.0\afterglow\s\"

# Copy P-mode afterglow
Copy-Item "generated-files\characterization\*Pmode*.json" "spectral_training_data\demo P4SPR 2.0\afterglow\p\"
Copy-Item "generated-files\characterization\*Pmode*.png" "spectral_training_data\demo P4SPR 2.0\afterglow\p\"
```

### Offline Processing
1. Calculate wavelength arrays from calibration
2. Compute transmittance spectra (T = signal / reference)
3. Generate full sensorgram time-series
4. Test different processing pipelines
5. Train ML models on production-matched data

### Repeat for Second Device
```bash
# New unsealed sensor
collect_full_device_dataset.bat "NEW_DEVICE_SERIAL" "new"
```

---

## Quick Start

**To start full collection right now:**
```bash
collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
```

**To test individual steps:**
```bash
# S-mode spectral only (15 min)
.\.venv312\Scripts\python.exe collect_spectral_data.py --mode S --duration 900 --device-serial "demo P4SPR 2.0" --sensor-quality "used"

# S-mode afterglow only (~45 min)
.\.venv312\Scripts\python.exe led_afterglow_integration_time_model.py --mode S
```
