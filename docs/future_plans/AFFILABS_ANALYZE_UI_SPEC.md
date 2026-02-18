# Affilabs.analyze UI Specification

**Version:** 1.0 Draft  
**Date:** February 2, 2026  
**Product:** Affilabs.analyze - SPR Data Analysis & Reporting Software  
**Tier:** Premium (separate from Affilabs.core)

---

## Executive Summary

Affilabs.analyze is a standalone desktop application for offline SPR data analysis, kinetic fitting, and report generation. It operates independently from Affilabs.core (instrument control software) and imports data via Excel/CSV files.

---

## Product Positioning

| Product | Purpose | License |
|---------|---------|---------|
| **Affilabs.core** | Instrument control, data acquisition, basic editing | Bundled with P4SPR hardware |
| **Affilabs.analyze** | Advanced analysis, kinetic fitting, reporting | Separate purchase / subscription |

---

## Application Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Affilabs.analyze                           │
├─────────────────────────────────────────────────────────────────┤
│  UI Layer (PySide6)                                             │
│  ├── Main Window                                                │
│  ├── Project Explorer Panel                                     │
│  ├── Analysis Workspace (Tabbed)                                │
│  │   ├── Data View                                              │
│  │   ├── Fitting View                                           │
│  │   └── Report Builder                                         │
│  └── Properties Panel                                           │
├─────────────────────────────────────────────────────────────────┤
│  Analysis Engine                                                │
│  ├── Data Importer (Excel, CSV, Affilabs project files)         │
│  ├── Signal Processing (baseline correction, smoothing)         │
│  ├── Kinetic Fitting (scipy.optimize)                           │
│  └── Statistics Module (error analysis, confidence intervals)   │
├─────────────────────────────────────────────────────────────────┤
│  Report Generator                                               │
│  ├── Template Engine                                            │
│  ├── PDF Export (reportlab / weasyprint)                        │
│  └── Figure Renderer (matplotlib / pyqtgraph export)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Main Window Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │  File   Edit   Analysis   View   Report   Help                           │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ 📂 New │ 📁 Open │ 💾 Save │ ┃ 📊 Import │ ┃ ▶ Fit │ 📄 Report │ ⚙ Settings │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
├────────────────┬─────────────────────────────────────────────┬───────────────┤
│                │                                             │               │
│   PROJECT      │  ┌─────────────────────────────────────┐   │  PROPERTIES   │
│   EXPLORER     │  │  [ Data ]  [ Fitting ]  [ Report ]  │   │               │
│                │  ├─────────────────────────────────────┤   │  Selected:    │
│  📁 Project    │  │                                     │   │  Run 1        │
│  ├─📁 Study 1  │  │                                     │   │               │
│  │ ├─📄 Run 1  │  │                                     │   │  ───────────  │
│  │ ├─📄 Run 2  │  │        WORKSPACE AREA               │   │  Channels: 4  │
│  │ └─📄 Run 3  │  │        (Tab Content)                │   │  Duration:    │
│  │             │  │                                     │   │   12.5 min    │
│  ├─📁 Study 2  │  │                                     │   │  Points:      │
│  │ └─📄 Run 1  │  │                                     │   │   7,500       │
│  │             │  │                                     │   │               │
│  └─📁 Study 3  │  │                                     │   │  ───────────  │
│                │  │                                     │   │  Fit Status:  │
│  ───────────── │  │                                     │   │  ⏳ Pending   │
│  QUICK STATS   │  │                                     │   │               │
│  Runs: 7       │  │                                     │   │  Conc: 100nM  │
│  Fitted: 3/7   │  │                                     │   │  Analyte:     │
│  KD range:     │  │                                     │   │   IgG-001     │
│  1.2-4.8 nM    │  │                                     │   │               │
│                │  └─────────────────────────────────────┘   │               │
├────────────────┴─────────────────────────────────────────────┴───────────────┤
│  Ready │ Project: Untitled │ 7 runs loaded │ Memory: 245 MB                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Tab 1: Data View

