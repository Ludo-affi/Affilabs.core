# Device-Specific ML Training Dataset Organization Plan

## Philosophy
Create comprehensive, device-specific datasets containing:
1. **Raw spectral data** (S-mode and P-mode at 4 Hz - production-matched timing)
2. **Afterglow characterization** (LED afterglow models for all channels)
3. **Physics parameters** (calculated offline for algorithm validation)
4. **Processing pipeline tests** (various denoising, filtering, calibration approaches)

This enables:
- ML training on production-representative data
- Offline optimization of signal processing
- Cross-device comparison (used sensor vs new unsealed sensor)
- Algorithm validation before deployment

---

## Target Folder Structure

```
spectral_training_data/
└── demo P4SPR 2.0/                    # Device serial number
    ├── device_info.json               # Sensor type, quality, etc.
    │
    ├── s/                             # S-signal (no sensor resonance)
    │   └── used/                      # Sensor quality
    │       └── 20251022_HHMMSS/       # Collection timestamp
    │           ├── channel_A.npz      # Spectra arrays
    │           ├── channel_B.npz
    │           ├── channel_C.npz
    │           ├── channel_D.npz
    │           ├── metadata.json      # Collection parameters
    │           └── summary.json       # Statistics
    │
    ├── p/                             # P-signal (sensor resonance)
    │   └── used/
    │       └── 20251022_HHMMSS/
    │           ├── (same as S-mode)
    │
    ├── afterglow/                     # LED afterglow characterization
    │   ├── led_afterglow_integration_time_models_TIMESTAMP.json
    │   ├── led_afterglow_integration_time_analysis.png
    │   ├── led_afterglow_all_channels.png
    │   ├── led_afterglow_model.png
    │   ├── led_afterglow_validation.png
    │   └── README.md                  # Describes afterglow data
    │
    ├── physics/                       # Calculated physics (offline)
    │   ├── wavelength_calibration.npz # Per-channel wavelength arrays
    │   ├── dark_correction.npz        # Dark spectra characterization
    │   ├── transmittance.npz          # T = signal / reference per channel
    │   ├── sensorgram.npz             # Full time-series sensorgram
    │   └── README.md                  # Calculation methods
    │
    ├── processed/                     # Various processing tests
    │   ├── denoising_comparison/      # Different denoising approaches
    │   ├── spectral_filtering/        # Filter size variations
    │   ├── calibration_methods/       # Different calibration algorithms
    │   └── README.md                  # Processing experiments
    │
    └── README.md                      # Device dataset overview
```

---

## Copy Operations Needed

### 1. Afterglow Data (from `generated-files/characterization/`)
**Source files:**
- `led_afterglow_integration_time_models_20251021_170728.json` (29.9 KB)
- `led_afterglow_integration_time_analysis.png` (249.4 KB)
- `led_afterglow_all_channels_20251011_195607.json` (58.1 KB)
- `led_afterglow_all_channels.png` (196.3 KB)
- `led_afterglow_model_20251011_195256.json` (13.5 KB)
- `led_afterglow_model.png` (206.7 KB)
- `led_afterglow_validation_20251011_205019.json` (14.8 KB)
- `led_afterglow_validation.png` (349.7 KB)

**Target:** `spectral_training_data/demo P4SPR 2.0/afterglow/`

**Total:** ~1.1 MB of afterglow characterization data

### 2. Afterglow Collection Scripts (documentation)
**Source files:**
- `led_afterglow_integration_time_model.py` (18.9 KB)
- `afterglow_correction.py` (21.5 KB)
- `tools/diagnostic_scripts/led_afterglow_model.py` (24.2 KB)

**Purpose:** Show how afterglow data was collected (for reproducibility)

**Target:** `spectral_training_data/demo P4SPR 2.0/afterglow/scripts/`

---

## Next Device: New Unsealed Sensor

When you collect data from the new unsealed sensor:

```
spectral_training_data/
├── demo P4SPR 2.0/       # Used sensor (poor quality)
│   └── (complete dataset as above)
│
└── [NEW_DEVICE_SERIAL]/  # New unsealed sensor
    ├── device_info.json   # Mark as "new" quality
    ├── s/
    ├── p/
    ├── afterglow/         # NEW afterglow characterization
    ├── physics/
    ├── processed/
    └── README.md
```

---

## ML Training Benefits

Having complete device datasets enables:

### 1. **Instrumental vs Consumable Pattern Recognition**
- Train on known "good" device baseline (used sensor, stable)
- Learn what sensor quality degradation looks like
- Compare used vs new sensor characteristics

### 2. **Offline Pipeline Optimization**
- Test denoising algorithms without hardware
- Validate transmittance calculations
- Optimize spectral filtering
- Measure processing improvements quantitatively

### 3. **Cross-Device Generalization**
- Does model trained on "demo P4SPR 2.0" work on other devices?
- What device-specific calibration is needed?
- Can we detect sensor quality automatically?

### 4. **Physics Validation**
- Calculate sensorgram from raw spectra offline
- Compare to production system output
- Validate wavelength calibration accuracy
- Test dark correction methods

---

## Immediate Next Steps

1. **Wait for S-mode collection to complete** (~10 more minutes)
2. **Copy afterglow data** into device folder structure
3. **Run P-mode collection** (same 5 min × 4 channels)
4. **Calculate physics offline**:
   - Wavelength arrays (from calibration data)
   - Transmittance spectra
   - Sensorgram time-series
5. **Test processing pipelines** with different parameters
6. **Repeat for new unsealed sensor device**

---

## File Size Estimates

Per device dataset:
- **Raw spectral data** (S + P modes): ~50-100 MB (1200 spectra × 4 channels × 2 modes)
- **Afterglow data**: ~1-2 MB (models + plots)
- **Physics calculations**: ~20-50 MB (processed arrays)
- **Processing experiments**: Variable (10-100 MB depending on tests)

**Total per device:** ~100-250 MB

**Two devices:** ~200-500 MB (manageable, comprehensive)

---

## Success Metrics

After collecting both device datasets, you should be able to:
- ✅ Train ML model on production-speed raw data (4 Hz)
- ✅ Recognize instrumental issues (afterglow, LED instability, noise)
- ✅ Distinguish sensor quality degradation patterns
- ✅ Optimize processing pipeline offline
- ✅ Validate algorithm improvements quantitatively
- ✅ Predict how changes translate to production

---

## Notes

- **Production-matched timing**: 4 Hz collection ensures ML learns from realistic signal characteristics
- **Complete physics chain**: From raw spectra → transmittance → sensorgram enables full validation
- **Cross-device validation**: Two sensor types (used, new) tests model generalization
- **Offline optimization**: Iterate fast without hardware in the loop
