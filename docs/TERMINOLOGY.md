# Affilabs.core — Terminology Reference

**Owner:** Affinite Instruments  
**Last Updated:** February 19, 2026  
**Purpose:** Canonical definitions for terms used across documentation, code, and communications. When in doubt, this file wins.

---

## 📋 Table of Contents

1. [Document Types](#1-document-types)
2. [Product & Brand Names](#2-product--brand-names)
3. [Hardware Terms](#3-hardware-terms)
4. [Optical & SPR Physics](#4-optical--spr-physics)
5. [Signal Processing](#5-signal-processing)
6. [Software Architecture](#6-software-architecture)
7. [Experiment & Data Terms](#7-experiment--data-terms)
8. [Instrument Models](#8-instrument-models)

---

## 1. Document Types

| Term | Abbreviation | Definition | Examples in this project |
|------|-------------|------------|--------------------------|
| **Product Requirements Document** | PRD | User-facing feature vision — personas, problem statement, roadmap, scope boundaries. Answers *what* we're building and *for whom*. Not an implementation spec. | `SPARQ_PRD.md` |
| **Functional Requirements Specification** | FRS | Software behavioral spec — what the UI must do, workflow logic, state machines, acceptance criteria. Answers *how the software behaves*. | `MANUAL_INJECTION_STATE_MACHINE.md` |
| **System Requirements Specification** | SRS | Hardware + software system specs — performance targets, signal chain, hardware interfaces, operating conditions. Answers *how the system performs*. IEEE 830 standard. | `LENSLESS_SPECTRAL_SPR_SYSTEM_REQUIREMENTS.md` |
| **Architecture Specification** | Arch Spec | Internal design — data flows, component boundaries, transformation pipelines, class responsibilities. For developers, not users. | `PRD_METHOD_BUILDER_DATA_FLOW.md` |
| **Concept Document** | — | Future-looking exploration of unbuilt technology or features. Not a commitment. Planning phase only. | *(none currently)* |
| **Feature Specification** | — | Detailed documentation of a shipped feature — how it works, configuration, edge cases. Reference for maintainers. | `docs/features/*.md` |

> **Rule:** Use the right type. A doc that describes UI behavior is an FRS, not a PRD. A doc about data flow is an Arch Spec, not a PRD. PRD = user-facing vision only.

---

## 2. Product & Brand Names

| Term | Definition | Notes |
|------|-----------|-------|
| **Affilabs.core** | Official software product name | Always written as `Affilabs.core` — capital A, lowercase c, with dot. The workspace folder `ezControl-AI` is a legacy alias; do not use it in communications or docs. |
| **Sparq** | The AI assistant embedded in Affilabs.core | Branded as **Sparq⚡**. Lettermark: stylized SPR sensorgram dip curve connects the tail of **p** to **q**. In code: `SparkAnswerEngine`, `SparkHelpWidget` (legacy naming, not yet renamed). |
| **AffiPump** | External syringe pump controller library | The library (`AffiPump/`) and the physical pump (Tecan/Cavro protocol). Used on P4PRO. |
| **Affinite Instruments** | The company | Do not abbreviate to "Affinite" in external docs without context. |
| **TracerDrawer** | External kinetics analysis software used by customers | Not made by Affinite. The Excel export format must be TracerDrawer-compatible. No code references exist — it is a compatibility target only. |

---

## 3. Hardware Terms

| Term | Definition | Notes |
|------|-----------|-------|
| **Controller** | The embedded microcontroller board inside the instrument | Identified at runtime by `ctrl_type`. Current models: `PicoP4SPR`, `PicoEZSPR`, `PicoP4PRO`. |
| **Detector** | The spectrometer that reads the optical signal | Ocean Optics Flame-T (primary), USB4000, Phase Photonics. Not a camera — a linear CCD array. |
| **Servo** | The digital servo motor that rotates the polarizer | Default model: HS-55MG. Controlled via PWM (1–255 = 5°–175°). |
| **Polarizer** | The optical element that the servo rotates | Two types: barrel (linear polarizer film in cylindrical housing) and circular (wave-retarder based). |
| **LED** | White broadband LED light source | 4 channels (A, B, C, D). All identical white-light LEDs — no color differences between channels. Never fire simultaneously. |
| **6-port valve** | Rotary valve that switches between buffer and sample | Present on P4PRO and P4PROPLUS only. Actuated by controller command. |
| **Flow cell** | The microfluidic channel on the sensor chip surface | One per optical channel. Fully independent — no cross-talk. |
| **Sensor chip** | Gold-coated glass substrate that sits on the prism | ~47–50 nm Au on 1–2 nm Cr on borosilicate glass. User-functionalized with binding chemistry. |
| **Prism** | BK7 glass optical coupling element | Holds the sensor chip against its flat face. Kretschmann geometry. n ≈ 1.515 at 633 nm. |
| **Fiber** | Bifurcated fiber optic bundle | 4 input branches (one per channel) → 1 output trunk → spectrometer. 100 µm or 200 µm core. |

---

## 4. Optical & SPR Physics

| Term | Definition | Notes |
|------|-----------|-------|
| **SPR** | Surface Plasmon Resonance | A quantum of charge-density oscillation (plasmon) at the gold/buffer interface, excited by P-polarized evanescent light. |
| **Resonance wavelength** | The wavelength at which SPR coupling is maximum, producing the dip minimum | The Y-axis of a sensorgram. Units: nm. |
| **Kretschmann configuration** | The prism-coupling geometry used in this system | Light enters through the prism base at TIR angle; evanescent field excites plasmons at the gold underside. |
| **P-polarization (TM mode)** | Electric field parallel to the plane of incidence | Couples to surface plasmons. Produces the SPR dip. |
| **S-polarization (TE mode)** | Electric field perpendicular to the plane of incidence | Does NOT couple to surface plasmons at this geometry. Used as intensity reference. |
| **S-ref** | The S-polarization reference spectrum captured during calibration | Stored in `CalibrationData.s_ref`. Used as per-pixel divisor for every P-pol frame. Session-persistent and stable — insensitive to binding events. |
| **P/S ratio** | The per-pixel ratio of P-pol counts to S-pol counts | Cancels LED intensity drift. The transmission spectrum. |
| **Transmission spectrum** | P/S ratio expressed as percentage (0–100%) | The SPR dip appears as a minimum in this spectrum. |
| **SPR dip** | The broadband absorption feature in the transmission spectrum at the resonance wavelength | ~20–40 nm FWHM. A minimum, not a maximum. |
| **Blue shift on binding** | When analyte binds, resonance wavelength decreases (moves shorter) | Opposite convention to angular SPR (Biacore). Injection detection looks for a wavelength DROP. |
| **Evanescent field** | The exponentially-decaying electromagnetic field that extends ~100–200 nm above the gold surface into the buffer | Only the evanescent field couples to plasmons — bulk solution beyond this depth does not contribute. |
| **Spectral range** | 560–720 nm | The SPR-active window for gold at this geometry. Data outside this range is not used for peak finding. |

---

## 5. Signal Processing

| Term | Definition | Notes |
|------|-----------|-------|
| **Dark subtraction** | Subtracting a dark-current spectrum (LED off) from each raw frame | Removes detector thermal noise and fixed-pattern noise. |
| **Baseline correction** | Normalizing the transmission spectrum to remove slow drift | Methods: `percentile`, `polynomial`, `off_spr`, `none`. |
| **Savitzky-Golay smoothing** | Polynomial smoothing filter applied to the transmission spectrum | Reduces high-frequency noise while preserving dip shape. |
| **Peak finding / dip finding** | Algorithm to locate the resonance wavelength minimum | Synonymous in this codebase. Operates on the transmission dip. |
| **Pipeline** | One complete peak-finding algorithm from spectrum → wavelength | Named variants: `centroid`, `fourier`, `polynomial`, `hybrid`, `consensus`. |
| **Centroid pipeline** | Weighted centroid of the dip region | Default. Robust to noise. |
| **Consensus pipeline** | Aggregates outputs of multiple pipelines, weighted by confidence | Most stable but highest compute. |
| **Integration time** | The exposure duration for each spectrometer frame | Range: 1–60 ms (software-enforced). Tuned during LED calibration. |
| **num_scans** | Number of spectral frames averaged per polarization position per LED | Set during calibration, stored in `CalibrationData.num_scans`. Typical: 1–5. |
| **LED boost correction** | Per-channel intensity correction factor applied when computing P/S ratio | Compensates for LED-to-LED brightness variation. |

---

## 6. Software Architecture

| Term | Definition | Notes |
|------|-----------|-------|
| **HAL** | Hardware Abstraction Layer | Interfaces in `affilabs/utils/hal/`. Decouples business logic from hardware-specific serial commands. |
| **Coordinator** | Event orchestration class — wires signals between managers, presenters, and widgets | Pattern: `*_event_coordinator.py`. Does not contain business logic itself. |
| **Presenter** | Mediates between a data source and a UI widget | Pattern: `*_presenter.py`. Follows MVP pattern. |
| **Mixin** | A class fragment extracted for large-class split | Used in `main.py` (PumpMixin, FlagMixin, CalibrationMixin, CycleMixin) and `affilabs_core_ui.py` (PanelBuilderMixin, DeviceStatusMixin, etc.). |
| **Manager** | Owns lifecycle and state for a subsystem | Examples: `DataAcquisitionManager`, `HardwareManager`, `RecordingManager`. |
| **Service** | Stateless or thin-state component for a specific operation | Examples: `ExcelExporter`, `CalibrationService`. |
| **Pipeline** | A peak-finding algorithm chain | In `affilabs/utils/pipelines/`. Each is a standalone callable: spectrum in → wavelength out. |
| **ApplicationState** | Target dataclass-based state container (`app_state.py`) | Migration from scattered `self.*` in `main.py` is incomplete — both coexist in v2.0.5. |
| **CalibrationData** | Dataclass holding all calibration outputs | Contains `s_ref`, `dark`, `led_intensities`, `num_scans`, servo positions, etc. |
| **CYCLE_SYNC mode** | V2.4+ firmware acquisition mode (default) | Synchronized LED firing tied to firmware cycle counter. More stable timing. |
| **EVENT_RANK mode** | Fallback acquisition mode | Used when firmware does not support CYCLE_SYNC. Controlled by `USE_CYCLE_SYNC` flag. |

---

## 7. Experiment & Data Terms

| Term | Definition | Notes |
|------|-----------|-------|
| **Sensorgram** | Plot of resonance wavelength (nm) vs. time | The primary measurement output. Y-axis in nm (not RU). |
| **Resonance unit (RU)** | Conversion: 1 nm ≈ 355 RU | System-specific. Used for comparison with angular SPR literature. Not the native unit. |
| **Cycle** | A labeled time segment in an experiment | Types: `Bind`, `Regen`, `Blank`, `Reference`, `Wash`, etc. Defined in Method Builder. |
| **Method** | A sequence of cycles defining one injection experiment | Authored in the Method Builder dialog and stored as a queue of `Cycle` objects. |
| **Queue** | The ordered list of cycles loaded for execution | Managed by the cycle queue system. Supports undo/redo via `CommandHistory`. |
| **Injection** | A fluidic event where sample is introduced to the flow cell | Detected algorithmically (wavelength drop) and/or triggered by the 6-port valve. |
| **Flag** | A user or system-placed annotation on the sensorgram timeline | Stored in the `Flags` Excel sheet. Labeled, colored, with optional note. |
| **S-ref staleness** | (NOT a concern) The S-pol reference captured at calibration is physics-insensitive to binding and session duration | Recalibration needed only for hardware changes (new chip, unplugged fiber, optical disturbance). |
| **Recording session** | The time span between "Start Recording" and "Stop Recording" | One `.xlsx` file per session. |
| **Excel export** | The `.xlsx` workbook produced at end of session | 8 sheets: Raw Data, Channels XY, Cycles, Flags, Events, Analysis, Metadata, Alignment. Must be TracerDrawer-compatible. |
| **Alignment** | Per-cycle time-shift and channel-filter settings from the Edits tab | Stored in Sheet 8 ("Alignment") of the exported workbook. |
| **Channels XY** | Wide-format Excel sheet pairing each channel's time and wavelength columns | The format TracerDrawer expects. Column names: `Time A (s)`, `Channel A (nm)`, etc. |

---

## 8. Instrument Models

| Term | Definition |
|------|-----------|
| **P4SPR** | 4-channel instrument with manual syringe injection. Each of 4 channels has an independent fluidic path. Adding AffiPump unlocks semi-automated mode. Primary development target. |
| **P4PRO** | 4-channel instrument with 6-port rotary valve + AffiPump (external syringe pump). 2 fluidic pairs: AC and BD. Accurate, pulse-free flow. |
| **P4PROPLUS** | 4-channel instrument with 6-port rotary valve + built-in peristaltic pumps. Dispense-only, preset flow rates. Lower flow quality (pulsatile). |
| **EzSPR** | Legacy instrument. <5 units in field. Lowest development priority. |
| **KNX2** | Legacy instrument. <5 units in field. Lowest development priority. |

> **Priority order:** P4SPR (1st) → P4PRO (2nd) → P4PROPLUS (3rd) → EzSPR / KNX2 (deprioritized)

---

*Add new terms here as they are defined. When a term changes meaning, update this file and note the date.*
