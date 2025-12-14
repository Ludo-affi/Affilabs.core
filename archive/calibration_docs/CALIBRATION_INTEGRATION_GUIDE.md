# SPR Calibration Integration Guide

## Quick Start - Deploy Calibration to New System

### 1. Clone Repository
```bash
git clone https://github.com/Ludo-affi/ezControl-AI.git
cd ezControl-AI
```

### 2. Locate Model File
```
spr_calibration/models/led_calibration_spr_processed_FLMT09116.json
```

### 3. Load Model in Your Code
```python
import json
from pathlib import Path

# Load calibration model
MODEL_PATH = Path("spr_calibration/models/led_calibration_spr_processed_FLMT09116.json")
with open(MODEL_PATH, 'r') as f:
    calibration = json.load(f)

models = calibration['models']  # Dict with 'S' and 'P' polarizations
```

### 4. Use Model to Predict Counts
```python
def predict_counts(led, pol, intensity, time_ms):
    """
    Predict detector counts using bilinear model.
    
    Args:
        led: 'A', 'B', 'C', or 'D'
        pol: 'S' or 'P'
        intensity: LED intensity (0-255)
        time_ms: Integration time in milliseconds
    
    Returns:
        Predicted counts (float)
    """
    params = models[pol][led]
    a = params['a']
    b = params['b']
    c = params['c']
    d = params['d']
    
    counts = (a * time_ms + b) * intensity + (c * time_ms + d)
    return counts
```

---

## File Structure

```
spr_calibration/
├── models/
│   ├── BILINEAR_MODEL_DOCUMENTATION.md    # Full model documentation
│   └── led_calibration_spr_processed_FLMT09116.json  # Production model
│
├── data/
│   ├── spr_2d_grid_S_FLMT09116.json       # Raw S-pol measurements
│   ├── spr_2d_grid_P_FLMT09116.json       # Raw P-pol measurements
│   └── dark_current_FLMT09116.json        # Dark current data
│
├── tests/
│   ├── validate_calibration.py            # Transmission spectra test
│   ├── validate_fixed_intensity.py        # Fixed-I variable-t test
│   └── test_sensitivity_correction_simple.py
│
├── validation_results/
│   ├── validation_transmission_spectra_FLMT09116.png
│   ├── validation_results_FLMT09116.json
│   ├── validation_fixed_intensity_FLMT09116.png
│   └── validation_fixed_intensity_FLMT09116.json
│
├── measure.py      # Data acquisition script (2-point sampling)
└── process.py      # Model fitting and validation
```

---

## Model Structure

### JSON Format
```json
{
  "device_id": "FLMT09116",
  "calibration_date": "2025-12-07",
  "models": {
    "S": {
      "A": {"a": 5.34, "b": 1121.3, "c": 4.70, "d": 3131.3},
      "B": {"a": 13.04, "b": 2736.6, "c": 4.70, "d": 3131.3},
      "C": {"a": 16.14, "b": 3387.9, "c": 4.70, "d": 3131.3},
      "D": {"a": 5.66, "b": 1188.8, "c": 4.70, "d": 3131.3}
    },
    "P": {
      "A": {"a": 2.90, "b": 608.4, "c": 4.70, "d": 3131.3},
      "B": {"a": 7.81, "b": 1639.7, "c": 4.70, "d": 3131.3},
      "C": {"a": 8.85, "b": 1858.4, "c": 4.70, "d": 3131.3},
      "D": {"a": 3.63, "b": 762.8, "c": 4.70, "d": 3131.3}
    }
  },
  "servo_positions": {
    "S": 72,
    "P": 8
  },
  "roi": {
    "wavelength_min": 560,
    "wavelength_max": 720,
    "unit": "nm"
  }
}
```

### Parameter Interpretation
- **a**: Sensitivity slope (counts/ms/intensity_unit)
- **b**: Sensitivity offset (counts/intensity_unit)  
- **c**: Dark signal slope (counts/ms)
- **d**: Dark signal offset (counts)

---

## Integration Examples

### Example 1: Calculate Safe Parameters for Target Counts

