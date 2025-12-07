# Quick Validation vs Full Calibration Comparison

## Overview

Two methods are available for servo polarizer position verification:

| Method | Time | When to Use | Output |
|--------|------|-------------|--------|
| **Full Calibration** | ~60s | First setup, type unknown, baseline establishment | P/S positions + type detection + stable ranges |
| **Quick Validation** | ~30s | Periodic checks, position verification, system health | Pass/Fail + noise metrics |

## Full Calibration (`calibrate_polarizer.py`)

### Purpose
Establish optimal P and S positions from scratch with automatic polarizer type detection.

### Process
1. **Stage 1:** 5-position bidirectional sweep (1→255→1)
   - Maps intensity across full range
   - Detects hysteresis
2. **Stage 2:** Automatic type detection (CIRCULAR vs BARREL)
   - Analyzes intensity distribution
   - Identifies P and S regions
3. **Stage 3:** ±10 PWM refinement around detected regions
   - 10 scans per position
   - Noise characterization
   - Stable range identification
   - Middle-of-plateau selection

### Use Cases
✅ **First-time system setup**
✅ **Unknown polarizer type**
✅ **After polarizer replacement**
✅ **Establishing baseline calibration**
✅ **Major mechanical changes**
✅ **Annual recalibration**

### Outputs
- `polarizer_calibration_results.csv` - P/S positions, ranges, type
- `polarizer_calibration_detail.csv` - Full sweep data

### Typical Results
```
P Position: PWM 6 (stable range: 1-11)
  Intensity: 5245.9 ± 11.9 counts (0.23% CV)
S Position: PWM 69 (stable range: 64-75)
  Intensity: 13455.0 ± 12.4 counts (0.09% CV)
S/P Ratio: 2.56×
Time: ~60 seconds
```

---

## Quick Validation (`validate_stored_calibration.py`)

### Purpose
Verify stored P and S positions are still valid (no drift, hardware functional).

### Process
1. Load positions from `polarizer_calibration_results.csv` (or command line)
2. Move to P position with directional approach
3. Take 20 measurements with spectral analysis
4. Move to S position with directional approach
5. Take 20 measurements with spectral analysis
6. Calculate S/P ratio, noise, separation
7. Apply pass/fail criteria

### Use Cases
✅ **Daily system checks**
✅ **After power cycle**
✅ **After moving hardware**
✅ **Periodic verification (weekly/monthly)**
✅ **Pre-experiment validation**
✅ **Automated testing (CI/CD)**

### Validation Criteria
| Check | Threshold | Typical Value |
|-------|-----------|---------------|
| S/P Ratio | > 1.5× | 2.56× |
| P Noise | < 2.0% CV | 0.35% CV |
| S Noise | < 2.0% CV | 0.11% CV |
| Separation | > 50% of P | 8218 counts |

### Command Line Options
```bash
# Auto-load from stored calibration
python validate_stored_calibration.py

# Manual positions
python validate_stored_calibration.py --p-pwm 6 --s-pwm 69

# Quiet mode (minimal output)
python validate_stored_calibration.py --quiet

# Custom calibration file
python validate_stored_calibration.py --csv /path/to/calibration.csv
```

### Exit Codes
- `0` = PASS (all checks passed)
- `1` = FAIL (one or more checks failed)

Useful for automated testing:
```bash
python validate_stored_calibration.py --quiet
if [ $? -eq 0 ]; then
    echo "Calibration valid"
else
    echo "Calibration invalid - run full calibration"
fi
```

### Outputs
- `polarizer_validation_results.csv` - Validation results with timestamp

### Typical Results
```
Validating P position (PWM 6)...
  Mean: 5268.4 ± 18.2 counts
  Noise: 0.35% CV

Validating S position (PWM 69)...
  Mean: 13486.2 ± 15.1 counts
  Noise: 0.11% CV

S/P Ratio: 2.56× ✓
Overall: ✓✓✓ PASS ✓✓✓
Time: ~30 seconds
```

---

## Decision Flow Chart

```
START
  |
  ├─ Do you have stored calibration?
  │    |
  │    NO ──> Run FULL CALIBRATION (60s)
  │    |
  │    YES ──> Is this first use / major change?
  │             |
  │             YES ──> Run FULL CALIBRATION (60s)
  │             |
  │             NO ──> Run QUICK VALIDATION (30s)
  │                     |
  │                     PASS ──> System ready ✓
  │                     |
  │                     FAIL ──> Run FULL CALIBRATION (60s)
```

