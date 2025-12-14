# Smart Calibration QC System - S-Reference Based

## 🎯 Core Concept
**Use stored S-mode reference spectra as quality control baseline.**

When user clicks "Calibrate":
1. Load stored S-ref spectra from device_config.json
2. Measure fresh S-ref spectra (water + prism required)
3. Compare: **Intensity** (within 5%) + **Spectral Shape** (correlation)
4. **Pass** → Use stored LED values (skip 2-3 min calibration)
5. **Fail** → Run full recalibration

---

## 📋 What Gets Stored in device_config.json

```json
{
  "led_calibration": {
    "calibration_date": "2025-10-22T14:30:00",
    "integration_time_ms": 32,
    "s_mode_intensities": {
      "A": 128,
      "B": 128,
      "C": 128,
      "D": 128
    },
    "p_mode_intensities": {
      "A": 172,
      "B": 185,
      "C": 192,
      "D": 199
    },
    "s_ref_baseline": {
      "A": [array of 1000+ pixels],
      "B": [array of 1000+ pixels],
      "C": [array of 1000+ pixels],
      "D": [array of 1000+ pixels]
    },
    "s_ref_max_intensity": {
      "A": 41250,
      "B": 42100,
      "C": 39800,
      "D": 40500
    }
  }
}
```

**Note**: S-ref spectra are ~1000 pixels (580-720nm SPR range) × 4 channels = ~32KB JSON data

---

## ✅ Two-Stage QC Validation

### Stage 1: Intensity Check (Critical)
**Purpose**: Detect LED degradation, detector drift, optical misalignment

```python
def validate_intensity(current_s_ref, baseline_s_ref) -> tuple[bool, float]:
    """
    Check if current S-ref intensity matches baseline within 5%.

    Returns:
        (passed, percent_deviation)
    """
    current_max = np.max(current_s_ref)
    baseline_max = stored_config['s_ref_max_intensity'][channel]

    deviation = abs(current_max - baseline_max) / baseline_max
    percent_dev = deviation * 100

    passed = percent_dev < 5.0  # 5% threshold

    return passed, percent_dev
```

**Pass**: Within 5% of baseline intensity
**Fail**: >5% deviation → Recalibrate

**Why 5%?**
- LED aging: ~1-2% per month (5% = ~3 months)
- Measurement noise: ~1-2%
- Optical drift: ~1%
- **Total budget: 5% is reasonable threshold**

---

### Stage 2: Spectral Shape Check (Important)
**Purpose**: Detect LED spectral shift, polarizer misalignment, optical contamination

```python
def validate_spectral_shape(current_s_ref, baseline_s_ref) -> tuple[bool, float]:
    """
    Check if current S-ref spectral shape matches baseline.

    Uses Pearson correlation coefficient to compare normalized spectra.

    Returns:
        (passed, correlation)
    """
    # Normalize both spectra to unit amplitude
    current_norm = current_s_ref / np.max(current_s_ref)
    baseline_norm = baseline_s_ref / np.max(baseline_s_ref)

    # Calculate Pearson correlation
    correlation = np.corrcoef(current_norm, baseline_norm)[0, 1]

    passed = correlation > 0.98  # 98% similarity

    return passed, correlation
```

**Pass**: Correlation > 0.98 (98% shape similarity)
**Fail**: Correlation ≤ 0.98 → Recalibrate

**Why Pearson correlation?**
- Intensity-independent (already checked in Stage 1)
- Detects spectral shifts (LED phosphor degradation)
- Detects polarizer rotation (changes spectral shape)
- Simple, fast, interpretable

---

## 🚀 Validation Workflow

```
User clicks "Calibrate"
    ↓
Check device_config.json for stored S-ref baseline?
    ├─ No → Run full calibration
    │
    ├─ Yes → Quick QC validation
    │         ↓
    │    ┌─────────────────────────────────────────┐
    │    │ REMINDER: Ensure prism + water in place │
    │    │ [Continue] [Cancel]                     │
    │    └─────────────────────────────────────────┘
    │         ↓
    │    Load stored LED intensities + integration time
    │         ↓
    │    Set polarizer to S-mode
    │         ↓
    │    Measure S-ref for all 4 channels (10 spectra each)
    │         ↓
    │    FOR EACH CHANNEL:
    │         ├─ Stage 1: Intensity within 5%? ──┐
    │         └─ Stage 2: Shape correlation > 0.98? ─┤
    │                                                 │
    │    ┌────────────────────────────────────────────┘
    │    ↓
    │    ALL PASS?
    │    ├─ Yes → Use stored calibration (5-10 sec)
    │    │         Log: "QC PASSED - Using stored values"
    │    │
    │    └─ No → Run full calibration (2-3 min)
    │              Log: "QC FAILED - Recalibrating"
    │              Log failure details per channel
```

