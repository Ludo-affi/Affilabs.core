# Calibration System Refactor Plan

## Problem Analysis

The calibration system has become fragmented across multiple layers:

1. **Backend (led_calibration.py)** - Works perfectly ✅
2. **Data Manager (_calibration_worker)** - Threading wrapper
3. **Calibration Coordinator** - UI orchestration
4. **Progress Dialog** - User interface
5. **QC Dialog** - Results display

**Issues:**
- Too many signal emissions causing slowdowns
- Progress callbacks not covering all steps (P-mode was invisible)
- QC data collection broken (looking for non-existent calibrator object)
- Excessive debug logging flooding I/O
- No clear separation between data flow and UI updates

## Proposed Solution: Simplified Direct Path

### Architecture

```
User clicks "Start Calibration"
         ↓
CalibrationManager (NEW - single class)
    ├── Initialize hardware
    ├── Call perform_full_led_calibration() [BACKEND - no changes]
    ├── Update progress (5-6 key steps only)
    ├── Store results in data_mgr
    └── Show QC dialog
         ↓
Done!
```

### Implementation Plan

1. **Create CalibrationManager class** (replaces coordinator + worker)
   - Single responsibility: Run calibration and report progress
   - Direct hardware access (no proxy through data_mgr)
   - Minimal signal emissions (start, progress, complete, failed)
   - Built-in error handling and logging

2. **Simplify progress callbacks**
   - Only 6 key milestones:
     * "Initializing..." (0%)
     * "Calibrating integration time..." (20%)
     * "Calibrating S-mode LEDs..." (40%)
     * "Measuring reference signals..." (60%)
     * "Calibrating P-mode LEDs..." (80%)
     * "Finalizing..." (95%)
   - Remove all intermediate channel-by-channel updates

3. **Fix QC data collection**
   - Direct access to data_mgr attributes
   - No "calibrator" proxy object
   - Validate data exists before showing dialog

4. **Reduce logging verbosity**
   - INFO: Key milestones only
   - DEBUG: Minimal (only failures)
   - Remove per-scan logging

### File Changes

**New:**
- `core/calibration_manager.py` - Single unified manager

**Modified:**
- `core/calibration_coordinator.py` - Simplify to use new manager
- `core/data_acquisition_manager.py` - Remove _calibration_worker
- `utils/led_calibration.py` - Reduce debug logging
- `main_simplified.py` - Wire up new manager

**Removed:**
- Complex threading logic in data_acquisition_manager
- Redundant progress callbacks

### Benefits

1. **Faster** - No excessive logging, fewer signal emissions
2. **Clearer** - Single path from UI → Backend → Results
3. **Debuggable** - One place to look for calibration issues
4. **Maintainable** - Less code, clearer responsibilities

### Migration Strategy

Phase 1: Create new CalibrationManager (parallel to existing)
Phase 2: Test with new manager
Phase 3: Remove old coordinator/worker code
Phase 4: Cleanup unused imports

---

## Next Steps

Would you like me to:
1. ✅ **Implement the simplified CalibrationManager now**
2. Keep the current system but fix remaining bugs
3. Just document the current system better

The new system will be ~200 lines total vs ~800 lines currently spread across 3 files.
