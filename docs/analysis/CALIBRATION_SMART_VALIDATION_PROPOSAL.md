# Smart Calibration Validation System - Proposal

## 🎯 Goal
Store LED intensities and integration time in `device_config.json` as **single source of truth**. Before running full calibration, validate if stored values still produce good quality data. Only recalibrate if quality has degraded.

---

## 📋 Current Architecture Issues

### Problem 1: No Single Source of Truth
- **LED intensities** currently stored in:
  - `ConfigurationManager.calibration.ref_intensity` (runtime)
  - `ConfigurationManager.calibration.pol_intensity` (runtime)
  - Calibration history files (timestamped archives)
  - ❌ **NOT in device_config.json**

### Problem 2: No Quality Validation
- Calibration runs fresh every time
- No check if previous values are still valid
- Wastes 2-3 minutes if LED/detector unchanged

### Problem 3: Fragmented Storage
- Integration time: `config_manager.calibration.integration`
- LED intensities: `config_manager.calibration.ref/pol_intensity`
- Dark noise: Generated files
- No unified device-level storage

---

## 🏗️ Proposed Architecture

### 1. Enhanced device_config.json Structure

```json
{
  "device_info": { ... },
  "hardware": { ... },
  "timing_parameters": { ... },

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
    "validation_metrics": {
      "signal_quality_score": 0.95,
      "snr_average": 85.3,
      "saturation_margin_percent": 35.0,
      "channel_balance_cv": 0.08
    }
  },

  "calibration_validation": {
    "last_validation_date": "2025-10-22T16:15:00",
    "validation_result": "PASS",
    "validation_notes": "Signal quality within 5% of baseline",
    "next_validation_due": "2025-10-29T14:30:00"
  }
}
```

### 2. Validation Workflow (Fast Path)

```
Start Calibration
    ↓
Check device_config.json for stored LED values?
    ├─ No → Run full calibration (slow path)
    │
    ├─ Yes → Quick validation test
    │         ↓
    │    Load stored LED intensities + integration time
    │         ↓
    │    Measure 10 S-mode + 10 P-mode spectra
    │         ↓
    │    Compare quality metrics vs baseline
    │         ↓
    │    ┌─────────────┴─────────────┐
    │    ↓ PASS                  ↓ FAIL
    │    Use stored values       Run full calibration
    │    (5-10 seconds)          (2-3 minutes)
```

---

## 📊 Validation Criteria (Pass/Fail)

### Metrics to Track

| Metric | Calculation | Pass Threshold | Action if Fail |
|--------|-------------|----------------|----------------|
| **Signal Stability** | `std(signal_max) / mean(signal_max)` | CV < 5% | Recalibrate |
| **Signal Level Drift** | `abs(current_mean - baseline_mean) / baseline_mean` | < 10% deviation | Recalibrate |
| **SNR Degradation** | `current_SNR / baseline_SNR` | > 0.85 (retain 85% SNR) | Recalibrate |
| **Saturation Check** | `max(signal) / detector_max` | < 95% (no saturation) | Recalibrate |
| **Channel Balance** | `std(channel_signals) / mean(channel_signals)` | CV < 20% | Recalibrate |
| **Dark Noise Drift** | `abs(current_dark - baseline_dark)` | < 100 counts | Acceptable |

### Combined Pass Criteria

**All conditions must pass:**
1. ✅ Signal stability CV < 5%
2. ✅ Signal level within ±10% of baseline
3. ✅ SNR > 85% of baseline
4. ✅ No saturation (max < 95%)
5. ✅ Channel balance CV < 20%

**If ANY fail → Run full calibration**

---

## 🔧 Implementation Plan

### Phase 1: Store Calibration in device_config.json

**File**: `utils/device_configuration.py`

