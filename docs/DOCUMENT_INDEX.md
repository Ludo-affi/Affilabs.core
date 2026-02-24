# Affilabs.core — Documentation Index

Last updated: 2026-02-24 (Added missing sections: Hardware, User Guides, Product Requirements, Setup; added Notes tab, Experiment Index/Browser, Transport Bar, Floating Panels, Guidance Coordinator, Accessibility Panel, Method Builder Redesign, Microfluidic Channels Panel, Compression Assistant, Injection Detection, Leak Detection, Tips System, Sensor Chip Metadata FRS docs; added UX_USER_JOURNEY.md to UI section; added all missing future_plans docs; updated EXPERIMENT_INDEX_FRS and NOTES_TAB_FRS to ✅)
Add a row whenever a new document is created; update Verified column after each code-verification pass.

**Verification key:**
- ✅ Code-verified — confirmed accurate against current codebase
- ⚠️ Unverified — content plausible but not cross-checked against code
- 🔴 Stale — known to be outdated (pre-rework, pre-refactor)
- 🗂️ Planned — does not exist yet

---

## Architecture Specs (`docs/architecture/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [LED_CONVERGENCE_ENGINE.md](architecture/LED_CONVERGENCE_ENGINE.md) | S-pol + P-pol convergence algorithm; ML models; per-channel orchestration | Feb 19 2026 | ✅ |
| [DEVICE_CONFIGURATION_SYSTEM.md](architecture/DEVICE_CONFIGURATION_SYSTEM.md) | Per-device JSON config lifecycle; EEPROM fallback; OEM calibration workflow | Feb 19 2026 | ✅ |
| [SPR_SIGNAL_PROCESSING_PIPELINE.md](architecture/SPR_SIGNAL_PROCESSING_PIPELINE.md) | Full pipeline: dark subtraction → P/S ratio → SG filter → Fourier peak detection; QC metrics; pipeline registry | Feb 18 2026 | ✅ |
| [INJECTION_AUTO_DETECTION_FRS.md](architecture/INJECTION_AUTO_DETECTION_FRS.md) | `auto_detect_injection_point` algorithm; confidence scoring; InjectionCoordinator flow; multi-channel scan; delta SPR; orientation validation | Feb 19 2026 | ✅ |
| [MANUAL_INJECTION_STATE_MACHINE.md](architecture/MANUAL_INJECTION_STATE_MACHINE.md) | P4SPR manual injection state machine; channel arm/inject/rinse UI states | Feb 18 2026 | ✅ |
| [CALIBRATION_ENTRY_EXIT_FLOWS.md](architecture/CALIBRATION_ENTRY_EXIT_FLOWS.md) | 5 calibration types; entry/exit transitions; state machine | Feb 3 2026 | ⚠️ |
| [CALIBRATION_FLOWS_VISUAL.md](architecture/CALIBRATION_FLOWS_VISUAL.md) | Visual flow diagrams for calibration sequences | unknown | ⚠️ |
| [ACQUISITION_SYSTEM.md](architecture/ACQUISITION_SYSTEM.md) | DataAcquisitionManager; spectrum_acquired signal; thread model | unknown | ⚠️ |
| [ACQUISITION_METHODS.md](architecture/ACQUISITION_METHODS.md) | CYCLE_SYNC vs EVENT_RANK acquisition modes | unknown | ⚠️ |
| [DATA_PROCESSING_PIPELINE.md](architecture/DATA_PROCESSING_PIPELINE.md) | Raw counts → dark subtraction → transmission → peak finding | unknown | 🔴 Superseded by SPR_SIGNAL_PROCESSING_PIPELINE.md |
| [SPR_BASELINE_PEAK_FINDING_METHOD.md](architecture/SPR_BASELINE_PEAK_FINDING_METHOD.md) | SG smoothing; Fourier; centroid; polynomial peak finders | Nov 2025 | 🔴 Pre-rework |
| [HARDWARE_COMMUNICATION_LAYER.md](architecture/HARDWARE_COMMUNICATION_LAYER.md) | HAL interfaces; serial protocol; controller abstractions | unknown | ⚠️ |
| [HARDWARE_DEVICES.md](architecture/HARDWARE_DEVICES.md) | Supported hardware models; device capability matrix | unknown | ⚠️ |
| [PUMP_VALVE_SYSTEM.md](architecture/PUMP_VALVE_SYSTEM.md) | AffiPump; 6-port valve; internal pumps; flow control | unknown | ⚠️ |
| [VALVE_SAFETY_TIMEOUT.md](architecture/VALVE_SAFETY_TIMEOUT.md) | Valve open/close safety timeout policy | unknown | ⚠️ |
| [P_MODE_FREEZE_POLICY.md](architecture/P_MODE_FREEZE_POLICY.md) | P-mode convergence freeze after calibration completes | unknown | ⚠️ |
| [SATURATION_HANDLING.md](architecture/SATURATION_HANDLING.md) | Detector saturation detection; fallback logic | unknown | ⚠️ |
| [SERVO_POSITIONS_CLEAN.md](architecture/SERVO_POSITIONS_CLEAN.md) | Servo PWM units; S/P position storage; barrel vs round polarizers | unknown | ⚠️ |
| [METHOD_CYCLE_SYSTEM.md](architecture/METHOD_CYCLE_SYSTEM.md) | Semi-automated cycle engine; method presets; queue system | unknown | ⚠️ |
| [TIMELINE_INTEGRATION_GUIDE.md](architecture/TIMELINE_INTEGRATION_GUIDE.md) | Timeline domain model integration: migration checklist (Phases 1–4 complete), 3 migration paths, integration point examples, backward compatibility | Feb 19 2026 | ✅ |
| [TIMELINE_QUICK_START.md](architecture/TIMELINE_QUICK_START.md) | Timeline API quick reference: core classes, event types, phase-by-phase change checklist (Phases 1–4 ✅), common operations, testing | Feb 19 2026 | ✅ |
| [WORKFLOW_ARCHITECTURE.md](architecture/WORKFLOW_ARCHITECTURE.md) | Overall application workflow; phase diagram | unknown | ⚠️ |
| [UI_ARCHITECTURE.md](architecture/UI_ARCHITECTURE.md) | MVP pattern; presenters; coordinators; mixin structure | unknown | ⚠️ |
| [SIGNAL_REGISTRY_GUIDE.md](architecture/SIGNAL_REGISTRY_GUIDE.md) | Qt signal inventory; cross-thread connection patterns | unknown | ⚠️ |
| [DATA_EXPORT_ARCHITECTURE.md](architecture/DATA_EXPORT_ARCHITECTURE.md) | Excel/CSV export pipeline; ExcelExporter | unknown | ⚠️ |
| [DATA_OUTPUT_STRUCTURE.md](architecture/DATA_OUTPUT_STRUCTURE.md) | Output file naming; folder layout; data schemas | unknown | ⚠️ |
| [DATA_OUTPUT_SYSTEM.md](architecture/DATA_OUTPUT_SYSTEM.md) | RecordingManager; file creation; session lifecycle | unknown | ⚠️ |
| [LIVE_DATA_FLOW_WALKTHROUGH.md](architecture/LIVE_DATA_FLOW_WALKTHROUGH.md) | End-to-end live data path: detector → UI | unknown | ⚠️ |
| [LIVE_DATA_CONDITIONS.md](architecture/LIVE_DATA_CONDITIONS.md) | Conditions gating live data display | unknown | ⚠️ |
| [MANUAL_INJECTION_DATA_FLOW_MAP.md](architecture/MANUAL_INJECTION_DATA_FLOW_MAP.md) | Data flow during manual injection; flag placement | unknown | ⚠️ |
| [OPTICAL_CONVERGENCE_ENGINE.md](architecture/OPTICAL_CONVERGENCE_ENGINE.md) | Older convergence engine doc — may overlap with LED_CONVERGENCE_ENGINE | unknown | 🔴 Suspected stale |
| [LED_CONVERGENCE_REFERENCE.md](architecture/LED_CONVERGENCE_REFERENCE.md) | Quick-reference companion to LED_CONVERGENCE_ENGINE | unknown | ⚠️ |
| [AFTERGLOW_FLEXIBLE_SEQUENCING.md](architecture/AFTERGLOW_FLEXIBLE_SEQUENCING.md) | Afterglow correction; flexible sequencing mode | unknown | ⚠️ |
| [BACKEND_SERVICE_CONTRACTS.md](architecture/BACKEND_SERVICE_CONTRACTS.md) | Service layer contracts; interface definitions | unknown | ⚠️ |
| [AFFILABS_CORE_BACKEND_ARCHITECTURE.md](architecture/AFFILABS_CORE_BACKEND_ARCHITECTURE.md) | Comprehensive backend overview | unknown | ⚠️ |
| [PRD_METHOD_BUILDER_DATA_FLOW.md](architecture/PRD_METHOD_BUILDER_DATA_FLOW.md) | Method builder dialog data flow | unknown | ⚠️ |
| [VISUAL_FLOW_GUIDE.md](architecture/VISUAL_FLOW_GUIDE.md) | Visual diagram guide for architecture flows | unknown | ⚠️ |
| [wavelength_mask_live_flow.md](architecture/wavelength_mask_live_flow.md) | Wavelength mask application in live data path | unknown | ⚠️ |