---

## 📊 QC Report Format

### If QC Passes:
```
================================================================================
CALIBRATION QC VALIDATION
================================================================================
Baseline date: 2025-10-15 14:30:00 (7 days ago)

Channel A:
  ✅ Intensity: 41,245 → 41,180 (0.2% deviation, pass)
  ✅ Shape: r=0.995 (excellent correlation, pass)

Channel B:
  ✅ Intensity: 42,100 → 41,950 (0.4% deviation, pass)
  ✅ Shape: r=0.993 (excellent correlation, pass)

Channel C:
  ✅ Intensity: 39,800 → 39,650 (0.4% deviation, pass)
  ✅ Shape: r=0.996 (excellent correlation, pass)

Channel D:
  ✅ Intensity: 40,500 → 40,420 (0.2% deviation, pass)
  ✅ Shape: r=0.994 (excellent correlation, pass)

✅ QC VALIDATION PASSED - Using stored calibration
   Integration time: 32ms
   S-mode LEDs: A=128, B=128, C=128, D=128
   P-mode LEDs: A=172, B=185, C=192, D=199

   Time saved: 2 min 45 sec
================================================================================
```

### If QC Fails:
```
================================================================================
CALIBRATION QC VALIDATION
================================================================================
Baseline date: 2025-09-10 14:30:00 (42 days ago)

Channel A:
  ✅ Intensity: 41,245 → 40,950 (0.7% deviation, pass)
  ✅ Shape: r=0.992 (good correlation, pass)

Channel B:
  ❌ Intensity: 42,100 → 39,800 (5.5% deviation, FAIL)
  ⚠️  Reason: LED degradation detected
  ✅ Shape: r=0.989 (good correlation, pass)

Channel C:
  ✅ Intensity: 39,800 → 39,200 (1.5% deviation, pass)
  ❌ Shape: r=0.965 (poor correlation, FAIL)
  ⚠️  Reason: Spectral shift detected

Channel D:
  ✅ Intensity: 40,500 → 40,150 (0.9% deviation, pass)
  ✅ Shape: r=0.993 (good correlation, pass)

❌ QC VALIDATION FAILED
   Failed channels: B (intensity), C (shape)
   Action: Running full recalibration...
================================================================================
```

---

## 🔧 Implementation Details

### Where to Store S-ref Arrays

**Option 1: device_config.json (Recommended)**
```json
"s_ref_baseline": {
  "A": [1234.5, 1245.2, ...],  // 1000 pixels
  "B": [2345.1, 2356.8, ...],
  "C": [3456.7, 3467.4, ...],
  "D": [4567.3, 4578.0, ...]
}
```
**Pros**: Single source of truth, easy to backup/restore
**Cons**: ~32KB JSON data (acceptable)

**Option 2: Separate .npy files + metadata in JSON**
```json
"s_ref_baseline_files": {
  "A": "generated-files/calibration_data/s_ref_baseline_a.npy",
  "B": "generated-files/calibration_data/s_ref_baseline_b.npy",
  "C": "generated-files/calibration_data/s_ref_baseline_c.npy",
  "D": "generated-files/calibration_data/s_ref_baseline_d.npy"
}
```
**Pros**: Smaller JSON, faster numpy loading
**Cons**: Multiple files to manage

**Recommendation**: Use Option 1 (JSON) for simplicity. 32KB is negligible.

---

### Code Structure

**File**: `utils/device_configuration.py`

