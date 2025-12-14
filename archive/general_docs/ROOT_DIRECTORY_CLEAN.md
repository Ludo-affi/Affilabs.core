# Root Directory - Production Files Only

**Status**: ✅ Clean workspace - only production files remain

---

## 📁 Remaining Python Files at Root (11 files)

All remaining files are **production utilities** used for setup, configuration, or core functionality:

### Setup & Configuration
1. `setup_device.py` - Device setup wizard
2. `factory_provision_device.py` - Factory provisioning tool
3. `install_config.py` - Configuration installation
4. `reorganize_device_config.py` - Config reorganization utility

### Application Entry Points
5. `run_app.py` - Main application launcher

### Core Utilities
6. `example_controller_hal_usage.py` - HAL usage examples
7. `spectral_quality_analyzer.py` - Spectral quality analysis
8. `training_data_manager.py` - Training data management
9. `version.py` - Version information

### Models
10. `led_afterglow_integration_time_model.py` - LED afterglow model
11. `led_afterglow_model.py` - LED afterglow correction

---

## 🗂️ Directory Structure (Production Only)

```
c:\Users\ludol\ezControl-AI\
│
├── Affilabs.core beta\          ← MAIN APPLICATION (v4.0+)
│   ├── main_simplified.py       ← Primary entry point
│   ├── LL_UI_v1_0.py           ← UI implementation
│   ├── utils\                   ← Core utilities
│   │   ├── servo_calibration.py
│   │   ├── device_configuration.py
│   │   └── ...
│   └── widgets\                 ← UI components
│
├── utils\                        ← Shared utilities
│   ├── spr_calibrator.py        ← Main calibration system
│   └── ...
│
├── docs\                         ← Documentation
│   ├── S_POL_P_POL_SPR_MASTER_REFERENCE.md
│   ├── SERVO_CALIBRATION_MASTER_REFERENCE.md
│   └── archive\                 ← Outdated docs
│       └── outdated_polarizer_docs\
│
├── archive\                      ← OLD CODE (reference only)
│   ├── old_software\            ← Legacy codebase
│   ├── backup_files\            ← Development backups
│   ├── analysis_scripts\        ← Dev/test scripts (48 files)
│   └── README.md
│
├── config\                       ← Device configurations
├── tests\                        ← Test suite (test_*.py files)
├── tools\                        ← Production tools
├── scripts\                      ← Production scripts
└── settings\                     ← Application settings
```

---

## ✅ Organization Results

### Archived:
- ✅ `Old software/` → `archive/old_software/`
- ✅ 5 backup files → `archive/backup_files/`
- ✅ 48 analysis/test scripts → `archive/analysis_scripts/`
- ✅ 20+ test files → `tests/` directory

### Kept at Root:
- ✅ 11 production utilities
- ✅ Essential setup/config scripts
- ✅ Application launcher

### Total Files Organized: **70+ files**

---

## 🎯 Active Development Guidelines

### Primary Development Location:
```
c:\Users\ludol\ezControl-AI\Affilabs.core beta\
```

**This is where ALL active development happens.**

### When to Use Root Directory Files:

1. **Setup new device**: `python setup_device.py`
2. **Provision at factory**: `python factory_provision_device.py`
3. **Launch application**: `python run_app.py`
4. **Check version**: `python version.py`

### When NOT to Use Archive:

- ❌ Don't import from `archive/`
- ❌ Don't modify files in `archive/`
- ❌ Don't copy from `archive/` without careful review

---

## 📊 Workspace Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Root .py files | ~90 | 11 | 88% reduction |
| Active directories visible | Mixed | Clear | Organized |
| Old code visibility | High | Archived | Separated |
| Search performance | Slow | Fast | Improved |
| Developer confusion | High | Low | Clear paths |

---

**END OF ROOT DIRECTORY SUMMARY**