---

## Feature Docs & FRS (`docs/features/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [HARDWARE_SCANNING_FRS.md](features/HARDWARE_SCANNING_FRS.md) | USB device scanning; serial port detection; spectrometer + controller handshake | Feb 19 2026 | ✅ |
| [EDITS_TABLE_FRS.md](features/EDITS_TABLE_FRS.md) | Edits tab cycle table: layout, column schema, add/populate paths, filtering, color coding, compact view, context menu, timeline markers, alignment panel, save/export | Feb 19 2026 | ✅ |
| [EDITS_EXPORT_FRS.md](features/EDITS_EXPORT_FRS.md) | Edits tab export system: sidebar buttons, all export paths, per-channel format, TraceDrawer CSV spec and gap, Save as Method, external software CSV, image export | Feb 19 2026 | ✅ |
| [EDITS_ALIGNMENT_DELTA_SPR_FRS.md](features/EDITS_ALIGNMENT_DELTA_SPR_FRS.md) | Edits tab alignment & ΔSPR: time-shift mechanics, slider/input sync, reference subtraction priority, cursor lock (contact_time×1.1), bar chart update, processing cycle export | Feb 19 2026 | ✅ |
| [EDITS_DATA_LOADING_FRS.md](features/EDITS_DATA_LOADING_FRS.md) | Edits tab data utilities: _edits_flags delegation to FlagManager, delta_spr parsing (dict+stringified), flags display icons, save path resolution, user export dir, experiment folder creation, duration calculation cascade | Feb 19 2026 | ✅ |
| [EDITS_CYCLE_DISPLAY_FRS.md](features/EDITS_CYCLE_DISPLAY_FRS.md) | Main window → EditsTab bridge: cycle selection/rendering (402-line core with RU conversion, ref subtraction, time shift), Excel loading (3 sheet formats), segment creation/export (TraceDrawer CSV), reference traces (3 slots), flag placement, demo data | Feb 19 2026 | ✅ |
| [RECORDING_MANAGER_FRS.md](features/RECORDING_MANAGER_FRS.md) | Data recording & export system: 3-layer architecture (RecordingManager → DataCollector → ExcelExporter), 2 recording modes (file/memory), auto-save (60s intervals), 7-sheet Excel export (Raw Data, Channels XY, Cycles, Events, Flags, Analysis, Metadata), cycle deduplication, user experiment count tracking, t=0 timestamp normalization | Feb 19 2026 | ✅ |
| [EXCEL_CHART_BUILDER_FRS.md](features/EXCEL_CHART_BUILDER_FRS.md) | Excel export & chart generation: ExcelExporter (8-sheet recording export) + ExcelChartBuilder (4 chart types: delta SPR bars, timeline lines, flags scatter, overview); live vs post-edit export modes; openpyxl integration; TraceDrawer CSV format; incomplete flag chart series (known issue) | Feb 19 2026 | ✅ |
| [PUMP_HAL_FRS.md](features/PUMP_HAL_FRS.md) | AffiPump HAL: PumpHAL Protocol, AffipumpAdapter, Cavro address space (0x41-0x43), factory function, Tecan syringe pump integration | Feb 19 2026 | ✅ |
| [CONTROLLER_HAL_FRS.md](features/CONTROLLER_HAL_FRS.md) | Controller HAL: ControllerHAL Protocol, PicoP4SPRAdapter (sv+ss/sp servo commands), PicoEZSPRAdapter (KNX valve/pump, 2-ch), capability matrix, factory function | Feb 19 2026 | ✅ |
| [EDITS_UI_BUILDERS_FRS.md](features/EDITS_UI_BUILDERS_FRS.md) | EditsTab UIBuildersMixin: complete widget hierarchy, 6 panel builders, all 33 `self.*` widget references, Delta SPR cursors, alignment panel, bar chart implementation | Feb 19 2026 | ✅ |
| [FLAGGING_SYSTEM_GUIDE.md](features/FLAGGING_SYSTEM_GUIDE.md) | FlagManager: centralized flag state (live/edits contexts), Flag domain model, injection alignment (channel time shifts), AutoMarker, contact timer overlay, keyboard movement, ScatterPlotItem visuals | Feb 19 2026 | ✅ |
| [METHOD_PRESETS_SYSTEM.md](features/METHOD_PRESETS_SYSTEM.md) | Preset save/load; CycleTemplateStorage + QueuePresetStorage (TinyDB); import/export; browser dialogs | Feb 18 2026 | ✅ |
| [SENSOR_IQ_SYSTEM.md](features/SENSOR_IQ_SYSTEM.md) | SensorIQ: wavelength zone scoring (560-720nm), FWHM thresholds (30/60/80nm), 5 IQ levels, global singleton classifier, trend history, log_sensor_iq() | Feb 19 2026 | ✅ |
| [NOTES_TAB_FRS.md](features/NOTES_TAB_FRS.md) | Notes tab (ELN): 3-panel layout (nav/list/preview), experiment list with filtering/tags/ratings, Kanban stub, ELN text editor, recording hooks, star rating widget, tag pill editor, sensorgram preview | Feb 24 2026 | ✅ |
| [EXPERIMENT_INDEX_FRS.md](features/EXPERIMENT_INDEX_FRS.md) | ExperimentIndex data layer: CRUD for experiment entries, rating/tags/notes, planned entries, extended search, schema v2 with v1 migration | Feb 24 2026 | ✅ |
| [EXPERIMENT_BROWSER_FRS.md](features/EXPERIMENT_BROWSER_FRS.md) | Experiment browser dialog: search, load, filter past recordings from Edits tab | Feb 19 2026 | 🗂️ Planned — dialog not yet created |
| [TRANSPORT_BAR_FRS.md](features/TRANSPORT_BAR_FRS.md) | TransportBar (toolbar redesign): icon rail, transport controls, connection status, signal indicators | Feb 23 2026 | ✅ |
| [FLOATING_PANELS_FRS.md](features/FLOATING_PANELS_FRS.md) | SpectrumBubble, RailTimerPopup, LiveContextPanel, LiveRightPanel — floating overlays and docked panels | Feb 23 2026 | ✅ |
| [GUIDANCE_COORDINATOR_FRS.md](features/GUIDANCE_COORDINATOR_FRS.md) | GuidanceCoordinator: adaptive contextual hints, Pass A logging, Pass B widget wiring (planned) | Feb 23 2026 | ✅ |
| [ACCESSIBILITY_PANEL_FRS.md](features/ACCESSIBILITY_PANEL_FRS.md) | Accessibility panel: colour palettes (standard/colorblind/high-contrast), line style overrides, dark mode; `int(pen_style)` → `pen_style.value` fix noted | Feb 23 2026 | ✅ |
| [METHOD_BUILDER_REDESIGN_FRS.md](features/METHOD_BUILDER_REDESIGN_FRS.md) | Method Builder UI redesign: 3-zone layout, template gallery, Sparq bar, hardware-conditional mode combo | unknown | ⚠️ |
| [METHOD_BUILDER_FRS.md](features/METHOD_BUILDER_FRS.md) | Method Builder dialog: cycle editor, template save/load, queue preview | unknown | ⚠️ |
| [MICROFLUIDIC_CHANNELS_PANEL_FRS.md](features/MICROFLUIDIC_CHANNELS_PANEL_FRS.md) | Contact Monitor panel, per-channel contact timers, binding symbols, wash monitoring | unknown | ⚠️ |
| [COMPRESSION_ASSISTANT_FRS.md](features/COMPRESSION_ASSISTANT_FRS.md) | Compression Assistant: guided chip compression, gauge display, QC leak check | unknown | ⚠️ |
| [INJECTION_DETECTION_FRS.md](features/INJECTION_DETECTION_FRS.md) | Live injection detection FRS: threshold triggers, confidence gating, P4SPR vs PRO detection paths | unknown | ⚠️ |
| [LEAK_DETECTION_SYSTEM.md](features/LEAK_DETECTION_SYSTEM.md) | Leak detection: pressure monitoring, alert system, fluidic safety | unknown | ⚠️ |
| [SENSOR_CHIP_METADATA.md](features/SENSOR_CHIP_METADATA.md) | Sensor chip metadata: chip type, lot, chemistry, storage with session data | unknown | ⚠️ |
| [TIPS_SYSTEM.md](features/TIPS_SYSTEM.md) | In-app tips system: tip storage, display triggers, dismissal tracking | unknown | ⚠️ |
| [DEPLOYMENT_GRACEFUL_DEGRADATION.md](features/DEPLOYMENT_GRACEFUL_DEGRADATION.md) | Missing hardware fallback; partial boot behavior | unknown | ⚠️ |
| [CHANNEL_CLICK_SELECTION.md](features/CHANNEL_CLICK_SELECTION.md) | Channel selection via sensogram click | unknown | ⚠️ |
| [CYCLE_OF_INTEREST_FILTERING_WALKTHROUGH.md](features/CYCLE_OF_INTEREST_FILTERING_WALKTHROUGH.md) | Cycle-of-interest UI filter walkthrough | unknown | ⚠️ |
| [PROTECTED_FEATURES.md](features/PROTECTED_FEATURES.md) | License-gated feature flags; production protection | unknown | ⚠️ |
| [PERFORMANCE_TUNING_GUIDE.md](features/PERFORMANCE_TUNING_GUIDE.md) | UI update batching; GC disable; queue draining | unknown | ⚠️ |

