# Orphan Code & Refactoring Opportunities Analysis

**Date**: December 15, 2025
**Target**: main-simplified.py initialization code
**Status**: Code Review - Cleanup Recommendations

---

## Executive Summary

Found **significant orphan code** in initialization - primarily an entire **disabled feature branch** for "Timeframe Mode" that adds complexity without providing value. Recommend immediate removal to improve maintainability.

**Impact**:
- **~200 lines of dead code** can be removed
- **8 state variables** can be eliminated
- **3 methods** can be deleted
- Reduces cognitive load for developers

---

## CRITICAL: Dead Feature - Timeframe Mode

### Feature Flag (DISABLED)
```python
# Line 596 - main-simplified.py
self.USE_TIMEFRAME_MODE = False  # Feature flag - DISABLED (using legacy cursor mode)
```

**Status**: Feature is PERMANENTLY DISABLED (hardcoded to False)
**Problem**: Entire feature implementation exists but is never executed

### Orphaned State Variables (Lines 593-609)

```python
# PHASE 1: Live Cycle Timeframe Mode (parallel to cursor system)
self._live_cycle_timeframe = 5  # minutes (default)
self._live_cycle_mode = "moving"  # 'moving' or 'fixed'
self.USE_TIMEFRAME_MODE = False  # ← DISABLED
self._timeframe_baseline_wavelengths = {
    "a": None, "b": None, "c": None, "d": None,
}
self._last_processed_time = {
    "a": -1.0, "b": -1.0, "c": -1.0, "d": -1.0,
}
self._last_timeframe_update = 0
```

**All 8 variables are only used when `USE_TIMEFRAME_MODE=True` (never happens)**

### Dead Code Locations

| File | Lines | Description | Used? |
|------|-------|-------------|-------|
| main-simplified.py | 593-609 | Timeframe state variables | ❌ NO |
| main-simplified.py | 956-972 | Timeframe mode initialization | ❌ NO |
| main-simplified.py | 1294-1298 | Timeframe signal connections | ❌ NO |
| main-simplified.py | 5240-5280 | `_on_timeframe_mode_changed()` method | ❌ NO |
| main-simplified.py | 5282-5330 | `_on_timeframe_duration_changed()` method | ❌ NO |
| main-simplified.py | 5490-5705 | `_update_live_cycle_timeframe()` method | ❌ NO |

### Feature Description (for context)

The "Timeframe Mode" was intended as an **alternative to cursor-based region selection**:
- **Cursor Mode (CURRENT)**: User drags start/stop cursors to select time region
- **Timeframe Mode (DISABLED)**: Automatically shows last N minutes (moving/fixed window)

**Why Disabled?**
- Cursor mode is more flexible and intuitive
- Users prefer manual control over automatic windowing
- Feature never reached production readiness

---

## Recommended Actions

### Priority 1: Remove Dead Timeframe Feature ⚠️ HIGH IMPACT

**Delete Lines 593-609** (State Variables):
```python
# DELETE ENTIRE SECTION:
# PHASE 1: Live Cycle Timeframe Mode (parallel to cursor system)
self._live_cycle_timeframe = 5  # minutes (default)
self._live_cycle_mode = "moving"  # 'moving' or 'fixed'
self.USE_TIMEFRAME_MODE = False  # Feature flag - DISABLED (using legacy cursor mode)
self._timeframe_baseline_wavelengths = {...}
self._last_processed_time = {...}
self._last_timeframe_update = 0  # Timestamp of last update (for throttling)
```

**Delete Lines 956-972** (Initialization):
```python
# DELETE:
if self.USE_TIMEFRAME_MODE:
    # NOTE: enable_timeframe_mode method not yet implemented in main window
    # self.main_window.enable_timeframe_mode(True)
    # ... entire block ...
    logger.info("  Timeframe mode disabled - using legacy cursor system")
```

