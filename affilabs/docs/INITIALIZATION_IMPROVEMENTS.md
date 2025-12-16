"""INITIALIZATION IMPROVEMENTS - REFACTORING PLAN

This document outlines the improvements to the Application initialization architecture
to address the identified weaknesses from the code review.

## IDENTIFIED ISSUES

### Issue 1: Large State Variables Method (Lines 558-655)
**Problem**: `_init_state_variables()` contains 50+ instance variables scattered across one method.
**Impact**:
- Hard to understand what state exists
- No logical grouping
- Difficult to serialize/test state
- Prone to initialization order bugs

**Solution**: Created `affilabs/app_state.py` with dataclass-based state groups:
```python
@dataclass
class ApplicationState:
    lifecycle: LifecycleState           # closing, device_config_initialized, ...
    experiment: ExperimentState         # start_time, session_cycles_dir, ...
    calibration: CalibrationState       # retry_count, completed, ...
    channel: ChannelState               # selected_axis, selected_channel, ...
    filtering: FilteringState           # filter_enabled, ema_state, ...
    timeframe_mode: TimeframeModeState  # live_cycle_timeframe, mode, ...
    led_monitoring: LEDMonitoringState  # led_status_timer
    performance: PerformanceState       # spectrum_queue, counters, ...
    ui: UIState                         # pending_graph_updates, ...
    baseline_recording: BaselineRecordingState  # recorder reference
```

**Benefits**:
- ✅ Type hints for IDE support
- ✅ Clear separation of concerns
- ✅ Easy to serialize for state persistence
- ✅ Testable (can create mock states)
- ✅ Single source of truth for initialization

### Issue 2: Direct UI→Hardware Reference (Line 764)
**Problem**: `self.main_window.hardware_manager = self.hardware_mgr` violates layering.
**Impact**:
- UI directly accesses hardware (lines 5517-5525 in affilabs_core_ui.py)
- Breaks signal-based architecture
- Tight coupling between UI and Business layer
- Can't test UI without hardware manager

**Current Code** (VIOLATION):
```python
# main-simplified.py line 764
self.main_window.hardware_manager = self.hardware_mgr

# affilabs_core_ui.py lines 5517-5525
def _apply_settings(self):
    # Direct access to hardware
    hardware_mgr = None
    if hasattr(self, 'hardware_manager'):
        hardware_mgr = self.hardware_manager

    if not hardware_mgr or not hardware_mgr.ctrl:
        QMessageBox.warning(self, "Error", "Controller not connected...")
        return

    ctrl = hardware_mgr.ctrl  # ← LAYERING VIOLATION
    ctrl.set_intensity('a', led_a)  # ← DIRECT HARDWARE ACCESS
```

**Solution**: Signal-based communication (see SIGNAL_BASED_SOLUTION.md for full implementation)

**Improved Code** (SIGNAL-BASED):
```python
# affilabs_core_ui.py - UI emits signal with data
class AffilabsMainWindow(QMainWindow):
    # Define signal (add to class body near top)
    apply_led_settings_requested = Signal(dict)  # {settings: {led_a: int, led_b: int, ...}}

    def _apply_settings(self):
        # Parse UI inputs
        led_settings = {
            'led_a': int(self.channel_a_input.text()) if self.channel_a_input.text() else None,
            'led_b': int(self.channel_b_input.text()) if self.channel_b_input.text() else None,
            'led_c': int(self.channel_c_input.text()) if self.channel_c_input.text() else None,
            'led_d': int(self.channel_d_input.text()) if self.channel_d_input.text() else None,
            's_pos': int(self.s_position_input.text()) if self.s_position_input.text() else None,
            'p_pos': int(self.p_position_input.text()) if self.p_position_input.text() else None,
        }

        # Emit signal - let Application handle business logic
        self.apply_led_settings_requested.emit(led_settings)

# main-simplified.py - Application handles signal
def _create_main_window(self):
    self.main_window = AffilabsMainWindow()
    # NO hardware manager reference!
    # self.main_window.hardware_manager = self.hardware_mgr  # ← DELETE THIS

def _connect_ui_signals(self):
    # Connect UI signal to application handler
    self.main_window.apply_led_settings_requested.connect(self._on_apply_led_settings)

def _on_apply_led_settings(self, settings: dict):
    \"\"\"Handle LED settings from UI (business logic in Application layer).\"\"\"
    # Validate hardware connected
    if not self.hardware_mgr or not self.hardware_mgr.ctrl:
        QMessageBox.warning(self.main_window, "Error", "Controller not connected...")
        return

    # Apply LED intensities
    ctrl = self.hardware_mgr.ctrl
    for channel, value in [('a', settings.get('led_a')), ('b', settings.get('led_b')),
                           ('c', settings.get('led_c')), ('d', settings.get('led_d'))]:
        if value is not None:
            ctrl.set_intensity(channel, value)

    # Save to device config
    if self.device_config:
        for channel in ['a', 'b', 'c', 'd']:
            key = f'led_{channel}'
            if settings.get(key) is not None:
                self.device_config.data['hardware']['led_intensities'][channel] = settings[key]
        self.device_config.save()
```

**Benefits**:
- ✅ Clean layering: UI → Application → Hardware
- ✅ UI is testable (no hardware dependencies)
- ✅ Business logic centralized in Application
- ✅ Can add validation/authorization in Application layer

### Issue 3: Optional Coordinators (Lines 798-803)
**Problem**: `if COORDINATORS_AVAILABLE:` creates runtime fragility.
**Impact**:
- Silent failures (coordinators missing but app continues)
- Null checks scattered throughout code
- Hard to debug (is coordinator missing or just not initialized?)
- Inconsistent behavior between environments

**Current Code** (FRAGILE):
```python
# main-simplified.py lines 798-803
if COORDINATORS_AVAILABLE:
    self.ui_updates = AL_UIUpdateCoordinator(self, self.main_window)
    self.dialog_manager = DialogManager(self.main_window)
else:
    self.ui_updates = None  # ← SILENT FAILURE
    self.dialog_manager = None

# Later in code (scattered null checks)
if self.ui_updates:  # ← FRAGILE
    self.ui_updates.update_status(...)
```

**Solution**: Fail-fast at import (remove optional flag)

**Improved Code** (FAIL-FAST):
```python
# main-simplified.py top imports (remove try/except)
from affilabs.presenters.ui_update_coordinator import AL_UIUpdateCoordinator
from affilabs.utils.dialog_manager import DialogManager

# If imports fail, app crashes immediately at startup (GOOD!)
# No silent degradation, no scattered null checks

def _init_coordinators(self):
    # Always initialize (no optional flag)
    self.ui_updates = AL_UIUpdateCoordinator(self, self.main_window)
    self.dialog_manager = DialogManager(self.main_window)
    logger.info("  UI coordinators initialized")

# Later in code (no null checks needed)
self.ui_updates.update_status(...)  # ← CLEAN, ALWAYS AVAILABLE
```

**Benefits**:
- ✅ Fail-fast: Missing dependencies caught at startup
- ✅ No scattered null checks
- ✅ Predictable behavior across environments
- ✅ Easier debugging (import fails immediately with traceback)

## MIGRATION PLAN

### Phase 1: State Refactoring (COMPLETED)
- [X] Create `affilabs/app_state.py` with dataclass groups
- [ ] Replace scattered variables with `self.state = ApplicationState()`
- [ ] Add backward compatibility properties during migration
- [ ] Gradually update all code to use `self.state.lifecycle.closing` instead of `self.closing`
- [ ] Remove compatibility properties once migration complete

### Phase 2: Signal-Based UI (IN PROGRESS)
- [X] Identify layering violations (line 764, lines 5517-5525)
- [ ] Add `apply_led_settings_requested` signal to AffilabsMainWindow
- [ ] Refactor `_apply_settings()` to emit signal instead of direct hardware access
- [ ] Add `_on_apply_led_settings()` handler in Application
- [ ] Remove `self.main_window.hardware_manager = self.hardware_mgr`
- [ ] Test LED settings still work via signal routing

### Phase 3: Fail-Fast Coordinators (NOT STARTED)
- [ ] Remove `try/except` around coordinator imports
- [ ] Remove `COORDINATORS_AVAILABLE` flag
- [ ] Remove null checks for `self.ui_updates` and `self.dialog_manager`
- [ ] Update Phase 2 validation to fail fast if coordinators missing
- [ ] Test app crashes gracefully if coordinators unavailable

### Phase 4: Documentation Update (NOT STARTED)
- [ ] Update AFFILABS_CORE_BACKEND_ARCHITECTURE.md with new state management
- [ ] Document signal-based UI patterns
- [ ] Add validation checklist for layering violations
- [ ] Update initialization flow diagram

## TESTING CHECKLIST

After each phase, verify:
- [ ] Application starts successfully
- [ ] Hardware connection works (Power button)
- [ ] LED settings can be applied from Settings tab
- [ ] Servo positions saved to device_config.json
- [ ] Calibration runs without errors
- [ ] Live acquisition displays correctly
- [ ] No runtime errors related to missing coordinators

## FILES TO MODIFY

1. **affilabs/app_state.py** (NEW - CREATED)
   - Dataclass definitions for grouped state

2. **main-simplified.py** (MODIFY)
   - Line 558-655: Replace `_init_state_variables()` with `self.state = ApplicationState()`
   - Line 764: Remove `self.main_window.hardware_manager = self.hardware_mgr`
   - Add `_on_apply_led_settings()` handler
   - Lines 798-803: Remove optional coordinator logic
   - Top imports: Remove try/except around coordinators

3. **affilabs/affilabs_core_ui.py** (MODIFY)
   - Add `apply_led_settings_requested` signal definition
   - Lines 5477-5580: Refactor `_apply_settings()` to emit signal
   - Remove hardware_manager access (lines 5517-5525)

4. **AFFILABS_CORE_BACKEND_ARCHITECTURE.md** (UPDATE)
   - Add state management section
   - Document signal-based UI patterns
   - Update initialization flow diagram

## BACKWARD COMPATIBILITY

During migration, add compatibility properties:

```python
# main-simplified.py
class Application(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        self.state = ApplicationState()  # New grouped state

    # Backward compatibility properties (remove after migration)
    @property
    def closing(self):
        return self.state.lifecycle.closing

    @closing.setter
    def closing(self, value):
        self.state.lifecycle.closing = value

    @property
    def experiment_start_time(self):
        return self.state.experiment.start_time

    @experiment_start_time.setter
    def experiment_start_time(self, value):
        self.state.experiment.start_time = value

    # ... repeat for all migrated variables
```

This allows gradual migration without breaking existing code.

## ROLLBACK PLAN

If issues arise:
1. Git revert to pre-refactoring commit
2. Keep `affilabs/app_state.py` for future use
3. Document issues encountered for next attempt

## SUCCESS CRITERIA

Refactoring complete when:
- ✅ All state variables grouped in `app_state.py`
- ✅ No direct UI→Hardware access (all via signals)
- ✅ No optional coordinators (fail-fast at import)
- ✅ Architecture document updated
- ✅ All tests passing
- ✅ No runtime errors in production use

## REFERENCES

- Original analysis: main-simplified.py lines 370-430 (9-phase init)
- HAL architecture: AFFILABS_CORE_BACKEND_ARCHITECTURE.md
- Signal patterns: Qt documentation on Signals & Slots
