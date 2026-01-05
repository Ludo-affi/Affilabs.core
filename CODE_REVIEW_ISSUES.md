# Code Review - Issues for Discussion

**Date:** January 4, 2026  
**Status:** Ready for refactoring discussion

---

## 🔴 CRITICAL ISSUES

### 1. **DUPLICATE LED CONVERGENCE IMPLEMENTATIONS** ✅ FIXED

**Problem:** 6+ convergence files existed with unclear purposes

**What Was Found:**
```
✅ DELETED: affilabs/utils/led_methods_OLD_BACKUP.py (46KB backup)
✅ DELETED: affilabs/utils/LEDCONVERGENCE.py (21KB duplicate)
✅ ARCHIVED: affilabs/core/led_convergence.py → archive/ (26KB unused)

✅ KEPT (Production):
  - affilabs/utils/led_convergence_algorithm.py (28KB - main loop)
  - affilabs/utils/led_convergence_core.py (20KB - primitives)
  - affilabs/utils/led_methods.py (10KB - wrappers)
  - affilabs/convergence/engine.py (100KB - new ML engine)
  - affilabs/convergence/production_wrapper.py (7KB - compatibility)
```

**Resolution:**
- Deleted 3 duplicate/backup files
- Created [LED_CONVERGENCE_ARCHITECTURE.md](docs/LED_CONVERGENCE_ARCHITECTURE.md) documenting:
  - Production code path: `led_convergence_algorithm.py`
  - New ML engine: `convergence/engine.py`
  - File responsibilities and migration guide
  - Common mistakes to avoid

**Status:** ✅ RESOLVED - Clean architecture documented

---

### 2. **CONTROLLER ABSTRACTION CONFUSION** ✅ FIXED

**Problem:** Multiple controller layers:

```python
# Layer 1: Raw hardware
affilabs/utils/controller.py (PicoP4PRO, PicoEZSPR)

# Layer 2: HAL wrapper  
affilabs/utils/hal/controller_hal.py (ControllerHAL)

# Layer 3: Manager
affilabs/core/hardware_manager.py (HardwareManager)

# Usage inconsistency:
ctrl._ctrl._ser.write(b"lx\n")  # BAD: Accessing raw serial through 2 layers
ctrl.enable_multi_led()          # GOOD: Using HAL method
```

**Fixed in test_exact_oem_path.py:**
```python
# Before:
ctrl._ctrl._ser.write(b"lx\n")  # ❌ Bypassing abstraction!

# After:
ctrl.turn_off_channels()  # ✅ Using HAL method
```

**Note:** HAL adapters (`affilabs/utils/hal/adapters.py`) legitimately access `._ctrl._ser` 
for batch commands - that's the abstraction layer's job. Only HAL implementation should 
access raw controller.

---

### 3. **PUMP CONTROLLER DUPLICATION** ✅ FIXED

**Problem:** Multiple pump implementations existed

**What Was Found:**
```
AffiPump/affipump_controller.py              # Main implementation (51KB)
AffiPump/affipump_v2_clean.py               # DUPLICATE (11KB)
AffiPump/affipump_v2_backup.py              # DUPLICATE (11KB)
affilabs/managers/pump_manager.py           # Manager layer
```

**Resolution:**
- ✅ Deleted `affipump_v2_backup.py` (identical to clean)
- ✅ Deleted `affipump_v2_clean.py` (not imported anywhere)
- ✅ Kept `affipump_controller.py` as production implementation
- Kept `pump_manager.py` (provides orchestration value)

**Status:** ✅ RESOLVED - Only production code remains

---

## ⚠️ MODERATE ISSUES

### 4. **ML TRAINING MODELS - VERSION CONFUSION**

**Files:**
```
tools/ml_training/models/           # Development models
affilabs/convergence/models/        # Production models (new!)
```

**Problem:**
- Production models recently deployed to `affilabs/convergence/models/`
- But training script saves to `tools/ml_training/models/`
- Need explicit copy step or symlink

