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
- One full acquisition cycle (all 4 channels × P-pol + S-pol) takes **~1 second** (≈250ms per channel at default integration time), giving **~1 Hz per channel**

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
  mixins/              ← main.py mixin extracts (PumpMixin, FlagMixin, etc.)

Runtime configuration (VISIBLE to Claude):
  config/              ← App configuration files
  settings/            ← User settings (settings.py = master constants)
  detector_profiles/   ← Detector-specific profiles (Flame-T, USB4000)
  data/                ← Runtime app data (data/spark/ — Spark AI knowledge base, tips, history)

Ignored by Claude Code (use --no-ignore to access):
  scripts/             ← Operational scripts (calibration, recovery, provisioning)
  tools/               ← Analysis, diagnostics, ML training, cleanup
    tools/diagnostics/ ← One-off diagnostic/debug scripts (USB, drivers, hardware)
  standalone_tools/    ← Standalone GUI utility tools
  tests/               ← Test suite
  calibrations/        ← Calibration scripts + per-device configs (servo, LED)
  docs/                ← Project documentation
    docs/features/     ← FRS specs for each subsystem (primary reference)
    docs/user_guides/  ← How-to guides, training docs, walkthroughs
    docs/architecture/ ← System design, data flows
    docs/hardware/     ← Firmware, EEPROM, OEM communication
    docs/future_plans/ ← Roadmaps, unimplemented designs
    docs/calibration/  ← Calibration procedures and specs
    docs/ui/           ← UI design system, component inventory, state machine
  _scratch/            ← Archived one-off scripts (do not add new files here — use tools/diagnostics/)
  _data/               ← All runtime-generated data and outputs
    _data/calibration_data/   ← Calibration JSON dumps from oem_calibrate.py
    _data/OpticalSystem_QC/   ← Per-device QC validation reports
    _data/led_calibration_official/ ← LED calibration data (official device records)
    _data/demo/               ← Demo/simulation data
    _data/logs/               ← App runtime logs (not committed)
  _build/              ← Build artifacts, PyInstaller outputs, installers
  .venv/               ← Python virtual environment
