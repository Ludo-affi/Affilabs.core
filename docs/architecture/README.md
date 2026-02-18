# Analysis Framework Documentation

This directory contains AFfilab's proprietary analysis and ML framework documentation.

---

## Core Documents

### 🔬 Machine Learning & Signal Analysis

| Document | Purpose | Status |
|----------|---------|--------|
| **SPECTRAL_ML_ANALYSIS_FRAMEWORK.md** | Physics-informed ML for SPR quality assessment | ✅ Complete |
| **SPECTRAL_ANALYSIS_FRAMEWORK.md** | Consumable issue detection from raw spectra | ✅ Complete |
| **LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md** | **[CRITICAL]** Distinguish device vs sensor issues in live data | ✅ Complete |

### 📊 Optimization & Performance

| Document | Purpose | Status |
|----------|---------|--------|
| FOURIER_ALPHA_OPTIMIZATION_GUIDE.md | Fourier smoothing parameter tuning | ✅ Complete |
| OPTIMAL_PROCESSING_PIPELINE.md | Real-time processing optimization | ✅ Complete |

### 🔧 Calibration & Quality Control

| Document | Purpose | Status |
|----------|---------|--------|
| CALIBRATION_SMART_VALIDATION_PROPOSAL.md | Intelligent calibration validation | ✅ Complete |
| CALIBRATION_QC_IMPLEMENTATION_COMPLETE.md | QC metrics implementation | ✅ Complete |
| CALIBRATION_S_REF_QC_SYSTEM.md | S-reference quality control | ✅ Complete |

---

## Quick Start

**If you're implementing live monitoring:**
1. Read: `LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md` (CRITICAL)
2. Understand: Multi-channel correlation = primary discriminator
3. Implement: Feature extraction + classification logic
4. Validate: Test with optics issues vs SPR issues

**If you're working on ML models:**
1. Read: `SPECTRAL_ML_ANALYSIS_FRAMEWORK.md`
2. Review: Algorithm bias correction formulas
3. Collect: Training data (spectral + afterglow)
4. Build: Empirical baseline for AFfilab sensors

**If you're optimizing signal processing:**
1. Read: `OPTIMAL_PROCESSING_PIPELINE.md`
2. Review: `FOURIER_ALPHA_OPTIMIZATION_GUIDE.md`
3. Benchmark: <10 ms processing requirement

---

## Key Concepts

### S-mode vs P-mode (from CALIBRATION_MASTER.md)

- **S-mode**: Detector + LED performance (NO SPR information)
- **P-mode**: Sensor + SPR validation (requires water for SPR dip)
- **Transmission (P/S)**: Isolates SPR response from optics

### Optics vs SPR Attribution (from LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md)

**During live measurements, signal changes originate from:**
1. **Optics** (device): LED, detector, fiber → Affects all channels equally
2. **SPR Sensor** (consumable): Water, binding, degradation → Channel-specific

**Primary discriminator:** Multi-channel correlation
- High (>0.8) → Optics issue → "Recalibrate system"
- Low (<0.3) → Sensor issue → "Replace sensor" or "Add water"

### Algorithm Bias (from SPECTRAL_ML_ANALYSIS_FRAMEWORK.md)

Different peak-finding algorithms have characteristic biases:
- **Direct minimum**: Fast but noisy (1.18 px bias)
- **Centroid**: Robust but high bias (11.42 px, sensitive to asymmetry)
- **Polynomial**: Balanced (2.06 px bias)
- **Spline**: Good accuracy (1.71 px bias)

**Correction:** `True_position = Measured_position - Bias(depth, FWHM, asymmetry)`

---

## Implementation Roadmap

### Phase 1: Data Collection ✅
- [x] Collect spectral data (S-mode + P-mode)
- [x] Build transmission analysis pipeline
- [x] Characterize algorithm bias
- [ ] Collect 4-channel dataset across sensor states

### Phase 2: Feature Engineering (Current)
- [ ] Implement optics-related features (intensity, slope, noise)
- [ ] Implement SPR-related features (depth, position, FWHM)
- [ ] Add multi-channel correlation analysis
- [ ] Validate feature extraction

### Phase 3: Classification
- [ ] Build rule-based classifier (optics vs SPR)
- [ ] Train supervised ML model
- [ ] Integrate with FMEA tracker
- [ ] Add UI status indicators

### Phase 4: Deployment
- [ ] Real-time processing (<10 ms)
- [ ] User alert system
- [ ] Field validation
- [ ] Continuous learning

---

## Performance Targets

| Metric | Target | Current Status |
|--------|--------|----------------|
| Processing time per spectrum | <10 ms | ✅ Algorithms tested |
| Peak tracking precision | <100 px P2P | ⏳ With bias correction |
| Optics vs SPR classification accuracy | >90% | 📝 Strategy documented |
| False positive rate (binding as error) | <5% | 📝 Rules defined |

---

## Cross-References

### Related Documentation

- `Affilabs.core beta/CALIBRATION_MASTER.md` - Calibration flow, S-mode/P-mode QC
- `utils/led_health_monitor.py` - LED degradation tracking (optics monitoring)
- `core/fmea_integration.py` - Failure mode logging
- `tools/spectral_quality_analyzer.py` - Feature extraction implementation
- `ML_MONITORING_OPTICS_VS_SPR_QUICK_REF.md` - Quick reference guide (root directory)

---

## Intellectual Property

**Proprietary Elements:**
1. Algorithm bias correction formulas
2. Adaptive method selection logic
3. Physics-informed validation models
4. Dual-mode (S+P) analysis strategy
5. Multi-channel consistency analysis for optics/SPR separation

**Patent Opportunities:**
- Method for SPR quality assessment using dual-polarization
- Adaptive peak-finding with bias correction
- Physics-informed ML for consumable quality classification
- Multi-channel diagnostics for biosensor systems

---

## Contact

**For questions about:**
- ML framework: See SPECTRAL_ML_ANALYSIS_FRAMEWORK.md
- Live monitoring: See LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md
- Implementation: Review integration examples in fmea_integration.py

---

**Last Updated:** November 23, 2025
**Status:** Documentation complete, implementation in progress
