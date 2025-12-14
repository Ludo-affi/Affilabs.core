# Spectral Quality Analyzer - Training Guide

## Overview

This tool analyzes SPR sensorgram data to distinguish between:
1. **Instrumental issues** (hardware, optics, electronics)
2. **Consumable quality** (sensor chip defects, coating quality)

## Key Features Analyzed

### 1. Noise Frequency Analysis
**What it reveals:**
- **High-frequency noise (>0.1 Hz)** → Instrumental issues
  - LED flickering or instability
  - Electronic noise
  - Detector shot noise

- **Low-frequency noise (<0.1 Hz)** → Consumable issues
  - Surface defects/roughness
  - Coating non-uniformity
  - Thermal expansion gradients

**Diagnostic pattern:**
```
Frequency Ratio > 2.0  → Instrumental problem
Frequency Ratio < 0.5  → Consumable problem
```

### 2. Wavelength Stability
**What it reveals:**
- **High wavelength drift** → Instrumental issues
  - Optical misalignment
  - LED quality/aging
  - Temperature instability affecting optics

**Diagnostic pattern:**
```
Wavelength Std > 0.5 nm   → Instrumental warning
Wavelength Std > 1.0 nm   → Instrumental critical
```

### 3. Temporal Drift
**What it reveals:**
- **Negative improvement** (worse over time) → Instrumental thermal issues
- **High drift rate** → Consumable coating instability

**Diagnostic pattern:**
```
Stability Improvement < 0    → Instrumental thermal problem
Drift Rate > 0.3 RU/s        → Consumable coating issue
```

### 4. Transmission Spectrum Features
**What it reveals:**
- **High transmission minimum** → Poor coating quality
- **Low smoothness** → Surface roughness
- **Asymmetric peaks** → Coating gradients

**Diagnostic pattern:**
```
Trans Min > 0.1      → Poor coating
Smoothness < 0.5     → Rough surface
Asymmetry > 1.0      → Coating gradient
```

## Usage Workflow

### Step 1: Collect Reference Data (Good Sensors)

```bash
# Analyze a known good sensor
python spectral_quality_analyzer.py analyze good_sensor_1.csv -o good_1.json
python spectral_quality_analyzer.py analyze good_sensor_2.csv -o good_2.json
python spectral_quality_analyzer.py analyze good_sensor_3.csv -o good_3.json
```

Expected characteristics of GOOD sensors:
- Noise Std < 5 RU
- Peak-to-peak < 20 RU
- Wavelength Std < 0.2 nm
- Instrumental Score > 80
- Consumable Score > 80
- Grade: A

### Step 2: Collect Reference Data (Poor Sensors - Known Issues)

#### Poor Instrumental Quality
```bash
# Known LED instability
python spectral_quality_analyzer.py analyze bad_led.csv -o bad_led.json

# Expected:
# - High wavelength instability (>1 nm)
# - High frequency noise ratio (>2)
# - Poor temporal stabilization
# - Instrumental Score < 50
```

#### Poor Consumable Quality
```bash
# Known defective chip
python spectral_quality_analyzer.py analyze bad_chip.csv -o bad_chip.json

# Expected:
# - Low frequency noise dominant (<0.5)
# - High transmission minimum (>0.1)
# - Low smoothness
# - High drift rate
# - Consumable Score < 50
```

### Step 3: Batch Analysis for Comparison

```bash
# Analyze all sensors in a folder
python spectral_quality_analyzer.py batch ./sensor_data/ -o batch_report.json
```

### Step 4: Build Classification Rules

Based on your collected data, refine the thresholds in `spectral_quality_analyzer.py`:

```python
'excellent': {
    'noise_std': 5.0,          # Adjust based on your best sensors
    'peak_to_peak': 20.0,
    'wavelength_std': 0.2,
    'drift_rate': 0.1,
},
'good': {
    'noise_std': 15.0,
    'peak_to_peak': 50.0,
    'wavelength_std': 0.5,
    'drift_rate': 0.3,
},
```

## Interpretation Examples

### Example 1: Instrumental Issue (LED Instability)
```
Channel B:
  Grade: D
  Instrumental Score: 45
  Consumable Score: 75

  Noise Frequency Ratio: 3.2 (HIGH)
  Wavelength Std: 1.2 nm (HIGH)
  Stability Improvement: -0.15 (NEGATIVE)

DIAGNOSIS: LED instability or optical misalignment
ACTION: Check/replace LED, verify optical alignment
```