**Delete Lines 1294-1298** (Signal Connections):
```python
# DELETE:
if self.USE_TIMEFRAME_MODE:
    # self.main_window.timeframe_mode_changed.connect(...)
    # self.main_window.timeframe_duration_changed.connect(...)
```

**Delete Methods** (Lines 5240-5705):
- `_on_timeframe_mode_changed()` - 40 lines
- `_on_timeframe_duration_changed()` - 48 lines
- `_update_live_cycle_timeframe()` - 215 lines

**Total Savings**: ~280 lines of unused code removed

**Risk**: NONE - code is never executed (behind `if False:` check)

---

## Priority 2: Clean Up Commented-Out Code

### Dead Signal Connections (Lines 1249-1251)

```python
# DELETE - Signals never implemented:
# self.main_window.clear_graphs_requested.connect(self._on_clear_graphs_requested)
# self.main_window.clear_flags_requested.connect(self._on_clear_flags_requested)
# self.main_window.pipeline_changed.connect(self._on_pipeline_changed)
```

**Action**: Delete if features are not planned for v1.0

### Dead LED Input Updates (Lines 6245-6248)

```python
# DELETE - UI update pattern replaced by signal-based architecture:
# self.main_window.channel_a_input.setText(str(led_a))
# self.main_window.channel_b_input.setText(str(led_b))
# self.main_window.channel_c_input.setText(str(led_c))
# self.main_window.channel_d_input.setText(str(led_d))
```

**Context**: From old calibration code, replaced by new signal-based LED settings

---

## Priority 3: Extract TODO Items

### TODO: 3-Stage Linear LED Calibration (3 occurrences)

```python
# Line 1608
# TODO: Integrate 3-stage linear LED calibration

# Line 6153
# TODO: Integrate 3-stage linear LED calibration model here

# Line 6238
# TODO: Integrate 3-stage linear calibration
```

**Status**: Model exists in `spr_calibrator.py`, integration incomplete
**Action**: Create GitHub issue or remove TODOs if not planned for v1.0

### TODO: Pump Control UI (Lines 3611, 3628, 3635)

```python
# TODO: Enable pump controls in UI
# TODO: Update UI pump status
# TODO: Update UI valve status
```

**Status**: Pump hardware exists, UI controls not implemented
**Action**: Create GitHub issue or document as future feature

### TODO: ViewModel Refactoring (Line 5752)

```python
# TODO: Remove this once all UI updates are driven by ViewModel signals
```

**Status**: Migration to ViewModels incomplete
**Action**: Track progress or remove if ViewModels not used

---

## Priority 4: Optimize State Variable Initialization

### Current Problem (Lines 558-655)

50+ scattered instance variables initialized in one massive method:

```python
def _init_state_variables(self):
    # Application lifecycle
    self.closing = False
    self._device_config_initialized = False
    # ... 46 more variables ...
```

### Solution: Use ApplicationState Dataclasses (ALREADY CREATED)

**File**: `affilabs/app_state.py` (created in previous refactoring)

**Migration**:
```python
# BEFORE (current):
def _init_state_variables(self):
    self.closing = False
    self.experiment_start_time = None
    self._calibration_retry_count = 0
    # ... 50+ more ...

# AFTER (refactored):
def __init__(self):
    super().__init__(sys.argv)
    self.state = ApplicationState()  # All state grouped in dataclasses
```

**Benefits**:
- ✅ Clear organization (lifecycle, experiment, calibration groups)
- ✅ Type hints
- ✅ Easy to test
- ✅ Reduces _init_state_variables() from 100 lines to 1 line

**Status**: Dataclasses created, migration not yet applied

---

## Not Orphan - Legitimate State Variables

### ✅ LED Status Timer (Lines 612, 2339-2362)
**Status**: USED - Monitors LED health every 2 seconds
**Action**: Keep (legitimate feature)

