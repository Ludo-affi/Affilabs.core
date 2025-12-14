# Live Monitoring: Optics vs SPR Issue Separation
## Critical Distinction for Real-Time Diagnostics

**Document Version:** 1.0
**Date:** November 23, 2025
**Status:** CRITICAL - ML System Design Document
**Purpose:** Ensure ML monitoring system correctly attributes signal changes to device (optics) vs sensor (SPR)

---

## Executive Summary

**CRITICAL CHALLENGE:** During live SPR measurements, the observed transmission spectrum reflects BOTH:
1. **Optical System Performance** (device-specific: LED, detector, fiber, optics)
2. **SPR Sensor Response** (consumable-specific: water coupling, surface chemistry, binding)

**ML system MUST distinguish these two sources** to provide actionable diagnostics:
- "Recalibrate LEDs" ← Optics issue
- "Replace sensor" ← SPR issue

**This document defines the separation strategy for live monitoring.**

---

## 1. The Convolution Problem

### 1.1 What We Measure (Live Acquisition)

During live measurement, the transmission spectrum is:

```
T_live(λ, t) = P_live(λ, t) / S_ref(λ)
             = [LED(λ) × Optics(λ) × SPR_sensor(λ, t)] / [LED(λ) × Optics(λ)]
             = SPR_sensor(λ, t)
```

**BUT** this assumes LED and Optics remain constant (from calibration).

### 1.2 What Actually Changes

**Reality:** Three independent factors can change:

1. **Optical System Drift** (device-specific):
   - LED intensity degradation
   - Detector sensitivity shift
   - Fiber misalignment
   - Temperature effects on optics
   - Polarizer position drift

2. **SPR Sensor Changes** (consumable-specific):
   - Analyte binding (SIGNAL - what we want!)
   - Surface degradation
   - Water evaporation (drying)
   - Contamination/fouling
   - Temperature effects on gold layer

3. **Calibration Reference Drift** (S-ref aging):
   - If S_ref was measured 2 hours ago, LED may have drifted
   - Causes apparent SPR shift that's actually LED drift

**Problem:** A change in T_live(λ, t) could be any of these three!

---

## 2. Separation Strategy: Feature-Based Discrimination

### 2.1 Core Principle

**Different sources have different signatures in feature space:**

| Feature | Optics Issue (Device) | Sensor Physical Issue | Experimental/Biology Issue |
|---------|----------------------|----------------------|---------------------------|
| **Affects all channels equally?** | ✅ YES (shared optics) | ❌ NO (independent sensors) | ❓ DEPENDS (flow-based vs sample-specific) |
| **Wavelength-dependent pattern?** | Matches LED spectrum shape | Matches SPR dip shape | Matches SPR dip + refractive index |
| **Temporal behavior?** | Slow drift (minutes-hours) | Step changes or gradual degradation | Binding curves, flow steps, temp ramps |
| **Peak depth change?** | Entire spectrum scales | Only SPR dip depth changes | SPR dip depth + position (coupled) |
| **Peak position change?** | Usually stable | Rare (unless decoupling) | ✅ YES (refractive index changes) |
| **FWHM change?** | Usually stable | Broadens with degradation | May narrow/broaden with temperature |
| **Background slope change?** | ✅ YES (LED spectrum shift) | ❌ NO (background unaffected) | ❌ NO (unless refractive index extreme) |
| **Reversibility?** | ❌ NO (monotonic drift) | ❌ NO (permanent damage) | ✅ YES (injection cycles, temperature) |
| **Flow correlation?** | ❌ NO | ❓ SOMETIMES (drying during stop) | ✅ YES (mass transport, shear) |
| **Temperature correlation?** | ⚠️ YES (electronics drift) | ⚠️ YES (gold thermal expansion) | ✅ YES (bulk refractive index) |

### 2.2 Diagnostic Decision Tree

