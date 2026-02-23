# Affilabs.core v2.0.5 beta

> **Official software name: Affilabs.core** (the folder name "ezControl-AI" is a legacy workspace alias — always refer to this project as **Affilabs.core**)

## How To Work With Me
- **Be direct.** No filler, no preamble, no "Great question!". Answer the thing.
- **Be concise.** Shortest correct answer wins. Code > prose. Tables > paragraphs.
- **Ask when unclear.** Don't guess silently — ask one pointed question. But if the answer is inferrable from the codebase, go find it instead of asking.
- **Take educated guesses with evidence.** Read the code, check patterns, then act. Document what you learned in the Active Context section if it's reusable.
- **No safety hedging.** Don't add "you might want to consider..." or "it's generally recommended to...". State what should be done and do it.
- **No summaries of what you just did** unless I ask. I can see the diffs.
- **Grep before reading.** This codebase has 25+ files over 1000 lines. Never read a large file top-to-bottom — search for what you need.
- **Fail fast, explain why.** If something won't work, say so immediately with the reason. Don't attempt a workaround without flagging the root issue.
- **Build the knowledge base.** When you discover a non-obvious pattern or gotcha, add it to the Key Gotchas section or Active Context so future sessions benefit.

## What This Is
SPR (Surface Plasmon Resonance) instrument control desktop application.
Controls optical detectors (spectrometers), syringe pumps, servo polarizers, and multi-LED systems via serial/USB.
Built with **PySide6** (Qt). Runs on Windows.

## SPR Measurement Technology

### Method: Lensless Spectral SPR — Kretschmann Configuration
This is **not** conventional angular SPR (like Biacore). Key differences:

| Property | This system | Angular SPR (Biacore) |
|----------|------------|----------------------|
| Interrogation | **Wavelength** (spectral) | Angle |
| Optics | **Lensless** — no focusing optics | Lens-based |
| Configuration | **Kretschmann** prism | Kretschmann prism |
| Signal unit | **nm** (resonance wavelength) | RU (resonance units) |
| Dip width | **Broad** (~20–40 nm FWHM) | Narrow (angular) |
| Output | Sensorgram: wavelength vs time | Sensorgram: RU vs time |

### Optical Path
```
4× White LEDs (channels A B C D) — fired SEQUENTIALLY, never simultaneously
  → Servo polarizer (rotates between P-pol and S-pol)
  → Prism (glass) with gold-coated sensor chip
  → Evanescent field at gold/buffer interface (SPR coupling)
  → Fiber optic
  → Spectrometer (Ocean Optics Flame-T or USB4000)
```

**LED system details:**
- All 4 LEDs are **identical white-light sources** — no color differences between channels
- Spectral range: **560–720 nm** (the SPR-active window for gold at this geometry)
- Channels are **time-multiplexed**: controller fires A, reads spectrum, fires B, reads spectrum, etc.
- There is **no simultaneous multi-channel acquisition** — each frame captures one channel at a time
- One full acquisition cycle (all 4 channels × P-pol + S-pol) takes ~1–2 seconds depending on integration time

### Signal Chain (Raw → Sensorgram)
```
Raw counts (P-pol + S-pol per LED channel, acquired sequentially)
  → Dark subtraction (SpectrumPreprocessor)
  → P/S ratio × LED boost correction → Transmission spectrum (0–100%)
  → Baseline correction (percentile / polynomial / off_spr / none)
  → Savitzky-Golay smoothing
  → Peak/dip finder (centroid / fourier / polynomial / hybrid / consensus)
  → Resonance wavelength (nm)  ← sensorgram Y-axis value
```

### Critical Physics for Algorithm Developers
1. **Signal polarity — RED SHIFT on binding**: When analyte binds the sensor, the resonance wavelength **INCREASES** (moves to longer wavelength). Injection detection must look for a **RISE** in wavelength. ΔSPR values are therefore **positive** on binding.
2. **S-polarization is the reference**: S-pol light does not couple to surface plasmons. P/S ratio cancels LED intensity drift, giving a stable transmission baseline.
3. **Broad dip**: The spectral SPR dip spans ~20–40 nm FWHM. Simple `argmin()` is noisy — hence multiple peak-finding pipelines (centroid, fourier, polynomial, consensus) exist to robustly track the broad minimum.
4. **Transmission dip, not peak**: The SPR feature is a **minimum** in transmission (dip), not a maximum. Pipelines operate on the inverted spectrum or explicitly search for the minimum.
5. **4 channels = 4 independent sensors, sequentially read**: Each LED (A, B, C, D) illuminates a separate region of the sensor chip. LEDs fire one at a time — never simultaneously. Channels are processed independently with independent calibration references.
6. **Calibration = S-pol reference acquisition**: The S-pol spectrum captured at calibration time serves as the reference for all subsequent P/S ratio calculations. Re-calibration resets the baseline.

