# affilabs/ — Source Code Map

> This is the main application package for **Affilabs.core**.
> Claude Code reads this file automatically when working inside `affilabs/`.

## Package Structure by Architectural Layer

### Layer 1: Hardware (talks to physical devices)
```
hardware/
  device_interface.py    ← Abstract device interface
  device_manager.py      ← Manages device lifecycle
  spectrometer_adapter.py ← Spectrometer HAL adapter
  servo_adapter.py       ← Servo polarizer adapter
  optimized_led_controller.py ← LED system control
  mock_devices.py        ← Simulation mode devices

utils/hal/
  interfaces.py          ← HAL interface definitions
  controller_hal.py      ← Controller HAL implementation
  pump_hal.py            ← Pump HAL implementation
  adapters.py            ← HAL adapters

utils/controller.py      ← Low-level serial controller
utils/usb4000_wrapper.py ← Ocean Optics spectrometer driver
utils/phase_photonics_*.py ← Phase Photonics detector
```

### Layer 2: Domain Models (pure data, no dependencies)
```
domain/
  cycle.py               ← Cycle data model
  spectrum_data.py       ← Spectrum data container
  flag.py                ← Flag/marker system
  device_status.py       ← Device status model
  acquisition_config.py  ← Acquisition configuration
  editable_segment.py    ← Editable data segments
  calibration_data.py    ← Calibration data model
```

### Layer 3: Core Business Logic (processing engines)
```
core/
  data_acquisition_manager.py  ← Main acquisition engine
  spectrum_processor.py        ← Spectrum processing
  calibration_orchestrator.py  ← Calibration flow
  calibration_service.py       ← Calibration logic
  led_convergence.py           ← LED convergence control
  hardware_manager.py          ← Hardware coordination
  recording_manager.py         ← Data recording
  fmea_tracker.py              ← FMEA quality tracking
  ml_qc_intelligence.py        ← ML quality control

convergence/
  engine.py              ← Convergence algorithm engine
  estimators.py          ← Parameter estimators
  policies.py            ← Convergence policies
  scheduler.py           ← Convergence scheduling

utils/pipelines/         ← Peak-finding algorithms
  centroid_pipeline.py
  fourier_pipeline.py
  polynomial_pipeline.py
  hybrid_pipeline.py
  consensus_pipeline.py
  (+ more variants)

utils/spr_signal_processing.py ← SPR signal algorithms
```

### Layer 4: Application Services
```
services/
  excel_exporter.py      ← Excel export
  cloud_database_sync.py ← Cloud sync
  calibration_validator.py ← Calibration validation
  data_collector.py      ← Data collection
  spark/                 ← Spark AI assistant

managers/
  pump_manager.py        ← Pump state management
  queue_manager.py       ← Cycle queue
  export_manager.py      ← Export orchestration
  calibration_manager.py ← Calibration state
  flag_manager.py        ← Flag management
  device_config_manager.py ← Device config
  segment_manager.py     ← Segment management
```

### Layer 5: Coordinators (event wiring)
```
coordinators/
  acquisition_event_coordinator.py  ← Acquisition events
  hardware_event_coordinator.py     ← Hardware events
  ui_update_coordinator.py          ← UI update events
  ui_control_event_coordinator.py   ← UI control events
  injection_coordinator.py          ← Injection flow
  recording_event_coordinator.py    ← Recording events
  graph_event_coordinator.py        ← Graph events
  dialog_manager.py                 ← Dialog lifecycle
```

### Layer 6: Presentation (MVP)
```
presenters/
  sensogram_presenter.py     ← Sensogram view logic
  spectroscopy_presenter.py  ← Spectroscopy view logic
  queue_presenter.py         ← Queue view logic
  navigation_presenter.py    ← Navigation
  status_presenter.py        ← Status bar

viewmodels/
  calibration_viewmodel.py
  cycle_config_viewmodel.py
  device_status_viewmodel.py
  spectrum_viewmodel.py
```

### Layer 7: UI (display only — NO business logic here)
```
ui/                      ← Qt .ui files + generated ui_*.py
widgets/                 ← All PySide6 widget implementations
tabs/                    ← Analysis tab, edits tab
sidebar_tabs/            ← Sidebar panel builders (AL_*.py)
dialogs/                 ← Modal dialog implementations
```

## Key Files
- `affilabs_core_ui.py` — Main UI controller class
- `affilabs_sidebar.py` — Sidebar panel controller
- `app_config.py` — Application configuration
- `app_state.py` — Global application state

## Dependency Rules
- **Hardware** depends on nothing in affilabs
- **Domain** depends on nothing
- **Core** depends on Domain + Hardware
- **Services/Managers** depend on Core + Domain
- **Coordinators** depend on Services + Managers
- **Presenters** depend on Coordinators + Services
- **Widgets/UI** depend on Presenters (never on Core directly)
