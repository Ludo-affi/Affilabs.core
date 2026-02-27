# Affilabs.core v2.0.5 — Evaluation & Demo Mode Guide

**Last Updated:** February 24, 2026  
**Audience:** New users evaluating the software, trainers, and sales/demo personnel

---

## Overview

Affilabs.core can run **without hardware connected**. This is useful for:

- **Evaluating** the software before purchasing an instrument
- **Training** new users on the UI and data analysis workflow
- **Demonstrating** features to potential customers
- **Developing** method templates offline

---

## Launching the Application

```powershell
# Standard launch (works with or without hardware)
python main.py
```

On startup, the application scans for connected hardware. If no spectrometer or controller is detected, the application still opens fully — you'll see "Not Connected" indicators in the sidebar hardware status section.

---

## Loading Demo Data

Press **`Ctrl+Shift+D`** at any time to load built-in demo data into the sensorgram.

This generates **3 cycles** of realistic SPR binding kinetics across all 4 channels:

| Cycle | Simulated Concentration | Wavelength Shift |
|-------|------------------------|-----------------|
| 1 | Low | ~20 nm |
| 2 | Medium | ~40 nm |
| 3 | High | ~65 nm |

Each cycle includes baseline, association (binding), and dissociation (washout) phases with realistic noise and channel-to-channel variation.

---

## What Works Without Hardware

| Feature | Available? | Notes |
|---------|-----------|-------|
| **Demo data loading** (`Ctrl+Shift+D`) | Yes | Simulated sensorgram with 3 binding cycles |
| **Edits tab** — data analysis | Yes | Load demo data or open saved `.xlsx` files |
| **Edits tab** — alignment & delta-SPR | Yes | Full cursor and alignment tools |
| **Edits tab** — binding plot & Kd fitting | Yes | Works on loaded data |
| **Edits tab** — Excel export | Yes | Full export with charts |
| **Notes tab** — experiment log | Yes | Create, tag, rate experiments |
| **Method Builder** — template creation | Yes | Build and save method templates |
| **Queue Manager** — experiment planning | Yes | Create and preview cycle queues |
| **Settings** — all configuration panels | Yes | Full access to all settings |
| **Sparq AI** — assistant | Yes | Pattern-based help and tips |
| **Accessibility panel** | Yes | Color palettes, line styles |

| Feature | Requires Hardware |
|---------|------------------|
| **Live calibration** | Spectrometer + Controller |
| **Live acquisition** (real-time sensorgram) | Spectrometer + Controller |
| **Recording** (auto-save to Excel) | Active acquisition session |
| **Injection detection** | Active acquisition + fluidics |
| **Pump control** | AffiPump connected |

---

## Recommended Evaluation Workflow

1. **Launch** the application: `python main.py`
2. **Explore the sidebar** — click through each tab to see the interface
3. **Load demo data** — press `Ctrl+Shift+D`
4. **Switch to the Edits tab** — the demo data appears as loadable cycles
5. **Try the analysis tools:**
   - Select a cycle from the table
   - Place alignment cursors on the sensorgram
   - Measure delta-SPR between two points
   - Open the binding plot and try a Kd fit
6. **Export to Excel** — click the Export button to generate a professional report
7. **Open the Method Builder** — create a sample multi-cycle experiment template
8. **Check the Notes tab** — log observations, rate the demo experiment

---

## Demo Data Details

The built-in demo data generator (`affilabs/utils/demo_data_generator.py`) produces:

- **Langmuir model kinetics** with realistic ka/kd rate constants
- **4 channels** (A, B, C, D) with 82–100% relative response variation
- **Gaussian noise** (~0.5 nm RMS) matching real instrument characteristics
- **Baseline drift** simulation (~0.1 nm/min)
- **~600 seconds per cycle** (60s baseline, 240s association, 300s dissociation)

---

## Taking Screenshots

For promotional or training materials:

1. Load demo data (`Ctrl+Shift+D`)
2. Best views:
   - **Full sensorgram** — all 3 cycles visible, shows overview
   - **Single cycle zoom** — clear association/dissociation phases
   - **Multi-channel overlay** — all 4 channels, shows comparison
   - **Edits tab with binding plot** — shows analysis capabilities
3. Use the accessibility panel to switch color palettes if needed

---

## Support

Questions about evaluation or purchasing:

- **Email:** info@affiniteinstruments.com

---

**© 2026 Affinite Instruments Inc.**
