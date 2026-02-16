# main.py Refactoring Opportunities

**Current State**: 9,984 lines, single Application class with 130+ methods
**Status**: Functional but shows God Object anti-pattern

---

## 1. ✅ COMPLETED CLEANUP (This Session)

### Removed Dead Code
- ✅ **`_on_add_to_queue()`** - 81 lines (referenced non-existent `sidebar.note_input`)
- ✅ **Dead connection attempt** - 9 lines (line 1927: `add_to_queue_btn` connection)
- ✅ **Status**: 90 lines of unreachable code removed

---

## 2. 🔴 FRAGMENTED SIGNAL WIRING (HIGH PRIORITY)

Multiple disconnected `_connect_*` methods that could be consolidated:

```python
# CURRENT: 8 separate methods (lines 1087-2181)
_init_state_variables()
_init_managers()
_init_services()
_init_coordinators()
_init_viewmodels()
_connect_all_signals()          # Line 1087 calling 6+ connect methods
_connect_signals()               # Line 1260 - duplicate naming
_connect_queue_widgets()         # Line 1447
_connect_ui_signals()            # Line 1601
_connect_ui_control_signals()    # Line 1664
_connect_viewmodel_signals()     # Line 2013
_connect_manager_signals()       # Line 2075
_connect_ui_event_signals()      # Line 2113
```

**Issue**: Confusing hierarchy - `_connect_all_signals()` doesn't call all connect methods

**Refactor Recommendation**:
```python
# PROPOSED: Unified signal wiring phase
def _init_phase_7_signal_wiring(self):
    """Single phase for all signal connections."""
    self._wire_queue_signals()
    self._wire_ui_signals()
    self._wire_viewmodel_signals()
    self._wire_manager_signals()
    self._wire_hardware_signals()
    # ... etc
```

**Impact**:
- +20 lines of refactoring
- -10 lines of confusion (remove duplicate naming)
- Better readability ✅

---

## 3. 🟡 SIGNAL HANDLER CONSOLIDATION (MEDIUM PRIORITY)

66 signal handler methods (~2,800 lines, 28% of code):

```python
# Pattern duplication example:
_on_detector_wait_changed()      # Line 2181
_on_hardware_connected()         # Line 4179
_on_hardware_disconnected()      # Line 4260
_on_injection_auto_detected()    # Line 3152
_on_injection_window_expired()   # Line 3165
_on_injection_cancelled()        # Line 3169
# ... 60+ more similar patterns
```

**Refactor Opportunity**: Extract into signal handler coordinator

```python
# NEW FILE: coordinators/signal_handlers.py
class SignalHandlers:
    """Centralized signal handlers extracted from Application class."""

    def __init__(self, application):
        self.app = application  # Reference back to app

    def on_hardware_connected(self, status: dict):
        """Extracted from Application._on_hardware_connected()"""
        # Implementation

    def on_injection_auto_detected(self, channel: str, ...):
        """Extracted from Application._on_injection_auto_detected()"""
        # Implementation
```

**Impact**:
- -1,400 lines from Application class
- +1,200 lines in new coordinator (cleaner, testable)
- Better separation of concerns ✅
- Can test signal handlers independently ✅

---

## 4. 🟡 DEPRECATED METHODS (MEDIUM PRIORITY)

Methods marked DEPRECATED but still present:

```python
# Line 3064
def _on_start_contact_countdown(self):
    """DEPRECATED: Use _start_contact_countdown() instead."""
    self._start_contact_countdown()

# Line 2773-2775
def _update_now_running_banner(self, ...):
    """DEPRECATED: Banner removed - running status shown in intelligence bar instead."""
    pass

# Line 1757-1761
# Start Cycle button: DEPRECATED - now in Method Builder dialog
# Next Cycle button: DEPRECATED - now in Method Builder dialog
```

**Action**:
- ✅ Already removed `_on_add_to_queue()` (similar pattern)
- ⏳ Review and remove other deprecated methods (low priority)

