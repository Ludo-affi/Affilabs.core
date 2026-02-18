# Backend Service Contracts

**Status**: Reference documentation for core service APIs
**Last Updated**: 2026-02-18

## Overview

This document defines the interfaces, input/output contracts, and lifecycle expectations for Affilabs.core backend services. Services are located in `affilabs/services/`, `affilabs/managers/`, and `affilabs/core/`.

---

## Service Tier Architecture

```
Layer 4: UI (widgets, dialogs, tabs)
    ↓ (Signals & callbacks)
Layer 3: Coordinators (cross-cutting orchestration)
    ↓ (Business logic dispatch)
Layer 2: Managers & Services (stateful business logic)
    ↓ (Lower-level services)
Layer 1: Core Services (hardware abstraction, data processing)
    ↓ (HAL, utilities)
Layer 0: Hardware (devices, serial comm)
```

---

## Core Services

### 1. DataAcquisitionManager

**Location**: `affilabs/core/data_acquisition_manager.py`

**Purpose**: Background acquisition thread; reads spectrometer data continuously.

**Lifecycle**:
```python
# Constructor
manager = DataAcquisitionManager(hardware_mgr, detector_profile)

# Start acquisition
manager.start_acquisition()

# Signals emitted during operation
manager.spectrum_acquired.connect(slot)      # Every spectrum (10-50 Hz)
manager.acquisition_started.connect(slot)
manager.acquisition_stopped.connect(slot)
manager.acquisition_error.connect(slot)      # Error message (str)

# Stop
manager.stop_acquisition()
manager.close()
```

**Signal Payloads**:
```python
# spectrum_acquired
{
    "time": 1.2345,                          # Elapsed seconds
    "channel_a": array([counts...]),         # Raw CCD array (np.ndarray)
    "channel_b": array([...]),
    "channel_c": array([...]),
    "channel_d": array([...]),
    "led_intensity": 85,                     # 0-255
    "integration_time": 5.4,                 # ms
    "epoch": 0,                              # Session number
}
```

**Key Methods**:
- `start_acquisition(led_intensity=85, integration_time=5.4)` → Start background loop
- `stop_acquisition()` → Stop thread cleanly
- `set_led_intensity(channel, value)` → Live LED control
- `set_integration_time(ms)` → Adjust exposure (respects min/max per detector)

**Thread Safety**:
- Runs on daemon thread; never blocks UI
- Emits signals via Qt.QueuedConnection
- All state changes guarded by locks

**Detector Integration**:
- Reads detector profile from disk (wavelength range, pixel count, min integration time)
- Enforces integration time limits: min=4.5ms (USB4000/Flame-T safety margin), max=100ms

---

### 2. RecordingManager

**Location**: `affilabs/managers/recording_manager.py`

**Purpose**: Collects acquisition data into memory; coordinates export and file I/O.

**Lifecycle**:
```python
manager = RecordingManager()

# Start recording
manager.start_recording(metadata={
    "user": "lucia",
    "device_sn": "FLMT09116",
    "experiment": "dose-response",
})

# Data accumulates automatically via signals
manager.recording_started.emit()

# Stop
manager.stop_recording()

# Export
manager.export_data(filepath, config)
manager.recording_stopped.emit()
```

**Data Accumulation**:
- Subscribes to `DataAcquisitionManager.spectrum_acquired` signal
- Buffers raw spectrum data, LED intensity, integration time
- Tags with elapsed time since recording start
- Stores in in-memory dataframes (pandas)

**Export Contract**:
```python
def export_data(
    filepath: Path,
    config: dict,  # {format, data_types, channels, precision, ...}
):
    """Export accumulated data to file."""
```

**Configuration**:
```python
{
    "format": "excel",               # or "csv", "json", "origin", "animl", etc.
    "data_types": {
        "raw": True,
        "processed": True,
        "cycles": True,
        "summary": True,
    },
    "channels": ["A", "B", "C", "D"],
    "precision": 4,
    "include_metadata": True,
    "include_events": True,
}
```

**Signals**:
- `recording_started` → Record session begins
- `recording_stopped` → Data collection halted
- `recording_paused` → Temporary pause (resume later)
- `export_complete(filepath)` → Export finished

---

### 3. CalibrationService

**Location**: `affilabs/core/calibration_service.py`

**Purpose**: Runs calibration workflows (startup, LED training, polarizer optimization, OEM).

