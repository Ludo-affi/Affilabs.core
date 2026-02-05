# Future Enhancements & Planned Features

**Last Updated:** February 2, 2026

This document tracks **genuine future work** for Affilabs.core. Obsolete TODOs have been removed.

---

## Medium Priority

### 1. Excel Data Visualization in Analysis View
**Status:** Partial Implementation
**Complexity:** Medium
**Impact:** Complete data import/export workflow

**Current State:**
- ✅ Excel loading works (loads cycles and analysis data)
- ✅ Success message shows cycle count
- ❌ Data not visualized in analysis graphs
- ❌ Segments not reconstructed in UI

**Implementation Steps:**
1. Load raw data into analysis view data dict format
2. Reconstruct segments from cycle sheet
3. Populate analysis results if present
4. Restore graph state and selections

**Location:** [affilabs/widgets/analysis.py](affilabs/widgets/analysis.py#L863)

---

### 2. CSV Export from Cycle Table
**Status:** Stub Implementation
**Complexity:** Low
**Impact:** Data portability

**Current State:**
- ✅ Export button exists in UI
- ✅ Click handler defined
- ❌ Only prints "Export CSV clicked"

**Export Format:**
- Cycle Name, Type, Duration, Status
- Timestamp, Integration Time
- Channel data (if available)

**Location:** [affilabs/cycle_table_dialog.py](affilabs/cycle_table_dialog.py#L397)

---

### 3. Clear Queue Confirmation Dialog
**Status:** Needs Implementation
**Complexity:** Low
**Impact:** Prevent accidental data loss

**Current State:**
- ✅ Clear All button exists
- ✅ Signal emitted on click
- ❌ No confirmation dialog (instant clear)

**Implementation:** Add QMessageBox confirmation before `clear_all_requested.emit()`

**Location:** [affilabs/widgets/queue_toolbar.py](affilabs/widgets/queue_toolbar.py#L229)

---

## Low Priority / Future Consideration

### 4. OAuth Authentication for Cloud Upload
**Status:** Placeholder Code
**Complexity:** High
**Impact:** Secure diagnostic upload to OneDrive/SharePoint

**Current State:**
- ✅ Upload infrastructure exists
- ✅ OneDrive API endpoints defined
- ❌ Hardcoded placeholder token: `'Bearer YOUR_OAUTH_TOKEN'`
- ❌ No token management

**Requirements:**
- OAuth provider selection
- Token acquisition flow
- Secure credential storage
- Token refresh logic

**Location:** [affilabs/services/diagnostic_uploader.py](affilabs/services/diagnostic_uploader.py#L268)

---

### 5. System Intelligence History Persistence
**Status:** Empty Stub Methods
**Complexity:** Medium
**Impact:** Long-term system diagnostics and trends

**Current State:**
- ✅ Session reports generated and saved
- ✅ In-memory metrics tracking works
- ❌ `_load_history()` and `_save_history()` are empty stubs
- ❌ No cross-session learning

**Note:** Intelligence Bar UI was removed (Feb 2026), but core intelligence system still generates valuable diagnostic reports.

**Location:** [affilabs/core/system_intelligence.py](affilabs/core/system_intelligence.py#L615-L620)

---

### 6. Pump Auto-Discovery
**Status:** Intentionally Not Implemented
**Complexity:** Medium
**Impact:** Automated pump connection

**Current State:**
- ✅ Manual pump connection works
- ✅ Error message explains feature not implemented
- ❌ No serial port scanning
- ❌ No automatic pump detection

**Reason for Deferral:** Requires hardware abstraction layer refactor. Current manual connection is reliable and sufficient.

**Location:** [affilabs/core/kinetic_manager.py](affilabs/core/kinetic_manager.py#L71-L78)

---

## Confirmed Obsolete / Already Implemented

The following items from old TODOs are **NOT** needed:

### ❌ 3-Stage Linear LED Calibration
**Status:** ALREADY IMPLEMENTED
LED calibration system exists:
- ✅ Model: `affilabs/models/led_calibration_result.py`
- ✅ Data loading: `settings_helpers.py` references calibration files
- ✅ Calibration data: `OpticalSystem_QC/{serial}/spr_calibration/led_calibration_spr_processed_latest.json`

Old TODO comments were stale - feature is complete.

---

### ❌ Pump Control UI Integration
**Status:** FULLY IMPLEMENTED
All pump controls exist and work:
- ✅ UI widgets: `pump1_toggle_btn`, `pump1_rpm_spin`, `pump1_correction_spin`
- ✅ Signal connections in [main.py](main.py#L1790)
- ✅ Start/Stop handlers: `_on_internal_pump1_toggle()`
- ✅ Flow rate controls: `_on_pump1_rpm_changed()`
- ✅ Status updates: Multiple state management functions
- ✅ UI builder: [AL_flow_builder.py](affilabs/sidebar_tabs/AL_flow_builder.py#L1014-L1023)

Old TODO was from early development - all functionality exists.

---

### ❌ Pump/Valve Status UI Updates
**Status:** IMPLEMENTED VIA LOGGING
Peripheral coordinator handles events:
- ✅ Pump state changes logged: `on_pump_state_changed()`
- ✅ Valve switches logged: `on_valve_switched()`
- ✅ Event handlers complete and functional

Old TODOs suggested additional UI updates, but current logging approach is sufficient for production use.

**Location:** [affilabs/coordinators/peripheral_event_coordinator.py](affilabs/coordinators/peripheral_event_coordinator.py#L55-L75)

---

### ❌ Queue Remaining Cycle Tracking
**Status:** ALREADY TRACKED
Queue presenter provides complete tracking:
- ✅ `get_queue_size()` returns remaining cycles
- ✅ UI displays: `f"Queue: Paused | {remaining} cycles remaining"`
- ✅ Real-time updates via `queue_changed` signal

Old TODO suggested additional tracking, but current implementation is complete.

**Location:** [main.py](main.py#L3130)

---

### ❌ Visual Feedback Enhancements (Channel Selection, Flags, Graph Updates)
**Status:** IMPLEMENTED OR INTENTIONALLY MINIMAL
- ✅ Channel selection works: `_selected_channel` tracked, logged
- ✅ Flag system complete: `set_flag()`, `get_flags_for_channel()`, stored in `_flag_data`
- ✅ Graph updates functional

Old TODOs suggested enhanced visual markers, but current approach prioritizes data integrity over visual flourishes.

**Locations:** [cycle_coordinator.py](affilabs/core/cycle_coordinator.py#L160), [cycle_coordinator.py](affilabs/core/cycle_coordinator.py#L225)

---

### ❌ Data Conversion Trigger
**Status:** LIKELY OBSOLETE
Empty comment in coordinator - no clear requirement.

**Location:** [ui_control_event_coordinator.py](affilabs/coordinators/ui_control_event_coordinator.py#L282)

---

### ❌ Form Value Extraction
**Status:** IMPLEMENTED
Cycle creation works via:
- ✅ Queue presenter handles form → cycle object conversion
- ✅ Cycle coordinator manages cycle lifecycle
- ✅ Form values successfully extracted and validated

Old TODO was from early scaffolding - feature is complete.

**Location:** [affilabs_core_ui.py](affilabs/affilabs_core_ui.py#L5572)

---

### ❌ Device Serial Number Detection
**Status:** WORKING AS DESIGNED
`"USB40HXXXXX"` is an **example placeholder** in special cases dict:
- ✅ Real detector serial numbers loaded from hardware
- ✅ Special cases system works correctly
- ✅ Placeholder shows pattern for adding new devices

Not a TODO - just example documentation.

**Location:** [affilabs/utils/device_special_cases.py](affilabs/utils/device_special_cases.py#L42)

---

## Implementation Guidelines

**Before Starting Any Task:**
1. Review this document for dependencies
2. Check related code sections
3. Create feature branch: `feature/[task-name]`
4. Update this document with status changes

**After Completion:**
1. Move item to `COMPLETED_FEATURES.md`
2. Update documentation
3. Add integration tests
4. Merge to main branch

**Priority Criteria:**
- **High:** User-facing features or critical calibration improvements
- **Medium:** Workflow enhancements or significant UX improvements
- **Low:** Nice-to-have features or internal refactoring

---

## Notes

- All TODOs removed from codebase as of February 2, 2026
- Task tracking now centralized in this document
- Regular review recommended quarterly
- Add new features to appropriate priority section
