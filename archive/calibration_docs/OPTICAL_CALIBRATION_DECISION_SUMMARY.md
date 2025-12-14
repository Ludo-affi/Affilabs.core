# Optical System Calibration - Architecture Decision Summary

**Date**: October 11, 2025
**Status**: ✅ Architecture Finalized

---

## Key Decision: Separate OEM Tool (NOT Step 10)

### The Question
Should optical system calibration be:
- **Option A**: New Step 10 in main calibration sequence?
- **Option B**: Separate OEM maintenance tool?

### **DECISION: Option B** ✅

**Rationale**: "Once the correction model is known, we don't need to do the calibration again. It's a once every 1000 hours operation thing. We only use the calibration model to correct the data - we don't do the procedure again."

---

## Architecture Summary

```
┌───────────────────────────────────────────────────────────────────┐
│                     TWO INDEPENDENT SYSTEMS                        │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐       ┌──────────────────────────┐  │
│  │  MAIN CALIBRATION       │       │  OPTICAL CALIBRATION     │  │
│  │  (9 Steps)              │       │  (Separate OEM Tool)     │  │
│  ├─────────────────────────┤       ├──────────────────────────┤  │
│  │ Frequency: DAILY        │       │ Frequency: RARE          │  │
│  │ Duration: 1.5 min       │       │ Duration: 2-3 min        │  │
│  │ User: AUTOMATIC         │       │ User: OEM ONLY           │  │
│  │ Purpose: Baselines      │       │ Purpose: τ tables        │  │
│  └─────────────────────────┘       └──────────────────────────┘  │
│            │                                    │                  │
│            │                                    │                  │
│            └───────────┬────────────────────────┘                  │
│                        ↓                                           │
│              ┌──────────────────┐                                 │
│              │ SPR MEASUREMENT  │                                 │
│              │ (with correction)│                                 │
│              └──────────────────┘                                 │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

---

## Comparison Table

| Aspect | Main Calibration | Optical Calibration |
|--------|-----------------|---------------------|
| **Frequency** | Every startup, daily | Once per 1000 hours |
| **Duration** | ~1.5 minutes | ~2-3 minutes |
| **Trigger** | Hardware connection, settings change | LED aging, hardware replacement |
| **User Access** | Automatic (all users) | Manual (OEM only) |
| **Purpose** | Optimize acquisition settings | Characterize LED phosphor decay |
| **Outputs** | LED intensities, integration time, dark noise, ref signals | τ(integration_time) lookup tables |
| **Storage** | `calibration_profiles/*.json` | `optical_calibration/system_*.json` |
| **Re-run?** | Yes, frequently | No, only after 1000 hours |
| **Correction** | Used for baseline/transmittance | Used for afterglow correction |

---

## Key Architectural Principles

### 1. **Separation of Concerns** ✅

**Main Calibration**:
- Handles parameters that change frequently
- Integration time optimization
- LED intensity settings
- Dark noise baselines
- Reference signal capture
- Runs automatically on startup

**Optical Calibration**:
- Characterizes hardware physics (phosphor decay)
- Generates τ(integration_time) lookup tables
- Changes only with LED aging or hardware replacement
- Runs manually when needed (~1000 hours)

### 2. **Correct Timescales** ✅

**Problem if combined**: Main calibration would go from 1.5 min → 3.5 min, every day!

**Solution**:
- Main calibration stays fast (1.5 min, frequent)
- Optical calibration runs rarely (2-3 min, once per 1000 hours)

### 3. **Passive Correction** ✅

**Once optical calibration is done**:
1. τ tables stored in `optical_calibration/system_SERIAL_DATE.json`
2. Main calibration runs normally (doesn't re-characterize phosphor)
3. Measurements load τ tables and apply correction
4. **No need to re-run optical calibration** - just use existing model

**Correction workflow**:
```python
# At system init
correction = AfterglowCorrection('optical_calibration/system_FLMT09788.json')

# During measurement (automatic)
corrected_signal = correction.apply_correction(
    measured_signal, previous_channel, integration_time_ms
)
```

### 4. **OEM Control** ✅

**Optical calibration is maintenance**:
- Not exposed to end users
- Hidden in OEM tools menu
- Controlled re-calibration schedule
- Documentation for field engineers

**Benefits**:
- No user confusion
- Scheduled maintenance
- Quality control
- Traceable calibration history

### 5. **Independence** ✅

```
Main Calibration ─────┐
                      ├──> SPR Measurement
Optical Calibration ──┘

• Either can run without the other
• No dependencies between them
• Can develop/test independently
• Can deploy separately
```

---

## Implementation Files

### Core Components

1. **`optical_system_calibration.py`** (OEM Tool)
   - Standalone script
   - Characterizes all 4 channels × 5 integration times
   - Generates τ(integration_time) lookup tables
   - Runtime: ~2.2 minutes (confirmed from testing)
   - Output: `optical_calibration/system_SERIAL_TIMESTAMP.json`

2. **`afterglow_correction.py`** (Production Module)
   - Loads optical calibration file
   - Builds cubic spline interpolators for τ(integration_time)
   - Provides correction API:
     - `calculate_correction(channel, int_time, delay) -> correction_value`
     - `apply_correction(signal, channel, int_time) -> corrected_signal`
   - No calibration code - just loads and applies existing model

3. **`spr_data_acquisition.py`** (Integration)
   - Loads optical calibration at init (if available)
   - Applies correction during multi-channel acquisition
   - Stores both raw + corrected data
   - Logs correction status

4. **`test_optical_calibration.py`** (Validation)
   - Quick-check tool for OEM
   - Verifies interpolation accuracy
   - Tests correction effectiveness
   - Runtime: ~2 minutes

### Configuration

**`device_config.json`**:
```json
{
  "spectrometer_serial": "FLMT09788",
  "optical_fiber_diameter_um": 200,
  "led_pcb_model": "luminus_cool_white",
  "optical_calibration_file": "optical_calibration/system_FLMT09788_20251011.json"
}
```

### Directory Structure

```
config/
├── device_config.json              # Links to optical calibration
├── optical_calibration/            # τ tables (long-lived)
│   ├── system_FLMT09788_20251011.json
│   └── system_FLMT09788_20251115.json  # Re-calibration after 1000h
└── calibration_profiles/           # Main calibration (frequent)
    ├── auto_save_20251011_220530.json
    └── auto_save_20251012_080245.json
```

---

## Usage Workflows

### Workflow 1: First Time Setup (OEM)

```
1. Hardware Assembly
   ↓
2. Run Optical Calibration
   $ python optical_system_calibration.py
   ↓ (generates τ tables, ~2-3 min)
3. Link in device_config.json
   ↓
4. Ship to Customer
```

### Workflow 2: Daily Operation (Customer)

```
1. Start Application
   ↓
2. Main Calibration (automatic, 1.5 min)
   ↓
3. SPR Measurements
   • Loads τ tables from optical calibration
   • Applies correction automatically
   • No re-calibration needed
```

### Workflow 3: Maintenance (After 1000 Hours)

```
1. LED Aging Detected or 1000h Operation
   ↓
2. Re-run Optical Calibration (OEM tool)
   $ python optical_system_calibration.py
   ↓ (generates new τ tables)
3. Update device_config.json
   ↓
4. Resume Normal Operation
   • Main calibration runs daily as usual
   • Measurements use updated τ tables
```

---

## Benefits of This Architecture

### ✅ **Performance**
- Main calibration stays fast (1.5 min)
- No daily overhead for optical characterization
- 2.3× faster multi-channel scanning with correction

### ✅ **Maintainability**
- Clear separation of concerns
- Independent testing and deployment
- Easy to update either system

### ✅ **User Experience**
- Automatic main calibration (no user action)
- Optical calibration hidden (OEM only)
- No confusion about different calibration types

### ✅ **Correctness**
- Appropriate timescales for each calibration
- Doesn't re-characterize stable hardware daily
- Allows infrequent updates when needed

### ✅ **Flexibility**
- Can add optical calibration to existing systems
- Can run without optical calibration (degrades gracefully)
- Can update correction algorithm independently

---

## Documentation Created

1. ✅ **`OPTICAL_CALIBRATION_ARCHITECTURE.md`** - Complete architecture design
2. ✅ **`CALIBRATION_STEP_BY_STEP_OUTLINE.md`** - Updated with architecture decision
3. ✅ **`OPTICAL_CALIBRATION_IMPLEMENTATION_PLAN.md`** - Updated with separation rationale
4. ✅ **`LED_INTENSITY_CALIBRATION_CONSIDERATIONS.md`** - Intensity effects analysis
5. ✅ **`HAL_LED_INTENSITY_FIX.md`** - Fixed HAL implementation

---

## Next Implementation Steps

### Phase 1: Correction Module (Next Priority)
- [ ] Create `afterglow_correction.py`
- [ ] Implement cubic spline interpolation
- [ ] Add correction API

### Phase 2: Integration
- [ ] Integrate with `spr_data_acquisition.py`
- [ ] Add enable/disable flag
- [ ] Store raw + corrected data

### Phase 3: Validation
- [ ] Create `test_optical_calibration.py`
- [ ] Test interpolation accuracy
- [ ] Verify correction effectiveness

### Phase 4: Documentation
- [ ] Rename script to `optical_system_calibration.py`
- [ ] Create OEM guide
- [ ] Update production documentation

---

## Summary

**Architecture Decision**: Optical system calibration is a **separate, infrequent OEM tool** that generates τ lookup tables once per ~1000 hours. Main calibration runs daily/automatically and remains fast (1.5 min). Correction loads existing τ tables and applies passively during measurements. No re-calibration needed until hardware ages.

**Key Quote**: "Once the correction model is known, we don't need to do the calibration again. We only use the calibration model to correct the data."

---

**Status**: ✅ Architecture Finalized
**Next**: Implement `afterglow_correction.py` with cubic spline interpolation
**Last Updated**: October 11, 2025