```
Signal change detected in live data
    ↓
┌───────────────────────────────────────────────────────────────┐
│ STEP 1: Multi-Channel Consistency Check                      │
├───────────────────────────────────────────────────────────────┤
│ Is change consistent across ALL 4 channels?                  │
│   YES → Likely OPTICS/LED or EXPERIMENTAL (flow/temp)        │
│         → Go to STEP 2A                                       │
│   NO  → Likely SENSOR-SPECIFIC or SAMPLE-SPECIFIC            │
│         → Go to STEP 2B                                       │
└───────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────┐
│ STEP 2A: All Channels Affected (System-Wide)                 │
├───────────────────────────────────────────────────────────────┤
│ Check feature pattern:                                        │
│  • Background slope changed?                                  │
│    → LED SPECTRUM SHIFT (device/optics)                       │
│  • Entire spectrum intensity scaled?                          │
│    → LED INTENSITY DRIFT (device/optics)                      │
│  • Position shift + depth change (coupled)?                   │
│    → TEMPERATURE CHANGE (experimental/biology)                │
│  • Noise increased?                                           │
│    → DETECTOR ISSUE (device/optics)                           │
│  • Correlated with pump action?                               │
│    → FLOW RATE CHANGE (experimental/biology)                  │
│  • Reversible with buffer injection?                          │
│    → BUFFER/CHEMISTRY (experimental/biology)                  │
└───────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────┐
│ STEP 2B: Single/Few Channels Affected (Channel-Specific)     │
├───────────────────────────────────────────────────────────────┤
│ Check feature pattern:                                        │
│  • Only SPR dip depth changed (position stable)?              │
│    → SENSOR COUPLING LOSS (sensor physical)                   │
│  • SPR dip position shifted (smooth curve)?                   │
│    → ANALYTE BINDING (experimental/biology - SIGNAL!)         │
│  • SPR dip broadened (FWHM increase)?                         │
│    → SENSOR DEGRADATION (sensor physical)                     │
│  • Step change during injection?                              │
│    → REFRACTIVE INDEX MISMATCH (experimental/biology)         │
│  • Gradual drift after injection?                             │
│    → NON-SPECIFIC BINDING (experimental/biology)              │
└───────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────┐
│ STEP 3: Temporal & Contextual Analysis                       │
├───────────────────────────────────────────────────────────────┤
│ Consider timing and context:                                 │
│  • Gradual over minutes-hours + irreversible?                │
│    → LED DRIFT (device) or SENSOR AGING (sensor)              │
│  • Sudden step + irreversible?                                │
│    → WATER LOSS (sensor) or AIR BUBBLE (experimental)         │
│  • Smooth curve + reversible (dissociation)?                  │
│    → BINDING/UNBINDING (experimental - EXPECTED SIGNAL!)      │
│  • Oscillating pattern?                                       │
│    → TEMPERATURE CYCLING (experimental) or PUMP (flow)        │
│  • Correlated with protocol steps?                            │
│    → EXPECTED EXPERIMENTAL BEHAVIOR                           │
│  • Random fluctuations?                                       │
│    → NOISE (device) or FLOW ARTIFACTS (experimental)          │
└───────────────────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────┐
│ STEP 4: Physics & Calibration Validation                     │
├───────────────────────────────────────────────────────────────┤
│ Final checks:                                                 │
│  • Time since calibration >2 hours?                           │
│    → RECALIBRATE (S_ref stale - device)                       │
│  • Peak features within SPR physics model?                    │
│    → EXPECTED BEHAVIOR (experimental or device OK)            │
│  • Peak features outside physics model?                       │
│    → SENSOR ISSUE (sensor physical - degraded/contaminated)   │
│  • Matches expected assay kinetics?                           │
│    → BIOLOGY/CHEMISTRY (experimental - VALID SIGNAL!)         │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Feature Extraction for Separation

### 3.1 Optics-Related Features (Device-Specific)

**These indicate LED/detector/fiber issues:**

1. **Global Intensity Scaling**
   ```python
   # Compare current spectrum to S_ref
   intensity_ratio = np.mean(current_spectrum) / np.mean(s_ref_spectrum)

   if intensity_ratio < 0.8 or intensity_ratio > 1.2:
       flag = "LED_INTENSITY_DRIFT"  # Optics issue
   ```

2. **Background Slope Change**
   ```python
   # Fit linear trend to transmission spectrum (exclude SPR dip region)
   background_slope = fit_linear_trend(transmission, exclude_dip=True)

   if abs(background_slope - calibration_slope) > threshold:
       flag = "LED_SPECTRUM_SHIFT"  # Optics issue
   ```

3. **Multi-Channel Correlation**
   ```python
   # Calculate cross-channel correlation of signal changes
   changes = [channel_A_change, channel_B_change, channel_C_change, channel_D_change]
   correlation = np.corrcoef(changes)

   if correlation.mean() > 0.9:
       flag = "SYSTEM_WIDE_OPTICAL_DRIFT"  # Optics issue
   ```

4. **Noise Floor Change**
   ```python
   # Measure noise in baseline region (away from SPR dip)
   current_noise = np.std(transmission[baseline_region])
   calibration_noise = np.std(transmission_cal[baseline_region])

   if current_noise > 2 * calibration_noise:
       flag = "DETECTOR_NOISE_INCREASE"  # Optics issue
   ```

### 3.2 SPR-Related Features (Sensor Physical - Chip/Coating)

**These indicate sensor chip physical issues:**

1. **SPR Dip Depth Change**
   ```python
   # Measure transmission minimum
   current_depth = transmission[dip_position]
   calibration_depth = transmission_cal[dip_position]

   if current_depth > calibration_depth + 0.1:  # Shallower dip
       flag = "WATER_LOSS_OR_DECOUPLING"  # SPR issue
   ```

2. **SPR Dip Position Shift**
   ```python
   # Track peak position over time
   position_shift = current_position - baseline_position

   if position_shift > 0.5 nm:  # Significant shift
       # Check temporal pattern to distinguish
       if smooth_curve_shape:
           flag = "BINDING_EVENT"  # Experimental/biology - SIGNAL
       else:
           flag = "SENSOR_DRIFT"  # Sensor physical issue
   ```

3. **FWHM Broadening**
   ```python
   # Calculate full width at half maximum
   current_fwhm = calculate_fwhm(transmission)
   calibration_fwhm = calculate_fwhm(transmission_cal)

   if current_fwhm > calibration_fwhm * 1.5:
       flag = "SENSOR_DEGRADATION"  # SPR issue (recycled/damaged)
   ```

4. **Channel-Specific Deviation**
   ```python
   # Check if only one channel shows issue
   if channel_A_deviated and not (channel_B or channel_C or channel_D):
       # Could be sensor physical OR sample-specific (different samples per channel)
       if during_injection:
           flag = "CHANNEL_A_SAMPLE_SPECIFIC"  # Experimental/biology
       else:
           flag = "CHANNEL_A_SENSOR_ISSUE"  # Sensor physical issue
   ```

### 3.3 Experimental/Biological Features ("Everything Above the Sensor")

**These indicate changes in buffer, chemistry, temperature, or biology:**

1. **Temperature-Correlated Changes**
   ```python
   # Check if signal correlates with temperature sensor
   temp_correlation = correlate(spr_signal, temperature_data)

   if temp_correlation > 0.8:  # Strong correlation
       # Calculate expected refractive index shift
       expected_shift = calculate_dn_dT(temp_change) * sensitivity

       if abs(position_shift - expected_shift) < 0.2 nm:
           flag = "TEMPERATURE_EFFECT"  # Experimental - expected physics
       else:
           flag = "TEMPERATURE_PLUS_OTHER"  # Investigate further
   ```

2. **Flow-Correlated Changes**
   ```python
   # Check correlation with pump events
   time_since_flow_change = current_time - last_pump_event

   if time_since_flow_change < 5.0:  # Within 5 seconds
       if position_shift > 0:  # Increasing signal
           flag = "MASS_TRANSPORT_EFFECT"  # Experimental - flow-enhanced binding
       elif dip_depth_increased:  # Shallower dip
           flag = "INJECTION_ARTIFACT"  # Experimental - refractive index step
   ```

3. **Reversible Binding Patterns**
   ```python
   # Analyze sensorgram shape for binding kinetics
   association_phase = detect_smooth_increase(signal)
   dissociation_phase = detect_smooth_decrease(signal)

   if association_phase and dissociation_phase:
       # Fit kinetic model
       ka, kd = fit_kinetic_model(signal, injection_times)

       if fit_quality > 0.9:
           flag = "BINDING_KINETICS"  # Experimental/biology - SIGNAL!
       else:
           flag = "IRREGULAR_BINDING"  # Investigate sample quality
   ```

4. **Buffer/Chemistry Effects**
   ```python
   # Check for bulk refractive index changes
   baseline_before = np.mean(signal[pre_injection_region])
   baseline_during = np.mean(signal[injection_region])
   baseline_after = np.mean(signal[post_injection_region])

   bulk_shift = baseline_during - baseline_before

   if abs(bulk_shift) > 50 RU:  # Large bulk shift
       flag = "BUFFER_MISMATCH"  # Experimental - refractive index difference

   if baseline_after != baseline_before:  # Doesn't return to baseline
       if smooth_return:
           flag = "MASS_TRANSPORT"  # Experimental - flow-limited dissociation
       else:
           flag = "NON_SPECIFIC_BINDING"  # Experimental/biology - sticky sample
   ```

5. **pH/Ionic Strength Effects**
   ```python
   # Detect sudden conformational changes
   if sudden_fwhm_change and position_stable:
       flag = "CONFORMATIONAL_CHANGE"  # Experimental/biology - pH or ionic strength

   # Detect aggregation
   if gradual_signal_increase and increasing_fwhm:
       flag = "AGGREGATION"  # Experimental/biology - sample instability
   ```

6. **Multi-Channel Sample-Specific Patterns**
   ```python
   # Different samples in different channels
   if different_samples_per_channel:
       # Check if patterns match expected sample behavior
       for channel in ['A', 'B', 'C', 'D']:
           sample_type = get_sample_type(channel)
           expected_response = get_expected_response(sample_type)

           if matches_expected(signal, expected_response):
               flag = f"CHANNEL_{channel}_EXPECTED_BIOLOGY"
           else:
               flag = f"CHANNEL_{channel}_UNEXPECTED_BEHAVIOR"
   ```

---

## 4. Implementation in ML System

### 4.1 Feature Vector Structure

```python
class LiveMonitoringFeatures:
    """Features for live monitoring - separated by source"""

    # === OPTICS-RELATED (Device) ===
    optical_intensity_drift: float       # Global intensity change
    optical_spectrum_shift: float        # Background slope change
    optical_noise_increase: float        # Baseline noise increase
    optical_multi_channel_correlation: float  # Cross-channel consistency
    optical_temperature_drift: float     # If temp sensor available

    # === SPR-RELATED (Sensor) ===
    spr_dip_depth_change: float         # Transmission minimum change
    spr_dip_position_shift: float       # Peak position shift (nm)
    spr_fwhm_broadening: float          # Peak width increase
    spr_dip_asymmetry_change: float     # Peak shape distortion
    spr_coupling_quality_score: float   # Overall SPR quality

    # === EXPERIMENTAL/BIOLOGY (Above Sensor) ===
    exp_temperature_correlation: float  # Correlation with temp sensor
    exp_flow_correlation: float         # Correlation with pump events
    exp_reversibility_score: float      # Binding/unbinding pattern
    exp_bulk_shift: float               # Buffer refractive index change
    exp_baseline_return: bool           # Returns to baseline after injection
    exp_kinetic_fit_quality: float      # Binding kinetics model fit

    # === TEMPORAL ===
    change_rate: float                   # How fast (RU/s or nm/s)
    time_since_calibration: float        # S_ref age (minutes)

    # === METADATA ===
    channel: str
    timestamp: float
    measurement_phase: str  # 'baseline', 'injection', 'dissociation', etc.