---

## User Guides (`docs/user_guides/`)

> Written for human operators. Do NOT use as code reference — not verified against source.

| Document | Coverage Area |
|----------|--------------|
| [OPERATION_MANUAL.md](user_guides/OPERATION_MANUAL.md) | Full instrument operation manual |
| [QUICK_START.md](user_guides/QUICK_START.md) | Quick-start guide for new users |
| [POWER_ON_PROCEDURE.md](user_guides/POWER_ON_PROCEDURE.md) | Power-on and startup sequence |
| [INJECTION_METHODS.md](user_guides/INJECTION_METHODS.md) | Injection workflow guide (P4SPR vs P4PRO/PROPLUS) |
| [INJECTION_QUICK_REF.md](user_guides/INJECTION_QUICK_REF.md) | One-page injection quick reference card |
| [INJECT_FUNCTION_README.md](user_guides/INJECT_FUNCTION_README.md) | Inject function usage guide |
| [KINETIC_METHODS.md](user_guides/KINETIC_METHODS.md) | Kinetic binding experiment design |
| [TRAINING_GUIDE.md](user_guides/TRAINING_GUIDE.md) | Operator training guide |
| [DEMO_QUICK_START.md](user_guides/DEMO_QUICK_START.md) | Demo mode quick start |
| [DEMO_DATA_README.md](user_guides/DEMO_DATA_README.md) | Demo data description and usage |
| [BUILD_INSTALLER.md](user_guides/BUILD_INSTALLER.md) | Build and installer guide for developers |
| [SHIPPING_GUIDE.md](user_guides/SHIPPING_GUIDE.md) | Device shipping and packaging procedure |
| [QUICK_SHIP.md](user_guides/QUICK_SHIP.md) | Quick-ship checklist |
| [PRIVACY_POLICY.md](user_guides/PRIVACY_POLICY.md) | Privacy policy |
| [PHASE_4_TESTING_GUIDE.md](user_guides/PHASE_4_TESTING_GUIDE.md) | Phase 4 feature testing guide |
| [DEV_MODE_CONFIG_DIALOG.md](user_guides/DEV_MODE_CONFIG_DIALOG.md) | Developer mode configuration dialog |
| [CYCLE_RECREATION_GUIDE.md](user_guides/CYCLE_RECREATION_GUIDE.md) | Cycle recreation from archived data |
| [UX_WORKFLOW_TEST_PROTOCOL.md](user_guides/UX_WORKFLOW_TEST_PROTOCOL.md) | UX testing: Sparq IQ scoring, workflow readiness, user journey validation |
| [README.md](user_guides/README.md) | User guides overview |

