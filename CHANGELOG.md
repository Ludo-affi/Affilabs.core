# Changelog

All notable changes to Affilabs.core are documented in this file.

---

## [2.0.5] — 2026-02-24

**Locked release for customer delivery.** Primary target: P4SPR. Compatible: P4PRO + AffiPump.

### Added
- **Notes tab (ELN)** — Experiment log with star ratings, tag filtering, sensorgram preview, Kanban view stub
- **Experiment Index** — Searchable record of all recording sessions (schema v2 with migration)
- **Accessibility panel** — Colour palette selector (standard / colorblind / high-contrast), line style overrides
- **Binding plot enhancements** — Concentration unit selector (nM / µM / pM), kinetics fitting (ka / kd / KD from association phases)
- **Injection action bar** — Contact Monitor with per-channel timers, binding symbols, wash detection
- **Live optical leak detection** — Signal-drop threshold alerting per channel
- **Timeline domain model** — Phases 1–4 complete (event stream, CycleMarker, flag integration, recording bridge)
- **TransportBar & floating panels** — New toolbar layout, SpectrumBubble, RailTimerPopup (stubs wired)
- **GuidanceCoordinator** — Pass A (logging) for adaptive contextual hints
- **SensorIQ quality scoring** — 5-level wavelength zone classification with FWHM thresholds
- **Selective cycle export** — Checkbox selection in Edits tab for per-cycle export
- **Demo concentration series** — Visually distinct curves per concentration level
- **About section** — Version info, support contact, and system details in Settings tab

### Changed
- **Method Builder redesign** — 3-zone layout, template gallery, Sparq integration bar
- **Edits tab** — Active cycle baseline, legend polish, cursor behaviour improvements
- **Spectroscopy plots** relocated from Settings tab to LiveContextPanel
- **Hardware Status** section merged into Settings tab (Phase 5)
- **Sparq AI** — TinyLM removed (caused 30s UI freezes); now pattern-matching + curated knowledge base only
- **Version** dropped "beta" tag — this is the locked customer release

### Fixed
- `int(pen_style)` → `pen_style.value` crash in colour palette (PySide6 enum incompatibility)
- Kinetics fit crash — invalid `getattr(None)` chain
- `IndentationError` in `injection_coordinator.py` — stray import outside `TYPE_CHECKING` block
- Build spec — removed missing servo_cal folder, fixed libusb lookup, added data/ bundle
- Injection lifecycle timeout — `done_event.wait()` now includes contact_time + 120s margin
- Contact time calculation uses 80% usable loop volume
- Bar chart label cutoff — increased spacing and padding
- Individual channel time shift applied only to selected channel
- Alignment panel loads saved shift values correctly
- USB timeout handling and OEM dialog improvements

---

## [2.0.4] — 2026-02-16

### Added
- Method builder enhancements — save/load templates, preset browser

---

## [2.0.3] — 2026-02-12

### Fixed
- UI cleanup, dialog deduplication, injection timing, timer and cycle fixes

---

## [2.0.2] — 2026-02-09

### Added
- User profile system — experiment count tracking, compression training progression
- Reference subtraction in Edits tab
- Flow tab UI polish, overnight mode relocation to dialog
- Compression Assistant UI with sweet spot adjustment controls

### Fixed
- Splash screen — replaced grey splash with blue splash, 3s minimum display
- Edits cycle graph reads live buffer when raw_data_rows is empty
- Piper TTS crash hardening (0xC0000409)

---

## [2.0.1] — 2026-02-09

### Added
- Splash protein art, export cleanup, UI fixes

---

## [2.0.0] — 2026-02-06

### Added
- **Edits tab** — Full post-acquisition analysis: cycle table, alignment, ΔSPR cursors, binding plot, export
- **Method Builder** — Cycle editor, queue system, preset save/load
- **Sparq AI assistant** — Pattern-matching Q&A with knowledge base, TTS (later removed)
- **Semi-automated injection** — P4PRO 6-port valve + AffiPump orchestration
- **Convergence engine** — ML-assisted LED convergence with S-pol + P-pol calibration
- **Recording system** — 3-layer architecture, auto-save, 7-sheet Excel export
- **Device configuration** — Per-device JSON config, EEPROM fallback, OEM calibration workflow
- **Configurable channel selection** — AC/BD pairing for P4PRO 3-way valves
- **Cycle auto-advance** — Timer-driven progression through method queue

### Fixed
- Servo double-conversion bug causing false recalibration
- Convergence early bail-out when polarizer blocks light
- P-mode convergence freeze bugs
- Servo positioning — persist S/P positions across startup

---

## [1.0.1] — 2025-12-XX

### Changed
- Consolidated entry point: `main_simplified.py` → `main.py`

---

## [1.0.0-alpha] — 2025-11-XX

**First fully functional core system.**

### Added
- 4-channel SPR acquisition (LED A/B/C/D, CYCLE_SYNC mode)
- Flame-T + USB4000 spectrometer support
- P4SPR manual injection workflow
- Startup calibration (6-step LED convergence)
- Basic data export (Excel)
- Spectroscopy and sensogram live graphs
- Calibration optimization + baseline correction

---

## [0.1.0] — 2025-XX-XX

**Initial release — proof of concept.**

### Added
- Core SPR measurement pipeline
- Serial communication with PicoP4SPR controller
- Basic UI shell (PySide6)
- Dark subtraction + transmission calculation