## Entry Point
- `main.py` — Application entry point (~10k lines, 9-phase initialization)
- Run: `.venv/Scripts/python.exe main.py`

## Architecture (4-Layer)
```
Layer 1: Hardware      → affilabs/hardware/, affilabs/utils/hal/, AffiPump/
Layer 2: Business      → affilabs/core/, affilabs/managers/, affilabs/services/
Layer 3: Orchestration → affilabs/coordinators/
Layer 4: UI            → affilabs/widgets/, affilabs/presenters/, affilabs/ui/
```

## Workspace Layout
```
Root (essential files only):
  main.py              ← App entry point
  run_app.py           ← Alternate launcher
  version.py / VERSION ← Version info
  pyproject.toml       ← Dependencies (PDM)
  CLAUDE.md            ← This file (Claude Code reads automatically)
  .claudeignore        ← Files Claude Code should skip
  README.md            ← Project readme

Source code (VISIBLE to Claude):
  affilabs/            ← THE application package (see affilabs/CLAUDE.md)
  AffiPump/            ← Pump controller library (Tecan/Cavro protocol)

Runtime configuration (VISIBLE to Claude):
  config/              ← App configuration files
  settings/            ← User settings (settings.py = master constants)
  detector_profiles/   ← Detector-specific profiles (Flame-T, USB4000)

Ignored by Claude Code (use --no-ignore to access):
  scripts/             ← Operational scripts (calibration, recovery, provisioning)
  tools/               ← Analysis, diagnostics, ML training, cleanup
  standalone_tools/    ← Standalone GUI utility tools
  tests/               ← Test suite (47 files)
  calibrations/        ← Calibration data + scripts (servo, LED, per-device)
  docs/                ← Project documentation (6 subdirs)
  _scratch/            ← Archived one-off scripts
  _data/               ← Data outputs, logs, simulation data
  _build/              ← Build artifacts, installers, dist
  .venv/               ← Python virtual environment
```

## Key External Dependencies
- PySide6 (Qt GUI)
- pyqtgraph (real-time plotting)
- numpy, scipy, pandas (data processing)
- openpyxl (Excel export)
- pyserial (serial communication)
- pump-controller, oceandirect (AffiLabs hardware packages from GitLab)

## Build & Packaging
- `_build/Affilabs-Core.spec` — PyInstaller spec
- `_build/installer.nsi` — NSIS installer script
- `pyproject.toml` — PDM project config

## Code Style
- Python 3.12+
- Type hints used throughout
- MVP pattern: presenters coordinate between widgets and services
- Event coordinators handle cross-cutting concerns
- Hardware abstraction via HAL interfaces
- Domain models are plain dataclasses

### Button Icons — SVG Rule
**All buttons with icons must use SVG, not emoji or PNG.**
- Store SVGs in `affilabs/ui/img/*.svg` (24×24 viewBox, `fill="none"` with explicit stroke/fill on paths)
- Load via `get_affilabs_resource("ui/img/foo.svg")` → `QIcon(str(path))` (from `affilabs.utils.resource_path`)
- Set size with `button.setIconSize(QSize(16, 16))` (use 14px for compact/inline buttons)
- Emoji in button text (`"📦 Export"`) are acceptable as a **temporary placeholder only** — replace with SVG before release
- `_create_svg_icon(svg_string, size)` in `method_builder_dialog.py` can generate `QIcon` from inline SVG markup (no file needed for one-off icons)
- For two-state buttons (checkable), render the SVG twice with different `currentColor` substitutions via `QSvgRenderer` → `QPainter` → `QIcon.addPixmap(state=Off/On)` — see `navigation_presenter._create_spark_toggle_button` as the canonical example
- **Canonical icons:** `sparq_icon.svg` = Sparq AI robot (used in nav bar + sidebar footer); always load from file, never duplicate inline

## FRS Documentation Map — Read Before Grepping

> `docs/` is excluded from Claude Code search, but **read_file always works**. Each entry below is a verified, condensed spec — faster than grepping 1000+ line Python files.

