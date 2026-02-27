# Affilabs.core v2.0.5 Beta — Release Readiness Report

**Date:** February 24, 2026  
**Target:** Locked release for customer delivery  
**Primary hardware:** P4SPR (manual syringe injection)  
**Compatible hardware:** P4PRO + AffiPump (basic support, full suite → v3.0)  
**Next versions:** v3.0 = full P4PRO/AffiPump integration · v4.0 = autosampler

---

## Version Roadmap

| Version | Scope | Hardware Target | Status |
|---------|-------|----------------|--------|
| **2.0.5** | Feature-locked beta — ship as-is | P4SPR (primary), P4PRO+AffiPump (compatible) | **THIS RELEASE** |
| 3.0 | Full P4PRO + AffiPump automated injection suite | P4PRO, P4PROPLUS, AffiPump | Planned |
| 4.0 | Autosampler integration | All models + autosampler | Planned |

---

## 1. What's DONE and Shipping ✅

### Core Instrument Functions
| Feature | Doc Coverage | Code Status |
|---------|-------------|-------------|
| 4-channel SPR acquisition (LED A/B/C/D) | SPR_SIGNAL_PROCESSING_PIPELINE.md ✅ | Shipping |
| Startup calibration (6-step LED convergence) | CALIBRATION_ORCHESTRATOR_FRS.md ✅ | Shipping |
| OEM device calibration (servo + LED model) | CALIBRATION_GUIDE.md ✅ | Shipping |
| Flame-T + USB4000 detector support | Detector profiles JSON ✅ | Shipping |
| P4SPR manual injection workflow | MANUAL_INJECTION_STATE_MACHINE.md ✅ | Shipping |
| P4PRO/AffiPump basic automated injection | PUMP_HAL_FRS.md + CONTROLLER_HAL_FRS.md ✅ | Shipping |
| Injection auto-detection (λ-threshold v1) | INJECTION_AUTO_DETECTION_FRS.md ✅ | Shipping |
| Contact timer + binding symbols | MICROFLUIDIC_CHANNELS_PANEL_FRS.md ✅ | Shipping |
| AutoMarker flag placement | FLAGGING_SYSTEM_GUIDE.md ✅ | Shipping |
| Live optical leak detection | LEAK_DETECTION_SYSTEM.md ✅ | Shipping |

### Data & Export
| Feature | Doc Coverage | Code Status |
|---------|-------------|-------------|
| Live recording (auto-save every 60s) | RECORDING_MANAGER_FRS.md ✅ | Shipping |
| 7-sheet Excel export | EXCEL_CHART_BUILDER_FRS.md ✅ | Shipping |
| TraceDrawer CSV export | EDITS_EXPORT_FRS.md ✅ | Shipping |
| PNG/SVG graph export | EDITS_EXPORT_FRS.md ✅ | Shipping |
| Clipboard copy | EDITS_EXPORT_FRS.md ✅ | Shipping |

### Edits Tab (Post-Acquisition Analysis)
| Feature | Doc Coverage | Code Status |
|---------|-------------|-------------|
| Cycle table with filtering | EDITS_TABLE_FRS.md ✅ | Shipping |
| Channel alignment (time-shift) | EDITS_ALIGNMENT_DELTA_SPR_FRS.md ✅ | Shipping |
| ΔSPR bar chart + cursors | EDITS_ALIGNMENT_DELTA_SPR_FRS.md ✅ | Shipping |
| Binding plot + Kd fitting | EDITS_BINDING_PLOT_FRS.md ✅ | Shipping |
| Cycle display + reference traces | EDITS_CYCLE_DISPLAY_FRS.md ✅ | Shipping |
| Save as Method | EDITS_EXPORT_FRS.md ✅ | Shipping |

### Method Builder & Queue
| Feature | Doc Coverage | Code Status |
|---------|-------------|-------------|
| Method Builder dialog | METHOD_BUILDER_FRS.md + METHOD_BUILDER_REDESIGN_FRS.md ✅ | Shipping |
| Cycle templates (save/load) | METHOD_PRESETS_SYSTEM.md ✅ | Shipping |
| Queue presets | METHOD_PRESETS_SYSTEM.md ✅ | Shipping |
| Mid-run cycle append | CLAUDE.md §Key Gotchas #11 ✅ | Shipping |

### UI & UX
| Feature | Doc Coverage | Code Status |
|---------|-------------|-------------|
| Sensogram + Spectroscopy graphs | UI_GRAPH_VISUALIZATION_SPEC.md ✅ | Shipping |
| Hardware state machine (6 states) | UI_STATE_MACHINE.md ✅ | Shipping |
| Accessibility panel (color palettes) | ACCESSIBILITY_PANEL_FRS.md ✅ | Shipping |
| Sparq AI assistant (pattern-matching Q&A) | Spark service files ✅ | Shipping |
| SensorIQ quality scoring | SENSOR_IQ_SYSTEM.md ✅ | Shipping |
| Notes tab (ELN + experiment index) | NOTES_TAB_FRS.md + EXPERIMENT_INDEX_FRS.md ✅ | Shipping |