```

### 4.2 Classification Logic

```python
def classify_issue_source(features: LiveMonitoringFeatures) -> str:
    """
    Determine if observed change is:
    - DEVICE_OPTICS (hardware-related)
    - SENSOR_PHYSICAL (chip/coating issue)
    - EXPERIMENTAL_BIOLOGY (buffer/chemistry/binding - expected!)
    - CALIBRATION_STALE (need recalibration)
    """

    # Rule 1: Multi-channel correlation → Device or Experimental
    if features.optical_multi_channel_correlation > 0.85:
        # Check if device-related
        if features.optical_intensity_drift > 0.2:
            return "DEVICE_OPTICS: LED_INTENSITY_DRIFT"
        elif features.optical_spectrum_shift > threshold:
            return "DEVICE_OPTICS: LED_SPECTRUM_SHIFT"
        elif features.optical_noise_increase > 2.0:
            return "DEVICE_OPTICS: DETECTOR_NOISE"

        # Check if experimental (temperature, flow, buffer)
        elif features.exp_temperature_correlation > 0.8:
            return "EXPERIMENTAL: TEMPERATURE_EFFECT"
        elif features.exp_flow_correlation > 0.8:
            return "EXPERIMENTAL: FLOW_EFFECT"
        elif features.exp_bulk_shift > 50:  # RU
            return "EXPERIMENTAL: BUFFER_MISMATCH"
        else:
            return "DEVICE_OPTICS: SYSTEM_DRIFT_UNKNOWN"

    # Rule 2: Single-channel deviation → Sensor or Sample-specific
    elif features.optical_multi_channel_correlation < 0.3:
        # Check if it looks like binding (smooth, reversible)
        if features.exp_kinetic_fit_quality > 0.9:
            return "EXPERIMENTAL_BIOLOGY: BINDING_EVENT"

        # Check for sensor physical degradation
        elif features.spr_fwhm_broadening > 1.5:
            return "SENSOR_PHYSICAL: SENSOR_DEGRADED"

        # Check for water loss (physical)
        elif features.spr_dip_depth_change > 0.15:
            return "SENSOR_PHYSICAL: WATER_LOSS"

        # Check for non-specific binding (biological)
        elif not features.exp_baseline_return:
            return "EXPERIMENTAL_BIOLOGY: NON_SPECIFIC_BINDING"

        # Check for contamination (physical)
        elif features.spr_dip_asymmetry_change > 0.3:
            return "SENSOR_PHYSICAL: CONTAMINATION"

        else:
            return "SENSOR_PHYSICAL: UNKNOWN"

    # Rule 3: Old calibration → Need refresh
    elif features.time_since_calibration > 120:  # 2 hours
        return "CALIBRATION_STALE: RECALIBRATE_NEEDED"

    # Rule 4: Within normal bounds
    else:
        return "NORMAL: NO_ISSUE_DETECTED"
