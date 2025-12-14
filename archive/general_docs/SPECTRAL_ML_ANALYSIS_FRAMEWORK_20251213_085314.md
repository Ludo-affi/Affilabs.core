# AFfilab Spectral ML Analysis Framework
## Proprietary Intelligent Diagnostic System for SPR Biosensors

**Document Version:** 1.0
**Date:** October 22, 2025
**Status:** Core IP - Confidential
**Author:** AFfilab R&D Team

---

## Executive Summary

This document describes AFfilab's proprietary machine learning framework for real-time quality assessment of SPR biosensor measurements at the **raw spectral data level**. The system can distinguish between instrumental artifacts, consumable issues, and true analytical signals—enabling proactive quality control before downstream processing.

**Core Innovation:** Separate algorithm bias from physical signal to detect sensor recycling, contamination, and degradation in real-time from spectral characteristics alone.

---

## 1. System Philosophy

### 1.1 Proactive vs. Reactive Quality Control

**Traditional Approach (Reactive):**
```
Raw spectra → Transmission → Sensorgram → Peak tracking → ❌ Discover noise
                                                           ↓
                                             Too late - data already collected
```

**AFfilab Approach (Proactive):**
```
Raw spectra → ML Quality Assessment → ✅ Flag issues immediately
    ↓                                      ↓
    └─────────────────────────────────────┴→ Adaptive processing
                                              - Method selection
                                              - Bias correction
                                              - Signal validation
```

### 1.2 Core Principle

> **"If ML can recognize at the raw data level any issues that impact downstream processing, then we don't have to monitor as much downstream—just focus on the input raw data."**

This inverts the traditional quality control paradigm: **prevent bad data rather than detect it after collection**.

---

## 2. Technical Foundation

### 2.1 SPR Transmission Spectrum

The fundamental measurement is the **transmission spectrum**:

```
T(λ) = [P(λ) - P_dark(λ)] / [S(λ) - S_dark(λ)]
```

Where:
- **P(λ)**: P-polarization signal (sample mode, with sensor resonance)
- **S(λ)**: S-polarization signal (reference mode, no sensor resonance)
- **P_dark, S_dark**: Dark spectra for noise correction
- **λ**: Wavelength (or pixel index)

The **sensor resonance** appears as a dip in transmission at a specific wavelength. Tracking the dip position over time creates the **sensorgram** (analytical signal).

### 2.2 The Separation Problem

**Total Measured Shift = Physical Signal + Algorithm Bias + Noise**

```
Δλ_measured = Δλ_physical + Δλ_bias + ε
              ︸̅̅̅̅̅̅̅̅︸     ︸̅̅̅̅̅̅︸     ︸︸
               WANT      ARTIFACT  RANDOM
```

**Challenge:** Algorithm bias changes with peak shape, making it appear like signal when it's actually an artifact.

**Solution:** Characterize bias as a function of spectral features, then correct.

---

## 3. The AFfilab Diagnostic Framework

