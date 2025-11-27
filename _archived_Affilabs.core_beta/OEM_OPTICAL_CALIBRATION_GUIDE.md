# OEM Feature: Optical Calibration (Afterglow Characterization)

## Important: OEM/Factory Feature Only

This feature uses **customer-facing terminology** in the UI:
- **User sees:** "Run Optical Calibration…"
- **Internal name:** Afterglow calibration (LED phosphor decay characterization)

**Purpose:** Characterize LED phosphor decay characteristics across integration times for correction algorithms.

---

## Enabling OEM Features

1. Edit `settings/settings.py`:
   ```python
   DEV = True  # Enable OEM/factory features
   ```

2. Restart application

3. The **"Run Optical Calibration…"** button will appear in Advanced Settings

4. **After OEM work is complete**, set back to `DEV = False` to hide from end-users

---

## When to Run This

### Factory/Initial Setup
- After device assembly
- After LED PCB replacement
- After detector replacement
- Creates initial `optical_calibration.json`

### Service/Maintenance
- If optical calibration data is corrupted
- If missing channels in calibration file
- After optical path repairs

### Never Expose to End-Users
- This is internal system characterization
- End-users don't need to know about "afterglow"
- Use "Optical Calibration" terminology with customers

---

## Current Issue: Missing Channel 'D'

**File:** `config/devices/FLMT09116/optical_calibration.json`
**Status:** Only has channels ['a', 'b', 'c'] - **missing channel 'd'**

**Impact:** Afterglow correction disabled (requires all 4 channels)

**Fix:**
1. Set `DEV = True` in `settings/settings.py`
2. Start application: `python main_simplified.py`
3. Open Advanced Settings
4. Click **"Run Optical Calibration…"**
5. Wait ~5-10 minutes
6. Verify all 4 channels present:
   ```powershell
   python -c "import json; d=json.load(open('config/devices/FLMT09116/optical_calibration.json')); print(f'Channels: {list(d[\"channel_data\"].keys())}')"
   ```
7. Set `DEV = False` to hide OEM features

---

## Technical Details

### What It Measures
For each channel × integration time combination:
- Turn LED ON (250ms) to saturate phosphor
- Turn LED OFF and measure decay (250ms)
- Fit exponential: `signal(t) = baseline + amplitude × e^(-t/τ)`
- Store: τ (time constant), amplitude, baseline

### Integration Times Tested
Default: [10, 25, 40, 55, 70, 85] ms

### Independent Channel Characterization (KEY ADVANTAGE)

**Critical Design Feature:** Each LED's afterglow is calibrated INDEPENDENTLY.

This means the system can correct for ANY channel sequence, not just sequential patterns:

| Application | Channel Sequence | Correction Applied |
|------------|------------------|-------------------|
| **Current 4-channel** | A→B→C→D | B corrected by A, C by B, D by C |
| **Future 2-channel (non-adjacent)** | A→C | C corrected by A directly |
| **Future 2-channel (non-adjacent)** | B→D | D corrected by B directly |
| **Custom sequence** | D→A→B | A corrected by D, B by A |

**Why This Matters:**
- Future assays may use only 2 channels (not all 4)
- Those 2 channels may NOT be adjacent (e.g., A+C instead of A+B)
- By knowing ALL LED afterglows, any combination works
- No need to recalibrate for different channel patterns

**Example Scenario:**
```
Assay needs channels A and C only (skipping B):
  1. Measure channel A
  2. LED A turns off, wait 5ms
  3. Measure channel C
  4. Apply correction: corrected_C = measured_C - afterglow_from_A(5ms)

The system looks up channel A's specific afterglow characteristics
and corrects channel C accordingly - no channel B involved.
```

### Traditional Sequential Pattern (Current)
- Channel A ← corrected by Channel D afterglow
- Channel B ← corrected by Channel A afterglow
- Channel C ← corrected by Channel B afterglow
- Channel D ← corrected by Channel C afterglow

**Result:** Missing ANY channel breaks entire correction system

But this is just ONE possible pattern. The architecture supports any sequence.

### Duration
- ~5-10 minutes (24 measurements: 6 integration times × 4 channels)
- 250ms per measurement
- Includes curve fitting and validation

---

## Files

| File | Purpose |
|------|---------|
| `widgets/advanced.py` | OEM button UI (line 82-88) |
| `utils/afterglow_calibration.py` | Measurement algorithm |
| `Affilabs.core beta/afterglow_correction.py` | Load and apply correction |
| `config/devices/{serial}/optical_calibration.json` | Stored calibration data |
| `settings/settings.py` | `DEV` flag to enable/disable |

---

## Terminology Guide

| Internal (Code) | User-Facing (UI/Docs) |
|----------------|----------------------|
| Afterglow calibration | Optical calibration |
| Phosphor decay | Optical response |
| Afterglow correction | Optical correction |
| LED afterglow | LED characteristics |

**Why?** "Afterglow" is technical/academic terminology that can confuse customers. "Optical calibration" is clear and professional.

---

## Troubleshooting

### Button Not Visible
- Check `DEV = True` in `settings/settings.py`
- Restart application
- Look in Advanced Settings dialog

### Channel Fails During Calibration
1. Check LED functionality:
   ```python
   app.hardware_mgr.ctrl.set_intensity('d', 255)
   time.sleep(0.5)
   spectrum = app.hardware_mgr.usb.read_intensity()
   print(f"Signal: {spectrum.max()} counts")  # Should be > 1000
   app.hardware_mgr.ctrl.all_off()
   ```

2. Check error logs for specific failure reason

3. May indicate hardware issue (LED, detector, optical path)

### File Already Complete
If file already has all 4 channels, no action needed. Re-run only if:
- Data is corrupted
- After hardware replacement
- Instructed by support/engineering

---

**Created:** 2025-11-23
**Audience:** OEM/Factory/Service personnel only
**Customer-Facing Feature Name:** "Optical Calibration"
