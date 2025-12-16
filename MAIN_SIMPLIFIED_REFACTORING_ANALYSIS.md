# main-simplified.py Refactoring Analysis

## Executive Summary

**Current State:** 6,450 lines in a single file
**Architecture Alignment:** Good structure but poor modularity
**Refactoring Priority:** HIGH - Extract signal handlers and coordinators

---

## Current Structure Analysis

### Size Breakdown
- **Total Lines:** 6,450
- **Application Class:** ~5,900 lines (lines 336-6237)
- **Setup Code:** ~335 lines (imports, filters, environment)
- **Main Function:** ~210 lines (splash screen, app launch)

### Method Distribution
```
Signal Handlers (_on_*):     66 methods  (~2,800 lines, 43%)
Initialization (_init_*):      6 methods  (~500 lines, 8%)
UI Updates (_update_*):        9 methods  (~600 lines, 9%)
Signal Wiring (_connect_*):    7 methods  (~400 lines, 6%)
Processing/Business Logic:    38 methods  (~1,600 lines, 25%)
Other (utilities, cleanup):   ~500 lines (8%)
```

---

## Architecture Assessment

### ✅ Strengths

1. **9-Phase Initialization** - Well-structured, clear phase boundaries
2. **Signal-Based Communication** - Proper Qt patterns
3. **Clear Layer Separation** - Good documentation of 4-layer architecture
4. **Thread Safety** - Explicit queue-based processing thread
5. **Comprehensive Documentation** - Good inline comments

### ❌ Architecture Violations

1. **God Object Anti-Pattern** - Single class with 130+ methods
2. **Mixed Concerns** - Business logic + UI coordination + event handling in one place
3. **Difficult Testing** - Cannot test components independently
4. **Poor Reusability** - Cannot reuse signal handlers or coordinators elsewhere
5. **Cognitive Overload** - Too much for one developer to hold in memory

---

## Refactoring Strategy

### Phase 1: Extract Signal Handler Coordinators (HIGH PRIORITY)

**Target:** Reduce Application class by ~2,800 lines (43%)

#### 1A. Hardware Event Coordinator (~800 lines)
```python
# affilabs/coordinators/hardware_event_coordinator.py
class HardwareEventCoordinator:
    """Handles hardware connection, disconnection, and status events."""

    def __init__(self, app, hardware_mgr, main_window):
        self._app = app
        self._hardware_mgr = hardware_mgr
        self._main_window = main_window

    # Move these methods:
    - _on_hardware_connected()
    - _on_hardware_disconnected()
    - _on_connection_progress()
    - _on_hardware_error()
    - _on_scan_requested()
    - _start_led_status_monitoring()
    - _stop_led_status_monitoring()
    - _update_led_status_display()
```

#### 1B. Acquisition Event Coordinator (~600 lines)
```python
# affilabs/coordinators/acquisition_event_coordinator.py
class AcquisitionEventCoordinator:
    """Handles acquisition lifecycle events."""

    # Move these methods:
    - _on_acquisition_started()
    - _on_acquisition_stopped()
    - _on_acquisition_pause_requested()
    - _on_acquisition_error()
    - _on_spectrum_acquired()
    - _on_start_button_clicked()
    - _on_detector_wait_changed()
```

#### 1C. Recording Event Coordinator (~400 lines)
```python
# affilabs/coordinators/recording_event_coordinator.py
class RecordingEventCoordinator:
    """Handles recording lifecycle and progress events."""

    # Move these methods:
    - _on_recording_started() [2 versions - deduplicate]
    - _on_recording_stopped()
    - _on_recording_progress()
    - _on_recording_complete()
    - _on_recording_error() [2 versions - deduplicate]
    - _on_event_logged()
    - _on_record_baseline_clicked()
```

#### 1D. UI Control Event Coordinator (~500 lines)
```python
# affilabs/coordinators/ui_control_event_coordinator.py
class UIControlEventCoordinator:
    """Handles UI control interactions (buttons, toggles, sliders)."""

    # Move these methods:
    - _on_filter_toggled()
    - _on_filter_strength_changed()
    - _on_axis_selected()
    - _on_unit_changed()
    - _on_colorblind_toggled()
    - _on_grid_toggled()
    - _on_autoscale_toggled()
    - _on_manual_scale_toggled()
    - _on_manual_range_changed()
    - _on_reference_changed()
    - _on_apply_settings()
    - _on_page_changed()
    - _on_tab_changing()
```

#### 1E. Graph Event Coordinator (~500 lines)
```python
# affilabs/coordinators/graph_event_coordinator.py
class GraphEventCoordinator:
    """Handles graph interactions and updates."""

    # Move these methods:
    - _on_graph_clicked()
    - _select_nearest_channel()
    - _add_flag()
    - _update_cycle_of_interest_graph()
    - _update_cycle_data_table()
    - _update_delta_display()
    - _update_stop_cursor_position()
```

#### 1F. Peripheral Event Coordinator (~300 lines)
```python
# affilabs/coordinators/peripheral_event_coordinator.py
class PeripheralEventCoordinator:
    """Handles pump and polarizer events."""

    # Move these methods:
    - _on_pump_initialized()
    - _on_pump_error()
    - _on_pump_state_changed()
    - _on_valve_switched()
    - _on_polarizer_toggle_clicked()
    - _on_polarizer_toggle()
    - _on_polarizer_calibration()
    - _on_oem_led_calibration()
```

**Total Extraction:** ~3,100 lines (48% reduction)

---

### Phase 2: Extract Processing Logic (~1,000 lines)

