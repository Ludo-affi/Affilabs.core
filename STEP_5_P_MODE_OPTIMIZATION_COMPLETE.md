# Step 5: P-Mode Optimization - COMPLETE REPLACEMENT

## Summary

**COMPLETELY OBLITERATED** old Step 5 (dark noise re-measurement) and replaced with new **P-Mode Optimization** step. This shifts all subsequent steps down by one number.

## New Calibration Flow (After This Change)

```
STEP 1: Dark Noise Baseline (Before LEDs)
STEP 2: Wavelength Range Calibration
STEP 3: LED Brightness Ranking
STEP 4: Integration Time Optimization (S-mode)
STEP 5: P-MODE OPTIMIZATION ← NEW! (was Step 8)
STEP 6: S-Mode Reference Signals (was Step 7)
STEP 7: P-Mode QC and Validation (was Step 8B/8C)
```

## What Step 5 Does Now

### **STEP 5: P-Mode Optimization (Transfer S-Mode + Boost)**

**Purpose**: Optimize P-mode parameters by transferring S-mode baseline and boosting LED intensities to maximize signal without saturation.

**Algorithm**:

1. **Switch to P-polarization** (servo to P-mode position)

2. **Transfer S-mode parameters (100% baseline)**:
   - LED intensities → `p_led_intensities` (copy of S-mode)
   - Integration time → `p_integration_time` (copy of S-mode)

3. **Boost LED intensities iteratively**:
   - Target: Weakest LED near 255 (proof of optimization)
   - Constraint: All channels <95% saturation
   - Max iterations: 10
   - Boost factor: Up to 10% per iteration

4. **Check for saturation**:
   - Measure all channels at current LED intensities
   - If any channel >95% → stop boosting
   - If weakest LED ≥250 → optimization complete

5. **Optional integration time increase** (if needed):
   - If weakest LED <240 and no saturation detected
   - Try increasing integration time by +5% (up to +10% max)
   - Re-test to ensure no saturation
   - Constraint: `p_integration_time ≤ s_integration_time × 1.10`

6. **Save P-mode raw data per channel**:
   - Measure each channel with `num_scans` averaging
   - Apply spectral filter (SPR range)
   - Store in `result.p_ref_sig`
   - Store LED intensities in `result.p_mode_intensity`

7. **Measure dark-ref at final P-mode integration time**:
   - Turn ALL LEDs OFF
   - Measure dark with `dark_scans` averaging
   - Store in `result.dark_noise` and `result.p_dark_ref`
   - **QC check**: Verify dark mean ≈ 3200 counts (2500-4000 range)

## Code Implementation

### New Step 5 (Lines 1455-1740)

```python
# ===================================================================
# STEP 5: P-MODE OPTIMIZATION (TRANSFER S-MODE + BOOST)
# ===================================================================

# 1. Switch to P-mode
switch_mode_safely(ctrl, "p", turn_off_leds=True)

# 2. Transfer S-mode parameters (100% baseline)
p_led_intensities = led_intensities.copy()  # From Step 4
p_integration_time = result.integration_time  # From Step 4

# 3. Boost LED intensities iteratively
for iteration in range(MAX_P_ITERATIONS):
    # Test all channels
    for ch in ch_list:
        ctrl.set_intensity(ch=ch, raw_val=p_led_intensities[ch])
        spectrum = usb.read_spectrum()
        max_signal = spectrum[wave_min_index:wave_max_index].max()
        signal_percent = (max_signal / detector_max) * 100

        # Check saturation
        if signal_percent > 95:
            saturation_detected = True

    # Check if optimized
    if saturation_detected or p_led_intensities[weakest_ch] >= 250:
        break

    # Boost all LEDs proportionally
    boost_factor = min(1.1, (255 / p_led_intensities[weakest_ch]))
    for ch in ch_list:
        p_led_intensities[ch] = min(255, int(p_led_intensities[ch] * boost_factor))

# 4. Optional integration time increase (if weakest LED <240)
if p_led_intensities[weakest_ch] < 240 and not saturation_detected:
    test_integration = min(max_p_integration, p_integration_time * 1.05)
    # Test and apply if no saturation

# 5. Save P-mode raw data per channel
p_ref_signals = {}
for ch in ch_list:
    ctrl.set_intensity(ch=ch, raw_val=p_led_intensities[ch])

    # Average multiple scans
    scan_accumulator = []
    for scan_idx in range(result.num_scans):
        spectrum = usb.read_spectrum()
        scan_accumulator.append(spectrum)

    avg_spectrum = np.mean(scan_accumulator, axis=0)
    filtered_spectrum = avg_spectrum[wave_min_index:wave_max_index]
    p_ref_signals[ch] = filtered_spectrum

result.p_ref_sig = p_ref_signals
result.p_mode_intensity = p_led_intensities
result.p_integration_time = p_integration_time

# 6. Measure dark-ref
ctrl.turn_off_channels()

dark_ref_accumulator = []
for scan_idx in range(dark_ref_scans):
    raw_spectrum = usb.read_spectrum()
    dark_ref_accumulator.append(raw_spectrum)

p_dark_ref = np.mean(dark_ref_accumulator, axis=0)
p_dark_ref_filtered = p_dark_ref[wave_min_index:wave_max_index]

result.dark_noise = p_dark_ref_filtered
result.p_dark_ref = p_dark_ref_filtered

# QC check
dark_mean = np.mean(p_dark_ref_filtered)
if 2500 <= dark_mean <= 4000:
    logger.info("✅ Dark-ref within expected range")
else:
    logger.warning("⚠️ Dark-ref outside expected range")
```

