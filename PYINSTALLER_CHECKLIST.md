# PyInstaller Preparation Checklist

## ✅ ALREADY DONE
- [x] .spec file configured with data files
- [x] Hidden imports declared (seabreeze, scipy, sklearn, etc.)
- [x] libusb DLL bundling configured
- [x] settings.py handles frozen state
- [x] VERSION file bundling configured

---

## 🔴 CRITICAL FIXES REQUIRED

### 1. **Fix Resource Path Loading** (BREAKS IN EXE!)

**Files that MUST be updated:**

#### A. `affilabs/affilabs_core_ui.py` (Line ~1193)
**BEFORE:**
```python
icon_path = Path(__file__).parent / "ui" / "img" / "affinite2.ico"
if icon_path.exists():
    icon = QIcon(str(icon_path))
```

**AFTER:**
```python
from affilabs.utils.resource_path import get_affilabs_resource

icon_path = get_affilabs_resource("ui/img/affinite2.ico")
if icon_path.exists():
    icon = QIcon(str(icon_path))
```

---

#### B. `affilabs/utils/splash_screen.py` (Lines ~145, ~229)
**BEFORE:**
```python
icon_path = Path(__file__).parent.parent / "ui" / "img" / "affinite2.ico"
if icon_path.exists():
    icon_pixmap = QPixmap(str(icon_path))
```

**AFTER:**
```python
from affilabs.utils.resource_path import get_affilabs_resource

icon_path = get_affilabs_resource("ui/img/affinite2.ico")
if icon_path.exists():
    icon_pixmap = QPixmap(str(icon_path))
```

---

#### C. **Search for ALL instances:**
Run this to find all files that need fixing:
```bash
grep -rn "__file__.*parent.*ui\|__file__.*parent.*img\|__file__.*parent.*config" affilabs/
```

**Common patterns to replace:**
- `Path(__file__).parent / "ui" / "img"` → `get_affilabs_resource("ui/img")`
- `Path(__file__).parent / "config"` → `get_affilabs_resource("config")`
- `Path(__file__).parent.parent / "ui"` → `get_affilabs_resource("ui")`

---

### 2. **Update .spec File** - Add Missing Resources

**File:** `Affilabs-Core.spec`

**Check these are included in `datas=[]` section:**
```python
datas=[
    ('VERSION', '.'),
    ('affilabs/ui', 'affilabs/ui'),  # ✅ Already there
    ('affilabs/config', 'affilabs/config'),  # ✅ Already there
    ('affilabs/convergence/models', 'affilabs/convergence/models'),  # ✅ Already there

    # ADD THESE IF MISSING:
    ('affilabs/data', 'affilabs/data'),  # knowledge_base.json, etc.
    ('calibrations', 'calibrations'),  # If you have calibration files
    ('ui/img', 'ui/img'),  # If you have ui/img separate from affilabs/ui/img
],
```

---

### 3. **Check Hidden Imports** (Add if missing)

**File:** `Affilabs-Core.spec`

**Verify these are in `hiddenimports=[]`:**
```python
hiddenimports=[
    # Qt/PySide6
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',

    # Hardware
    'seabreeze',
    'seabreeze.cseabreeze',
    'seabreeze.pyseabreeze',  # ADD THIS
    'libusb_package',

    # Scientific
    'numpy',
    'scipy',
    'scipy.special._cdflib',
    'scipy.integrate',
    'sklearn',
    'sklearn.ensemble',
    'joblib',

    # Plotting
    'pyqtgraph',
    'pyqtgraph.graphicsItems',

    # Affilabs modules
    'affilabs.utils.resource_path',  # ADD THIS (NEW)
    'standalone_tools.compression_trainer_ui',
],
```

---

### 4. **Icon File Path** (Line 118 in .spec)

**BEFORE:**
```python
icon=['ui\\img\\affinite2.ico'],
```

**AFTER:**
```python
icon='affilabs/ui/img/affinite2.ico',  # Use forward slashes, no brackets
```

---

### 5. **Test in Development First**

Before building, test the resource_path helper works:

```python
# Add this test to main.py or run separately:
from affilabs.utils.resource_path import get_affilabs_resource

icon_path = get_affilabs_resource("ui/img/affinite2.ico")
print(f"Icon path: {icon_path}")
print(f"Exists: {icon_path.exists()}")
```

---

## 🟡 RECOMMENDED IMPROVEMENTS

### 6. **Console Window** (Line 112 in .spec)

**Current:**
```python
console=True,
```

**For production release:**
```python
console=False,  # Hides black console window
```

Keep `console=True` during testing to see errors!

---

### 7. **Add Compression** (Already enabled with UPX)

Your .spec already has:
```python
upx=True,
```

This is good - it compresses the exe by ~50%.

---

### 8. **Clean Up Before Building**

```bash
# Delete these before building:
rmdir /s /q build
rmdir /s /q dist
rmdir /s /q __pycache__
del /s *.pyc
```

---

## 📋 BUILD PROCESS

### Step 1: Apply All Fixes Above

### Step 2: Build the EXE
```bash
pyinstaller Affilabs-Core.spec
```

### Step 3: Test the EXE
```bash
cd dist
.\Affilabs-Core-v2.0.2.exe
```

### Step 4: Check for Missing Files

If the exe crashes:
1. Run with `console=True` in .spec to see errors
2. Look for "FileNotFoundError" or "ModuleNotFoundError"
3. Add missing files to `datas=[]` or `hiddenimports=[]`

---

## 🐛 COMMON ISSUES

### Issue: "FileNotFoundError: affinite2.ico"
**Fix:** Applied fix #1 (resource_path helper)

### Issue: "ModuleNotFoundError: seabreeze.pyseabreeze"
**Fix:** Add to hiddenimports

### Issue: "libusb-1.0.dll not found"
**Fix:** Already handled in .spec lines 12-32

### Issue: Black console window appears
**Fix:** Set `console=False` in .spec (only after testing!)

### Issue: EXE is 500+ MB
**Normal!** Includes:
- Python runtime (~50MB)
- PySide6/Qt (~200MB)
- NumPy/SciPy (~100MB)
- Your code + dependencies

---

## ✅ FINAL CHECKLIST

Before releasing:
- [ ] All resource paths use `get_resource_path()` or `get_affilabs_resource()`
- [ ] Tested exe with `console=True` (no errors)
- [ ] Tested exe with `console=False` (no black window)
- [ ] Icon appears correctly in exe
- [ ] All data files load (configs, images, models)
- [ ] Hardware devices connect properly
- [ ] Calibration files load/save correctly
- [ ] No crashes on startup
- [ ] VERSION displays correctly in UI

---

## 📞 NEED HELP?

If exe crashes, run with console and paste the error message.

Common PyInstaller debugging commands:
```bash
# See what's bundled:
pyi-archive_viewer dist\Affilabs-Core-v2.0.2.exe

# Check dependencies:
pipdeptree -p seabreeze
```
