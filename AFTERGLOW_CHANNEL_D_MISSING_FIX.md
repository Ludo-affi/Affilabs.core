# Afterglow Calibration - Channel 'D' Missing - ROOT CAUSE & FIX

## Problem Summary

**Error Message**:
```
AfterglowCorrection unavailable: Missing channel 'd' in calibration data
Available channels: ['a', 'b', 'c']
```

**Impact**: CRITICAL - Afterglow correction completely disabled. All 4 channels required due to cross-channel correction pattern.

---

## Root Cause Analysis

### 1. Cross-Channel Correction Dependency

Afterglow correction uses a circular pattern where each channel's afterglow corrects the **next** channel:

```
Channel A  ← corrected by Channel D afterglow
Channel B  ← corrected by Channel A afterglow
Channel C  ← corrected by Channel B afterglow
Channel D  ← corrected by Channel C afterglow
```

**IMPORTANT:** This is just the DEFAULT sequential pattern. The system architecture is more flexible.

### Flexible Channel Sequencing (Design Advantage)

Each LED's afterglow is calibrated INDEPENDENTLY, which enables:

**Current Usage (4-channel sequential):**
- Measure A→B→C→D in sequence
- Each channel corrected by previous channel's afterglow

**Future Usage (2-channel non-adjacent):**
- Measure only channels A and C (skip B and D)
- C is corrected directly by A's afterglow
- OR measure B and D (skip A and C)
- D is corrected directly by B's afterglow

**Custom Sequences:**
- Any arbitrary channel order
- System looks up the specific LED that was previously active
- Applies that LED's afterglow correction automatically

**Why All 4 Channels Still Required:**
Even though you might only use 2 channels in an assay, you need all 4 calibrated because:
1. Different assays may use different channel combinations
2. Future flexibility to choose ANY 2 (or 3, or 4) channels
3. Maintenance/validation requires full system characterization

**Result**: Missing ANY channel limits future assay flexibility and breaks correction for any sequence involving that channel.

**Code Reference**: `Affilabs.core beta/afterglow_correction.py`, lines 193-203:
```python
required_channels = ['a', 'b', 'c', 'd']
for channel in required_channels:
    if channel not in data['channel_data']:
        raise ValueError(
            f"Missing channel '{channel}' in calibration data\n"
            f"Available channels: {list(data['channel_data'].keys())}"
        )
```

### 2. Current Calibration File Status

**File**: `c:\Users\ludol\ezControl-AI\Affilabs.core beta\config\devices\FLMT09116\optical_calibration.json`

**Analysis**:
- ✅ Channel 'a': 6 integration time data points
- ✅ Channel 'b': 6 integration time data points
- ✅ Channel 'c': 5 integration time data points
- ❌ Channel 'd': **MISSING COMPLETELY**

**Integration time grid used**: [5, 10, 15, 20, 30, 50, 100] ms
**Created**: 2025-11-22T03:57:23Z
**Device**: FLMT09116

### 3. Why Channel 'D' Failed

The `run_afterglow_calibration()` function has error handling that **continues on failure**:

**Code**: `Affilabs.core beta/utils/afterglow_calibration.py`, lines 163-176:
```python
try:
    # Pre-on to charge phosphor
    if led_intensities and ch in led_intensities:
        ctrl.set_intensity(ch=ch, raw_val=int(led_intensities[ch]))
    else:
        ctrl.set_intensity(ch=ch, raw_val=255)
    # ... measurement code ...
except Exception as e:
    # Log error and continue with other channels/points
    logger.error(f"❌ Afterglow calibration failed for channel '{ch}' at {int_ms}ms: {e}")
    time.sleep(0.05)
    continue  # <-- CONTINUES, doesn't stop
```

**Result**: When channel 'd' encountered an error (LED communication issue, timing problem, hardware fault), the error was logged but the calibration continued without it.

**Modern version** (lines 177-191) adds validation to **catch this and fail**:
```python
missing_channels = []
for ch in channels:
    if not out["channel_data"][ch]["integration_time_data"]:
        missing_channels.append(ch)

if missing_channels:
    logger.error(f"❌ CRITICAL: Afterglow calibration incomplete!")
    raise RuntimeError(
        f"Afterglow calibration failed: missing data for channels {missing_channels}. "
        f"All 4 channels must be calibrated for proper afterglow correction."
    )
```

**However**: Your optical_calibration.json was created **before this validation was added**, so it was saved with only 3 channels.

---

## Fix Strategy

### Option 1: Re-run Full Afterglow Calibration (RECOMMENDED)

This will regenerate the entire `optical_calibration.json` file with all 4 channels.

#### A. From GUI (if available)
1. Open your SPR application
2. Go to **Calibration** menu
3. Select **Run Optical Calibration** or **Run Afterglow Calibration**
4. Wait ~5-10 minutes for completion
5. Verify all 4 channels present (see verification section below)

#### B. From Code (if in development)

The calibrator has a method for this:

```python
from utils.spr_calibrator import SPRCalibrator

# Assuming you have calibrator instance already
success = calibrator._run_optical_calibration()

if success:
    print("✅ Optical calibration complete")
    # Verify channels
    import json
    cal_file = device_manager.current_device_dir / "optical_calibration.json"
    with open(cal_file, 'r') as f:
        data = json.load(f)
        channels = list(data['channel_data'].keys())
        print(f"Channels: {channels}")
        assert len(channels) == 4, f"Missing channels! Only has {channels}"
else:
    print("❌ Optical calibration failed")
```

**Code Reference**: `utils/spr_calibrator.py`, lines 854-927

**What it does**:
1. Uses calibrated LED intensities from `device_config.json`
2. Tests integration times: [10, 25, 40, 55, 70, 85] ms (configurable)
3. Measures afterglow decay for all 4 channels
4. Fits exponential decay: `signal(t) = baseline + amplitude * exp(-t/τ)`
5. Saves to `config/devices/{serial}/optical_calibration.json`

**Duration**: ~5-10 minutes (6 integration times × 4 channels × 250ms acquisition each)

### Option 2: Quick Fix - Copy Channel C Data to Channel D (NOT RECOMMENDED)

⚠️ **WARNING**: This is a temporary workaround only for testing. Channel D afterglow characteristics are likely different from Channel C.

```python
import json
from pathlib import Path

cal_file = Path("c:/Users/ludol/ezControl-AI/Affilabs.core beta/config/devices/FLMT09116/optical_calibration.json")

with open(cal_file, 'r') as f:
    data = json.load(f)

# Copy channel 'c' data to channel 'd' (ROUGH APPROXIMATION)
data['channel_data']['d'] = data['channel_data']['c'].copy()

with open(cal_file, 'w') as f:
    json.dump(data, f, indent=2)

print("✅ Temporary fix applied - channel 'd' data copied from 'c'")
print("⚠️  This is APPROXIMATE. Re-run proper calibration when possible.")
```

### Option 3: Disable Afterglow Correction (NOT RECOMMENDED)

Modify `core/data_acquisition_manager.py`, lines 916-956:

```python
def _load_afterglow_correction(self):
    # ... existing code ...

    try:
        self.afterglow_corrector = AfterglowCorrection(
            calibration_file=calibration_file,
            device_serial=serial_number
        )
        self.afterglow_enabled = True
    except Exception as e:
        logger.warning(f"AfterglowCorrection unavailable: {e}")
        logger.warning("Proceeding without afterglow correction")
        self.afterglow_corrector = None
        self.afterglow_enabled = False
        # CHANGED: Don't block operation, just disable correction
```

**Impact**: Live measurements will have afterglow artifacts. Only use for non-critical testing.

---

## Verification After Fix

Run this command to verify all 4 channels are present:

### PowerShell:
```powershell
$cal_file = "c:\Users\ludol\ezControl-AI\Affilabs.core beta\config\devices\FLMT09116\optical_calibration.json"
$data = Get-Content $cal_file | ConvertFrom-Json
$channels = $data.channel_data.PSObject.Properties.Name
Write-Host "Channels present: $channels"
Write-Host "Count: $($channels.Count)"

if ($channels.Count -eq 4) {
    Write-Host "✅ SUCCESS: All 4 channels present" -ForegroundColor Green
} else {
    Write-Host "❌ FAILURE: Missing channels! Only has: $channels" -ForegroundColor Red
}
```

### Python:
```python
import json

cal_file = "c:/Users/ludol/ezControl-AI/Affilabs.core beta/config/devices/FLMT09116/optical_calibration.json"

with open(cal_file, 'r') as f:
    data = json.load(f)

channels = list(data['channel_data'].keys())
print(f"Channels present: {channels}")
print(f"Count: {len(channels)}")

for ch in channels:
    num_points = len(data['channel_data'][ch]['integration_time_data'])
    print(f"  Channel {ch}: {num_points} data points")

if len(channels) == 4:
    print("✅ SUCCESS: All 4 channels present")
else:
    missing = [ch for ch in ['a', 'b', 'c', 'd'] if ch not in channels]
    print(f"❌ FAILURE: Missing channels: {missing}")
```

---

## Prevention for Future

### Code Enhancement: Add Channel Validation

The validation code (lines 177-191 in `afterglow_calibration.py`) will **prevent this from happening again**. It's already in your current code.

When afterglow calibration runs now, if any channel fails, the entire calibration will **fail immediately** rather than creating an incomplete file.

### Testing Before Deployment

After any afterglow calibration, add this check:

```python
def validate_afterglow_calibration(device_serial: str) -> bool:
    """Validate afterglow calibration has all required channels.

    Returns:
        True if valid, False otherwise
    """
    from utils.device_manager import get_device_manager
    import json

    device_manager = get_device_manager()
    cal_file = device_manager.get_device_dir(device_serial) / "optical_calibration.json"

    if not cal_file.exists():
        logger.error(f"❌ No optical calibration file: {cal_file}")
        return False

    try:
        with open(cal_file, 'r') as f:
            data = json.load(f)

        required_channels = ['a', 'b', 'c', 'd']
        actual_channels = list(data.get('channel_data', {}).keys())

        if set(actual_channels) != set(required_channels):
            missing = set(required_channels) - set(actual_channels)
            logger.error(f"❌ Missing channels in optical calibration: {missing}")
            logger.error(f"   Required: {required_channels}")
            logger.error(f"   Found: {actual_channels}")
            return False

        # Check each channel has data
        for ch in required_channels:
            data_points = len(data['channel_data'][ch]['integration_time_data'])
            if data_points < 3:
                logger.error(f"❌ Channel '{ch}' has insufficient data points: {data_points} (need ≥3)")
                return False

        logger.info(f"✅ Optical calibration valid: {actual_channels}")
        return True

    except Exception as e:
        logger.exception(f"❌ Failed to validate optical calibration: {e}")
        return False
```