## Updated Step Numbering

### **OLD** (Before This Change):
```
Step 5: Re-measure Dark Noise (GitHub Step 5)
Step 6: Apply LED Calibration (GitHub Step 6, no-op)
Step 7: Measure S-Mode References (GitHub Step 7)
Step 8: P-Mode Calibration (GitHub Step 8)
  8A: P-mode LED optimization
  8B: Polarity detection
  8C: QC metrics
```

### **NEW** (After This Change):
```
Step 5: P-MODE OPTIMIZATION ← NEW!
  • Switch to P-mode
  • Transfer S-mode parameters (100%)
  • Boost LED intensities (iterative)
  • Optional integration time increase (+10% max)
  • Save P-mode raw data per channel
  • Measure dark-ref at P-mode integration time

Step 6: S-Mode Reference Signals (was Step 7)
  • Switch back to S-mode
  • Measure S-refs with S-mode LED/integration
  • Validate S-ref quality

Step 7: P-Mode QC and Validation (was Step 8B/8C)
  • Polarity detection
  • FWHM measurement
  • SNR calculation
  • LED health baseline
```

## Data Flow

**Step 4 → Step 5**:
```python
# Step 4 outputs:
led_intensities = {ch: led_value}  # S-mode LED intensities
result.integration_time = X  # S-mode integration time (ms)

# Step 5 receives:
p_led_intensities = led_intensities.copy()  # 100% baseline
p_integration_time = result.integration_time  # Start with S-mode

# Step 5 outputs:
result.p_mode_intensity = {ch: boosted_led_value}  # Optimized P-mode LEDs
result.p_integration_time = Y  # P-mode integration (≤ X × 1.10)
result.p_ref_sig = {ch: spectrum}  # P-mode raw data
result.p_dark_ref = spectrum  # Dark at P-mode integration
```

**Step 5 → Step 6**:
```python
# Step 6 receives:
led_intensities  # S-mode LEDs (from Step 4, still in scope)
result.integration_time  # S-mode integration
result.dark_noise  # Dark-ref from Step 5

# Step 6 outputs:
result.s_ref_sig = {ch: spectrum}  # S-mode references
```

## Key Benefits

1. **✅ Clean P-Mode Optimization**: Dedicated step for P-mode parameter tuning
2. **✅ Baseline Transfer**: Start with proven S-mode parameters (100%)
3. **✅ Iterative Boosting**: Safe, incremental LED increases with saturation checks
4. **✅ Integration Time Flexibility**: Allow up to +10% increase if needed
5. **✅ Per-Channel Raw Data**: Save P-mode spectra for each channel
6. **✅ Dark-Ref QC**: Validate dark noise at P-mode integration time
7. **✅ Proof of Optimization**: Weakest LED near 255 confirms max signal extraction

## QC Checks

### **P-Mode Signal Validation**:
- All channels <95% saturation (prevents detector clipping)
- Weakest LED ≥250 (proof of optimization, within 2% of max)
- Integration time ≤ S-mode × 1.10 (max +10% increase)

### **Dark-Ref Validation**:
- Mean: 2500-4000 counts (typical Ocean Optics range)
- If outside range:
  - Too high (>4000): LEDs not fully off, light leak, detector issue
  - Too low (<2500): Detector offset drift, temperature change

## Testing Checklist

- [ ] Step 5 executes without errors
- [ ] P-mode LED boosting converges (≤10 iterations)
- [ ] Weakest LED reaches ≥250 intensity
- [ ] No saturation detected (all channels <95%)
- [ ] Integration time increase works (if needed)
- [ ] P-mode raw data saved for all channels
- [ ] Dark-ref measured and validated (2500-4000 counts)
- [ ] Step 6 (S-ref) executes correctly after Step 5
- [ ] Data flow Step 4→5→6 verified

---

**Date**: November 27, 2025
**Status**: ✅ COMPLETE - Step 5 P-Mode Optimization implemented
**Next**: Test with hardware to validate P-mode boosting algorithm
