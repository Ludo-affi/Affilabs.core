# LED Aging Monitoring System

## Overview
The afterglow calibration system automatically collects LED health metrics during optical calibration. This data is **non-blocking** and stored for system-level monitoring and future predictive maintenance ML models.

## Purpose
- **Passive Data Collection**: Health metrics captured automatically during routine calibration
- **Long-term Monitoring**: Track LED degradation trends over instrument lifetime
- **Predictive Maintenance**: Enable ML-based prediction of component failure
- **No User Disruption**: Non-blocking - never prevents calibration or measurements

---

## Collected Metrics

### 1. **Spectral Peak Shift** (EARLIEST Indicator)
- **What**: LED wavelength peak position change (ROI index)
- **Physics**: Phosphor degradation causes color shift
- **Timeline**: Detectable 6-12 months before other metrics
- **Critical Threshold**: > 10 indices shift
- **Warning Threshold**: > 5 indices shift

### 2. **Peak Intensity Loss**
- **What**: Maximum signal amplitude degradation
- **Physics**: LED brightness decline over time
- **Timeline**: Visible after 12-18 months
- **Critical Threshold**: > -30% loss
- **Warning Threshold**: > -15% loss

### 3. **Afterglow Amplitude Increase**
- **What**: Phosphor decay signal growth
- **Physics**: Material fatigue increases afterglow
- **Timeline**: Measurable after 18-24 months
- **Critical Threshold**: > 100% increase
- **Warning Threshold**: > 50% increase

### 4. **Cross-Channel Divergence**
- **What**: Standard deviation of τ across channels
- **Physics**: Non-uniform aging across PCB
- **Timeline**: Indicates thermal or electrical issues
- **Critical Threshold**: σ > 5ms
- **Warning Threshold**: σ > 3ms

### 5. **Decay Time Constant (τ) Drift**
- **What**: Individual channel τ change
- **Physics**: Material property degradation
- **Timeline**: Late-stage indicator
- **Critical Threshold**: > 20% change
- **Warning Threshold**: > 10% change

### 6. **Baseline Drift**
- **What**: Dark signal level change
- **Physics**: Detector or electronics degradation
- **Timeline**: Can indicate non-LED issues
- **Critical Threshold**: > 500 counts
- **Warning Threshold**: > 200 counts

---

## Data Storage

### Location
All aging data stored in: `optical_calibration.json`

### Structure
```json
{
  "afterglow_correction": {
    "metadata": {
      "led_spectral_info": {
        "A": {
          "peak_roi_index": 245,
          "peak_intensity": 42350
        },
        "B": {
          "peak_roi_index": 198,
          "peak_intensity": 38920
        },
        "C": {
          "peak_roi_index": 312,
          "peak_intensity": 41100
        },
        "D": {
          "peak_roi_index": 156,
          "peak_intensity": 39800
        }
      },
      "aging_assessment": {
        "status": "warning",
        "user_message": "ℹ️ Light Source Aging Detected\n\nYour instrument's LEDs are showing signs of wear...",
        "critical_channels": 0,
        "warning_channels": 2,
        "good_channels": 2,
        "mean_spectral_shift": 6.2,
        "mean_intensity_loss_pct": -12.3,
        "channel_details": {
          "A": {
            "status": "⚠️",
            "peak_shift_idx": 8,
            "intensity_loss_pct": -18.5,
            "amplitude_increase_pct": 45.2,
            "tau_change_pct": 5.3,
            "baseline_drift": 120
          },
          ...
        }
      }
    }
  }
}
```

### Key Features
- **Timestamped**: Calibration date recorded in metadata
- **Versioned**: Tracks changes between calibration runs
- **Complete History**: All raw fit parameters preserved
- **Human-Readable**: JSON format for easy inspection

---

## Usage Guidelines

### For System Integrators
1. **Data Access**: Read from `optical_calibration.json` → `afterglow_correction` → `metadata` → `aging_assessment`
2. **Status Levels**:
   - `"good"`: Normal operation
   - `"warning"`: Monitor, consider planning maintenance
   - `"critical"`: Schedule maintenance soon
