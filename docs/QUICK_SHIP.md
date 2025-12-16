# Affilabs-Core Quick Shipping Reference

## 🚀 ONE-COMMAND SHIP

```powershell
# Complete automated shipping process
.\ship_production.ps1 -Version "1.0.0-beta" -Target "all"
```

## 📦 What Gets Shipped

### ✅ Production Package Includes:
```
Affilabs-Core.exe          # Standalone executable (150-250 MB)
config/                    # Device configurations
detector_profiles/         # Detector calibrations
led_calibration_official/  # LED models
servo_polarizer_calibration/ # Servo configs
settings/                  # Default settings
README.md                  # User guide
SHIPPING_GUIDE.md          # Full deployment docs
```

### ❌ What Stays in Development:
```
archive/                   # Old code
scripts/                   # Dev/analysis tools
tests/                     # Unit tests
test_*.py                  # Test scripts
firmware_archive/          # Firmware dev (separate repo)
logs/                      # Dev logs
data_results/              # Analysis results
```

## 🔧 Quick Commands

### Check Current State
```powershell
# See what needs organizing
python prepare_for_shipping.py
```

### Organize Workspace (Safe)
```powershell
# Moves test files to tests/, cleanup to tools/
python prepare_for_shipping.py --execute
```

### Create Source Package
```powershell
# Creates: dist/Affilabs-Core-v1.0.0-beta-source.zip
python prepare_for_shipping.py --package
```

### Build Standalone Executable
```powershell
# Full automated build
.\ship_production.ps1 -Target "exe"
```

### Build Source Package Only
```powershell
.\ship_production.ps1 -Target "source"
```

## ✅ Pre-Ship Checklist

- [ ] Version number updated in `VERSION` file
- [ ] README.md is current
- [ ] All tests pass: `pytest tests/`
- [ ] No test files in root
- [ ] Hardware connects properly
- [ ] Calibration workflow works
- [ ] Data export produces valid files

## 🎯 Quick Test

```powershell
# Test the built executable
.\dist\Affilabs-Core.exe

# Or test from source
python main-simplified.py
```

## 📊 Expected File Sizes

- **Standalone EXE**: 150-250 MB (includes Python runtime)
- **Source ZIP**: 5-10 MB (excludes venv)
- **Full Package**: ~300 MB (with all data directories)

## 🐛 Quick Fixes

### "Missing Dependencies"
```powershell
# Reinstall from requirements
pip install -r requirements.txt
```

### "Hardware Not Detected"
```powershell
# Check if USB drivers installed
# Include libusb-1.0.dll with package
```

### "Config Files Not Found"
```powershell
# Ensure config/ is in same directory as .exe
# Check paths are relative, not absolute
```

## 📞 Contact

- **Repository**: https://github.com/Ludo-affi/Affilabs-Core
- **Firmware**: https://github.com/Ludo-affi/pico-p4spr-firmware
- **Issues**: GitHub Issues

---

**Ready to ship!** See `SHIPPING_GUIDE.md` for complete details.