### 3.1 Multi-Level Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 1: Raw Spectral Feature Extraction                       │
├─────────────────────────────────────────────────────────────────┤
│ Input: S-mode and P-mode spectra                               │
│ Output: Transmission spectrum T(λ)                             │
│                                                                 │
│ Features extracted:                                             │
│  • Peak position (wavelength/pixel of minimum)                 │
│  • Peak depth (transmission % at minimum)                      │
│  • FWHM (full width at half maximum)                           │
│  • Peak asymmetry/skewness                                     │
│  • Peak sharpness (curvature at minimum)                       │
│  • Background slope/baseline trend                             │
│  • Signal-to-noise ratio                                       │
│  • Spectral quality metrics                                    │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 2: Algorithm Performance Prediction                      │
├─────────────────────────────────────────────────────────────────┤
│ Input: Spectral features from Level 1                          │
│ Output: Expected algorithm bias for each method                │
│                                                                 │
│ Bias models (empirically derived):                             │
│                                                                 │
│   Direct method:                                                │
│     bias = 0.607·depth - 0.268                                 │
│                                                                 │
│   Centroid method:                                              │
│     bias = 1.513·depth + 0.002·FWHM + 52.455·asymmetry - 0.961│
│                                                                 │
│   Polynomial method:                                            │
│     bias = 1.112·depth + 0.810·asymmetry - 0.831              │
│                                                                 │
│ Decision: Select best method for current spectral shape        │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 3: Physics-Informed Validation                           │
├─────────────────────────────────────────────────────────────────┤
│ Input: Measured features + algorithm bias estimate             │
│ Output: Deviation from expected SPR behavior                   │
│                                                                 │
│ SPR Theory (AFfilab empirical baseline):                       │
│  • Peak shifts to longer λ → becomes shallower + broader       │
│  • Sensitivity increases in certain wavelength regions         │
│  • Expected depth(λ) relationship                              │
│  • Expected FWHM(λ) relationship                               │
│                                                                 │
│ Validation checks:                                              │
│  ✓ Is depth within expected range for this wavelength?        │
│  ✓ Is FWHM within expected range?                             │
│  ✓ Is peak shape consistent with SPR physics?                 │
│  ✓ Is channel-to-channel variation within tolerance?          │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 4: Issue Classification & Action                         │
├─────────────────────────────────────────────────────────────────┤
│ Input: Features + bias + physics deviation                     │
│ Output: Quality classification + recommended action            │
│                                                                 │
│ Classification logic:                                           │
│                                                                 │
│  ✅ GOOD SIGNAL:                                               │
│     • Features within expected ranges                          │
│     • Low algorithm bias                                       │
│     • Physics-consistent behavior                              │
│     → Action: Proceed with standard processing                │
│                                                                 │
│  ⚠️  RECYCLED SENSOR:                                          │
│     • Peak broader than expected for wavelength                │
│     • Consistent pattern (not random)                          │
│     • Depth may be shallower than fresh sensor                 │
│     → Action: Flag for user review, apply correction          │
│                                                                 │
│  ⚠️  CONTAMINATED SENSOR:                                      │
│     • Peak position deviates from expected trajectory          │
│     • Irregular peak shape (asymmetry, multiple minima)        │
│     • Inconsistent between channels                            │
│     → Action: Alert user, recommend cleaning/replacement      │
│                                                                 │
│  ❌ DEGRADED/BAD SENSOR:                                       │
│     • Extremely shallow or absent peak                         │
│     • Very broad/undefined resonance                           │
│     • Erratic behavior over time                               │
│     → Action: Stop measurement, require sensor replacement    │
│                                                                 │
│  🔧 HARDWARE ISSUE:                                            │
│     • All channels show consistent deviation                   │
│     • Optical alignment issues                                 │
│     • LED/detector problems                                    │
│     → Action: Trigger hardware diagnostics                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Adaptive Method Selection

Different spectral shapes require different algorithms:

| Spectral Shape | Best Method | Reason |
|----------------|-------------|---------|
| **Sharp, deep peak** | Direct minimum | Low noise, clear minimum, fast |
| **Moderate peak** | Spline interpolation | Sub-pixel accuracy, balanced |
| **Shallow, broad peak** | Centroid | Averages noise, robust |
| **Asymmetric peak** | Polynomial fit | Handles skewness |
| **Noisy data** | Gaussian fit | Smoothing built-in |

**ML Decision Tree:**
```
if depth > 0.6 and FWHM < 100:
    method = "direct"          # Sharp peak
elif depth > 0.4 and FWHM < 200:
    method = "spline"          # Moderate peak
elif depth < 0.4 or FWHM > 200:
    method = "centroid"        # Shallow/broad peak
elif abs(asymmetry) > 0.2:
    method = "polynomial"      # Asymmetric peak
else:
    method = "spline"          # Default
```

### 3.3 Bias Correction Framework

After method selection, apply bias correction:

```python
# 1. Extract spectral features
depth, fwhm, asymmetry = extract_features(transmission_spectrum)

# 2. Select best method
method = select_method(depth, fwhm, asymmetry)

# 3. Find uncorrected peak position
peak_uncorrected = find_peak(transmission_spectrum, method)

# 4. Calculate expected bias
bias_correction = bias_model[method](depth, fwhm, asymmetry)

# 5. Apply correction
peak_corrected = peak_uncorrected - bias_correction

# 6. Validate against physics
deviation = validate_physics(peak_corrected, depth, fwhm, wavelength_range)

# 7. Classify quality
quality_status = classify(deviation, depth, fwhm, asymmetry)
```

---

## 4. Empirical Baseline Construction

### 4.1 Data Collection Strategy

To build AFfilab's proprietary SPR behavior baseline:

**Phase 1: Device Characterization**
- Collect data from multiple devices (inter-device variation)
- All 4 channels per device (intra-device variation)
- Multiple integration times and LED intensities

