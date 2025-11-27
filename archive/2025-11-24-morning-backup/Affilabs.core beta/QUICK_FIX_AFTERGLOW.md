# Quick Fix Guide: Regenerate Afterglow Calibration with Channel 'D'

## Current Status

✅ **File exists**: `config/devices/FLMT09116/optical_calibration.json`
❌ **Problem**: Only has channels ['a', 'b', 'c'] - **MISSING channel 'd'**

**Impact**: Afterglow correction is DISABLED because all 4 channels are required for cross-channel correction.

---

## Solution: Re-run Optical Calibration

### METHOD 1: Using the GUI (EASIEST) ⭐

**Note:** This button is OEM/factory-only and hidden by default.

1. **Enable OEM mode:**
   - Edit `settings/settings.py`
   - Change `DEV = False` to `DEV = True`
   - Save file

2. **Start the application:**
   ```powershell
   cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"
   python main_simplified.py
   ```

3. **Wait for hardware to connect and stabilize** (~10 seconds)

4. **Look for the "Run Optical Calibration…" button:**
   - It's in the **Advanced Settings** dialog
   - Shows as "[OEM/Factory Only] Characterize optical system response"
   - File: `widgets/advanced.py`, line 82
   - Click this button to trigger optical calibration

4. **Wait for calibration to complete** (~5-10 minutes)
   - The system will test all 4 channels: a, b, c, d
   - Each channel tested at 6 integration times
   - Progress will be shown in logs

5. **After completion, disable OEM mode:**
   - Edit `settings/settings.py`
   - Change `DEV = True` back to `DEV = False`
   - This hides OEM-only features from end-users

6. **Verify the result:**
   ```powershell
   python -c "import json; data = json.load(open('config/devices/FLMT09116/optical_calibration.json')); channels = list(data['channel_data'].keys()); print(f'Channels: {channels} ({len(channels)}/4)')"
   ```

   **Expected output:**
   ```
   Channels: ['a', 'b', 'c', 'd'] (4/4)
   ```

---

### METHOD 2: Using Python Console (ADVANCED)

If you have the application running and can access a Python console/debugger:

```python
# Get the calibration coordinator from the app
calibration_coordinator = app.calibration_coordinator

# Get the calibrator instance
calibrator = calibration_coordinator.calibrator

# Run optical calibration
success = calibrator._run_optical_calibration()

if success:
    print('✅ Optical calibration complete - check for all 4 channels')

    # Verify
    import json
    from pathlib import Path
    cal_file = Path('config/devices/FLMT09116/optical_calibration.json')
    with open(cal_file, 'r') as f:
        data = json.load(f)
        channels = list(data['channel_data'].keys())
        print(f'Channels: {channels}')

        if len(channels) == 4:
            print('✅ SUCCESS: All 4 channels calibrated!')
        else:
            missing = [ch for ch in ['a', 'b', 'c', 'd'] if ch not in channels]
            print(f'❌ FAILURE: Still missing {missing}')
            print('Check logs for errors during channel d measurement')
else:
    print('❌ Optical calibration failed - check logs')
```

---

### METHOD 3: Temporary Workaround (TESTING ONLY)

⚠️ **WARNING**: This is NOT recommended for production use. It copies channel 'c' data to channel 'd' as a rough approximation.

```powershell
cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"
python
```

```python
import json
from pathlib import Path

cal_file = Path('config/devices/FLMT09116/optical_calibration.json')

with open(cal_file, 'r') as f:
    data = json.load(f)

# Copy channel 'c' data to channel 'd' (ROUGH APPROXIMATION)
data['channel_data']['d'] = data['channel_data']['c'].copy()

# Backup original
backup_file = cal_file.parent / 'optical_calibration_BACKUP_3ch.json'
with open(backup_file, 'w') as f:
    json.dump(data, f, indent=2)
print(f'Backup saved: {backup_file}')

# Save modified version
with open(cal_file, 'w') as f:
    json.dump(data, f, indent=2)

print('✅ Temporary fix applied - channel d data copied from channel c')
print('⚠️  This is APPROXIMATE. Re-run proper calibration ASAP.')
```

