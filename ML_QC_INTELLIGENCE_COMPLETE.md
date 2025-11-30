# ML QC Intelligence System - Implementation Complete

**Date:** November 28, 2025
**Status:** ✅ Complete
**Architecture:** ML-Enhanced QC Layer

---

## Overview

Implemented ML-based predictive analytics for SPR calibration quality monitoring with 4 intelligent models:

1. **Calibration Quality Predictor** - Predicts failure probability for next calibration
2. **LED Health Monitor** - Tracks LED degradation and predicts replacement timeline
3. **Sensor Coating Degradation** - Estimates sensor chip lifespan from FWHM trends
4. **Optical Alignment Monitor** - Detects hardware drift using calibration baseline (non-interfering)

---

## Key Features

### ✅ Non-Interfering Design
- **Model 4 (Optical Alignment)** uses **CALIBRATION BASELINE** data only
- **NEVER analyzes real-time SPR measurements** during experiments
- Detects hardware drift (polarizer, fiber alignment) without touching dynamic SPR data
- Allows full range of biological SPR responses without ML interference

### ✅ Predictive Maintenance
- Predicts calibration failures before they occur
- Estimates LED lifespan in days
- Forecasts sensor chip replacement needs
- Detects optical misalignment early

### ✅ Automatic Integration
- Runs automatically after every calibration
- No user intervention required
- Logs predictions to console
- Saves history for continuous learning

---

## Architecture

### Data Flow
```
Calibration Complete
    ↓
CalibrationData (QC metrics)
    ↓
CalibrationService._update_ml_intelligence()
    ↓
┌─────────────────────────────────────────────────┐
│ MLQCIntelligence                                │
├─────────────────────────────────────────────────┤
│ Model 1: Calibration Quality Predictor          │
│   - Analyzes last 10 calibrations               │
│   - Predicts failure probability (0-1)          │
│   - Generates risk level (low/medium/high)      │
│   - Provides maintenance recommendations        │
├─────────────────────────────────────────────────┤
│ Model 2: LED Health Monitor                     │
│   - Tracks LED intensity trends                 │
│   - Calculates health score per channel         │
│   - Predicts days until replacement             │
│   - Flags critical LED status                   │
├─────────────────────────────────────────────────┤
│ Model 3: Sensor Coating Degradation             │
│   - Monitors FWHM trend over time               │
│   - Estimates experiments remaining             │
│   - Warns when FWHM approaching 60nm            │
│   - Recommends chip replacement timing          │
├─────────────────────────────────────────────────┤
│ Model 4: Optical Alignment Monitor               │
│   - Compares calibration P/S ratios to baseline │
│   - Detects hardware drift (3-sigma rule)       │
│   - NON-INTERFERING: Uses baseline data only    │
│   - Does NOT analyze real SPR measurements      │
└─────────────────────────────────────────────────┘
    ↓
ML Predictions Logged
    ↓
History Saved for Continuous Learning
```

---

## Model Details

### Model 1: Calibration Quality Predictor

**Input Features:**
- Last 10 calibrations (FWHM, LED intensities, saturation flags)
- Recent failure rate
- FWHM degradation trends
- LED health status

**Output:**
```python
CalibrationPrediction(
    failure_probability=0.15,    # 15% chance of failure
    predicted_fwhm={'a': 28.5, 'b': 30.1, 'c': 27.8, 'd': 29.3},
    confidence=0.85,              # 85% confidence
    warnings=["FWHM increasing rapidly (1.5nm per calibration)"],
    recommendations=["Inspect sensor chip for contamination"],
    risk_level='low'              # 'low', 'medium', 'high'
)
```

**Thresholds:**
- Risk HIGH: failure_probability > 0.7
- Risk MEDIUM: failure_probability > 0.4
- Risk LOW: failure_probability ≤ 0.4

---

### Model 2: LED Health Monitor

**Input Features:**
- LED intensity history per channel
- Integration time trends
- Calibration timestamps

**Output:**
```python
LEDHealthStatus(
    channel='a',
    current_intensity=195,
    intensity_trend=+2.3,         # +2.3 intensity units per calibration
    days_until_replacement=26,    # 26 days estimated lifespan
    health_score=0.82,            # 82% health (1.0 = perfect)
    status='good',                # 'excellent', 'good', 'degrading', 'critical'
    replacement_recommended=False
)
```