**Phase 2: Sensor State Mapping**
```
1. New Sealed Sensors (pristine)
   → Baseline for "perfect" sensor characteristics

2. New Unsealed Sensors (unused but exposed)
   → Effect of air exposure on spectral features

3. Used Sensors (after normal assay)
   → Effect of protein binding on permanent features
   → Distinguish reversible vs. irreversible changes

4. Recycled Sensors (multiple use cycles)
   → Degradation patterns (broadening, depth loss)

5. Contaminated Sensors (deliberate contamination)
   → Characteristic deviations from normal patterns
```

**Phase 3: Environmental Factors**
- Temperature effects on peak shape
- Time-dependent drift patterns
- Buffer composition effects

### 4.2 Feature Relationship Modeling

Build empirical models for AFfilab's specific sensors:

**Model 1: Peak Depth vs. Wavelength**
```
depth(λ) = f(λ, sensor_state, buffer)
```
- Expected depth for each wavelength region
- Tolerance bands for acceptable variation
- State-dependent adjustments

**Model 2: FWHM vs. Wavelength**
```
FWHM(λ) = g(λ, sensor_state, coating_quality)
```
- Natural broadening at longer wavelengths
- Abnormal broadening patterns (recycling indicator)

**Model 3: Sensitivity Curve**
```
sensitivity(λ) = dλ/dn(λ)
```
- Regions of highest sensitivity
- Expected dynamic range
- Calibration standards

**Model 4: Multi-Channel Consistency**
```
variance(channels) = h(device_age, calibration_date)
```
- Expected channel-to-channel variation
- Outlier detection threshold
- Hardware health indicators

### 4.3 Training Dataset Structure

```
spectral_training_data/
├── {device_serial}/
│   ├── s/  (S-polarization reference)
│   │   ├── new_sealed/
│   │   │   ├── {timestamp}/
│   │   │   │   ├── channel_A.npz  (480 spectra @ 4 Hz)
│   │   │   │   ├── channel_B.npz
│   │   │   │   ├── channel_C.npz
│   │   │   │   ├── channel_D.npz
│   │   │   │   ├── metadata.json
│   │   │   │   └── summary.json
│   │   ├── new_unsealed/
│   │   └── used/
│   └── p/  (P-polarization sample)
│       ├── new_sealed/
│       ├── new_unsealed/
│       └── used/
└── afterglow_models/
    └── {device_serial}/
        └── {timestamp}_afterglow_tau.json
```

**Each NPZ contains:**
- `spectra`: (N_time, N_wavelength) - time series of spectra
- `dark`: (1, N_wavelength) - dark reference
- `timestamps`: (N_time,) - temporal information

**Metadata includes:**
- Device serial, sensor lot, buffer composition
- Integration time, LED intensity, acquisition rate
- Temperature, user ID, collection purpose

---

## 5. Machine Learning Architecture

### 5.1 Feature Engineering

**Raw Features (directly measured):**
1. Peak position (pixel/wavelength)
2. Peak depth (transmission %)
3. FWHM (pixels)
4. Peak asymmetry
5. Peak sharpness
6. Background slope
7. SNR

**Derived Features (calculated):**
8. Depth deviation from expected (physics)
9. FWHM deviation from expected (physics)
10. Channel uniformity score
11. Temporal stability (variance over 2 min)
12. Predicted algorithm bias
13. Corrected peak position
14. Quality confidence score

**Time-Series Features:**
15. Drift rate (nm/s or px/s)
16. Noise level (std of sensorgram)
17. Anomaly score (outlier detection)
18. Afterglow contribution estimate

### 5.2 Model Pipeline

```
┌─────────────────────┐
│   Raw Spectra       │
│  S-mode, P-mode     │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Preprocessing      │
│  - Dark correction  │
│  - Transmission     │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Feature Extraction  │
│  - Peak analysis    │
│  - Shape metrics    │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Bias Prediction     │
│  - Method selection │
│  - Correction calc  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Physics Validation  │
│  - Compare to model │
│  - Deviation score  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Quality Classifier  │
│  - Good / Recycled  │
│  - Contaminated     │
│  - Degraded         │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Action & Report     │
│  - Proceed / Alert  │
│  - Applied corr.    │
└─────────────────────┘
```

### 5.3 Classifier Training

