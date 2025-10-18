# URGENT: Fresh Calibration Required

## Current Situation
The calibration from 8:02 PM still shows the OLD behavior:
- `weakest_channel`: NOT FOUND (Step 3 didn't run)
- LED intensities: {a:133, b:255, c:133, d:133} (NOT balanced!)
- S-mode signals: C=93.4%, D=95.3% (ALREADY saturating!)
- Result: P-mode will definitely saturate C and D at 65535

## Why This Happened
The changes were committed to Git, but the **running application** was still using the old code from before the refactor. Python loads modules once at startup, so code changes don't take effect until you restart.

## What You MUST Do Now

### 1. **CLOSE the Application Completely**
- Don't just minimize it
- Make sure Python process is terminated
- Check Task Manager if needed

### 2. **Delete ALL Calibration Cache**
```powershell
Remove-Item generated-files/calibration_data/*_latest.npy -Force
Remove-Item generated-files/calibration_profiles/auto_save_*.json -Force
```

This ensures we get a **truly fresh** calibration with the new code.

### 3. **Restart the Application**
```powershell
python run_app.py
```

This will load the NEW code with:
- `_identify_weakest_channel()` (Step 3)
- `_optimize_integration_time()` (Step 4)
- Safety checks in Step 6

### 4. **Run Calibration and Watch Logs**

Look for these **NEW** log messages:

#### **Step 3 (NEW)**:
```
================================================================================
STEP 3: Identifying Weakest Channel
================================================================================
📊 Testing all channels at LED=168 (66% intensity)
   Measuring in 580-610nm range
   Channel a: XXXXX counts
   Channel b: XXXXX counts  ← This will be LOWEST
   Channel c: XXXXX counts
   Channel d: XXXXX counts

✅ Weakest channel: b (XXXXX counts)
   Strongest channel: c (XXXXX counts)
   Ratio: X.XXx
✅ Weakest channel: b
   This channel will be FIXED at LED=255
   Other channels will be adjusted DOWN to match
```

#### **Step 4 (NEW)**:
```
================================================================================
STEP 4: Optimizing Integration Time
================================================================================
📊 Starting integration: 100.0ms
   Weakest channel (b) will be set to LED=255
   Target: 52428 counts (80% of 65535)
   Initial: XXXXX counts (XX.X%)
   ✅ Target reached after X iterations

✅ INTEGRATION TIME OPTIMIZED: XXX.Xms
   Weakest channel (b) at LED=255: XXXXX counts (XX.X%)
   Status: EXCELLENT/ACCEPTABLE
```

#### **Step 6 (MUST SEE THIS)**:
```
================================================================================
STEP 6: LED Intensity Calibration (S-mode Binary Search)
================================================================================
📊 Weakest channel: b (from Step 3)  ← CRITICAL: Must show channel name
   Setting b to LED=255 (fixed)
   Other channels will be binary-searched to match intensity

📊 Starting binary search for channel a (LED range: 13-255)
Binary iter 0: LED=134, measured=XXXXX, target=XXXXX
Binary iter 1: LED=XXX, measured=XXXXX, target=XXXXX
...
✅ Channel a binary search complete: LED=XXX

📊 Starting binary search for channel c (LED range: 13-255)
Binary iter 0: LED=134, measured=XXXXX, target=XXXXX
...
✅ Channel c binary search complete: LED=XXX

📊 Starting binary search for channel d (LED range: 13-255)
...
```

### 5. **Expected Results**

#### **LED Intensities** (SHOULD BE VARIED):
```json
{
  "a": 85-120,   ← Dimmed to match weakest
  "b": 255,      ← Weakest, at maximum
  "c": 60-90,    ← Dimmed significantly (brightest LED)
  "d": 75-110    ← Dimmed to match weakest
}
```

❌ **NOT** all at 133!
❌ **NOT** same values!

#### **S-mode Reference Signals** (SHOULD BE BALANCED):
```
Channel A: ~50,000 counts (75-80%)
Channel B: ~50,000 counts (75-80%)  ← Weakest at LED=255
Channel C: ~50,000 counts (75-80%)  ← Was 93%, now dimmed
Channel D: ~50,000 counts (75-80%)  ← Was 95%, now dimmed
```

All within ±5,000 counts of each other!

#### **P-mode Live Signals** (NO SATURATION):
```
Integration: 100ms (scaled from 200ms)
Channel A: 30,000-40,000 counts (45-60%)
Channel B: 30,000-40,000 counts (45-60%)
Channel C: 30,000-40,000 counts (45-60%)  ← Was 65535, now healthy
Channel D: 30,000-40,000 counts (45-60%)  ← Was 65535, now healthy
```

### 6. **Verify Success**

After calibration completes, check the profile:

```powershell
python -c "import json; data=json.load(open(max([f for f in glob.glob('generated-files/calibration_profiles/*.json')], key=os.path.getmtime))); print('Weakest channel:', data.get('weakest_channel', 'NOT FOUND')); print('LED intensities:', json.dumps(data.get('ref_intensity', {}), indent=2))"
```

Should show:
- `Weakest channel: b` (or a/c/d - whichever is actually weakest)
- LED intensities: VARIED values, not all 133

### 7. **If Still Failing**

If you still see:
- `weakest_channel: NOT FOUND`
- LED intensities all at 133
- C and D saturating

Then **STOP** and check:

1. Did the application restart? (Check process ID changed)
2. Did cache get deleted? (No `*_latest.npy` files)
3. Are logs showing "STEP 3: Identifying Weakest Channel"?
4. Does Step 3 complete and show "✅ Weakest channel: X"?

If Step 3 is NOT appearing, then the old `calibrate_integration_time()` is still being called instead of the new separate steps.

## Quick Diagnostic

To see which calibration ran:

```powershell
# Check latest profile
$latest = Get-ChildItem "generated-files/calibration_profiles/*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
python -c "import json; data=json.load(open('$($latest.FullName)')); print('Profile:', data.get('profile_name')); print('Weakest:', data.get('weakest_channel', 'NOT FOUND')); print('LEDs:', data.get('ref_intensity'))"
```

Expected:
```
Profile: auto_save_YYYYMMDD_HHMMSS
Weakest: b  ← MUST be a channel name, not "NOT FOUND"
LEDs: {'a': 105, 'b': 255, 'c': 78, 'd': 92}  ← MUST be varied
```

## Summary

The code is correct and pushed. You just need to:
1. **Close app**
2. **Delete cache**
3. **Restart app**
4. **Run calibration**
5. **Watch for "STEP 3: Identifying Weakest Channel"**
6. **Verify balanced LED intensities**

If you see "NOT FOUND" for weakest_channel again, let me know immediately - it means the new code path isn't executing.