```python
def calculate_parameters(led, pol, target_counts=40000, max_counts=60000):
    """
    Calculate LED intensity and integration time for target counts.
    
    Keeps system in safe operating range (10-60ms, <60k counts).
    """
    params = models[pol][led]
    a, b, c, d = params['a'], params['b'], params['c'], params['d']
    
    # Strategy: Fix intensity, solve for time
    intensity = 100  # moderate level
    
    # Solve: target = (a*t + b)*I + (c*t + d)
    time_ms = (target_counts - b*intensity - d) / (a*intensity + c)
    
    # Check if within safe range
    if time_ms < 10 or time_ms > 60:
        # Switch strategy: fix time, solve for intensity
        time_ms = 30.0
        intensity = (target_counts - c*time_ms - d) / (a*time_ms + b)
    
    # Predict actual counts
    predicted = (a*time_ms + b)*intensity + (c*time_ms + d)
    
    return {
        'intensity': int(np.clip(intensity, 0, 255)),
        'integration_time_ms': round(time_ms, 2),
        'predicted_counts': int(predicted)
    }

# Usage
params = calculate_parameters('C', 'S', target_counts=40000)
print(f"Set LED_C to I={params['intensity']}, t={params['integration_time_ms']}ms")
print(f"Expected counts: {params['predicted_counts']}")
```

### Example 2: Multi-LED Balanced Operation

```python
def balance_all_leds(target_counts=35000, pol='S'):
    """
    Calculate parameters to achieve similar counts across all 4 LEDs.
    
    Returns dict with parameters for each LED.
    """
    results = {}
    
    for led in ['A', 'B', 'C', 'D']:
        params = calculate_parameters(led, pol, target_counts)
        results[led] = params
        
        print(f"LED_{led}: I={params['intensity']:3d}, "
              f"t={params['integration_time_ms']:5.2f}ms, "
              f"counts={params['predicted_counts']:5d}")
    
    return results

# Usage
led_params = balance_all_leds(target_counts=40000, pol='S')
```

### Example 3: Check if Parameters Will Saturate

```python
def check_saturation(led, pol, intensity, time_ms, threshold=60000):
    """
    Check if given parameters will cause detector saturation.
    
    Returns: (predicted_counts, will_saturate)
    """
    predicted = predict_counts(led, pol, intensity, time_ms)
    will_saturate = predicted > threshold
    
    if will_saturate:
        # Calculate max safe time at this intensity
        params = models[pol][led]
        a, b, c, d = params['a'], params['b'], params['c'], params['d']
        max_time = (threshold - b*intensity - d) / (a*intensity + c)
        
        print(f"⚠️  LED_{led} will saturate!")
        print(f"   Predicted: {predicted:.0f} counts (limit: {threshold})")
        print(f"   Max safe time at I={intensity}: {max_time:.1f}ms")
        return predicted, True
    
    return predicted, False

# Usage
counts, saturated = check_saturation('C', 'S', intensity=150, time_ms=50)
```

---

## Common Integration Patterns

### Pattern 1: Fixed Integration Time, Variable Intensity
**Use case:** Fast scanning, consistent timing

```python
def get_intensity_for_target(led, pol, target_counts, time_ms=30.0):
    """Calculate LED intensity needed for target counts at fixed time."""
    params = models[pol][led]
    a, b, c, d = params['a'], params['b'], params['c'], params['d']
    
    intensity = (target_counts - c*time_ms - d) / (a*time_ms + b)
    return int(np.clip(intensity, 0, 255))

# Set all LEDs to 30ms, calculate intensities for 40k counts
for led in ['A', 'B', 'C', 'D']:
    intensity = get_intensity_for_target(led, 'S', 40000, 30.0)
    print(f"LED_{led}: I={intensity} at t=30.0ms")
```

### Pattern 2: Fixed Intensity, Variable Time
**Use case:** Consistent brightness, adaptive exposure

```python
def get_time_for_target(led, pol, target_counts, intensity=100):
    """Calculate integration time needed for target counts at fixed intensity."""
    params = models[pol][led]
    a, b, c, d = params['a'], params['b'], params['c'], params['d']
    
    time_ms = (target_counts - b*intensity - d) / (a*intensity + c)
    return round(time_ms, 2)

# Set all LEDs to I=100, calculate times for 40k counts
for led in ['A', 'B', 'C', 'D']:
    time_ms = get_time_for_target(led, 'S', 40000, 100)
    print(f"LED_{led}: t={time_ms}ms at I=100")
```

### Pattern 3: SPR Measurement Workflow
**Use case:** Full SPR spectrum acquisition

```python
def setup_spr_measurement(target_counts=40000):
    """
    Calculate optimal parameters for SPR measurement.
    
    Returns parameters for both S and P polarizations.
    """
    measurement_config = {
        'S': {},
        'P': {}
    }
    
    for pol in ['S', 'P']:
        for led in ['A', 'B', 'C', 'D']:
            params = calculate_parameters(led, pol, target_counts)
            measurement_config[pol][led] = params
    
    return measurement_config

# Get configuration
config = setup_spr_measurement(target_counts=35000)

# Use in measurement
for pol in ['S', 'P']:
    print(f"\n{pol}-Polarization (servo={calibration['servo_positions'][pol]}):")
    for led in ['A', 'B', 'C', 'D']:
        p = config[pol][led]
        print(f"  LED_{led}: I={p['intensity']:3d}, "
              f"t={p['integration_time_ms']:5.2f}ms → "
              f"{p['predicted_counts']:5d} counts")
```