**Lifecycle**:
```python
service = CalibrationService(hardware_mgr, data_acq_mgr)

# Run full system calibration
service.run_full_calibration(
    contact_time_s=300,
    led_target=1000,                  # Target count level
    progress_callback=on_progress,
)

# Signals
service.calibration_progress.emit(message, percent)  # 0-100
service.calibration_complete.emit(calibration_data)

# Or error
service.calibration_failed.emit(error_message)
```

**Calibration Workflows**:
1. **Startup Calibration** (1-2 min) — Auto-runs on Power On
   - Dark reference
   - S/P convergence
   - Reference generation
   - QC validation

2. **Full System Calibration** (3-5 min)
   - All steps from startup + validation checks

3. **Simple LED Calibration** (10-20 sec)
   - Assumes LED model exists; just re-optimizes intensity

4. **OEM Calibration** (10-15 min)
   - Servo calibration (find optimal positions)
   - LED model training
   - Full system calibration

5. **Polarizer Calibration** (2-5 min)
   - Sweep servo across 180°
   - Find optimal S/P positions

**Output Contract**:
```python
CalibrationData = {
    "status": "success" | "failed",
    "timestamp": datetime,
    "qc_report": {
        "signal_strength": "good" | "fair" | "poor",
        "led_convergence_time": float,
        "baseline_drift": float,
        "reference_quality": str,
        "warnings": list[str],
    },
    "reference_spectra": {
        "s_mode": array,
        "p_mode": array,
        "timestamp": datetime,
    },
    "servo_positions": {
        "s_mode": 45.2,                  # Degrees
        "p_mode": 90.1,
    },
}
```

---

### 4. SpectrumProcessor

**Location**: `affilabs/services/spectrum_processor.py`

**Purpose**: Converts raw spectra to transmission signals (dark subtraction, transmission calc, baseline).

**Contract**:
```python
processor = SpectrumProcessor(detector_profile)

# Process single spectrum
result = processor.process(
    raw_spectrum=array([counts...]),
    wavelengths=array([wavelengths...]),
    dark_reference=array([dark...]),
    led_intensity=85,
)

# Result
{
    "transmission": array([values...]),           # 0-100%
    "baseline": float,                            # Percentile baseline
    "peak_position": float,                       # Wavelength of dip
    "peak_height": float,                         # Depth of dip
    "signal_quality": "good" | "fair" | "poor",
    "saturation_pixels": int,                     # Count of saturated pixels
}
```

**Dark Subtraction**:
```
transmission = 100 * (raw_spectrum - dark_reference) / (reference - dark_reference)
```

**Transmission Baseline** (Savitzky-Golay + percentile):
- Smooth transmission with 51-point SG filter
- Extract baseline as 5th percentile

**Quality Checks**:
- LED detection (confirms light path works)
- Array alignment (detects sensor misalignment)
- Saturation warning (>500 pixels at 255 counts)

---

### 5. Pipeline Services (Centroid, Fourier, Polynomial, etc.)

**Location**: `affilabs/utils/pipelines/*.py`

**Purpose**: Find SPR dip position from transmission spectrum.

**Contract**:
```python
pipeline = CentroidPipeline()

result = pipeline.find_peak(
    transmission=array([values...]),      # 0-100%
    wavelengths=array([wavelengths...]),
    baseline=32.5,                        # Percentile baseline
)

# Result
{
    "peak_position": 750.23,              # nm
    "peak_height": 18.5,                  # %
    "peak_width": 2.1,                    # nm FWHM
    "confidence": 0.98,                   # 0-1
}
```

**Available Pipelines**:
1. **Centroid** — Center-of-mass (fast, standard)
2. **Fourier** — FFT-based peak finding (robust to noise)
3. **Polynomial** — Parabolic fit to dip (precise)
4. **Hybrid** — Consensus of multiple methods
5. **Consensus** — Weighted voting across all

---

### 6. ExcelExporter

**Location**: `affilabs/services/excel_exporter.py`

**Purpose**: Writes accumulated data to Excel workbook.

**Contract**:
```python
exporter = ExcelExporter()

exporter.export_to_excel(
    filepath=Path("/data/experiment.xlsx"),
    raw_data_rows=[
        {time: 0.0, channel_a: 12345, channel_b: 12400, ...},
        {time: 0.1, channel_a: 12346, ...},
        ...
    ],
    cycles=[
        {id: 1, type: "Baseline", start: 0, duration: 300, ...},
        {id: 2, type: "Concentration", start: 300, concentration: "100nM", ...},
    ],
    flags=[
        {type: "injection", time: 310, channel: "A", confidence: 0.95},
    ],
    events=[
        (0.0, "Recording started"),
        (310.0, "Injection flagged"),
    ],
    analysis_results=[
        {cycle: 2, channel: "A", peak_position: 750.2, peak_height: 15.3, ...},
    ],
    metadata={
        "user": "lucia",
        "device": "FLMT09116",
        "date": "2026-02-18",
        "experiment": "dose-response",
    },
    recording_start_time=1708286400.0,
)
```