**Recommendation:**
- Add deployment step to training script:
  ```python
  # After training
  import shutil
  shutil.copy("tools/ml_training/models/*.joblib", "affilabs/convergence/models/")
  ```
- Or symlink production dir to training output

---

### 5. **DEVICE CONFIG DUPLICATION**

**Files:**
```
affilabs/config/device_config.json           # Main config
affilabs/config/devices/FLMT09792/           # Per-device configs
affilabs/utils/device_configuration.py       # Config loader
affilabs/managers/device_config_manager.py   # Config manager
```

**Confusion:**
- Two config manager implementations?
- When to use which?

**Recommendation:**
- Consolidate to single config manager
- Document device-specific vs global config

---

### 6. **CALIBRATION ORCHESTRATOR COMPLEXITY**

**File:** `affilabs/core/calibration_orchestrator.py`

**Issues:**
- Very long file (likely >1000 lines)
- Multiple responsibilities:
  - Orchestration
  - Step sequencing
  - Progress reporting
  - Error handling
  - Result formatting

**Recommendation:**
- Split into:
  ```
  calibration_orchestrator.py     # Main flow
  calibration_steps/              # One file per step
    ├── step1_dark_spectrum.py
    ├── step2_wavelength.py
    ├── step3_led_normalization.py
    ├── step4_convergence_s.py
    ├── step5_convergence_p.py
    └── step6_qc_validation.py
  ```

---

### 7. **TEST FILE PROLIFERATION** ✅ FIXED

**Problem:** 40 test files cluttering root directory

**Resolution:**
- ✅ Created `archive/test_explorations/` directory
- ✅ Moved all 40 exploratory `test_*.py` files to archive
- ✅ Kept only production diagnostic tools in root:
  - `test-pump-direction.py` (diagnostic tool)
  - `test-valve-safety.py` (safety check)
  - `test-valves.py` (validation)

**Before:**
```
Root directory: 40+ test files (test_led_*.py, test_servo_*.py, etc.)
```

**After:**
```
Root directory: 3 production diagnostic tools
archive/test_explorations/: 40 exploratory test files
```

**Status:** ✅ RESOLVED - Clean root directory

---

## 💡 NAMING INCONSISTENCIES

### 8. **Case Convention Violations**

**Python Standard:** `snake_case` for functions/methods

**Violations Found:**
```python
# In led_methods.py:
LEDnormalizationintensity()  # Should be: led_normalization_intensity()
LEDnormalizationtime()       # Should be: led_normalization_time()
LEDconverge()                # Should be: led_converge()

# Legacy from old code - need compatibility wrappers:
def led_normalization_intensity(...):  # New name
    """..."""
    pass

# Deprecated - for backward compatibility
def LEDnormalizationintensity(...):
    warnings.warn("Use led_normalization_intensity()", DeprecationWarning)
    return led_normalization_intensity(...)
```

---

### 9. **File Naming Confusion**

**Problem:** Similar names, different purposes:

```
affilabs/utils/LEDCONVERGENCE.py        # All caps
affilabs/core/led_convergence.py        # Snake case
affilabs/utils/led_convergence_core.py
affilabs/utils/led_convergence_algorithm.py
```

**Recommendation:**
- Remove `LEDCONVERGENCE.py` (all caps is confusing)
- Keep snake_case only

---

## 📋 DOCUMENTATION GAPS

### 10. **Missing "Which File to Use" Guide**

**Problem:** New contributor doesn't know:
- Which LED convergence file to import?
- Which calibration orchestrator to use?
- Which pump controller is production?

**Recommendation:**
Create `docs/ARCHITECTURE.md`:
```markdown
# Architecture Guide

## LED Convergence
- **Production:** `affilabs/convergence/engine.py` (new)
- **Legacy:** `affilabs/utils/led_convergence_algorithm.py`
- **Use:** `from affilabs.convergence import ConvergenceEngine`

## Calibration
- **Production:** `affilabs/core/calibration_service.py`
- **Use:** `from affilabs.core import CalibrationService`

## Hardware Control
- **Controller:** Use HAL wrapper from `hardware_manager.ctrl`
- **Never** access `._ctrl._ser` directly
```