Add methods:
```python
def save_led_calibration(
    self,
    integration_time_ms: int,
    s_mode_intensities: dict[str, int],
    p_mode_intensities: dict[str, int],
    validation_metrics: dict[str, float]
) -> None:
    """Save LED calibration to device_config.json"""

def load_led_calibration(self) -> Optional[dict]:
    """Load LED calibration from device_config.json"""

def is_calibration_recent(self, max_age_days: int = 7) -> bool:
    """Check if calibration is recent enough"""
```

### Phase 2: Quick Validation Method

**File**: `utils/spr_calibrator.py`

Add new method:
```python
def validate_stored_calibration(
    self,
    stored_config: dict,
    num_samples: int = 10
) -> tuple[bool, dict[str, float]]:
    """
    Quick validation test using stored LED values.

    Args:
        stored_config: LED calibration from device_config.json
        num_samples: Number of spectra to measure (default: 10)

    Returns:
        (passed, metrics) - True if quality acceptable, False if recalibration needed
    """
    # 1. Load stored LED intensities
    # 2. Set integration time
    # 3. Measure S-mode signals (10 spectra)
    # 4. Measure P-mode signals (10 spectra)
    # 5. Calculate quality metrics
    # 6. Compare to baseline
    # 7. Return pass/fail
```

### Phase 3: Smart Calibration Entry Point

**File**: `utils/spr_calibrator.py`

Modify `run_full_calibration()`:
```python
def run_full_calibration(
    self,
    force_recalibrate: bool = False,  # NEW: Skip validation
    validation_threshold: float = 0.85,  # NEW: Customizable
    ...
) -> tuple[bool, str]:
    """
    Smart calibration with optional quick validation.

    Args:
        force_recalibrate: Skip validation, run full calibration
        validation_threshold: SNR retention threshold (default: 85%)
    """

    # NEW: Try fast path first
    if not force_recalibrate:
        device_config = DeviceConfiguration()
        stored_cal = device_config.load_led_calibration()

        if stored_cal and device_config.is_calibration_recent(max_age_days=7):
            logger.info("🔍 Found recent calibration, running quick validation...")

            passed, metrics = self.validate_stored_calibration(stored_cal)

            if passed:
                logger.info("✅ Stored calibration still valid! Using stored values.")
                logger.info(f"   Signal stability: {metrics['stability_cv']:.2%}")
                logger.info(f"   SNR retention: {metrics['snr_ratio']:.2%}")
                logger.info(f"   Time saved: ~2-3 minutes")

                # Load stored values into calibration state
                self._load_stored_calibration(stored_cal)
                return True, ""
            else:
                logger.warning("❌ Validation failed, running full calibration...")
                logger.warning(f"   Reason: {metrics['failure_reason']}")

    # Continue with full calibration (existing code)
    ...
```

---

## 📈 Expected Benefits

### Time Savings
- **Full calibration**: 2-3 minutes
- **Quick validation**: 5-10 seconds
- **Savings**: ~95% faster when validation passes

### Stability
- Consistent LED values across sessions
- Single source of truth
- Easy to audit/debug

### Quality Assurance
- Automatic drift detection
- Quantitative pass/fail criteria
- Traceable validation history

---

## 🎯 Pass/Fail Criteria - Detailed Recommendations

### 1. Signal Stability (Within Single Run)
**Metric**: Coefficient of variation of max signal across 10 spectra
```python
signal_max_array = [max(spectrum) for spectrum in spectra]
stability_cv = std(signal_max_array) / mean(signal_max_array)
```
**Threshold**: CV < 5% (very stable)
**Rationale**: LED output should be consistent shot-to-shot

### 2. Signal Level Drift (vs Baseline)
**Metric**: Relative change in mean signal
```python
current_mean = mean([max(spectrum) for spectrum in spectra])
baseline_mean = stored_config['validation_metrics']['signal_mean']
drift = abs(current_mean - baseline_mean) / baseline_mean
```
**Threshold**: < 10% drift
**Rationale**: Small drift ok (temperature, LED aging), large drift = problem

