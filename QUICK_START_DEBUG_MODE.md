# Quick Start Guide - Debug Mode

## How to Test

### Option 1: Bypass Calibration (Fastest)
1. Launch application: `.\run_app_312.ps1`
2. Press **`Ctrl+Shift+C`** (calibration bypass)
3. Click **"Start"** button
4. **Watch for crash** - if no crash, UI opens successfully!

### Option 2: After Real Calibration
1. Launch application: `.\run_app_312.ps1`
2. Connect hardware
3. Run calibration normally (Settings → Calibrate)
4. Wait for calibration to complete
5. Click **"Start"** button
6. **Watch for crash** - Start button now does NOT upload method

---

## What's Different?

### Before (Crashed):
```
Click Start
  → Check calibration
  → Upload method to controller ❌ CRASH HERE?
  → Switch polarizer
  → Set integration time
  → Start acquisition thread
  → Open live data dialog
```

### After (Debug Mode):
```
Click Start
  → Open live data dialog ✅ UI ONLY
  → Unlock buttons ✅ UI ONLY
  → Update UI state ✅ UI ONLY
  → Show debug message
  → DONE (no hardware interaction)
```

---

## What to Look For

### If App CRASHES:
- **Before dialog opens**: Issue in button click handling or pre-flight checks
- **During dialog open**: Issue in `LiveDataDialog` constructor or Qt threading
- **After dialog opens**: Issue in UI state update or button enabling

### If App DOES NOT CRASH:
🎉 **SUCCESS!** The crash is in the hardware/method upload layer, not the UI!

Next step: Gradually add back hardware interactions:
1. Add polarizer switching only
2. Add integration time setting only
3. Add LED intensity setting only
4. Add full method upload

---

## Debug Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+C` | Bypass calibration (mark as calibrated, no hardware) |
| `Ctrl+Shift+T` | Test acquisition thread (disabled by default) |

---

## Log Messages to Watch

Success path:
```
🚀 User requested start - SIMPLIFIED MODE (UI only, no method upload)
📊 Opening live data dialog (UI only)...
✅ Live data dialog opened
🔓 Unlocking UI elements (simulating post-calibration)...
✅ UI elements unlocked
🎭 Setting UI to 'acquiring' state (cosmetic only)...
✅ UI state updated
✅ SIMPLIFIED START COMPLETE - UI ready, no hardware interaction
```

If you see all these messages and then crash → UI issue
If you don't see all these messages → Button handling issue

---

## Emergency Revert

If you need to restore normal behavior:

```powershell
# Open main_simplified.py
# Find _on_start_button_clicked() method (around line 615)
# Replace the entire method with the original implementation
# (Or use git to revert the file)
```

---

## Questions to Answer

After testing, document:

1. **Did the app crash?** (Yes/No)
2. **When did it crash?** (Before dialog / During dialog / After dialog)
3. **Last log message before crash?** (Copy the line)
4. **Any error dialog shown?** (Screenshot if possible)
5. **Windows error dialog?** (Application stopped responding)

---

## Expected Time to Test

- **Option 1** (Bypass): 30 seconds
- **Option 2** (Real calibration): 5-10 minutes

Choose Option 1 first for fastest feedback!