**Supervised Learning:**
- Training set: Labeled data (good/recycled/contaminated/bad)
- Validation: Cross-device, cross-channel
- Metrics: Precision, recall, F1 for each class

**Semi-Supervised Learning:**
- Unlabeled production data for distribution learning
- Anomaly detection for novel failure modes
- Active learning: flag uncertain cases for expert review

**Reinforcement Learning (future):**
- Optimize method selection over time
- Learn device-specific patterns
- Adapt to changing environmental conditions

---

## 6. Real-Time Implementation

### 6.1 Processing Requirements

**Performance Constraints:**
- **Processing time per spectrum:** < 10 ms
- **Acquisition rate:** 4 Hz (250 ms per spectrum)
- **Channels:** 4 simultaneous
- **Total cycle time:** ~1 second for 4-channel measurement

**Processing Budget:**
```
250 ms available per spectrum:
  - Acquisition: ~100 ms
  - Transfer: ~10 ms
  - Processing: < 10 ms ✓
  - Display: ~20 ms
  - Buffer: ~110 ms
```

### 6.2 Algorithm Performance (Measured)

| Algorithm | Processing Time | Accuracy | Use Case |
|-----------|----------------|----------|----------|
| Direct | 0.003 ms | 1.18 px bias | Sharp peaks |
| Spline | 0.174 ms | 1.71 px bias | General use |
| Polynomial | 0.081 ms | 2.06 px bias | Asymmetric |
| Centroid | 0.034 ms | 11.42 px bias* | Shallow/broad |
| Gaussian | 1.785 ms | 15.25 px bias* | Very noisy |

*Systematic bias, but reduces noise variance

**All methods meet <10 ms requirement ✓**

### 6.3 Denoising Strategy

**Location Testing:**
1. **Pre-transmission denoising** (on raw S and P spectra)
   - Pro: Reduces noise propagation
   - Con: May smooth out real features

2. **Post-transmission denoising** (on transmission spectrum)
   - Pro: Preserves spectral features better
   - Con: Noise already amplified by division

3. **Post-tracking denoising** (on sensorgram)
   - Pro: Fastest, applied to 1D signal
   - Con: Can't recover lost information

**Method Testing:**
- Savitzky-Golay filter (polynomial smoothing)
- Median filter (spike removal)
- Gaussian filter (general smoothing)
- Wavelet denoising (frequency-domain)
- **No smoothing** (preserve temporal resolution) ← Current approach

---

## 7. Diagnostic Capabilities

### 7.1 Sensor Quality Assessment

**Recycled Sensor Detection:**
```
Indicators:
  • FWHM > expected_FWHM(λ) + 2σ
  • Depth < expected_depth(λ) - σ
  • Consistent across channels
  • Pattern stable over time

Confidence score:
  - High: All indicators present, >3σ deviation
  - Medium: 2+ indicators, >2σ deviation
  - Low: 1 indicator, <2σ deviation

Action:
  - High: Alert user, recommend replacement
  - Medium: Flag for monitoring
  - Low: Log for trend analysis
```

**Contamination Detection:**
```
Indicators:
  • Peak position deviates from trajectory
  • Irregular/multiple minima
  • Asymmetry > threshold
  • Channel-specific (not uniform)

Classification:
  - Protein contamination: Specific peak shift pattern
  - Particulate: Irregular, time-varying
  - Bubble: Sudden, transient deviation
  - Chemical: Unusual depth/FWHM combination

Action:
  - Stop measurement
  - Recommend cleaning protocol
  - Guide troubleshooting
```

**Degraded Sensor:**
```
Indicators:
  • Depth > 0.8 (very shallow resonance)
  • FWHM > 400 px (extremely broad)
  • SNR < threshold
  • Progressive worsening over time

Action:
  - Immediate replacement required
  - No correction possible
  - Log failure mode for QC
```

### 7.2 Hardware Health Monitoring

**CRITICAL DISTINCTION: Optics vs SPR Issue Separation**

During live measurements, signal changes can originate from:
1. **Optical system** (device-specific): LED, detector, fiber, optics
2. **SPR sensor** (consumable-specific): water coupling, surface chemistry, binding

**See dedicated document:** `LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md` for complete separation strategy.

**Key discrimination features:**