### 3. SNR Degradation
**Metric**: Ratio of current SNR to baseline SNR
```python
current_snr = mean(signal) / std(dark_noise)
baseline_snr = stored_config['validation_metrics']['snr_average']
snr_ratio = current_snr / baseline_snr
```
**Threshold**: > 0.85 (retain 85% of SNR)
**Rationale**: Some degradation acceptable, but not >15%

### 4. Saturation Check
**Metric**: Detector utilization
```python
max_signal = max([max(spectrum) for spectrum in spectra])
saturation_percent = (max_signal / detector_max) * 100
```
**Threshold**: < 95%
**Rationale**: Must stay in linear range

### 5. Channel Balance
**Metric**: Variation across channels
```python
channel_means = [mean(ch_spectra) for ch in channels]
balance_cv = std(channel_means) / mean(channel_means)
```
**Threshold**: CV < 20%
**Rationale**: Channels should be roughly balanced

### 6. Dark Noise Drift
**Metric**: Change in dark noise level
```python
current_dark = mean(dark_spectrum)
baseline_dark = stored_config['dark_noise_mean']
dark_drift = abs(current_dark - baseline_dark)
```
**Threshold**: < 100 counts (small absolute change)
**Rationale**: Dark noise should be very stable (detector electronics)

---

## 🚀 Recommended Thresholds Summary

| Metric | Formula | Pass If | Fail If | Priority |
|--------|---------|---------|---------|----------|
| **Signal Stability** | `std(max) / mean(max)` | CV < 5% | CV ≥ 5% | 🔴 Critical |
| **Signal Drift** | `Δmean / baseline` | < 10% | ≥ 10% | 🔴 Critical |
| **SNR Ratio** | `SNR_now / SNR_baseline` | > 0.85 | ≤ 0.85 | 🟡 Important |
| **Saturation** | `max / detector_max` | < 95% | ≥ 95% | 🔴 Critical |
| **Channel Balance** | `std(channels) / mean(channels)` | CV < 20% | CV ≥ 20% | 🟡 Important |
| **Dark Drift** | `abs(dark - baseline)` | < 100 cts | ≥ 100 cts | 🟢 Nice-to-have |

### Strictness Levels

**Option A: Conservative (Recommended for Production)**
- Signal stability: CV < 5%
- Signal drift: < 10%
- SNR ratio: > 0.90 (retain 90%)
- **Result**: Recalibrates more often, ensures consistent quality

**Option B: Balanced (Recommended for Development)**
- Signal stability: CV < 5%
- Signal drift: < 15%
- SNR ratio: > 0.85 (retain 85%)
- **Result**: Good balance between speed and quality

**Option C: Permissive (Debug Only)**
- Signal stability: CV < 10%
- Signal drift: < 20%
- SNR ratio: > 0.80 (retain 80%)
- **Result**: Rarely recalibrates, accepts degraded quality

---

## 🔄 User Experience

### UI Flow

```
User clicks "Calibrate"
    ↓
System checks device_config.json
    ↓
Found calibration from 2 days ago
    ↓
[Dialog Box]
┌────────────────────────────────────────────┐
│  Calibration Found (2 days old)            │
│                                            │
│  ✓ Integration time: 32 ms                │
│  ✓ LED intensities: Stored                │
│  ✓ Last validation: PASSED                │
│                                            │
│  [Quick Validate (10s)] [Full Cal (3min)] │
└────────────────────────────────────────────┘
    ↓
User clicks "Quick Validate"
    ↓
System measures 10 S + 10 P spectra
    ↓
┌────────────────────────────────────────────┐
│  Validation Complete                       │
│                                            │
│  ✅ Signal stability: 2.3% (pass)         │
│  ✅ Signal drift: 4.1% (pass)             │
│  ✅ SNR retention: 92% (pass)             │
│  ✅ No saturation (pass)                  │
│  ✅ Channel balance: 12% (pass)           │
│                                            │
│  Using stored calibration.                │
│  Time saved: 2 min 45 sec                 │
│                                            │
│              [OK]                          │
└────────────────────────────────────────────┘
```

