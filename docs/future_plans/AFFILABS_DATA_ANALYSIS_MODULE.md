# Affilabs.data Analysis Module (Planned)

**Status**: Design & planning phase
**Target Release**: Q3 2026
**Priority**: High (core data processing capability)

## Vision

Create a standalone Python package (`affilabs.data` or `affilabs.analyze`) for SPR data processing, metrics calculation, and report generation. This module will:

1. **Load exported Excel/CSV files** produced by Affilabs.core
2. **Calculate SPR metrics** (kinetics, thermodynamics, binding models)
3. **Generate publication-ready reports** (PDF, HTML, PNG charts)
4. **Integrate with Jupyter notebooks** for exploratory analysis
5. **Support external analysis tools** (R, MATLAB, GraphPad Prism via CSV/JSON export)

---

## Architecture Overview

```
User Workflow:
    Export from Affilabs.core (Excel/.xlsx)
        ↓
    Load into affilabs.data.Experiment
        ↓
    Automated metrics calculation
        ↓
    Generate report (PDF/HTML)
        ↓
    Optionally: Jupyter analysis, export to Prism, etc.
```

---

## Module Structure

```
affilabs/
├── data/                              (NEW PACKAGE)
│   ├── __init__.py
│   ├── experiment.py                  # Core Experiment class
│   ├── cycle.py                       # Cycle-level data model
│   ├── channel.py                     # Per-channel data model
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── kinetics.py               # ka, kd, Kd calculations
│   │   ├── binding.py                # Affinity, Rmax, chi-squared
│   │   ├── thermodynamics.py         # ΔG, ΔH, ΔS (ITC combo)
│   │   └── quality.py                # Signal-to-noise, drift, saturation
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── pdf_generator.py          # PDF reports
│   │   ├── html_generator.py         # HTML dashboards
│   │   ├── chart_builder.py          # Matplotlib/plotly charts
│   │   └── templates/
│   │       ├── standard_report.html
│   │       ├── kinetics_analysis.html
│   │       └── dose_response.html
│   ├── io/
│   │   ├── __init__.py
│   │   ├── excel_loader.py           # Load .xlsx from Affilabs.core
│   │   ├── csv_loader.py             # Load generic CSV
│   │   ├── json_loader.py            # Load JSON
│   │   └── animl_loader.py           # Load AnIML
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── baseline_correction.py    # Baseline subtraction
│   │   ├── normalization.py          # Min-max, z-score
│   │   ├── smoothing.py              # Savitzky-Golay, Butterworth
│   │   └── alignment.py              # Time/wavelength alignment
│   ├── models/
│   │   ├── __init__.py
│   │   ├── langmuir_1to1.py          # Simple 1:1 binding
│   │   ├── bivalent_analyte.py       # Bivalent analyte model
│   │   └── kinetic_fit.py            # ka/kd fitting
│   └── utils/
│       ├── __init__.py
│       ├── validators.py             # Data validation
│       ├── converters.py             # Unit conversion
│       └── statistics.py             # Statistical analysis
```

---

## Core API

### Experiment Class

```python
from affilabs.data import Experiment

# Load from Affilabs.core export
exp = Experiment.from_excel(
    filepath="/data/experiment_2026_02_18.xlsx",
    metadata={
        "ligand": "Antibody XYZ",
        "sensor": "Gold, dextran-coated",
    }
)

# OR create manually
exp = Experiment(
    name="Dose-Response Titration",
    device_sn="FLMT09116",
    operator="lucia",
)

# Access data
exp.metadata          # Dict of experiment metadata
exp.cycles           # List of Cycle objects
exp.channels         # Dict of Channel objects: {A: Channel, B: ..., ...}
exp.wavelengths      # Array of wavelengths (nm)
exp.recording_start  # Datetime

# Per-channel operations
channel_a = exp.get_channel("A")
channel_a.raw_data      # Array of raw counts
channel_a.transmission  # Array of transmission %
channel_a.wavelengths   # Corresponding wavelengths

# Cycle-level access
baseline = exp.get_cycles(type="Baseline")[0]
conc_cycles = exp.get_cycles(type="Concentration")

for cycle in conc_cycles:
    print(f"{cycle.type}: {cycle.concentration}")

# Calculate metrics
metrics = exp.calculate_metrics()
print(metrics)
# {
#   "channels": {
#     "A": {
#       "binding_curves": [...],
#       "kinetics": {ka, kd, Kd},
#       "signal_quality": "good",
#     },
#     ...
#   }
# }

# Generate report
exp.generate_report(
    output_dir="/reports/",
    format="pdf",        # or "html", "both"
    include_charts=True,
    include_statistics=True,
)
```