```

### 4.3 User-Facing Actions

Map classifications to actionable recommendations:

```python
ACTION_RECOMMENDATIONS = {
    # === DEVICE/OPTICS (Hardware) ===
    "DEVICE_OPTICS: LED_INTENSITY_DRIFT": {
        "severity": "MEDIUM",
        "action": "Recalibrate system - LED intensity has drifted >20%",
        "icon": "🔧",
        "technical": "Check LED operating hours, may need replacement if >5000h",
        "category": "DEVICE"
    },

    "DEVICE_OPTICS: LED_SPECTRUM_SHIFT": {
        "severity": "MEDIUM",
        "action": "Recalibrate system - LED spectrum has shifted",
        "icon": "🔧",
        "technical": "LED aging or temperature effect, recalibration will correct",
        "category": "DEVICE"
    },

    "DEVICE_OPTICS: DETECTOR_NOISE": {
        "severity": "HIGH",
        "action": "Check spectrometer connection and reduce integration time",
        "icon": "⚠️",
        "technical": "USB communication issue or detector overheating",
        "category": "DEVICE"
    },

    # === SENSOR PHYSICAL (Chip/Coating) ===
    "SENSOR_PHYSICAL: SENSOR_DEGRADED": {
        "severity": "HIGH",
        "action": "Replace sensor - FWHM broadening indicates damage/recycling",
        "icon": "🔴",
        "technical": "Sensor surface degraded, >50% wider than calibration",
        "category": "CONSUMABLE"
    },

    "SENSOR_PHYSICAL: WATER_LOSS": {
        "severity": "CRITICAL",
        "action": "STOP - Water/buffer has evaporated or decoupled",
        "icon": "🚨",
        "technical": "SPR dip depth increased >15%, no water contact with sensor",
        "category": "CONSUMABLE"
    },

    "SENSOR_PHYSICAL: CONTAMINATION": {
        "severity": "HIGH",
        "action": "Clean sensor - contamination detected from peak asymmetry",
        "icon": "⚠️",
        "technical": "Peak shape distorted, likely particulate or bubble",
        "category": "CONSUMABLE"
    },

    # === EXPERIMENTAL/BIOLOGY (Expected Behavior) ===
    "EXPERIMENTAL_BIOLOGY: BINDING_EVENT": {
        "severity": "INFO",
        "action": "Normal - analyte binding detected (kinetic fit quality >0.9)",
        "icon": "✅",
        "technical": "Expected SPR response, smooth binding curve",
        "category": "EXPECTED_SIGNAL"
    },

    "EXPERIMENTAL: TEMPERATURE_EFFECT": {
        "severity": "INFO",
        "action": "Temperature change detected - signal follows expected physics",
        "icon": "🌡️",
        "technical": "Signal correlates with temperature sensor (r>0.8)",
        "category": "EXPECTED_SIGNAL"
    },

    "EXPERIMENTAL: FLOW_EFFECT": {
        "severity": "INFO",
        "action": "Flow rate change detected - mass transport effect",
        "icon": "💧",
        "technical": "Signal correlates with pump events, may affect kinetics",
        "category": "EXPECTED_SIGNAL"
    },

    "EXPERIMENTAL: BUFFER_MISMATCH": {
        "severity": "LOW",
        "action": "Large bulk shift detected - check buffer matching",
        "icon": "⚗️",
        "technical": "Refractive index mismatch >50 RU, consider matched buffers",
        "category": "EXPERIMENTAL"
    },

    "EXPERIMENTAL_BIOLOGY: NON_SPECIFIC_BINDING": {
        "severity": "MEDIUM",
        "action": "Signal doesn't return to baseline - non-specific binding or aggregation",
        "icon": "⚠️",
        "technical": "Check sample purity, pH, ionic strength",
        "category": "EXPERIMENTAL"
    },

    # === CALIBRATION ===
    "CALIBRATION_STALE: RECALIBRATE_NEEDED": {
        "severity": "MEDIUM",
        "action": "Recalibrate system - reference data is >2 hours old",
        "icon": "🔄",
        "technical": "S_ref may have drifted, refresh calibration for accuracy",
        "category": "CALIBRATION"
    }
}
```

---

## 5. Real-Time Monitoring Implementation

### 5.1 Processing Pipeline

```python
class LiveOpticsVsSPRMonitor:
    """Real-time monitoring with optics vs SPR separation"""

    def __init__(self, calibration_data: dict):
        self.s_ref = calibration_data['s_ref']
        self.calibration_features = self._extract_calibration_features()
        self.calibration_timestamp = time.time()
        self.channel_history = {ch: [] for ch in ['A', 'B', 'C', 'D']}

    def process_live_spectrum(self, p_live: np.ndarray, channel: str,
                             timestamp: float) -> dict:
        """
        Process one live P-spectrum and classify issues.

        Args:
            p_live: Live P-mode spectrum
            channel: Channel ID
            timestamp: Acquisition timestamp

        Returns:
            {
                'classification': str,  # Issue type
                'severity': str,        # INFO/MEDIUM/HIGH/CRITICAL
                'action': str,          # User recommendation
                'features': dict,       # Extracted features
                'confidence': float     # 0-1
            }
        """
        # Step 1: Calculate transmission
        transmission = p_live / self.s_ref[channel]

        # Step 2: Extract features
        features = self._extract_live_features(transmission, channel, timestamp)

        # Step 3: Compare to calibration baseline
        deviations = self._calculate_deviations(features, self.calibration_features[channel])

        # Step 4: Multi-channel correlation analysis
        multi_channel_corr = self._check_multi_channel_correlation(features, channel)
        features.optical_multi_channel_correlation = multi_channel_corr

        # Step 5: Classify issue source
        classification = classify_issue_source(features)

        # Step 6: Generate recommendation
        recommendation = ACTION_RECOMMENDATIONS[classification]

        # Step 7: Calculate confidence
        confidence = self._calculate_confidence(features, deviations)

        # Store in history
        self.channel_history[channel].append({
            'timestamp': timestamp,
            'features': features,
            'classification': classification
        })

        return {
            'classification': classification,
            'severity': recommendation['severity'],
            'action': recommendation['action'],
            'features': asdict(features),
            'confidence': confidence,
            'timestamp': timestamp
        }

    def _check_multi_channel_correlation(self, current_features: LiveMonitoringFeatures,
                                         current_channel: str) -> float:
        """
        Check if observed change is consistent across all channels.

        High correlation (>0.8) → Likely optics issue
        Low correlation (<0.3) → Likely sensor-specific issue
        """
        # Get recent features from all channels
        recent_window = 10  # Last 10 measurements

        changes = []
        for ch in ['A', 'B', 'C', 'D']:
            if len(self.channel_history[ch]) < recent_window:
                return 0.5  # Not enough data yet

            recent = self.channel_history[ch][-recent_window:]
            baseline = self.calibration_features[ch]

            # Calculate average deviation from calibration
            intensity_change = np.mean([f['features'].optical_intensity_drift for f in recent])
            changes.append(intensity_change)

        # Calculate correlation coefficient
        correlation_matrix = np.corrcoef(changes)
        avg_correlation = np.mean(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)])

        return avg_correlation

    def _extract_live_features(self, transmission: np.ndarray, channel: str,
                              timestamp: float) -> LiveMonitoringFeatures:
        """Extract all features from live transmission spectrum"""

        # === OPTICS FEATURES ===

        # Global intensity (compare to S_ref baseline intensity)
        baseline_intensity = np.mean(transmission[200:400])  # Baseline region
        cal_baseline_intensity = self.calibration_features[channel]['baseline_intensity']
        intensity_drift = abs(baseline_intensity - cal_baseline_intensity) / cal_baseline_intensity

        # Spectrum shape (background slope)
        background_slope = np.polyfit(range(100, 200), transmission[100:200], 1)[0]
        cal_slope = self.calibration_features[channel]['background_slope']
        spectrum_shift = abs(background_slope - cal_slope)

        # Noise (baseline region std)
        noise = np.std(transmission[200:400])
        cal_noise = self.calibration_features[channel]['baseline_noise']
        noise_increase = noise / cal_noise

        # === SPR FEATURES ===

        # Find SPR dip
        dip_position = np.argmin(transmission)
        dip_depth = transmission[dip_position]
        cal_dip_depth = self.calibration_features[channel]['dip_depth']
        depth_change = abs(dip_depth - cal_dip_depth)

        # Peak position (wavelength)
        position_shift = dip_position - self.calibration_features[channel]['dip_position']

        # FWHM
        fwhm = self._calculate_fwhm(transmission, dip_position)
        cal_fwhm = self.calibration_features[channel]['fwhm']
        fwhm_broadening = fwhm / cal_fwhm

        # Asymmetry
        asymmetry = self._calculate_asymmetry(transmission, dip_position)
        cal_asymmetry = self.calibration_features[channel]['asymmetry']
        asymmetry_change = abs(asymmetry - cal_asymmetry)

        # === TEMPORAL ===
        time_since_cal = (timestamp - self.calibration_timestamp) / 60.0  # minutes

        return LiveMonitoringFeatures(
            # Optics
            optical_intensity_drift=intensity_drift,
            optical_spectrum_shift=spectrum_shift,
            optical_noise_increase=noise_increase,
            optical_multi_channel_correlation=0.0,  # Filled in later
            optical_temperature_drift=0.0,  # TODO: Add if temp sensor available

            # SPR
            spr_dip_depth_change=depth_change,
            spr_dip_position_shift=position_shift,
            spr_fwhm_broadening=fwhm_broadening - 1.0,  # Excess over 1.0
            spr_dip_asymmetry_change=asymmetry_change,
            spr_coupling_quality_score=self._calculate_spr_quality(dip_depth, fwhm),

            # Temporal
            change_rate=0.0,  # TODO: Calculate from history
            time_since_calibration=time_since_cal,

            # Metadata
            channel=channel,
            timestamp=timestamp,
            measurement_phase='live'  # TODO: Get from cycle protocol
        )
