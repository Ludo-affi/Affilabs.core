# AFfilab Spectral Analysis Framework
## Physics-Informed Machine Learning for SPR Signal Quality Assessment

**Document Version:** 1.0
**Date:** October 22, 2025
**Status:** CONFIDENTIAL - AFfilab Proprietary

---

## Executive Summary

This document describes AFfilab's proprietary approach to real-time SPR signal quality assessment using physics-informed machine learning. The framework enables proactive detection of consumable issues (recycled sensors, contamination, degradation) by analyzing raw spectral data characteristics, **before** they impact downstream analytical measurements.

### Core Innovation

**Traditional approach:** Monitor assay output → detect problems late → troubleshoot backwards
**AFfilab approach:** Analyze raw spectra → predict signal quality → flag issues proactively

**Key Principle:** If ML can recognize issues at the raw data level, we don't need to monitor as much downstream—just focus on the input raw data.

---

## 1. Framework Overview

### 1.1 Problem Statement

SPR biosensor measurements are affected by multiple factors:
- **Instrumental artifacts**: Peak-finding algorithm bias, noise, LED drift
- **Consumable quality**: Sensor degradation, recycling, contamination
- **Expected physics**: SPR theory predicts peak depth, width, and position relationships

**Challenge:** Separate these three components to:
1. Correct for algorithm bias → get true physical signal
2. Detect consumable issues → flag for user action
3. Account for expected SPR physics → avoid false alarms

### 1.2 Solution Architecture

```
Raw Spectra (S-mode + P-mode)
    ↓
Transmission Calculation: T = (P - P_dark) / (S - S_dark)
    ↓
Feature Extraction:
├─ Peak position (wavelength)
├─ Peak depth (transmission %)
├─ FWHM (full width at half maximum)
├─ Peak sharpness/asymmetry
├─ Background slope/curvature
└─ Signal-to-noise ratio
    ↓
Physics-Informed Analysis:
├─ Expected behavior model (empirical baseline)
├─ Algorithm bias correction
└─ Deviation scoring
    ↓
Classification:
├─ ✅ Good signal (within expected bounds)
├─ ⚠️ Consumable issue (recycled/contaminated)
└─ ❌ Hardware/instrumental issue
```

---

## 2. Mathematical Foundation

### 2.1 Transmission Spectrum Calculation

The fundamental measurement is the transmission spectrum:

```
T(λ) = (P_signal(λ) - P_dark(λ)) / (S_signal(λ) - S_dark(λ))
```

Where:
- **P-mode**: Sample signal with sensor resonance (dip in transmission)
- **S-mode**: Reference signal without sensor resonance (polarization orthogonal)
- **Dark spectra**: Background with LED off

**Key insight:** S-mode provides LED spectral characteristics; P-mode provides sensor response. The ratio isolates sensor physics from LED variations.

### 2.2 Peak-Finding Algorithm Bias

Different algorithms for finding the transmission minimum have characteristic biases:

**Direct minimum (argmin):**
```
bias_direct ≈ 0.607 × depth - 0.268
```
- Fast (0.003 ms/spectrum)
- Low mean bias (1.18 pixels)
- Sensitive to noise spikes

**Centroid method:**
```
bias_centroid ≈ 1.513 × depth + 0.002 × FWHM + 52.455 × asymmetry - 0.961
```
- Moderate speed (0.034 ms/spectrum)
- Higher systematic bias (11.42 pixels)
- Robust to noise (smoothing effect)
- **Strong sensitivity to peak asymmetry**

**Polynomial fit:**
```
bias_polynomial ≈ 1.112 × depth + 0.810 × asymmetry - 0.831
```
- Moderate speed (0.081 ms/spectrum)
- Sub-pixel accuracy
- Can fail on irregular peaks

**Spline interpolation:**
```
bias_spline ≈ 1.216 × depth - 0.602
```
- Slower (0.174 ms/spectrum)
- Good accuracy (1.71 pixels)
- Smooth interpolation

**Gaussian fitting:**
```
bias_gaussian ≈ 1.378 × depth + 0.002 × FWHM + 75.694 × asymmetry - 1.010
```
- Slowest (1.785 ms/spectrum)
- Assumes Gaussian peak shape
- Fails on highly asymmetric peaks

