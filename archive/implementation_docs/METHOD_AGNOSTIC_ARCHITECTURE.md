# METHOD-AGNOSTIC ARCHITECTURE - COMPLETE

## Core Principle

**Calibration determines parameters → Live acquisition executes them**

Live acquisition is **completely method-agnostic**. It doesn't know or care which calibration method was used. It simply executes whatever parameters calibration provides.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CALIBRATION                              │
│                                                             │
│  Method Selection (affects ONLY calibration):              │
│  ┌──────────────────────┐  ┌─────────────────────────┐   │
│  │ Global LED Intensity │  │ Variable LED (future)   │   │
│  │ - All LEDs = 255     │  │ - Variable LED per ch   │   │
│  │ - Global integration │  │ - Fixed integration     │   │
│  │ - num_scans = 1      │  │ - num_scans = X         │   │
│  └──────────────────────┘  └─────────────────────────┘   │
│                                                             │
│  Output Parameters (method-independent):                    │
│  - integration_time: ms                                     │
│  - num_scans: count                                         │
│  - leds_calibrated: {ch: intensity}                         │
│  - ref_intensity: {ch: intensity}                           │
│  - dark_noise: baseline                                     │
│  - ref_sig: {ch: spectrum}                                  │
│  - wave_data: wavelengths                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LIVE ACQUISITION                            │
│                 (Method-Agnostic)                           │
│                                                             │
│  FOR EACH CHANNEL:                                          │
│    1. Set LED = leds_calibrated[channel]                   │
│    2. Set integration = integration_time                    │
│    3. Acquire raw spectrum                                  │
│    4. Subtract dark_noise                                   │
│    5. Apply afterglow correction                            │
│    6. Calculate transmission: P_live / S_ref                │
│    7. Process & emit data                                   │
│                                                             │
│  NO METHOD-SPECIFIC LOGIC                                   │
│  NO ASSUMPTIONS ABOUT LED VALUES                            │
│  NO VALIDATION OF PARAMETERS                                │
│  JUST EXECUTE WHAT CALIBRATION PROVIDES                     │
└─────────────────────────────────────────────────────────────┘
```

## Code Structure

### Calibration Manager (`calibration_manager.py`)

**Role**: Route to appropriate calibration method

```python
if use_fast_track:
    cal_result = run_fast_track_calibration(...)
else:
    cal_result = perform_alternative_calibration(...)  # Global LED method

# Store results (method-agnostic)
data_mgr.integration_time = cal_result.integration_time
data_mgr.num_scans = cal_result.num_scans
data_mgr.leds_calibrated = cal_result.leds_calibrated
data_mgr.ref_intensity = cal_result.ref_intensity
# ... etc
```

**No method-specific validation** - just stores whatever calibration provides.

### Data Acquisition Manager (`data_acquisition_manager.py`)

**Role**: Execute calibration parameters

```python
def _acquire_channel_spectrum(self, channel: str):
    # Get LED intensity from calibration
    led_intensity = self.leds_calibrated.get(channel)

    # Set LED
    ctrl.set_intensity(ch=channel, raw_val=led_intensity)

    # Set integration time from calibration
    usb.set_integration(self.integration_time)

    # Acquire
    raw_spectrum = usb.read_intensity()

    # Process (dark subtraction, afterglow, transmission)
    # ...
```

**No method-specific logic** - just uses parameters as provided.

### Settings (`settings.py`)

**Role**: Select calibration method

```python
# Method selection ONLY affects calibration
# Live acquisition is method-agnostic
USE_ALTERNATIVE_CALIBRATION = True  # Global LED Intensity
```

**Clear documentation** that method affects calibration only.

## Removed Code

### ❌ Deleted: Method-Specific Validation in Live Acquisition

**Before**:
```python
# VALIDATION: Enforce LED=255 in Global LED Intensity method
if led_intensity != 255:
    logger.warning("LED intensity != 255")
    led_intensity = 255
```

**After**:
```python
# Get LED intensity from calibration (method-agnostic)
led_intensity = self.leds_calibrated.get(channel)
```

### ❌ Deleted: Method-Specific Documentation in Live Acquisition

**Before**:
```python
# CRITICAL: Global LED Intensity method ENFORCED
# - All LEDs = 255
# - Global integration time
# - num_scans = 1
```

**After**:
```python
# Calibration parameters (method-agnostic)
# Live acquisition executes whatever calibration provides
```

### ❌ Deleted: Method-Specific Startup Messages

**Before**:
```python
logger.info("🚀 STARTING LIVE ACQUISITION - GLOBAL LED INTENSITY METHOD")
logger.info("All LEDs=255 (ENFORCED)")
logger.info("Global integration time (ENFORCED)")
```

**After**:
```python
logger.info("🚀 STARTING LIVE ACQUISITION")
logger.info(f"Integration Time: {self.integration_time}ms")
logger.info(f"P-mode LEDs: {self.leds_calibrated}")
```

## Benefits of Method-Agnostic Architecture

### 1. **Separation of Concerns**
- Calibration: Optimize parameters
- Live Acquisition: Execute parameters
- Clear responsibility boundaries

### 2. **Flexibility**
- Easy to add new calibration methods
- No changes to live acquisition code needed
- Just provide the required parameters

### 3. **Testability**
- Can test calibration independently
- Can test acquisition with mock parameters
- No coupling between components

### 4. **Maintainability**
- Single source of truth (calibration results)
- No duplicate validation logic
- Clear data flow

### 5. **Consistency Guarantee**
- Live data ALWAYS matches calibration QC
- Parameters are identical by design
- No drift or divergence possible

## Critical Parameters Flow

### Calibration → Storage → Acquisition

```
CALIBRATION METHOD
      ↓
  Optimize parameters
      ↓
  Create CalibrationResult
      ↓
  Store in data_mgr
      ↓
  Live acquisition reads from data_mgr
      ↓
  Execute parameters exactly as stored
      ↓
  GUARANTEED CONSISTENCY