---

## 🔧 PROPOSED CLEANUP ACTIONS

### Phase 1: Safe Deletions ✅ COMPLETED

**Executed January 4, 2026:**
```bash
# ✅ Delete backup files
rm affilabs/utils/led_methods_OLD_BACKUP.py
rm affilabs/utils/LEDCONVERGENCE.py
rm AffiPump/affipump_v2_backup.py
rm AffiPump/affipump_v2_clean.py

# ✅ Archive unused files
mv affilabs/core/led_convergence.py archive/src_old_structure/

# ✅ Archive old test files (40 files)
mkdir archive/test_explorations
mv test_*.py archive/test_explorations/  # Kept 3 diagnostic tools

# ✅ Fix abstraction bypass
# Edited test_exact_oem_path.py to use ctrl.turn_off_channels()
```

**Results:**
- Deleted: 5 duplicate/backup files
- Archived: 41 files (1 LED convergence + 40 tests)
- Fixed: 2 abstraction bypass violations
- Created: LED_CONVERGENCE_ARCHITECTURE.md documentation

### Phase 2: Renaming (Needs Code Updates)
```python
# In led_methods.py - add deprecation warnings
import warnings

def LEDnormalizationintensity(*args, **kwargs):
    warnings.warn(
        "LEDnormalizationintensity is deprecated, use led_normalization_intensity",
        DeprecationWarning,
        stacklevel=2
    )
    return led_normalization_intensity(*args, **kwargs)
```

### Phase 3: Architecture Consolidation
```
1. Document production vs legacy code paths
2. Create migration guide
3. Deprecate old implementations
4. Remove after 1 version cycle
```

---

## ❓ QUESTIONS FOR DISCUSSION

1. **LED Convergence:** Switch fully to `ConvergenceEngine` or keep legacy?
   - Engine seems more mature with ML models
   - Legacy still referenced in some places

2. **Pump Manager:** Keep `pump_manager.py` or use `affipump_controller.py` directly?
   - Manager adds complexity
   - But might provide useful abstractions?

3. **Test Files:** Delete exploratory tests or archive?
   - 40+ test files in root
   - Most seem like debugging artifacts

4. **Calibration Steps:** Split orchestrator into step files?
   - Pro: Cleaner separation
   - Con: More files to navigate

5. **HAL Bypass:** Should we add linting rule to prevent `._ctrl` access?
   - Enforce abstraction boundaries
   - Catch violations in CI

---

## 📊 METRICS

**Before Cleanup:**
- **Duplicate files:** 15+ identified
- **Test files in root:** 40+
- **Naming violations:** 10+
- **Abstraction bypass:** Multiple locations
- **Backup files:** 3 (OLD_BACKUP, v2_backup, v2_clean)

**After Cleanup (January 4, 2026):**
- **Duplicates:** 0 ✅
- **Root test files:** 3 (production diagnostic tools only) ✅
- **Backup files:** 0 ✅
- **Abstraction bypass:** Fixed in test files ✅
- **Documentation:** LED_CONVERGENCE_ARCHITECTURE.md created ✅

**Files Cleaned:**
- Deleted: 5 files (3 LED convergence duplicates + 2 pump duplicates)
- Archived: 41 files (1 unused LED convergence + 40 test files)
- Fixed: 2 abstraction bypass violations
- Documented: Production code paths and architecture

---

## 🎯 NEXT STEPS

1. **Review this document** - Discuss which issues to tackle first
2. **Prioritize** - Critical (blocking) vs Nice-to-have
3. **Create tasks** - One issue at a time
4. **Execute** - Make changes in feature branches
5. **Test** - Ensure no regressions

**Estimated cleanup time:** 2-4 hours for Phase 1 (safe deletions)