**Status Criteria:**
- **Excellent:** intensity < 200
- **Good:** 200 ≤ intensity < 230
- **Degrading:** 230 ≤ intensity < 250
- **Critical:** intensity ≥ 250 (replacement recommended)

---

### Model 3: Sensor Coating Degradation

**Input Features:**
- FWHM history (averaged across channels)
- Session quality metrics
- Calibration frequency

**Output:**
```python
SensorCoatingStatus(
    current_fwhm_avg=32.5,
    fwhm_trend=+0.8,              # +0.8nm per calibration
    estimated_experiments_remaining=35,
    coating_quality='good',       # 'excellent', 'good', 'acceptable', 'poor'
    replacement_warning=False,
    confidence=0.75
)
```

**Quality Thresholds:**
- **Excellent:** FWHM < 30nm
- **Good:** 30 ≤ FWHM < 45nm
- **Acceptable:** 45 ≤ FWHM < 60nm
- **Poor:** FWHM ≥ 60nm (coating degraded)

**Replacement Warning:** Triggered when FWHM > 55nm OR < 10 experiments remaining

---

### Model 4: Optical Alignment Monitor (Non-Interfering)

**CRITICAL DESIGN:** This model uses **CALIBRATION BASELINE** data only, NOT real-time SPR measurements.

**Input Features (Calibration QC Only):**
- P/S ratio from calibration transmission QC
- Historical calibration baseline (last 50 calibrations)
- Baseline statistics (mean, std)

**Output:**
```python
OpticalAlignmentStatus(
    ps_ratio_baseline=0.652,
    ps_ratio_deviation=0.023,     # Deviation from baseline
    orientation_confidence=0.88,  # 88% alignment confidence
    alignment_drift_detected=False,
    maintenance_recommended=False,
    warning_message=None
)
```

**Drift Detection Logic:**
- Uses **3-sigma rule** on calibration baseline (not real SPR data)
- Drift = deviation > (3 × baseline_std)
- Maintenance recommended if deviation > 0.2
- **Never touches experiment data** - baseline comparison only

**Why Non-Interfering:**
- Real SPR experiments show **dynamic P/S variations** (biological binding)
- Model 4 only checks **hardware drift** using calibration water baseline
- Separates **hardware issues** (polarizer shift) from **SPR signals** (real data)

---

## File Structure

### New Files
```
src/core/ml_qc_intelligence.py      # ML QC intelligence system (4 models)
```

### Modified Files
```
src/core/calibration_service.py     # ML integration after calibration
    - Added _ml_intelligence field
    - Added _update_ml_intelligence() method
    - Integrated ML predictions in QC flow
```

### Archived Files
```
archive/legacy_modules/
    ├── spr_data_acquisition.py     # Old ML afterglow correction (removed)
    └── spr_state_machine.py        # State machine dependency (removed)
```

---

## ML Data Storage

### Per-Device History
```
data/devices/{detector_serial}/ml_qc/
    ├── calibration_history.json         # Last 100 calibrations
    ├── led_health.json                  # LED degradation tracking
    ├── sensor_coating.json              # FWHM trend history
    └── alignment_baseline.json          # P/S ratio baseline (last 50)
```

### History Retention
- **Calibrations:** Last 100 stored
- **Alignment Baseline:** Last 50 calibrations
- **Continuous Learning:** Models improve with more data

---

## Usage

### Automatic Operation
```python
# ML intelligence runs automatically after each calibration
# No user intervention required

# In CalibrationService:
def _show_qc_dialog(self, calibration_data):
    # ... show QC dialog ...

    # Automatic ML analysis
    self._update_ml_intelligence(calibration_data)
```

### Manual Access
```python
# Get ML intelligence instance
ml_intel = app.calibration.get_ml_intelligence()

if ml_intel:
    # Model 1: Predict next calibration
    prediction = ml_intel.predict_next_calibration()
    print(f"Failure probability: {prediction.failure_probability*100:.1f}%")

    # Model 2: Check LED health
    led_statuses = ml_intel.predict_led_health()
    for led in led_statuses:
        print(f"Ch {led.channel}: {led.status} ({led.health_score*100:.0f}%)")

    # Model 3: Sensor coating life
    coating = ml_intel.predict_sensor_coating_life()
    print(f"Coating: {coating.coating_quality}, {coating.estimated_experiments_remaining} experiments left")

    # Model 4: Optical alignment (baseline-based)
    alignment = ml_intel.check_optical_alignment(calibration_data)
    print(f"Alignment drift: {alignment.alignment_drift_detected}")

    # Generate full report
    report = ml_intel.generate_intelligence_report()
    print(report)
```