**Output Sheets**:
- Raw Data (time, per-channel counts)
- Channel Data (time, per-channel transmission)
- Cycles (metadata and boundaries)
- Flags (injection, wash events)
- Events (system timeline)
- Analysis (measurement results)
- Metadata (experiment info)

**Performance**:
- Handles millions of data points
- Uses Pandas ExcelWriter for streaming
- Memory efficient (chunks large files)

---

### 7. HardwareManager

**Location**: `affilabs/managers/device_manager.py`

**Purpose**: Detects connected devices and instantiates hardware HAL layers.

**Contract**:
```python
hw_mgr = HardwareManager()

# Scan for devices
devices = hw_mgr.scan_devices()  # List of detected serial/USB devices

# Connect to specific device
hw_mgr.connect_device(device_sn="FLMT09116")

# Get detector instance
detector = hw_mgr.get_detector()  # Returns Ocean Optics, Phase Photonics, or None

# Get pump instance
pump = hw_mgr.get_pump()  # Returns AffiPump, P4PROPLUS, or None

# Check connection
is_connected = hw_mgr.is_connected()

# Signals
hw_mgr.device_connected.emit(device_info)
hw_mgr.device_disconnected.emit()
hw_mgr.device_error.emit(error_message)

# Cleanup
hw_mgr.close()
```

**Device Info Contract**:
```python
{
    "type": "spectrometer",          # or "pump", "controller"
    "model": "Ocean Optics Flame-T",
    "serial_number": "FLMT09116",
    "port": "COM3",                  # or /dev/ttyUSB0
    "firmware_version": "2.4",
    "detector_profile": {...},       # From detector_profiles/*.json
}
```

---

### 8. ConvergenceEngine

**Location**: `affilabs/convergence/engine.py`

**Purpose**: Adjusts LED intensity and integration time to target signal level.

**Contract**:
```python
engine = ConvergenceEngine(policies=[...])

result = engine.converge(
    current_spectrum=array([counts...]),
    target_level=50000,              # Desired peak counts
    max_iterations=20,
    timeout_s=60,
)

# Result
{
    "converged": True | False,
    "final_led_intensity": 120,      # 0-255
    "final_integration_time": 5.4,   # ms
    "iterations": 8,
    "execution_time_s": 3.2,
    "saturation_pixels": 0,
    "warnings": [],
}
```

**Policies**:
- **SaturationPolicy** — Back off if saturating
- **LEDPolicy** — Prefer LED intensity adjustment first
- **IntegrationPolicy** — Adjust exposure as fallback
- **TimeoutPolicy** — Abort if converging too slowly

**Safety**:
- Never exceeds detector min/max limits
- Respects LED power envelope
- Aborts if saturation detected and can't escape

---

### 9. UserProfileManager

**Location**: `affilabs/services/user_profile_manager.py`

**Purpose**: Manages multi-user profiles, preferences, and session state.

**Contract**:
```python
mgr = UserProfileManager()

# Get all users
users = mgr.get_all_users()  # List of user objects

# Create user
mgr.create_user(
    name="lucia",
    email="lucia@affiniteinstruments.com",
    role="scientist",
)

# Set active user
mgr.set_active_user("lucia")

# Get current settings
settings = mgr.get_user_settings("lucia")  # Dict of preferences

# Update settings
mgr.update_user_settings("lucia", {
    "default_contact_time": 300,
    "preferred_channels": ["A", "B"],
})

# Track session
mgr.record_session("lucia", "experiment_XYZ", duration_s=1800)
```

**User Object**:
```python
{
    "id": "lucia",
    "name": "Lucia",
    "email": "lucia@example.com",
    "role": "scientist" | "admin" | "guest",
    "created_date": datetime,
    "last_used": datetime,
    "settings": {
        "default_contact_time": 300,
        "preferred_channels": ["A", "B", "C", "D"],
        "export_format": "excel",
        "theme": "light" | "dark",
    },
    "sessions": [
        {experiment: "dose-response", duration: 1800, date: datetime},
    ],
}
```

---

## Manager Classes

### ExportManager

**Location**: `affilabs/managers/export_manager.py`

**Purpose**: Orchestrates export UI interactions and config extraction.