### Cycle Class

```python
cycle = Cycle.from_dict({
    "id": 2,
    "type": "Concentration",
    "start_time": 300,
    "duration": 300,
    "concentration": "100nM",
    "channels": ["A", "B"],
})

# Access cycle data
cycle.type              # "Concentration"
cycle.concentration     # "100nM"
cycle.start_time       # Seconds
cycle.duration         # Seconds
cycle.time_range       # (start, end) tuple
cycle.phase            # "association", "dissociation", "plateau"

# Get data slice for this cycle
time_slice = cycle.get_time_data()           # Times relative to cycle start
transmission_a = cycle.get_channel_data("A") # Transmission for channel A

# Analyze cycle
binding_rate = cycle.calculate_association_rate("A")  # %/sec
dissociation_rate = cycle.calculate_dissociation_rate("A")  # %/sec
```

### Channel Class

```python
channel = exp.get_channel("A")

# Properties
channel.name            # "A"
channel.raw_counts      # Array
channel.transmission    # Array (%)
channel.baseline        # Float (%)
channel.wavelengths     # Array

# Quality metrics
channel.signal_quality  # "good" | "fair" | "poor"
channel.saturation_pixels  # Int
channel.baseline_drift  # Float (%)
channel.noise_level     # Float (std dev of baseline)

# Analysis
channel.find_peaks()    # List of peak indices
channel.calculate_snr() # Signal-to-noise ratio
channel.detect_spikes() # Outlier detection
```

---

## Metrics Calculation

### Kinetics Metrics

```python
from affilabs.data.metrics import calculate_kinetics

# Fit association/dissociation curves
kinetics = calculate_kinetics(
    time=array([...]),
    response=array([...]),
    model="langmuir_1to1",
    t_assoc=(300, 600),  # Association window (seconds)
    t_dissoc=(600, 900), # Dissociation window
)

# Result
{
    "ka": 1.5e5,                # Association rate constant (M^-1 s^-1)
    "kd": 1.2e-3,               # Dissociation rate constant (s^-1)
    "Kd": kd / ka,              # Dissociation constant (M)
    "chi_squared": 0.95,        # Fit quality (0-1, higher is better)
    "r_squared": 0.998,         # R² of fit
    "t_half": -np.log(2) / kd,  # Half-life (seconds)
}
```

### Binding Metrics

```python
from affilabs.data.metrics import calculate_binding_affinity

# Fit dose-response curve
binding = calculate_binding_affinity(
    concentrations=[10e-9, 50e-9, 100e-9, 500e-9],  # M
    responses=[2000, 4500, 6200, 7100],              # RU (response units)
    model="langmuir_1to1",
)

# Result
{
    "EC50": 75e-9,              # Concentration at 50% max response (M)
    "Kd": 75e-9,                # Dissociation constant
    "Rmax": 8000,               # Maximum response (RU)
    "chi_squared": 0.92,        # Fit quality
    "hill_coefficient": 1.05,   # Cooperativity (>1 = positive, <1 = negative)
}
```

### Quality Metrics