---

## Example Log Output

### After Calibration
```
================================================================================
🤖 ML QC INTELLIGENCE - POST-CALIBRATION ANALYSIS
================================================================================

📊 Model 1: Next Calibration Prediction
   Failure Probability: 12.5%
   Risk Level: LOW
   💡 System healthy - no action needed

💡 Model 2: LED Health Status
   ✅ Ch A: excellent (intensity=185, trend=+1.2/cal)
   ✅ Ch B: good (intensity=210, trend=+2.1/cal)
   ✅ Ch C: excellent (intensity=192, trend=+0.9/cal)
   ⚠️  Ch D: degrading (intensity=235, trend=+3.5/cal)
      ⚠️  Estimated 6 days until replacement

🔬 Model 3: Sensor Coating Status
   Quality: GOOD
   Current FWHM (avg): 32.1 nm
   Trend: +0.5 nm/calibration
   Estimated Lifespan: 55 experiments

🔧 Model 4: Optical Alignment (Calibration Baseline)
   P/S Ratio Baseline: 0.648
   Deviation: 0.018
   Confidence: 92%
   ✅ Alignment stable

================================================================================
```

---

## Safety Features

### 1. Non-Interfering Model 4
- ✅ Uses calibration baseline ONLY
- ✅ Never analyzes real SPR experiment data
- ✅ Allows full dynamic SPR response range
- ✅ Separates hardware issues from biological signals

### 2. Graceful Degradation
- ✅ Works with limited data (minimum 3 calibrations)
- ✅ Confidence scores indicate prediction reliability
- ✅ Never blocks calibration on ML errors
- ✅ Falls back to physics-only when ML unavailable

### 3. Data Privacy
- ✅ All data stored locally per device
- ✅ No cloud transmission
- ✅ JSON format (human-readable)
- ✅ History capped at 100 calibrations

---

## Benefits

### 1. Predictive Maintenance
- **Before:** Calibration fails → manual troubleshooting → downtime
- **After:** ML predicts failure → proactive maintenance → no downtime

### 2. LED Lifespan Management
- **Before:** LED dies unexpectedly → experiment interrupted
- **After:** ML predicts replacement date → scheduled LED swap

### 3. Sensor Chip Optimization
- **Before:** Chip degrades → experiments fail → trial-and-error replacement
- **After:** ML tracks degradation → replace at optimal time

### 4. Optical Alignment Monitoring
- **Before:** Polarizer drifts → data quality degrades silently
- **After:** ML detects drift → maintenance scheduled → quality maintained

---

## Future Enhancements

### Phase 2: Advanced ML Models
1. **Deep Learning FWHM Predictor** - LSTM network for better FWHM forecasting
2. **Anomaly Detection** - Unsupervised learning to detect unusual patterns
3. **Multi-Device Learning** - Transfer learning across similar devices
4. **Experiment Success Predictor** - Predict if experiment will succeed based on calibration

### Phase 3: Cloud Intelligence (Optional)
1. **Fleet-Wide Analytics** - Aggregate insights across all devices
2. **Failure Pattern Recognition** - Learn from global calibration data
3. **Automated Troubleshooting** - AI-driven maintenance recommendations

---

## Testing Checklist

- [x] ML intelligence initializes on first calibration
- [x] All 4 models execute without errors
- [x] Predictions logged to console
- [x] History saved to JSON files
- [x] Model 4 uses calibration baseline only (non-interfering)
- [x] Graceful handling of insufficient data
- [x] Confidence scores calculated correctly
- [x] Legacy ML afterglow code archived

---

## Conclusion

The ML QC Intelligence system is now fully integrated into the calibration pipeline. All 4 predictive models run automatically after each calibration, providing:

✅ **Calibration failure prediction**
✅ **LED health monitoring**
✅ **Sensor coating lifespan tracking**
✅ **Optical alignment drift detection (baseline-based, non-interfering)**

The system learns continuously from calibration history and provides actionable maintenance recommendations without interfering with real SPR experimental data.