```python
def save_calibration_baseline(
    self,
    integration_time_ms: int,
    s_mode_intensities: dict[str, int],
    p_mode_intensities: dict[str, int],
    s_ref_spectra: dict[str, np.ndarray]
) -> None:
    """
    Save LED calibration + S-ref baseline to device_config.json.

    Args:
        integration_time_ms: Calibrated integration time
        s_mode_intensities: LED intensities for S-mode (per channel)
        p_mode_intensities: LED intensities for P-mode (per channel)
        s_ref_spectra: S-mode reference spectra (per channel)
    """
    self.config['led_calibration'] = {
        'calibration_date': datetime.now().isoformat(),
        'integration_time_ms': integration_time_ms,
        's_mode_intensities': s_mode_intensities,
        'p_mode_intensities': p_mode_intensities,
        's_ref_baseline': {
            ch: spec.tolist() for ch, spec in s_ref_spectra.items()
        },
        's_ref_max_intensity': {
            ch: float(np.max(spec)) for ch, spec in s_ref_spectra.items()
        }
    }
    self._save_config()

def load_calibration_baseline(self) -> Optional[dict]:
    """Load LED calibration + S-ref baseline from device_config.json."""
    if 'led_calibration' not in self.config:
        return None

    cal = self.config['led_calibration']

    # Convert lists back to numpy arrays
    if 's_ref_baseline' in cal:
        cal['s_ref_baseline'] = {
            ch: np.array(spec) for ch, spec in cal['s_ref_baseline'].items()
        }

    return cal
```

**File**: `utils/spr_calibrator.py`

```python
def validate_s_ref_qc(
    self,
    baseline_config: dict,
    num_samples: int = 10
) -> tuple[bool, dict[str, dict]]:
    """
    Quick QC validation using S-mode reference spectra.

    Requires: Prism + water in place, same as full calibration.

    Args:
        baseline_config: Stored calibration from device_config.json
        num_samples: Number of spectra to average per channel (default: 10)

    Returns:
        (all_passed, channel_results)

        channel_results format:
        {
          'A': {
            'intensity_pass': True,
            'intensity_deviation': 0.2,
            'shape_pass': True,
            'shape_correlation': 0.995,
            'overall_pass': True
          },
          ...
        }
    """
    logger.info("="*80)
    logger.info("CALIBRATION QC VALIDATION (S-REF BASED)")
    logger.info("="*80)

    # Load baseline
    baseline_s_ref = baseline_config['s_ref_baseline']
    baseline_max = baseline_config['s_ref_max_intensity']
    baseline_date = baseline_config['calibration_date']

    logger.info(f"Baseline date: {baseline_date}")
    logger.info(f"Measuring fresh S-ref spectra (prism + water required)...")

    # Set polarizer to S-mode
    self.ctrl.set_mode('s')
    time.sleep(2.0)

    # Load stored LED intensities + integration time
    s_intensities = baseline_config['s_mode_intensities']
    integration_ms = baseline_config['integration_time_ms']

    self.usb.set_integration_time(integration_ms / 1000.0)
    logger.info(f"Using stored integration time: {integration_ms}ms")

    channel_results = {}
    all_passed = True

    for ch in CH_LIST:
        logger.info(f"\nValidating Channel {ch}:")

        # Turn on LED with stored intensity
        self.ctrl.turn_on_channel(ch.lower())
        self.ctrl.set_intensity(ch.lower(), s_intensities[ch])
        time.sleep(1.0)

        # Measure fresh S-ref (average of num_samples)
        spectra = []
        for _ in range(num_samples):
            raw = self.usb.read_spectrum()
            spectra.append(raw)
            time.sleep(0.1)

        current_s_ref = np.mean(spectra, axis=0)

        # Apply dark noise correction
        if self.state.dark_noise is not None:
            current_s_ref = current_s_ref - self.state.dark_noise

        # Stage 1: Intensity check
        current_max = float(np.max(current_s_ref))
        baseline_max_val = baseline_max[ch]
        intensity_deviation = abs(current_max - baseline_max_val) / baseline_max_val
        intensity_percent = intensity_deviation * 100
        intensity_pass = intensity_percent < 5.0

        logger.info(f"  Intensity: {baseline_max_val:.0f} → {current_max:.0f} "
                   f"({intensity_percent:.1f}% deviation, "
                   f"{'pass' if intensity_pass else 'FAIL'})")

        # Stage 2: Spectral shape check
        current_norm = current_s_ref / np.max(current_s_ref)
        baseline_norm = baseline_s_ref[ch] / np.max(baseline_s_ref[ch])
        correlation = np.corrcoef(current_norm, baseline_norm)[0, 1]
        shape_pass = correlation > 0.98

        logger.info(f"  Shape: r={correlation:.3f} "
                   f"({'excellent' if correlation > 0.99 else 'good'} correlation, "
                   f"{'pass' if shape_pass else 'FAIL'})")

        # Overall pass
        overall_pass = intensity_pass and shape_pass

        if not intensity_pass:
            logger.warning(f"  ⚠️  Reason: LED degradation or detector drift")
        if not shape_pass:
            logger.warning(f"  ⚠️  Reason: Spectral shift or polarizer misalignment")

        # Turn off channel
        self.ctrl.turn_off_channel(ch.lower())

        # Store results
        channel_results[ch] = {
            'intensity_pass': intensity_pass,
            'intensity_deviation': intensity_percent,
            'shape_pass': shape_pass,
            'shape_correlation': correlation,
            'overall_pass': overall_pass
        }

        if not overall_pass:
            all_passed = False

    logger.info("="*80)

    if all_passed:
        logger.info("✅ QC VALIDATION PASSED - Using stored calibration")
    else:
        failed = [ch for ch, r in channel_results.items() if not r['overall_pass']]
        logger.warning(f"❌ QC VALIDATION FAILED - Channels: {', '.join(failed)}")
        logger.warning("   Running full recalibration...")

    return all_passed, channel_results


def run_full_calibration(
    self,
    force_recalibrate: bool = False,
    ...
) -> tuple[bool, str]:
    """
    Smart calibration with optional S-ref QC validation.
    """

    # NEW: Try QC validation first (unless forced)
    if not force_recalibrate:
        device_config = DeviceConfiguration()
        baseline = device_config.load_calibration_baseline()

        if baseline:
            logger.info("🔍 Found stored calibration, running S-ref QC validation...")
            logger.info("📋 ENSURE: Prism + water in place for validation")

            # Run QC validation
            passed, results = self.validate_s_ref_qc(baseline)

            if passed:
                logger.info("✅ QC passed - Loading stored calibration")

                # Load stored values into calibration state
                self.state.integration = baseline['integration_time_ms']
                self.state.leds_calibrated = baseline['s_mode_intensities']
                self.state.pol_intensity = baseline['p_mode_intensities']
                self.state.ref_sig = baseline['s_ref_baseline']

                # Mark as calibrated
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()

                logger.info(f"   Time saved: ~2-3 minutes")
                return True, ""
            else:
                logger.warning("❌ QC failed - Running full recalibration")

    # Continue with full calibration (existing code)
    logger.info("🔧 Starting full calibration workflow...")
    ...
```

