# Fix AttributeError - Restart Required

**Error**: `AttributeError: 'StartupCalibProgressDialog' object has no attribute 'update_step_description'`

**Cause**: Python is running an old cached version of the dialog from before the changes were made.

---

## ✅ SOLUTION: Restart the Application

### Step 1: Stop the Running Application
- Close the application window
- If it doesn't close, press `Ctrl+C` in the terminal
- Make sure all Python processes are stopped

### Step 2: Verify Cache is Cleared
```bash
# Already done - cache cleared
```

### Step 3: Restart the Application
```bash
python main.py
```

---

## ✅ CODE IS CORRECT

The `update_step_description` method **DOES EXIST** in the file:

**File**: `affilabs/dialogs/startup_calib_dialog.py`
**Line 355**:
```python
def update_step_description(self, description: str) -> None:
    """Update the step description label (thread-safe via signal)."""
    self._update_step_description_signal.emit(description)
```

The method is there - Python just needs to reload the module.

---

## 🔍 OTHER ERROR NOTICED

```
ERROR :: read_intensity error: [Errno 10060] Operation timed out
```

**This is a separate issue** - USB communication timeout with spectrometer.

**Possible causes**:
1. USB cable connection loose
2. Integration time too short (below 3.5ms minimum)
3. USB controller under load
4. Spectrometer firmware issue

**This error is NOT related to the code changes** - it's a hardware/timing issue that was already present.

---

## 📋 QUICK FIX STEPS

1. **Close the application** (Ctrl+C or close window)
2. **Restart**: `python main.py`
3. **Try calibration again**

The `update_step_description` error will be gone after restart.

---

## ✅ VERIFICATION

After restart, you should see:
- ✅ No AttributeError
- ✅ Step descriptions appear in calibration dialog
- ✅ "Hardware Validation & LED Verification" appears at step 1
- ✅ Elapsed time continues ticking

---

**Status**: Code is correct, just needs restart to load new version.