```

### Example: Global LED Intensity Method

```
CALIBRATION:
  1. Set all LEDs to 255
  2. Optimize integration time → 42ms (global max)
  3. Measure dark noise at 42ms
  4. Capture S-ref at LED=255, 42ms
  5. Verify P-mode at LED=255, 42ms
  6. Store: integration_time=42, leds_calibrated={a:255, b:255, c:255, d:255}

LIVE ACQUISITION:
  1. Read integration_time → 42ms
  2. Read leds_calibrated → {a:255, b:255, c:255, d:255}
  3. For each channel:
     - Set LED from leds_calibrated[channel]
     - Set integration from integration_time
     - Acquire with num_scans
  4. Result: IDENTICAL to calibration QC
```

### Example: Variable LED Method (Future)

```
CALIBRATION:
  1. Set integration time to 50ms (global)
  2. Optimize LED per channel → {a:180, b:220, c:200, d:255}
  3. Measure dark noise at 50ms
  4. Capture S-ref at respective LEDs, 50ms
  5. Verify P-mode at respective LEDs, 50ms
  6. Store: integration_time=50, leds_calibrated={a:180, b:220, c:200, d:255}

LIVE ACQUISITION:
  1. Read integration_time → 50ms
  2. Read leds_calibrated → {a:180, b:220, c:200, d:255}
  3. For each channel:
     - Set LED from leds_calibrated[channel]  ← Different per channel!
     - Set integration from integration_time  ← Same for all
     - Acquire with num_scans
  4. Result: IDENTICAL to calibration QC

NO CODE CHANGES NEEDED IN LIVE ACQUISITION!
```

## Validation Strategy

### Calibration-Time Validation

✅ **Do at calibration**:
- Check integration time > 0
- Check LED intensities valid
- Check dark noise measured
- Check reference spectra captured
- Validate QC metrics

### Live Acquisition Validation

✅ **Do at acquisition start**:
- Check parameters exist (not None)
- Check parameters are valid types
- Log parameters for user visibility

❌ **Don't do at acquisition**:
- Validate specific values (e.g., LED=255)
- Check method-specific constraints
- Modify/override calibration parameters
- Enforce method assumptions

## Files Modified

### Core Changes
1. **`src/core/data_acquisition_manager.py`**
   - Removed method-specific validation
   - Simplified parameter usage
   - Generic documentation
   - Method-agnostic logging

2. **`src/core/calibration_manager.py`**
   - Removed method-specific validation after calibration
   - Simple parameter transfer
   - Generic error checking

3. **`src/settings/settings.py`**
   - Clarified method affects calibration only
   - Explained method-agnostic architecture

### No Changes Needed
- `src/utils/led_calibration.py` (calibration backend)
- `src/utils/calibration_6step.py` (calibration backend)
- All other files (already method-agnostic)

## Testing Checklist

### Test Current Method (Global LED Intensity)
- [x] Run calibration
- [x] Check parameters stored correctly
- [x] Start live acquisition
- [x] Verify LED=255 used
- [x] Verify integration time correct
- [x] Compare QC vs live data

### Test Future Method (Variable LED) - When Implemented
- [ ] Implement variable LED calibration
- [ ] Run calibration
- [ ] Check parameters stored correctly
- [ ] Start live acquisition **WITHOUT CODE CHANGES**
- [ ] Verify different LEDs per channel used
- [ ] Verify integration time correct
- [ ] Compare QC vs live data

### Expected Behavior
- ✅ Live acquisition works with ANY method
- ✅ Parameters are executed as calibration provides
- ✅ QC data matches live data
- ✅ No code changes needed for new methods

## Summary

### Before: Method-Coupled Architecture
```
Calibration → Parameters → Live Acquisition
                              ↓
                       (checks if Global LED)
                              ↓
                       (enforces LED=255)
                              ↓
                       (validates num_scans=1)
```
**Problem**: Live acquisition has method-specific logic

### After: Method-Agnostic Architecture
```
Calibration → Parameters → Live Acquisition
                              ↓
                         (use as-is)
```
**Solution**: Live acquisition just executes parameters

---

## Conclusion

✅ **Architecture is now clean and robust**:
- Calibration determines ALL parameters
- Live acquisition executes them exactly
- No method-specific logic in acquisition
- Easy to add new calibration methods
- Guaranteed consistency between QC and live data

**Result**: Simplified code, better separation of concerns, future-proof architecture.