| Feature | Optics Issue | SPR Sensor Issue |
|---------|-------------|------------------|
| Multi-channel correlation | ✅ HIGH (all channels) | ❌ LOW (channel-specific) |
| Wavelength pattern | Matches LED spectrum | Matches SPR dip only |
| Temporal behavior | Slow drift (hours) | Fast changes (seconds) |
| Background slope | Changes | Stable |
| SPR dip depth | Entire spectrum scales | Only dip affected |
| SPR dip position | Usually stable | Shifts with binding |

**Optical System Monitoring:**
- LED intensity drift detection (multi-channel correlation)
- Afterglow model changes over time
- Detector sensitivity changes (noise floor)
- Polarizer positioning accuracy

**SPR Sensor Monitoring:**
- Water coupling quality (dip depth)
- Surface degradation (FWHM broadening)
- Contamination (asymmetry, background)
- Binding events (smooth position shifts)

**Fluidic System:**
- Bubble detection from spectral artifacts
- Flow uniformity (channel comparison)
- Temperature stability

**System-Wide:**
- Multi-channel consistency metrics
- Calibration drift tracking
- Component lifetime prediction

---

## 8. Competitive Advantages

### 8.1 AFfilab Proprietary Elements

**1. Bias Correction Models**
- Empirically derived for AFfilab's specific sensors
- Accounts for unique optical geometry
- Wavelength range optimized for applications

**2. Physics-Informed Validation**
- SPR behavior baseline built from real data
- Not generic literature values
- Device-specific, environment-adjusted

**3. Real-Time Classification**
- All processing < 10 ms
- Actionable feedback during measurement
- Prevents wasted time on bad sensors

**4. Adaptive Intelligence**
- Method selection based on spectral shape
- Self-optimizing over device lifetime
- Learns from production data

**5. Multi-Level Diagnostics**
- Separates consumable from hardware issues
- Guides user to correct action
- Reduces support burden

### 8.2 Business Value

**For Users:**
- ✅ Fewer failed measurements
- ✅ Higher confidence in results
- ✅ Reduced consumable waste
- ✅ Less expertise required

**For AFfilab:**
- ✅ Competitive differentiation
- ✅ Valuable production data collection
- ✅ Continuous improvement loop
- ✅ Upsell opportunities (advanced features)
- ✅ Reduced support costs

**Market Position:**
- Competitors: Reactive quality control (detect issues after measurement)
- AFfilab: **Proactive quality control** (prevent bad measurements)

---

## 9. Development Roadmap

### Phase 1: Foundation (Current - Q4 2025)
- [x] Data collection infrastructure
- [x] Bias characterization framework
- [x] Algorithm performance testing
- [ ] Empirical baseline construction
- [ ] Feature extraction pipeline

### Phase 2: Model Development (Q1 2026)
- [ ] Train quality classifier
- [ ] Validate on production data
- [ ] Build physics models
- [ ] Create correction lookup tables
- [ ] Performance optimization

### Phase 3: Integration (Q2 2026)
- [ ] Real-time processing engine
- [ ] UI feedback system
- [ ] User alert framework
- [ ] Diagnostic reporting
- [ ] A/B testing with users

### Phase 4: Intelligence (Q3 2026)
- [ ] Adaptive method selection
- [ ] Device-specific learning
- [ ] Predictive maintenance
- [ ] Automatic calibration
- [ ] Remote diagnostics

### Phase 5: Ecosystem (Q4 2026+)
- [ ] Multi-device learning
- [ ] Cloud-based model updates
- [ ] Advanced analytics dashboard
- [ ] API for third-party integration
- [ ] Research collaboration tools

---

## 10. Key Performance Indicators

### Technical Metrics
- **Accuracy:** Correctly classify sensor state (target: >95%)
- **Precision:** Minimize false positives (target: <5%)
- **Speed:** Processing time per spectrum (target: <10 ms)
- **Robustness:** Performance across devices (target: >90% consistency)

### Business Metrics
- **Measurement Success Rate:** % measurements with acceptable quality
- **Consumable Lifetime:** Extended by early detection
- **User Satisfaction:** Reduced frustration from failed measurements
- **Support Tickets:** Reduction in quality-related issues

### Research Metrics
- **Dataset Size:** Spectra collected across states
- **Model Performance:** Improvement over time
- **Novel Insights:** Discovery of new failure modes
- **Publications:** IP-protected research outputs

---

## 11. Intellectual Property Strategy

### 11.1 Core Protectable Elements

**1. Bias Correction Models**
- Mathematical relationships between spectral features and algorithm bias
- Empirically derived coefficients for each method
- Trade secret: Keep formulas confidential

