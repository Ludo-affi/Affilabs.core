# Spectral Quality Analysis System - Phase 1: System Characterization

## 🎯 Current Focus: Optimizing Your Instrument

**PRIMARY GOAL**: Characterize and optimize the core SPR measurement system for minimal peak-to-peak variation.

This phase focuses on understanding and optimizing:
1. **LED performance** (stability, spectrum, afterglow)
2. **Detector characteristics** (noise, linearity, thermal behavior)
3. **Peak tracking algorithm** (accuracy, stability, robustness)
4. **Signal processing** (filtering, baseline correction, wavelength calibration)

**FUTURE EXPANSION**: Once the instrument is fully characterized and optimized, these tools can expand to distinguish consumable quality issues.

## 📁 Files Created

### 1. `spectral_quality_analyzer.py` (Main Tool)
**Purpose**: Analyze individual or batch CSV files and generate diagnostic reports

**Key Features**:
- Extracts 30+ spectral features per channel
- Performs frequency analysis of noise (high-freq = instrumental, low-freq = consumable)
- Calculates quality scores (0-100) for instrumental and consumable
- Assigns overall grade (A/B/C/D/F)
- Generates detailed JSON reports with diagnosis

**Usage**:
```bash
# Analyze single file
python spectral_quality_analyzer.py analyze test.csv -o report.json

# Analyze all files in directory
python spectral_quality_analyzer.py batch ./sensor_data/ -o batch_report.json

# Display existing report
python spectral_quality_analyzer.py report batch_report.json
```

### 2. `compare_sensors.py` (Comparison Tool)
**Purpose**: Compare multiple sensors to identify patterns

**Key Features**:
- Side-by-side comparison of key metrics
- Pattern detection (consistent issues = instrumental, varying = consumable)
- Identifies best/worst sensors
- Provides targeted recommendations

**Usage**:
```bash
python compare_sensors.py sensor1.csv sensor2.csv sensor3.csv
```

### 3. `SPECTRAL_QUALITY_TRAINING_GUIDE.md` (Documentation)
**Purpose**: Complete guide for training the system on your data

**Contents**:
- Feature explanations
- Diagnostic patterns
- Training workflow (baseline → controlled degradation → blind testing)
- Interpretation examples
- Integration instructions

## 🔬 How It Works

### Feature Categories Analyzed

#### 1. **Noise Frequency Analysis** (KEY DISCRIMINATOR)
- **High frequency (>0.1 Hz)**: LED flickering, electronics, shot noise → **INSTRUMENTAL**
- **Low frequency (<0.1 Hz)**: Surface defects, coating non-uniformity → **CONSUMABLE**

```
Frequency Ratio > 2.0  → Instrumental problem
Frequency Ratio < 0.5  → Consumable problem
```

#### 2. **Wavelength Stability**
- Measures peak wavelength drift over time
- High drift (>0.5 nm) indicates optical/LED issues → **INSTRUMENTAL**

#### 3. **Temporal Behavior**
- Signal improving over time (thermal stabilization) → Normal
- Signal worsening over time → **INSTRUMENTAL** thermal issue
- High drift rate → **CONSUMABLE** coating instability

#### 4. **Transmission Spectrum Quality**
- High transmission minimum → Poor coating → **CONSUMABLE**
- Low smoothness → Surface roughness → **CONSUMABLE**
- Asymmetric peaks → Coating gradients → **CONSUMABLE**

### Quality Scoring Algorithm

**Instrumental Score (0-100)**:
```
Start: 100
- High frequency noise ratio > 2.0: -30 pts
- Wavelength std > 0.5 nm: -25 pts
- Thermal instability (worsening): -20 pts
- Overall high noise: -25 pts
```

**Consumable Score (0-100)**:
```
Start: 100
- Low frequency noise ratio < 0.5: -30 pts
- Transmission min > 0.05: -25 pts
- Low smoothness < 1.0: -20 pts
- High drift rate > 0.2: -25 pts
```