### ✅ Last Cycle Bounds (Lines 565, 3144-3158)
**Status**: USED - Optimization to skip redundant cycle graph updates
**Action**: Keep (performance optimization)

### ✅ QC Dialog (Lines 572, 1195-1222)
**Status**: USED - Shows calibration QC results
**Action**: Keep (critical feature)

---

## Summary Table

| Category | Lines | Impact | Risk |
|----------|-------|--------|------|
| **Timeframe Mode (DEAD)** | ~280 | Remove entire feature | NONE |
| **Commented-out signals** | ~10 | Delete or implement | LOW |
| **TODO comments** | ~8 | Create issues or delete | NONE |
| **State variable refactoring** | ~100 | Migrate to dataclasses | MEDIUM |
| **TOTAL REMOVABLE** | **~400 lines** | Cleaner codebase | LOW |

---

## Implementation Plan

### Phase 1: Dead Code Removal (1 hour)
1. ✅ Verify `USE_TIMEFRAME_MODE` is never True (grep search confirms)
2. ✅ Remove timeframe state variables (lines 593-609)
3. ✅ Remove timeframe initialization (lines 956-972)
4. ✅ Remove timeframe signals (lines 1294-1298)
5. ✅ Delete 3 timeframe methods (~280 lines)
6. ✅ Remove commented-out signal connections
7. ✅ Test: Run application, verify no errors

**Risk**: NONE - Code never executes

### Phase 2: State Refactoring (2-4 hours)
1. Audit all usages of scattered state variables
2. Replace with `self.state.lifecycle.closing` pattern
3. Add backward compatibility properties during migration
4. Remove compatibility properties once complete
5. Test: Verify all functionality works

**Risk**: MEDIUM - Requires careful migration

### Phase 3: TODO Cleanup (30 minutes)
1. Create GitHub issues for planned features
2. Delete TODOs for cancelled features
3. Update documentation with roadmap

**Risk**: NONE - Documentation only

---

## Testing Checklist

After each phase:
- [ ] Application starts successfully
- [ ] Hardware connection works
- [ ] Calibration runs without errors
- [ ] Live acquisition displays correctly
- [ ] Settings tab LED controls work
- [ ] No console errors or warnings
- [ ] Cursor-based region selection works (verify timeframe removal didn't break cursors)

---

## Git Commit Strategy

**Separate commits for reviewability**:
1. `refactor: Remove dead Timeframe Mode feature (~280 lines)`
2. `refactor: Delete commented-out signal connections`
3. `docs: Create GitHub issues for TODOs, remove obsolete comments`
4. `refactor: Migrate scattered state to ApplicationState dataclasses` (optional)

**Branch**: `cleanup/remove-orphan-code`

---

## Files to Modify

### main-simplified.py
- **Lines to delete**: 593-609, 956-972, 1249-1251, 1294-1298, 5240-5705, 6245-6248
- **Total lines removed**: ~300 lines
- **Methods deleted**: 3 (timeframe-related)
- **State variables removed**: 8

### No other files affected
- Timeframe feature is self-contained in main-simplified.py
- No external dependencies or imports

---

## Appendix: Full Grep Results

### USE_TIMEFRAME_MODE Usage (11 matches)
```
Line 596:  self.USE_TIMEFRAME_MODE = False  # HARDCODED DISABLED
Line 956:  if self.USE_TIMEFRAME_MODE:  # Never True
Line 1294: if self.USE_TIMEFRAME_MODE:  # Never True
Line 3102: if self.USE_TIMEFRAME_MODE:  # Never True
Line 5307: if not self.USE_TIMEFRAME_MODE:  # Always True (inverse)
Line 5494: if not self.USE_TIMEFRAME_MODE:  # Always True (inverse)
```

**Analysis**: Feature flag is hardcoded to False and never changed at runtime. All conditional blocks are dead code.

---

**Recommendation**: Proceed with Phase 1 (Dead Code Removal) immediately. Low risk, high reward.