**2. Adaptive Method Selection**
- Decision tree logic
- Feature thresholds
- Performance optimization criteria
- Patent potential: "System and method for adaptive SPR analysis"

**3. Physics-Informed Validation**
- Empirical SPR baseline for AFfilab sensors
- Deviation scoring algorithms
- Multi-level classification logic
- Trade secret: Keep baseline models confidential

**4. Real-Time Diagnostic System**
- Complete pipeline architecture
- Feature extraction algorithms
- Classification framework
- Patent potential: "Proactive quality control system for biosensors"

**5. Training Dataset**
- Curated sensor state library
- Multi-device characterization
- Proprietary labeling scheme
- Trade secret: Most valuable long-term asset

### 11.2 Protection Strategy

**Patents:**
- File for adaptive processing methods
- Claim proactive quality assessment approach
- Broad claims on ML-driven biosensor diagnostics

**Trade Secrets:**
- Keep model coefficients confidential
- Protect empirical baselines
- Secure training dataset
- NDAs for collaborators

**Software Copyright:**
- Protect implementation code
- License restrictions
- Obfuscation of critical algorithms

**Competitive Moats:**
- Data advantage (continuous collection)
- First-mover advantage (market education)
- Network effects (multi-device learning)

---

## 12. Conclusion

The AFfilab Spectral ML Analysis Framework represents a paradigm shift in biosensor quality control:

**From:** "Measure everything, find problems later"
**To:** "Assess quality first, measure only when confident"

**Key Innovation:** Separating algorithm bias from physical signal enables unprecedented insight into sensor state and measurement quality at the raw data level.

**Competitive Advantage:** Proactive quality control reduces failures, improves user experience, and creates a continuous learning system that gets smarter with every measurement.

**Strategic Value:** The combination of proprietary models, empirical baselines, and real-time intelligence creates a sustainable competitive moat that compounds over time as the dataset grows.

This framework is the foundation for AFfilab's next-generation intelligent biosensor platform.

---

## Appendix A: Mathematical Details

### A.1 Transmission Calculation

Given raw spectra:
- S(λ): Reference signal (S-polarization)
- P(λ): Sample signal (P-polarization)
- S_dark(λ): S-mode dark spectrum
- P_dark(λ): P-mode dark spectrum

Dark-corrected signals:
```
S'(λ) = S(λ) - S_dark(λ)
P'(λ) = P(λ) - P_dark(λ)
```

Transmission:
```
T(λ) = P'(λ) / S'(λ)
```

With numerical stability:
```
ε = 1e-6
S'_safe(λ) = max(S'(λ), ε)
T(λ) = P'(λ) / S'_safe(λ)
```

### A.2 Peak Finding Algorithms

**Direct Minimum:**
```python
def find_minimum_direct(spectrum, search_region):
    start, end = search_region
    region = spectrum[start:end]
    min_idx = np.argmin(region)
    return start + min_idx
```

**Polynomial Fit:**
```python
def find_minimum_polynomial(spectrum, search_region, window=3):
    start, end = search_region
    region = spectrum[start:end]
    min_idx = np.argmin(region)

    # Fit parabola around minimum
    x = np.arange(min_idx - window, min_idx + window + 1)
    y = region[x]
    coeffs = np.polyfit(x, y, 2)

    # Vertex: x = -b / (2a)
    if coeffs[0] > 0:  # Opens upward
        refined_min = -coeffs[1] / (2 * coeffs[0])
        return start + refined_min
    return start + min_idx
```

**Centroid:**
```python
def find_minimum_centroid(spectrum, search_region, threshold_factor=1.2):
    start, end = search_region
    region = spectrum[start:end]
    min_val = np.min(region)

    # Define dip region
    threshold = min_val * threshold_factor
    dip_mask = region < threshold

    # Weighted average
    x = np.arange(len(region))
    centroid = np.sum(x[dip_mask] * region[dip_mask]) / np.sum(region[dip_mask])
    return start + centroid
```

### A.3 Bias Correction Formulas

Based on synthetic data analysis (2,400 test cases):

**Direct Method:**
```
bias_direct = 0.607 * depth - 0.268
```

**Centroid Method:**
```
bias_centroid = 1.513 * depth + 0.002 * FWHM + 52.455 * asymmetry - 0.961
```