> These docs are also cross-referenced in `docs/features/`:

| Document | Coverage Area |
|----------|--------------|
| [MANUAL_INJECTION_GUIDE.md](features/MANUAL_INJECTION_GUIDE.md) | P4SPR manual injection workflow (user-facing) |
| [CALIBRATION_TRAINING.md](features/CALIBRATION_TRAINING.md) | Calibration workflow training guide |
| [METHOD_BUILDING_TRAINING.md](features/METHOD_BUILDING_TRAINING.md) | Method builder training guide |
| [PUMP_TRAINING.md](features/PUMP_TRAINING.md) | AffiPump operation training |
| [UI_ADAPTER_EXAMPLES.md](features/UI_ADAPTER_EXAMPLES.md) | UIAdapter pattern examples |

---

## Roadmaps & Future Plans (`docs/future_plans/`)

> These describe planned or aspirational features. Do NOT assume they reflect current code.

| Document | Coverage Area |
|----------|-------------|
| [TIMELINE_ROADMAP.md](future_plans/TIMELINE_ROADMAP.md) | Phase 5+ timeline integration roadmap: presenter queries, InjectionCoordinator, clean refactor, 6 improvement proposals |
| [FUTURE_ENHANCEMENTS.md](future_plans/FUTURE_ENHANCEMENTS.md) | General feature backlog |
| [MAIN_PY_REFACTORING_OPPORTUNITIES.md](future_plans/MAIN_PY_REFACTORING_OPPORTUNITIES.md) | main.py decomposition opportunities |
| [AFFILABS_ANALYZE_UI_SPEC.md](future_plans/AFFILABS_ANALYZE_UI_SPEC.md) | AffiLabs Analyze companion app UI spec |
| [AFFILABS_DATA_ANALYSIS_MODULE.md](future_plans/AFFILABS_DATA_ANALYSIS_MODULE.md) | Data analysis module design |
| [ANIML_SILA_IMPLEMENTATION_PLAN.md](future_plans/ANIML_SILA_IMPLEMENTATION_PLAN.md) | AnIML / SiLA 2 protocol integration plan |
| [AUTOSAMPLER_INTEGRATION_PLAN.md](future_plans/AUTOSAMPLER_INTEGRATION_PLAN.md) | Autosampler hardware + software integration plan |
| [DEMO_MODE_PLAN.md](future_plans/DEMO_MODE_PLAN.md) | Demo mode implementation plan |
| [ADAPTIVE_GUIDANCE_PLAN.md](future_plans/ADAPTIVE_GUIDANCE_PLAN.md) | Adaptive contextual guidance system design |
| [SIDEBAR_REDESIGN_PLAN.md](future_plans/SIDEBAR_REDESIGN_PLAN.md) | Sidebar v2.1 redesign plan |
| [SPARQ_AI_UPGRADE_PLAN.md](future_plans/SPARQ_AI_UPGRADE_PLAN.md) | Sparq AI assistant upgrade roadmap |
| [21CFR_PART11_GAP_ANALYSIS.md](future_plans/21CFR_PART11_GAP_ANALYSIS.md) | 21 CFR Part 11 compliance gap analysis; implementation order |
| [IQOQ_PLAN.md](future_plans/IQOQ_PLAN.md) | IQ/OQ validation plan: check IDs, test suites, report format |
| [LICENSE_STRATEGY.md](future_plans/LICENSE_STRATEGY.md) | Software licensing strategy |
| [ONLINE_DEPLOYMENT_GUIDE.md](future_plans/ONLINE_DEPLOYMENT_GUIDE.md) | Cloud/remote deployment guide |
| [SHAREPOINT_UPLOAD_SETUP.md](future_plans/SHAREPOINT_UPLOAD_SETUP.md) | SharePoint auto-upload setup |
| [SHAREPOINT_WIX_INTEGRATION_GUIDE.md](future_plans/SHAREPOINT_WIX_INTEGRATION_GUIDE.md) | SharePoint + Wix integration |
| [TICKET_SYSTEM_DESIGN.md](future_plans/TICKET_SYSTEM_DESIGN.md) | In-app support ticket system design |
| [CUSTOMER_DATA_REVIEW_PLAN.md](future_plans/CUSTOMER_DATA_REVIEW_PLAN.md) | Plan for reviewing and managing customer data |
| [SPARK_WORKFLOW_ROADMAP.md](features/SPARK_WORKFLOW_ROADMAP.md) | Spark AI assistant planned capabilities |
| [SYSTEM_INTELLIGENCE_INTEGRATION.md](features/SYSTEM_INTELLIGENCE_INTEGRATION.md) | SensorIQ + Spark AI integration architecture (planned) |
| [SYSTEM_INTELLIGENCE_QUICKSTART.md](features/SYSTEM_INTELLIGENCE_QUICKSTART.md) | Quick-start for Spark / SensorIQ features |