### If Validation Fails

```
┌────────────────────────────────────────────┐
│  Validation Failed                         │
│                                            │
│  ❌ Signal drift: 15.2% (threshold: 10%)  │
│                                            │
│  Reason: Significant LED aging detected   │
│  Action: Running full recalibration...    │
│                                            │
│  [Cancel] [Continue]                      │
└────────────────────────────────────────────┘
```

---

## 💡 Additional Suggestions

### 1. Automatic Validation Scheduling
Store `next_validation_due` in device_config.json:
- First 30 days: Validate every 7 days
- After 30 days: Validate every 3 days (LED aging accelerates)
- After 6 months: Validate every session

### 2. Trend Tracking
Store validation history:
```json
"validation_history": [
  {
    "date": "2025-10-15",
    "signal_drift": 2.1,
    "snr_ratio": 0.98,
    "result": "PASS"
  },
  {
    "date": "2025-10-22",
    "signal_drift": 4.5,
    "snr_ratio": 0.94,
    "result": "PASS"
  }
]
```
→ Predict when recalibration will be needed

### 3. Channel-Specific Recalibration
If only 1 channel fails validation, recalibrate just that channel:
```python
if len(failed_channels) == 1:
    logger.info(f"Only channel {failed_channels[0]} failed - spot recalibration")
    recalibrate_single_channel(failed_channels[0])
```

### 4. Temperature Compensation
Store calibration temperature, adjust thresholds:
```python
temp_delta = abs(current_temp - calibration_temp)
if temp_delta > 5:  # °C
    drift_threshold *= 1.5  # More permissive
```

---

## ✅ Implementation Checklist

### Phase 1: Storage (1-2 hours)
- [ ] Add `led_calibration` section to device_config.json schema
- [ ] Implement `save_led_calibration()` in DeviceConfiguration
- [ ] Implement `load_led_calibration()` in DeviceConfiguration
- [ ] Update calibration save logic to write to device_config

### Phase 2: Validation Logic (2-3 hours)
- [ ] Implement `validate_stored_calibration()` method
- [ ] Add metric calculation functions
- [ ] Define pass/fail thresholds (tunable constants)
- [ ] Add logging for validation results

### Phase 3: Integration (1 hour)
- [ ] Modify `run_full_calibration()` to check for stored values
- [ ] Add `force_recalibrate` flag
- [ ] Update UI to show validation option

### Phase 4: Testing (1 hour)
- [ ] Test with valid calibration (should pass)
- [ ] Test with aged LEDs (should fail)
- [ ] Test with saturated detector (should fail)
- [ ] Verify time savings

---

## 🎯 Success Criteria

**Fast Path Success**:
- ✅ Validation completes in < 15 seconds
- ✅ 95% of sessions use stored values (if LEDs stable)
- ✅ False positive rate < 5% (valid cal wrongly rejected)
- ✅ False negative rate < 1% (invalid cal wrongly accepted)

**Quality Assurance**:
- ✅ No degraded data in production
- ✅ Automatic detection of LED aging
- ✅ Clear audit trail (when/why recalibrated)

---

## 📝 Notes

**Why These Thresholds?**
- **5% stability**: LEDs are very stable, >5% suggests hardware issue
- **10% drift**: Small aging expected, 10% is measurable but acceptable
- **85% SNR**: Enough degradation to notice, but not critical yet
- **95% saturation**: Safe margin before nonlinearity

**Alternative: Machine Learning Approach**
Could train classifier on "good" vs "bad" calibrations:
- Features: stability CV, drift, SNR ratio, channel balance
- Labels: Manual QA assessment
- Model: Random Forest (fast, interpretable)
- Threshold: Probability > 0.9 → PASS

---

**Status**: 📋 Proposal Draft
**Next Step**: Review and approve thresholds
**Estimated Implementation**: 4-6 hours total