```

## File Placement Rules
> **When creating a new file, pick the first matching rule.**

| File type | Where it goes |
|-----------|--------------|
| App source code — new widget, service, coordinator, pipeline | `affilabs/<layer>/` matching the 4-layer architecture |
| `main.py` method group too large | Extract to `mixins/<group>_mixin.py` |
| FRS / feature spec doc | `docs/features/<SUBSYSTEM_NAME>_FRS.md` |
| How-to guide, training doc, walkthrough | `docs/user_guides/` |
| Architecture / data-flow doc | `docs/architecture/` |
| Hardware / firmware / OEM reference | `docs/hardware/` |
| Roadmap / unimplemented design | `docs/future_plans/` |
| Operational script (calibration, provisioning, shipping) | `scripts/<category>/` |
| Analysis, ML, data-processing script | `tools/<category>/` |
| One-off diagnostic / debug script (USB, drivers, hardware probe) | `tools/diagnostics/` |
| Runtime-generated data, JSON dumps, QC reports | `_data/<category>/` |
| Calibration per-device configs + scripts | `calibrations/` |
| Standalone GUI utility (runs without main app) | `standalone_tools/` |
| Build spec, installer script | `_build/` |
| **Root** | Only the files listed in Workspace Layout above — nothing else |

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
| EditsTab — cycle boundary adjust (Adjust tab, ±20% padding, drag handles, time correction) | [CYCLE_BOUNDARY_ADJUST_FRS.md](docs/features/CYCLE_BOUNDARY_ADJUST_FRS.md) | `affilabs/tabs/edits/_ui_builders.py`, `affilabs/tabs/edits/_adjust_mixin.py` (planned) |
| EditsTab — data loading utilities | [EDITS_DATA_LOADING_FRS.md](docs/features/EDITS_DATA_LOADING_FRS.md) | `affilabs/tabs/edits/_data_utils.py` |
| Recording, auto-save, Excel export | [RECORDING_MANAGER_FRS.md](docs/features/RECORDING_MANAGER_FRS.md) | `affilabs/managers/recording_manager.py` |
| Experiment index — searchable log of all recording sessions | [EXPERIMENT_INDEX_FRS.md](docs/features/EXPERIMENT_INDEX_FRS.md) | `affilabs/services/experiment_index.py` |
| Experiment browser dialog — search/load past recordings from Edits tab | [EXPERIMENT_BROWSER_FRS.md](docs/features/EXPERIMENT_BROWSER_FRS.md) | `affilabs/dialogs/experiment_browser_dialog.py` (planned) |
| Notes tab — ELN, experiment list, Kanban, planning, tags, ratings | [NOTES_TAB_FRS.md](docs/features/NOTES_TAB_FRS.md) | `affilabs/tabs/notes_tab.py` |
| Excel chart generation | [EXCEL_CHART_BUILDER_FRS.md](docs/features/EXCEL_CHART_BUILDER_FRS.md) | `affilabs/services/excel_exporter.py` |
| Controller HAL, servo commands, adapters | [CONTROLLER_HAL_FRS.md](docs/features/CONTROLLER_HAL_FRS.md) | `affilabs/utils/hal/controller_hal.py` |
| Pump HAL, AffiPump, Cavro protocol | [PUMP_HAL_FRS.md](docs/features/PUMP_HAL_FRS.md) | `affilabs/utils/hal/pump_hal.py` |
| P4PRO fluidic system — KC1/KC2, 6-port loop, 3-way valves, channel mapping | [P4PRO_FLUIDIC_ARCHITECTURE.md](docs/hardware/P4PRO_FLUIDIC_ARCHITECTURE.md) | `affilabs/coordinators/injection_coordinator.py` |
| **Firmware files** — latest .c and .uf2 for P4SPR/P4PRO/P4PROPLUS, shipped devices, flash instructions | [FIRMWARE_QUICK_REFERENCE.md](docs/hardware/FIRMWARE_QUICK_REFERENCE.md) | `C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Firmware\CLAUDE.md` (firmware repo) |
| Hardware scanning, USB connect flow | [HARDWARE_SCANNING_FRS.md](docs/features/HARDWARE_SCANNING_FRS.md) | `affilabs/core/hardware_manager.py` |
| Injection flags, AutoMarker, contact timer | [FLAGGING_SYSTEM_GUIDE.md](docs/features/FLAGGING_SYSTEM_GUIDE.md) | `affilabs/managers/flag_manager.py` |
| Injection workflow — all scenarios (manual/auto, 3-channel, wash, markers) | [INJECTION_WORKFLOW_FRS.md](docs/features/INJECTION_WORKFLOW_FRS.md) | `affilabs/coordinators/injection_coordinator.py`, `affilabs/dialogs/manual_injection_dialog.py`, `affilabs/widgets/injection_action_bar.py`, `mixins/_pump_mixin.py` |
| Kinetic cycle injection — flow-based, valve timing, kobs/ka/kd fitting, dissociation phase | [KINETIC_INJECTION_FRS.md](docs/features/KINETIC_INJECTION_FRS.md) | `affilabs/coordinators/injection_coordinator.py`, `affilabs/services/kinetics_fitter.py` (planned), `affilabs/domain/cycle.py` |
| Calibration flow, servo auto-cal | [CALIBRATION_ORCHESTRATOR_FRS.md](docs/calibration/CALIBRATION_ORCHESTRATOR_FRS.md) | `affilabs/core/calibration_orchestrator.py` |
| OEM factory provisioning — servo cal, LED model training, startup cal, ultra-sensitive detection | [OEM_OPTICAL_CALIBRATION_GUIDE.md](docs/calibration/OEM_OPTICAL_CALIBRATION_GUIDE.md) | `scripts/provisioning/oem_calibrate.py`, `affilabs/core/oem_model_training.py`, `calibrations/servo_polarizer/calibrate_polarizer.py` |
| Signal quality, IQ levels, wavelength zones | [SENSOR_IQ_SYSTEM.md](docs/features/SENSOR_IQ_SYSTEM.md) | `affilabs/utils/sensor_iq.py` |
| Signal event classifier — pre-inject readiness badge, bubble detection, telemetry logger, per-cycle quality score, run star rating | [SIGNAL_EVENT_CLASSIFIER_FRS.md](docs/features/SIGNAL_EVENT_CLASSIFIER_FRS.md) | `affilabs/utils/signal_event_classifier.py`, `affilabs/services/signal_telemetry_logger.py`, `affilabs/services/signal_quality_scorer.py`, `affilabs/widgets/signal_event_badge.py` (planned) |
| Optical fault detection — leak (raw intensity drop) + air bubble (wavelength/transmittance transient); all alerts via Sparq bubble | [OPTICAL_FAULT_DETECTION_FRS.md](docs/features/OPTICAL_FAULT_DETECTION_FRS.md) | `mixins/_acquisition_mixin.py`, `affilabs/services/air_bubble_detector.py`, `affilabs/utils/spectrum_helpers.py`, `affilabs/widgets/spark_bubble.py` |
| Device health dashboard — unified aggregator for all health signals (IQ, P2P, FWHM, faults, run quality); wiring plan + gap analysis | [DEVICE_HEALTH_DASHBOARD_FRS.md](docs/features/DEVICE_HEALTH_DASHBOARD_FRS.md) | `affilabs/coordinators/device_health_coordinator.py` (planned), `affilabs/widgets/device_status.py`, `affilabs/sidebar_tabs/AL_device_status_builder.py` |
| Sparq account — device registration, Sparq Coach upload, Nutshell CRM integration, failure-pattern upsell pipeline | [SPARQ_ACCOUNT_FRS.md](docs/features/SPARQ_ACCOUNT_FRS.md) | `affilabs/services/sparq_account_service.py`, `affilabs/services/sparq_coach_service.py`, `affilabs/dialogs/sparq_registration_dialog.py` (planned) |
| Sparq Coach Beta — auto bug reporting (Discord + Nutshell), Claude Haiku chat fallback, Cloudflare Worker proxy, rate limiting per device | [SPARQ_COACH_BETA_FRS.md](docs/features/SPARQ_COACH_BETA_FRS.md) | `affilabs/services/sparq_coach_service.py`, `affilabs/services/bug_reporter.py`, `affilabs/widgets/spark_help_widget.py`, `affilabs/ui/img/bug_icon.svg` |
| Cycle templates, queue presets | [METHOD_PRESETS_SYSTEM.md](docs/features/METHOD_PRESETS_SYSTEM.md) | `affilabs/services/cycle_template_storage.py` |
| Method Builder UI redesign (3-zone layout, template gallery, Sparq bar) | [METHOD_BUILDER_REDESIGN_FRS.md](docs/features/METHOD_BUILDER_REDESIGN_FRS.md) | `affilabs/widgets/method_builder_dialog.py` |
| Contact Monitor panel, per-channel contact timers, binding symbols | [MICROFLUIDIC_CHANNELS_PANEL_FRS.md](docs/features/MICROFLUIDIC_CHANNELS_PANEL_FRS.md) | `affilabs/widgets/injection_action_bar.py` |
| Compression Assistant — guided chip compression, gauge, QC leak check | [COMPRESSION_ASSISTANT_FRS.md](docs/features/COMPRESSION_ASSISTANT_FRS.md) | `standalone_tools/compression_trainer_ui.py` |
| Injection auto-detection FRS v2 — multi-feature scorer, event flags, timing, scoring | [INJECTION_DETECTION_FRS.md](docs/features/INJECTION_DETECTION_FRS.md) | `affilabs/utils/spr_signal_processing.py`, `affilabs/coordinators/injection_coordinator.py` |
| In-app tips system — tip storage, display triggers, dismissal tracking | [TIPS_SYSTEM.md](docs/features/TIPS_SYSTEM.md) | `affilabs/services/` |
| Timeline events, CycleMarker, stream API | [TIMELINE_QUICK_START.md](docs/architecture/TIMELINE_QUICK_START.md) | `affilabs/domain/timeline.py`, `affilabs/core/recording_manager.py`, `affilabs/managers/flag_manager.py`, `mixins/_cycle_mixin.py` |
| Timeline Phase 5+ roadmap, proposed improvements | [TIMELINE_ROADMAP.md](docs/future_plans/TIMELINE_ROADMAP.md) | `affilabs/domain/timeline.py` |
| Platform strategy — retention layers, revenue streams, data flywheel, competitive positioning, implementation priority | [PLATFORM_STRATEGY.md](docs/future_plans/PLATFORM_STRATEGY.md) | — |
| 21 CFR Part 11 compliance — gap analysis, implementation order, files to create | [21CFR_PART11_GAP_ANALYSIS.md](docs/future_plans/21CFR_PART11_GAP_ANALYSIS.md) | `affilabs/services/audit_log.py` (planned) |
| IQ/OQ plan — check IDs, test suites, report format, implementation order | [IQOQ_PLAN.md](docs/future_plans/IQOQ_PLAN.md) | `scripts/validation/`, `tests/oq/` (planned) |
| Software update delivery — drop-in exe vs full installer, user data safety, USB edge case, auto-update plan | [SOFTWARE_UPDATE_DELIVERY_FRS.md](docs/features/SOFTWARE_UPDATE_DELIVERY_FRS.md) | `_build/installer.nsi`, `_build/Affilabs-Core.spec`, `version.py` |
| Interactive SPR Legend — floating Δ SPR overlay on Active Cycle graph; channel selection, curve highlighting, left/right nudge (±1 s / ±5 s) for inter-channel injection skew correction | [INTERACTIVE_SPR_LEGEND_FRS.md](docs/features/INTERACTIVE_SPR_LEGEND_FRS.md) | `affilabs/widgets/interactive_spr_legend.py`, `affilabs/affilabs_core_ui.py`, `affilabs/utils/ui_update_helpers.py` |
| TransportBar (toolbar redesign), IconRail (vertical tab strip) | [TRANSPORT_BAR_FRS.md](docs/features/TRANSPORT_BAR_FRS.md) | `affilabs/widgets/transport_bar.py`, `affilabs/widgets/icon_rail.py` |
| SpectrumBubble, RailTimerPopup, LiveContextPanel, LiveRightPanel | [FLOATING_PANELS_FRS.md](docs/features/FLOATING_PANELS_FRS.md) | `affilabs/widgets/spectrum_bubble.py`, `affilabs/widgets/rail_timer_popup.py`, `affilabs/widgets/live_context_panel.py`, `affilabs/widgets/live_right_panel.py` |
| GuidanceCoordinator — adaptive contextual hints | [GUIDANCE_COORDINATOR_FRS.md](docs/features/GUIDANCE_COORDINATOR_FRS.md) | `affilabs/coordinators/guidance_coordinator.py` |
| Accessibility panel — colour palettes, line styles, dark mode, **Large Text (FontScale)** | [ACCESSIBILITY_PANEL_FRS.md](docs/features/ACCESSIBILITY_PANEL_FRS.md) | `affilabs/widgets/accessibility_panel.py`, `affilabs/ui_styles.py` |
| LED calibration model — 3-stage linear model, per-device JSON, load/calculate intensity | [LED_MODEL_LOADER_FRS.md](docs/features/LED_MODEL_LOADER_FRS.md) | `affilabs/services/led_model_loader.py` |
| ML QC intelligence — 4 predictive models: calibration failure, LED health, sensor coating, optical alignment | [ML_QC_INTELLIGENCE_FRS.md](docs/features/ML_QC_INTELLIGENCE_FRS.md) | `affilabs/core/ml_qc_intelligence.py` |
| FMEA system — failure mode tracking across calibration, afterglow, live data; cross-phase correlation | [FMEA_SYSTEM_FRS.md](docs/features/FMEA_SYSTEM_FRS.md) | `affilabs/core/fmea_tracker.py`, `affilabs/core/fmea_integration.py` |
| Acquisition event coordinator — start/stop lifecycle, hardware config, error handling, UI state | [ACQUISITION_EVENT_COORDINATOR_FRS.md](docs/features/ACQUISITION_EVENT_COORDINATOR_FRS.md) | `affilabs/coordinators/acquisition_event_coordinator.py` |
| Calibration validator — spectrum quality checks (signal, saturation, SNR), LED + integration time validation | [CALIBRATION_VALIDATOR_FRS.md](docs/features/CALIBRATION_VALIDATOR_FRS.md) | `affilabs/services/calibration_validator.py` |
| Startup calibration dialog — non-modal progress dialog, thread-safe signals, Start/Retry/Continue buttons | [STARTUP_CALIBRATION_DIALOG_FRS.md](docs/features/STARTUP_CALIBRATION_DIALOG_FRS.md) | `affilabs/dialogs/startup_calib_dialog.py` |
| Data acquisition manager — DAQ loop, 3-tier fallback (rankbatch/batch/sequential), threading, error recovery | [DATA_ACQUISITION_FRS.md](docs/features/DATA_ACQUISITION_FRS.md) | `affilabs/core/data_acquisition_manager.py` |
| Spectrum processing pipelines — 9 pipelines (Fourier, centroid, polynomial, hybrid, batch SG, consensus, etc.), PipelineRegistry | [SPECTRUM_PIPELINES_FRS.md](docs/features/SPECTRUM_PIPELINES_FRS.md) | `affilabs/utils/pipelines/`, `affilabs/utils/processing_pipeline.py` |
| Sensogram presenter — timeline + cycle-of-interest graphs, cursors, flag markers, channel visibility | [SENSOGRAM_PRESENTER_FRS.md](docs/features/SENSOGRAM_PRESENTER_FRS.md) | `affilabs/presenters/sensogram_presenter.py` |
| Spectroscopy presenter — transmission + raw spectrum plots, wavelength filtering, dual access path | [SPECTROSCOPY_PRESENTER_FRS.md](docs/features/SPECTROSCOPY_PRESENTER_FRS.md) | `affilabs/presenters/spectroscopy_presenter.py` |
| Queue manager — cycle queue, locking semantics, mid-run append, method snapshot, serialization | [QUEUE_MANAGER_FRS.md](docs/features/QUEUE_MANAGER_FRS.md) | `affilabs/managers/queue_manager.py` |
| User profiles — multi-user, XP levels, guidance leveling, hint dismissal, compression training | [USER_PROFILES_FRS.md](docs/features/USER_PROFILES_FRS.md) | `affilabs/widgets/user_panel_popup.py`, `affilabs/services/user_profile_manager.py` |
| Settings system — 22 constant groups (settings.py) + runtime config (app_config.py), local_settings override | [SETTINGS_SYSTEM_FRS.md](docs/features/SETTINGS_SYSTEM_FRS.md) | `settings/settings.py`, `affilabs/app_config.py` |
| Detector profiles — JSON hardware profiles for Flame-T and USB4000, runtime override of deprecated settings | [DETECTOR_PROFILES_FRS.md](docs/features/DETECTOR_PROFILES_FRS.md) | `detector_profiles/*.json` |
| Sidebar builders — 7 AL_* builder modules (settings, flow, method, graphic, device status, export, replay) | [SIDEBAR_BUILDERS_FRS.md](docs/features/SIDEBAR_BUILDERS_FRS.md) | `affilabs/sidebar_tabs/` |
| UI styling — design tokens (Colors, Fonts, Dimensions, Spacing), 26 stylesheet builders, FontScale accessibility | [UI_STYLING_FRS.md](docs/features/UI_STYLING_FRS.md) | `affilabs/ui_styles.py` |

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

### Serial Number Prefix Rule

| Prefix | Rule |
|--------|------|
| **`AFFI`** | **All new devices.** Write `AFFI` for any new serial created from this point forward (e.g. `AFFI09792`, `AFFI10979`). |
| **`FLMT`** | **Legacy read-only.** Existing `FLMT` serials are kept as-is in the registry and on the physical hardware — do not rename them. Code must accept both prefixes when reading/matching. |
| **`ST`** | **Legacy read-only.** Phase Photonics prototype builds — treat the same as `FLMT`. |

**Rule in plain terms:** never write a new `FLMT` serial. If `oem_calibrate.py` auto-detects a serial from the hardware, use that. If you are assigning a serial manually (test unit, replacement, new build), use `AFFI`.

| Database | Path | Format | Purpose |
|----------|------|--------|---------|
| **device_registry.json** | `_data/calibration_data/device_registry.json` | JSON | Customer + shipping identity (who owns each unit, invoice, country) |
| **device_history.db** | `tools/ml_training/device_history.db` | SQLite | Per-device calibration performance history for ML training (FWHM, SNR, convergence stats) |

### device_registry.json (identity/CRM)
- One entry per serial, keyed by serial string (e.g. `"AFFI09792"` for new units, `"FLMT09788"` for legacy)
- Fields: `customer.name`, `customer.country`, `order.invoice`, `shipped_date`, `calibration_files[]`, `ml_training_include`
- Add new device by inserting a new key into the `"devices"` object
- `ml_training_include: false` to exclude prototypes or returned units

### device_history.db (ML training)
- Managed by `DeviceHistoryDatabase` in `tools/ml_training/device_history.py`
- Records added via `record_calibration_to_database()` in `tools/ml_training/record_calibration_result.py`
- Keyed by `detector_serial` (integer — numeric portion of serial, e.g. `9792` for `AFFI09792`)
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

> **Marketing names (docs/UI/comms):** SimplexSPR · SimplexFlow · SimplexPro
> **Code/firmware identifiers (source code only):** P4SPR · P4PRO · P4PROPLUS — these are `ctrl_type` values from hardware. Do not rename them in code.

> **Priority order: SimplexSPR/P4SPR (1st) → SimplexFlow/P4PRO (2nd) → SimplexPro/P4PROPLUS (3rd)**
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

### Live Tab vs Edits Tab — Fundamental Separation of Concerns (P4SPR / Manual Injection)

**Live tab is PURELY about good data acquisition.** Edits tab is for data processing and scientific assessment.

| Live tab concerns | Edits tab concerns |
|-------------------|-------------------|
| Bubbles present? | ΔSPR magnitude |
| Leak detected? | Binding curve shape / Kd fitting |
| Signal stable and at expected level? | Alignment, baseline subtraction |
| Contact time adequate? | Export, reporting |
| Data quality OK — or does the run need to be repeated? | Comparing cycles |

**What Live does NOT do (P4SPR):**
- No SPR-specific interpretation (binding affinity, on/off rates, Rmax)
- No assessment of whether the experiment is scientifically meaningful
- No comparison between channels or concentrations

**Rule:** If a feature tells the user something about their *science*, it belongs in Edits. If it tells the user something about their *instrument or data quality*, it belongs in Live.

---

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
- UX polish / feature-completion phase — v2.0.5 beta released 2026-02-17
- Sidebar redesign (v2.1): `TransportBar`, `IconRail`, floating panels complete ✅ — stubs for `LiveContextPanel` (Phase 3) and `LiveRightPanel` (Phase 2) in place, not wired

### In-Progress / Known Issues
- `ApplicationState` migration incomplete — `app_state.py` defines target but `main.py` not yet converted
- Timeline Phase 5 (Presenters: SensogramPresenter + EditsTab query from stream) — ready to start
- **GuidanceCoordinator Pass B** — Pass A (logging only) complete; Pass B (widget calls: `push_hint`, show/hide rail buttons, update combos) not yet implemented
- **Injection autodetection live validation pending** — `_InjectionMonitor` fire #1 (injection) + fire #2 (wash) implemented. Needs hardware live test.
- **No wash flag on early wash** — `_InjectionMonitor` fire #2 → `_handle_wash()` updates bar UI only. No wash flag placed if user washes before contact timer expires. `_place_automatic_wash_flags()` only runs at timer expiry.
- **Contact marker doesn't move on wash** — marker stays at predicted `injection_time + contact_time`. No code currently moves it to actual wash time.

### Recently Completed
- **Firmware repo reorg + CLAUDE.md** ✅ (Mar 1 2026) — Firmware repo reorganized into `p4spr/`, `P4PRO/`, `p4proplus/` subfolders. `CLAUDE.md` added to firmware repo root (`d5cde53`). `docs/hardware/FIRMWARE_QUICK_REFERENCE.md` added to app repo. Latest files: P4SPR v2.4.1, P4PRO v2.3, P4PROPLUS v2.3.4.
- **GitHub app repo reorg** ✅ (Mar 1 2026) — 106 changes committed (`e6d36bf`), 12 stale branches archived+deleted, CI rewritten to safe read-only checks. App repo: `v2.0.5-beta` at `d219cd6`.
- **Simple cal servo fix** ✅ (Mar 1 2026) — `simple_led_calibration.py`: `getattr(device_config, "servo_s_position", None)` → `device_config.get_servo_s_position()`.
- **IQ check via `--iq-check` flag** ✅ (Mar 1 2026) — `scripts/validation/iq_check.py` (9 checks) + module-level intercept in `main.py`.
- **Sparq Coach Beta — fully live** ✅ (Mar 1 2026) — Cloudflare Worker + KV + Discord + Nutshell wired end-to-end.
- **Active Cycle legend focus persistence** ✅ (Mar 1 2026) — `StrongFocus` + `_user_has_selected` flag.

### Next Session
- **Sparq Coach Beta — Phase 1.6:** Wire "Ask Sparq Coach ✨" button in `spark_help_widget.py` for local engine misses (FRS §11.2). Calls `SparqCoachService.ask_coach()`.
- **Cycle Boundary Adjust** — FRS at [CYCLE_BOUNDARY_ADJUST_FRS.md](docs/features/CYCLE_BOUNDARY_ADJUST_FRS.md). Start with §8 steps 1–3.

### Planned — Future Milestones
- **v2.2:** Autosampler integration (Knauer Azura TCP + TTL trigger option) — see `docs/future_plans/AUTOSAMPLER_INTEGRATION_PLAN.md`
  - TTL trigger path: ~4–5 days (firmware GPIO input + `ControllerHAL.get_pending_trigger_events()` + `InjectionCoordinator.on_external_injection_trigger()`). **Blocked on firmware team confirming P4PRO GPIO pin availability.**
  - TCP polling path: already designed in plan, no firmware changes needed
- **v2.3:** SiLA 2 wrapper — gRPC server exposing SPRAcquisition / FluidicControl / RecordingControl features. ~1 week. See `docs/future_plans/ANIML_SILA_IMPLEMENTATION_PLAN.md`.

### Context Maintenance Workflow
**At the end of each work session**, update this "Active Context" section:
1. Move completed items from "In-Progress" to "Recently Completed"
2. Add any new in-progress work or discovered issues
3. Delete "Recently Completed" items older than ~2 sessions (they're in git history)
4. Keep total length under 15 lines — ruthlessly trim
5. If a major architectural decision was made, add it to the relevant section above (not here)