3. **Non-Blocking**: Never prevent measurements based on this data (informational only)

### For ML/Analytics
1. **Time Series Analysis**: Track metrics across calibration dates
2. **Failure Prediction**: Train models on pre-failure data
3. **Correlation Studies**: Link spectral shift to other failure modes
4. **PCB Lifespan Modeling**: Estimate remaining useful life

### For UI Development (Optional)
- **Current Implementation**: Data stored, not displayed
- **Future Enhancement**: Optional dashboard showing trends
- **User Notifications**: Could show maintenance recommendations
- **Example Message**: `"Consider light source replacement within 3 months"`

---

## Implementation Details

### Calibration Workflow
1. **Dark Measurement**: Capture baseline noise
2. **LED Spectral Capture**: Measure peak position during pre-on phase
3. **Afterglow Grid**: Standard decay curve measurements
4. **Fit & Validate**: Quality control checks
5. **Aging Analysis**: Compare with previous calibration (if exists)
6. **Store All Data**: Save fits + spectral info + aging assessment

### Comparison Logic
- **First Run**: No previous data → aging_assessment = None
- **Subsequent Runs**: Automatic comparison with previous calibration
- **Metrics Calculated**: All 6 indicators per channel
- **Status Determined**: Based on worst channel + cross-channel consistency

### Quality Control Integration
Aging data is separate from QC:
- **QC Checks**: Block calibration on bad fits (R² < 0.85, invalid τ, etc.)
- **Aging Checks**: Informational only, never block
- **Logging**: Aging status logged but doesn't affect calibration success

---

## Technical Reference

### Physics Background
- **LED Phosphor**: White LEDs use blue LED + yellow phosphor
- **Decay Mechanism**: Exponential relaxation after excitation
- **Aging Physics**:
  - Phosphor degradation → spectral shift (blue shift or color change)
  - Material fatigue → increased afterglow amplitude
  - Thermal stress → non-uniform aging across channels

### Measurement Accuracy
- **Spectral Resolution**: ROI index (288 points across spectrum)
- **Intensity Precision**: ±50 counts typical noise
- **Temporal Resolution**: 10-85ms integration time grid
- **Repeatability**: τ measurements ±0.5ms run-to-run

### Validation Strategy
1. **Track Known-Good Instruments**: Establish baseline aging rates
2. **Correlate with Failures**: Link metrics to PCB replacements
3. **Refine Thresholds**: Adjust based on field data
4. **ML Training**: Use historical data for predictive models

---

## Future Enhancements

### Phase 1: Data Collection (CURRENT)
- ✅ Automatic metric capture
- ✅ JSON storage
- ✅ Non-blocking operation

### Phase 2: ML Integration (FUTURE)
- 📊 Time series database export
- 🤖 Failure prediction models
- 📈 Remaining useful life estimation
- 🔔 Proactive maintenance alerts

### Phase 3: User Features (OPTIONAL)
- 📱 Dashboard showing LED health trends
- 📧 Email notifications for maintenance
- 🛠️ Maintenance scheduler integration
- 📊 Fleet-wide health monitoring

---

## Related Documentation
- **Afterglow Calibration**: See `afterglow_calibration.py` module docstring
- **Quality Control**: See `CALIBRATION_QC_IMPLEMENTATION_COMPLETE.md`
- **Optical Calibration Architecture**: See `docs/implementation/OPTICAL_CALIBRATION_ARCHITECTURE.md`
- **Predictive Maintenance**: (Future) ML model documentation

---

## Contact & Support
For questions about:
- **Data Format**: See JSON schema above
- **ML Integration**: Contact system architecture team
- **Threshold Tuning**: Contact optical calibration team
- **Bug Reports**: File issue with calibration logs attached

---

**Last Updated**: November 23, 2025
**Status**: Production - Passive data collection active
**Next Review**: After 6 months of field data collection