### Hardware Check

If channel 'd' consistently fails during calibration:

1. **Check LED Connection**
   - Is Channel D LED functional?
   - Test: `ctrl.set_intensity('d', 255)` and verify light output

2. **Check Spectrometer Signal**
   - Is Channel D wavelength range visible to detector?
   - Test: Manually measure Channel D spectrum

3. **Check Timing**
   - Does Channel D have unusually fast/slow afterglow?
   - May need different `pre_on_duration_s` or `acquisition_duration_ms`

---

## Related Issue: LED Intensity Propagation

**User Requirement**:
> "If upstream we identified the led intensity that dont saturate, then it should be transferred to afterglow"

### Current Behavior

✅ **GOOD**: The LED intensities ARE being passed correctly.

**Code**: `utils/spr_calibrator.py`, lines 893-904:
```python
# Use calibrated LED intensities (P-mode if available)
led_intensities = self.state.ref_intensity.copy()

logger.info(f"   LED intensities: {led_intensities}")

# Run afterglow calibration
calibration_data = run_afterglow_calibration(
    ctrl=self.ctrl,
    usb=self.usb,
    # ... other params ...
    led_intensities=led_intensities,  # ← Passed here
)
```

**Code**: `utils/afterglow_calibration.py`, lines 128-134:
```python
for ch in channels:
    try:
        # Pre-on to charge phosphor
        if led_intensities and ch in led_intensities:
            ctrl.set_intensity(ch=ch, raw_val=int(led_intensities[ch]))  # ← Used here
        else:
            ctrl.set_intensity(ch=ch, raw_val=255)  # ← Fallback to max
```

### Verification

After LED calibration, check that `device_config.json` has the intensities:

```python
import json

config_file = "c:/Users/ludol/ezControl-AI/Affilabs.core beta/config/devices/FLMT09116/device_config.json"

with open(config_file, 'r') as f:
    config = json.load(f)

led_intensities = config.get('led_intensities', {})
print(f"LED intensities from calibration:")
for ch in ['a', 'b', 'c', 'd']:
    intensity = led_intensities.get(ch, 'NOT SET')
    print(f"  Channel {ch}: {intensity}")
```

These intensities are then used during afterglow measurement to prevent saturation.

---

## Summary

| Issue | Status | Action |
|-------|--------|--------|
| Channel 'd' missing | ❌ BLOCKING | Re-run optical calibration |
| LED intensities propagation | ✅ WORKING | No action needed |
| Validation after calibration | ✅ PRESENT | Already implemented |
| Cross-channel dependency | ℹ️ BY DESIGN | All 4 channels required |

**Next Steps**:
1. ✅ Re-run optical calibration (Option 1)
2. ✅ Verify all 4 channels present
3. ✅ Test afterglow correction loading
4. ✅ Verify no errors during live measurement startup

---

## Quick Reference

### Files Involved

| File | Purpose |
|------|---------|
| `Affilabs.core beta/afterglow_correction.py` | Loads calibration, validates channels |
| `Affilabs.core beta/utils/afterglow_calibration.py` | Runs calibration, measures decay |
| `utils/spr_calibrator.py` | Orchestrates calibration, passes LED intensities |
| `config/devices/{serial}/optical_calibration.json` | Stores afterglow data |
| `config/devices/{serial}/device_config.json` | Stores LED intensities |

### Key Functions

- `run_afterglow_calibration()` - Measures afterglow for all channels
- `_run_optical_calibration()` - High-level wrapper in SPRCalibrator
- `AfterglowCorrection.__init__()` - Validates all 4 channels present
- `_load_afterglow_correction()` - Loads correction in DataAcquisitionManager

### Integration Times Tested

| Integration Time | Purpose |
|------------------|---------|
| 10 ms | Fast scans |
| 25 ms | Low signal |
| 40 ms | Medium signal |
| 55 ms | Medium-high signal |
| 70 ms | High signal |
| 85 ms | Very high signal |

Each channel × each integration time = 24 measurements total
Duration: ~5-10 minutes

---

## Contact Points

If channel 'd' continues to fail after multiple attempts:

1. **Check hardware**: LED 'd' functional? Spectrometer sees channel 'd' wavelength?
2. **Check timing parameters**: May need longer `pre_on_duration_s` for channel 'd'
3. **Check error logs**: What specific error occurred during channel 'd' measurement?
4. **Temporary workaround**: Copy channel 'c' data (Option 2 above) for testing only

**End of Document**