| Working on... | Read this first | Source file(s) |
|---------------|----------------|----------------|
| UX testing, Sparq IQ scoring, workflow readiness | [UX_WORKFLOW_TEST_PROTOCOL.md](docs/user_guides/UX_WORKFLOW_TEST_PROTOCOL.md) | `docs/ui/UX_USER_JOURNEY.md`, `product_requirements/SPARQ_PRD.md` |
| EditsTab — table, columns, filtering | [EDITS_TABLE_FRS.md](docs/features/EDITS_TABLE_FRS.md) | `affilabs/tabs/edits/_table_manager.py` |
| EditsTab — layout, widget refs | [EDITS_UI_BUILDERS_FRS.md](docs/features/EDITS_UI_BUILDERS_FRS.md) | `affilabs/tabs/edits/_ui_builders.py` |
| EditsTab — export, Save as Method | [EDITS_EXPORT_FRS.md](docs/features/EDITS_EXPORT_FRS.md) | `affilabs/tabs/edits/_export_mixin.py` |
| EditsTab — alignment, delta SPR cursors | [EDITS_ALIGNMENT_DELTA_SPR_FRS.md](docs/features/EDITS_ALIGNMENT_DELTA_SPR_FRS.md) | `affilabs/tabs/edits/_interaction_mixin.py` |
| EditsTab — binding plot, Kd fitting | [EDITS_BINDING_PLOT_FRS.md](docs/features/EDITS_BINDING_PLOT_FRS.md) | `affilabs/tabs/edits/_binding_plot_mixin.py` |
| EditsTab — cycle display, graph rendering | [EDITS_CYCLE_DISPLAY_FRS.md](docs/features/EDITS_CYCLE_DISPLAY_FRS.md) | `main.py` (`_display_cycle_in_edits*`) |
| EditsTab — data loading utilities | [EDITS_DATA_LOADING_FRS.md](docs/features/EDITS_DATA_LOADING_FRS.md) | `affilabs/tabs/edits/_data_utils.py` |
| Recording, auto-save, Excel export | [RECORDING_MANAGER_FRS.md](docs/features/RECORDING_MANAGER_FRS.md) | `affilabs/managers/recording_manager.py` |
| Excel chart generation | [EXCEL_CHART_BUILDER_FRS.md](docs/features/EXCEL_CHART_BUILDER_FRS.md) | `affilabs/services/excel_exporter.py` |
| Controller HAL, servo commands, adapters | [CONTROLLER_HAL_FRS.md](docs/features/CONTROLLER_HAL_FRS.md) | `affilabs/utils/hal/controller_hal.py` |
| Pump HAL, AffiPump, Cavro protocol | [PUMP_HAL_FRS.md](docs/features/PUMP_HAL_FRS.md) | `affilabs/utils/hal/pump_hal.py` |
| P4PRO fluidic system — KC1/KC2, 6-port loop, 3-way valves, channel mapping | [P4PRO_FLUIDIC_ARCHITECTURE.md](docs/hardware/P4PRO_FLUIDIC_ARCHITECTURE.md) | `affilabs/coordinators/injection_coordinator.py` |
| Hardware scanning, USB connect flow | [HARDWARE_SCANNING_FRS.md](docs/features/HARDWARE_SCANNING_FRS.md) | `affilabs/core/hardware_manager.py` |
| Injection flags, AutoMarker, contact timer | [FLAGGING_SYSTEM_GUIDE.md](docs/features/FLAGGING_SYSTEM_GUIDE.md) | `affilabs/managers/flag_manager.py` |
| Calibration flow, servo auto-cal | [CALIBRATION_ORCHESTRATOR_FRS.md](docs/calibration/CALIBRATION_ORCHESTRATOR_FRS.md) | `affilabs/core/calibration_orchestrator.py` |
| Signal quality, IQ levels, wavelength zones | [SENSOR_IQ_SYSTEM.md](docs/features/SENSOR_IQ_SYSTEM.md) | `affilabs/utils/sensor_iq.py` |
| Cycle templates, queue presets | [METHOD_PRESETS_SYSTEM.md](docs/features/METHOD_PRESETS_SYSTEM.md) | `affilabs/services/cycle_template_storage.py` |
| Method Builder UI redesign (3-zone layout, template gallery, Sparq bar) | [METHOD_BUILDER_REDESIGN_FRS.md](docs/features/METHOD_BUILDER_REDESIGN_FRS.md) | `affilabs/widgets/method_builder_dialog.py` |
| Contact Monitor panel, per-channel contact timers, binding symbols | [MICROFLUIDIC_CHANNELS_PANEL_FRS.md](docs/features/MICROFLUIDIC_CHANNELS_PANEL_FRS.md) | `affilabs/widgets/injection_action_bar.py` |
| Compression Assistant — guided chip compression, gauge, QC leak check | [COMPRESSION_ASSISTANT_FRS.md](docs/features/COMPRESSION_ASSISTANT_FRS.md) | `standalone_tools/compression_trainer_ui.py` |
| Timeline events, CycleMarker, stream API | [TIMELINE_QUICK_START.md](docs/architecture/TIMELINE_QUICK_START.md) | `affilabs/domain/timeline.py`, `affilabs/core/recording_manager.py`, `affilabs/managers/flag_manager.py`, `mixins/_cycle_mixin.py` |
| Timeline Phase 5+ roadmap, proposed improvements | [TIMELINE_ROADMAP.md](docs/future_plans/TIMELINE_ROADMAP.md) | `affilabs/domain/timeline.py` |