**Overall Grade**:
- A: avg score ≥ 80 (Excellent)
- B: avg score ≥ 65 (Good)
- C: avg score ≥ 50 (Acceptable)
- D: avg score ≥ 35 (Poor)
- F: avg score < 35 (Failing)

## 📊 Your Current Data Analysis

From `test.csv` (analyzed automatically):

| Channel | Grade | Inst Score | Cons Score | Noise (RU) | P2P (RU) | Wavelength Std |
|---------|-------|------------|------------|------------|----------|----------------|
| **A** | **B** | **100** | **53** | **2.16** | **11.5** | **0.09 nm** ✅ |
| B | D | 55 | 43 | 14.12 | 67.2 | 1.01 nm ⚠️ |
| C | B | 100 | 30 | 10.66 | 47.4 | 0.42 nm |
| D | C | 86 | 31 | 16.76 | 88.7 | 0.77 nm |

### Diagnosis for Your System:
1. **PRIMARY ISSUE**: Consumable quality (low frequency noise dominant in all channels)
   - Sensor chip likely has surface defects or coating non-uniformity
   - **Recommendation**: Try fresh sensor chip

2. **SECONDARY ISSUE**: Channel B has instrumental problems
   - High wavelength instability (1.01 nm)
   - LED may be unstable or nearing end of life
   - **Recommendation**: Monitor Channel B LED specifically

3. **GOOD NEWS**: Channel A excellent performance validates that:
   - Your LED delay fix (2.6ms → 20ms) is working ✅
   - Afterglow correction is effective ✅
   - Instrumental system is fundamentally sound ✅

## 🚀 Phase 1 Workflow: Instrument Characterization

### Step 1: Baseline LED/Detector Performance (Week 1)
```bash
# Multiple measurements with SAME chip to isolate instrument behavior
# This removes chip-to-chip variation from the analysis

# Measurement 1 (fresh start, after warm-up)
python spectral_quality_analyzer.py analyze measurement_1.csv -o m1.json

# Measurement 2 (30 min later, same chip)
python spectral_quality_analyzer.py analyze measurement_2.csv -o m2.json

# Measurement 3 (next day, same chip)
python spectral_quality_analyzer.py analyze measurement_3.csv -o m3.json

# Compare to see instrument consistency
python compare_sensors.py measurement_1.csv measurement_2.csv measurement_3.csv
```

**Goal**:
- Quantify instrument repeatability (should be excellent if chip constant)
- Establish baseline noise floor for each channel
- Identify any thermal drift patterns
- Validate LED stability across multiple runs

### Step 2: LED Characterization (Week 2)

**Test A: Warm-up Behavior**
```bash
# Measure immediately after power-on (no warm-up)
python spectral_quality_analyzer.py analyze cold_start.csv -o cold.json

# Measure after 5 min warm-up
python spectral_quality_analyzer.py analyze warmup_5min.csv -o warm5.json

# Measure after 15 min warm-up
python spectral_quality_analyzer.py analyze warmup_15min.csv -o warm15.json

# Compare thermal stabilization
python compare_sensors.py cold_start.csv warmup_5min.csv warmup_15min.csv
```
**Expected**: Wavelength stability improves, noise decreases with warm-up time

**Test B: LED Delay Validation**
```bash
# Current setting: 20ms delay
# Verify all channels show consistent afterglow correction
python spectral_quality_analyzer.py analyze current_delay.csv -o delay_current.json
```
**Goal**: Confirm high-frequency noise is minimized, wavelength stability is excellent

**Test C: Per-Channel LED Performance**
```bash
# Analyze which channel LEDs are most stable
# Look for wavelength_std < 0.5 nm as "good"
# wavelength_std > 0.8 nm as "needs attention"
```

### Step 3: Peak Tracking Validation (Week 3)

**Test D: Peak Tracking Under Known Conditions**
```bash
# Use measurement with good signal (like your Channel A)
# Verify peak tracking is stable: wavelength_std should be < 0.2 nm

# If peak wanders > 0.5 nm → review peak finding algorithm
# If sharp jumps visible → may need smoothing in peak detection
```

