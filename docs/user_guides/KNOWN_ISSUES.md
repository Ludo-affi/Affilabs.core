# Affilabs.core v2.0.5 — Known Issues & Limitations

**Last Updated:** February 24, 2026

This document lists known issues, limitations, and workarounds in the current release. Items are listed by severity.

---

## Known Issues

### 1. Manual injection auto-detection may not trigger (P4SPR)

**Severity:** Medium  
**Affected:** P4SPR manual injection workflow  

The live injection auto-detection algorithm (`λ-threshold v1`) may not fire in some conditions when using manual syringe injection. This depends on the magnitude of the wavelength shift and the detection window timing.

**Workaround:** Place injection flags manually using the flag toolbar buttons or keyboard shortcuts. The auto-detection is a convenience feature — manual flag placement produces identical data.

---

### 2. Wash flags are visual only — no timeline event

**Severity:** Low  
**Affected:** Contact Monitor panel wash detection  

When the WashMonitor detects a wash event, it updates the visual indicator on the injection action bar but does **not** place a flag in the timeline or on the sensorgram. Wash flags are only placed by the automatic wash timer system.

**Workaround:** If precise wash timing matters for your analysis, place a manual flag at the start of each wash step using the flag toolbar.

---

### 3. GuidanceCoordinator hints not yet active

**Severity:** Low  
**Affected:** Contextual hint overlay  

The adaptive guidance system (Pass A) is logging user actions for future hint generation, but contextual hints are not yet displayed in the UI (Pass B not implemented).

**Workaround:** None needed — the system is collecting data silently. Hints will be activated in a future update. Use Sparq AI (sidebar) for on-demand help.

---

## Limitations

### Software

| Limitation | Detail |
|-----------|--------|
| **Windows only** | Windows 10 (build 19041+) and Windows 11 64-bit. macOS and Linux are not supported. |
| **Python 3.12 required** | The application enforces Python 3.12 at startup. Other versions will not work. |
| **Maximum data points** | ~500,000 per recording session before performance degrades |
| **Maximum concurrent cycles** | 100 per experiment method |
| **Channels** | 4 channels (A, B, C, D) — fixed by hardware design |
| **Single instrument** | One spectrometer + one controller per application instance |
| **Demo mode** | Press `Ctrl+Shift+D` to load demo data; live acquisition features are unavailable without hardware |

### Hardware

| Limitation | Detail |
|-----------|--------|
| **Spectrometers** | Ocean Optics Flame-T (primary) and USB4000 only. Other Ocean Optics models are not supported. |
| **Controller firmware** | PicoP4SPR V2.4 recommended. V2.2 supported with reduced features (no CYCLE_SYNC mode). |
| **P4PRO + AffiPump** | Basic semi-automated injection is functional. Full automated protocol builder deferred to v3.0. |
| **P4PROPLUS internal pumps** | Pump commands are implemented. Full workflow orchestration deferred to v3.0. |
| **EzSPR / KNX2** | Legacy support present in code but these devices are end-of-life (<5 units in field). Not actively tested. |

### Data & Export

| Limitation | Detail |
|-----------|--------|
| **Excel import** | Loading archived data supports `.xlsx` only (3 sheet format variants). CSV import via the UI is not available. |
| **TraceDrawer CSV** | Export works; import back into Affilabs.core of TraceDrawer-format files is not supported. |
| **Real-time chart export** | Charts are generated only in post-edit Excel export, not in live auto-save files. |
| **Flag chart series** | Flag markers in Excel chart sheets may not render correctly in all cases (known openpyxl limitation). |

### Features Not Included in v2.0.5

These features are planned for future versions:

| Feature | Target Version |
|---------|---------------|
| Full P4PRO/AffiPump automated protocol suite | v3.0 |
| Autosampler integration | v4.0 |
| 21 CFR Part 11 compliance (audit trail, e-signatures) | v3.0+ |
| IQ/OQ validation suite | v3.0+ |
| License key enforcement | v3.0 |
| Experiment Browser dialog (search/load past recordings) | v3.0 |
| AnIML / SiLA 2 data standards | v4.0+ |
| Sparq AI with LLM-based answers | v3.0+ |
| Adaptive contextual hints (GuidanceCoordinator Pass B) | v3.0 |

---

## Reporting Issues

If you encounter a problem not listed here:

1. Check the error log: `Settings → Hardware Status → Debug Log`
2. Note the steps to reproduce the issue
3. Email **info@affiniteinstruments.com** with:
   - Software version (Settings → About Affilabs.core)
   - Hardware model and detector serial number
   - Steps to reproduce
   - Screenshots if applicable

---

**© 2026 Affinite Instruments Inc.**