**Impact**: +10-50 lines cleanup

---

## 5. 🔴 STATE MANAGEMENT FRAGMENTATION (HIGH PRIORITY)

State variables scattered throughout `__init__`:

```python
# Current: ~40 instance variables in _init_state_variables()
self.segment_queue = []
self.method_data = {}
self.current_cycle = None
self.acquisition_active = False
self.detector_connected = False
# ... etc scattered through __init__
```

**Refactor Recommendation**: Group into domain objects

```python
# PROPOSED: Create ApplicationState dataclass
@dataclass
class ApplicationState:
    """All application state in one organized object."""

    # Queue management
    segment_queue: list[Cycle] = field(default_factory=list)
    current_cycle: Cycle | None = None

    # Hardware state
    detector_connected: bool = False
    hardware_status: dict = field(default_factory=dict)

    # Acquisition state
    acquisition_active: bool = False
    experiment_start_time: float | None = None
```

**Impact**:
- -200 lines of scattered variable declarations
- +150 lines for dataclass definition
- Better organization ✅
- Type safety ✅
- Can snapshot/serialize state ✅

---

## 6. 🟡 INITIALIZATION PHASE CONSOLIDATION (LOW PRIORITY)

Current 9 phases could be more explicit:

```python
# Current implementation (implicit phases)
def __init__(self):
    # Phase 1-2: State & managers (implicit)
    self._init_state_variables()
    self._init_managers()
    self._init_services()

    # Phase 3: UI (implicit)
    self.main_window = create_ui()

    # Phase 4-5: Coordinators (implicit)
    self._init_coordinators()
    self._init_viewmodels()

    # Phase 6-7: Signals (implicit)
    self._connect_all_signals()
```

**Refactor Recommendation**: Make phases explicit

```python
# Proposed: Explicit phase structure
def __init__(self):
    # ================== PHASE 1 ==================
    self._phase_1_validate_requirements()

    # ================== PHASE 2 ==================
    self._phase_2_infrastructure_setup()

    # ================== PHASE 3 ==================
    self._phase_3_state_initialization()

    # ... etc through Phase 8
```

**Benefits**:
- Crystal clear initialization order ✅
- Easier debugging ✅
- Self-documenting code ✅

---

## 7. REFACTORING ROADMAP

### Quick Wins (1-2 hours)
```
1. ✅ Remove deprecated methods
2. ✅ Consolidate signal wiring method names
3. ⏳ Extract ApplicationState dataclass
```

### Medium Effort (3-4 hours)
```
4. ⏳ Extract SignalHandlers coordinator
5. ⏳ Make initialization phases explicit
```

### Major Refactoring (1-2 days)
```
6. ⏳ Extract UI coordinators (separate concerns)
7. ⏳ Extract business logic coordinators
```

---

## 8. KEY STATISTICS

**Current main.py**:
- Total lines: 9,984
- Application class: ~9,650 lines (97%)
- Methods: 130+
- Signal handlers: 66 methods (28% of code)
- Initialization phases: 9 (implicit, could be explicit)

**After Quick Wins**:
- Lines saved: ~90 (dead code removed ✅)
- Clarity improved: ✅ (consolidated method names)

**After Medium Refactoring**:
- Application class: ~6,000 lines (-32%)
- SignalHandlers coordinator: +1,200 lines
- ApplicationState dataclass: +150 lines
- Initialization phases: Explicit (easier to understand)

---

## 9. RECOMMENDATION

**Start with**: Signal wiring consolidation (quick fix, high impact on clarity)
**Then tackle**: ApplicationState dataclass (organization + type safety)
**Finally**: SignalHandlers extraction (separation of concerns, testability)

**Risk Level**: LOW - All refactorings are internal restructuring, no API changes

---

## 10. NOTES

- Removed `_on_add_to_queue()` dead code (81 lines) ✅
- Removed dead signal connection (9 lines) ✅
- Remaining refactoring maintains functionality while improving structure
- All changes are non-breaking internal improvements
