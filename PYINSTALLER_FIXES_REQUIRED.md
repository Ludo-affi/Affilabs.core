# PyInstaller: Files Requiring Immediate Fix

## 🔴 CRITICAL: 15 Files Need Resource Path Updates

These files use `Path(__file__).parent` which **BREAKS** in PyInstaller!

---

## Files to Fix (In Priority Order):

### 1. `affilabs/affilabs_core_ui.py` (Line 1193)
**Current:**
```python
icon_path = Path(__file__).parent / "ui" / "img" / "affinite2.ico"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
icon_path = get_affilabs_resource("ui/img/affinite2.ico")
```

---

### 2. `affilabs/utils/splash_screen.py` (Lines 145, 229)
**Current:**
```python
icon_path = Path(__file__).parent.parent / "ui" / "img" / "affinite2.ico"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
icon_path = get_affilabs_resource("ui/img/affinite2.ico")
```

---

### 3. `affilabs/core/hardware_manager.py` (Line 609)
**Current:**
```python
config_path = Path(__file__).parent.parent / "config" / "device_config.json"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
config_path = get_affilabs_resource("config/device_config.json")
```

---

### 4. `affilabs/core/oem_model_training.py` (Line 542)
**Current:**
```python
config_path = Path(__file__).parent.parent / "config" / "device_config.json"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
config_path = get_affilabs_resource("config/device_config.json")
```

---

### 5. `affilabs/presenters/navigation_presenter.py` (Line 333)
**Current:**
```python
Path(__file__).parent.parent / "ui" / "img" / "affinite-no-background.png"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
get_affilabs_resource("ui/img/affinite-no-background.png")
```

---

### 6. `affilabs/services/spark/knowledge_base.py` (Line 45)
**Current:**
```python
db_path = Path(__file__).parent.parent.parent / "data" / "spark" / "knowledge_base.json"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
db_path = get_affilabs_resource("data/spark/knowledge_base.json")
```

---

### 7. `affilabs/utils/device_configuration.py` (Lines 180, 190)
**Current:**
```python
Path(__file__).parent.parent / "config" / "devices" / device_serial
config_dir = Path(__file__).parent.parent / "config"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
get_affilabs_resource(f"config/devices/{device_serial}")
config_dir = get_affilabs_resource("config")
```

---

### 8. `affilabs/utils/oem_calibration_tool.py` (Lines 868, 871)
**Current:**
```python
config_path = Path(__file__).parent.parent / "config" / "devices" / serial_number / "device_config.json"
config_path = Path(__file__).parent.parent / "config" / "device_config.json"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
config_path = get_affilabs_resource(f"config/devices/{serial_number}/device_config.json")
config_path = get_affilabs_resource("config/device_config.json")
```

---

### 9. `affilabs/utils/pipelines/__init__.py` (Line 35)
**Current:**
```python
Path(__file__).parent.parent.parent / "settings" / "pipeline_config.json"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_resource_path
get_resource_path("settings/pipeline_config.json")
```

---

### 10-11. `affilabs/tools/plot_s_ref_latest.py` & `print_sp_from_config.py`
**Current:**
```python
CONFIG_DEVICES_DIR = Path(__file__).resolve().parents[1] / "config" / "devices"
```
**Fix:**
```python
from affilabs.utils.resource_path import get_affilabs_resource
CONFIG_DEVICES_DIR = get_affilabs_resource("config/devices")
```

---

### 12. `affilabs/settings/settings.py` (Line 51)
**Note:** This file already handles `sys._MEIPASS` for VERSION, but line 51 might need:
```python
# ONLY if this causes issues:
from affilabs.utils.resource_path import get_resource_path
spec_file = get_resource_path("build/main.spec")
```

---

## 🎯 Quick Fix Script

Run this PowerShell script to add the import to all files at once:

```powershell
# Add import statement to each file (after existing imports)
$files = @(
    "affilabs\affilabs_core_ui.py",
    "affilabs\utils\splash_screen.py",
    "affilabs\core\hardware_manager.py",
    "affilabs\core\oem_model_training.py",
    "affilabs\presenters\navigation_presenter.py",
    "affilabs\services\spark\knowledge_base.py",
    "affilabs\utils\device_configuration.py",
    "affilabs\utils\oem_calibration_tool.py",
    "affilabs\utils\pipelines\__init__.py",
    "affilabs\tools\plot_s_ref_latest.py",
    "affilabs\tools\print_sp_from_config.py"
)

foreach ($file in $files) {
    Write-Host "Check: $file"
    # You'll need to manually update each file's Path(__file__) calls
}
```

---

## ✅ After Fixing All Files

1. **Test in development:**
   ```bash
   python main.py
   ```
   Make sure everything still works!

2. **Build with PyInstaller:**
   ```bash
   pyinstaller Affilabs-Core.spec
   ```

3. **Test the exe:**
   ```bash
   cd dist
   .\Affilabs-Core-v2.0.2.exe
   ```

4. **Check logs for errors:**
   - Look in generated-files/logfile.txt
   - Watch console output (if console=True)

---

## 📊 Progress Tracker

- [ ] affilabs/affilabs_core_ui.py
- [ ] affilabs/utils/splash_screen.py
- [ ] affilabs/core/hardware_manager.py
- [ ] affilabs/core/oem_model_training.py
- [ ] affilabs/presenters/navigation_presenter.py
- [ ] affilabs/services/spark/knowledge_base.py
- [ ] affilabs/utils/device_configuration.py
- [ ] affilabs/utils/oem_calibration_tool.py
- [ ] affilabs/utils/pipelines/__init__.py
- [ ] affilabs/tools/plot_s_ref_latest.py
- [ ] affilabs/tools/print_sp_from_config.py
- [ ] Test in development
- [ ] Build with PyInstaller
- [ ] Test exe

---

## 🐛 If Something Breaks

1. Revert changes
2. Fix one file at a time
3. Test after each fix
4. The resource_path helper is working - the issue will be in how you called it

Example:
```python
# WRONG:
path = get_affilabs_resource("/ui/img/icon.ico")  # Don't start with /

# RIGHT:
path = get_affilabs_resource("ui/img/icon.ico")  # No leading slash
```