**Rule:** If the task touches a subsystem listed above, read the FRS doc first. Only open the source file if the doc doesn't answer the question.

---

## Common Tasks
- **Add a new widget**: Create in `affilabs/widgets/`, wire through relevant coordinator
- **Add a new pipeline**: Add to `affilabs/utils/pipelines/`
- **Modify hardware comm**: Work in `affilabs/hardware/` or `affilabs/utils/hal/`
- **Change export format**: Work in `affilabs/services/excel_exporter.py` and `affilabs/utils/export_*.py`
- **Edit UI layout**: Modify `.ui` files in `affilabs/ui/`, recompile with `compile_ui.py`

## Data Flow: Spectrometer → UI
```
1. DataAcquisitionManager (background thread)
   → Sets LED intensity, reads raw spectrum from detector
   → Emits spectrum_acquired Signal(dict) with raw numpy array

2. main.py._on_spectrum_acquired (Qt.QueuedConnection, thread-safe)
   → Tags with elapsed time + session epoch
   → Puts into _spectrum_queue (non-blocking)
   → Processing worker thread drains queue

3. SpectrumProcessor
   → Dark subtraction (SpectrumPreprocessor)
   → Transmission calculation (TransmissionProcessor: Savitzky-Golay + percentile baseline)
   → Quality validation (LED detection, array alignment)

4. Pipeline (centroid/fourier/polynomial/hybrid/consensus)
   → Finds SPR dip position → wavelength value

5. AL_UIUpdateCoordinator
   → Batches updates on timer → dispatches to SensogramPresenter + SpectroscopyPresenter
   → Presenters update pyqtgraph widgets
```

## Key Signals (Qt)
| Owner | Signal | Payload | Purpose |
|-------|--------|---------|---------|
| DataAcquisitionManager | `spectrum_acquired` | dict | Raw spectrum from detector |
| DataAcquisitionManager | `acquisition_started/stopped` | — | Lifecycle events |
| HardwareManager | `hardware_connected/disconnected` | — | Device state |
| CalibrationService | `calibration_complete` | CalibrationData | Calibration done |
| CalibrationService | `calibration_progress` | (str, int) | Message + percent |
| RecordingManager | `recording_started/stopped` | str/— | File recording |
| InjectionCoordinator | `injection_flag_requested` | (str, float, float) | channel, time, confidence |

All cross-thread signals use `Qt.QueuedConnection` explicitly (wired in main.py ~L1300).

## Threading Model
- **`threading.Thread` (dominant)** — All worker threads are `daemon=True`
  - Acquisition loop, hardware connection, calibration flows, injection ops, USB scanning
- **`QThread` (rare)** — Only pump priming worker + pump timing calibration dialog
- **`gc.disable()`** is called in `data_acquisition_manager.py` to prevent GC pauses during acquisition
- Cross-thread data goes through Qt Signals, never shared mutable state

## Settings & Config (3 sources)
| Source | Location | Purpose |
|--------|----------|---------|
| **settings.py** | `settings/settings.py` (606 lines) | Master constants: timing, signal processing, calibration thresholds, feature flags |
| **app_config.py** | `affilabs/app_config.py` (100 lines) | Runtime limits: max points, update intervals, quality thresholds |
| **Detector profiles** | `detector_profiles/*.json` | Hardware-specific overrides (pixel count, wavelength range, integration limits) |

`settings/__init__.py` does `from .settings import *` — importing bare `from settings import X` works because root is on `sys.path`.
Detector profiles override deprecated constants in settings.py at runtime via `get_current_detector_profile()`.

## Device Databases (2 systems — both required going forward)

> **This is the canonical approach for tracking all shipped and in-house devices.** Any new device must be added to both databases.

| Database | Path | Format | Purpose |
|----------|------|--------|---------|
| **device_registry.json** | `_data/calibration_data/device_registry.json` | JSON | Customer + shipping identity (who owns each unit, invoice, country) |
| **device_history.db** | `tools/ml_training/device_history.db` | SQLite | Per-device calibration performance history for ML training (FWHM, SNR, convergence stats) |