---

## Calibration Docs (`docs/calibration/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [CALIBRATION_ORCHESTRATOR_FRS.md](calibration/CALIBRATION_ORCHESTRATOR_FRS.md) | 6-step orchestrator; CalibrationService threading; servo auto-cal fallback; pump prime parallel flow | Feb 19 2026 | ✅ |
| [CALIBRATION_MASTER.md](calibration/CALIBRATION_MASTER.md) | Comprehensive calibration system description — 3939 lines (superseded by CALIBRATION_ORCHESTRATOR_FRS) | Nov 2025 | 🔴 Superseded |
| [CALIBRATION_GUIDE.md](calibration/CALIBRATION_GUIDE.md) | User-facing calibration guide | unknown | ⚠️ |
| [CALIBRATION_LOGIC_LOCKED.md](calibration/CALIBRATION_LOGIC_LOCKED.md) | Lock/protect constraints on calibration logic | unknown | ⚠️ |
| [CALIBRATION_SYSTEMS_SUMMARY.md](calibration/CALIBRATION_SYSTEMS_SUMMARY.md) | Summary of all calibration subsystems | unknown | ⚠️ |
| [OEM_OPTICAL_CALIBRATION_GUIDE.md](calibration/OEM_OPTICAL_CALIBRATION_GUIDE.md) | OEM calibration procedure for production builds | unknown | ⚠️ |
| [STARTUP_CALIBRATION_TROUBLESHOOTING.md](calibration/STARTUP_CALIBRATION_TROUBLESHOOTING.md) | Troubleshooting calibration failures at startup | unknown | ⚠️ |