### Hardware Support
| Model | Support Level | Notes |
|-------|-------------|-------|
| **P4SPR** | **Full** (primary target) | Manual injection, 4 independent fluidic channels |
| **P4PRO** | Compatible | 6-port valve + AffiPump basic injection works |
| **P4PROPLUS** | Compatible | Internal pump commands implemented |
| EzSPR | Legacy (< 5 units) | Code present, lowest priority |
| KNX2 | Legacy (< 5 units) | Code present, lowest priority |

---

## 2. What's MISSING — Action Items

### ✅ BLOCKERS — ALL RESOLVED

| # | Item | Resolution |
|---|------|------------|
| B1 | **Version strings** | Unified to `2.0.5` in VERSION, version.py, pyproject.toml, installer.nsi, README.md, QUICK_START.md, OPERATION_MANUAL.md |
| B2 | **CHANGELOG** | Created `CHANGELOG.md` (v0.1.0 through v2.0.5) |
| B3 | **About dialog** | Added About section to Settings sidebar tab (`AL_settings_builder.py`) |
| B4 | **Product name** | Fixed "ezControl-AI" → "Affilabs.core" in all user-facing docs |

### ✅ HIGH PRIORITY — ALL RESOLVED

| # | Item | Resolution |
|---|------|------------|
| H1 | **KNOWN_ISSUES.md** | Created `docs/user_guides/KNOWN_ISSUES.md` — 3 known issues, limitations tables, deferred features list |
| H2 | **INSTALLATION_GUIDE.md** | Created `docs/user_guides/INSTALLATION_GUIDE.md` — 5-step guide (installer → Zadig → controller → first launch → calibration) |
| H3 | **HARDWARE_COMPATIBILITY.md** | Created `docs/user_guides/HARDWARE_COMPATIBILITY.md` — full instrument/detector/firmware/OS matrix |
| H4 | **DEMO_QUICK_START.md** | Rewritten as evaluation & demo mode guide — fixed stale paths, added works-without-hardware table |
| H5 | **SENSOR_CHIP_GUIDE.md** | Created `docs/user_guides/SENSOR_CHIP_GUIDE.md` — handling, surface chemistries, storage, regeneration, troubleshooting |
| H6 | **OPERATION_MANUAL.md** | Updated: version history table (added v2.0.5), fixed Update Policy section, fixed product name, updated footer to v2.0.5 |
| H7 | **EULA** | Drafted `docs/user_guides/EULA.md` — 13-section agreement (flagged: needs legal review before distribution) |

### 🟢 NICE TO HAVE (can follow after initial ship)

| # | Item | Notes |
|---|------|-------|
| N1 | Consolidated troubleshooting index | Content exists across 10+ docs; a single TOC page would help |
| N2 | Settings reference document | 100+ constants in `settings.py` — source comments are adequate for now |
| N3 | Excel output column-level schema | EXCEL_CHART_BUILDER_FRS has detail, but no customer-facing "data dictionary" |
| N4 | **License key — replace secret before shipping** | `_SECRET` placeholder in `affilabs/services/license_service.py` and `tools/keygen.py` must be replaced with a real 32-byte secret (`python -c "import secrets; print(secrets.token_hex(32))"`). Both files must be identical. Then run `keygen.py --tier base` and `--tier pro` to generate the final customer keys. Regenerate all keys if secret is rotated. |
| N5 | Remove EzSPR/KNX dead code | 28 files have legacy paths. Safe but dead weight. Defer to v3.0 cleanup. |
| N6 | `ApplicationState` migration | `app_state.py` vs `self.*` coexistence documented as known technical debt |

---

## 3. Documentation Inventory — What Ships with v2.0.5

### Customer-Facing (ship / link from app)

| Document | Status | Path |
|----------|--------|------|
| Operation Manual | ✅ Updated to v2.0.5 | `docs/user_guides/OPERATION_MANUAL.md` |
| Quick Start | ✅ Fixed (v2.0.5, correct name) | `docs/user_guides/QUICK_START.md` |
| Power-On Procedure | ✅ | `docs/user_guides/POWER_ON_PROCEDURE.md` |
| Injection Methods | ✅ | `docs/user_guides/INJECTION_METHODS.md` |
| Injection Quick Reference | ✅ | `docs/user_guides/INJECTION_QUICK_REF.md` |
| Kinetic Methods | ✅ | `docs/user_guides/KINETIC_METHODS.md` |
| Training Guide | ⚠️ Version says 1.0 | `docs/user_guides/TRAINING_GUIDE.md` |
| Calibration Guide | ✅ (947 lines, thorough) | `docs/calibration/CALIBRATION_GUIDE.md` |
| Calibration Troubleshooting | ✅ (481 lines) | `docs/calibration/STARTUP_CALIBRATION_TROUBLESHOOTING.md` |
| Demo Quick Start | ✅ Rewritten as evaluation guide | `docs/user_guides/DEMO_QUICK_START.md` |
| Privacy Policy | ✅ | `docs/user_guides/PRIVACY_POLICY.md` |
| Installation Guide | ✅ Created | `docs/user_guides/INSTALLATION_GUIDE.md` |
| Known Issues | ✅ Created | `docs/user_guides/KNOWN_ISSUES.md` |
| Hardware Compatibility | ✅ Created | `docs/user_guides/HARDWARE_COMPATIBILITY.md` |
| Sensor Chip Guide | ✅ Created | `docs/user_guides/SENSOR_CHIP_GUIDE.md` |
| Changelog / What's New | ✅ Created | `CHANGELOG.md` |
| EULA | ✅ Draft (needs legal review) | `docs/user_guides/EULA.md` |