### device_registry.json (identity/CRM)
- One entry per serial, keyed by serial string (e.g. `"FLMT09788"`)
- Fields: `customer.name`, `customer.country`, `order.invoice`, `shipped_date`, `calibration_files[]`, `ml_training_include`
- Add new device by inserting a new key into the `"devices"` object
- `ml_training_include: false` to exclude prototypes or returned units

### device_history.db (ML training)
- Managed by `DeviceHistoryDatabase` in `tools/ml_training/device_history.py`
- Records added via `record_calibration_to_database()` in `tools/ml_training/record_calibration_result.py`
- Keyed by `detector_serial` (integer — numeric portion of serial, e.g. `9788` for `FLMT09788`)
- Schema: one row per calibration run — `success`, `s_mode_iterations`, `p_mode_iterations`, `final_fwhm_avg`, `final_snr_avg`, etc.
- Used by `train_convergence_predictor.py` to add 17 per-device history features to the ML model
- Run `tools/ml_training/train_all_models.py` to rebuild all models (includes device history export step)

### Workflow when provisioning a new device
1. Run OEM calibration: `.venv\Scripts\python.exe scripts/provisioning/oem_calibrate.py`
   - **Phase 1a — Servo calibration:** auto-detects S and P polarizer positions → writes to `affilabs/config/devices/{SERIAL}/device_config.json` (S/P PWM values). EEPROM write may fail on some units — safe to ignore, app reads from JSON on every connect.
   - **Phase 1b — LED model training:** measures LED intensity response across 3 integration times at 5 intensity levels each. Automatically detects ultra-sensitive devices (saturate at I=60 with 10ms) and switches to shorter times `[5, 10, 15]ms` + lower intensities `[10, 20, 30, 40, 60]`. Writes `led_model.json`.
   - **Phase 2 — Startup calibration:** LED convergence + S-pol reference capture → writes `startup_config.json`. Uses the same `run_startup_calibration()` function as the main app (no difference in behavior).
   - Auto-saves full record to `_data/calibration_data/device_SERIAL_DATE.json`
   - Auto-adds serial to `_data/calibration_data/device_registry.json` (status: "in-house")
2. Open `device_registry.json`, fill in customer name/country/invoice for the serial
3. Retrain models if enough new devices: `python tools/ml_training/train_all_models.py`

**CLI flags:** `--skip-oem-model` (LED model already exists, skip Phase 1), `--skip-phase2` (skip startup cal), `--serial OVERRIDE` (force serial instead of auto-detect)

> **Standalone vs main app:** Both call the same functions — `run_oem_model_training_workflow()` and `run_startup_calibration()` from `affilabs/core/`. The standalone script is a CLI wrapper with no Qt UI. Any fix to `oem_model_training.py` applies to both automatically.

## Naming Conventions
| Component | Pattern | Example |
|-----------|---------|---------|
| Sidebar tabs | `AL_*_builder.py` | `AL_flow_builder.py` |
| Widgets | descriptive_noun.py | `cycle_controls_widget.py` |
| Dialogs | `*_dialog.py` | `calibration_qc_dialog.py` |
| Presenters | `*_presenter.py` | `sensogram_presenter.py` |
| Coordinators | `*_event_coordinator.py` | `acquisition_event_coordinator.py` |
| ViewModels | `*_viewmodel.py` | `calibration_viewmodel.py` |
| HAL | `*_hal.py` | `pump_hal.py` |
| Pipelines | `*_pipeline.py` | `centroid_pipeline.py` |

## Key Gotchas
1. **Check FRS docs before grepping source:** `docs/features/` has 15+ verified FRS docs. Reading a 300-line FRS doc is faster than grepping a 3000-line Python file. See **FRS Documentation Map** above.
2. **Large files — use grep, never read whole:**
   - `main.py` (3.4k lines after mixin extraction), `affilabs_core_ui.py` (3.7k after mixin extraction), `controller.py` (3.6k), `datawindow.py` (2.8k)
   - 25+ files exceed 1000 lines in `affilabs/`
2. **Never edit generated files:** `affilabs/ui/ui_*.py` and `affilabs/ui/ai_rc.py` are auto-generated from `.ui` files
3. **Mixin pattern for large classes:**
   - `main.py` uses `PumpMixin` (1.9k) + `FlagMixin` (346) + `CalibrationMixin` (699) + `CycleMixin` (618) in `mixins/`
   - `affilabs_core_ui.py` uses `PanelBuilderMixin` (1.2k) + `DeviceStatusMixin` (711) + `TimerMixin` (529) + `EditsCycleMixin` (1.7k) + `SettingsMixin` (369) in `affilabs/ui_mixins/`
   - Same pattern as `EditsTab` — extract method groups to mixin files for maintainability
