# Affilabs-Core Production Shipping Guide

**Date**: December 14, 2025
**Version**: 1.0.0-beta
**Status**: Beta Release

---

## 📦 Quick Ship Checklist

### ✅ Pre-Ship Verification
- [ ] All tests pass in `tests/` directory
- [ ] Python 3.12+ verified (run `python --version`)
- [ ] Virtual environment `.venv312` is clean
- [ ] No test files in root directory
- [ ] Build artifacts cleaned
- [ ] Documentation is current

### ✅ Production Files (DO SHIP)
```
affilabs/                  # Core application package
├── core/                  # Business logic (hardware, acquisition, processing)
├── dialogs/              # UI dialogs
├── sidebar_tabs/         # Sidebar components
├── utils/                # Utilities and algorithms
└── widgets/              # Main UI widgets

affipump/                  # Pump control integration
config/                    # Device configurations and profiles
detector_profiles/         # Detector calibration profiles
led_calibration_official/  # LED calibration system (3-stage models)
servo_polarizer_calibration/ # Servo calibration system
settings/                  # Application settings
ui/                        # Qt UI files (.ui) and resources
widgets/                   # Main window widgets
utils/                     # Shared utilities

main-simplified.py         # PRIMARY APPLICATION ENTRY POINT
run_app.py                 # Development launcher with environment verification
version.py                 # Version management
VERSION                    # Version file (3.2.9)

pyproject.toml            # Project configuration and dependencies
pdm.toml                  # PDM configuration
pyrightconfig.json        # Type checking configuration
README.md                 # User documentation
ACQUISITION_METHODS.md    # Acquisition method documentation
```

### ❌ Development Files (DO NOT SHIP)
```
archive/                   # Archived old code and documentation
archive_root_files/        # Archived root files
build_artifacts/           # Build outputs (generated)
calibration_checkpoints/   # Development calibration data
calibration_data/          # Old calibration data
calibration_results/       # Test calibration results
data/                      # Test data cycles
data_results/              # Analysis results
docs/                      # Internal documentation
firmware_archive/          # Firmware development (use separate repo)
generated-files/           # Generated outputs
logs/                      # Application logs (generated at runtime)
OpticalSystem_QC/          # QC analysis tools (development)
scripts/                   # Development/analysis scripts
tests/                     # Unit/integration tests
tools/                     # Development tools

test_*.py                  # Test scripts in root
cleanup_*.py               # Cleanup scripts
check_*.py                 # Check scripts
*.png                      # Test plots and screenshots
*.7z                       # Compressed libraries (include libusb if needed)

.git/                      # Git repository
.vscode/                   # VS Code settings
.mypy_cache/               # Type checker cache
.ruff_cache/               # Linter cache
.pylintrc                  # Linter config
__pycache__/               # Python cache (auto-generated)
```

---

## 🚀 Shipping Methods

### Method 1: PyInstaller (Recommended for Windows)

**Create standalone executable:**
```powershell
# 1. Activate environment
.\.venv312\Scripts\Activate.ps1

# 2. Install PyInstaller (if not already)
pip install pyinstaller

# 3. Build executable
pyinstaller --name="Affilabs-Core" `
            --onefile `
            --windowed `
            --add-data "ui;ui" `
            --add-data "config;config" `
            --add-data "detector_profiles;detector_profiles" `
            --add-data "settings;settings" `
            --hidden-import=PySide6 `
            --hidden-import=pyqtgraph `
            --hidden-import=oceandirect `
            --icon=ui/img/affinite2.ico `
            main-simplified.py

# Output will be in: dist/Affilabs-Core.exe
```

### Method 2: Source Distribution (For Python Users)

**Create clean source package:**
```powershell
# Run the shipping preparation script
python prepare_for_shipping.py

# This creates: Affilabs-Core-v1.0.0-beta-source.zip
```

### Method 3: PDM Build (Python Package)

**Build Python wheel:**
```powershell
# 1. Activate environment
.\.venv312\Scripts\Activate.ps1

# 2. Build with PDM
pdm build

# Output: dist/affilabs_spr_control-0.1.0-py3-none-any.whl
```

---

## 📋 Production Deployment Structure

### Minimal Deployment (Standalone EXE)
```
Affilabs-Core-v3.2.9/
├── Affilabs-Core.exe          # Main executable
├── config/                    # Device configurations (REQUIRED)
│   ├── device_config.json
│   └── devices/
├── detector_profiles/         # Detector calibrations (REQUIRED)
├── led_calibration_official/  # LED models (REQUIRED)
├── servo_polarizer_calibration/ # Servo configs (REQUIRED)
├── settings/                  # App settings (auto-generated)
├── logs/                      # Application logs (auto-generated)
├── README.md                  # User guide
└── LICENSE                    # License file
```

### Full Source Deployment (For Developers)
```
Affilabs-Core-v1.0.0-beta-source/
├── affilabs/                  # Application source
├── affipump/
├── config/
├── detector_profiles/
├── led_calibration_official/
├── servo_polarizer_calibration/
├── settings/
├── ui/
├── widgets/
├── utils/
├── main-simplified.py         # Entry point
├── run_app.py                 # Development launcher
├── pyproject.toml             # Dependencies
├── requirements.txt           # Pip dependencies (generated)
├── README.md
├── ACQUISITION_METHODS.md
└── docs/                      # User documentation only
    ├── QUICK_START.md
    └── USER_GUIDE.md
