# Main.py Remaining Refactoring Opportunities

## Current Status
- **Total Lines**: 2,454 lines (current)
- **Original Size**: ~3,235 lines (before refactoring)
- **Lines Removed**: ~781 lines (24% reduction)

## Completed Refactorings ✅

### Phase 1: Data Processing (Complete)
- ✅ **Module**: `utils/spr_data_processor.py` (550 lines)
- ✅ **Removed from main**: ~550 lines
- ✅ **Methods**: Transmission calculation, resonance finding, filtering

### Phase 2: Calibration (Complete)
- ✅ **Module**: `utils/spr_calibrator.py` (945 lines)
- ✅ **Removed from main**: ~686 lines
- ✅ **Methods**: 9-step calibration process, LED optimization, validation

### Phase 3: Data I/O (In Progress - 60% Complete)
- ✅ **Module**: `utils/data_io_manager.py` (740 lines)
- ✅ **Refactored in main.py**: 
  - `save_temp_log()` (~26 → 4 lines)
  - `save_kinetic_log()` (~119 → 16 lines)
- ⚙️ **Remaining**: Widget file I/O operations (~550 lines)

### Hardware Management (Complete)
- ✅ **Pump Manager**: `utils/cavro_pump_manager.py` (integrated)
- ✅ **Kinetic Manager**: `utils/kinetic_manager.py` (integrated)
- ✅ **Hardware abstraction**: Signal-based communication

---

## Remaining Refactoring Candidates

### 🔴 Priority 1: Large Complex Methods (High Impact)

#### 1. **_grab_data() Method** (~185 lines, lines 1110-1295)
**Current Size**: 185 lines  
**Complexity**: Very High  
**Purpose**: Main SPR data acquisition loop

**What it does**:
- Infinite loop for continuous data acquisition
- Multi-channel LED switching and intensity reading
- Dark noise subtraction
- Transmission calculation (now using data_processor ✅)
- Resonance wavelength finding (now using data_processor ✅)
- Median filtering (now using data_processor ✅)
- Buffer management
- Signal emission for UI updates
- Error handling

**Refactoring Potential**: 🟢 **Medium (50-80 lines could be extracted)**

**Recommended Approach**: Create `SPRDataAcquisition` manager
```python
# New module: utils/spr_data_acquisition.py
class SPRDataAcquisition:
    """Manages continuous SPR data acquisition loop."""
    
    def __init__(self, ctrl, usb, data_processor, calibration_data):
        self.ctrl = ctrl
        self.usb = usb
        self.data_processor = data_processor
        # ... calibration parameters
    
    def acquire_channel_data(self, channel: str) -> ChannelReading:
        """Acquire data for single channel."""
        # LED control
        # Intensity reading
        # Dark noise subtraction
        # Returns structured data
    
    def process_reading(self, reading: ChannelReading) -> ProcessedReading:
        """Process raw reading to wavelength."""
        # Transmission calculation
        # Resonance finding
        # Filtering
    
    def run_acquisition_loop(self, stop_event, callback):
        """Main acquisition loop."""
        # Manages timing
        # Channel iteration
        # Error handling
```

**Benefits**:
- ✅ Testable in isolation
- ✅ Clearer separation of concerns
- ✅ Easier to add features (e.g., multi-threading)
- ✅ Reduces main.py by ~100 lines

**Estimated Impact**: Extract ~100-120 lines → Reduce main.py to ~2,330 lines

---

#### 2. **sensor_reading_thread() Method** (~97 lines, lines 1763-1860)
**Current Size**: 97 lines  
**Complexity**: High  
**Purpose**: Background thread for sensor monitoring

**What it does**:
- Infinite loop for continuous sensor reading
- Reads temperature sensors via kinetic_manager (already refactored ✅)
- Valve state checking
- Device temperature monitoring
- P4SPR-specific temperature logging
- Temperature averaging and buffering
- Signal emission for UI updates
- Timing control (sensor_interval)

**Refactoring Potential**: 🟡 **Low-Medium (30-40 lines could be simplified)**