#### 2A. Spectrum Processing Service
```python
# affilabs/services/spectrum_processing_service.py
class SpectrumProcessingService:
    """Separates spectrum processing from Application class."""

    # Move these methods:
    - _process_spectrum_data()
    - _handle_intensity_monitoring()
    - _queue_transmission_update()
    - _apply_smoothing()
    - _apply_online_smoothing()
    - _init_kalman_filters()
```

#### 2B. UI Update Service
```python
# affilabs/services/ui_update_service.py
class UIUpdateService:
    """Manages UI update throttling and batching."""

    # Move these methods:
    - _process_pending_ui_updates()
    - _should_update_transmission()
    - _update_sensor_iq_display()
```

---

### Phase 3: Extract UI Binding Logic (~400 lines)

#### 3A. Signal Connection Manager
```python
# affilabs/coordinators/signal_connection_manager.py
class SignalConnectionManager:
    """Centralizes all signal→slot connections."""

    # Move these methods:
    - _connect_all_signals()
    - _connect_signals()
    - _connect_ui_signals()
    - _connect_ui_control_signals()
    - _connect_viewmodel_signals()
    - _connect_manager_signals()
    - _connect_ui_event_signals()
```

---

### Phase 4: Extract Utilities (~500 lines)

#### 4A. Display Filter Manager
```python
# affilabs/utils/display_filter_manager.py
class DisplayFilterManager:
    """Manages EMA and Kalman filtering for live display."""

    # Move filtering state and methods:
    - _ema_state
    - _display_filter_method
    - _display_filter_alpha
    - _kalman_filters
    - _set_display_filter()
```

#### 4B. Reference Subtraction Manager
```python
# affilabs/utils/reference_subtraction_manager.py
class ReferenceSubtractionManager:
    """Handles reference channel subtraction logic."""

    # Move reference state and methods:
    - _reference_channel
    - _ref_subtraction_enabled
    - _ref_channel
    - _apply_reference_subtraction()
    - _reset_channel_style()
```

---

## Proposed Final Structure

### Reduced Application Class (~2,000 lines)
```python
class Application(QApplication):
    """Main application coordinator - orchestrates subsystems only."""

    # Phase 1-9 initialization (keep as-is)
    # Coordinator references (new)
    # Lifecycle management (keep)
    # Processing thread (keep)
    # Cleanup methods (keep)
```

### New Files (11 new modules)

```
affilabs/coordinators/
├── hardware_event_coordinator.py      (~800 lines)
├── acquisition_event_coordinator.py   (~600 lines)
├── recording_event_coordinator.py     (~400 lines)
├── ui_control_event_coordinator.py    (~500 lines)
├── graph_event_coordinator.py         (~500 lines)
├── peripheral_event_coordinator.py    (~300 lines)
└── signal_connection_manager.py       (~400 lines)

affilabs/services/
├── spectrum_processing_service.py     (~600 lines)
└── ui_update_service.py               (~400 lines)

affilabs/utils/
├── display_filter_manager.py          (~300 lines)
└── reference_subtraction_manager.py   (~200 lines)
```

---

## Benefits

### Maintainability
- **68% reduction** in main Application class size (6,450 → 2,000 lines)
- Single Responsibility Principle - each coordinator handles one domain
- Easier to locate bugs - domain-based organization

### Testability
- Can unit test coordinators independently
- Mock dependencies easily
- Test signal handling without full app initialization

### Reusability
- Coordinators can be reused in different contexts
- Services are pure business logic
- Better separation enables CLI/API/GUI variations

### Developer Experience
- New developers can understand one coordinator at a time
- Parallel development - multiple devs can work on different coordinators
- Reduced cognitive load - no need to understand 6,450 lines

---

## Migration Path (Low Risk)

### Step 1: Extract without breaking
1. Create new coordinator files
2. Move methods but keep them callable from Application (wrapper methods)
3. Update signal connections to use coordinators
4. Test thoroughly

### Step 2: Update references
1. Search codebase for direct calls to moved methods
2. Update to use coordinator references
3. Run full test suite

### Step 3: Remove wrappers
1. Delete wrapper methods from Application
2. Final integration testing

---

## Estimated Effort

- **Phase 1 (Coordinators):** 2-3 days (high value, low risk)
- **Phase 2 (Services):** 1 day
- **Phase 3 (Signal Manager):** 1 day
- **Phase 4 (Utilities):** 1 day
- **Testing & Polish:** 1 day

**Total:** ~5-7 days for complete refactoring

---

## Immediate Next Step

**Recommendation:** Start with Phase 1A - Extract HardwareEventCoordinator

**Why this first?**
1. Clear boundaries - all hardware connection events
2. Low coupling - minimal dependencies on other parts
3. High impact - removes ~800 lines immediately
4. Easy to test - hardware events are well-defined
5. Template for other coordinators - establish pattern

**Command to proceed:**
```bash
# Create the first coordinator
touch affilabs/coordinators/hardware_event_coordinator.py
```

---

## Anti-Patterns to Avoid

1. ❌ **Don't create "Utils" classes** - Each coordinator should have clear domain
2. ❌ **Don't pass entire Application** - Pass only needed dependencies
3. ❌ **Don't create circular dependencies** - Coordinators should be independent
4. ❌ **Don't split mid-method** - Move entire cohesive methods
5. ❌ **Don't break signal connections** - Maintain all existing connections

---

## Success Metrics

- Application class < 2,500 lines
- No single coordinator > 800 lines
- All coordinators independently testable
- Zero regressions in existing functionality
- Pylance/Pyright still pass
- Pre-commit hooks still pass

---

## Questions for Discussion

1. Should we do this incrementally or all at once?
2. Any specific coordinators to prioritize for business reasons?
3. Want to review the first coordinator (HardwareEventCoordinator) before continuing?
4. Should we add unit tests as we extract, or in a separate pass?

---

*Generated: December 15, 2025*
