# Bilinear Model Quick Reference

## Model Equation
```
counts(I, t) = (a·t + b)·I + (c·t + d)
```

## Model Parameters (FLMT09116)

### S-Polarization (PWM=72)
| LED | a | b | c | d |
|-----|------|---------|------|---------|
| A | 5.34 | 1121.3 | 4.70 | 3131.3 |
| B | 13.04 | 2736.6 | 4.70 | 3131.3 |
| C | 16.14 | 3387.9 | 4.70 | 3131.3 |
| D | 5.66 | 1188.8 | 4.70 | 3131.3 |

### P-Polarization (PWM=8)
| LED | a | b | c | d |
|-----|------|---------|------|---------|
| A | 2.90 | 608.4 | 4.70 | 3131.3 |
| B | 7.81 | 1639.7 | 4.70 | 3131.3 |
| C | 8.85 | 1858.4 | 4.70 | 3131.3 |
| D | 3.63 | 762.8 | 4.70 | 3131.3 |

## Python Code

### Load Model
```python
import json
with open('spr_calibration/models/led_calibration_spr_processed_FLMT09116.json') as f:
    models = json.load(f)['models']
```

### Predict Counts
```python
def predict(led, pol, I, t):
    p = models[pol][led]
    return (p['a']*t + p['b'])*I + (p['c']*t + p['d'])
```

### Calculate Safe Parameters
```python
def safe_params(led, pol, target=40000):
    p = models[pol][led]
    I = 100
    t = (target - p['b']*I - p['d']) / (p['a']*I + p['c'])
    return {'I': int(I), 't': round(t,2)}
```

## Operating Limits
- **Time:** 10-60 ms (optimal)
- **Counts:** < 60,000 (avoid saturation)
- **ROI:** 560-720 nm (SPR region)

## Validation
- **R²:** > 0.9999 ✅
- **Error:** < 2% (10-60ms) ✅
- **Date:** Dec 7, 2025 ✅

## Files
- **Model:** `spr_calibration/models/led_calibration_spr_processed_FLMT09116.json`
- **Docs:** `spr_calibration/models/BILINEAR_MODEL_DOCUMENTATION.md`
- **Guide:** `spr_calibration/CALIBRATION_INTEGRATION_GUIDE.md`

## Example Usage
```python
# Predict LED_C, S-pol at I=100, t=30ms
counts = predict('C', 'S', 100, 30.0)
# Expected: ~53,000 counts

# Get safe parameters for LED_A, P-pol, 35k counts
params = safe_params('A', 'P', 35000)
# Returns: {'I': 100, 't': 48.26}
```