**Why less refactoring potential**:
- Already uses kinetic_manager for most operations ✅
- Device-specific logic (P4SPR vs KNX) hard to abstract
- Thread control logic must stay in main
- UI signal emission must stay in main

**Possible Improvements**:
```python
# Extract P4SPR temperature logging to calibrator or data_io
def log_p4spr_temperature(self):
    """Log P4SPR device temperature."""
    # Move temperature buffering logic
    # Move temperature log management
    # Return formatted temp string
```

**Estimated Impact**: Minor cleanup, ~10-20 lines reduction

---

#### 3. **save_calibration_profile() Method** (~62 lines, lines 1859-1921)
**Current Size**: 62 lines  
**Complexity**: Medium  
**Purpose**: Save calibration data to JSON file

**What it does**:
- Prompts for filename (if not provided)
- Collects calibration parameters
- Converts numpy arrays to lists
- Saves to JSON file
- Error handling

**Refactoring Potential**: 🟢 **High (entire method could move to SPRCalibrator)**

**Recommended Approach**: Move to calibrator module
```python
# In utils/spr_calibrator.py
class SPRCalibrator:
    def save_profile(self, profile_name: str | None = None) -> bool:
        """Save calibration profile to file."""
        # Current save_calibration_profile logic
        # Already has access to all calibration data
        
    def load_profile(self, profile_name: str | None = None) -> bool:
        """Load calibration profile from file."""
        # Current load_calibration_profile logic
```

**In main.py**:
```python
def save_calibration_profile(self, profile_name: str | None = None) -> bool:
    """Save calibration profile."""
    if self.calibrator:
        return self.calibrator.save_profile(profile_name)
    return False
```

**Benefits**:
- ✅ Calibration data management in one place
- ✅ Easier to test
- ✅ Reduces main.py by ~120 lines (save + load methods)

**Estimated Impact**: ~120 lines reduction → main.py down to ~2,210 lines

---

#### 4. **load_calibration_profile() Method** (~97 lines, lines 1921-2018)
**Current Size**: 97 lines  
**Complexity**: High  
**Purpose**: Load calibration data from JSON file

**See analysis above** - should move to SPRCalibrator with save_calibration_profile()

---

### 🟡 Priority 2: Medium Complexity Methods (Moderate Impact)

#### 5. **auto_polarization() Method** (~40 lines, lines 1408-1448)
**Current Size**: 40 lines  
**Purpose**: Automatic polarizer optimization

**Refactoring Potential**: 🟢 **High (move to SPRCalibrator)**

This is a calibration-related function and should live in the calibrator module.

**Estimated Impact**: ~40 lines reduction

---

#### 6. **update_advanced_params() Method** (~68 lines, lines 2113-2181)
**Current Size**: 68 lines  
**Purpose**: Update device parameters from advanced settings

**Refactoring Potential**: 🟡 **Medium (create ConfigurationManager)**

Could be part of a configuration management system:
```python
# utils/config_manager.py
class DeviceConfigManager:
    def update_led_settings(self, params)
    def update_timing_settings(self, params)
    def update_filter_settings(self, params)
    def validate_parameters(self, params)
```

**Estimated Impact**: ~50 lines reduction

---

#### 7. **disconnect_handler() Method** (~86 lines, lines 2285-2371)
**Current Size**: 86 lines  
**Purpose**: Handle device disconnection

**Refactoring Potential**: 🟡 **Medium (simplify with manager cleanup methods)**

Each hardware manager could have a `cleanup()` method:
```python
# In each manager
class PumpManager:
    def cleanup(self):
        """Stop operations and disconnect."""
        self.stop()
        self.disconnect()

# In main.py
def disconnect_handler(self, disconnect_type: str):
    if self.pump_manager:
        self.pump_manager.cleanup()
    if self.kinetic_manager:
        self.kinetic_manager.cleanup()
    # ... etc
```

**Estimated Impact**: ~30 lines reduction

---

### 🟢 Priority 3: Small Methods (Low Impact but Easy Wins)