---

## 🎯 User Interaction Flow

### UI Dialog (When QC Available)

```
┌────────────────────────────────────────────────────────────┐
│  Calibration Options                                       │
│                                                            │
│  Found calibration from 2025-10-15 (7 days ago)           │
│                                                            │
│  ✓ Integration time: 32 ms                                │
│  ✓ S-mode LEDs: 128 (all channels)                       │
│  ✓ P-mode LEDs: 172-199                                  │
│                                                            │
│  ⚠️  IMPORTANT: Ensure prism + water in place             │
│                                                            │
│  [ Quick QC (10s) ]  [ Full Calibration (3min) ]         │
│                                                            │
│  ℹ️  Quick QC validates stored calibration is still good │
└────────────────────────────────────────────────────────────┘
```

### After QC Pass

```
┌────────────────────────────────────────────────────────────┐
│  QC Validation Complete                                    │
│                                                            │
│  ✅ All channels passed QC validation                     │
│                                                            │
│  Channel A: 0.2% intensity deviation, r=0.995 ✅          │
│  Channel B: 0.4% intensity deviation, r=0.993 ✅          │
│  Channel C: 0.4% intensity deviation, r=0.996 ✅          │
│  Channel D: 0.2% intensity deviation, r=0.994 ✅          │
│                                                            │
│  Using stored calibration.                                │
│  Time saved: 2 min 45 sec                                 │
│                                                            │
│              [Start Measurement]                          │
└────────────────────────────────────────────────────────────┘
```

### After QC Fail

