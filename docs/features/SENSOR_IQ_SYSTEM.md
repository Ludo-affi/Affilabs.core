# Sensor IQ - SPR Data Quality Classification System

**Document Status:** ✅ Code-verified  
**Last Updated:** February 19, 2026  
**Source File:** `affilabs/utils/sensor_iq.py` (430 lines)

## Overview

The **Sensor IQ (Intelligence Quotient)** system provides real-time quality assessment for SPR sensorgram data. It automatically classifies data quality based on wavelength position and FWHM (Full Width at Half Maximum) characteristics, helping users identify sensor issues before they affect data quality.

## Quality Classification Zones

### Wavelength Zones

The sensorgram wavelength range is divided into quality zones based on typical SPR sensor behavior:

| Zone | Wavelength Range | Classification | Description |
|------|-----------------|----------------|-------------|
| **Good** | 590-690 nm | ✅ EXPECTED | Normal operating range, high confidence |
| **Questionable Low** | 560-590 nm | ⚠️ EDGE | Lower boundary, acceptable but monitor |
| **Questionable High** | 690-720 nm | ⚠️ EDGE | Upper boundary, acceptable but monitor |
| **Out of Bounds Low** | <560 nm | ⛔ INVALID | Below valid range, sensor issues |
| **Out of Bounds High** | >720 nm | ⛔ INVALID | Above valid range, sensor issues |

### Visual Representation

```
  <560nm   560-590nm    590-690nm      690-720nm    >720nm
  ┌────┬──────────┬────────────────┬──────────┬─────┐
  │ ⛔ │    ⚠️     │      ✅        │    ⚠️     │  ⛔ │
  │OUT │QUESTION- │     GOOD       │QUESTION- │ OUT │
  │    │ABLE LOW  │   (Expected)   │ABLE HIGH │     │
  └────┴──────────┴────────────────┴──────────┴─────┘
```

## FWHM Quality Thresholds

FWHM (Full Width at Half Maximum) indicates the sharpness of the SPR dip, correlating with sensor surface quality:

| FWHM Range | Quality | Sensor Status |
|------------|---------|---------------|
| <30 nm | ⭐ **EXCELLENT** | Sharp peak, optimal coupling |
| 30-60 nm | ✅ **GOOD** | Normal operating range |
| 60-80 nm | ⚠️ **POOR** | Degraded coupling, monitor |
| >80 nm | ⛔ **CRITICAL** | Severe coupling issues |

### FWHM Interpretation

- **Narrow FWHM (15-30nm)**: Indicates good water contact, high sensitivity sensor
- **Broad FWHM (>50nm)**: May indicate:
  - Poor water contact
  - Air bubbles on sensor surface
  - Sensor contamination or degradation
  - Dry sensor (no water in flow cell)

## Sensor IQ Levels

The system combines wavelength zone and FWHM to produce an overall **Sensor IQ Level**:

### 🌟 EXCELLENT
- Wavelength: 590-690 nm
- FWHM: <30 nm
- Quality Score: 0.9-1.0
- **Action**: Continue experiment, optimal conditions

### ✅ GOOD
- Wavelength: 590-690 nm
- FWHM: 30-60 nm
- Quality Score: 0.6-0.9
- **Action**: Normal operation, data is reliable

### ⚠️ QUESTIONABLE
- Wavelength: 560-590 nm OR 690-720 nm
- FWHM: Any reasonable value
- OR: Good wavelength zone but FWHM 60-80 nm
- Quality Score: 0.3-0.6
- **Action**: Monitor closely, may indicate:
  - Binding event (wavelength shift)
  - Gradual sensor drift
  - Early coupling degradation

### 🔶 POOR
- Wavelength: Edge zones with high FWHM
- OR: Good zone but FWHM >80 nm
- Quality Score: 0.1-0.3
- **Action**: Check sensor surface quality, verify water contact

### ⛔ CRITICAL
- Wavelength: <560 nm OR >720 nm
- Quality Score: 0.0-0.1
- **Action**: STOP - Check sensor immediately:
  - Verify water contact
  - Inspect for air bubbles
  - Check for surface contamination
  - Ensure proper sensor installation

## Integration

### Automatic Classification

Every SPR data point is automatically classified during acquisition:

```python
# In data_acquisition_manager.py
from affilabs.utils.sensor_iq import classify_spr_quality, log_sensor_iq

# After peak finding
sensor_iq = classify_spr_quality(
    wavelength=peak_wavelength,
    fwhm=fwhm_nm,
    channel=channel
)

# Log warnings for poor quality
if sensor_iq.iq_level in [SensorIQLevel.CRITICAL, SensorIQLevel.POOR]:
    log_sensor_iq(sensor_iq, channel)
```

### Data Structure

Each processed data point includes sensor IQ metrics:

```python
{
    'wavelength': 645.2,  # nm
    'fwhm': 28.5,         # nm
    'sensor_iq': SensorIQMetrics(
        wavelength=645.2,
        fwhm=28.5,
        zone=WavelengthZone.GOOD,
        iq_level=SensorIQLevel.EXCELLENT,
        quality_score=0.95,
        warning_message=None,
        recommendation=None
    )
}
```

## Usage Examples

### Manual Quality Check

```python
from affilabs.utils.sensor_iq import classify_spr_quality

# Check a single measurement
iq = classify_spr_quality(wavelength=642.5, fwhm=25.0, channel='a')

print(f"IQ Level: {iq.iq_level.value}")
print(f"Quality Score: {iq.quality_score:.2f}")
print(f"Zone: {iq.zone.value}")

if iq.warning_message:
    print(f"Warning: {iq.warning_message}")
if iq.recommendation:
    print(f"Recommendation: {iq.recommendation}")
```

### Trend Analysis

```python
from affilabs.utils.sensor_iq import get_sensor_iq_classifier

classifier = get_sensor_iq_classifier()

# Get recent trend for channel A
trend = classifier.get_channel_trend('a', window=20)

if trend:
    print(f"Mean wavelength: {trend['wavelength_mean']:.2f} nm")
    print(f"Wavelength drift: {trend['wavelength_drift']:.2f} nm")
    print(f"Quality trend: {trend['quality_score_trend']}")
```

## Logging Behavior

### Automatic Logging Levels

- **CRITICAL IQ**: `logger.error()` - Red text, immediate attention
- **POOR IQ**: `logger.warning()` - Yellow text, monitor
- **QUESTIONABLE IQ**: `logger.info()` - White text, informational
- **GOOD/EXCELLENT IQ**: `logger.debug()` - Only in debug mode

### Example Log Output

```
[Ch A] Sensor IQ EXCELLENT: λ=642.3nm, FWHM=26.5nm, Score=0.96
[Ch B] Sensor IQ QUESTIONABLE: λ=695.8nm (Zone: questionable_high)
   ⚠️  Wavelength 695.8nm in edge zone
[Ch C] Sensor IQ POOR: λ=712.4nm, FWHM=78.2nm
   ⚠️  Wavelength 712.4nm in edge zone with poor FWHM 78.2nm
   → Check sensor surface quality and water contact
[Ch D] Sensor IQ CRITICAL: ⛔ CRITICAL: Wavelength 752.1nm is above valid range (>720nm)
   → Verify sensor coupling, check for contamination or surface degradation
```

## Troubleshooting Guide

### High FWHM (>60 nm) in Good Zone

**Symptoms**: FWHM consistently >60 nm, wavelength in 590-690 nm range

**Possible Causes**:
1. Air bubbles on sensor surface
2. Poor water contact (dry spots)
3. Temperature instability
4. Sensor surface contamination

**Solutions**:
1. Prime flow cell thoroughly
2. Check flow rate (ensure continuous flow)
3. Clean sensor surface with appropriate protocol
4. Verify temperature stabilization

### Wavelength Drift to Edge Zones

**Symptoms**: Wavelength gradually moving toward 560 nm or 720 nm

**Possible Causes**:
1. Binding event (expected for assays)
2. Temperature drift
3. Sensor degradation
4. Refractive index change

**Solutions**:
1. If during assay: Normal, monitor binding curve
2. If at baseline: Check temperature control
3. Verify buffer composition hasn't changed
4. Inspect sensor surface condition

### Critical Out-of-Bounds Wavelength

**Symptoms**: Wavelength <560 nm or >720 nm

**Possible Causes**:
1. No water in flow cell (dry sensor)
2. Air bubble covering sensor
3. Sensor surface damage
4. Optical misalignment

**Solutions**:
1. STOP acquisition immediately
2. Check flow cell for water
3. Prime system thoroughly
4. Inspect sensor surface visually
5. If persistent, replace sensor chip

## API Reference

### Main Functions

#### `classify_spr_quality(wavelength, fwhm=None, channel=None)`
Classify SPR data quality with full IQ assessment.

**Parameters**:
- `wavelength` (float): SPR peak wavelength in nm
- `fwhm` (float, optional): Full width at half maximum in nm
- `channel` (str, optional): Channel identifier for history tracking

**Returns**: `SensorIQMetrics` object with complete quality assessment

#### `log_sensor_iq(metrics, channel)`
Log sensor IQ metrics with appropriate severity level.

**Parameters**:
- `metrics` (SensorIQMetrics): Quality metrics to log
- `channel` (str): Channel identifier

### Classes

#### `SensorIQClassifier`
Main classifier for sensor quality assessment. Singleton instance available via `get_sensor_iq_classifier()`.

**Methods**:
- `classify_wavelength_zone(wavelength)`: Get wavelength zone
- `classify_fwhm_quality(fwhm)`: Get FWHM quality category
- `compute_sensor_iq(wavelength, fwhm, channel)`: Full IQ computation
- `get_channel_trend(channel, window)`: Analyze recent trend

#### `SensorIQMetrics` (dataclass)
Container for quality assessment results.

**Fields**:
- `wavelength` (float): Measured wavelength
- `fwhm` (float | None): Measured FWHM
- `zone` (WavelengthZone): Wavelength zone classification
- `iq_level` (SensorIQLevel): Overall quality level
- `quality_score` (float): Numeric score 0.0-1.0
- `warning_message` (str | None): Warning text if applicable
- `recommendation` (str | None): Recommended action if applicable

### Enums

#### `SensorIQLevel`
- `EXCELLENT`: Best quality (0.9-1.0)
- `GOOD`: Normal quality (0.6-0.9)
- `QUESTIONABLE`: Monitor (0.3-0.6)
- `POOR`: Check sensor (0.1-0.3)
- `CRITICAL`: Stop and fix (0.0-0.1)

#### `WavelengthZone`
- `GOOD`: 590-690 nm
- `QUESTIONABLE_LOW`: 560-590 nm
- `QUESTIONABLE_HIGH`: 690-720 nm
- `OUT_OF_BOUNDS_LOW`: <560 nm
- `OUT_OF_BOUNDS_HIGH`: >720 nm

## Future Enhancements

### Planned Features

1. **Real-time UI Indicators**
   - Color-coded quality badges on sensorgram display
   - FWHM trend graph in diagnostics
   - Quality history chart per channel

2. **Predictive Alerts**
   - Detect gradual quality degradation
   - Predict sensor failure before critical
   - Suggest maintenance windows

3. **Automated Responses**
   - Pause acquisition on critical quality
   - Auto-adjust LED delays for poor FWHM
   - Smart recalibration triggers

4. **Quality Reports**
   - Session quality summary
   - Per-channel quality statistics
   - Export quality metrics with data

## Related Systems

- **Peak Tracking** (`utils/enhanced_peak_tracking.py`): Provides wavelength measurement
- **FWHM Calculation** (`utils/led_calibration.py`): Computes peak width
- **Data Acquisition** (`core/data_acquisition_manager.py`): Integrates quality checks
- **Flagging System** (`FLAGGING_SYSTEM_GUIDE.md`): Manual quality annotations

---

**Version**: 2.0  
**Date**: February 19, 2026  
**Module**: `affilabs/utils/sensor_iq.py`