### Purpose
Import, visualize, and organize sensorgram data from Affilabs.core exports.

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [ Data ]  [ Fitting ]  [ Report ]                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │                     OVERLAY SENSORGRAM PLOT                            │  │
│  │                                                                        │  │
│  │   Response                                                             │  │
│  │   (RU)  ▲                                                              │  │
│  │    800  │          ┌─────────────────┐                                 │  │
│  │         │         ╱│                 │╲     ── 100 nM                  │  │
│  │    600  │        ╱ │                 │ ╲    ── 50 nM                   │  │
│  │         │       ╱  │                 │  ╲   ── 25 nM                   │  │
│  │    400  │      ╱   │                 │   ╲  ── 12.5 nM                 │  │
│  │         │     ╱    │                 │    ╲ ── 6.25 nM                 │  │
│  │    200  │    ╱     │                 │     ╲                           │  │
│  │         │   ╱      │                 │      ╲                          │  │
│  │      0  │──╱───────┴─────────────────┴───────╲──────────▶ Time (s)     │  │
│  │         0        100       200       300       400       500           │  │
│  │                   │ Association │ Dissociation │                       │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────┐  ┌────────────────────────────────────┐ │
│  │  ALIGNMENT CONTROLS             │  │  DATA TABLE                        │ │
│  │                                 │  │                                    │ │
│  │  Align to: [Injection Start ▼]  │  │  Run    Conc   Ch   Rmax   Status  │ │
│  │  Time offset: [0.0    ] s       │  │  ─────────────────────────────────│ │
│  │                                 │  │  ☑ Run1  100nM  A   823    ✓ OK    │ │
│  │  Y-Axis:                        │  │  ☑ Run2   50nM  A   612    ✓ OK    │ │
│  │  ○ Absolute (RU)                │  │  ☑ Run3   25nM  A   445    ✓ OK    │ │
│  │  ● Normalized (%)               │  │  ☑ Run4 12.5nM  A   298    ✓ OK    │ │
│  │  ○ Baseline-subtracted          │  │  ☐ Run5 6.25nM  A    52    ⚠ Low   │ │
│  │                                 │  │                                    │ │
│  │  [Apply Baseline Correction]    │  │  [Select All] [Invert] [Remove]    │ │
│  └─────────────────────────────────┘  └────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Features

| Feature | Description |
|---------|-------------|
| **Multi-file Import** | Drag & drop multiple Excel files from Affilabs.core |
| **Auto-alignment** | Detect injection points, align overlays automatically |
| **Channel Selection** | Toggle visibility per channel (A, B, C, D) |
| **Concentration Labels** | Color-code by concentration series |
| **Baseline Correction** | Reference subtraction, drift correction |
| **Data Quality Flags** | Auto-detect low signal, drift, artifacts |

---

## Tab 2: Fitting View

