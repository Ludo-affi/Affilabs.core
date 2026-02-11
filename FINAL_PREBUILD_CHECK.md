# FINAL PRE-BUILD CHECKLIST

**Status**: 🟡 In Progress | ⚠️ 2 critical issues remaining + 1 dependency fix

---

## ✅ VERIFIED WORKING

1. **Resource Path Helper** - Created and tested
   - `affilabs/utils/resource_path.py` exists
   - Function works correctly in dev mode
   - Returns: `C:\...\affilabs\ui\img\affinite2.ico`
   - File exists: ✓

2. **Python Environment**
   - Python 3.9.12 (64-bit)
   - Not frozen (running from source)

3. **.spec File Basics**
   - File exists: `Affilabs-Core.spec`
   - Entry point: `main.py`
   - libusb DLL handling configured
   - Hidden imports declared

---

## 🔴 CRITICAL ISSUES TO FIX BEFORE BUILDING

### Issue #1: Missing `affilabs/data` in .spec

**Problem:** `knowledge_base.json` won't be found in exe!

**Location:** `Affilabs-Core.spec` line 38-48

**Fix:** Add this line to `datas=[]`:
```python
datas=[
    ('VERSION', '.'),
    ('affilabs/ui', 'affilabs/ui'),
    ('affilabs/config', 'affilabs/config'),
    ('affilabs/data', 'affilabs/data'),  # ← ADD THIS LINE
    ('affilabs/convergence/models', 'affilabs/convergence/models'),
    ('detector_profiles', 'detector_profiles'),
    # ... rest ...
],
```

**Files affected:**
- `affilabs/data/spark/knowledge_base.json` ✓ Found
- `affilabs/data/spark/qa_history.json` ✓ Found

---

### Issue #2: 15 Files Using Broken Resource Paths

**Problem:** All use `Path(__file__).parent` which breaks in exe!

**Files requiring fix:**
1. `affilabs/affilabs_core_ui.py` (line 1193) - Icon loading
2. `affilabs/utils/splash_screen.py` (lines 145, 229) - Icon loading
3. `affilabs/core/hardware_manager.py` (line 609) - Config loading
4. `affilabs/core/oem_model_training.py` (line 542) - Config loading
5. `affilabs/presenters/navigation_presenter.py` (line 333) - Image loading
6. `affilabs/services/spark/knowledge_base.py` (line 45) - **CRITICAL** - Spark AI data
7. `affilabs/utils/device_configuration.py` (lines 180, 190) - Device configs
8. `affilabs/utils/oem_calibration_tool.py` (lines 868, 871) - Device configs
9. `affilabs/utils/pipelines/__init__.py` (line 35) - Pipeline config
10. `affilabs/tools/plot_s_ref_latest.py` (line 18) - Config dir
11. `affilabs/tools/print_sp_from_config.py` (line 7) - Config dir

**How to fix each:** See `PYINSTALLER_FIXES_REQUIRED.md` for exact code changes.

**Quick fix template:**
```python
# BEFORE:
icon_path = Path(__file__).parent / "ui" / "img" / "icon.ico"

# AFTER:
from affilabs.utils.resource_path import get_affilabs_resource
icon_path = get_affilabs_resource("ui/img/icon.ico")
```

---

### Issue #3: Missing Dependencies (PARTIALLY FIXED)

**Problem:** Missing required packages for hardware communication!

**Status:**
- ✅ PyInstaller installed
- ✅ pyusb installed (just fixed - required for USB4000 spectrometer)
- ⚠️ Need to verify all dependencies in requirements.txt are installed

**Recent fix:**
```bash
pip install pyusb
```

**Verify all dependencies:**
```bash
pip install -r requirements.txt
```

---

## 📋 PRE-BUILD CHECKLIST

Before running `pyinstaller Affilabs-Core.spec`:

- [ ] **Issue #1 Fixed:** Added `('affilabs/data', 'affilabs/data')` to .spec
- [ ] **Issue #2 Fixed:** All 15 files updated to use `get_affilabs_resource()`
- [ ] **Issue #3 Fixed:** PyInstaller installed (`pip install pyinstaller`)
- [ ] **Test in dev:** Run `python main.py` - should work with no errors
- [ ] **Clean build artifacts:**
  ```bash
  rmdir /s /q build dist
  del /s /q __pycache__ *.pyc
  ```

---

## 🎯 BUILD COMMAND

Once all issues are fixed:

```bash
# 1. Clean previous builds
rmdir /s /q build dist 2>nul

# 2. Build
pyinstaller Affilabs-Core.spec

# 3. Test
cd dist
.\Affilabs-Core-v2.0.2.exe
```

---

## 🐛 IF BUILD FAILS

### "ModuleNotFoundError: No module named 'affilabs'"
**Fix:** Add to .spec `hiddenimports=['affilabs', 'affilabs.utils', 'affilabs.utils.resource_path']`

### "FileNotFoundError: knowledge_base.json"
**Fix:** You forgot Issue #1 - add `affilabs/data` to datas

### "FileNotFoundError: affinite2.ico"
**Fix:** You forgot Issue #2 - update file to use `get_affilabs_resource()`

### "AttributeError: 'NoneType' object has no attribute 'reset'"
**Fix:** Already fixed in `usb4000_wrapper.py` - ignore if at shutdown only

---

## ✅ AFTER SUCCESSFUL BUILD

Test these features in the exe:

1. **Icon displays** - Window should show AffiLabs icon
2. **Splash screen** - Should appear with icon
3. **Device configs load** - Hardware connects properly
4. **Spark AI works** - Knowledge base loads
5. **Compression Assistant** - Loads calibration data
6. **No console spam** - No FileNotFoundError messages

---

## 📊 PRIORITY ORDER

**Fix in this order:**

1. **FIRST:** Issue #1 (add affilabs/data to .spec) - 2 minutes
2. **SECOND:** Issue #3 (install PyInstaller) - 1 minute
3. **THIRD:** Issue #2 (fix 15 files) - 30-60 minutes
   - Start with highest priority:
     - `affilabs/affilabs_core_ui.py` (main window icon)
     - `affilabs/utils/splash_screen.py` (splash icon)
     - `affilabs/services/spark/knowledge_base.py` (Spark AI)
     - `affilabs/core/hardware_manager.py` (device configs)

---

## 🚀 QUICK START

If you want to build NOW (without fixing Issue #2):

1. Fix Issue #1 (add affilabs/data)
2. Install PyInstaller (Issue #3)
3. Build and test

**Result:** Exe will build but may crash when loading icons/images.

For production release, fix all 3 issues first!

---

**Last check:** 2026-02-10
**Blocking issues:** 3
**Documentation:** Complete (3 files created)