**Polynomial Method:**
```
bias_polynomial = 1.112 * depth + 0.810 * asymmetry - 0.831
```

**Spline Method:**
```
bias_spline = 1.216 * depth - 0.069 * asymmetry - 0.602
```

Where:
- `depth`: Transmission at minimum (0 to 1)
- `FWHM`: Full width at half maximum (pixels)
- `asymmetry`: Skewness parameter (-1 to 1)

### A.4 Feature Extraction

**Peak Depth:**
```python
depth = transmission[peak_idx]
```

**FWHM:**
```python
half_max = (transmission[peak_idx] + background) / 2
left_idx = find_crossing(transmission[:peak_idx], half_max, direction='down')
right_idx = find_crossing(transmission[peak_idx:], half_max, direction='up')
FWHM = right_idx - left_idx
```

**Asymmetry:**
```python
# Skewness of peak region
peak_region = transmission[peak_idx-window:peak_idx+window]
asymmetry = scipy.stats.skew(peak_region)
```

**Sharpness:**
```python
# Second derivative at minimum
second_deriv = np.gradient(np.gradient(transmission))
sharpness = abs(second_deriv[peak_idx])
```

---

## Appendix B: Data Collection Specifications

### B.1 Collection Parameters

**Spectral Collection:**
- Duration: 120 seconds (2 minutes)
- Acquisition rate: 4 Hz (250 ms per spectrum)
- Total spectra: 480 per channel
- Integration time: 100 ms (optimized for signal level)
- LED intensity: 100% (maximize SNR)
- LED stabilization delay: 20 ms

**Modes:**
- S-polarization: Reference (no sensor resonance)
- P-polarization: Sample (with sensor resonance)
- Dark: LED off (noise floor)

**Channels:**
- 4 channels per device (A, B, C, D)
- Multiplexed acquisition
- Same optical path, different sensors

### B.2 Data Quality Requirements

**Signal Requirements:**
- Peak-to-peak signal: > 20,000 counts
- SNR: > 100:1
- Dark level: < 3,500 counts
- Saturation: Avoid (max 65,535 counts)

**Temporal Requirements:**
- Timing jitter: < 10 ms
- Drift: < 50 pixels over 2 minutes
- Stability: RSD < 5% within run

**Environmental Requirements:**
- Temperature: 20-30°C (controlled)
- No external light contamination
- Vibration isolation
- No bubbles in flow cell

### B.3 Metadata Captured

**Device Information:**
- Serial number
- Firmware version
- Calibration date
- Total operating hours

**Sensor Information:**
- Lot number
- Coating type
- Age (sealed/unsealed date)
- Usage history

**Measurement Conditions:**
- Buffer composition
- Flow rate
- Temperature
- User ID
- Timestamp

**Performance Metrics:**
- Actual acquisition rate
- Signal levels
- Afterglow τ values
- Quality flags

---

## Appendix C: Implementation Checklist

### Core Infrastructure
- [ ] Data collection scripts (spectral + afterglow)
- [ ] NPZ file format standardization
- [ ] Metadata schema definition
- [ ] Database for training set management

### Analysis Pipeline
- [ ] Transmission calculation module
- [ ] Feature extraction library
- [ ] Peak-finding algorithm suite
- [ ] Bias correction implementation
- [ ] Physics validation module

### Machine Learning
- [ ] Training data labeling tool
- [ ] Model training pipeline
- [ ] Cross-validation framework
- [ ] Performance monitoring
- [ ] Model versioning system

### Real-Time System
- [ ] Processing optimization (<10 ms)
- [ ] Method selection logic
- [ ] Quality classification engine
- [ ] Alert generation system
- [ ] User feedback UI
- [ ] **Optics vs SPR separation logic (see LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md)**
- [ ] **Multi-channel correlation analysis**

### Quality Assurance
- [ ] Unit tests for all algorithms
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Validation on diverse datasets
- [ ] User acceptance testing
- [ ] **Optics issue validation (LED drift, noise)**
- [ ] **SPR issue validation (water loss, degradation)**

### Documentation
- [ ] API documentation
- [ ] User guide for diagnostics
- [ ] Troubleshooting flowcharts
- [ ] Research publications
- [ ] Patent applications
- [ ] ✅ **Optics vs SPR separation strategy (LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md)**

---

**End of Document**

*This document contains proprietary and confidential information of AFfilab. Unauthorized disclosure, copying, or distribution is prohibited.*