```

---

## 6. Integration with Existing Systems

### 6.1 Connection to LED Health Monitor

**utils/led_health_monitor.py** tracks LED degradation over time (device-specific).

**Integration:**
```python
# In live monitoring, check if LED health check is overdue
if led_health_monitor.should_run_health_check():
    # LED drift suspected, classify as OPTICS issue
    classification = "OPTICS: LED_AGING_DETECTED"
```

### 6.2 Connection to FMEA Tracker

**core/fmea_integration.py** logs failure modes.

**Integration:**
```python
# Map classification to FMEA failure mode
if classification.startswith("OPTICS:"):
    fmea_helper.log_live_data_event(
        event_type='optical_system_drift',
        channel=channel,
        passed=False,
        metrics=features_dict,
        failure_mode=FailureMode.LED_DRIFT,  # or DETECTOR_NOISE, etc.
        severity=Severity.MEDIUM,
        mitigation="Recalibrate system"
    )

elif classification.startswith("SPR_ISSUE:"):
    fmea_helper.log_live_data_event(
        event_type='spr_sensor_issue',
        channel=channel,
        passed=False,
        metrics=features_dict,
        failure_mode=FailureMode.SENSOR_DEGRADATION,  # or WATER_LOSS, etc.
        severity=Severity.HIGH,
        mitigation="Replace sensor"
    )