4. **`ApplicationState` migration is incomplete:** `app_state.py` defines the target dataclass-based state, but `main.py` still uses scattered `self.*` instance variables. Both coexist.
5. **`from settings import *`** imports 100+ constants into caller namespace — this is intentional, not a bug
6. **`spectrum_acquired` emits RAW data only** — processing happens in a separate subscriber, not in the DAQ
7. **4 LED channels (a, b, c, d)** — each operates independently. Channel index mapping in `CHANNEL_INDICES`
8. **Two acquisition modes:** `CYCLE_SYNC` (V2.4 firmware, default) vs `EVENT_RANK` (fallback) — toggled by `USE_CYCLE_SYNC` flag
9. **Supported detectors:** Ocean Optics Flame-T (primary) and USB4000 — profiles in `detector_profiles/`
10. **Phantom USB devices on Windows:** When Ocean Optics detectors are unplugged/replugged, Windows leaves "phantom" device entries in Device Manager (Status: Unknown). **Don't try to clean them up** — instead, implement a **handshake test** in `usb4000_wrapper.py` that tries to read device properties (wavelengths, serial, etc.) on each device in `list_devices()`. Only the real device will respond. This avoids the need for manual registry cleanup. See **usb4000_wrapper.py:360-385** for implementation.
11. **Mid-run cycle append:** `QueueManager.add_cycle()` is allowed during execution (lock does NOT block adds). When `_lock` is True and `_original_method` is non-empty, the new cycle is deep-copied into `_original_method` as well as `_queue`, so the execution loop (`_original_method[_method_progress:]`) will pick it up after all currently-pending cycles finish. The `QueueSummaryWidget` in locked/execution-mode shows `_original_method`, so the appended cycle will appear in the table immediately. Deletion and reordering remain blocked while running.
12. **`_AlignChannelProxy` — silent crash risk in EditsTab:** The alignment channel selector in EditsTab (`affilabs/tabs/edits/_ui_builders.py`) was changed from a `QComboBox` to `_AlignChannelProxy` (a thin wrapper over the All/A/B/C/D buttons). `_on_cycle_selected_in_table()` in `_edits_cycle_mixin.py` calls `.blockSignals()` and `.setCurrentText()` on it — these methods **must exist** on the proxy or the entire function silently fails (wrapped in `try/except`) and the graph stays blank. The proxy's `_btn_map` dict must also be wired to `_alignment_ch_btns` after button creation so `setCurrentText()` can sync button visuals.

## Import Conventions
- **Absolute imports** from `affilabs.*` are the standard: `from affilabs.core.spectrum_processor import SpectrumProcessor`
- **Relative imports** only within sub-packages: `from .interfaces import LEDCommand`
- Key re-exports: `affilabs/coordinators/__init__.py`, `affilabs/services/__init__.py`, `affilabs/managers/__init__.py`, `affilabs/presenters/__init__.py`

## Documentation Maintenance Rules
When creating or updating documentation:
1. **Never create session summary .md files** — they become stale immediately
2. **Place new docs in the appropriate `docs/` subfolder**:
   - `docs/architecture/` — system design, data flows, processing logic
   - `docs/calibration/` — calibration procedures and specifications
   - `docs/features/` — feature documentation and user-facing guides
   - `docs/hardware/` — firmware, EEPROM, device-specific references
   - `docs/user_guides/` — how-to guides, operation manuals, quick refs
   - `docs/future_plans/` — roadmaps, unimplemented feature designs
3. **Update existing docs** rather than creating new ones for the same topic
4. **Delete docs when the work they describe is completed** (fix notes, migration plans, audit reports)
5. **Docs that describe the current system** are valuable; docs that describe **a completed change** are not

## Hardware Models & Development Priority

> **Priority order: P4SPR (1st) → P4PRO (2nd) → P4PROPLUS (3rd)**
> EzSPR and KNX2 are legacy devices (<5 units in field) — lowest priority, rarely touched.

### Model Comparison

