# Lensless Spectral SPR — Technology Requirements Document

**Technology Name:** Lensless Spectral SPR (Wavelength Interrogation)  
**Configuration:** Kretschmann Prism  
**Product Line:** P4SPR (primary), P4PRO, P4PROPLUS  
**Owner:** Affinite Instruments  
**Status:** 🟢 Production — Retroactive Documentation  
**Last Updated:** February 18, 2026

---

## 📋 Table of Contents

1. [Technology Overview](#1-technology-overview)
2. [Physical Principle](#2-physical-principle)
3. [Optical System Architecture](#3-optical-system-architecture)
4. [Signal Processing Chain](#4-signal-processing-chain)
5. [Hardware Requirements](#5-hardware-requirements)
6. [Performance Specifications](#6-performance-specifications)
7. [Data Quality Requirements](#7-data-quality-requirements)
8. [Peak Finding Algorithms](#8-peak-finding-algorithms)
9. [Calibration Requirements](#9-calibration-requirements)
10. [Implementation Status](#10-implementation-status)
11. [Known Limitations](#11-known-limitations)
12. [References](#12-references)

---

## 1. Technology Overview

### What is Lensless Spectral SPR?

Affinite's Surface Plasmon Resonance (SPR) technology is based on **wavelength interrogation** in a **Kretschmann prism configuration** using **lensless optics**. This is fundamentally different from conventional angular SPR systems (e.g., Biacore).

| Property | Affinite Lensless Spectral SPR | Angular SPR (Biacore) |
|----------|-------------------------------|----------------------|
| **Interrogation method** | **Wavelength** (spectral scan) | Angle (fixed wavelength) |
| **Light source** | White LED (broadband) | Monochromatic laser |
| **Detector** | Spectrometer (Ocean Optics) | Photodiode array |
| **Optics** | **Lensless** — no focusing optics | Lens-based optical train |
| **Configuration** | Kretschmann prism | Kretschmann prism |
| **Polarization control** | Servo-actuated polarizer | Fixed or electronically rotated |
| **Signal output** | **Resonance wavelength (nm)** | Resonance units (RU) |
| **Sensorgram Y-axis** | Wavelength (nm) vs. time | RU vs. time |
| **SPR feature shape** | **Broad dip** (~20–40 nm FWHM) | Narrow angular peak |
| **Acquisition rate** | 2–5 Hz (4 channels) | 1–10 Hz (single or multi-spot) |

### Why Lensless?

**Advantages:**
- **Simplicity** — fewer optical components = lower cost, less alignment sensitivity
- **Robustness** — no lenses to misalign, scratch, or introduce aberrations
- **Fiber coupling** — direct coupling to spectrometer via optical fiber
- **Field-deployable** — compact, portable, no delicate optics

**Trade-offs:**
- **Lower spatial resolution** — no focusing = larger illumination area (~1 mm spot)
- **Broad spectral feature** — wavelength interrogation produces wider dip than angular (20–40 nm FWHM vs. narrow angular peak)
- **Complex peak finding** — broad dip requires sophisticated algorithms to track sub-nm shifts

---

## 2. Physical Principle

### Kretschmann Configuration

```
White LED (broadband 400–900 nm)
  ↓
Servo polarizer (P-pol or S-pol)
  ↓
Glass prism (BK7, n=1.515 @ 633nm)
  ↓
Gold-coated sensor chip (50 nm Au film)
  ↓
Evanescent wave at Au/buffer interface
  ↓ (SPR coupling at resonance wavelength)
Reflected light (transmitted through prism)
  ↓
Optical fiber (600 µm core, multimode)
  ↓
Spectrometer (Ocean Optics Flame-T, USB4000)
```

### SPR Resonance Condition

At the resonance wavelength $\lambda_{\text{SPR}}$, the incident light couples to surface plasmons at the Au/buffer interface, causing **maximum absorption** → **minimum transmission**.

The resonance condition depends on:
- **Refractive index at the interface** — binding events increase local RI → shift $\lambda_{\text{SPR}}$
- **Gold film thickness** — optimized at ~50 nm for visible light
- **Incident angle** — fixed by prism geometry (~68° for BK7/Au/water)
- **Wavelength** — scanned via spectrometer (560–720 nm active range)

### Signal Polarity: Blue Shift on Binding

**Critical physics fact:** When analyte binds to the sensor surface, the resonance wavelength **DECREASES** (blue shifts to shorter wavelength).

$$
\Delta \lambda_{\text{SPR}} < 0 \quad \text{(binding event)}
$$

**This is opposite to angular SPR convention**, where binding increases RU (positive signal). Injection detection algorithms must look for a **DROP** in wavelength, not a rise.

### Polarization: P vs. S

- **P-polarization (TM mode)**: Electric field parallel to plane of incidence → **couples to surface plasmons** → SPR dip visible
- **S-polarization (TE mode)**: Electric field perpendicular → **does not couple** → no SPR feature, flat transmission

**Importance:** 
- S-pol serves as the **reference spectrum** (no SPR, only LED/detector characteristics)
- P/S ratio cancels LED intensity drift, fiber coupling variations, and detector non-uniformity
- Transmission spectrum = P-pol / S-pol × 100%

---

## 3. Optical System Architecture

### Light Path

```
┌─────────────────────────────────────────────────────────────────┐
│  LED Controller (PicoP4SPR, PicoP4PRO, PicoP4PROPLUS)          │
│  4× identical white LEDs (channels A, B, C, D)                  │
│  Spectral range: 400–900 nm (SPR-active: 560–720 nm)           │
│  Time-multiplexed: SEQUENTIAL firing, never simultaneous        │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Servo Polarizer (barrel or circular type)                      │
│  Rotates between P-pol and S-pol positions                      │
│  Calibrated positions stored in device_config.json              │
│  Settling time: ~50-100 ms after rotation                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Prism + Sensor Chip (BK7 glass / 50 nm Au / functionalized)   │
│  Flow cells: 4 independent channels (A, B, C, D)                │
│  Chip size: ~12 × 24 mm (4 flow cell regions)                   │
│  Each LED illuminates one flow cell region (~1 mm spot)         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓ (SPR coupling → absorption at resonance)
┌─────────────────────────────────────────────────────────────────┐
│  Optical Fiber (multimode, 600 µm core)                         │
│  Direct coupling (no lenses)                                    │
│  1-2 meters length (controller to spectrometer)                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Spectrometer (Ocean Optics Flame-T or USB4000)                 │
│  Detector: 2048-pixel CCD (Flame-T) or 3648-pixel CCD (USB4000)│
│  Wavelength range: 200–1000 nm (SPR ROI: 560–720 nm)           │
│  Integration time: 10–100 ms (optimized per setup)             │
│  Readout: USB connection to PC (libseabreeze/Ocean Direct)     │
└─────────────────────────────────────────────────────────────────┘
```

### LED System Details

- **4 channels (A, B, C, D)** — each LED illuminates one flow cell region
- **Identical white LEDs** — no spectral differences between channels; all LEDs are the same part number
- **Time-multiplexed acquisition** — LEDs fire one at a time:
  1. Fire LED A → Rotate to P-pol → Read spectrum → Rotate to S-pol → Read spectrum
  2. Fire LED B → (repeat)
  3. Fire LED C → (repeat)
  4. Fire LED D → (repeat)
  5. Return to LED A (next acquisition cycle)
- **Full cycle time**: ~1–2 seconds for all 4 channels × 2 polarizations = 8 spectra
- **Acquisition rate**: 2–5 Hz for full 4-channel readout (cycle sync mode)

**No simultaneous multi-channel acquisition** — hardware limitation of single-spectrometer design.

---

## 4. Signal Processing Chain

### End-to-End Data Flow

```
Raw Spectrum (P-pol, S-pol per channel)
  ↓
[Step 1] Dark Subtraction (SpectrumPreprocessor)
  → Remove detector dark current baseline (~3500 counts for USB4000)
  ↓
[Step 2] Transmission Calculation (P/S Ratio)
  → T = (P - dark) / (S - dark) × 100%
  → Cancels LED drift, fiber coupling, detector non-uniformity
  ↓
[Step 3] Baseline Correction (TransmissionProcessor)
  → Methods: percentile, polynomial, off_spr, none
  → Flattens spectrum, removes long-wavelength tilt
  ↓
[Step 4] Savitzky-Golay Smoothing (optional)
  → Window: 11–21 points, polynomial order 2–3
  → Reduces high-frequency noise
  ↓
[Step 5] Peak Finding (Multiple Pipelines Available)
  → Centroid, Fourier, Polynomial, Hybrid, Direct Argmin, Consensus
  → Output: Resonance wavelength λ_SPR (nm)
  ↓
[Step 6] Temporal Filtering (optional)
  → Kalman filter, median filter
  → Reduces frame-to-frame jitter
  ↓
Resonance Wavelength (nm) → Sensorgram Y-axis value
```

### Transmission Spectrum

The transmission spectrum is the **primary intermediate data product**:

$$
T(\lambda) = \frac{I_P(\lambda) - I_{\text{dark}}}{I_S(\lambda) - I_{\text{dark}}} \times 100\%
$$

Where:
- $I_P(\lambda)$ = P-pol intensity spectrum (raw counts)
- $I_S(\lambda)$ = S-pol intensity spectrum (raw counts)
- $I_{\text{dark}}$ = Dark spectrum (detector baseline, no LED)
- $T(\lambda)$ = Transmission spectrum (0–100%, SPR dip visible)

**Typical transmission spectrum characteristics:**
- **Baseline level**: 80–95% (flat regions away from SPR)
- **Dip depth**: 10–30% (at resonance wavelength)
- **Dip width (FWHM)**: 20–40 nm (broad compared to angular SPR)
- **Dip position**: 600–670 nm typical for water-based assays

---

## 5. Hardware Requirements

### Spectrometer Specifications

| Parameter | Ocean Optics Flame-T | Ocean Optics USB4000 |
|-----------|---------------------|---------------------|
| **Pixels** | 2048 | 3648 |
| **Wavelength range** | 200–1000 nm | 200–850 nm |
| **SPR ROI** | 560–720 nm | 560–720 nm |
| **Integration time** | 10–100 ms | 10–100 ms |
| **Dark noise** | ~3500 counts baseline | ~3500 counts baseline |
| **Saturation level** | 65535 counts (16-bit) | 65535 counts (16-bit) |
| **Connection** | USB 3.0 (WinUSB driver) | USB 2.0 (WinUSB driver) |
| **API** | seabreeze / Ocean Direct | seabreeze / Ocean Direct |

**Detector profile files:** `detector_profiles/Flame-T.json`, `detector_profiles/USB4000.json`

### LED Controller Specifications

| Parameter | Value |
|-----------|-------|
| **LED channels** | 4 (A, B, C, D) |
| **LED type** | White broadband (400–900 nm) |
| **Intensity range** | 0–255 (8-bit PWM) |
| **Typical intensity** | 150–200 (calibrated per channel) |
| **Settling time** | 50 ms after intensity change |
| **Communication** | USB serial (virtual COM port) |
| **Protocol** | Custom binary protocol (PicoP4SPR) |

### Servo Polarizer Specifications

| Parameter | Barrel Type | Circular Type |
|-----------|------------|--------------|
| **Rotation range** | 0–180° | 0–360° continuous |
| **Position resolution** | 0.1° | 0.1° |
| **Settling time** | 100 ms | 100 ms |
| **P-pol position** | Device-specific (calibrated) | Device-specific (calibrated) |
| **S-pol position** | P-pol + 90° | Device-specific (calibrated) |
| **Calibration method** | Simple (2 peaks) | Complex (quadrant search) |

**Calibration data:** Stored in `config/devices/{serial}/device_config.json`

---

## 6. Performance Specifications

### Target Performance Metrics

| Metric | Target | Typical Achieved | Unit |
|--------|--------|-----------------|------|
| **Baseline noise (RMS)** | < 2.0 | 0.5–1.5 | RU |
| **Baseline drift** | < 1.0 | 0.2–0.5 | RU/min |
| **Resolution** | < 0.01 | 0.002–0.005 | nm |
| **Detection limit (Δλ)** | 0.01 | 0.005 | nm |
| **Acquisition rate** | 2–5 | 2–3 | Hz (4ch) |
| **SNR** | > 60:1 | 80:1–120:1 | — |
| **Peak-to-peak noise** | < 5 | 2–4 | RU |

**Conversion factor:** 1 nm ≈ 355 RU (system-specific calibration)

### Operating Conditions

| Parameter | Range | Notes |
|-----------|-------|-------|
| **Temperature** | 15–30 °C | Detector thermal stabilization required |
| **Humidity** | 20–80% RH | Non-condensing |
| **Buffer temperature** | 20–25 °C | ±0.1 °C stability recommended for kinetics |
| **Flow rate (P4PRO)** | 5–100 µL/min | Pulse-free (syringe pump) |
| **Flow rate (P4PROPLUS)** | 25 µL/min fixed | Peristaltic (pulsatile) |
| **Flow rate (P4SPR)** | Manual | User-controlled syringe injection |

---

## 7. Data Quality Requirements

### Quality Metrics (QC Validation)

After calibration, the system must meet these quality thresholds:

| Metric | Threshold | Consequence if Failed |
|--------|-----------|----------------------|
| **SNR** | > 40:1 | Low signal quality — recalibrate, check LED brightness |
| **LED convergence error** | < 5% | Poor LED balance — rerun LED calibration |
| **P/S ratio range** | 50–150% | Inverted or saturated spectra — check servo positions |
| **Dark noise** | < 8000 counts | Detector issue — check temperature, USB connection |
| **S-pol flatness** | Std < 5% | S-pol has SPR feature (wrong polarity) — recalibrate servo |
| **Integration time** | 10–100 ms | Outside range — detector saturation or too dim |

**QC Report:** Generated automatically after calibration, shown to user in `CalibrationQCDialog`.

### Signal Anomalies to Detect

| Anomaly | Detection Method | Typical Cause |
|---------|-----------------|---------------|
| **Spiky noise** | High-frequency variance > threshold | Air bubble, loose fiber, electrical noise |
| **Baseline drift** | Linear slope > 0.5 nm/min | Thermal drift, incomplete priming, chip degradation |
| **LED saturation** | Raw counts > 60000 | LED too bright, integration time too long |
| **LED too dim** | Raw counts < 3000 | LED too dim, integration time too short, fiber disconnected |
| **No SPR dip** | Dip depth < 5% | Wrong polarization, no gold film, fiber misaligned |
| **Inverted dip (peak)** | Transmission > 95% at expected dip | P/S inverted — recalibrate servo |

---

## 8. Peak Finding Algorithms

Affinite's lensless SPR system has **9 implemented peak-finding pipelines** to handle the broad spectral dip. Different pipelines excel in different noise regimes.

### Available Pipelines

| Pipeline | Method | Speed | Noise Robustness | Best For |
|----------|--------|-------|-----------------|----------|
| **Direct Argmin** | `np.argmin()` on SPR ROI | < 0.1 ms | Medium | Clean signals, fast prototyping |
| **Centroid** | Weighted average around dip | 0.5 ms | High | Broad dips, asymmetric peaks |
| **Fourier** | DST + IDCT + linear regression | 2 ms | Very High | Noisy signals, SNR-aware weighting |
| **Polynomial** | Gaussian or Lorentzian fit | 5 ms | Medium | Symmetric dips, sub-pixel precision |
| **Hybrid** | Argmin + local polynomial refinement | 1 ms | High | Balanced speed/precision |
| **Hybrid Original** | Legacy hybrid (argmin + parabolic fit) | 1 ms | High | Backward compatibility |
| **Consensus** | Majority vote from multiple pipelines | 10 ms | Very High | Ultra-stable, cross-validation |
| **Adaptive MultiFeature** | FWHM, depth, slope analysis + temporal coherence | 3 ms | Very High | Advanced QC, research applications |
| **Batch Savgol** | Batch Savitzky-Golay + argmin | 0.5 ms | Medium-High | Batch processing, offline analysis |

**Active pipeline selection:** Set in `affilabs/utils/processing_pipeline.py` via `PipelineRegistry`. Default: **Hybrid Pipeline** (good balance of speed and robustness).

### Fourier Pipeline (Most Robust)

The **Fourier pipeline** is the gold standard for noisy signals. It uses Discrete Sine Transform (DST) to enhance the SPR dip feature in the frequency domain:

**Algorithm:**
1. **Linear detrending** — Remove baseline slope
2. **DST (Discrete Sine Transform)** — Transform to frequency domain with SNR-aware weights
3. **Low-pass filtering** — Suppress high-frequency noise
4. **IDCT (Inverse Discrete Cosine Transform)** — Return to spatial domain (denoised)
5. **Zero-crossing detection** — Find where derivative crosses zero (dip center)
6. **Linear regression refinement** — Sub-pixel interpolation (165-point window)

**Advantages:**
- **SNR-aware weighting** — uses S-pol reference to weight by signal quality per wavelength
- **Sub-pixel precision** — typically achieves 0.002–0.005 nm resolution
- **Noise rejection** — Fourier regularization parameter α = 2000 (optimized)

**Implementation:** `affilabs/utils/pipelines/fourier_pipeline.py`, `affilabs/utils/spr_signal_processing.py::find_resonance_wavelength_fourier()`

---

## 9. Calibration Requirements

Calibration is the **critical prerequisite** for all SPR measurements. Without calibration, the system cannot:
- Determine proper LED intensities
- Validate S/P polarizer orientation
- Optimize integration time
- Establish S-pol reference spectra

### Calibration Types

1. **Startup Calibration** (auto, 1–2 min)
   - Runs automatically on Power On
   - Quick LED convergence + QC validation
   - Must pass QC before acquisition allowed

2. **Simple LED Calibration** (10–20 sec)
   - For same-type sensor swaps
   - Adjusts LED intensities only
   - Requires existing LED model

3. **Full LED Calibration** (5–10 min)
   - After new sensor or hardware changes
   - Rebuilds LED response model
   - Includes servo validation

4. **Servo Position Calibration** (1.4 min barrel, ~13 min circular)
   - First-time setup or after servo replacement
   - Finds P-pol and S-pol positions
   - Stores in `device_config.json`

5. **OEM Optical Calibration** (10–15 min, factory-only)
   - Afterglow characterization (LED phosphor decay)
   - Requires `DEV=True` in settings
   - Generates `optical_calibration.json`

**Calibration documentation:** `docs/calibration/CALIBRATION_MASTER.md` (3939 lines, comprehensive)

### Calibration Data Storage

| File | Contents | Purpose |
|------|---------|---------|
| `config/devices/{serial}/device_config.json` | Servo positions (P-pol, S-pol angles), LED model parameters | Per-device configuration |
| `config/devices/{serial}/optical_calibration.json` | Afterglow time constants per channel × integration time | Afterglow correction (OEM feature) |
| `config/devices/{serial}/calibration_checkpoint.pkl` | Full calibration state (LED models, references, QC data) | Fast reload on app restart |

---

## 10. Implementation Status

### ✅ Implemented Features

| Feature | Status | Implementation |
|---------|--------|---------------|
| **Lensless optical path** | ✅ Complete | Hardware design (prism, fiber, spectrometer) |
| **4-channel LED time-multiplexing** | ✅ Complete | `data_acquisition_manager.py`, `PicoP4SPRHAL` |
| **P/S ratio transmission calculation** | ✅ Complete | `SpectrumPreprocessor`, `TransmissionProcessor` |
| **9 peak-finding pipelines** | ✅ Complete | `affilabs/utils/pipelines/*.py` |
| **Baseline correction (4 methods)** | ✅ Complete | `TransmissionProcessor` (percentile, polynomial, off_spr, none) |
| **Savitzky-Golay smoothing** | ✅ Complete | `scipy.signal.savgol_filter` integration |
| **Temporal filtering** | ✅ Complete | Kalman, median filter (`TemporalFilter` class) |
| **Calibration system (5 types)** | ✅ Complete | `calibration_service.py`, detailed docs in `docs/calibration/` |
| **QC validation** | ✅ Complete | `CalibrationQCDialog`, SNR/LED error checks |
| **Detector profiles** | ✅ Complete | JSON profiles for Flame-T, USB4000 |
| **SNR-aware Fourier weighting** | ✅ Complete | Uses S-pol reference to weight by signal quality |
| **Blue shift detection (injection)** | ✅ Complete | `InjectionCoordinator`, looks for wavelength DROP |
| **Servo calibration (barrel + circular)** | ✅ Complete | `servo_calibration.py` (2 methods) |
| **Afterglow correction** | ✅ Complete | OEM feature, `optical_calibration.json` |

### 🔄 Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| **Single spectrometer = sequential channel readout** | 4-channel acquisition takes 1–2 sec | Not fixable (hardware) — use cycle sync timing |
| **Broad spectral dip (~30 nm FWHM)** | Lower resolution than angular SPR | Fourier/Consensus pipelines compensate |
| **Lensless = large spot size (~1 mm)** | No spatial imaging, single-spot per channel | Multi-channel independence compensates |
| **Manual injection (P4SPR)** | ±15 sec inter-channel timing skew | P4PRO/PLUS solve with automated injection |
| **Afterglow (LED phosphor decay)** | Creates temporal bias if integration time changes | OEM calibration corrects (optional feature) |

---

## 11. References

### Technical Documentation

- **Signal Chain Walkthrough:** `docs/architecture/LIVE_DATA_FLOW_WALKTHROUGH.md`
- **Data Processing Pipeline:** `docs/architecture/DATA_PROCESSING_PIPELINE.md`
- **Calibration Master Doc:** `docs/calibration/CALIBRATION_MASTER.md`
- **Device Registration:** `docs/DEVICE_DATABASE_REGISTRATION.md`
- **Peak Finding Comparison:** `_scratch/analysis/walkthrough_peak_finding.py`
- **Integration Time Optimization:** `tools/optimize_integration_time.py`

### Source Code Locations

```
Spectrum Processing:
├── affilabs/core/spectrum_processor.py          # Main processor, pipeline coordinator
├── affilabs/core/spectrum_preprocessor.py       # Dark subtraction, P/S ratio
├── affilabs/core/transmission_processor.py      # Baseline correction, smoothing
└── affilabs/utils/spr_signal_processing.py      # Low-level SPR algorithms

Peak Finding Pipelines:
├── affilabs/utils/pipelines/centroid_pipeline.py
├── affilabs/utils/pipelines/fourier_pipeline.py
├── affilabs/utils/pipelines/polynomial_pipeline.py
├── affilabs/utils/pipelines/hybrid_pipeline.py
├── affilabs/utils/pipelines/direct_argmin_pipeline.py
├── affilabs/utils/pipelines/consensus_pipeline.py
├── affilabs/utils/pipelines/adaptive_multifeature_pipeline.py
├── affilabs/utils/pipelines/batch_savgol_pipeline.py
└── affilabs/utils/pipelines/hybrid_original_pipeline.py

Hardware Interfaces:
├── affilabs/hardware/device_interface.py        # Spectrometer interface
├── affilabs/hardware/servo_adapter.py           # Polarizer control
└── affilabs/utils/hal/picop4spr_hal.py          # LED controller HAL

Calibration:
├── affilabs/services/calibration_service.py     # Calibration orchestrator
├── affilabs/dialogs/calibration_qc_dialog.py    # QC validation UI
└── scripts/servo_calibration.py                 # Servo position calibration
```

### Key Physics Constants

| Constant | Value | Source |
|----------|-------|--------|
| **Gold film thickness** | 50 nm | Standard for SPR in visible |
| **Prism refractive index** | 1.515 @ 633nm | BK7 glass |
| **Incident angle** | ~68° (Kretschmann) | Fixed by prism geometry |
| **SPR wavelength range** | 560–720 nm | Gold plasmon resonance in visible |
| **Resonance wavelength (water)** | 600–670 nm typical | Depends on chip, buffer RI |
| **Conversion factor (nm → RU)** | 355 RU/nm | System-specific calibration |
| **Dip width (FWHM)** | 20–40 nm | Spectral interrogation characteristic |

---

## 12. Validation & Testing

### Baseline Stability Test

**Protocol:**
1. Run 10-minute baseline (buffer only, no analyte)
2. Record sensorgram (all 4 channels)
3. Calculate RMS noise and peak-to-peak drift

**Pass Criteria:**
- RMS noise < 2 RU
- Peak-to-peak drift < 5 RU over 10 min
- No spiky artifacts (air bubbles)

**Test scripts:** `_scratch/analysis/analyze_baseline_peak_to_peak.py`

### Peak-Finding Comparison Study

**Protocol:**
1. Capture 100+ baseline spectra (stable conditions)
2. Run all 9 pipelines on same data
3. Calculate mean, std, range for each pipeline
4. Compare speed (ms per spectrum)

**Results:** Direct Argmin and Hybrid pipelines are top 2 for speed/stability balance. Fourier pipeline wins for noisy signals.

**Test scripts:** `_scratch/analysis/walkthrough_peak_finding.py`, `tools/analysis/compare_peak_vs_dip_finding.py`

### Integration Time Optimization

**Protocol:**
1. Test 7 integration times: 20, 30, 40, 50, 60, 80, 100 ms
2. Measure SNR, peak stability, acquisition rate
3. Select optimal integration time per channel

**Target:** Integration time that achieves < 2 RU noise with maximum acquisition rate.

**Test scripts:** `tools/optimize_integration_time.py`

---

## Appendix A: Conversion Factors

### Wavelength ↔ RU

System-specific calibration: **1 nm = 355 RU**

This is derived from empirical testing and assumes:
- 50 nm gold film
- Water-based buffer (RI ≈ 1.33)
- 600–670 nm operating range

**Not universal** — other SPR systems may use different conversion factors (e.g., Biacore uses ~1000 RU per RI unit change).

### Transmission ↔ Signal Quality

| Transmission Range | Interpretation |
|-------------------|----------------|
| 80–95% (baseline) | Normal — good signal |
| 50–80% (dip region) | SPR coupling — expected |
| > 95% | Too high — check S/P orientation, LED saturation |
| < 50% | Too low — LED too dim, fiber disconnected |

---

## Appendix B: Troubleshooting Decision Tree

```
User reports: "No SPR dip visible"
  ↓
1. Check transmission spectrum shape
   ├─ Flat (no dip) → Check polarizer (is P-pol active?)
   ├─ Peak (not dip) → P/S inverted — recalibrate servo
   └─ Noisy → Check fiber connection, LED brightness

2. Check QC metrics (last calibration)
   ├─ SNR < 40 → Recalibrate, check LED brightness
   ├─ P/S ratio out of range → Recalibrate servo
   └─ Integration time wrong → Rerun startup calibration

3. Check raw spectra
   ├─ Dark counts > 8000 → Detector temperature issue
   ├─ P-pol saturated (> 60000) → Reduce LED intensity
   └─ S-pol has dip → Wrong polarity — recalibrate servo

4. Check hardware
   ├─ Fiber disconnected → Reconnect, check coupling
   ├─ LED not lighting → Check controller connection
   └─ Servo not moving → Check servo cable, power
```

---

**Document Version:** 1.0  
**Author:** Affinite Instruments  
**Last Reviewed:** February 18, 2026  
**Status:** Production — captures existing implementation as of v2.0.5 beta
