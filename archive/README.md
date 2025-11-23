# Archive Directory

**Purpose**: Historical reference for old code versions and backup files

**Created**: November 23, 2025

---

## 📁 Directory Structure

### `old_software/`
Contains the complete "Old software" directory with legacy implementations.

**Contents**:
- Legacy main application files
- Old calibration implementations
- Previous UI versions
- Historical build configurations
- Old servo calibration tests

**Status**: Reference only - DO NOT USE for active development

**Note**: This was the complete pre-v4.0 codebase before the major refactoring to `Affilabs.core beta`.

---

### `backup_files/`
Contains backup copies of files during active development.

**Contents**:
- `LL_UI_v1_0_CURRENT_BACKUP.py` - UI backup
- `main_simplified_CURRENT_BACKUP.py` - Main app backup
- `sidebar_BACKUP_current.py` - Sidebar backup
- `usb4000.py.old` - Old USB4000 driver
- `usb4000_oceandirect.py.old` - Old OceanDirect driver

**Status**: Reference only - Active code is in `Affilabs.core beta/`

**Note**: These backups were created during development iterations for rollback safety.

---

### `analysis_scripts/`
Contains diagnostic, testing, and analysis scripts used during development.

**Contents** (~48 files):
- `analyze_*.py` - Performance and data analysis scripts
- `benchmark_*.py` - Performance benchmarking tools
- `check_*.py` - System check and validation scripts
- `compare_*.py` - Comparison and regression testing
- `debug_*.py` - Debugging utilities
- `diagnose_*.py` - Diagnostic tools
- `demonstrate_*.py` - Feature demonstration scripts
- `monitor_*.py` - Real-time monitoring tools
- `optimize_*.py` - Optimization analysis scripts
- `validate_*.py` - Validation testing scripts
- `verify_*.py` - Verification utilities
- `collect_*.py` - Data collection scripts
- `create_*.py` - Setup and creation utilities
- `fix_*.py` - Quick fix scripts
- `*.bat` - Testing batch files

**Status**: Historical reference - Used during development and optimization

**Note**: These scripts were used for profiling, testing, and analyzing the system during development. They are preserved for reference but are not part of the active codebase.

---

## 🎯 Active Development Location

**ALL active development should happen in**:
```
c:\Users\ludol\ezControl-AI\Affilabs.core beta\
```

This is the current, maintained codebase (v4.0+).

---

## ⚠️ Important Notes

1. **Do not modify files in this archive** - they are for reference only
2. **Do not import from archive** - use `Affilabs.core beta` for all active code
3. **Do not restore backup files** without careful review - they may be outdated
4. **Refer to master documentation** in `docs/` for current implementations

---

## 📚 Related Documentation

For understanding what changed between old and new code:
- `docs/SERVO_CALIBRATION_MASTER_REFERENCE.md` - Current servo calibration
- `docs/S_POL_P_POL_SPR_MASTER_REFERENCE.md` - Current S-pol/P-pol understanding
- `SERVO_CALIBRATION_IMPLEMENTATION_COMPLETE.md` - Implementation status
- `docs/archive/outdated_polarizer_docs/` - Outdated polarizer documentation

---

## 🗂️ Archival Policy

Files are archived when:
1. Replaced by newer implementations
2. No longer part of active codebase
3. Kept for historical reference or rollback safety
4. Contains useful patterns but outdated implementation

**Retention**: Keep indefinitely for historical reference unless explicitly removed during major cleanup.

---

**END OF ARCHIVE README**