#### 8. **Kinetic Operation Methods** (8 methods, ~200 lines total)
**Lines 507-673**:
- `regenerate()` (~32 lines)
- `flush()` (~21 lines)
- `inject()` (~43 lines)
- `cancel_injection()` (~12 lines)
- `change_flow_rate()` (~43 lines)
- `initialize_pumps()` (~17 lines)
- `stop_pump()` (~39 lines)
- `three_way()` (~14 lines)
- `six_port()` (~15 lines)

**Refactoring Potential**: 🟡 **Medium (consolidate into KineticOperations class)**

**Recommended Approach**:
```python
# utils/kinetic_operations.py
class KineticOperations:
    """High-level kinetic experiment operations."""
    
    def __init__(self, kinetic_manager, pump_manager, ...):
        self.kinetic_manager = kinetic_manager
        self.pump_manager = pump_manager
    
    async def regenerate(self, contact_time, flow_rate):
        """Regeneration sequence."""
        
    async def flush(self, flush_time, flow_rate):
        """Flush sequence."""
        
    async def inject(self, contact_time, flow_rate, channel):
        """Injection sequence."""
```

**Estimated Impact**: ~150 lines reduction → main.py down to ~2,060 lines

---

#### 9. **Valve Control Handlers** (4 methods, ~90 lines)
**Lines 1558-1647**:
- `three_way_handler()` (~20 lines)
- `six_port_handler()` (~69 lines)
- `turn_off_six_ch1()` (~6 lines)
- `turn_off_six_ch2()` (~6 lines)

**Refactoring Potential**: 🟡 **Low-Medium**

These are mostly UI event handlers and should stay in main. However, `six_port_handler()` has complex logic that could be simplified using kinetic_manager methods.

**Estimated Impact**: ~20 lines reduction through simplification

---

### 📊 Refactoring Summary Table

| Method/Area | Current Lines | Refactoring Potential | New Module | Lines Saved | Priority |
|-------------|--------------|----------------------|------------|-------------|----------|
| **_grab_data()** | 185 | High | SPRDataAcquisition | ~100-120 | 🔴 High |
| **save/load_calibration_profile()** | 159 | High | SPRCalibrator | ~120 | 🔴 High |
| **auto_polarization()** | 40 | High | SPRCalibrator | ~35 | 🔴 High |
| **Kinetic operations** | 200 | Medium | KineticOperations | ~150 | 🟡 Medium |
| **update_advanced_params()** | 68 | Medium | ConfigManager | ~50 | 🟡 Medium |
| **disconnect_handler()** | 86 | Medium | Manager cleanup | ~30 | 🟡 Medium |
| **sensor_reading_thread()** | 97 | Low | Minor cleanup | ~20 | 🟢 Low |
| **Valve handlers** | 90 | Low | Simplification | ~20 | 🟢 Low |
| **Widget Data I/O** | 550* | High | DataIOManager | ~400 | 🔴 High |

\*In widgets/datawindow.py and widgets/analysis.py, not main.py

**Total Potential Reduction**: ~925 lines from main.py  
**Projected Final Size**: ~1,530 lines (from current 2,454)  
**Overall Reduction**: ~53% from original 3,235 lines

---

## Recommended Refactoring Phases

### 🎯 **Phase 4: Calibration Profile Management** (Recommended Next)
**Effort**: Low (1-2 hours)  
**Impact**: High (~120 lines)  
**Risk**: Low (well-contained functionality)

**Steps**:
1. Add `save_profile()` and `load_profile()` methods to SPRCalibrator
2. Add `auto_polarization()` method to SPRCalibrator
3. Update main.py to delegate to calibrator
4. Test save/load functionality

**Expected Result**: main.py → ~2,290 lines

---

### 🎯 **Phase 5: Data Acquisition Manager** (High Value)
**Effort**: Medium (4-6 hours)  
**Impact**: High (~120 lines)  
**Risk**: Medium (core data loop - needs careful testing)

**Steps**:
1. Create `utils/spr_data_acquisition.py`
2. Extract channel acquisition logic
3. Extract processing pipeline
4. Create acquisition loop manager
5. Update main.py _grab_data() to use manager
6. Extensive testing

**Expected Result**: main.py → ~2,170 lines

---