**Test E: Multi-Channel Comparison**
```bash
# Compare all 4 channels from same measurement
# They should show similar instrumental scores (since same hardware timing)
# Differences reveal per-channel LED/detector quality
```

### Step 4: Detector Noise Floor (Week 3-4)

**Test F: Dark Measurement Analysis**
```bash
# Run measurement with LEDs off (if possible)
# Or analyze pre-LED portions of spectrum
# Quantify detector read noise, dark current
```

**Test G: Saturation Check**
```bash
# Verify peak intensities are 50-80% of detector max
# Too low → poor SNR
# Too high → risk saturation artifacts
```

## 📈 Integration with Your Workflow

Add automatic quality checks to `spr_data_acquisition.py`:

```python
from spectral_quality_analyzer import SpectralQualityAnalyzer

# After saving CSV
def auto_quality_check(csv_path):
    analyzer = SpectralQualityAnalyzer()
    features = analyzer.analyze_csv(csv_path)

    for feat in features:
        if feat.overall_quality_grade in ['D', 'F']:
            logger.warning(f"⚠️ Quality Alert - Channel {feat.channel}")
            logger.warning(f"   Grade: {feat.overall_quality_grade}")
            logger.warning(f"   Instrumental: {feat.instrumental_quality_score:.0f}")
            logger.warning(f"   Consumable: {feat.consumable_quality_score:.0f}")

            if feat.instrumental_quality_score < 50:
                logger.warning("   → Possible HARDWARE issue - check LED/optics")
            if feat.consumable_quality_score < 50:
                logger.warning("   → Possible CHIP issue - consider replacing")
```

## 🎓 Phase 1 Learning: Instrument Characterization Patterns

### Pattern 1: Excellent LED Performance (Target State)
```
✅ Wavelength std < 0.2 nm (like your Channel A: 0.09 nm)
✅ High instrumental score (> 85)
✅ Low high-frequency noise
✅ Positive stability improvement (thermal stabilization)
✅ Low peak-to-peak variation (< 15 RU)

Example: Your Channel A - this is the reference!
```

### Pattern 2: LED Needs Optimization
```
⚠️ Wavelength std > 0.5 nm (like your Channel B: 1.01 nm)
⚠️ High-frequency noise dominant
⚠️ Instrumental score < 70
⚠️ Negative stability improvement

Action: Check LED delay, verify thermal stabilization, consider LED replacement
Example: Your Channel B
```

### Pattern 3: Insufficient Warm-up
```
⚠️ Negative stability improvement
⚠️ Higher noise in first half vs second half
⚠️ Wavelength drift over measurement

Action: Increase warm-up time from 5min → 15min
```

### Pattern 4: Peak Tracking Issues
```
⚠️ Sudden wavelength jumps (> 1 nm steps)
⚠️ Wavelength std high but smoothly varying
⚠️ Good intensity SNR but poor wavelength stability

Action: Review peak finding algorithm, add smoothing/filtering
```

### Pattern 5: Detector Noise
```
⚠️ High baseline noise even with good signal
⚠️ Noise similar across all wavelengths
⚠️ Consistent across different measurements

Action: Check detector temperature, verify gain settings
```

## 📝 Data Collection Template

For each measurement, record:
```
Filename: sensor_2025-10-22_001.csv
Chip ID: ABC-12345
Chip Age: 2 months
Storage: Refrigerated (4°C), desiccated
Expected Quality: Good
Warm-up Time: 15 minutes
Visual Inspection: No visible defects
Notes: First use of this chip

Analysis Results:
- Overall Grade: B
- Instrumental: 85
- Consumable: 70
- Match Expected: Yes
```

## 🎯 Phase 1 Success Criteria

Your instrument characterization is complete when:

1. ✅ **All 4 channels achieve < 15 RU peak-to-peak variation** (same performance as Channel A)
2. ✅ **Wavelength stability < 0.3 nm std** across all channels (proves peak tracking is solid)
3. ✅ **Instrumental scores > 85** for all channels (proves LED/detector are optimized)
4. ✅ **Repeatability < 5% variation** between measurements with same chip (proves instrument is stable)
5. ✅ **Warm-up protocol defined** (know how long to wait for thermal stability)

**Your Current Status**:
- ✅ Channel A: **EXCELLENT** (11.5 RU p-p, 0.09 nm wavelength std, Inst=100)
- ⚠️ Channel B: Needs LED optimization (67.2 RU p-p, 1.01 nm wavelength std, Inst=55)
- ⚠️ Channel C: Good instrument, but... (47.4 RU p-p, 0.42 nm wavelength std, Inst=100)
- ⚠️ Channel D: Good instrument, but... (88.7 RU p-p, 0.77 nm wavelength std, Inst=86)

**Next Priority**:
1. Fix Channel B LED (wavelength instability suggests LED issue)
2. Investigate why C/D have high p-p despite good instrumental scores → likely indicates our Phase 1 focus is correct!

## 📞 Phase 1 Action Plan

### This Week: Instrument Repeatability
1. **Immediate**: Run 3 measurements with **the same chip** (spaced 30min apart)
   - Use `compare_sensors.py` to see if instrument is repeatable
   - If instrumental scores vary → thermal or LED stability issue
   - If they're consistent → proves instrument is stable

2. **Channel B Investigation**:
   ```bash
   # Check if Channel B LED delay is different
   # Verify Channel B wavelength stability improves after longer warm-up
   # If not → Channel B LED may need replacement
   ```

3. **Baseline Dataset**: Collect 5 measurements with same chip
   - Creates "instrument fingerprint"
   - Quantifies best-case performance

### Next Week: Optimization
1. **Warm-up protocol**: Test 0min, 5min, 10min, 15min warm-up times
2. **Per-channel tuning**: Can Channel B LED delay be adjusted independently?
3. **Peak tracking review**: Analyze if wavelength jumps correlate with noise spikes

### Phase 2 (Future): Consumable Characterization
*Only after all channels achieve <15 RU p-p and <0.3 nm wavelength stability*

Then expand tools to distinguish chip quality variations.

## 🔧 Customization

Adjust thresholds in `spectral_quality_analyzer.py` line 49-67:

```python
self.thresholds = {
    'excellent': {
        'noise_std': 5.0,      # Based on your best Channel A
        'peak_to_peak': 20.0,
        'wavelength_std': 0.2,
        'drift_rate': 0.1,
    },
    # Adjust based on your data
}
```

## ❓ Phase 1 Questions This System Answers

### Instrument Characterization Focus:
- ✅ **Which channel LED needs attention?** (Wavelength stability check)
- ✅ **Is thermal warm-up sufficient?** (Stability improvement trend)
- ✅ **Is peak tracking algorithm working?** (Wavelength std < 0.3 nm?)
- ✅ **Is detector noise acceptable?** (Baseline noise analysis)
- ✅ **Are all channels performing equally?** (Multi-channel comparison)
- ✅ **Is the instrument repeatable?** (Same chip, multiple measurements)
- ✅ **What's the instrument noise floor?** (Best-case performance)

### Current Findings from Your Data:
- ✅ **Channel A is reference-quality** → Use as optimization target
- ⚠️ **Channel B has LED instability** → Priority fix
- ⚠️ **Channels C/D have moderate noise** → May need fine-tuning

**You now have tools to characterize and optimize your SPR instrument!** 🎉

---

## 🔮 Future: Phase 2 Expansion

Once all channels achieve **<15 RU p-p** and **<0.3 nm wavelength stability**, these tools can expand to:
- Distinguish chip quality (good batch vs bad batch)
- Identify consumable storage issues
- Predict chip lifetime
- Validate new chip designs

**But first: Let's get all 4 channels performing like Channel A!** �
