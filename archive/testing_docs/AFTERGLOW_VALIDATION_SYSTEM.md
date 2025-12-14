# Afterglow Validation System

## Overview

Comprehensive validation system for LED afterglow measurements to ensure data quality and detect hardware/timing issues. The system is **NON-BLOCKING** - it logs warnings but allows operation to continue, enabling us to collect data and refine thresholds as we learn more about different LED types.

## LED Type Tracking

### LED Type Codes
- **LCW**: Luminus Cool White (most common)
- **OWW**: Osram Warm White

### Device Serial Integration
LED type is saved with device serial number in:
1. **Device profiles**: `calibration_data/device_profiles/device_{serial}_{date}.json`
2. **Device config**: `config/device_config.json` (hardware.led_type_code)

## Validation Checks

### 1. **Fit Quality (R²)**
Validates exponential decay model fit quality:
- **Excellent**: R² ≥ 0.95
- **Good**: R² ≥ 0.85
- **Poor**: R² < 0.85 ⚠️ Warning

**Purpose**: Ensures decay model accurately represents measured data.

### 2. **Tau Range Validation**
Checks phosphor decay time constant against expected ranges:

#### Luminus Cool White (LCW)
- **Expected range**: 15-26 ms
- **Warning range**: 10-35 ms
- **Error range**: < 10 ms or > 35 ms

#### Osram Warm White (OWW)
- **Expected range**: 14-24 ms
- **Warning range**: 10-35 ms
- **Error range**: < 10 ms or > 35 ms

**Purpose**: Detects LED timing issues (too short = LED not fully on, too long = unusual phosphor behavior).

### 3. **Amplitude Reasonableness**
Validates afterglow amplitude:
- **Normal**: 100-10,000 counts
- **Warning**: > 10,000 counts (LED may not be turning off properly)
- **Error**: < 0 counts (fit error)

**Purpose**: Detects LED control timing problems where LED doesn't fully turn off.

### 4. **Baseline Stability**
Checks steady-state baseline signal:
- **Normal**: 0-1000 counts (near dark noise)
- **Warning**: > 1000 counts (LED residual glow)
- **Warning**: < -100 counts (unexpected negative offset)

**Purpose**: Ensures LED fully turns off and detector baseline is stable.

### 5. **Integration Time Dependency**
Validates tau trend across integration times:
- **Expected**: Tau increases or stays stable with integration time
  (longer exposure accumulates more phosphor energy)
- **Warning**: Decreasing trend (slope < -0.1)

**Purpose**: Validates physics consistency - phosphor should accumulate energy with longer integration.

## Usage

### During OEM Calibration
```bash
python utils/oem_calibration_tool.py \
  --serial FLMT12345 \
  --led-type LCW \
  --detector "Flame-T"
```

### Automatic Validation
Validation runs automatically when:
1. **OEM calibration** completes (tool validates fresh measurements)
2. **Afterglow correction loads** (validates stored calibration file)

### Validation Output
```
📊 Validating afterglow data for Luminus Cool White (LCW)
⚠️ Afterglow validation: Ch B @ 80ms: τ=27.23ms outside typical range [15, 26]ms for Luminus Cool White
✅ Afterglow validation: All checks passed
```

## Data Collection for Learning

### Metrics Stored
All validation results are saved in calibration files:
```json
{
  "validation": {
    "afterglow": {
      "led_type": "LCW",
      "passed": true,
      "warnings": [...],
      "errors": [...],
      "metrics": {
        "tau_slope_ch_a": 0.15,
        "tau_slope_ch_b": 0.12,
        ...
      }
    }
  }
}
```

### Threshold Refinement Strategy
As we collect more data from different devices:

1. **Collect measurements** from multiple devices with same LED type
2. **Analyze distribution** of tau values across devices
3. **Refine expected ranges** in `afterglow_correction.py` LED_SPECS:
   ```python
   'LCW': {
       'tau_range_ms': (15, 26),  # Adjust based on real data
       'tau_warn_range_ms': (10, 35),
       ...
   }
   ```
4. **Update thresholds** without affecting deployed systems (non-blocking validation)

## LED Type Documentation

### Luminus Cool White (LCW)
- **Phosphor**: Likely YAG:Ce³⁺ (Yttrium Aluminum Garnet doped with Cerium)
- **Expected τ**: 15-26 ms
- **Typical behavior**: Moderate afterglow, stable across devices
- **Most common**: Standard LED PCB in current production

### Osram Warm White (OWW)
- **Phosphor**: May include red phosphors for warmer spectrum
- **Expected τ**: 14-24 ms (preliminary)
- **Typical behavior**: To be characterized as more devices measured
- **Usage**: Alternative LED PCB, less common

## Implementation Files

### Core Validation
- **`Old software/afterglow_correction.py`**
  - `LED_SPECS`: Expected ranges per LED type
  - `AfterglowValidationResult`: Validation result container
  - `_validate_calibration_data()`: Main validation logic

### OEM Tool
- **`utils/oem_calibration_tool.py`**
  - `--led-type` parameter (LCW/OWW)
  - LED type saved in device profile
  - LED type passed to afterglow metadata

### Device Configuration
- **`utils/device_configuration.py`**
  - `LED_TYPE_MAP`: Code to full name mapping
  - `led_type_code` stored in hardware config

## Benefits

1. **Quality Assurance**: Catch hardware/calibration issues early
2. **Non-Blocking**: Warnings logged but operation continues
3. **Data Collection**: Build knowledge base of LED behavior
4. **Traceability**: Track LED type with device serial
5. **Adaptable**: Refine thresholds as we learn without code changes

## Future Enhancements

1. **Statistical Analysis**: Aggregate data from multiple devices
2. **Device-Specific Thresholds**: Per-device tolerance based on history
3. **Drift Detection**: Track tau changes over device lifetime
4. **LED Health Monitoring**: Use tau/amplitude changes to predict LED degradation
5. **Automated Reporting**: Generate LED type performance reports

## Notes

- Validation is **informational** - does not block operation
- Thresholds will be **refined** as we collect more real-world data
- LED type tracking enables **statistical analysis** across fleet
- System designed for **long-term learning** about LED characteristics