### 2.3 Bias Correction Strategy

**Total measured shift = Physical shift (signal) + Algorithm bias (artifact)**

To recover true physical signal:
```
True_shift = Measured_shift - Bias(depth, FWHM, asymmetry)
```

**Implementation:**
1. Extract peak shape features from transmission spectrum
2. Calculate expected algorithm bias using correction formula
3. Subtract bias to obtain bias-corrected position
4. Track corrected position over time (sensorgram)

---

## 3. Spectral Feature Extraction

### 3.1 Core Features

**Peak Position:**
- Location of transmission minimum (wavelength/pixel)
- Primary analytical signal in SPR measurements
- Shifts with refractive index changes (binding events)

**Peak Depth:**
- Transmission value at minimum (0-100%)
- Related to coupling efficiency and sensor quality
- **AFfilab-specific:** Shallow peaks may indicate degraded sensors

**FWHM (Full Width at Half Maximum):**
- Width of resonance dip at 50% depth
- Related to sensor surface quality and resonance sharpness
- **AFfilab-specific:** Broadening indicates recycled/damaged sensors

**Asymmetry:**
- Skewness of peak shape
- Quantified as difference in left vs. right half-widths
- Affects algorithm bias significantly

**Peak Sharpness:**
- Second derivative at minimum
- Quantifies how "sharp" vs. "rounded" the resonance is
- Influences tracking precision

**Background Characteristics:**
- Slope: linear trend in transmission spectrum
- Curvature: quadratic component
- Indicates optical path issues or contamination

### 3.2 Signal Quality Metrics

**Signal-to-Noise Ratio (SNR):**
```
SNR = (Transmission_baseline - Transmission_minimum) / Noise_std
```

**Temporal Stability:**
- Peak-to-peak variation in position over measurement window
- Should be minimal for stable systems
- Excessive variation → hardware issues or poor sensor

**Consistency Across Channels:**
- Compare features across 4 channels
- Deviation indicates channel-specific problems
- Useful for detecting contamination or flow issues

---

## 4. Physics-Informed Models

### 4.1 SPR Theory Relationships

**Fundamental SPR physics** (general principles):

1. **Peak position vs. depth:** As resonance shifts to longer wavelengths, peak typically becomes shallower
2. **Peak position vs. width:** Longer wavelength peaks tend to be broader
3. **Sensitivity vs. wavelength:** SPR sensitivity varies with wavelength in a predictable manner
4. **Refractive index relationship:** Peak position shifts with surface refractive index

**CRITICAL:** AFfilab sensors have **unique characteristics** due to:
- Proprietary gold coating thickness
- Specific flow cell geometry
- Custom optical configuration
- Multi-channel simultaneous measurement

### 4.2 Empirical Baseline Development

**AFfilab's approach:** Build empirical models from real sensor data rather than assuming generic SPR theory.

**Data Collection Strategy:**
```
Sensor States:
├─ new_sealed: Never used, factory sealed
├─ new_unsealed: Opened but not used in assay
└─ used: After typical assay usage

Channels: A, B, C, D (4 independent measurements)

Modes: S-mode (reference) + P-mode (sample)

Collection: 480 spectra @ 4 Hz over 2 minutes
```

**Baseline Construction:**
1. Collect data across all sensor states and channels
2. Extract features: position, depth, FWHM, asymmetry
3. Build empirical relationships:
   ```
   depth_expected = f(position)
   FWHM_expected = g(position)
   sensitivity = h(position)
   ```
4. Define "normal" envelopes (mean ± tolerance)
5. Account for manufacturing variation

### 4.3 Deviation Scoring

For each measurement, calculate deviation from expected behavior:

**Depth deviation:**
```
Δ_depth = |depth_measured - depth_expected(position)| / σ_depth
```

**Width deviation:**
```
Δ_FWHM = |FWHM_measured - FWHM_expected(position)| / σ_FWHM
```

**Combined quality score:**
```
Quality_score = w₁×Δ_depth + w₂×Δ_FWHM + w₃×Δ_asymmetry + w₄×SNR
```