```python
from affilabs.data.metrics import assess_data_quality

quality = assess_data_quality(
    channel_data=channel_a,
    baseline_threshold_percent=2.0,
    saturation_threshold_pixels=100,
)

# Result
{
    "baseline_drift": 1.3,           # % over recording
    "saturation_pixels": 45,         # Pixels at 255 counts
    "signal_to_noise": 120,          # SNR ratio
    "outliers_detected": 2,          # Number of spikes
    "overall_quality": "good",       # good | fair | poor
    "warnings": [
        "Baseline drift 1.3% (threshold 2.0%) — acceptable",
        "Minor outliers detected (2) — recommend smoothing",
    ],
}
```

---

## Report Generation

### PDF Report

```python
from affilabs.data.reporting import PDFGenerator

pdf = PDFGenerator(experiment=exp)
pdf.add_metadata_page()
pdf.add_summary_statistics()
pdf.add_kinetics_analysis()
pdf.add_binding_curves()
pdf.add_quality_assessment()
pdf.add_raw_data_charts()
pdf.save("/reports/experiment_2026_02_18.pdf")
```

**Output**: Multi-page PDF with:
- Title page (experiment metadata)
- Summary statistics (per-cycle, per-channel)
- Kinetics analysis (ka, kd, Kd with fit curves)
- Binding curves (dose-response plots)
- Quality assessment (baseline drift, saturation, SNR)
- Raw data visualizations (spectrograms, time series)
- Appendix (raw numbers, all data tables)

### HTML Dashboard

```python
from affilabs.data.reporting import HTMLGenerator

html = HTMLGenerator(experiment=exp)
html.set_template("standard_report")
html.add_interactive_charts()  # Plotly charts (zoom, hover)
html.add_data_table()           # Interactive table
html.add_metadata()
html.save("/reports/experiment_2026_02_18.html")
```

**Output**: Standalone HTML with:
- Interactive plotly charts (zoom, pan, legend toggle)
- Summary statistics table
- Sortable/filterable data table
- Metadata section
- Self-contained (no external dependencies needed)

---

## Integration with External Tools

### Export to GraphPad Prism

```python
exp.export_to_prism(
    output_path="/data/prism_ready.xlsx",
    include_analysis_sheets=True,
)
```

**Prism format**:
- Column A: Time/Concentration
- Columns B-E: Channels A-D
- XY layout (ready for curve fitting)
- Analysis sheet with control samples

### Export to Origin

```python
exp.export_to_origin(
    output_path="/data/origin.opj",
    plots=["kinetics", "dose_response"],
)
```

**Origin format**:
- Worksheets per channel
- Pre-built plots with formatting
- Analysis parameters metadata

### R/Python Integration

```python
# Numpy array export for external analysis
data_dict = exp.to_numpy()
# {
#   "time": array([...]),
#   "channels": {
#     "A": array([...]),
#     "B": array([...]),
#   },
#   "wavelengths": array([...]),
# }

# Or Pandas DataFrame (R-compatible)
df = exp.to_dataframe()  # Long format: time, channel, transmission
df.to_csv("experiment.csv")
```

---

## Jupyter Integration

```python
import affilabs.data as ad

# Load from Excel
exp = ad.Experiment.from_excel("experiment.xlsx")

# Exploratory analysis
import matplotlib.pyplot as plt

fig, ax = plt.subplots(2, 2, figsize=(12, 8))

for i, ch in enumerate(['A', 'B', 'C', 'D']):
    ax.flat[i].plot(exp.channels[ch].time, exp.channels[ch].transmission)
    ax.flat[i].set_title(f"Channel {ch}")
    ax.flat[i].set_xlabel("Time (s)")
    ax.flat[i].set_ylabel("Transmission (%)")

plt.tight_layout()
plt.show()

# Calculate metrics
metrics = exp.calculate_metrics()
print(f"Channel A Kd: {metrics['channels']['A']['kinetics']['Kd']:.2e} M")

# Generate full report
exp.generate_report("/reports/", format="html")
```

---