| Feature | P4SPR | P4PRO | P4PROPLUS |
|---------|-------|-------|-----------|
| **Injection method** | Manual syringe | 6-port rotary valve + AffiPump | 6-port rotary valve + internal pumps |
| **Pump** | None (or optional AffiPump) | AffiPump (external high-end syringe pump) | Built-in peristaltic pumps (V2.3+ fw) |
| **Method mode** | Manual only (locked) | Manual or Semi-Automated | Manual or Semi-Automated |
| **6-port valve** | ❌ | ✅ controller-actuated | ✅ controller-actuated |
| **Channel layout** | 4 independent fluidic channels — up to 4 different samples | 4 optical channels; **2 fluidic channels addressable per cycle** (AC or BD) | 4 optical channels; **2 fluidic channels addressable per cycle** (AC or BD) |
| **Flow quality** | N/A | Excellent (syringe pump, pulse-free) | Lower (peristaltic pulsation) |
| **Controller ID** | `PicoP4SPR` / `PicoEZSPR` | Detected by `ctrl_type` | Detected by `'p4proplus' in firmware_id` |

### P4SPR Injection: Manual Syringe
- Each optical channel (A, B, C, D) is paired with its own **independent fluidic channel** — user can inject up to **4 different samples** in one experiment
- User **physically pipettes** sample into each flow cell inlet port by hand
- Injections are intended to be parallel, but sequentially pipetting A through D can introduce **up to 15 seconds** of inter-channel delay
- Injection detection algorithm must be tolerant of this inter-channel timing skew
- Channels used: **any combination** of A, B, C, D (user selects freely; unused channels are left in buffer)
- Adding AffiPump unlocks Semi-Automated mode (same 6-port valve flow as P4PRO)

### P4PRO / P4PROPLUS Injection: Automated Flow
- **4 optical channels total, but only 2 fluidic channels are addressable per injection cycle** — the 6-port valve routes sample to one pair at a time
- Standard pairs: **AC** (channels A and C share one fluidic path) and **BD** (channels B and D share one fluidic path); non-standard AD or CB is possible but uncommon
- To inject a different sample into each pair, the user runs two sequential injection cycles (AC first, then BD, or vice versa)
- **6-port rotary valve** is actuated by the controller to switch between buffer and sample
- **AffiPump** (P4PRO) = high-end external syringe pump — pulse-free, accurate flow rates; **can aspirate and dispense**; fully programmable (flow rate, volume, speed profile per injection)
- **Internal pumps** (P4PROPLUS) = built-in peristaltic pumps — **dispense only** (no aspiration); **on/off control only with preset flow rates** (not individually programmable); lower quality due to flow pulsation; contact time minimum 180 s at 25 µL/min [firmware warning enforced]
- Flow rates, injection volume, and contact time are precisely controlled by software
- `_update_internal_pump_visibility()` shows/hides P4PROPLUS-specific pump UI

### Preset Design Philosophy: Human-as-Autosampler (P4SPR) vs Automated Flow (P4PRO/PROPLUS)

**P4SPR presets: one cycle = one watchable region (~5–10 min).**

The user physically pipettes samples. Each cycle must show something clear on the live sensorgram — a signal event the user can observe and act on. The live view is ~5–10 min of context. Design presets around that constraint:

- **Binding reps** (8.5min each) → one cycle per rep. Short enough to watch, distinct enough to identify later in Edits.
- **Immobilization** (30min), **extended baseline** (15min) → single long cycles are fine — the user is monitoring a slow drift, not making injection decisions every few minutes.
- **No regen/baseline padding between every binding rep** — those micro-cycles create queue noise. The user pipettes regen manually during the binding window; alignment happens in Edits.
- **Target ~6–10 meaningful queue entries** for a full amine coupling: baseline → activation → immobilization → blocking → baseline → 5× binding.
- **Never create 60-min black-box binding cycles** — users can't make sense of a 60-min sensorgram window while also pipetting.

Post-hoc work (cursor placement, region alignment, delta-SPR, export) all happens in the **Edits tab**.

**P4PRO/PROPLUS presets: one cycle = one injection event.**

With AffiPump or internal pumps, each injection is automated and timed. Cycles can be short (2–15 min) and fully segmented — the machine handles timing so the user doesn't need to watch constantly. No Edits post-processing needed for alignment.

**Rule for preset authoring:**
- P4SPR: regen and baseline are **not queue cycles** — folded into neighboring steps. User adds them manually if needed. All prep steps (EDC/NHS, ligand, ethanolamine) collapse into **one immobilization cycle of 30min**. Each binding rep gets its own 8.5min cycle.
- P4PRO/PROPLUS: explicit regen + baseline cycles between every binding rep is correct — the machine handles timing so fine-grained segmentation works.
- Never pad P4SPR presets with regen/baseline cycles between binding reps.
- Never create 60-min black-box binding windows for P4SPR.

### Code Gotchas
- `ctrl_type` field in `hardware_mgr` status dict identifies the model at runtime
- `'p4proplus' in firmware_id.lower()` is the guard for internal pump features
- `configure_for_hardware(hw_name, has_affipump)` in `MethodBuilderDialog` sets mode combo based on model
- P4SPR mode_combo is **disabled** (locked to "Manual"); PRO/PROPLUS defaults to "Semi-Automated"

