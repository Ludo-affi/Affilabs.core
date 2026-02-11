# Calibration Dialog - Before & After

## BEFORE (What you had)
```
┌─────────────────────────────────────────────┐
│         Calibrating SPR System              │
├─────────────────────────────────────────────┤
│  ████████████░░░░░░░  45%                   │
├─────────────────────────────────────────────┤
│  Calibrating... (2m 15s elapsed)            │
├─────────────────────────────────────────────┤
│  Step 4/6                                   │  ← Generic, unclear
└─────────────────────────────────────────────┘
```

**Problem:** User doesn't know what "Step 4/6" means or what the system is doing.

---

## AFTER (What you have now)
```
┌─────────────────────────────────────────────┐
│         Calibrating SPR System              │
├─────────────────────────────────────────────┤
│  S-Mode LED Convergence + Reference Capture │  ← NEW! Clear description
├─────────────────────────────────────────────┤
│  ████████████░░░░░░░  45%                   │
├─────────────────────────────────────────────┤
│  Calibrating... (2m 15s elapsed)            │  ← Shows work continuing
├─────────────────────────────────────────────┤
│  Step 4/6: S-Mode LED Convergence +         │  ← Full details
│  Reference Capture                          │
└─────────────────────────────────────────────┘
```

**Benefits:**
✅ User knows exactly what step is running
✅ Elapsed time shows system is working (not frozen)
✅ Progress bar shows overall completion
✅ Professional appearance

---

## All 6 Step Descriptions

### During Calibration, users will see:

**Step 1/6** (0-17%):
```
Hardware Validation & LED Verification
```
- Checking controller and spectrometer
- Turning off all LEDs
- Preparing for measurement

---

**Step 2/6** (17-30%):
```
Wavelength Calibration
```
- Reading detector EEPROM
- Calculating SPR wavelength range (560-720nm)
- Defining measurement ROI

---

**Step 3/6** (30-45%):
```
LED Brightness Measurement & 3-Stage Linear Model Load
```
- Loading LED calibration model
- Identifying weakest LED channel
- Preparing for convergence

---

**Step 4/6** (45-65%):
```
S-Mode LED Convergence + Reference Capture
```
- Positioning polarizer to S-mode
- Running LED convergence algorithm
- Capturing S-pol reference spectra
- **⏱️ This step can take 1-2 minutes**

---

**Step 5/6** (65-85%):
```
P-Mode LED Convergence + Reference + Dark Capture
```
- Switching polarizer to P-mode
- Running LED convergence for P-pol
- Capturing P-pol reference spectra
- Capturing dark spectrum (LEDs OFF)
- **⏱️ This step can take 1-2 minutes**

---

**Step 6/6** (85-100%):
```
QC Validation & Result Packaging
```
- Validating reference quality
- Calculating transmission curves
- Checking SPR dip detection
- Packaging calibration data

---

## Example Scenario

### Situation: Step 4 is running, progress bar stuck at 47% for 90 seconds

**What user sees:**
```
┌─────────────────────────────────────────────┐
│         Calibrating SPR System              │
├─────────────────────────────────────────────┤
│  S-Mode LED Convergence + Reference Capture │  ← They know what's happening
├─────────────────────────────────────────────┤
│  █████████░░░░░░░░░░░  47%                  │  ← Not moving, but...
├─────────────────────────────────────────────┤
│  Calibrating... (1m 30s elapsed)            │  ← Time is ticking = still working!
├─────────────────────────────────────────────┤
│  Step 4/6: S-Mode LED Convergence +         │
│  Reference Capture                          │
└─────────────────────────────────────────────┘
```

**User reaction:** "OK, it's doing LED convergence, and the timer is ticking, so it's still working. I'll wait."

---

### Without the enhancements, user would see:
```
┌─────────────────────────────────────────────┐
│         Calibrating SPR System              │
├─────────────────────────────────────────────┤
│  ████████░░░░░░░░░░░░  47%                  │  ← Stuck?
├─────────────────────────────────────────────┤
│  Working...                                 │  ← No context
├─────────────────────────────────────────────┤
│  Step 4/6                                   │  ← What does this mean?
└─────────────────────────────────────────────┘
```

**User reaction:** "Is it frozen? What is Step 4? Should I restart?"

---

## Technical Details

### Label Properties
- **Font**: System default (Segoe UI on Windows)
- **Size**: 13px
- **Weight**: 600 (semi-bold)
- **Color**: #007AFF (iOS blue)
- **Alignment**: Center
- **Word Wrap**: Enabled
- **Visibility**: Hidden until calibration starts

### Update Frequency
- **Step description**: Updates at start of each step (6 times total)
- **Elapsed time**: Updates every 1 second
- **Progress bar**: Updates whenever backend reports progress

### Performance Impact
- ✅ Zero performance impact
- ✅ Updates happen via Qt signals (thread-safe)
- ✅ No blocking operations
- ✅ No additional CPU usage

---

## Code Quality

- ✅ **Type hints**: All methods properly typed
- ✅ **Thread safety**: Qt Signal/Slot pattern used throughout
- ✅ **Error handling**: Try/except blocks for widget deletion
- ✅ **Documentation**: Docstrings for all new methods
- ✅ **Single Source of Truth**: Step descriptions defined once
- ✅ **No duplication**: All code references central CALIBRATION_STEPS dict

---

## Testing

### Manual Test Steps:
1. Launch application
2. Start calibration
3. Observe step descriptions appearing at:
   - 5% - Step 1 description
   - 17% - Step 2 description
   - 30% - Step 3 description
   - 45% - Step 4 description
   - 65% - Step 5 description
   - 85% - Step 6 description

4. Verify elapsed time continues updating every second
5. Verify UI remains responsive (can move window, etc.)
6. Verify no crashes or freezes

### Expected Behavior:
- Blue step description appears and updates
- Elapsed time ticks every second
- Progress bar advances smoothly
- Dialog centers on parent window
- No console errors

---

**Status**: ✅ Implementation complete - Ready for testing
