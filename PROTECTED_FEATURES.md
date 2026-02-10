# PROTECTED FEATURES - DO NOT REMOVE WITHOUT EXPLICIT USER PERMISSION

**CRITICAL**: This document lists features that must NOT be removed by automated refactoring, cleanup, or "polishing" operations.

**For AI Assistants**: Before removing ANY feature listed below, you MUST:
1. Ask the user explicitly: "Should I remove [feature name]?"
2. Explain what will be deleted and the impact
3. Wait for explicit confirmation ("yes, remove it")
4. Do NOT assume "cleanup" or "polish" means "remove features"

---

## SIDEBAR TABS

### ⚡ Spark AI Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: ACTIVE - User explicitly requested restoration (2026-02-09)
- **Code Locations**:
  - Tab definition: Lines ~233-240 in tab_definitions list
  - Builder method: `_build_spark_tab()` (~line 741)
  - Lazy-loading: `_on_tab_changed()` (~line 755)
  - Icon rotation: Lines ~310-360 (lightning bolt rotation code)
  - Green styling: Lines ~362-380 (light green background)
- **Remove only if**: User explicitly says "remove Spark tab" or "delete Spark"
- **History**: Removed in v2.0.2 commit 44a0798, restored 2026-02-09 per user request

### Device Status Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Method Builder Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Flow Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Export Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Settings Tab
- **File**: `affilabs/affilabs_sidebar.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## METHOD BUILDER FEATURES

### Overnight Mode Checkbox
- **File**: `affilabs/widgets/method_builder_dialog.py`
- **Status**: ACTIVE - User explicitly requested (moved to Method Queue bottom, 2026-02-09)
- **Code Location**: Below Method Queue table (~line 952)
- **Widget**: `self.overnight_mode_check` in MethodBuilderDialog
- **Functionality**: Updates `settings.OVERNIGHT_MODE` when toggled
- **Remove only if**: User explicitly says "remove overnight mode"

### Build Method Button
- **File**: `affilabs/sidebar_tabs/AL_method_builder.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## FLOW CONTROL FEATURES

### Baseline Button
- **File**: `affilabs/sidebar_tabs/AL_flow_builder.py`
- **Status**: ACTIVE - User explicitly requested (2026-02-07)
- **Widget**: Baseline button with flowrate control
- **Remove only if**: User explicitly says "remove baseline"

### Injection Buttons (Simple/Advanced)
- **File**: `affilabs/sidebar_tabs/AL_flow_builder.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Pump Control Buttons (Home/Stop/Flush)
- **File**: `affilabs/sidebar_tabs/AL_flow_builder.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## EXPORT FEATURES

### Export Format Optimizer
- **File**: `affilabs/sidebar_tabs/AL_export_builder.py`
- **Status**: ACTIVE - User explicitly requested (2026-02-09)
- **Feature**: "Optimize For" dropdown (Prism, Origin, TraceDrawer)
- **Code Location**: ~line 70-95
- **Remove only if**: User explicitly says "remove export optimizer"

---

## CALIBRATION FEATURES

### Startup Calibration Dialog
- **File**: `affilabs/dialogs/startup_calib_dialog.py`
- **Status**: CORE FEATURE
- **Protected Elements**:
  - Activity indicator ("Working..." animation) - Lines ~125, ~382
  - Progress bar
  - Start button
- **Remove only if**: User explicitly requests removal

### Calibration QC Dialog
- **File**: `affilabs/widgets/calibration_qc_dialog.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## HARDWARE FEATURES

### USB4000 Spectrometer Support
- **File**: `affilabs/utils/usb4000_wrapper.py`
- **Status**: CORE FEATURE
- **Critical Settings**:
  - Minimum integration time: 3.5ms (NOT 3ms) - Line 583
  - USB timeout handling
- **Remove only if**: User explicitly requests removal

### Phase Photonics Controller Support
- **File**: `affilabs/utils/phase_photonics_wrapper.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

### Pump Manager
- **File**: `affilabs/managers/pump_manager.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## CONVERGENCE ENGINE

### P-pol Saturation Recovery
- **File**: `affilabs/convergence/policies.py`
- **Status**: CRITICAL BUG FIX (2025-12-14)
- **Code Location**: Lines ~134-135
- **Feature**: Allows integration time reduction for severe P-pol saturation
- **Remove only if**: User explicitly requests removal
- **History**: Fixed critical bug where P-pol couldn't escape saturation

---

## UI FEATURES

### Debug Log Download Button
- **File**: `affilabs/affilabs_core_ui.py`
- **Status**: ACTIVE - User explicitly requested (2026-02-09)
- **Feature**: Automatic log download to current directory
- **Method**: `_handle_debug_log_download()`
- **Remove only if**: User explicitly says "remove debug download"

### Device Status Widget
- **File**: `affilabs/widgets/device_status.py`
- **Status**: CORE FEATURE
- **Remove only if**: User explicitly requests removal

---

## GENERAL RULES FOR AI ASSISTANTS

### When user says "clean up":
- ✅ DO: Fix formatting, remove unused imports, improve comments
- ❌ DON'T: Remove features, delete functions, remove UI elements

### When user says "polish":
- ✅ DO: Improve styling, fix alignment, enhance UX
- ❌ DON'T: Remove features, delete code sections

### When user says "refactor":
- ✅ DO: Improve code structure, extract methods, improve naming
- ❌ DON'T: Remove features without explicit permission

### Before ANY deletion:
1. Ask: "Should I remove [specific feature]?"
2. Explain what it does and impact of removal
3. Wait for explicit "yes" confirmation
4. If in doubt, DON'T remove it

---

## CHANGE LOG

### 2026-02-09
- Created PROTECTED_FEATURES.md
- Added Spark AI Tab (restored after accidental removal)
- Added Overnight Mode (moved to Method Builder)
- Added Export Format Optimizer
- Added Debug Log Download Button
- Added Activity Indicator in Calibration Dialog

### Future Updates
- Add new protected features here as they're identified
- Document any features user explicitly wants preserved
- Note any critical bug fixes that must not be reverted

---

**Last Updated**: 2026-02-09
**Maintained By**: Lucia (Project Owner)
**Purpose**: Prevent accidental removal of user-requested features during automated code changes