## Implementation Roadmap

### Phase 1: Core API (Q2 2026)
- [ ] Experiment, Cycle, Channel classes
- [ ] Basic I/O (load from Excel, save to CSV)
- [ ] Kinetics fitting (Langmuir 1:1 model)
- [ ] Data validation

### Phase 2: Metrics & Analysis (Q2 2026)
- [ ] Quality assessment
- [ ] Binding affinity calculations
- [ ] Peak finding and alignment
- [ ] Statistical analysis

### Phase 3: Reporting (Q3 2026)
- [ ] PDF generator
- [ ] HTML dashboard
- [ ] Chart builder (matplotlib + plotly)
- [ ] Template system

### Phase 4: Advanced Models (Q3 2026)
- [ ] Bivalent analyte model
- [ ] Kinetic deconvolution
- [ ] Thermodynamic calculations
- [ ] Fitted rate constant export

### Phase 5: Integration (Q4 2026)
- [ ] Prism export
- [ ] Origin export
- [ ] Jupyter integration examples
- [ ] API documentation

---

## Design Decisions

### Why Separate Package?
1. **Decoupling**: Analysis logic independent of Affilabs.core UI
2. **Reusability**: Used standalone (not just in main app)
3. **Dependency management**: Optional numpy/scipy/pandas only needed for analysis
4. **Testability**: Core data processing tested in isolation

### Why Langmuir 1:1 as Default?
- Most common SPR binding model (simple, robust)
- Other models can be added as extensions
- Fits well for monovalent ligands

### Why Standalone Reports?
- No dependency on external tools (no Office required)
- Reproducible (HTML/PDF fully self-contained)
- Shareable (email, cloud, GitHub)

---

## Testing Strategy

### Unit Tests
```python
# test_kinetics.py
def test_langmuir_1to1_fit():
    time = np.linspace(0, 1000, 1000)
    ka, kd = 1e5, 1e-3
    response = simulate_langmuir_response(time, ka, kd)

    fitted = calculate_kinetics(time, response, model="langmuir_1to1")
    assert abs(fitted['ka'] - ka) / ka < 0.05  # Within 5%
    assert abs(fitted['kd'] - kd) / kd < 0.05
```

### Integration Tests
```python
# test_experiment_workflow.py
def test_load_export_metrics():
    exp = Experiment.from_excel("test_data.xlsx")
    metrics = exp.calculate_metrics()
    assert "channels" in metrics
    assert all(ch in metrics["channels"] for ch in exp.channels)
```

### End-to-End Tests
```python
# test_full_analysis.py
def test_full_workflow():
    exp = Experiment.from_excel("experiment.xlsx")
    exp.generate_report("/tmp/", format="pdf")
    assert Path("/tmp/experiment_report.pdf").exists()
```

---

## Dependencies

### Core
- `numpy`, `scipy` — Numerical computation
- `pandas` — Data manipulation
- `openpyxl` — Excel I/O

### Optional (Reporting)
- `matplotlib`, `plotly` — Charting
- `reportlab` — PDF generation
- `jinja2` — HTML templating

### Optional (Advanced)
- `lmfit` — Non-linear fitting
- `sympy` — Symbolic math (thermodynamic equations)

---

## API Stability

This module will follow semantic versioning:
- **v0.1.0** (beta): Core API, expect changes
- **v1.0.0** (stable): API frozen, backward compatibility
- **v2.0.0+** (future): Major releases only break API

---

## References

- **Affilabs.core Excel export format**: See `docs/architecture/DATA_EXPORT_ARCHITECTURE.md`
- **SPR metrics reference**: Karlsson et al. (2004), Homola et al. (2006)
- **Kinetics fitting**: Schuck & Minton (1996), Ridgeway et al. (2004)

---

## Contact & Collaboration

- **Lead**: Data Analysis Team
- **Review**: Software Architecture, QA
- **Community Input**: User feedback from v2.0.5+ alpha testing
