# Polarizer Calibration Algorithm Optimization

## Current Implementation Issues

### 1. **Inefficient Sequential Sweep**
- **Current**: Sweeps through ALL positions 10-255 in steps of 5 (49 positions)
- **Time**: ~3 minutes (2 measurements per position + servo settling)
- **Problem**: Wastes time measuring positions that clearly block light

### 2. **Low S/P Ratio (1.79×)**
Your hardware only achieves 1.79× ratio when it should be >3.0×. This suggests:
- Polarizer might not be properly aligned with optical path
- Current positions (50, 139) aren't optimal transmission angles
- Hardware may have mechanical limitations

### 3. **Fixed Step Size**
- Uses 5-position steps throughout entire range
- Doesn't adapt to find precise peak centers

## Proposed Optimizations

### **Optimization 1: Coarse-to-Fine Sweep (3×-5× faster)**

```python
def run_calibration_optimized(self) -> dict:
    """Optimized polarizer calibration using coarse-to-fine strategy."""

    # PHASE 1: Coarse sweep (step=10) - Find approximate peak regions
    # Range: 10-255 in steps of 10 → ~25 measurements
    # Time: ~45 seconds (vs 3 minutes)

    # PHASE 2: Fine sweep around detected peaks (step=2)
    # Refine ±20 positions around each peak → ~40 additional measurements
    # Time: ~60 seconds

    # Total: ~105 seconds (vs 180 seconds) = **40% faster**
```

### **Optimization 2: Adaptive Thresholding**

```python
# Skip positions with intensity < 20% of current max
# Most positions block light (near zero) - no need to measure them all
# Estimated speedup: 50-60% fewer measurements
```

### **Optimization 3: Parallel Measurements (if hardware supports)**

```python
# Measure both S and P at same servo positions simultaneously
# Potential 2× speedup if hardware allows
```

### **Optimization 4: Peak Detection Improvements**

```python
# Current: Uses scipy peak detection with fixed prominence=200
# Better: Adaptive prominence based on signal statistics
# Benefit: More reliable peak detection, especially with low S/P ratios
```

## Recommended Algorithm

### **Two-Phase Adaptive Search**

```python
def run_calibration_two_phase(self):
    """Two-phase adaptive polarizer calibration.

    Phase 1: Coarse sweep to identify peak regions
    Phase 2: Fine refinement around peaks
    """

    # === PHASE 1: COARSE SWEEP ===
    logger.info("Phase 1: Coarse sweep (step=10)...")
    coarse_step = 10
    coarse_range = range(10, 256, coarse_step)

    coarse_intensities = []
    coarse_positions = []

    for pos in coarse_range:
        # Set position
        self.ctrl.servo_set(s=pos, p=(pos + 128) % 256)
        time.sleep(0.3)

        # Measure
        self.ctrl.set_mode("s")
        time.sleep(0.2)
        intensity = self.spec.intensities().max()

        coarse_intensities.append(intensity)
        coarse_positions.append(pos)

        # Early termination if we find clear peaks
        if len(coarse_intensities) > 10:
            # Check if we have two distinct peaks
            peaks, _ = find_peaks(coarse_intensities, prominence=500)
            if len(peaks) >= 2:
                logger.info(f"  Found {len(peaks)} peaks early, skipping rest of coarse sweep")
                break

    # Identify peak regions
    peaks, properties = find_peaks(
        coarse_intensities,
        prominence=np.std(coarse_intensities) * 2,  # Adaptive
        width=2
    )

    if len(peaks) < 2:
        logger.error("Failed to find two peaks in coarse sweep")
        return None

    # Select two highest peaks
    peak_heights = [coarse_intensities[p] for p in peaks]
    top_2_indices = np.argsort(peak_heights)[-2:]
    peak_regions = [coarse_positions[peaks[i]] for i in top_2_indices]

    logger.info(f"  Identified peak regions: {peak_regions}")

    # === PHASE 2: FINE REFINEMENT ===
    logger.info("Phase 2: Fine refinement (step=2)...")

    refined_positions = []
    for center_pos in peak_regions:
        # Search ±15 positions around peak center
        fine_range = range(max(10, center_pos - 15),
                          min(255, center_pos + 15),
                          2)

        fine_intensities = []
        fine_pos = []

        for pos in fine_range:
            self.ctrl.servo_set(s=pos, p=(pos + 128) % 256)
            time.sleep(0.2)  # Faster settling for small moves

            self.ctrl.set_mode("s")
            time.sleep(0.15)
            intensity = self.spec.intensities().max()

            fine_intensities.append(intensity)
            fine_pos.append(pos)

        # Find peak maximum in fine scan
        max_idx = np.argmax(fine_intensities)
        refined_pos = fine_pos[max_idx]
        refined_positions.append(refined_pos)

        logger.info(f"  Refined peak: {center_pos} → {refined_pos} "
                   f"({fine_intensities[max_idx]:.0f} counts)")

    return refined_positions
```

## Performance Comparison

| Method | Measurements | Time | Pros | Cons |
|--------|-------------|------|------|------|
| **Current (Sequential)** | 49 | ~3 min | Simple, complete coverage | Slow, measures many blocked positions |
| **Coarse-to-Fine** | ~65 | ~1.8 min | 40% faster, same accuracy | Slightly more complex |
| **Adaptive Threshold** | ~30 | ~1 min | 65% faster | May miss weak peaks |
| **Recommended (Two-Phase)** | ~40 | ~1.2 min | 60% faster, more reliable | Best balance |

## Implementation Recommendation

Use **Two-Phase Adaptive** because:
1. **60% faster** (1.2 min vs 3 min)
2. **More robust** - adaptive thresholding handles varying signal levels
3. **Better precision** - fine refinement finds true peak centers
4. **Early termination** - can stop coarse sweep when peaks are obvious

## Your Low S/P Ratio Issue (1.79×)

The fundamental problem is **hardware alignment**, not the algorithm:

### Possible Causes:
1. **Polarizer not perpendicular** to optical path
2. **Servo mounting angle** not optimal
3. **Optical fiber position** not aligned with polarizer
4. **Internal reflection** reducing contrast

### Solutions:
1. **Try wider position search** - maybe optimal positions are outside 50-139 range
2. **Mechanical adjustment** - physically rotate polarizer mount
3. **Accept lower ratio** - if hardware limited, calibrate with current positions
4. **Add note to validation** - warn users if ratio < 2.0

Would you like me to:
1. Implement the optimized two-phase algorithm?
2. Add a wider search range to find better positions?
3. Both?