---

## UI Docs (`docs/ui/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [UI_DESIGN_SYSTEM.md](ui/UI_DESIGN_SYSTEM.md) | Color palette, typography, spacing, button variants, input fields, status indicators — all rules for consistent styling | Feb 19 2026 | ✅ |
| [UI_COMPONENT_INVENTORY.md](ui/UI_COMPONENT_INVENTORY.md) | Every sidebar tab, main page, reusable widget, dialog, and presenter — what it does, what rules govern it, and when things are enabled/disabled | Feb 23 2026 | ✅ |
| [UI_STATE_MACHINE.md](ui/UI_STATE_MACHINE.md) | Every application state (disconnected → searching → connected → calibrated → acquiring → recording/paused), all transition triggers, and exact UI changes at each transition | Feb 19 2026 | ✅ |
| [UI_GRAPH_VISUALIZATION_SPEC.md](ui/UI_GRAPH_VISUALIZATION_SPEC.md) | All 7 graphs: axes, units, channel colors (standard + colorblind), update architecture (10 Hz throttle), cursor behavior, cycle shading, anti-patterns | Feb 19 2026 | ✅ |
| [UI_HARDWARE_MODEL_REQUIREMENTS.md](ui/UI_HARDWARE_MODEL_REQUIREMENTS.md) | Per-model UI differences: P4SPR / P4PRO / P4PROPLUS — mode combo locking, pump/valve visibility, fluidics subunit, AffiPump detection, injection channel pairing, internal pump constraints | Feb 19 2026 | ✅ |
| [UX_USER_JOURNEY.md](ui/UX_USER_JOURNEY.md) | User journey across 6 experiment stages (Connect → Calibrate → Acquire → Inject → Record → Export); what users need at each stage | Feb 19 2026 | ✅ |