### 🎯 **Phase 6: Kinetic Operations Manager** (Nice to Have)
**Effort**: Medium (3-5 hours)  
**Impact**: Medium (~150 lines)  
**Risk**: Low (high-level operations)

**Steps**:
1. Create `utils/kinetic_operations.py`
2. Move regenerate/flush/inject sequences
3. Update UI handlers to use operations manager
4. Test all kinetic workflows

**Expected Result**: main.py → ~2,020 lines

---

### 🎯 **Phase 7: Widget Data I/O Integration** (Complete Phase 3)
**Effort**: Medium (3-4 hours)  
**Impact**: N/A (widgets, not main.py)  
**Risk**: Low (DataIOManager already created)

**Steps**:
1. Update `widgets/datawindow.py` save methods (~400 lines)
2. Update `widgets/analysis.py` save methods (~150 lines)
3. Test all export functionality

---

## Methods That Should NOT Be Refactored

### ❌ UI Event Handlers
- `handle_regen_button()`, `handle_flush_button()`, `handle_inject_button()`
- `speed_change_handler()`, `run_button_handler()`, `flush_button_handler()`
- These are thin wrappers that connect UI to business logic
- **Reason**: Part of application orchestration layer

### ❌ Qt Signal Handlers
- `_on_pump_state_changed()`, `_on_valve_state_changed()`, etc.
- `_on_calibration_started()`, `_on_calibration_status()`
- **Reason**: Need to stay in main to emit UI signals and update app state

### ❌ Application Lifecycle Methods
- `startup()`, `stop()`, `close()`
- `connect_dev()`, `open_device()`
- **Reason**: Core application control flow

### ❌ Thread Management
- `connection_thread()`, thread creation/joining logic
- **Reason**: Application-level concurrency control

### ❌ Data Accessors
- `sensorgram_data()`, `spectroscopy_data()`, `transfer_sens_data()`
- **Reason**: Simple data formatting for UI, minimal logic

---

## Final Architecture Vision

```
main/main.py (~1,500 lines)
├── Application lifecycle
├── UI event handlers (thin wrappers)
├── Qt signal handlers
├── Thread management
├── State coordination
└── Manager orchestration

utils/
├── spr_data_processor.py (550 lines) ✅ Complete
├── spr_calibrator.py (945 lines) ✅ Complete
│   └── + save/load profile (Phase 4)
│   └── + auto_polarization (Phase 4)
├── data_io_manager.py (740 lines) ✅ Complete
├── cavro_pump_manager.py ✅ Complete
├── kinetic_manager.py ✅ Complete
├── spr_data_acquisition.py (NEW - Phase 5)
│   ├── Channel acquisition
│   ├── Processing pipeline
│   └── Acquisition loop management
├── kinetic_operations.py (NEW - Phase 6)
│   ├── Regeneration sequence
│   ├── Flush sequence
│   └── Injection sequence
└── config_manager.py (NEW - Optional)
    └── Parameter validation & updates

widgets/
├── datawindow.py (use DataIOManager - Phase 7)
└── analysis.py (use DataIOManager - Phase 7)
```

---

## Metrics Summary

### Current Status
- **Original main.py**: 3,235 lines
- **Current main.py**: 2,454 lines
- **Reduction so far**: 781 lines (24%)

### After All Proposed Refactoring
- **Projected main.py**: ~1,530 lines
- **Total reduction**: 1,705 lines (53%)
- **Code quality**: Modular, testable, maintainable

### Lines of Code Distribution (Final)
- main.py: ~1,530 lines (orchestration)
- Utility modules: ~3,800 lines (business logic)
- Total codebase: ~5,330 lines (vs ~3,235 original)

**Net increase**: ~2,095 lines  
**Why this is good**: Code is now organized, documented, testable, and maintainable!

---

## Recommendation

**Start with Phase 4** (Calibration Profile Management):
- ✅ Lowest effort
- ✅ High impact (~120 lines)
- ✅ Low risk
- ✅ Quick win to build momentum

Then decide between Phase 5 (Data Acquisition - more complex but high value) or Phase 6 (Kinetic Operations - simpler but good cleanup).

Complete Phase 7 (Widget I/O) to finish the Data I/O refactoring story.