```

### 6.3 Connection to Spectral ML Framework

**docs/analysis/SPECTRAL_ML_ANALYSIS_FRAMEWORK.md** defines physics-informed models.

**Integration:**
- Use empirical SPR baseline to validate spr_coupling_quality_score
- Apply algorithm bias correction before peak position tracking
- Leverage adaptive method selection based on peak shape

---

## 7. User Interface Indicators

### 7.1 Real-Time Status Display

**Proposed UI elements:**

```
┌─────────────────────────────────────────────────────────────┐
│ SYSTEM HEALTH MONITOR                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  OPTICAL SYSTEM: ✅ GOOD                                    │
│    LED Drift: 3.2% (threshold: 20%)                        │
│    Detector Noise: 1.2× baseline (threshold: 2×)           │
│    Last Calibration: 45 min ago                            │
│                                                             │
│  SPR SENSORS:                                              │
│    Channel A: ✅ Normal (coupling: 95%)                    │
│    Channel B: ✅ Normal (coupling: 93%)                    │
│    Channel C: ⚠️ WARNING - FWHM broadened 35%             │
│                   → Recommend sensor inspection            │
│    Channel D: ✅ Normal (coupling: 94%)                    │
│                                                             │
│  RECOMMENDED ACTIONS:                                      │
│    • Monitor Channel C - may need replacement soon         │
│    • Recalibration due in 75 minutes                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Alert Prioritization

