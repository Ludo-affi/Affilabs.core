# SPR Resonance Dip Algorithm - CORRECTED

## The Fundamental Principle

In Surface Plasmon Resonance (SPR), we are looking for a **SINGLE MINIMUM** in transmission, not peaks:

- **P position** = **MINIMUM transmission** (resonance dip at ~620nm)
- **S position** = **MAXIMUM transmission** (reference, no resonance)

## Why This Matters

The previous algorithm was **WRONG** - it looked for 2 peaks (maxima) and tried to determine which was "higher" and "lower". This doesn't match SPR physics:

### ❌ Old (Incorrect) Approach
```python
# WRONG: Looking for peaks (maxima)
peaks = find_peaks(intensities)[0]
prominences = peak_prominences(intensities, peaks)
prominent_peaks = prominences[0].argsort()[-2:]  # Get 2 most prominent
# Then try to figure out which is S and which is P...
```

### ✅ New (Correct) Approach
```python
# CORRECT: Look for single minimum (resonance dip)
min_idx = np.argmin(intensities)  # P position = MINIMUM
p_position = positions[min_idx]
p_intensity = intensities[min_idx]

# And single maximum (reference)
max_idx = np.argmax(intensities)  # S position = MAXIMUM
s_position = positions[max_idx]
s_intensity = intensities[max_idx]
```

## Algorithm Details

### 1. Find Resonance Dip (P Position)
```python
min_idx = np.argmin(intensities)
p_position = positions[min_idx]
p_intensity = intensities[min_idx]
```

**Validation**: Check dip depth is significant
```python
dip_depth = intensities.max() - p_intensity
dip_depth_percent = (dip_depth / intensities.max()) * 100

if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:  # e.g., 10%
    # Fail - no clear resonance
```

### 2. Find Reference Maximum (S Position)
```python
max_idx = np.argmax(intensities)
s_position = positions[max_idx]
s_intensity = intensities[max_idx]
```

### 3. Validate Separation
```python
separation = abs(s_position - p_position)

if separation < 65 or separation > 95:  # Expected ~80° apart
    # Fail - positions not physically reasonable
```

### 4. Validate S/P Ratio
```python
sp_ratio = s_intensity / p_intensity

if sp_ratio < 1.3:  # S should be significantly higher than P
    # Fail - resonance not deep enough
```

## Physical Interpretation

```
Intensity vs Servo Position (SPR with sample)

    High ──┐     ┌── S position (MAXIMUM)
           │     │   Reference, no resonance
           │     │   HIGH transmission
           │     │
    Mid ───┤     │
           │     │
           │     │         ┌── Resonance dip width
    Low ───┴─────┴────────┘
                          └── P position (MINIMUM)
                               Resonance at sample
                               LOW transmission

           10°         90°         170°
           └───────────┴───────────┘
              Servo sweep range
```

## Key Differences from OLD Algorithm

| Aspect | OLD (Wrong) | NEW (Correct) |
|--------|-------------|---------------|
| **What to find** | 2 peaks (maxima) | 1 minimum + 1 maximum |
| **P position** | "Lower" of 2 peaks | **Global minimum** |
| **S position** | "Higher" of 2 peaks | **Global maximum** |
| **Scipy functions** | `find_peaks`, `peak_prominences`, `peak_widths` | `np.argmin`, `np.argmax` |
| **Complexity** | High (peak detection, sorting, edge calculation) | Low (simple min/max) |
| **Robustness** | Sensitive to noise, multiple peaks | Direct, unambiguous |
| **Validation** | Peak count, prominence, separation | Dip depth, separation, ratio |

## Configuration Parameters

```python
# Sweep parameters
MIN_ANGLE = 10              # Start of servo sweep
MAX_ANGLE = 170             # End of servo sweep
ANGLE_STEP = 5              # Step size

# Validation thresholds
MIN_SEPARATION = 65         # Minimum S-P separation (degrees)
MAX_SEPARATION = 95         # Maximum S-P separation (degrees)
MIN_SP_RATIO = 1.3          # Minimum S/P intensity ratio
IDEAL_SP_RATIO = 1.5        # Ideal S/P intensity ratio
MIN_DIP_DEPTH_PERCENT = 10.0  # Minimum resonance dip depth (%)
```

## Example Output

```
================================================================================
RESONANCE DIP ANALYSIS (SPR)
================================================================================

1. Finding Resonance Dip (P position):
   P position (MINIMUM): 55°
   P intensity: 28000 counts (LOW - resonance dip)
   Dip depth: 20000 counts (41.7% of maximum)
   ✓ PASS: Significant resonance dip detected

2. Finding Reference Maximum (S position):
   S position (MAXIMUM): 145°
   S intensity: 48000 counts (HIGH - reference)

3. Position Separation:
   Measured: 90°
   Expected: 65-95°
   ✓ PASS: Separation is valid

4. Intensity Verification:
   S-mode intensity: 48000 (HIGH - reference)
   P-mode intensity: 28000 (LOW - resonance)
   ✓ PASS: S is higher than P

5. S/P Ratio:
   Measured: 1.71×
   Minimum: 1.30×
   Ideal: 1.50×
   ✓ PASS: Ratio is ideal

================================================================================
✅ ALL VALIDATIONS PASSED
================================================================================
   S position: 145° (HIGH transmission)
   P position: 55° (LOW transmission - resonance dip)
   S/P ratio: 1.71×
```

## Testing

Run the corrected test script:
```bash
# Basic test
python test_servo_calibration.py

# Force full calibration (skip EEPROM check)
python test_servo_calibration.py --force

# Save to EEPROM after success
python test_servo_calibration.py --save
```

## Next Steps

1. **Test the script** with your hardware to verify the resonance dip is correctly identified
2. **Review the output** - the P position should correspond to the lowest transmission point
3. **Port to main.py** once validated - replace the incorrect peak-finding algorithm with this simple min/max approach

## Critical Insight

The confusion came from the NEW software's comments mentioning "LOWER transmission" for P-mode. This refers to **during measurement with a sample**, not during calibration. During **calibration without a sample**, we're setting up the servo positions so that later, when measuring:
- P-mode will show the resonance dip (sample interaction)
- S-mode will show high transmission (reference)

But the calibration itself finds these positions by looking for where the **minimum** and **maximum** transmission occur across the servo sweep range.