### Example 2: Consumable Issue (Poor Coating)
```
Channel C:
  Grade: D
  Instrumental Score: 85
  Consumable Score: 40

  Noise Frequency Ratio: 0.3 (LOW - surface noise)
  Transmission Min: 0.15 (HIGH - poor coating)
  Smoothness: 0.4 (LOW - rough surface)
  Drift Rate: 0.5 RU/s (HIGH)

DIAGNOSIS: Defective sensor chip (poor coating)
ACTION: Replace sensor chip, check storage conditions
```

### Example 3: Mixed Issues
```
Channel D:
  Grade: F
  Instrumental Score: 50
  Consumable Score: 45

  Wavelength Std: 0.8 nm (Moderate-High)
  Noise Frequency Ratio: 1.0 (Mixed)
  Transmission Min: 0.12 (High)

DIAGNOSIS: Both instrumental AND consumable issues
ACTION:
  1. Replace sensor chip first
  2. If problem persists, check LED/optics
```

## Training the System

### Phase 1: Baseline Establishment (Week 1)
1. Run 10+ measurements with **brand new, high-quality chips**
2. Use the **same instrument** throughout
3. Record all results as "GOOD baseline"
4. Calculate average scores and thresholds

### Phase 2: Controlled Degradation (Week 2-3)
1. **Instrumental degradation:**
   - Slightly misalign optics → measure
   - Use aged LED → measure
   - Run without thermal stabilization → measure

2. **Consumable degradation:**
   - Use expired chips → measure
   - Intentionally contaminate chip surface → measure
   - Use chips stored improperly → measure

### Phase 3: Blind Testing (Week 4)
1. Mix unknown quality sensors
2. Run analyzer
3. Compare predictions with known ground truth
4. Refine thresholds and rules

## Advanced: Machine Learning Enhancement

Once you have 50+ labeled samples (good/bad instrumental, good/bad consumable), you can train a classifier:

```python
# Pseudocode for ML enhancement
from sklearn.ensemble import RandomForestClassifier

# Features: all spectral features extracted
# Labels: [instrumental_good/bad, consumable_good/bad]

# Train classifier
clf = RandomForestClassifier()
clf.fit(features, labels)

# Predict new samples
prediction = clf.predict(new_features)
```

## Integration with Existing System

Add to `spr_data_acquisition.py`:

```python
from spectral_quality_analyzer import SpectralQualityAnalyzer

def auto_quality_check(csv_file):
    """Automatically check quality after measurement"""
    analyzer = SpectralQualityAnalyzer()
    features = analyzer.analyze_csv(csv_file)

    for feat in features:
        if feat.overall_quality_grade in ['D', 'F']:
            logger.warning(f"⚠️ Channel {feat.channel} quality issue detected!")
            logger.warning(f"   Instrumental: {feat.instrumental_quality_score:.0f}")
            logger.warning(f"   Consumable: {feat.consumable_quality_score:.0f}")
```

## Quick Reference: Diagnostic Flowchart

```
High Peak-to-Peak Noise?
├─ YES → Check Noise Frequency Ratio
│   ├─ >2.0 → INSTRUMENTAL (LED/electronics)
│   ├─ <0.5 → CONSUMABLE (surface defects)
│   └─ 0.5-2.0 → Check wavelength stability
│       ├─ >0.5nm → INSTRUMENTAL (optics)
│       └─ <0.5nm → CONSUMABLE (coating)
│
└─ NO → Check Temporal Drift
    ├─ High drift rate → CONSUMABLE (coating instability)
    └─ Negative improvement → INSTRUMENTAL (thermal)
```

## Expected Results from Your Current Data

Based on `test.csv` analysis:
- **Channel A**: Grade B - Good instrumental, moderate consumable (likely reference quality)
- **Channel B**: Grade D - Poor instrumental (wavelength instability) + poor consumable
- **Channel C**: Grade B - Good instrumental, moderate consumable issues
- **Channel D**: Grade C - Moderate instrumental, poor consumable (likely afterglow source)

**Overall Assessment**: Consumable quality appears to be the primary issue (low frequency noise dominant), but Channel B also has instrumental problems (LED instability).

## Next Steps

1. ✅ **Tool created and tested** on your current data
2. **Collect more samples:**
   - Run with 3-5 different sensor chips (same instrument)
   - Record which chips were fresh vs old vs stored improperly
3. **Build training dataset:**
   - Label each CSV with known quality (good chip/bad chip)
   - Record any known instrumental issues during measurement
4. **Refine thresholds** based on your specific instrument characteristics
5. **Automate quality checks** by integrating into your acquisition workflow

## Questions to Guide Training

For each measurement, document:
1. Chip batch number and age
2. Storage conditions
3. Any observed instrumental issues during measurement
4. Visual inspection of chip surface
5. Expected outcome (good/bad)

This creates ground truth for validating the analyzer's predictions.