---

## Running Calibration on New Detector

### Step 1: Update Device Config
Edit `src/config/devices/{SERIAL}/device_config.json`:
```json
{
  "hardware": {
    "spectrometer_serial": "FLMT09999",  // New serial
    "servo_positions": {
      "S": 72,
      "P": 8
    }
  }
}
```

### Step 2: Run Calibration Measurement
```bash
cd ezControl-AI
python spr_calibration/measure.py
```

**Duration:** ~15 minutes  
**Output:** 
- `spr_calibration/data/spr_2d_grid_S_FLMT09999.json`
- `spr_calibration/data/spr_2d_grid_P_FLMT09999.json`
- `spr_calibration/data/dark_current_FLMT09999.json`

### Step 3: Process Data
```bash
python spr_calibration/process.py
```

**Output:**
- `spr_calibration/models/led_calibration_spr_processed_FLMT09999.json`
- Validation plots in `LED-Counts relationship/`

### Step 4: Validate Model
```bash
# Test 1: Transmission spectra
python spr_calibration/tests/validate_calibration.py

# Test 2: Fixed intensity linearity
python spr_calibration/tests/validate_fixed_intensity.py
```

**Check results:**
- Errors should be < 2% in 10-60ms range
- R² > 0.9999 for linearity
- P/S transmission ratios 0.98-1.00

### Step 5: Deploy via Git
```bash
git add spr_calibration/models/led_calibration_spr_processed_FLMT09999.json
git add spr_calibration/data/*FLMT09999.json
git add spr_calibration/validation_results/*FLMT09999.*
git commit -m "Add calibration for detector FLMT09999"
git push
```

---

## Troubleshooting

### Issue: Model file not found
**Solution:** Check that detector serial matches filename:
```python
detector_serial = "FLMT09116"  # Update this
model_path = f"spr_calibration/models/led_calibration_spr_processed_{detector_serial}.json"
```

### Issue: Predictions seem wrong
**Solution:** Verify units:
- Intensity: 0-255 (PWM value)
- Time: milliseconds (not seconds!)
- Counts: raw detector ADC counts (0-65535)

### Issue: Getting saturation warnings
**Solution:** Reduce intensity or integration time:
```python
# If counts > 60k, reduce parameters by 20%
new_intensity = int(old_intensity * 0.8)
new_time = old_time * 0.8
```

### Issue: Different results between S and P
**Solution:** This is expected! P-pol has ~54% transmission of S-pol due to perpendicular orientation. Use appropriate model for each polarization.

---

## Performance Tips

### Tip 1: Cache Model at Startup
```python
# Load once at program start
CALIBRATION_MODEL = None

def load_model():
    global CALIBRATION_MODEL
    if CALIBRATION_MODEL is None:
        with open('spr_calibration/models/led_calibration_spr_processed_FLMT09116.json') as f:
            CALIBRATION_MODEL = json.load(f)
    return CALIBRATION_MODEL

# Use cached model
models = load_model()['models']
```

### Tip 2: Vectorize Predictions
```python
def predict_counts_batch(led, pol, intensities, times):
    """Predict counts for multiple I/t pairs at once."""
    params = models[pol][led]
    a, b, c, d = params['a'], params['b'], params['c'], params['d']
    
    I = np.array(intensities)
    t = np.array(times)
    
    counts = (a*t + b)*I + (c*t + d)
    return counts
```

### Tip 3: Pre-calculate Lookup Tables
```python
# Build lookup table at startup for common parameters
LOOKUP_TABLE = {}
for led in ['A', 'B', 'C', 'D']:
    for pol in ['S', 'P']:
        for I in range(0, 256, 10):  # Every 10 intensity units
            for t in range(10, 61, 5):  # Every 5ms
                key = (led, pol, I, t)
                LOOKUP_TABLE[key] = predict_counts(led, pol, I, t)

# Use lookup table (faster than calculation)
counts = LOOKUP_TABLE[('C', 'S', 100, 30)]
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-07 | Initial production-ready model (FLMT09116) |

---

## Support

**Documentation:** `spr_calibration/models/BILINEAR_MODEL_DOCUMENTATION.md`  
**Repository:** https://github.com/Ludo-affi/ezControl-AI  
**Branch:** affilabs.core-beta

---

**Last Updated:** December 7, 2025  
**Status:** Production-Ready ✅