**Methods**:
- `get_export_config()` → Dict of current UI selections
- `on_export_data()` → Emit `export_requested` signal
- `on_quick_csv_preset()` → Preset: CSV all channels
- `on_analysis_preset()` → Preset: Excel processed data
- `on_publication_preset()` → Preset: Excel high precision

---

### CycleManager

**Location**: `affilabs/core/cycle_coordinator.py`

**Purpose**: Manages method queue and cycle execution state.

**Methods**:
- `push_cycle(cycle)` → Add to queue
- `start_cycle_run()` → Begin execution
- `next_cycle()` → Advance to next (skip current early)
- `pause_cycle()` → Pause execution
- `resume_cycle()` → Resume from pause
- `abort_run()` → Stop all cycles

**Signals**:
- `cycle_started(cycle)` → Current cycle began
- `cycle_completed(cycle)` → Cycle data collection finished
- `run_completed()` → All queued cycles done

---

### QCReportManager

**Location**: `affilabs/managers/qc_report_manager.py`

**Purpose**: Generates and validates QC (quality control) reports post-calibration.

**Methods**:
- `generate_qc_report(calibration_data)` → Analyze results
- `validate_results()` → Check thresholds
- `get_warnings()` → List issues found

**Output**:
```python
{
    "status": "pass" | "fail",
    "timestamp": datetime,
    "signal_strength": "good" | "fair" | "poor",
    "led_convergence_time": float,
    "baseline_drift_percent": float,
    "reference_quality": str,
    "warnings": [
        "Low signal on Channel B (48000 counts, target 50000)",
        "Baseline drift 2.3% (threshold 2.0%)",
    ],
    "recommendations": [
        "Check prism cleanliness",
        "Increase ambient light filtering",
    ],
}
```

---

## Coordinator Classes

Coordinators handle cross-cutting concerns (events, state, multiple services):

### RecordingEventCoordinator

**Location**: `affilabs/coordinators/recording_event_coordinator.py`

**Purpose**: Coordinates recording lifecycle and data collection signals.

**Responsibilities**:
- Subscribe to `DataAcquisitionManager.spectrum_acquired`
- Relay to `RecordingManager` for buffering
- Update UI in real-time
- Emit recording progress signals

### AcquisitionEventCoordinator

**Location**: `affilabs/coordinators/acquisition_event_coordinator.py`

**Purpose**: Manages live spectra updates and visualization.

**Responsibilities**:
- Receive spectrum updates
- Dispatch to analysis pipelines
- Update live graphs
- Handle errors gracefully

### CalibrationCoordinator

**Purpose**: Orchestrates multi-phase calibration workflows.

**Responsibilities**:
- Queue calibration steps
- Monitor progress
- Emit progress signals with percent complete
- Handle retries on failure

---

## Error Handling Conventions

All services follow these error patterns:

```python
try:
    result = service.operation()
except HardwareError as e:
    # Device communication failed
    logger.error(f"Hardware error: {e}")
    service.error_signal.emit(str(e))
except ValueError as e:
    # Invalid input
    logger.warning(f"Invalid input: {e}")
except Exception as e:
    # Unexpected error
    logger.exception(f"Unexpected error: {e}")
    service.error_signal.emit(f"Internal error: {e}")
finally:
    # Cleanup
    service.cleanup()
```

**Key Signals**:
- `*_error(message)` — Error occurred
- `*_warning(message)` — Non-critical issue
- `*_progress(message, percent)` — Operation in progress

---

## Testing Strategy

### Unit Tests
- Test services in isolation
- Mock hardware layer
- Test input/output contracts

### Integration Tests
- Wire services together
- Test signal/callback flows
- Verify data contracts

### End-to-End Tests
- Full recording → export workflow
- Calibration → data collection → export
- Error recovery scenarios

---

## References

- **Service layer**: `affilabs/services/`, `affilabs/managers/`, `affilabs/core/`
- **Coordinator layer**: `affilabs/coordinators/`
- **Hardware layer**: `affilabs/hardware/`, `affilabs/utils/hal/`
- **Pipeline layer**: `affilabs/utils/pipelines/`
- **Main entry point**: `main.py` (signal wiring)

---

## Active Notes

**For v2.0.6+**:
1. Document all remaining manager classes (SegmentManager, CursorManager, etc.)
2. Formalize service lifecycle (init → start → stop → close)
3. Add service registry/factory pattern for cleaner instantiation
4. Define transactional contracts (atomicity, rollback behavior)
5. Create service mocking utilities for UI testing