---

## Hardware Docs (`docs/hardware/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [P4PRO_FLUIDIC_ARCHITECTURE.md](hardware/P4PRO_FLUIDIC_ARCHITECTURE.md) | P4PRO fluidic system: KC1/KC2, 6-port loop, 3-way valves, channel mapping | Feb 19 2026 | ✅ |
| [P4PRO_Firmware_Documentation.md](hardware/P4PRO_Firmware_Documentation.md) | P4PRO firmware command reference | unknown | ⚠️ |
| [P4SPR_Firmware_Documentation.md](hardware/P4SPR_Firmware_Documentation.md) | P4SPR firmware command reference | unknown | ⚠️ |
| [FIRMWARE_V2.2_NOTES.md](hardware/FIRMWARE_V2.2_NOTES.md) | Firmware V2.2 change notes | unknown | ⚠️ |
| [FIRMWARE_V2.4_CYCLE_SYNC.md](hardware/FIRMWARE_V2.4_CYCLE_SYNC.md) | Firmware V2.4 CYCLE_SYNC acquisition mode | unknown | ⚠️ |
| [EEPROM_DEVICE_CONFIG_SPEC.md](hardware/EEPROM_DEVICE_CONFIG_SPEC.md) | EEPROM device config spec: layout, write protocol, fallback | unknown | ⚠️ |
| [EEPROM_IMPLEMENTATION_SUMMARY.md](hardware/EEPROM_IMPLEMENTATION_SUMMARY.md) | EEPROM implementation summary | unknown | ⚠️ |
| [INTERNAL_PUMP_ARCHITECTURE.md](hardware/INTERNAL_PUMP_ARCHITECTURE.md) | P4PROPLUS internal pump architecture | unknown | ⚠️ |
| [INTERNAL_PUMP_UI_SYNC_ISSUES.md](hardware/INTERNAL_PUMP_UI_SYNC_ISSUES.md) | Known UI sync issues with internal pumps | unknown | ⚠️ |
| [P4PROPLUS_PUMP_COMMANDS_CORRECT.md](hardware/P4PROPLUS_PUMP_COMMANDS_CORRECT.md) | Correct P4PROPLUS pump command sequences | unknown | ⚠️ |
| [P4PROPLUS_QUICK_REF.md](hardware/P4PROPLUS_QUICK_REF.md) | P4PROPLUS quick reference card | unknown | ⚠️ |
| [PUMP_CONTROL_ARCHITECTURE.md](hardware/PUMP_CONTROL_ARCHITECTURE.md) | Pump control architecture (P4PRO + P4PROPLUS) | unknown | ⚠️ |
| [PUMP_IMPROVEMENTS_FROM_CAVRO.md](hardware/PUMP_IMPROVEMENTS_FROM_CAVRO.md) | Cavro syringe pump improvement notes | unknown | ⚠️ |
| [DEVICE_DATABASE_REGISTRATION.md](hardware/DEVICE_DATABASE_REGISTRATION.md) | Device registry + device_history.db workflows | unknown | ⚠️ |
| [HIGH_SENSITIVITY_REFINEMENTS.md](hardware/HIGH_SENSITIVITY_REFINEMENTS.md) | High-sensitivity detector refinements | unknown | ⚠️ |
| [CONVERGENCE_STARTUP_SAFETY_IMPROVEMENTS.md](hardware/CONVERGENCE_STARTUP_SAFETY_IMPROVEMENTS.md) | Convergence safety improvements at startup | unknown | ⚠️ |
| [README_HARDWARE_BEHAVIOR.md](hardware/README_HARDWARE_BEHAVIOR.md) | Hardware behavior overview README | unknown | ⚠️ |