---

## Comparison Details

### Time Breakdown

**Full Calibration (~60s):**
- Stage 1 (bidirectional sweep): ~20s
- Stage 2 (type detection): <1s
- Stage 3 (refinement): ~40s
- **Total:** ~60s

**Quick Validation (~30s):**
- Hardware setup: ~5s
- P validation (20 measurements): ~12s
- S validation (20 measurements): ~12s
- **Total:** ~30s

### Measurement Details

| Aspect | Full Calibration | Quick Validation |
|--------|------------------|------------------|
| Positions tested | 52 (5 + 5 + 21 + 21) | 2 (P + S) |
| Scans per position | 1-10 | 20 |
| Total spectra | ~500 | 40 |
| Spectral analysis | Yes | Yes |
| Directional approach | Yes | Yes |
| Type detection | Yes | No |
| Stable range finding | Yes | No |

### Data Generated

**Full Calibration:**
- Complete intensity map across range
- Polarizer type classification
- P and S stable ranges
- Noise characterization at 42 positions
- Optimal middle positions

**Quick Validation:**
- P position verification (20 measurements)
- S position verification (20 measurements)
- Pass/fail status
- Timestamp for tracking

---

## Best Practices

### When to Run Full Calibration
- **First time:** Always establish baseline
- **After changes:** Polarizer replacement, mechanical adjustments
- **Periodically:** Annually or when drift suspected
- **Validation fails:** Quick validation indicates problem

### When to Use Quick Validation
- **Routine checks:** Daily, weekly, or before experiments
- **After transport:** Hardware moved to new location
- **After power cycle:** System restarted
- **Automated testing:** Part of CI/CD pipeline
- **Troubleshooting:** Quick system health check

### Recommended Schedule

| Frequency | Action |
|-----------|--------|
| **Daily** | Quick validation (if system used daily) |
| **Weekly** | Quick validation (minimum) |
| **Monthly** | Review validation logs for trends |
| **Quarterly** | Consider full calibration if drift observed |
| **Annually** | Full calibration (establish new baseline) |
| **After changes** | Full calibration (required) |

---

## Troubleshooting

### Quick Validation Fails

**Issue:** S/P ratio too low (< 1.5×)
- **Cause:** Positions drifted, hardware changed
- **Solution:** Run full calibration

**Issue:** Noise too high (> 2% CV)
- **Cause:** Mechanical vibration, unstable mount, LED instability
- **Solution:** Check mounting, LED power supply, run full calibration

**Issue:** Cannot load stored calibration
- **Cause:** No `polarizer_calibration_results.csv` file
- **Solution:** Run full calibration or specify positions with `--p-pwm` and `--s-pwm`

### Full Calibration Issues

**Issue:** Type detection incorrect
- **Cause:** Wrong dark threshold, unusual polarizer
- **Solution:** Check dark threshold (3000 counts for USB4000), review Stage 1 data

**Issue:** No stable range found
- **Cause:** Mechanical issues, wrong positions
- **Solution:** Check servo operation, LED brightness, repeat calibration

---

## Integration Examples

### Python Script
```python
import subprocess
import sys

# Run quick validation
result = subprocess.run(
    ['python', 'validate_stored_calibration.py', '--quiet'],
    capture_output=True
)

if result.returncode == 0:
    print("Calibration valid - proceeding with experiment")
    # Your experiment code here
else:
    print("Calibration invalid - running full calibration")
    subprocess.run(['python', 'calibrate_polarizer.py'])
    sys.exit(1)
```

### Shell Script (Bash)
```bash
#!/bin/bash

# Daily validation check
python validate_stored_calibration.py --quiet

if [ $? -eq 0 ]; then
    echo "$(date): Validation PASS" >> calibration.log
else
    echo "$(date): Validation FAIL - running full calibration" >> calibration.log
    python calibrate_polarizer.py
fi
```

### Automated Testing
```python
# pytest example
def test_polarizer_calibration():
    """Verify polarizer calibration is valid."""
    result = subprocess.run(
        ['python', 'validate_stored_calibration.py', '--quiet'],
        cwd='servo_polarizer_calibration'
    )
    assert result.returncode == 0, "Polarizer calibration invalid"
```

---

## Summary

- **Full Calibration:** Use for baseline establishment (60s, comprehensive)
- **Quick Validation:** Use for routine checks (30s, pass/fail)
- **Decision:** Run full calibration when validation fails or after major changes
- **Best Practice:** Daily/weekly validation + annual full calibration