Where weights (w₁, w₂, w₃, w₄) are empirically determined.

---

## 5. Consumable Issue Detection

### 5.1 Problem Classifications

**Good Signal (✅):**
- All features within expected envelopes
- Consistent across channels
- Stable over time
- Normal SNR and peak sharpness

**Recycled Sensor (⚠️):**
- **Primary indicator:** FWHM broader than expected for given position
- Peak may be shallower than expected
- Surface chemistry degraded from previous use
- **Pattern:** Progressive broadening over multiple uses

**Contaminated Sensor (⚠️):**
- **Primary indicator:** Peak position deviates from expected trajectory
- Unusual peak shape or asymmetry
- Background slope/curvature anomalies
- **Pattern:** Sudden changes, not progressive

**Degraded Coating (⚠️):**
- **Primary indicator:** Shallow peak depth
- Poor coupling efficiency
- May show irregular peak shapes
- **Pattern:** Consistent across measurement, may worsen

**Hardware/Instrumental Issue (❌):**
- Inconsistent between channels
- Erratic temporal variation
- Excessive noise
- **Pattern:** Reproducible on repeat measurements

### 5.2 Detection Logic

**Step 1: Calculate deviations from baseline**
```python
if all_deviations < threshold:
    return "Good signal ✅"
```

**Step 2: Check FWHM (recycled sensor indicator)**
```python
if FWHM > expected + 3σ:
    if depth < expected - 2σ:
        return "Recycled sensor - broad & shallow ⚠️"
    else:
        return "Damaged sensor - excessive broadening ⚠️"
```

**Step 3: Check position consistency (contamination)**
```python
if position_deviation > threshold:
    if background_anomaly:
        return "Contamination - optical path affected ⚠️"
    else:
        return "Sensor surface issue ⚠️"
```

**Step 4: Check temporal stability (hardware)**
```python
if peak_to_peak_variation > threshold:
    if consistent_across_channels:
        return "System-wide instability ❌"
    else:
        return "Channel-specific hardware issue ❌"
```

**Step 5: Cross-channel consistency**
```python
if large_variation_across_channels:
    identify_outlier_channels()
    return "Channel(s) X require attention ⚠️"
```

---

## 6. Adaptive Processing Pipeline

### 6.1 Method Selection Based on Peak Shape

Different peak shapes require different algorithms for optimal tracking:

**Sharp, Deep Peaks (depth < 40%, FWHM < 100 px):**
- **Best:** Direct minimum or spline
- Low bias, high precision
- Noise is minor factor

**Moderate Peaks (40% < depth < 60%, 100 < FWHM < 200 px):**
- **Best:** Polynomial fit or spline
- Balance accuracy and robustness
- Sub-pixel refinement beneficial

**Shallow, Broad Peaks (depth > 60%, FWHM > 200 px):**
- **Best:** Centroid or Gaussian fit
- Direct minimum too noisy
- Smoothing effect beneficial
- **Caution:** Apply bias correction!

**Asymmetric Peaks:**
- **Best:** Spline interpolation
- Centroid has large bias (52× asymmetry)
- Gaussian fitting assumes symmetry (poor choice)

### 6.2 Real-Time Processing Pipeline

**Production implementation (<10 ms requirement):**

```python
def process_spectrum(s_signal, p_signal, s_dark, p_dark):
    """
    Real-time spectrum processing pipeline.
    Target: <10 ms per channel
    """
    # Step 1: Calculate transmission (0.1 ms)
    transmission = (p_signal - p_dark) / (s_signal - s_dark)

    # Step 2: Extract peak features (0.5 ms)
    features = extract_features(transmission)
    # - position (initial estimate)
    # - depth
    # - FWHM
    # - asymmetry

    # Step 3: Select optimal algorithm (0.01 ms)
    algorithm = select_algorithm(features.depth, features.FWHM, features.asymmetry)

    # Step 4: Refined peak finding (0.1 - 1.0 ms depending on algorithm)
    position_measured = algorithm.find_minimum(transmission)

    # Step 5: Apply bias correction (0.01 ms)
    bias = calculate_bias(algorithm, features.depth, features.FWHM, features.asymmetry)
    position_corrected = position_measured - bias

    # Step 6: Compare to expected baseline (0.1 ms)
    deviation_score = calculate_deviation(features, expected_baseline)
    quality_flag = classify_quality(deviation_score, features)

    # Total: ~1-2 ms (well under 10 ms target)
    return {
        'position': position_corrected,
        'features': features,
        'quality': quality_flag,
        'processing_time': elapsed_time
    }
```