---

## Product Requirements (`docs/product_requirements/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [SPARQ_PRD.md](product_requirements/SPARQ_PRD.md) | Sparq AI assistant product requirements | unknown | ⚠️ |
| [LENSLESS_SPECTRAL_SPR_SYSTEM_REQUIREMENTS.md](product_requirements/LENSLESS_SPECTRAL_SPR_SYSTEM_REQUIREMENTS.md) | System requirements spec (SRS) for lensless spectral SPR instrument | unknown | ⚠️ |
| [NOTION_IMPORT.md](product_requirements/NOTION_IMPORT.md) | Legacy Notion content import | unknown | ⚠️ |
| [README.md](product_requirements/README.md) | Product requirements overview | unknown | ⚠️ |

---

## Setup Docs (`docs/setup/`)

| Document | Coverage Area |
|----------|--------------|
| [SMTP_SETUP_GUIDE.md](setup/SMTP_SETUP_GUIDE.md) | SMTP email configuration for notifications |

---

## Root Docs (`docs/`)

| Document | Coverage Area | Last Updated | Verified |
|----------|--------------|-------------|----------|
| [TERMINOLOGY.md](TERMINOLOGY.md) | Standard doc type labels; document taxonomy | Feb 19 2026 | ✅ |
| [DOCUMENT_INDEX.md](DOCUMENT_INDEX.md) | This file | Feb 24 2026 | — |

---

## Planned / Critical Gaps

| Document (to create) | Priority | Rationale |
|----------------------|----------|-----------|
| `architecture/APPLICATION_STATE_MIGRATION.md` | MEDIUM | `ApplicationState` dataclass vs `self.*` coexistence — no doc; migration incomplete |
| `architecture/MIXIN_SYSTEM.md` | LOW | main.py + affilabs_core_ui.py mixin patterns; how to add a new mixin; extraction guide |

---

## Maintenance Rules

1. **Add a row** for every new doc created — never let the index fall behind.
2. **Update Verified** to ✅ after a code-verification pass; set date to verification date.
3. **Set 🔴 Stale** when you know code has changed substantially since the doc was written.
4. **Delete rows** only when the actual file is deleted.
5. **Planned rows** move to their section once the file is created.