## UI Request Protocol

When the user writes **`REQ: [one sentence]`**, treat it as a UI change request. Execute immediately — no backlog, no ticketing.

**Steps:**
1. Check [UI_STATE_MACHINE.md](docs/ui/UI_STATE_MACHINE.md) — does this affect a state or transition?
2. Check [UI_COMPONENT_INVENTORY.md](docs/ui/UI_COMPONENT_INVENTORY.md) — which widget / presenter / sidebar tab owns it?
3. Check [UI_DESIGN_SYSTEM.md](docs/ui/UI_DESIGN_SYSTEM.md) — what style rules apply (color token, button variant, spacing)?
4. Check [UI_HARDWARE_MODEL_REQUIREMENTS.md](docs/ui/UI_HARDWARE_MODEL_REQUIREMENTS.md) — is this hardware-conditional?
5. Check [UI_GRAPH_VISUALIZATION_SPEC.md](docs/ui/UI_GRAPH_VISUALIZATION_SPEC.md) — does this touch a graph?
6. Implement in the correct file(s).
7. Validate against the §New Component Checklist in UI_COMPONENT_INVENTORY.md.
8. Update whichever UI doc(s) changed.

**UI docs live in:** `docs/ui/` (6 files — Design System, Component Inventory, State Machine, Graph Spec, Hardware Model Requirements, **UX User Journey**)

> When designing or evaluating any UI element, check [UX_USER_JOURNEY.md](docs/ui/UX_USER_JOURNEY.md) first — it defines what users need at each of the 6 experiment stages (Connect → Calibrate → Acquire → Inject → Record → Export).

---

## Active Context (update at end of each session)

<!-- This section is a cross-session scratchpad. Update it before ending a session. -->
<!-- Keep it SHORT — 5-10 bullet points max. Delete stale items aggressively. -->

### Current Focus
- UX polish / feature-completion phase post-mixin refactor — app boots cleanly
- v2.0.5 beta released 2026-02-17
- **Timeline system implementation** — Phases 1–4 + improvements B/C/D/E/F complete ✅

### In-Progress / Known Issues
- `ApplicationState` migration incomplete — `app_state.py` defines target but `main.py` not yet converted
- Timeline Phase 5 (Presenters: SensogramPresenter + EditsTab query from stream) — ready to start
- Binding Plot (`_binding_plot_mixin.py`) — plan complete, implementation not yet started
- **No wash flag from WashMonitor** — `_WashMonitor.wash_detected` only calls `bar.set_channel_wash(ch)` (visual). No graph flag placed. Wash flags only come from `_timer_mixin._place_automatic_wash_flags()` on timer expiry.
- **Manual injection auto-detection not firing** — `_scan_channel()` uses `auto_detect_injection_point()` (raw nm, no RU conversion). `[SCAN x]` lines now at INFO level. Needs live test to confirm detection fires; if still silent, check `detection_priority` passed from coordinator and whether `window_start_time` mask leaves enough points.

### Recently Completed
- **Injection lifecycle timeout fix** ✅ (Feb 22 2026) — `done_event.wait(timeout=95)` in `injection_coordinator.py` fired `injection_completed` prematurely when contact_time was set. Now: `_on_dialog_complete` doesn't unblock BG thread when contact_time exists; waits for `_on_bar_done` (all channels washed). Timeout = `95 + contact_time + 120s`.
- **Dormant vs active panel appearance** ✅ (Feb 22 2026) — Were visually identical (`#F2F2F7`, `#8E8E93`). Now: dormant = dashed `#C7C7CC` border + lighter text; active = solid `rgba(0,122,255,0.20)` blue border + `#F8F8FA` bg + "Waiting for injection…" text.
- **EditsTab blank graph bug fixed** ✅ (Feb 21 2026) — `_AlignChannelProxy` was missing `blockSignals()` and `setCurrentText()` methods
- **Active Cycle graph embeds** ✅ (Feb 21 2026) — `InteractiveSPRLegend` IQ dots live-wired; `CycleStatusOverlay` replaces floating popup

### Context Maintenance Workflow
**At the end of each work session**, update this "Active Context" section:
1. Move completed items from "In-Progress" to "Recently Completed"
2. Add any new in-progress work or discovered issues
3. Delete "Recently Completed" items older than ~2 sessions (they're in git history)
4. Keep total length under 15 lines — ruthlessly trim
5. If a major architectural decision was made, add it to the relevant section above (not here)