### 6.3 Denoising Strategy

**Key question:** Apply denoising to raw spectra or transmission spectrum?

**Option 1: Denoise raw spectra (P-mode and S-mode separately)**
- **Pro:** Reduces noise before division (avoids noise amplification)
- **Pro:** Can use mode-specific noise characteristics
- **Con:** May smooth out real spectral features
- **Method:** Savitzky-Golay filter (preserves peak shape)

**Option 2: Denoise transmission spectrum**
- **Pro:** Directly reduces noise in analytical signal
- **Pro:** Simpler pipeline
- **Con:** Division can amplify noise where S-mode is low
- **Method:** Wavelength-dependent filtering

**Option 3: No smoothing (recommended starting point)**
- **Pro:** Preserves temporal resolution (ms-range)
- **Pro:** No risk of artificial peak distortion
- **Pro:** Algorithm selection + bias correction may be sufficient
- **Con:** Higher noise floor

**AFfilab recommendation:** Start with Option 3. Use algorithm robustness (centroid, polynomial) instead of spectral smoothing. Only add denoising if peak-to-peak variation exceeds requirements after bias correction.

---

## 7. Machine Learning Integration

### 7.1 Training Data Structure

**Dataset organization:**
```
spectral_training_data/
  {device_serial}/
    {mode}/           # s or p
      {quality}/      # new_sealed, new_unsealed, used
        {timestamp}/
          channel_A.npz
          channel_B.npz
          channel_C.npz
          channel_D.npz
          metadata.json
          summary.json
```

**Features for ML model:**
- Peak position (pixel or wavelength)
- Peak depth (transmission %)
- FWHM (pixels)
- Asymmetry (left/right ratio)
- Peak sharpness (2nd derivative)
- Background slope
- SNR
- Temporal stability (std over window)
- Cross-channel consistency
- Deviation from expected baseline

**Labels:**
- `good`: Signal within normal parameters
- `recycled`: Broadened peak, typical of reused sensor
- `contaminated`: Position/shape deviation, optical interference
- `degraded`: Shallow/irregular peak, coating damage
- `hardware_issue`: Temporal instability, inconsistent across channels

### 7.2 Model Architecture

**Phase 1: Rule-based classifier (immediate deployment)**
- Threshold-based decision tree
- Physics-informed rules
- Interpretable, no training required
- Baseline performance

**Phase 2: Supervised ML classifier (after data collection)**
- Input: Extracted features (10-20 dimensions)
- Model: Random Forest or XGBoost
- Output: Quality classification + confidence score
- Training: 1000+ examples per class (target)

**Phase 3: Deep learning (advanced)**
- Input: Raw transmission spectra (3648 pixels × time series)
- Model: 1D CNN or LSTM for temporal patterns
- Output: Quality classification + feature importance
- Training: 10,000+ examples (long-term goal)

### 7.3 Continuous Learning

**Online learning strategy:**
1. Collect data from production systems
2. Users provide feedback (sensor worked well / had issues)
3. Retrain models with new examples
4. Push updated models via software updates
5. Improve classification accuracy over time

**Key advantage:** Models learn AFfilab's specific sensor characteristics and customer usage patterns.

---

## 8. Implementation Roadmap

### Phase 1: Data Collection & Baseline (Current)
**Timeline:** Weeks 1-4

**Objectives:**
- ✅ Collect spectral data from Channel A (complete)
- ✅ Build transmission analysis pipeline (complete)
- ✅ Test peak-finding algorithms (complete)
- ✅ Characterize algorithm bias (complete)
- ⏳ Collect 4-channel dataset (all channels)
- ⏳ Collect across sensor states (new_sealed, new_unsealed, used)
- ⏳ Build empirical baseline models

