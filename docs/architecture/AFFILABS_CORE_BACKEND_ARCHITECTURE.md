# Affilabs-Core Backend Architecture Master Document

**Version**: 1.0.0
**Date**: December 15, 2025
**Status**: Architecture Reference (Gold Standard)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Hardware Abstraction Layer (HAL)](#hardware-abstraction-layer-hal)
3. [Data Acquisition Pipeline](#data-acquisition-pipeline)
4. [Spectrum Averaging Architecture](#spectrum-averaging-architecture)
5. [Detector Agnostic Design](#detector-agnostic-design)
6. [Key Components](#key-components)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Design Principles](#design-principles)
9. [Code Organization](#code-organization)
10. [Removed Features](#removed-features)

---

## Architecture Overview

Affilabs-Core implements a **clean layered architecture** with strict separation of concerns:

```
┌─────────────────────────────────────────────┐
│          UI Layer (PySide6/PyQtGraph)       │
├─────────────────────────────────────────────┤
│     Application Layer (main-simplified.py)  │
├─────────────────────────────────────────────┤
│   Core Services (Data Acquisition Manager)  │
├─────────────────────────────────────────────┤
│  Hardware Abstraction Layer (HAL Adapters)  │ ← CRITICAL
├─────────────────────────────────────────────┤
│    Hardware Drivers (USB4000, PhasePhotonics)│
└─────────────────────────────────────────────┘
```

### Core Principle: **ALL hardware access goes through HAL**

No component should directly call hardware methods except through HAL interfaces. This ensures:
- Detector vendor independence
- Consistent data processing
- Single source of truth for averaging
- Easy testing and mocking

---

## Hardware Abstraction Layer (HAL)

### Location
- **Interfaces**: `affilabs/utils/hal/interfaces.py`
- **Adapters**: `affilabs/utils/hal/adapters.py`

### HAL Contract (Protocol)

```python
class Spectrometer(Protocol):
    def read_roi(self, wave_min_index: int, wave_max_index: int, num_scans: int = 1) -> Optional[np.ndarray]
    def read_wavelength(self) -> np.ndarray
    def set_integration(self, integration_ms: int) -> None

    @property
    def min_integration(self) -> float

    @property
    def serial_number(self) -> Optional[str]
```

### Key HAL Method: `read_roi()`

**Purpose**: Read Region of Interest with optional built-in averaging

**Signature**:
```python
def read_roi(self, wave_min_index: int, wave_max_index: int, num_scans: int = 1)
```

**Behavior**:
- `num_scans=1` → Single read, NO averaging
- `num_scans>1` → Multiple reads, returns `np.mean(stack, axis=0)`

**Implementation** (`adapters.py` lines 156-190):

```python
def read_roi(self, wave_min_index, wave_max_index, num_scans=1):
    try:
        if getattr(self._usb, "use_seabreeze", False):
            # SeaBreeze backend (Ocean Optics USB4000)
            if num_scans == 1:
                full = self._usb.read_intensity()
                return full[wave_min_index:wave_max_index].astype('u4')
            else:
                stack = np.empty((num_scans, spectrum_length), dtype='u2')
                for i in range(num_scans):
                    full = self._usb.read_intensity()
                    stack[i] = full[wave_min_index:wave_max_index]
                return np.mean(stack, axis=0).astype('u4')
        else:
            # DLL backend (PhasePhotonics) - OPTIMIZED FAST PATH
            # Direct memory access via sensor frames
            offset = wave_min_index * 2
            num = wave_max_index - wave_min_index
            # ... ctypes DLL calls for performance ...
    except Exception:
        return None
```

### Why HAL is Critical

✅ **Single Source of Truth**: Averaging logic exists in ONE place
✅ **Performance Optimization**: Fast path for different detector backends
✅ **Vendor Independence**: Swap detectors by wrapping in adapter
✅ **ROI Efficiency**: No need to read full spectrum then slice
✅ **Consistent Behavior**: All acquisition code uses same interface

---

## Data Acquisition Pipeline

### Live Acquisition Flow

```
Hardware Manager
    ↓
Data Acquisition Manager (_acquire_raw_spectrum)
    ↓
HAL Adapter (read_roi with num_scans)
    ↓
Detector (USB4000 / PhasePhotonics)
    ↓
← Raw ROI spectrum (dark-subtracted by caller)
    ↓
Main App (_process_spectrum_data)
    ↓ (dark subtraction + transmission calculation)
UI Update Coordinator (batch updates every 100ms)
    ↓
SpectroscopyPresenter
    ↓
PyQtGraph plots
```

### Key Acquisition Method

**File**: `affilabs/core/data_acquisition_manager.py`
**Method**: `_acquire_raw_spectrum()` (lines 1755-1765)

```python
# Use HAL interface with built-in averaging
raw_spectrum = usb.read_roi(
    self.calibration_data.wave_min_index,
    self.calibration_data.wave_max_index,
    num_scans=num_scans  # From calibration data or limited by timing window
)
```

### Calibration Acquisition

**File**: `affilabs/utils/calibration_adaptive_integration.py`
**S-Mode Reference** (lines 392-397):

```python
spectrum = usb.read_roi(
    wave_min_index,
    wave_max_index,
    num_scans=scan_config.ref_scans  # Typically 5-10
)
```

**P-Mode Reference** (lines 467-475):

```python
spectrum = usb.read_roi(
    wave_min_index,
    wave_max_index,
    num_scans=scan_config.ref_scans
)
```

**Dark Noise** (lines 520-529):

```python
dark_full_spectrum = usb.read_roi(
    0,  # Full spectrum
    len(usb.read_wavelength()),
    num_scans=scan_config.dark_scans
)
```

---

## Spectrum Averaging Architecture

### Averaging Strategy

**ALL spectrum averaging is done in software via HAL `read_roi()`**

**Hardware Detector**: Returns single raw spectrum per `read_intensity()` call

---

## Removed Features

### Timeframe Mode (Removed)

The previously disabled "Timeframe Mode" (moving/fixed window visualization) has been fully removed from `main-simplified.py`.

- Removed: State (`_live_cycle_timeframe`, `_live_cycle_mode`, `USE_TIMEFRAME_MODE`, `_timeframe_baseline_wavelengths`, `_last_processed_time`, `_last_timeframe_update`), signals, and handlers.
- Preserved: Legacy cursor-based extraction via `_extract_cycle_from_cursors()`.
- Verified: Single authoritative `_update_device_status_ui()` with correct implementation; syntax check passes.

Rationale: The feature flag was permanently False, leaving ~280+ lines unreachable and adding maintenance risk. Removal simplifies initialization and runtime paths without changing user-facing behavior.
**Software HAL**: Loops `num_scans` times, collects stack, returns `np.mean()`

### Averaging Locations (All via HAL)

1. **Live Acquisition** (`data_acquisition_manager.py`)
   - num_scans from calibration data
   - Limited by detection window timing: `max_scans = detector_window_ms / integration_time_ms`

2. **Calibration** (`calibration_adaptive_integration.py`)
   - S-mode: `scan_config.ref_scans` (typically 5-10)
   - P-mode: `scan_config.ref_scans` (typically 5-10)
   - Dark: `scan_config.dark_scans` (typically 10)

3. **Reference Baseline** (`reference_baseline_processing.py`)
   - User-configurable `num_scans`

### NOT Averaging (Statistical Analysis Only)

The following files use `np.mean()` for **statistics, NOT spectrum averaging**:

- `spectrum_data.py`: Mean intensity for display
- `transmission_calculator.py`: Transmission statistics
- `calibration_validator.py`: Signal validation metrics
- `baseline_corrector.py`: Baseline shift calculation

### Legacy Exception: `startup_calibration.py`

**Function**: `acquire_raw_spectrum()` (lines 1118-1133)
**Why**: Works with FULL spectrum during initial calibration before ROI indices established
**Status**: Legitimate - HAL cannot be used before wavelength calibration

---

## Detector Agnostic Design

### Supported Detectors

✅ **Ocean Optics USB4000** (SeaBreeze backend)
✅ **PhasePhotonics** (DLL backend with optimized sensor frames)
✅ **Any new detector** (via adapter pattern)

### Adding New Detectors

**Step 1**: Create detector driver

```python
class NewDetector:
    def read_intensity(self) -> np.ndarray:  # Full spectrum
    def read_wavelength(self) -> np.ndarray:  # Wavelength calibration
    def set_integration(self, ms: float):     # Integration time

    @property
    def serial_number(self) -> str

    @property
    def min_integration(self) -> float
```

**Step 2**: Wrap in HAL adapter

```python
from affilabs.utils.hal.adapters import OceanSpectrometerAdapter

detector = NewDetector()
hal_detector = OceanSpectrometerAdapter(detector)
```

**Step 3**: Use throughout application

```python
# All acquisition code automatically works
spectrum = hal_detector.read_roi(wave_min, wave_max, num_scans=5)
```

### Detector Detection

HAL adapter automatically detects backend type:

```python
if getattr(self._usb, "use_seabreeze", False):
    # SeaBreeze path
else:
    # DLL path with optimizations
```

---

## Key Components

### 1. Hardware Manager
**File**: `affilabs/core/hardware_manager.py`
**Role**: Initialize hardware, create HAL wrappers, manage connections
**Key Method**: `initialize_detector()` - wraps detector in `OceanSpectrometerAdapter`

### 2. Data Acquisition Manager
**File**: `affilabs/core/data_acquisition_manager.py`
**Role**: Control acquisition timing, LED synchronization, spectrum collection
**Key Methods**:
- `_acquire_raw_spectrum()`: Single channel acquisition via HAL
- `start_rankbatch()`: Multi-channel synchronized acquisition
- `_emit_raw_spectrum()`: Emit data package to application

### 3. Calibration Service
**File**: `affilabs/utils/calibration_adaptive_integration.py`
**Role**: Determine optimal LED intensities and integration times
**HAL Usage**: All reference and dark captures via `read_roi()`

### 4. Main Application
**File**: `main-simplified.py`
**Role**: Process raw spectra, calculate transmission, update UI
**Key Methods**:
- `_process_spectrum_data()`: Dark subtraction + transmission
- `_queue_transmission_update()`: Batch updates to UI

### 5. UI Update Coordinator
**File**: `affilabs/presenters/ui_update_coordinator.py`
**Role**: Batch UI updates every 100ms to prevent GUI freezing
**Pattern**: Queue-based deferred updates

### 6. Spectroscopy Presenter
**File**: `affilabs/presenters/spectroscopy_presenter.py`
**Role**: Update PyQtGraph plots with latest data
**Methods**: `update_raw_spectrum()`, `update_transmission_spectrum()`

---

## Data Flow Diagrams

### Live Acquisition Data Flow

```
┌─────────────────────┐
│  Hardware Manager   │
│  (usb wrapped in    │
│   HAL adapter)      │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────────────────────┐
│  Data Acquisition Manager           │
│  ┌───────────────────────────────┐  │
│  │ _acquire_raw_spectrum()       │  │
│  │   usb.read_roi(               │  │ ← HAL INTERFACE
│  │     wave_min, wave_max,       │  │
│  │     num_scans                 │  │
│  │   )                           │  │
│  └───────────────────────────────┘  │
└──────────┬──────────────────────────┘
           │ spectrum_acquired.emit()
           ↓
┌─────────────────────────────────────┐
│  Main App                           │
│  ┌───────────────────────────────┐  │
│  │ _on_spectrum_acquired()       │  │
│  │   → Queue to processing thread │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ _process_spectrum_data()      │  │
│  │   - Dark subtraction          │  │
│  │   - Transmission = dark_sub / │  │
│  │                     s_pol_ref │  │
│  │   - Peak extraction           │  │
│  └───────────────────────────────┘  │
└──────────┬──────────────────────────┘
           │ queue_transmission_update()
           ↓
┌─────────────────────────────────────┐
│  UI Update Coordinator              │
│  (100ms timer batch processing)     │
└──────────┬──────────────────────────┘
           │ _update_transmission_curves()
           ↓
┌─────────────────────────────────────┐
│  SpectroscopyPresenter              │
│  update_raw_spectrum()              │
└──────────┬──────────────────────────┘
           │
           ↓
┌─────────────────────────────────────┐
│  PyQtGraph Plots (Sidebar/Graphs)   │
└─────────────────────────────────────┘
```

### Data Package Structure

**Emitted by**: `DataAcquisitionManager._emit_raw_spectrum()` (line 1268)

```python
spectrum_data = {
    "channel": channel,
    "raw_spectrum": raw_spectrum,           # ← From HAL read_roi()
    "wavelength": self.calibration_data.wavelengths,
    "timestamp": time.time(),
    "integration_time": self.calibration_data.integration_time,
    "num_scans": self.calibration_data.num_scans,
    "led_intensity": led_intensities.get(channel, 0),
    "s_pol_ref": self.calibration_data.s_pol_ref.get(channel),  # ← Reference
    "dark_s": self.calibration_data.dark_s.get(channel),        # ← Dark
    "wave_min_index": self.calibration_data.wave_min_index,
    "wave_max_index": self.calibration_data.wave_max_index,
}
```

**Processing**: Main app unpacks and calculates:

```python
raw_spectrum = data["raw_spectrum"]
dark_spectrum = data["dark_s"]
s_pol_ref = data["s_pol_ref"]

# Dark subtraction
dark_subtracted = raw_spectrum - dark_spectrum

# Transmission calculation
transmission_spectrum = dark_subtracted / s_pol_ref

# Peak extraction for sensorgram
peak_idx = np.argmin(spr_region)
wavelength = wavelength_axis[peak_idx]
```

---

## Design Principles

### 1. Hardware Abstraction
✅ **NEVER** call detector methods directly
✅ **ALWAYS** use HAL interface (`read_roi()`)
✅ **EXCEPTION**: Initialization code before ROI indices available

### 2. Single Source of Truth
✅ Spectrum averaging: HAL adapter ONLY
✅ Dark subtraction: Main app processing ONLY
✅ Transmission calculation: Main app processing ONLY

### 3. Detector Independence
✅ Application code never checks detector type
✅ HAL adapter handles backend-specific optimizations
✅ New detectors integrate via wrapper pattern

### 4. Separation of Concerns
✅ **Hardware Manager**: Hardware initialization, connection management
✅ **Data Acquisition Manager**: Timing, LED control, spectrum collection
✅ **Main App**: Data processing, transmission calculation
✅ **UI Coordinator**: Batch updates, prevent GUI freezing
✅ **Presenters**: Update plots with processed data

### 5. Data Flow Direction
```
Hardware → HAL → Acquisition → Processing → Coordination → Presentation → Display
```
**NEVER skip layers or access hardware directly**

---

## Code Organization

### Production Code HAL Compliance

✅ **Core Acquisition**: `affilabs/core/data_acquisition_manager.py`
✅ **Calibration**: `affilabs/utils/calibration_adaptive_integration.py`
✅ **Reference Processing**: `affilabs/utils/reference_baseline_processing.py`

### Legacy/Special Cases

⚠️ **Startup Calibration**: `affilabs/utils/startup_calibration.py`
- Uses direct `read_intensity()` for full spectrum
- Legitimate: Runs before ROI indices established
- Function: `acquire_raw_spectrum()` (lines 1118-1133)

### Test Code (Non-Production)
- `affilabs/test_*.py` - May use direct hardware calls for testing
- `tests/` directory - Test utilities

### Deprecated/Archive
- `affilabs/utils/led_calibration_nov20_working.py` - Legacy calibration
- `archive/` directory - Old implementations

---

## Architecture Validation Checklist

Use this checklist when reviewing code or adding new features:

### HAL Compliance
- [ ] All detector reads go through `read_roi()`
- [ ] No direct `usb.read_intensity()` calls (except initialization)
- [ ] Averaging handled by HAL `num_scans` parameter
- [ ] No manual averaging loops (`for i in range(num_scans)`)

### Data Flow
- [ ] Hardware → HAL → Acquisition → Processing → UI
- [ ] No layers skipped
- [ ] Data packages include calibration references
- [ ] Dark subtraction happens in processing layer

### Detector Independence
- [ ] No detector type checks in application code
- [ ] HAL adapter handles backend differences
- [ ] New detectors can be added via wrapper

### Code Organization
- [ ] Hardware code in `affilabs/core/hardware_manager.py`
- [ ] Acquisition code in `affilabs/core/data_acquisition_manager.py`
- [ ] Processing code in `main-simplified.py`
- [ ] Presentation code in `affilabs/presenters/`

---

## Future Considerations

### Potential Improvements
1. **HAL Extension**: Add `read_full_spectrum()` for initialization phase
2. **Async Acquisition**: Non-blocking spectrum collection
3. **Streaming Mode**: Continuous acquisition without queuing
4. **Hardware Buffering**: Utilize detector's internal buffers if available

### Detector Support Roadmap
- [ ] Thorlabs spectrometers
- [ ] Hamamatsu detectors
- [ ] Avantes spectrometers
- [ ] Generic USB spectrometer support

---

## Critical Files Reference

| Component | File | Key Methods |
|-----------|------|-------------|
| HAL Interface | `affilabs/utils/hal/interfaces.py` | Protocol definitions |
| HAL Adapter | `affilabs/utils/hal/adapters.py` | `read_roi()`, detector switching |
| Hardware Manager | `affilabs/core/hardware_manager.py` | `initialize_detector()` |
| Acquisition Manager | `affilabs/core/data_acquisition_manager.py` | `_acquire_raw_spectrum()`, `start_rankbatch()` |
| Calibration | `affilabs/utils/calibration_adaptive_integration.py` | S/P-mode optimization |
| Main Application | `main-simplified.py` | `_process_spectrum_data()` |
| UI Coordinator | `affilabs/presenters/ui_update_coordinator.py` | Batch updates |
| Spectroscopy Presenter | `affilabs/presenters/spectroscopy_presenter.py` | Plot updates |

---

## Glossary

**HAL**: Hardware Abstraction Layer - Interface isolating hardware specifics
**ROI**: Region of Interest - Wavelength range for SPR measurements (typically 580-720nm)
**num_scans**: Number of detector reads to average for noise reduction
**SeaBreeze**: Ocean Optics driver backend
**DLL Backend**: PhasePhotonics optimized driver using direct memory access
**Dark Spectrum**: Detector reading with LEDs off (noise baseline)
**S-pol Reference**: Calibration reference with S-polarized light
**Transmission**: Ratio of dark-subtracted signal to reference (dark_sub / s_pol_ref)
**Sensorgram**: Plot of SPR peak wavelength vs. time
**Integration Time**: Detector exposure duration (milliseconds)
**Batch Command**: Optimized LED control setting all channels atomically

---

## RECENT IMPROVEMENTS (December 2025)

### 1. Application State Management Refactoring

**Problem**: Scattered instance variables (50+) across `Application.__init__()`
**Solution**: Created `affilabs/app_state.py` with grouped dataclasses

```python
@dataclass
class ApplicationState:
    lifecycle: LifecycleState           # closing, device_config_initialized
    experiment: ExperimentState         # start_time, session_cycles_dir
    calibration: CalibrationState       # retry_count, completed
    channel: ChannelState               # selected_axis, selected_channel
    filtering: FilteringState           # filter_enabled, ema_state
    performance: PerformanceState       # spectrum_queue, counters
    ui: UIState                         # pending_graph_updates
    # ... and more
```

**Benefits**:
- ✅ Clear separation of concerns (lifecycle vs. experiment vs. calibration state)
- ✅ Type hints for IDE support
- ✅ Easy to serialize for state persistence
- ✅ Testable (can create mock states)
- ✅ Single source of truth for initialization

**Migration Status**: Data classes created, full migration pending

### 2. Signal-Based UI Architecture (CRITICAL FIX)

**Problem**: UI directly accessed hardware manager (layering violation)

```python
# BEFORE (VIOLATION):
self.main_window.hardware_manager = self.hardware_mgr  # Line 764
# UI calls hardware directly:
ctrl = self.hardware_manager.ctrl
ctrl.set_intensity('a', led_a)  # BREAKS LAYERING
```

**Solution**: Signal-based communication

```python
# AFTER (CLEAN ARCHITECTURE):
# UI emits signal with validated data
class AffilabsMainWindow(QMainWindow):
    apply_led_settings_requested = Signal(dict)

    def _apply_settings(self):
        settings = {'led_a': led_a, 'led_b': led_b, ...}
        self.apply_led_settings_requested.emit(settings)

# Application handles business logic
class Application:
    def _on_apply_led_settings(self, settings: dict):
        ctrl = self.hardware_mgr.ctrl
        for channel, value in settings.items():
            ctrl.set_intensity(channel, value)
```

**Benefits**:
- ✅ Clean layering: UI → Application → Hardware
- ✅ UI is testable (no hardware dependencies)
- ✅ Business logic centralized in Application
- ✅ Can add validation/authorization in Application layer

**Status**: IMPLEMENTED in main-simplified.py and affilabs_core_ui.py

### 3. Fail-Fast Coordinators (NO SILENT FAILURES)

**Problem**: Optional coordinators with scattered null checks

```python
# BEFORE (FRAGILE):
try:
    from affilabs.coordinators.ui_update_coordinator import AL_UIUpdateCoordinator
    COORDINATORS_AVAILABLE = True
except ImportError:
    COORDINATORS_AVAILABLE = False

if self.ui_updates:  # Scattered null checks everywhere
    self.ui_updates.update_status(...)
```

**Solution**: Required imports (fail-fast at startup)

```python
# AFTER (ROBUST):
from affilabs.coordinators.ui_update_coordinator import AL_UIUpdateCoordinator
# If missing, app crashes immediately with clear error message

# Later in code (no null checks needed):
self.ui_updates.update_status(...)  # ALWAYS AVAILABLE
```

**Benefits**:
- ✅ Fail-fast: Missing dependencies caught at startup
- ✅ No scattered null checks throughout code
- ✅ Predictable behavior across environments
- ✅ Easier debugging (import fails immediately with traceback)

**Status**: IMPLEMENTED in main-simplified.py

---

## Architecture Validation Checklist (UPDATED)

Before committing code, verify:

### HAL Compliance
- [ ] NO direct `usb.read_intensity()` calls (use `usb.read_roi()` instead)
- [ ] ALL spectrum averaging via HAL `num_scans` parameter
- [ ] Any `np.mean()` calls are for statistics ONLY, not spectrum averaging
- [ ] New detector support uses adapter pattern (see `OceanSpectrometerAdapter`)

### UI Layering
- [ ] UI components do NOT import hardware managers
- [ ] UI components do NOT import data acquisition managers
- [ ] ALL UI→Application communication via signals
- [ ] Business logic in Application layer, NOT in UI

### Initialization Architecture
- [ ] State grouped in `ApplicationState` dataclasses (no scattered variables)
- [ ] Imports are fail-fast (no silent optional imports)
- [ ] 9-phase initialization order respected (see main-simplified.py lines 370-430)
- [ ] No circular dependencies

### Data Flow
- [ ] Hardware → HAL → Manager → Application → UI (one direction only)
- [ ] UI signals → Application handlers → Manager methods
- [ ] Thread-safe queued connections for cross-thread signals

---

**Document Maintenance**: Update this document when making architectural changes
**Last Updated**: December 15, 2025
**Review Cycle**: Quarterly or when adding major features

---

## Related Documentation

- **INITIALIZATION_IMPROVEMENTS.md**: Detailed refactoring plan for Application state
- **affilabs/app_state.py**: Grouped state dataclasses implementation
- **CODE_CLEANUP_ANALYSIS.md**: Overall code quality improvements
- **EEPROM_DEVICE_CONFIG_SPEC.md**: Hardware configuration persistence