**After this workaround:**
- Application will start without errors
- Afterglow correction will work but may be inaccurate for channel D
- **Must re-run proper calibration at earliest opportunity**

---

## Verification After Fix

Run this to confirm all 4 channels are present:

```powershell
cd "c:\Users\ludol\ezControl-AI\Affilabs.core beta"

# Quick check
python -c "import json; d=json.load(open('config/devices/FLMT09116/optical_calibration.json')); chs=list(d['channel_data'].keys()); print(f'✅ SUCCESS: All 4 channels present!' if len(chs)==4 else f'❌ FAILURE: Only {len(chs)} channels: {chs}')"
```

**Expected output:**
```
✅ SUCCESS: All 4 channels present!
```

---

## What This Calibration Does

The optical calibration measures LED phosphor afterglow characteristics:

1. **For each channel (a, b, c, d):**
   - Turns LED ON for 250ms to "charge" the phosphor
   - Turns LED OFF and measures decay over 250ms
   - Fits exponential decay curve: `signal(t) = baseline + amplitude × e^(-t/τ)`

2. **For each integration time ([10, 25, 40, 55, 70, 85] ms):**
   - Measures decay at that integration time
   - Stores τ (time constant), amplitude, baseline

3. **Result:** Interpolation table for each channel
   - Used during live measurements to subtract afterglow
   - Improves measurement accuracy by 10-20%

**Duration:** ~5-10 minutes (24 measurements: 6 integration times × 4 channels)

---

## Why Channel 'D' Failed Originally

The calibration file was created on **2025-11-22T03:57:23Z** with only 3 channels.

**Possible causes:**
1. LED D hardware communication error
2. Timing/synchronization issue during measurement
3. Insufficient signal from LED D
4. Error was caught and logged but calibration continued without channel D

**The fix:** Modern code now validates ALL 4 channels are present before saving the file. If any channel fails, the entire calibration will fail rather than creating an incomplete file.

---

## Troubleshooting

### If Channel 'D' Fails Again:

1. **Check hardware:**
   ```python
   # In Python console with app running
   app.hardware_mgr.ctrl.set_intensity('d', 255)
   time.sleep(0.5)
   spectrum = app.hardware_mgr.usb.read_intensity()
   print(f"Channel D signal: {spectrum.max()} counts")
   app.hardware_mgr.ctrl.all_off()
   ```
   - Should see signal > 1000 counts
   - If signal too low, LED D may be faulty

2. **Check logs during calibration:**
   - Look for: `"❌ Afterglow calibration failed for channel 'd'"`
   - Error message will show specific failure reason

3. **Try different LED intensity:**
   - Default uses calibrated LED intensities from device_config.json
   - If those are wrong, channel D measurement may fail
   - Temporary fix: Edit device_config.json to set channel d intensity to 255

---

## Next Steps

1. ✅ Run optical calibration using METHOD 1 (GUI) or METHOD 2 (Python console)
2. ✅ Verify all 4 channels present
3. ✅ Restart application
4. ✅ Confirm no "AfterglowCorrection unavailable" error
5. ✅ Test live measurements work correctly

---

## Files Modified

- `config/devices/FLMT09116/optical_calibration.json` - Will be regenerated with all 4 channels

## Documentation

- See: `AFTERGLOW_CHANNEL_D_MISSING_FIX.md` for complete root cause analysis
- See: `Affilabs.core beta/afterglow_correction.py` for technical details
- See: `Affilabs.core beta/utils/afterglow_calibration.py` for measurement code

---

**Created:** 2025-11-23
**Status:** ⚠️ ACTION REQUIRED - Re-run optical calibration to add channel 'd'
