# PyInstaller Build - Current Status

**Updated**: 2026-02-10 16:10
**Ready to Build**: ⚠️ Not yet - Issue #2 (resource paths) still needs fixing

---

## ✅ ISSUES FIXED

### Issue #1: Missing `affilabs/data` ✅ FIXED
**Status**: Added to .spec file line 41
```python
('affilabs/data', 'affilabs/data'),  # CRITICAL: Spark AI knowledge base
```

### Issue #3: Missing Dependencies ✅ FIXED
**Status**: All dependencies installed and added to .spec
- ✅ PyInstaller installed
- ✅ pyusb installed (just now - fixes seabreeze USB communication)
- ✅ Added to hiddenimports:
  - `seabreeze.pyseabreeze`
  - `usb`, `usb.core`, `usb.backend`, `usb.backend.libusb1`

---

## 🔴 CRITICAL ISSUE REMAINING

### Issue #2: 15 Files Using Broken Resource Paths
**Status**: ⚠️ NOT FIXED - Will cause exe to crash!

**Problem**: These files use `Path(__file__).parent` which breaks in PyInstaller exe

**Files requiring fix** (in priority order):
1. ✅ `affilabs/utils/resource_path.py` - Helper created
2. ❌ `affilabs/affilabs_core_ui.py` (line 1193) - Icon loading
3. ❌ `affilabs/utils/splash_screen.py` (lines 145, 229) - Splash icon
4. ❌ `affilabs/core/hardware_manager.py` (line 609) - Config loading
5. ❌ `affilabs/services/spark/knowledge_base.py` (line 45) - **CRITICAL** - Spark AI
6. ❌ `affilabs/utils/device_configuration.py` (lines 180, 190) - Device configs
7. ❌ 9 more files listed in PYINSTALLER_FIXES_REQUIRED.md

**Impact if not fixed:**
- ❌ Application will crash on startup (can't find icon)
- ❌ Spark AI won't work (can't find knowledge_base.json)
- ❌ Device configurations won't load
- ❌ Splash screen won't show

**Fix required for each file:**
```python
# BEFORE (BREAKS IN EXE):
icon_path = Path(__file__).parent / "ui" / "img" / "icon.ico"

# AFTER (WORKS IN EXE):
from affilabs.utils.resource_path import get_affilabs_resource
icon_path = get_affilabs_resource("ui/img/icon.ico")
```

**See**: PYINSTALLER_FIXES_REQUIRED.md for exact code changes

---

## 📊 BUILD READINESS CHECKLIST

Before running `pyinstaller Affilabs-Core.spec`:

- [x] ✅ Issue #1: affilabs/data added to .spec
- [x] ✅ Issue #3: Dependencies installed (pyusb, PyInstaller)
- [x] ✅ Issue #3: hiddenimports updated with USB modules
- [ ] ❌ Issue #2: Fix 15 files to use get_affilabs_resource()
- [ ] ⚠️  Test in dev: Run `python main.py` - should work with no errors

---

## ⚡ QUICK BUILD (SKIP ISSUE #2 - NOT RECOMMENDED)

If you want to build NOW without fixing Issue #2:

```bash
pyinstaller Affilabs-Core.spec
```

**Result**: Exe will build but will crash when:
- Loading main window (can't find icon)
- Opening Spark AI (can't find knowledge_base.json)
- Loading device configs

**Recommendation**: ❌ DON'T DO THIS - Fix Issue #2 first!

---

## ✅ PROPER BUILD PROCESS

### Step 1: Fix Resource Paths (30-60 minutes)
Update all 15 files listed in PYINSTALLER_FIXES_REQUIRED.md

Start with highest priority:
1. `affilabs/affilabs_core_ui.py` (main icon)
2. `affilabs/utils/splash_screen.py` (splash icon)
3. `affilabs/services/spark/knowledge_base.py` (Spark AI data)
4. `affilabs/core/hardware_manager.py` (device configs)

### Step 2: Test in Development
```bash
python main.py
```

Should work perfectly with no FileNotFoundError messages.

### Step 3: Clean Build Artifacts
```bash
rmdir /s /q build dist
del /s /q __pycache__ *.pyc
```

### Step 4: Build with PyInstaller
```bash
pyinstaller Affilabs-Core.spec
```

Watch for errors during build:
- Look for "ModuleNotFoundError" → add to hiddenimports
- Look for "FileNotFoundError" → add to datas

### Step 5: Test the Exe
```bash
cd dist
.\Affilabs-Core-v2.0.2.exe
```

Test these features:
1. ✅ Icon displays in window
2. ✅ Splash screen appears
3. ✅ Spark AI loads (knowledge base accessible)
4. ✅ Device configs load
5. ✅ Hardware connects properly
6. ✅ Compression Assistant works

---

## 🐛 IF BUILD FAILS

### Error: "ModuleNotFoundError: No module named 'X'"
**Fix**: Add 'X' to hiddenimports in .spec file

### Error: "FileNotFoundError: knowledge_base.json"
**Fix**: You forgot Issue #2 - update the file to use get_affilabs_resource()

### Error: "FileNotFoundError: affinite2.ico"
**Fix**: Update affilabs_core_ui.py and splash_screen.py to use get_affilabs_resource()

---

## 🎯 CURRENT RECOMMENDATION

**Option 1**: Fix Issue #2 first (30-60 min), then build
- ✅ Proper solution
- ✅ Exe will work correctly
- ✅ No crashes on startup

**Option 2**: Build now, debug crashes later
- ❌ Exe will crash immediately
- ❌ Wastes time troubleshooting
- ❌ Not recommended

**Choose Option 1** - Fix the resource paths first, then build once correctly.

---

## 📝 NOTES

### Python Version
- Current: Python 3.9.12
- Target: Python 3.12 (not installed)
- Status: Code is compatible with both versions
- Action: No changes needed for Python version

### Calibration Dialog Enhancements
- ✅ Step descriptions added
- ✅ Elapsed time tracking working
- ✅ All changes persistent
- ✅ Ready for PyInstaller (no special handling needed)

### Dependencies Recently Added
- pyusb (for USB spectrometer)
- pydantic, pandas, requests (already in .spec)

---

**NEXT STEP**: Fix Issue #2 (resource paths) before building. See PYINSTALLER_FIXES_REQUIRED.md for exact changes.
