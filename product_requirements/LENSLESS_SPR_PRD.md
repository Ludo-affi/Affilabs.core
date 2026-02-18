# Lensless SPR Technology — PRD

**Product**: Lensless SPR — next-generation optical platform
**Status**: Planning
**Owner**: Lucia / Hardware + Software Team
**Last Updated**: 2026-02-18

---

## Vision

A miniaturized, low-cost SPR platform that eliminates the conventional lens-based optical path. Enables portable, wearable, or point-of-care SPR sensing without sacrificing sensitivity.

---

## Problem Statement

Current SPR instruments (including P4SPR) require:
- Precision optics (lenses, prisms, polarizers)
- Large form factor
- Complex alignment and calibration
- High per-unit manufacturing cost

Lensless SPR eliminates most optics by placing the detector directly in the near-field of the sensor — dramatically shrinking the instrument while maintaining nanometer-level sensitivity.

---

## Technology Overview

### Principle
- Direct illumination of the SPR sensor without intermediate lenses
- Near-field diffraction pattern captured by a CMOS image sensor
- Computational reconstruction of SPR signal from raw diffraction data

### Key Differences from Current Platform

| Feature | P4SPR (current) | Lensless SPR |
|---------|----------------|--------------|
| Optics | Prism + lenses + polarizer | None (or minimal) |
| Detector | Spectrometer (USB4000/Flame-T) | CMOS image sensor |
| Form factor | Benchtop | Portable / wearable |
| Cost | High | Low |
| Calibration | Complex (servo + LED) | Software-only |
| Channels | 4 (A, B, C, D) | TBD |
| Signal processing | Spectral centroid | Image reconstruction |

---

## Requirements

### Hardware

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 1 | CMOS sensor integration (OV2640 or equivalent) | High | [ ] |
| 2 | Compact LED illumination (no prism) | High | [ ] |
| 3 | Microfluidic flow cell compatible with near-field geometry | High | [ ] |
| 4 | USB or BLE connectivity to host | Medium | [ ] |
| 5 | Battery-powered operation (portable mode) | Low | [ ] |

### Software (Affilabs.core integration)

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 6 | New HAL driver for CMOS image sensor | High | [ ] |
| 7 | Image acquisition pipeline (raw frames → diffraction pattern) | High | [ ] |
| 8 | Computational SPR reconstruction algorithm | High | [ ] |
| 9 | Detector profile for lensless device | Medium | [ ] |
| 10 | Calibration workflow (software-only, no servo) | Medium | [ ] |
| 11 | UI: display 2D diffraction image alongside sensorgram | Medium | [ ] |
| 12 | Export: include raw image frames in Excel output | Low | [ ] |

### Signal Processing

| # | Requirement | Priority | Status |
|---|-------------|----------|--------|
| 13 | Diffraction pattern → SPR angle extraction | High | [ ] |
| 14 | Baseline correction for image drift | High | [ ] |
| 15 | Multi-channel extraction from single image (if applicable) | Medium | [ ] |
| 16 | Noise model for CMOS sensor (dark current, shot noise) | Medium | [ ] |

---

## Architecture (Planned)

```
CMOS Sensor (USB/BLE)
    ↓
LenslessAcquisitionManager (new)
    ↓ raw frames (2D arrays)
ImagePreprocessor
    → dark frame subtraction
    → flat-field correction
    ↓
DiffractionReconstructionPipeline (new)
    → FFT / holographic reconstruction
    → SPR angle extraction
    ↓
Standard SpectrumProcessor interface (compatible with existing)
    ↓
Sensogram + UI (existing, reused)
```

**Integration point**: Implement `LenslessAcquisitionManager` as a drop-in replacement for `DataAcquisitionManager`, emitting the same `spectrum_acquired` signal shape so downstream processing is unchanged.

---

## Phases

### Phase 1: Feasibility (Q2 2026)
- [ ] Prototype optical geometry (bench test)
- [ ] Choose CMOS sensor (resolution, noise, frame rate)
- [ ] Validate SPR signal extraction from diffraction pattern
- [ ] Baseline sensitivity benchmarking vs P4SPR

### Phase 2: Software Integration (Q3 2026)
- [ ] HAL driver for CMOS sensor
- [ ] Image acquisition pipeline
- [ ] SPR reconstruction algorithm (v1)
- [ ] Basic UI for image display
- [ ] Calibration workflow design

### Phase 3: Hardware Prototype (Q4 2026)
- [ ] PCB design for compact form factor
- [ ] Microfluidic flow cell integration
- [ ] Firmware (if embedded MCU needed)
- [ ] Full software integration with Affilabs.core

### Phase 4: Validation (Q1 2027)
- [ ] Sensitivity comparison vs P4SPR
- [ ] Multi-sample reproducibility
- [ ] User testing (usability)
- [ ] Regulatory assessment (if POC use case)

---

## Open Questions

1. **Multi-channel support**: Can a single CMOS capture multiple fluidic channels simultaneously?
2. **Polarization**: Does lensless geometry require polarization control? If so, how?
3. **Coherence**: Is coherent (laser) or incoherent (LED) illumination preferred?
4. **Resolution**: What pixel pitch and resolution is needed for nm-level sensitivity?
5. **Connectivity**: USB (lab use) vs BLE (portable) — or both?
6. **Software architecture**: Extend Affilabs.core or create separate Affilabs.lite?

---

## Success Metrics

- SPR sensitivity: ≤1 nm wavelength shift detection (match current platform)
- Form factor: <100 cm³ (vs current ~1000 cm³)
- Cost per unit: <20% of current P4SPR cost
- Calibration time: <5 min (vs current 10-15 min)
- Time-to-data: <30 min from unboxing