**Severity levels:**

- **INFO** (✅): Normal operation, expected binding
- **MEDIUM** (🔧): Recalibration recommended, not urgent
- **HIGH** (⚠️): Sensor quality degraded, replace soon
- **CRITICAL** (🚨): Stop measurement, water loss or major failure

---

## 8. Validation Strategy

### 8.1 Test Scenarios

**Optics Issues (should flag as device-specific):**
1. Reduce LED intensity manually → Expect "LED_INTENSITY_DRIFT"
2. Wait 4 hours after calibration → Expect "CALIBRATION_STALE"
3. Disconnect fiber briefly → Expect "DETECTOR_NOISE"

**SPR Issues (should flag as sensor-specific):**
1. Let water evaporate → Expect "WATER_LOSS"
2. Use recycled sensor → Expect "SENSOR_DEGRADED"
3. Inject analyte → Expect "BINDING_EVENT" (not an issue!)

**Cross-Validation:**
- Change affecting all 4 channels → Must flag as OPTICS
- Change affecting 1 channel only → Must flag as SPR_ISSUE

### 8.2 Performance Metrics

**Accuracy targets:**
- Correct optics vs SPR classification: >90%
- False positive rate (flagging binding as issue): <5%
- True positive rate (catching real issues): >95%

---

## 9. Documentation Cross-References