```

---

## 🔧 Pre-Shipping Cleanup

### Automated Cleanup (Safe)
```powershell
# Clean all test files, logs, and caches
python cleanup_for_shipping.py
```

### Manual Cleanup (If needed)
```powershell
# Remove test files from root
Remove-Item test_*.py
Remove-Item cleanup_*.py
Remove-Item check_*.py

# Clean caches
Remove-Item -Recurse -Force __pycache__
Remove-Item -Recurse -Force .mypy_cache
Remove-Item -Recurse -Force .ruff_cache

# Clean generated files
Remove-Item -Recurse -Force build_artifacts/
Remove-Item -Recurse -Force logs/*.txt
Remove-Item -Recurse -Force calibration_results/

# Clean development data
Remove-Item -Recurse -Force data/cycles/
Remove-Item -Recurse -Force data_results/
```

---

## ✅ Verification Tests

### Before Shipping, Verify:

**1. Application Starts Clean:**
```powershell
python main-simplified.py
# Should start without errors
# Should auto-detect hardware
# Should load last calibration
```

**2. Core Functions Work:**
- [ ] Hardware detection (spectrometer + controller)
- [ ] Live acquisition (all 4 channels)
- [ ] Calibration workflow (8 steps)
- [ ] Data export (CSV, JSON)
- [ ] Settings persistence

**3. No Development Artifacts:**
```powershell
# Should return nothing:
Get-ChildItem -Recurse | Where-Object { $_.Name -match 'test_.*\.py' -and $_.DirectoryName -notmatch 'tests' }
```

**4. Dependencies Check:**
```powershell
# Verify all imports work:
python -c "import affilabs; import affipump; import oceandirect; print('✅ All imports OK')"
```

---

## 📝 Requirements Generation

### Create requirements.txt for pip users:
```powershell
# Activate environment
.\.venv312\Scripts\Activate.ps1

# Export requirements
pip freeze > requirements.txt

# Or use PDM
pdm export -o requirements.txt --without-hashes
```

---

## 🔒 Security Considerations

### Before Shipping:
- [ ] Remove any API keys or credentials from config files
- [ ] Check for hardcoded paths (should use relative paths)
- [ ] Verify no sensitive device serial numbers in code
- [ ] Remove development database/log files
- [ ] Clear any cached authentication tokens

### Config Sanitization:
```python
# Run security check:
python -c "from utils.security import check_security; check_security()"
```

---

## 📊 Build Verification

### Post-Build Checklist:
- [ ] Executable runs without console window (windowed mode)
- [ ] Icon displays correctly in Windows Explorer
- [ ] File associations work (if applicable)
- [ ] All DLLs bundled correctly (check with Dependency Walker)
- [ ] Configuration files load from correct relative paths
- [ ] First-run wizard works for new installations

### Size Expectations:
- **Standalone EXE**: ~150-250 MB (includes Python runtime)
- **Source ZIP**: ~5-10 MB (excludes virtual environment)
- **Wheel Package**: ~2-5 MB (pure Python)

---

## 🐛 Common Shipping Issues

### Issue 1: Missing Dependencies
**Symptom**: ImportError on fresh installation
**Fix**: Ensure all dependencies in `pyproject.toml` are correct
```powershell
pdm install --prod  # Test production install
```

### Issue 2: Hardware Not Detected
**Symptom**: USB4000 or controller not found
**Fix**: Bundle libusb drivers or include installer
```powershell
# Include in package:
libusb/
├── libusb-1.0.dll
└── INSTALL_DRIVERS.txt
```

### Issue 3: Config Files Not Found
**Symptom**: FileNotFoundError for config files
**Fix**: Use Path relative to executable
```python
# In code:
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = Path(sys.executable).parent
else:
    # Running as script
    base_path = Path(__file__).parent
```

### Issue 4: Qt Plugins Missing
**Symptom**: "Could not find Qt platform plugin"
**Fix**: Add Qt plugins to PyInstaller spec
```python
# In .spec file:
a = Analysis(
    ...
    datas=[
        ('venv/Lib/site-packages/PySide6/plugins', 'PySide6/plugins'),
    ],
)
```

---

## 📞 Support Information

### For Customers:
- Documentation: See `README.md` and `docs/USER_GUIDE.md`
- Hardware: USB4000 spectrometer + PicoP4SPR controller required
- OS: Windows 10/11 (64-bit)
- Python: 3.12+ (if running from source)

### For Developers:
- Repository: https://github.com/Ludo-affi/Affilabs-Core
- Firmware: https://github.com/Ludo-affi/pico-p4spr-firmware
- Issues: GitHub Issues tracker
- Contact: development@affinite.com

---

## 🎯 Final Shipping Command

```powershell
# ONE-COMMAND SHIP (automated)
.\ship_production.ps1 -Version "1.0.0-beta" -Target "all"

# This will:
# 1. Clean workspace
# 2. Run tests
# 3. Build executable
# 4. Create source package
# 5. Generate checksums
# 6. Create release notes
# 7. Package everything into dist/Affilabs-Core-v1.0.0-beta/
```

---

## ✨ Success Criteria

**Ready to ship when:**
- ✅ All automated tests pass
- ✅ Manual smoke tests complete
- ✅ No test files in production package
- ✅ Documentation is current
- ✅ Version numbers match everywhere
- ✅ Build runs on clean Windows VM
- ✅ Hardware auto-detection works
- ✅ Calibration workflow completes
- ✅ Data export produces valid files

**Ship with confidence!** 🚀