### Purpose
Apply kinetic models to sensorgram data and extract binding parameters.

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [ Data ]  [ Fitting ]  [ Report ]                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │                    FITTED SENSORGRAM + RESIDUALS                        │ │
│  │                                                                         │ │
│  │   RU  ▲      ═══ Experimental    ─── Fitted                             │ │
│  │  800  │          ══════════════════                                     │ │
│  │       │         ─────────────────── (fitted curve overlaid)             │ │
│  │  400  │                                                                 │ │
│  │       │                                                                 │ │
│  │    0  └────────────────────────────────────────────────▶ Time           │ │
│  │       ┌────────────────────────────────────────────────┐                │ │
│  │   Res │  ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿  │ Residuals       │ │
│  │       └────────────────────────────────────────────────┘                │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────┐  ┌──────────────────────────────────────┐   │
│  │  FITTING PARAMETERS         │  │  RESULTS                             │   │
│  │                             │  │                                      │   │
│  │  Model: [1:1 Langmuir    ▼] │  │  Parameter    Value      Error       │   │
│  │                             │  │  ──────────────────────────────────  │   │
│  │  Fitting Mode:              │  │  ka (1/Ms)    1.23e5    ± 2.1e3      │   │
│  │  ● Global (linked ka/kd)    │  │  kd (1/s)     2.34e-4   ± 1.2e-5     │   │
│  │  ○ Local (per curve)        │  │  KD (nM)      1.90      ± 0.15       │   │
│  │                             │  │  Rmax (RU)    856       ± 12         │   │
│  │  Fit Range:                 │  │                                      │   │
│  │  Association: [60-180] s    │  │  ──────────────────────────────────  │   │
│  │  Dissociation: [180-400] s  │  │  Chi² (χ²)    0.42                   │   │
│  │                             │  │  R²           0.9987                 │   │
│  │  ☑ Mass transport (km)      │  │  DoF          1247                   │   │
│  │  ☐ Bulk RI correction       │  │                                      │   │
│  │                             │  │  ──────────────────────────────────  │   │
│  │  [▶ Fit Selected]           │  │  Confidence: 95%                     │   │
│  │  [▶▶ Fit All]               │  │  ka range: [1.19e5 - 1.27e5]         │   │
│  │  [↺ Reset]                  │  │  kd range: [2.22e-4 - 2.46e-4]       │   │
│  │                             │  │                                      │   │
│  └─────────────────────────────┘  └──────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  CONCENTRATION SERIES SUMMARY                                        │    │
│  │                                                                      │    │
│  │  Conc (nM)   ka (1/Ms)    kd (1/s)     KD (nM)    Rmax    χ²   Incl │    │
│  │  ────────────────────────────────────────────────────────────────── │    │
│  │    100       1.24e5       2.31e-4      1.86       823     0.38   ☑  │    │
│  │     50       1.22e5       2.35e-4      1.93       612     0.41   ☑  │    │
│  │     25       1.23e5       2.38e-4      1.94       445     0.44   ☑  │    │
│  │   12.5       1.21e5       2.32e-4      1.92       298     0.45   ☑  │    │
│  │   6.25       1.18e5       2.41e-4      2.04        52     1.23   ☐  │    │
│  │  ────────────────────────────────────────────────────────────────── │    │
│  │  GLOBAL:     1.23e5       2.34e-4      1.90 nM           0.42       │    │
│  │                                                                      │    │
│  │  [Export CSV]  [Copy to Clipboard]  [Add to Report]                  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Kinetic Models

| Model | Equation | Use Case |
|-------|----------|----------|
| **1:1 Langmuir** | dR/dt = ka·C·(Rmax-R) - kd·R | Simple binding |
| **1:1 + Mass Transport** | Adds km parameter | High-density surfaces |
| **Heterogeneous (1:2)** | Two independent sites | Complex analytes |
| **Bivalent Analyte** | Avidity effects | Antibodies |
| **Conformational Change** | Two-step binding | Induced fit |

### Fitting Algorithm

```python
# Core fitting approach (scipy.optimize)
from scipy.optimize import curve_fit, differential_evolution

def langmuir_1to1(t, ka, kd, Rmax, C):
    """1:1 Langmuir binding model."""
    kobs = ka * C + kd
    Req = (ka * C * Rmax) / kobs
    return Req * (1 - np.exp(-kobs * t))

# Global fitting: shared ka, kd across concentrations
# Local fitting: independent parameters per curve
```

---

## Tab 3: Report Builder

### Purpose
Create publication-ready reports with customizable templates.

### Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [ Data ]  [ Fitting ]  [ Report ]                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌───────────────────────────────────────────────────┐   │
│  │  COMPONENTS    │  │                                                   │   │
│  │                │  │              REPORT PREVIEW                       │   │
│  │  ┌──────────┐  │  │                                                   │   │
│  │  │ 📝 Title │  │  │  ┌─────────────────────────────────────────────┐  │   │
│  │  └──────────┘  │  │  │                                             │  │   │
│  │  ┌──────────┐  │  │  │  SPR Binding Analysis Report                │  │   │
│  │  │ 📊 Senso-│  │  │  │  ════════════════════════════               │  │   │
│  │  │   gram   │  │  │  │                                             │  │   │
│  │  └──────────┘  │  │  │  Study: Anti-HER2 Binding Kinetics          │  │   │
│  │  ┌──────────┐  │  │  │  Date: February 2, 2026                     │  │   │
│  │  │ 📈 Fit   │  │  │  │  Analyst: J. Smith                          │  │   │
│  │  │   Plot   │  │  │  │                                             │  │   │
│  │  └──────────┘  │  │  │  ─────────────────────────────────────────  │  │   │
│  │  ┌──────────┐  │  │  │                                             │  │   │
│  │  │ 📋 Results│  │  │  │  1. Experimental Overview                  │  │   │
│  │  │   Table  │  │  │  │                                             │  │   │
│  │  └──────────┘  │  │  │  [Sensorgram Figure]                        │  │   │
│  │  ┌──────────┐  │  │  │                                             │  │   │
│  │  │ 📉 Resi- │  │  │  │  Figure 1: Overlay of sensorgrams at       │  │   │
│  │  │   duals  │  │  │  │  concentrations 6.25-100 nM.               │  │   │
│  │  └──────────┘  │  │  │                                             │  │   │
│  │  ┌──────────┐  │  │  │  ─────────────────────────────────────────  │  │   │
│  │  │ 📝 Text  │  │  │  │                                             │  │   │
│  │  │   Block  │  │  │  │  2. Kinetic Analysis                        │  │   │
│  │  └──────────┘  │  │  │                                             │  │   │
│  │  ┌──────────┐  │  │  │  [Fitting Plot with Residuals]              │  │   │
│  │  │ 🔬 Methods│  │  │  │                                             │  │   │
│  │  └──────────┘  │  │  │  [Results Table]                            │  │   │
│  │                │  │  │                                             │  │   │
│  │  ───────────── │  │  │  KD = 1.90 ± 0.15 nM                        │  │   │
│  │  TEMPLATES     │  │  │                                             │  │   │
│  │                │  │  └─────────────────────────────────────────────┘  │   │
│  │  ○ Standard    │  │                                                   │   │
│  │  ○ Detailed    │  │  Page 1 of 3   [◀ Prev] [Next ▶]                  │   │
│  │  ○ Summary     │  │                                                   │   │
│  │  ○ Custom...   │  │                                                   │   │
│  │                │  │                                                   │   │
│  └────────────────┘  └───────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  OUTPUT OPTIONS                                                      │    │
│  │                                                                      │    │
│  │  Format: ● PDF  ○ Word (.docx)  ○ HTML  ○ PowerPoint                 │    │
│  │                                                                      │    │
│  │  Page Size: [Letter (8.5x11") ▼]    Orientation: ● Portrait ○ Land.  │    │
│  │                                                                      │    │
│  │  ☑ Include raw data appendix    ☑ Include methods section            │    │
│  │  ☑ Include QC metrics           ☐ Include analyst signature block    │    │
│  │                                                                      │    │
│  │  [Preview Full Report]           [📄 Export Report]                  │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Report Sections

| Component | Content | Editable |
|-----------|---------|----------|
| **Title Block** | Study name, date, analyst, organization | Yes |
| **Sensorgram** | Overlay plot with legend | Figure options |
| **Fitting Plot** | Experimental vs fitted with residuals | Figure options |
| **Results Table** | ka, kd, KD, Rmax, χ², statistics | Column selection |
| **Methods** | Auto-generated from analysis parameters | Yes |
| **Conclusions** | Free-text interpretation | Yes |

---

## Import/Export Formats

### Import (from Affilabs.core)

| Format | Extension | Contents |
|--------|-----------|----------|
| **Excel Workbook** | .xlsx | Time, Ch A-D, metadata sheet |
| **CSV** | .csv | Simple time-series data |
| **Affilabs Project** | .alfproj | Full project with settings (future) |

### Export

| Format | Use Case |
|--------|----------|
| **PDF Report** | Publication, sharing |
| **Excel** | Further analysis in other tools |
| **CSV** | Data interchange |
| **PNG/SVG** | Figures for presentations |
| **PowerPoint** | Direct slide insertion |

---

## Settings Dialog

```
┌──────────────────────────────────────────────────────────────────┐
│  Settings                                                    [X] │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐                                              │
│  │ General        │  ┌────────────────────────────────────────┐  │
│  │ Fitting        │  │  FITTING DEFAULTS                      │  │
│  │ Display        │  │                                        │  │
│  │ Export         │  │  Default Model: [1:1 Langmuir      ▼]  │  │
│  │ License        │  │                                        │  │
│  └────────────────┘  │  Default Mode:  ● Global  ○ Local      │  │
│                      │                                        │  │
│                      │  Convergence:                          │  │
│                      │  Max iterations: [1000    ]            │  │
│                      │  Tolerance:      [1e-8    ]            │  │
│                      │                                        │  │
│                      │  Constraints:                          │  │
│                      │  ☑ ka > 0                              │  │
│                      │  ☑ kd > 0                              │  │
│                      │  ☑ Rmax > 0                            │  │
│                      │                                        │  │
│                      │  Error Estimation:                     │  │
│                      │  ● Standard error (covariance)         │  │
│                      │  ○ Bootstrap (slower, more robust)     │  │
│                      │                                        │  │
│                      └────────────────────────────────────────┘  │
│                                                                  │
│                                        [Cancel]  [Apply]  [OK]   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Color Scheme & Styling

### Consistent with Affilabs.core

```python
# Shared design tokens (ui_styles.py)
COLORS = {
    "PRIMARY": "#2E30E3",        # Affilabs blue
    "PRIMARY_LIGHT": "rgba(46, 48, 227, 0.1)",
    "SUCCESS": "#34C759",
    "WARNING": "#FF9500",
    "ERROR": "#FF3B30",
    "BACKGROUND": "#F5F5F7",
    "SURFACE": "#FFFFFF",
    "TEXT_PRIMARY": "#1D1D1F",
    "TEXT_SECONDARY": "#86868B",
}

# Concentration series palette (colorblind-safe)
CONC_PALETTE = [
    "#4477AA",  # Blue (highest)
    "#EE6677",  # Red
    "#228833",  # Green
    "#CCBB44",  # Yellow
    "#66CCEE",  # Cyan
    "#AA3377",  # Purple
    "#BBBBBB",  # Gray (lowest)
]
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save project |
| `Ctrl+I` | Import data |
| `Ctrl+E` | Export report |
| `Ctrl+F` | Fit selected |
| `Ctrl+Shift+F` | Fit all |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+1/2/3` | Switch tabs |
| `F5` | Refresh preview |

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **UI Framework** | PySide6 | Same as Affilabs.core, shared components |
| **Plotting** | pyqtgraph + matplotlib | Fast interactive + publication quality |
| **Fitting** | scipy.optimize | Robust, well-documented |
| **Statistics** | numpy, scipy.stats | Industry standard |
| **PDF Export** | reportlab or weasyprint | Professional output |
| **Data Storage** | SQLite + JSON | Lightweight project files |

---

## Development Phases

### Phase 1: Core Import & Visualization (MVP)
- [ ] Excel/CSV importer from Affilabs.core
- [ ] Multi-sensorgram overlay plot
- [ ] Basic alignment tools
- [ ] Project save/load

### Phase 2: Kinetic Fitting
- [ ] 1:1 Langmuir model
- [ ] Global/local fitting modes
- [ ] Residual plots
- [ ] Error estimation

### Phase 3: Advanced Models
- [ ] Mass transport correction
- [ ] Heterogeneous binding
- [ ] Bivalent analyte
- [ ] Custom model editor

### Phase 4: Report Builder
- [ ] Template system
- [ ] Drag-drop report assembly
- [ ] PDF export
- [ ] Word/PowerPoint export

### Phase 5: Polish & Integration
- [ ] Batch processing
- [ ] Cloud backup (optional)
- [ ] License management
- [ ] Auto-update system

---

## File: Main Entry Point

```python
# affilabs_analyze/main.py
"""Affilabs.analyze - SPR Data Analysis & Reporting

Standalone application for offline analysis of SPR data
exported from Affilabs.core.
"""

import sys
from PySide6.QtWidgets import QApplication
from affilabs_analyze.ui.main_window import AnalyzeMainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Affilabs.analyze")
    app.setOrganizationName("Affilabs")
    app.setOrganizationDomain("affilabs.com")
    
    window = AnalyzeMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

## Next Steps

1. **Review this spec** - Confirm UI layout and features match your vision
2. **Prioritize MVP features** - What's needed for first release?
3. **Create project structure** - Separate repo or monorepo with Affilabs.core?
4. **Design data interchange format** - Standardize Excel export from Affilabs.core

---

*Document maintained by Affilabs Development Team*