### Developer / Internal (don't ship, keep in repo)

| Category | Count | Status |
|----------|-------|--------|
| Architecture specs | 38 docs | 5 code-verified, rest ⚠️ unverified |
| Feature FRS docs | 43 docs | 15 code-verified ✅ |
| Hardware docs | 17 docs | 1 verified (P4PRO_FLUIDIC) |
| Calibration docs | 8 docs | 2 verified |
| UI docs | 6 docs | All ✅ verified |
| Future plans | 19 docs | Aspirational only |
| Product requirements | 4 docs | Reference only |

---

## 4. Recommended Action Plan — Priority Order

### Week 1: Blockers (ship-stopping)

```
Day 1:  B1 — Fix version strings (pyproject.toml, README, QUICK_START, OPERATION_MANUAL)
        B3 — Build About dialog (version, date, contact email)
        B4 — Fix product name "ezControl-AI" → "Affilabs.core" in user docs
Day 2:  B2 — Write CHANGELOG.md (v1.0 → v2.0 → v2.0.5 beta)
```

### Week 1–2: High Priority (professional polish)

```
Day 3:  H1 — Write KNOWN_ISSUES.md (pull from CLAUDE.md + test findings)
        H3 — Write HARDWARE_COMPATIBILITY.md (one-page matrix)
Day 4:  H2 — Write INSTALLATION_GUIDE.md (installer → Zadig → first launch)
        H4 — Rewrite DEMO_QUICK_START.md
Day 5:  H5 — Write SENSOR_CHIP_GUIDE.md (handling, storage, surfaces)
        H6 — Update OPERATION_MANUAL.md to v2.0.5
```

### Post-Ship: Nice to Have

```
N1 — Troubleshooting index
N3 — Excel data dictionary
H7 — EULA (requires legal review, can ship beta without)
```

---

## 5. Scope Boundaries — What v2.0.5 Does NOT Include

These features are **explicitly deferred** and should NOT be documented as current capabilities:

| Feature | Deferred To | Current State |
|---------|------------|---------------|
| Full P4PRO semi-automated suite | v3.0 | Basic injection works, full protocol editor deferred |
| P4PROPLUS internal pump workflows | v3.0 | Commands implemented, workflow orchestration deferred |
| Autosampler integration | v4.0 | Plan exists in `AUTOSAMPLER_INTEGRATION_PLAN.md` |
| GuidanceCoordinator Pass B (adaptive hints) | v3.0 | Pass A (logging) ships; widget hints deferred |
| Timeline Phase 5 (presenter integration) | v3.0 | Phases 1–4 complete, Phase 5 deferred |
| 21 CFR Part 11 compliance | v3.0+ | Gap analysis done, ~15–20% compliant |
| IQ/OQ validation suite | v3.0+ | Plan exists, not implemented |
| Experiment Browser dialog | v3.0 | FRS written, dialog not created |
| License key enforcement | v3.0 | Infrastructure scaffolded, not enforced |
| Injection auto-detection v2 (multi-feature) | v3.0 | v1 (λ-threshold) ships |
| AnIML / SiLA 2 | v4.0+ | Plan only |
| Sparq LLM-based answers | v3.0+ | Pattern matching ships; LLM removed |

---

## 6. Sign-Off Checklist

Before declaring v2.0.5 "gold":

- [ ] All blocker items (B1–B4) resolved
- [ ] Version strings consistent across all files
- [ ] CHANGELOG.md written and accurate
- [ ] About dialog shows correct version + support contact
- [ ] KNOWN_ISSUES.md covers all beta limitations
- [ ] Installation guide tested on clean Windows 10/11 machine
- [ ] QUICK_START.md rewritten with correct product name + version
- [ ] OPERATION_MANUAL.md updated to v2.0.5
- [ ] Hardware compatibility sheet reviewed by hardware team
- [ ] Demo mode tested and DEMO_QUICK_START.md updated
- [ ] Full build + installer tested (`_build/Affilabs-Core.spec` + `installer.nsi`)
- [ ] Smoke test: connect P4SPR → calibrate → acquire → record → export Excel
- [ ] Smoke test: demo mode without hardware
- [ ] **License key secret replaced** in `affilabs/services/license_service.py` AND `tools/keygen.py` (must match)
- [ ] **Final customer keys generated** with `keygen.py --tier base` / `--tier pro` and stored internally
- [ ] **Activation dialog tested**: enter valid key → activates; enter garbage → red error; "Continue in Demo" → demo mode; restart after activation → no dialog shown
- [ ] Customer-facing docs reviewed for "ezControl-AI" → "Affilabs.core" naming