### 9.1 Related Documents

| Document | Relevance |
|----------|-----------|
| `SPECTRAL_ML_ANALYSIS_FRAMEWORK.md` | Physics models, algorithm bias, feature extraction |
| `CALIBRATION_MASTER.md` | S-mode vs P-mode distinction, QC metrics |
| `led_health_monitor.py` | LED degradation tracking (optics) |
| `fmea_integration.py` | Failure mode logging |
| `spectral_quality_analyzer.py` | Feature extraction implementation |

### 9.2 Key Concepts Summary

**From CALIBRATION_MASTER.md:**
- S-mode = Detector + LED performance (NO SPR information)
- P-mode = Sensor + SPR validation (requires water for SPR dip)
- Transmission (P/S) cancels LED drift → BUT only if S_ref is fresh!

**From SPECTRAL_ML_ANALYSIS_FRAMEWORK.md:**
- Algorithm bias depends on peak shape (depth, FWHM, asymmetry)
- Physics-informed models predict expected SPR behavior
- Deviation from expected → Sensor issue

**From this document:**
- Multi-channel correlation → Optics issue
- Single-channel deviation → Sensor issue
- Feature patterns distinguish optics from SPR

---

## 10. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Implement `LiveMonitoringFeatures` dataclass
- [ ] Implement `LiveOpticsVsSPRMonitor` class
- [ ] Add multi-channel correlation analysis
- [ ] Create classification decision tree

### Phase 2: Feature Extraction
- [ ] Extract optics-related features (intensity, slope, noise)
- [ ] Extract SPR-related features (depth, position, FWHM)
- [ ] Validate feature extraction on known good/bad data

### Phase 3: Classification Logic
- [ ] Implement `classify_issue_source()` function
- [ ] Define `ACTION_RECOMMENDATIONS` mapping
- [ ] Add confidence scoring

### Phase 4: Integration
- [ ] Connect to LED health monitor
- [ ] Connect to FMEA tracker
- [ ] Connect to Spectral ML framework
- [ ] Add UI status indicators

### Phase 5: Validation
- [ ] Test with optics issues (LED drift, noise)
- [ ] Test with SPR issues (water loss, degradation)
- [ ] Measure classification accuracy
- [ ] Collect field data for model refinement

---

## 11. Key Takeaways

### ✅ DO THIS:

1. **Always check multi-channel correlation FIRST**
   - High correlation → Optics (all channels affected)
   - Low correlation → Sensor (channel-specific)

2. **Use feature patterns, not just magnitude**
   - Background slope change → LED spectrum shift (optics)
   - SPR dip broadening → Sensor degradation (SPR)

3. **Consider temporal behavior**
   - Slow drift → LED/detector aging (optics)
   - Fast step → Sensor event (SPR)

4. **Track calibration age**
   - S_ref >2 hours old → May be stale (flag for recalibration)

5. **Provide actionable recommendations**
   - Don't just say "Issue detected" - say "Recalibrate LEDs" or "Replace sensor"

### ❌ AVOID THIS:

1. **Don't assume single-channel change = binding**
   - Could be sensor degradation, water loss, contamination

2. **Don't ignore multi-channel consistency**
   - All channels drifting together → Not sensor, it's optics!

3. **Don't treat all deviations equally**
   - Some are expected (binding), some are critical (water loss)

4. **Don't forget to update S_ref**
   - Stale reference → Apparent SPR shifts that are really LED drift

---

## 12. Future Enhancements

### Advanced ML Model

Train supervised classifier on labeled dataset:
- **Input:** LiveMonitoringFeatures vector
- **Labels:** [OPTICS_LED, OPTICS_DETECTOR, SPR_BINDING, SPR_WATER_LOSS, SPR_DEGRADATION, etc.]
- **Output:** Classification + confidence score

### Predictive Maintenance

Use historical trends to predict:
- When LED recalibration will be needed (before it fails)
- When sensor will degrade (end-of-life prediction)
- Optimal recalibration schedule

### Cloud Learning

Aggregate data across devices to improve models:
- Learn device-specific vs. universal patterns
- Detect manufacturing batch effects
- Improve classification accuracy over time

---

**END OF DOCUMENT**

*This document is CRITICAL for ensuring the ML monitoring system correctly attributes signal changes to their true source (optics vs SPR), enabling actionable diagnostics during live measurements.*