```
┌────────────────────────────────────────────────────────────┐
│  QC Validation Failed                                      │
│                                                            │
│  ❌ Channel B: 5.5% intensity deviation (threshold: 5%)  │
│     Reason: LED degradation detected                      │
│                                                            │
│  ❌ Channel C: Shape correlation 0.965 (threshold: 0.98) │
│     Reason: Spectral shift or polarizer misalignment     │
│                                                            │
│  Running full recalibration...                           │
│  This will take approximately 2-3 minutes.               │
│                                                            │
│              [Continue]                                   │
└────────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Checks Summary

| Check | Method | Pass Threshold | What It Detects |
|-------|--------|----------------|-----------------|
| **Intensity** | Compare max counts | Within 5% | LED aging, detector drift, optical misalignment |
| **Spectral Shape** | Pearson correlation | r > 0.98 | LED spectral shift, polarizer rotation, contamination |
| **Combined** | Both must pass | AND logic | Overall optical system health |

---

## 🚀 Benefits of S-Ref Based QC

### Advantages
1. ✅ **Simple**: Only need S-mode spectra (already measured in calibration)
2. ✅ **Fast**: 10 spectra × 4 channels = ~5-10 seconds
3. ✅ **Comprehensive**: Validates entire optical path (LED → prism → detector)
4. ✅ **Polarizer check**: Wrong polarization changes spectral shape
5. ✅ **Single measurement condition**: S-mode only (P-mode derived from S)
6. ✅ **Water requirement**: Same as calibration (ensures consistency)

### What It Validates
- ✅ LED intensity stable (within 5%)
- ✅ LED spectral profile unchanged
- ✅ Polarizer in S-position (shape would differ if in P)
- ✅ Detector sensitivity unchanged
- ✅ Optical alignment maintained
- ✅ Prism clean (contamination would change shape)

---

## 📝 Implementation Checklist

### Phase 1: Storage (1 hour)
- [ ] Add `led_calibration` section to device_config.json
- [ ] Implement `save_calibration_baseline()` method
- [ ] Implement `load_calibration_baseline()` method
- [ ] Update Step 7 (S-ref measurement) to save baseline

### Phase 2: QC Validation (2 hours)
- [ ] Implement `validate_s_ref_qc()` method
- [ ] Add intensity deviation calculation
- [ ] Add spectral shape correlation
- [ ] Add per-channel pass/fail logic
- [ ] Add comprehensive logging

### Phase 3: Integration (1 hour)
- [ ] Modify `run_full_calibration()` to check for baseline
- [ ] Add QC validation before full calibration
- [ ] Load stored values if QC passes
- [ ] Add "force recalibration" option

### Phase 4: UI (1 hour)
- [ ] Add QC validation dialog
- [ ] Show QC results (pass/fail per channel)
- [ ] Display time saved
- [ ] Add "Quick QC" vs "Full Calibration" buttons

### Phase 5: Testing (1 hour)
- [ ] Test with recent calibration (should pass)
- [ ] Test with aged LEDs (should fail intensity)
- [ ] Test with wrong polarizer position (should fail shape)
- [ ] Verify full recalibration runs if QC fails

---

## 🎯 Success Criteria

**QC Performance**:
- ✅ QC completes in < 15 seconds
- ✅ 90%+ sessions use stored calibration (if LEDs stable)
- ✅ Zero false positives (valid cal rejected) in testing
- ✅ Zero false negatives (invalid cal accepted) in testing

**User Experience**:
- ✅ Clear "prism + water required" reminder
- ✅ Per-channel QC results displayed
- ✅ Time savings shown (~2-3 minutes)
- ✅ Failed channels clearly identified

**Quality Assurance**:
- ✅ No degraded data reaches live measurement
- ✅ LED aging automatically detected
- ✅ Polarizer misalignment detected
- ✅ Optical contamination detected

---

## 💡 Additional Refinements

### 1. Age-Based Thresholds
Relax thresholds for newer calibrations:
```python
days_old = (datetime.now() - calibration_date).days

if days_old < 7:
    intensity_threshold = 3.0%  # Stricter
elif days_old < 30:
    intensity_threshold = 5.0%  # Normal
else:
    intensity_threshold = 7.0%  # More permissive (expect drift)
```

### 2. Trend Tracking
Store QC history to predict when recalibration needed:
```json
"qc_history": [
  {"date": "2025-10-15", "intensity_dev": 0.2, "shape_corr": 0.995},
  {"date": "2025-10-18", "intensity_dev": 1.1, "shape_corr": 0.992},
  {"date": "2025-10-22", "intensity_dev": 2.4, "shape_corr": 0.989}
]
```
→ Linear extrapolation: Will exceed 5% in ~10 days

### 3. Channel-Specific Recalibration
If only 1 channel fails, recalibrate just that channel:
```python
if len(failed_channels) == 1:
    logger.info(f"Only {failed_channels[0]} failed - spot recalibration")
    recalibrate_single_channel(failed_channels[0])
```

---

**Status**: 📋 Ready for Implementation
**Estimated Time**: 4-6 hours
**Next Step**: Approve and implement