**Deliverables:**
- Dataset: 4 channels × 3 sensor states × 480 spectra = ~6,000 spectra
- Empirical models: depth(position), FWHM(position), sensitivity(position)
- Algorithm bias corrections validated on real data

### Phase 2: Feature Engineering & Classification (Weeks 5-8)

**Objectives:**
- Implement complete feature extraction pipeline
- Create deviation scoring system
- Build rule-based classifier
- Test on collected dataset
- Measure classification accuracy

**Deliverables:**
- Feature extraction module (<1 ms processing)
- Rule-based classifier with threshold optimization
- Validation report: precision, recall, F1-score per class
- Processing pipeline meeting <10 ms requirement

### Phase 3: ML Model Development (Weeks 9-12)

**Objectives:**
- Label collected dataset (good/recycled/contaminated/etc.)
- Train supervised ML classifier (Random Forest / XGBoost)
- Compare ML vs. rule-based performance
- Optimize for production deployment

**Deliverables:**
- Trained ML model with >90% accuracy (target)
- Model deployment package
- A/B testing framework (rule-based vs. ML)
- Performance benchmarks

### Phase 4: Production Integration (Weeks 13-16)

**Objectives:**
- Integrate classification into main application
- Real-time quality flagging in UI
- User feedback collection system
- Field testing with beta customers

**Deliverables:**
- Production-ready quality assessment module
- User documentation
- Customer training materials
- Feedback collection pipeline for continuous improvement

---

## 9. Key Performance Indicators (KPIs)

### 9.1 Technical Metrics

**Processing Speed:**
- Target: <10 ms per channel (complete spectrum → quality flag)
- Production: 4 channels × <10 ms = <40 ms total (50% of 80 ms cycle budget)

**Peak Tracking Precision:**
- Current (no correction): 505-1817 pixels peak-to-peak (Channel A, centroid method)
- Target: <100 pixels peak-to-peak after bias correction
- Stretch goal: <50 pixels (equivalent to 11.53 RU on current system)

**Classification Accuracy:**
- Rule-based baseline: >80% accuracy (target)
- ML classifier: >90% accuracy (target)
- False positive rate: <5% (avoid unnecessary user alarms)

### 9.2 Business Metrics

**Issue Detection Rate:**
- % of sensor issues caught before assay failure
- Target: >95% detection before irreversible damage

**User Satisfaction:**
- Reduced troubleshooting time
- Fewer failed assays due to undetected sensor issues
- Increased confidence in measurement quality

**Competitive Advantage:**
- Unique real-time quality assessment
- Physics-informed approach (not black-box ML)
- Proactive vs. reactive quality control

---

## 10. Proprietary Advantages

### 10.1 Unique AFfilab Innovations

**1. Dual-Mode Analysis (S-mode + P-mode):**
- Most SPR systems: P-mode only
- AFfilab: Separate LED characteristics (S-mode) from sensor response (P-mode)
- Enables LED-independent quality assessment

**2. Physics-Informed ML:**
- Not pure pattern recognition
- Incorporates SPR theory + algorithm bias models
- Interpretable results (explain WHY signal is flagged)

**3. Empirical Baseline Approach:**
- Custom models for AFfilab's specific sensor design
- Not dependent on generic SPR literature
- Adapts to manufacturing variations

**4. Algorithm Bias Correction:**
- Unique characterization of bias vs. peak shape
- Enables separation of fitting artifact from physical signal
- Improves tracking precision without smoothing

**5. Multi-Channel Consistency Analysis:**
- 4 simultaneous channels enable cross-validation
- Detect channel-specific vs. system-wide issues
- Higher confidence in quality assessment

### 10.2 Patent Opportunities

**Potential patent claims:**

1. **Method for SPR signal quality assessment using dual-polarization spectral analysis**
   - Using S-mode reference to normalize P-mode sensor response
   - Extracting peak shape features independent of LED characteristics

2. **Adaptive peak-finding with bias correction based on peak morphology**
   - Algorithm selection based on extracted peak features
   - Bias correction formulas as function of depth, FWHM, asymmetry
   - Real-time switching between algorithms

3. **Physics-informed machine learning for biosensor consumable quality classification**
   - Combining empirical baseline with ML classifier
   - Deviation scoring relative to expected SPR behavior
   - Classification of recycled, contaminated, degraded sensors

4. **Multi-channel consistency analysis for SPR system diagnostics**
   - Cross-channel feature comparison
   - Distinguishing sensor issues from instrumental issues
   - Automated channel health scoring

---

## 11. Competitive Landscape

### 11.1 Current Market Approaches

**Traditional SPR systems:**
- Monitor assay output (kinetic curves)
- Flag issues when binding curves look abnormal
- **Limitation:** Detects problems too late (after assay running)

**Spectral analysis in competitors:**
- Typically limited to peak position tracking
- No sophisticated peak shape analysis
- No ML-based quality assessment
- **Limitation:** Cannot distinguish sensor vs. instrumental issues

**User-dependent quality control:**
- Operators manually inspect spectra
- Subjective assessment
- Requires training and experience
- **Limitation:** Inconsistent, time-consuming, error-prone

### 11.2 AFfilab Differentiation

**Proactive vs. Reactive:**
- Detect issues at raw data level (before assay failure)
- Flag potential problems before irreversible
- Guide user actions (replace sensor, clean, etc.)

**Automated vs. Manual:**
- No user interpretation required
- Consistent, objective assessment
- Real-time feedback (<10 ms)

**Physics-Informed vs. Black-Box:**
- Explainable results (show WHY flagged)
- User trust through transparency
- Easier regulatory approval (medical applications)

**Adaptive vs. Fixed:**
- Algorithm selection based on signal characteristics
- Continuous learning from field data
- Improves with usage

---

## 12. Next-Generation Enhancements

### 12.1 Advanced Features (Future Development)

**Predictive Maintenance:**
- Predict sensor end-of-life before failure
- Estimate remaining useful life (RUL)
- Optimize sensor replacement scheduling

**Automated Optimization:**
- Suggest optimal integration time per sensor state
- Adjust LED intensity based on signal characteristics
- Dynamic parameter tuning for best performance

**Application-Specific Models:**
- Different baselines for different assay types
- Binding kinetics-informed quality assessment
- Distinguish analyte binding from sensor drift

**Multi-Device Learning:**
- Aggregate data across customer fleet
- Identify systematic issues (batch effects, manufacturing drift)
- Improve baseline models with larger dataset

### 12.2 Integration with Other Systems

**Consumable Tracking:**
- Link spectral analysis to sensor lot numbers
- Detect batch-to-batch variations
- QC feedback to manufacturing

**Assay Result Correlation:**
- Link spectral quality to assay success rate
- Build predictive models: spectra → assay outcome
- Optimize quality thresholds for specific applications

**Cloud Analytics:**
- Upload anonymized spectral data
- Centralized model training and updates
- Cross-site performance benchmarking

---

## 13. Conclusion

AFfilab's spectral analysis framework represents a **paradigm shift** in SPR biosensor quality control:

**From:** "Run assay → detect failure → troubleshoot"
**To:** "Analyze spectra → predict quality → prevent failure"

### Core Principles:

1. **Physics-informed:** Leverage SPR theory + empirical data
2. **Proactive:** Detect issues at raw data level
3. **Adaptive:** Algorithm selection based on signal characteristics
4. **Explainable:** Users understand why signals are flagged
5. **Continuous improvement:** Learn from field data

### Competitive Advantages:

- ✅ Unique dual-mode (S + P) analysis
- ✅ Real-time quality assessment (<10 ms)
- ✅ Algorithm bias correction (proprietary)
- ✅ Multi-channel consistency validation
- ✅ Physics-informed ML (not black-box)

### Impact:

- 🎯 Reduce failed assays
- 🎯 Detect recycled/contaminated sensors
- 🎯 Improve user confidence
- 🎯 Enable proactive maintenance
- 🎯 Strengthen AFfilab market position

**This framework is the foundation for AFfilab's intelligent biosensor platform and represents significant intellectual property value.**

---

**Document Control:**
- Author: AFfilab Development Team
- Classification: CONFIDENTIAL - Internal Use Only
- Distribution: Management, R&D, Engineering
- Review: Quarterly updates as framework evolves

---
