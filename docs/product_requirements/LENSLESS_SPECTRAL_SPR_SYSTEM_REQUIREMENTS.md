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
11. [Potential Improvements & Future Directions](#11-potential-improvements--future-directions)
12. [References](#12-references)
13. [Validation & Testing](#13-validation--testing)

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

### What This System Is Not

A key aspect of correctly specifying software requirements is knowing which conventional SPR features are absent. The following components and capabilities are **not present** in this system:

| Absent feature | Conventional use | Why absent here |
|----------------|-----------------|-----------------|
| **Lens** | Focus beam to µm-scale spot; collimate or converge light along optical path | No lens anywhere in the optical path — LED light travels directly through polarizer → prism → fiber without any focusing element |
| **Mirror / reflective optics** | Redirect or fold the optical path; used in interferometers and some SPR configurations | Straight-through Kretschmann geometry; no mirrors required or present |
| **Temperature control** | Stabilize buffer/sensor temperature to suppress refractive index drift; required for accurate kinetic rate constants | Not implemented — no Peltier, no thermistor feedback loop, no software temperature control |
| **Imaging / camera** | Spatially resolve binding across sensor surface; multi-spot or array SPR | Not imaging — one bulk integrated signal per channel |
| **Goniometer / angle scan** | Rotate sample or beam to find resonance angle; required for angular SPR | Not angle-based — wavelength is scanned instead; prism geometry is fixed |
| **Laser** | Monochromatic, collimated source for angular SPR (e.g., 633 nm or 785 nm) | White LED broadband source used instead; enables spectral interrogation |
| **PMT (photomultiplier tube)** | High-gain single-point light detection; used with lasers or monochromators | CCD spectrometer replaces PMT + monochromator; all wavelengths detected simultaneously |
| **Camera / CCD imaging array** | 2D spatial mapping of SPR signal | 1D CCD linear array (spectrometer) only — no spatial information |

**Software consequences:** None of the above require software support. The software must not expose temperature control UI, goniometer commands, camera feeds, or angular scan pipelines. Any future integration of temperature sensing would require new hardware and a new software module.

### What the Lensless Design Enables

The absence of lenses and mirrors is not purely a cost trade-off — it creates a geometrically open optical path above the sensor chip. Because no focusing optic sits between the LED and the prism, the **top surface of the sensor chip (the buffer-facing side) is freely accessible**.

This makes it possible to perform **top-side spectroscopy** alongside the SPR measurement:

- The same broadband white LED light that drives SPR through the prism can also illuminate the flow cell from above
- A fiber or detector positioned above the chip can measure **transmission, absorption, or scattering** from the sample in the flow cell
- This enables complementary optical measurements (e.g., colorimetric assays, turbidity, nanoparticle absorbance) without a separate instrument

> **Current status:** Top-side spectroscopy is not implemented in software. The hardware geometry supports it. This capability is documented here as a future development path enabled by the lensless architecture.

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
Optical fiber (100 or 200 µm core, multimode)
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
│  Optical Fiber (multimode, 100 or 200 µm core)                  │
│  Direct coupling (no lenses)                                    │
│  1-2 meters length (controller to spectrometer)                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  Spectrometer (Ocean Optics Flame-T or USB4000)                 │
│  Detector: 3648-pixel CCD (Flame-T and USB4000)                │
│  Wavelength range: ~441–773 nm (SPR ROI: 560–720 nm)           │
│  Integration time: 1–60 ms (optimized per setup)               │
│  Readout: USB connection to PC (libseabreeze/Ocean Direct)     │
└─────────────────────────────────────────────────────────────────┘
```

### LED System Details

#### Channels

- **4 channels (A, B, C, D)** — each LED illuminates one flow cell region
- **Identical white LEDs** — same part number across channels; spectral profile is nominally identical, with minor unit-to-unit variation corrected by per-channel calibration

#### Control Modes

The software must support the following LED control modes:

| Mode | Description | Status |
|------|-------------|--------|
| **Single channel** | Fire one LED (A, B, C, or D) at a programmable intensity (0–255); all others off | ✅ Implemented |
| **All off** | All LEDs off — used for dark frame acquisition and detector baseline capture | ✅ Implemented |
| **All on (diagnostic)** | All 4 LEDs at full intensity simultaneously — **not valid for SPR acquisition** (single spectrometer cannot distinguish channels); diagnostic/setup use only | ✅ Implemented |
| **Sequential — standard** | A → B → C → D, cycled continuously; default SPR acquisition mode | ✅ Implemented |
| **Sequential — custom pattern** | User-defined subset and order (e.g., A → C only, or B → D); used for paired-channel mode (P4PRO AC/BD pairs) or partial-channel experiments | ✅ Implemented |

#### Timing Requirements

The LED timing chain is the fundamental rate constraint of the system:

| Timing Parameter | Value | Notes |
|-----------------|-------|-------|
| **Minimum per-LED dwell time** | 250 ms | Integration time + LED settle + servo travel + readout |
| **Full cycle time (4-channel)** | ~1 s | 4 × ~250 ms = 1000 ms = 1 Hz per channel (`CYCLE_TIME = 1.0`) |
| **LED settle time** | 45 ms | `DETECTOR_WAIT_MS` — after intensity change; before spectrum acquisition |
| **Servo settle time** | 100 ms | After polarizer rotation; included within the 250 ms per-LED budget |
| **Dark frame overhead** | ~100 ms | Acquired once per session at calibration; not per-cycle |

**Critical timing constraint:** The software must never reduce per-LED dwell below 250 ms. Integration time selection (1–60 ms) must leave sufficient headroom within the 250 ms window for servo rotation and spectrometer readout. Violating this produces underexposed spectra and invalid P/S ratios.

**Standard sequential acquisition cycle:**
1. Fire LED A → Rotate to P-pol → Read spectrum → Rotate to S-pol → Read spectrum
2. Fire LED B → (repeat)
3. Fire LED C → (repeat)
4. Fire LED D → (repeat)
5. Return to LED A (next acquisition cycle)

**Full cycle time:** ~1 second for all 4 channels × 2 polarizations = 8 spectra per cycle (`CYCLE_TIME = 1.0`)
**Acquisition rate:** 1 Hz per channel (each channel updated once per full cycle)

**No simultaneous multi-channel acquisition** — hardware limitation of single-spectrometer design.

#### Overnight / Long-Duration Operation Mode

The software must support unattended acquisition sessions lasting hours to overnight without user intervention:

| Requirement | Specification | Status |
|-------------|--------------|--------|
| **No hard session time limit** | Acquisition runs until manually stopped or storage is exhausted | ✅ Implemented |
| **Continuous LED cycling** | LEDs cycle without interruption for the entire session duration | ✅ Implemented |
| **LED drift compensation** | Calibration-derived boost factors (per-channel) correct for slow intensity drift over hours | ✅ Implemented (afterglow correction + LED model) |
| **Storage monitoring** | Recording system must warn before disk space is exhausted | ⚠️ Partial |
| **Degraded signal detection** | If SNR drops below threshold for N consecutive frames, system flags degraded quality; no automatic in-run LED recalibration | ⚠️ Partial (QC flags raised; no auto-recal) |
| **USB reconnect recovery** | If spectrometer or controller USB drops during a long run, software must attempt reconnect and resume | ❌ Not implemented |

#### LED Spectral Profile System

All 4 LEDs are nominally identical white broadband sources, but calibration measures and normalizes unit-to-unit and channel-to-channel spectral variation:

| Concept | Description |
|---------|-------------|
| **Raw LED profile** | Actual measured spectral intensity of each LED (400–900 nm) in detector counts — captured during LED calibration |
| **Target spectral profile** | The desired ("ideal") spectral shape in the 560–720 nm SPR window — defines what the corrected spectrum should look like |
| **LED boost correction** | Per-channel, per-wavelength multiplier that shapes the raw LED spectrum toward the target profile |
| **Channel-to-channel normalization** | Ensures all 4 channels produce comparable signal levels so sensorgrams are directly comparable across A, B, C, D |

Boost correction factors are computed during LED calibration and stored in `config/devices/{serial}/calibration_checkpoint.pkl`. They are applied in `SpectrumPreprocessor` before P/S ratio calculation. The target profile is fixed at calibration time and does not change mid-run.

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
| **Pixels** | 3648 | 3648 |
| **Wavelength range** | ~441–773 nm | ~441–773 nm |
| **SPR ROI** | 560–720 nm | 560–720 nm |
| **Integration time** | 1–60 ms | 1–60 ms |
| **Dark noise** | ~3500 counts baseline | ~3500 counts baseline |
| **Saturation level** | 65,535 counts (16-bit) | 65,535 counts (16-bit) |
| **Connection** | USB (WinUSB / SeaBreeze driver) | USB (WinUSB / SeaBreeze driver) |
| **API** | python-seabreeze | python-seabreeze |

**Detector profile files:** `detector_profiles/ocean_optics_flame_t.json`, `detector_profiles/ocean_optics_usb4000.json`

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

### LED Software Control Requirements

| Requirement | Specification | Implementation |
|-------------|--------------|----------------|
| **Per-channel intensity control** | Independent 0–255 intensity per LED | `PicoP4SPRHAL.set_led_intensity(channel, value)` |
| **Mode switching** | All modes (single / all-off / all-on / sequential) switchable without app restart | `DataAcquisitionManager` |
| **Custom acquisition pattern** | Active channel subset (e.g., A+C only) configurable via settings | `CHANNEL_INDICES` in `settings.py` |
| **Timing floor enforcement** | Per-LED dwell ≥ 250 ms enforced in software | Acquisition loop in `data_acquisition_manager.py` |
| **Overnight stability** | LED intensity stable ±5% over 8-hour run after thermal settle | Afterglow calibration + LED boost correction |
| **Target spectral profile** | Per-channel boost factors applied to match target spectrum in 560–720 nm window | `SpectrumPreprocessor`, stored in calibration checkpoint |
| **LED failure detection** | LED-off detected via `led_detected` quality flag; acquisition continues with flag raised (not auto-stopped) | `QualityValidator` |

### Batch LED Commands

Setting all 4 LED intensities one channel at a time via sequential serial commands adds latency and risks frame-to-frame jitter. The batch command collapses all 4 intensity assignments into a single serial transaction, reducing LED setup overhead from ~4 × 15 ms → ~15 ms total.

| Concept | Description |
|---------|-------------|
| **`set_batch_intensities(a, b, c, d)`** | Single firmware command sets all 4 channel intensities atomically; response `b"1"` confirms acceptance |
| **Serial wire format** | `lb<mode><default><ch_a><int_a><ch_b><int_b>...\n` (binary protocol, Pico controllers only) |
| **Pre-enable prerequisite (P4PRO)** | P4PRO firmware requires `enable_multi_led()` (`lm:A,B,C,D` command) **before** `set_batch_intensities()` will take effect; P4SPR does not require this step |
| **Sequential fallback** | For controllers that do not support the batch command (PicoEZSPR), `CtrlLEDAdapter.execute_batch()` automatically falls back to sequential `set_intensity()` calls |
| **Brightness setup per batch** | Each batch command carries per-channel intensities independently — channels do not share a single value; used to maintain calibrated unequal intensities across A/B/C/D |
| **`execute_batch(commands)`** | Higher-level HAL method accepting a list of `LEDCommand` objects; dispatches to batch or sequential path based on controller capability via `"Pico" in controller_type` check |

**Implementation:** `CtrlLEDAdapter.execute_batch()` in `affilabs/utils/hal/adapters.py`; `set_batch_intensities()` in `PicoP4SPRAdapter` and `PicoP4PROAdapter` in `affilabs/utils/hal/controller_hal.py`.

### LED Rank Sequence (Firmware-Controlled)

For LED calibration (finding relative brightness across channels), the software needs to flash each LED individually and read a spectrum. On V2.4+ firmware, this is offloaded to the firmware to achieve tighter timing than Python-controlled sequencing allows.

| Aspect | Detail |
|--------|--------|
| **Method** | `led_rank_sequence(test_intensity, settling_ms, dark_ms, timeout_s)` |
| **Mechanism** | Firmware sequences all 4 LEDs internally with `settling_ms` dwell (default 45 ms) and `dark_ms` dark gap (default 5 ms); signals Python via serial `READY` / `READ` / `DONE` events |
| **Python role** | Generator: yields `(channel, signal)` tuples; reads spectrometer when `signal == "READ"` |
| **Timing advantage** | Firmware controls LED timing directly from hardware clock — eliminates Python scheduling jitter (~1–5 ms) that accumulates over 4 channels |
| **Batch rank calibration** | After rank sequence, LED intensities are adjusted channel-by-channel to bring all 4 into alignment (ranked weakest → strongest, boost weakest to match strongest) |
| **Controller support** | PicoP4SPR V2.4+ only — PicoEZSPR and PicoP4PRO return `None` from `led_rank_sequence()`; software falls back to Python-controlled sequential mode |

**Implementation:** `ControllerHAL.led_rank_sequence()` (Protocol); `PicoP4SPRAdapter.led_rank_sequence()` in `controller_hal.py`; used in `calibration_service.py`.

### Cross-Controller Compatibility

The LED control layer must present a **uniform interface** regardless of which controller hardware is connected. Capability differences are resolved at the HAL adapter layer — upstream code (DAM, calibration service) never checks controller type directly.

| Feature | PicoP4SPR (primary) | PicoEZSPR (legacy) | PicoP4PRO |
|---------|--------------------|--------------------|-----------|
| **LED channels** | 4 (A, B, C, D) | 2 (A, B) | 4 (A, B, C, D) |
| **`set_batch_intensities()`** | ✅ Native batch command | ❌ Sequential fallback (4 × single) | ✅ Native batch command |
| **Pre-enable required** | ❌ Not needed | ❌ Not needed | ✅ `enable_multi_led()` before batch |
| **`led_rank_sequence()`** | ✅ V2.4+ firmware | ❌ Not supported | ❌ Not supported |
| **Polarizer / servo** | ✅ Servo control | ❌ None | ✅ Servo control |
| **`get_all_led_intensities()`** | ✅ V1.1+ firmware | ⚠️ If supported | ⚠️ If supported |
| **HAL adapter class** | `PicoP4SPRAdapter` | `PicoEZSPRAdapter` | `PicoP4PROAdapter` |
| **Capability query** | `supports_batch_leds`, `supports_rank_sequence`, `supports_polarizer` | Same (return False) | Same |

**Single-LED communications (non-batch path):** For one-off intensity changes (e.g., live brightness edit from Settings tab), the software uses `ctrl.set_intensity(channel, value)` — a single serial round-trip (~15 ms) emitting the confirmed `"1"` response. This is distinct from the batch path and always safe to call on any controller.

**Capability guards:** Use `hal.supports_batch_leds` and `hal.supports_rank_sequence` property checks — never string-match against controller class name in business logic. `CtrlLEDAdapter.execute_batch()` and calibration code use these properties internally.

**Implementation:** `ControllerHAL` Protocol + three adapter classes in `affilabs/utils/hal/controller_hal.py`; `CtrlLEDAdapter` in `affilabs/utils/hal/adapters.py`.

### Timing Optimization & Computing Overhead

LED acquisition timing has a fixed hardware floor and a variable software overhead that must be minimized to sustain the target acquisition rate.

#### Timing Budget per LED Channel

```
Per-LED dwell = 250 ms total
  ├── LED_ON_TIME_MS = 225 ms  (software-settable; actual LED-on window)
  ├── Serial command overhead  = ~15 ms  (turn_on_channel or set_intensity RTT)
  ├── Python scheduling jitter = ±2–5 ms (threading, OS scheduler)
  └── Headroom / guard margin  = ~10 ms
```

`LED_ON_TIME_MS = 225` (defined in `settings.py`); combined with ~25 ms serial + scheduling overhead = ~250 ms effective per-channel dwell.

#### Acquisition Mode & Overhead Breakdown

| Component | Overhead | Notes |
|-----------|----------|-------|
| **Serial `turn_on_channel()` RTT** | ~15 ms | USB serial latency (pyserial + WinUSB) |
| **Spectrometer readout** | 1–60 ms | Integration time (software-enforced ceiling: 60 ms) |
| **Servo rotation + settle** | ~100 ms | Per polarization switch; included in dwell budget |
| **Python queue put/get** | < 1 ms | Non-blocking; never limits throughput |
| **Spectrum processing** (downstream) | 2–10 ms | Runs in separate thread; does not block DAM loop |
| **`gc.disable()`** | — | GC disabled in `data_acquisition_manager.py` to prevent multi-ms GC pauses during acquisition loop |
| **DEBUG logging overhead** | 1–2 ms/cycle | Console logging at DEBUG adds latency; use INFO in production |
| **Total 4-channel cycle** | ~1,000–1,400 ms | → 0.7–1 Hz full cycle (all 4 channels, 2 polarizations each) |

#### Cycle Sync Mode vs Event Rank Mode

Two acquisition timing architectures are supported, selectable via `USE_CYCLE_SYNC` in `settings.py`:

| Mode | Mechanism | Benefit | Use Case |
|------|-----------|---------|----------|
| **CYCLE_SYNC** (V2.4 firmware, default) | Firmware controls LED cycle timing; Python syncs to firmware-generated events | Tighter timing, less Python jitter, higher sustained rate | Normal operation on V2.4+ hardware |
| **EVENT_RANK** (fallback) | Python drives all LED timing directly; firmware is passive | Compatible with older firmware; simpler | Legacy devices, debugging |

**Implementation:** `DataAcquisitionManager` (`affilabs/managers/data_acquisition_manager.py`); `gc.disable()` call at module level; `USE_CYCLE_SYNC` flag in `settings/settings.py`.

### Brightness Control, Querying & Mapping

#### Per-Channel Brightness Setup

LED brightness is set independently per channel and stored at two levels:

| Source | Contents | Used For |
|--------|---------|---------|
| **Calibration checkpoint** | Calibrated P-mode final brightness per channel (A/B/C/D) | Restored on app restart; loaded into Settings tab |
| **`config/devices/{serial}/device_config.json`** | Last-saved intensity per channel | Hardware config backup |
| **Live settings tab** | User-editable fields (0–255 per channel) | Immediate override; emits `led_brightness_changed` signal → `_on_led_brightness_changed()` in `main.py` → `ctrl.set_intensity()` |

On startup, brightness is read from calibration checkpoint first (P-mode calibrated value); if unavailable, queried from hardware via `get_all_led_intensities()` (V1.1+ firmware); if hardware not connected, used from config file.

#### Brightness Mapping (Calibration-Derived)

During LED calibration, raw LED brightness across all 4 channels is characterized and a **brightness map** is produced:

1. All 4 LEDs fire at test intensity (e.g., 128/255) via rank sequence or sequential mode
2. Peak signal count is measured per channel
3. Channels are ranked weakest → strongest
4. Weakest channel becomes the **reference** (intensity = 255 max)
5. Stronger channels are scaled down to match: `mapped_intensity = int(ref_peak / ch_peak × 255)`
6. Mapped intensities are stored in calibration checkpoint and applied on every subsequent run

This produces a per-channel intensity map (`{a: 255, b: 210, c: 198, d: 243}` for example) that equalizes signal levels across channels **without software post-correction**, keeping the P/S ratio calculation clean.

#### Brightness Query

`get_all_led_intensities()` reads current firmware intensity register for all 4 channels in one serial round-trip (V1.1+ firmware only). Used to:
- Verify batch command took effect
- Populate Settings tab on hardware connect
- Cross-check calibrated vs actual intensity after a long run

Returns `dict[str, int]` `{'a': ..., 'b': ..., 'c': ..., 'd': ...}` or `None` if not supported.

**Implementation:** `_on_led_brightness_changed()` in `main.py`; `_build_led_brightness_settings()` in `affilabs/sidebar_tabs/AL_settings_builder.py`; `get_all_led_intensities()` + brightness mapping in `affilabs/services/calibration_service.py`; `_settings_mixin.py` (`_load_led_brightness_from_calibration()`).

---

### LED Engineering History — Tried & Abandoned

This section records approaches that were investigated, prototyped, or partially built but ultimately abandoned or deprioritized. Preserved here to avoid re-investigating dead ends.

#### ❌ Afterglow Correction (Abandoned — timing and comms delays)

**What it was:** White LED phosphors have a slow decay tail (afterglow) after the LED turns off. In a time-multiplexed system, the previous LED's phosphor still emits faint light when the next LED fires. The correction model characterized this as a per-channel exponential decay:

```
signal(t) = baseline + amplitude × exp(-t / τ)
```

A full characterization tool was built (`tools/led_afterglow_integration_time_model.py`, ~40–50 min runtime) that measured each channel's `τ` across multiple integration times (e.g., 20–100 ms), producing integration-time-dependent lookup tables. The correction was cross-channel:
- Channel A is corrected for D's afterglow
- Channel B is corrected for A's afterglow
- Channel C is corrected for B's afterglow
- Channel D is corrected for C's afterglow

**Why it failed:**
1. **Timing was the bigger problem.** The actual per-LED dwell (250 ms) is long relative to the phosphor `τ` (~5–30 ms typical). By the time the next LED fires and the spectrometer integrates, the afterglow contribution is negligible relative to signal noise. The correction was applying sub-count-level adjustments.
2. **USB serial communication delays swamped the timing model.** The correction depended on knowing the exact elapsed time between LED-off and spectrometer readout start. USB serial RTT (~15 ms) + Python scheduler jitter (±2–5 ms) made the actual delay unpredictable enough to introduce more error than the correction removed.
3. **Integration time coupling.** The correction required a separate `τ` lookup per integration time — if the user changed integration time mid-session, the correction became invalid and re-characterization (40–50 min) was required.

**Current status:** `optical_calibration.json` and the `AfterglowCorrection` class still exist as an OEM-gated feature but are not used in standard acquisition. `run_afterglow_calibration.py` remains in `affilabs/` but is not invoked in normal flow. Can be revisited if a detector with slower phosphor decay is adopted.

---

#### ⚠️ Firmware-Controlled Independent LED Operation (Partial — watchdog and command conflicts)

**What it was:** The idea was to offload the LED sequencing loop to the firmware entirely — the controller runs the A→B→C→D cycle autonomously at hardware clock precision, with the PC acting purely as a data consumer. This would eliminate Python scheduler jitter from the acquisition loop entirely and allow sub-250 ms per-channel timing.

The firmware-side `led_rank_sequence()` (V2.4+) is a limited implementation of this concept, used for calibration only (one-shot, not continuous).

**Why it hasn't been fully implemented:**
1. **Watchdog conflicts.** Firmware watchdog timers expect regular command traffic (keepalive pings) from the host PC. A fully autonomous LED loop that doesn't need PC commands during a cycle triggered watchdog resets on some hardware revisions.
2. **Command collision.** During firmware-autonomous operation, any host command (servo move, intensity change, query) that arrives mid-cycle could conflict with the LED sequencing state machine, causing garbled responses or dropped cycles.
3. **Sync signal protocol not finalized.** The PC needs a reliable signal per channel indicating "LED is stable, start integrating now." The `READY`/`READ`/`DONE` protocol used in `led_rank_sequence()` works for short calibration sequences but has not been stress-tested for hours-long continuous operation (timing drift, missed signals).
4. **P4PRO doesn't support it.** Only PicoP4SPR V2.4+ has the rank sequence command; P4PRO has no equivalent.

**Current status:** Could eventually work with firmware revisions. Priority items before attempting: (1) define keepalive framing that coexists with autonomous LED loop, (2) harden `READY`/`READ`/`DONE` protocol with sequence numbers and timeout recovery, (3) validate on both PicoP4SPR and (if supported) P4PRO. Not scheduled.

---

### LED Serial Command Reference (All Controllers)

Complete map of firmware serial commands for LED control across supported controllers. All commands terminate with `\n`; all responses are ASCII, terminated with `\r\n`.

#### PicoP4SPR (Primary — V1.x / V2.x / V2.4+)

| Command | Wire Format | Response | Description |
|---------|------------|----------|-------------|
| **Turn on channel** | `la\n`, `lb\n`, `lc\n`, `ld\n` | `1` | Turn on single LED (a/b/c/d); intensity must be pre-set |
| **Turn off all** | `loff\n` | `1` | Turn off all LED channels |
| **Set intensity (single)** | `la<NNN>\n` (e.g., `la200\n`) | `1` | Set intensity for channel A (0–255, zero-padded to 3 digits) |
| **Set batch intensities** | `lb<mode>255<ch><NNN>...\n` | `1` | Set all channel intensities in one command (e.g., `lbp255a200b210c198d243\n`) |
| **Query all intensities** | `li\n` | `a:NNN,b:NNN,c:NNN,d:NNN` | Read current intensity registers (V1.1+) |
| **LED rank sequence** | `lr<intensity><settling_ms><dark_ms>\n` | Streaming: `READY`, `READ`, `DONE` per channel | Firmware-driven rank calibration sequence (V2.4+) |
| **All LEDs on (diagnostic)** | `lall<NNN>\n` | `1` | All 4 LEDs on simultaneously at given intensity; not for SPR acquisition |

#### PicoEZSPR (Legacy — 2 channels only)

| Command | Wire Format | Response | Description |
|---------|------------|----------|-------------|
| **Turn on channel** | `la\n`, `lb\n` | `1` | 2 channels only (A, B) |
| **Turn off all** | `loff\n` | `1` | Turn off both channels |
| **Set intensity (single)** | `la<NNN>\n`, `lb<NNN>\n` | `1` | Set intensity per channel |
| **Batch intensities** | ❌ Not supported | — | Falls back to sequential `set_intensity()` calls in HAL |
| **LED rank sequence** | ❌ Not supported | — | Returns `None` from adapter |
| **Query all intensities** | Device-dependent | — | Only if firmware supports `li` command |

#### PicoP4PRO

| Command | Wire Format | Response | Description |
|---------|------------|----------|-------------|
| **Multi-LED enable (required first)** | `lm:A,B,C,D\n` | `1` | Must be sent before any intensity or batch command will take effect |
| **Turn on channel** | `la\n`, `lb\n`, `lc\n`, `ld\n` | `1` | Turn on after enable |
| **Turn off all** | `loff\n` | `1` | Turn off all channels |
| **Set intensity (single)** | `la<NNN>\n` | `1` | Single-channel intensity |
| **Set batch intensities** | `lb<mode>255<ch><NNN>...\n` | `1` | Same format as P4SPR; **requires prior `lm:` enable** |
| **LED rank sequence** | ❌ Not supported | — | Returns `None` from adapter |
| **Query all intensities** | Device-dependent | — | Only if firmware supports `li` command |

> **Note:** Command formats are firmware-version-dependent. The formats above reflect the last-known working format as of v2.0.5. The `lb` batch format was verified in `_scratch/test_scripts/test_batch_acquisition.py` and `test_p4pro_led_batch.py`. Always verify against actual firmware response when updating firmware.

---

### Servo Polarizer Specifications

The servo polarizer sits in the optical path between the LED source and the prism. It is rotated by a digital servo (default: **HS-55MG**) to two discrete positions — P-polarization and S-polarization — and dwells at each long enough for the spectrometer to acquire a frame. The ratio of P to S transmission cancels LED drift and provides a stable SPR baseline.

#### 5.3.1 Servo Hardware & PWM Mapping

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Default servo model** | HS-55MG | Configurable in `device_config.json` |
| **Control signal** | PWM via controller firmware | 8-bit range 1–255 |
| **Physical range** | 5°–175° | Hard mechanical limits |
| **Degree conversion** | `degrees = 5 + (pwm / 255) × 170°` | Linear mapping across 170° span |
| **Position stored as** | PWM integer | `servo_s_position`, `servo_p_position` in `device_config.json` |
| **Settling time** | 100 ms (nominal) | 100–500 ms actual depending on travel distance |
| **EEPROM usage** | None at runtime | Positions loaded from JSON on startup; legacy `servo_get()` deleted |

#### 5.3.2 Servo Wire Commands (PicoP4SPR / PicoP4PRO)

| Step | Command | Format | Purpose |
|------|---------|--------|---------|
| 1 | `sv` | `sv<s_deg_3digit><p_deg_3digit>\n` | Load both S and P degree positions into servo RAM |
| 2a | `ss` | `ss\n` | Move servo to S position |
| 2b | `sp` | `sp\n` | Move servo to P position |

**Example:** S at PWM 120 → 85°, P at PWM 30 → 25° → sends `sv085025\n`, then `ss\n` or `sp\n`

> **Critical:** `sv` is a RAM-only write. It does **not** write to EEPROM. Positions must be re-sent after power cycle; the software reloads from `device_config.json` on every connect.

> **Fallback mode (`sv+sp`):** If Stage 1 calibration detects the servo is not physically moving (flat signal, std < 5, range < 10 counts), the system falls back to an alternate sweep using the `sv` + `sp` command pair directly to step P through the full 0–255 range while S is held fixed at 128.

#### 5.3.3 Polarizer Types

Two physical polarizer designs are in use across the instrument fleet. The software must auto-detect and handle both.

##### Barrel Polarizer

A cylindrical barrel that holds a linear polarizer film at a fixed orientation on the servo shaft. The barrel has opaque blocking material everywhere except **two narrow transmission windows** oriented 90° apart (P, S). When the servo positions the barrel outside a transmission window, essentially no light reaches the detector.

| Property | Value |
|----------|-------|
| **Transmission windows** | 2 (P and S), each ~10–15° wide |
| **Window separation** | ~90 PWM (~90°) — validated at 60–110 PWM tolerance |
| **Blocking regions** | Dark (near dark-current level) between windows |
| **P position** | Calibrated — stored as `servo_p_position` |
| **S position** | Calibrated — stored as `servo_s_position` |
| **Detection hallmark** | Dynamic range > 3.5×; some sweep positions at or below `dark_current × 3` |

##### Circular (Round) Polarizer

A continuously rotating polarizer disc mounted on the servo shaft. The film transmits at **every angle** but the polarization axis rotates with the disc. No blocking regions exist.

| Property | Value |
|----------|-------|
| **Transmission windows** | All positions transmit |
| **Window separation** | N/A — P = S + 90 PWM by mathematical rule |
| **Blocking regions** | None |
| **P position** | S + 90 PWM (derived, not measured) |
| **S position** | Coarse max-transmission peak from sweep (highest signal = S-pol) |
| **Detection hallmark** | All positions above `dark_current × 6`; low dynamic range (< 3.5×) |

> **Config/UI terminology mismatch:** The code and `device_config.json` store `"barrel"` and `"round"`. The device configuration UI dialog displays `"barrel"` and `"circle"`. These refer to the same physical types. The discrepancy is cosmetic and should be resolved in a future UI audit.

#### 5.3.4 Auto-Detection Algorithm (Run at Calibration)

Polarizer type detection is fully automatic and runs as part of the servo calibration workflow (`calibrations/servo_polarizer/calibrate_polarizer.py`).

**Stage 1 — Bidirectional Sweep**

Coarse sweep at 5 evenly spaced positions in both directions to characterize the full transmission range and catch hysteresis:

- Forward: PWM positions `[1, 65, 128, 191, 255]`
- Backward: PWM positions `[255, 223, 159, 96, 32, 1]`

Flat-signal guard: if `std < 5` and `range < 10` counts across all positions → servo did not move → switch to `sv+sp` fallback mode (Stage 3 converging scan).

**Stage 2 — Type Classification (`detect_polarizer_type()`)**

| Threshold | Formula | Purpose |
|-----------|---------|---------|
| `DARK_THRESHOLD` | `dark_current × 3` | Upper bound for "near-dark" classification |
| `BRIGHT_THRESHOLD` | `dark_current × 6` | Minimum for "clearly transmitting" |

| Condition | Type | Action |
|-----------|------|--------|
| All sweep positions above `BRIGHT_THRESHOLD` AND dynamic range < 3.5× | **CIRCULAR** | S = argmax of forward sweep; P = S + 90 PWM (mod 256) |
| Some positions below `DARK_THRESHOLD` AND dynamic range ≥ 3.5× | **BARREL** | Identify 2 bright peaks; assign P and S to each; validate separation 60–110 PWM |

**Stage 3 — Position Refinement**

±10 PWM sweep around each coarse window center to find precise P and S peak positions. Results are saved to `device_config.json` as `servo_s_position` and `servo_p_position`.

#### 5.3.5 Config Storage

```jsonc
// config/devices/{serial}/device_config.json
{
  "polarizer_type": "barrel",       // "barrel" or "round"
  "servo_model": "HS-55MG",
  "servo_s_position": 120,          // PWM integer, set by calibration
  "servo_p_position": 30            // PWM integer, set by calibration
}
```

Positions are `null` / `None` before first calibration. Software blocks acquisition if positions are unset.

**Implementation refs:** `calibrations/servo_polarizer/calibrate_polarizer.py`, `PicoP4SPRAdapter.set_mode()` and `servo_move_raw_pwm()` in `affilabs/utils/hal/controller_hal.py`, `affilabs/utils/device_configuration.py`, diagnostic tool `find_barrel_windows.py`

**Calibration data:** Stored in `config/devices/{serial}/device_config.json`

#### 5.3.6 When the Polarizer Moves (and Why)

The servo does **not** alternate between P and S on every acquisition frame. Movement happens at two distinct points only:

| Event | Direction | Why |
|-------|-----------|-----|
| **During calibration — S-ref capture** | → S position | Capture S-pol reference spectrum; stored in `CalibrationData.s_ref`; reused for every P/S ratio calculation during the session |
| **During calibration — dark capture** | Doesn't matter (LED off) | Dark current measurement; polarizer position is irrelevant |
| **Acquisition start** | → P position | Move once to P-pol; stay there for the entire acquisition session |
| **User-triggered toggle (UI)** | → opposite position | Manual inspection only; not part of normal measurement |
| **Calibration re-run** | → S, then back to P | Re-captures S-ref and returns to P for acquisition |

**Why stay in P-pol?** The S-pol reference is static — it was captured under controlled conditions at calibration time and serves as a per-pixel divisor for every subsequent P frame. Toggling the servo every frame would:
- Add 100–500 ms mechanical settle latency per half-cycle (halving throughput)
- Introduce jitter between the P and S frames (different LED intensities, different buffer conditions)
- Break the assumption that the S reference is captured at the same physical state as the calibration baseline

This is a deliberate architectural choice: **single reference, single move, session-persistent P-pol acquisition.**

**S-ref stability:** The S-pol reference is thermally and optically stable once captured. Because S-pol does not couple to surface plasmons, it is insensitive to binding events, buffer changes, or analyte injections. In practice, the S-ref captured at the start of a session remains valid for the entire session (hours of acquisition). Recalibration is needed only when a material hardware change occurs — new chip, unplugged fiber, significant LED intensity drift, or physical disturbance of the optical path. **There is no time limit on S-ref validity** within a continuous session.

---

### 5.4 Prism

The prism is the optical coupling element that enables SPR. It is made of **BK7 glass** (refractive index n ≈ 1.515 at 633 nm) and holds a gold-coated sensor chip pressed against its flat face.

Light enters the prism at a steep angle (total internal reflection geometry — Kretschmann configuration). At that angle, two things happen depending on polarization:

- **P-polarized light** (electric field parallel to the plane of incidence) can couple into the surface plasmon wave at the gold/buffer interface. When the resonance condition is met at a specific wavelength, energy is transferred from the light into the plasmon — that wavelength is strongly **absorbed/attenuated**, producing the characteristic SPR dip in the transmission spectrum.
- **S-polarized light** (electric field perpendicular to the plane of incidence) cannot couple to surface plasmons at this geometry. It reflects off the gold surface without interaction and exits through the fiber. This makes it an ideal intensity reference — it sees all the same LED and optical drift as P-pol but carries no SPR information.

The software has no direct interaction with the prism. It is a passive optical component. Software requirements arising from the prism:
- The SPR dip produced by a bare gold/buffer interface falls in the **560–720 nm** window — this drives the spectrometer wavelength range requirement.
- Binding events cause a **blue shift** (wavelength decrease) in the dip — signal extraction algorithms must search for this minimum correctly.
- If the sensor chip is absent, improperly seated, or dry, the SPR dip disappears or shifts anomalously — the software must recognize these failure modes during calibration QC.

---

### 5.5 Fiber Optic

The fiber carries transmitted light from the prism exit face to the spectrometer input slit. It is a **bifurcated bundle**: 4 input branches (one per LED channel / flow cell region) merge into a single output trunk that connects to the detector.

```
Channel A fiber branch ─┐
Channel B fiber branch ─┤
Channel C fiber branch ─┤─── single trunk ──→ Spectrometer slit
Channel D fiber branch ─┘
```

Only one LED fires at a time. When LED A is active, only Channel A's light travels through the A branch; the other branches are dark. Time-multiplexing ensures no optical crosstalk between channels.

#### Fiber Specifications

| Parameter | Option 1 | Option 2 |
|-----------|----------|----------|
| **Core diameter** | 200 µm | 100 µm |
| **Signal level** | Higher (more light collection) | Lower |
| **Spectral resolution** | Lower (larger entrance aperture) | Higher (smaller entrance aperture) |
| **Primary use** | Standard — most instruments | Higher-resolution applications |
| **Factory default** | ✅ 200 µm | — |

**Config key:** `optical_fiber_diameter_um` in `device_config.json` (100 or 200).

The fiber diameter affects the required LED intensity calibration target (200 µm needs less LED drive current to reach target counts) and influences spectral resolution seen by the spectrometer. The software reads this value at startup and uses it to inform LED calibration thresholds.

**Implementation ref:** `affilabs/utils/device_configuration.py` → `get_optical_fiber_diameter()`; `scripts/provisioning/factory_provision_device.py` (provisioning prompt)

---

### 5.6 Spectrometer (Detector)

The spectrometer converts the fiber output light into a digitized spectral array. It is a CCD-based diffraction grating spectrometer — no moving parts.

#### 5.6.1 Integration Time

Integration time is the duration for which the CCD collects photons before readout. It directly controls signal level and acquisition throughput.

| Parameter | Value |
|-----------|-------|
| **Minimum** | 1 ms |
| **Maximum** | 60 ms (software-enforced limit; prevents motion blur and LED drift artifacts) |
| **Recommended / calibration target** | 10 ms |
| **Step resolution (Flame-T)** | 2.5 ms |
| **Calibration target counts** | 50,000–55,000 counts (out of 65,535 max) |
| **Auto-calibration** | Software adjusts integration time iteratively to hit target counts; max 20 iterations |
| **Stored in** | `CalibrationData.integration_time` — reloaded at every acquisition start |

Longer integration time = more signal but slower per-LED frame rate. The 60 ms ceiling keeps the total 4-LED cycle under ~1 second.

#### 5.6.2 Sensitivity & Bit Depth

| Detector | ADC | Max counts | Dark noise (mean) | Dark noise (std) | Typical SNR |
|----------|-----|-----------|-------------------|-----------------|------------|
| **Ocean Optics Flame-T** | 16-bit | 65,535 | ~3,500 | ~50 | ~300:1 |
| **Ocean Optics USB4000** | 16-bit | 65,535 | ~3,500 | ~50 | ~300:1 |
| **Phase Photonics** | 12-bit | 4,095 | TBD | TBD | Lower |

Dark current is subtracted per-pixel during preprocessing (`SpectrumPreprocessor`). The 30-scan dark average captured at calibration is used for all subsequent dark subtractions.

#### 5.6.3 Spectral Bandwidth & Resolution

| Parameter | Flame-T / USB4000 | Phase Photonics |
|-----------|-------------------|-----------------|
| **Full detected range** | 441–773 nm | ~570–773 nm (min filtered at 570 nm) |
| **SPR analysis window** | 560–720 nm | 570–720 nm |
| **Pixel count** | 3,648 | 1,848 |
| **Grating** | 600 lines/mm | TBD |
| **Slit width** | 25 µm | TBD |
| **Approx. resolution** | ~0.09 nm/pixel | ~0.11 nm/pixel |
| **Pixels in SPR window** | ~1,591 | ~720 |

The SPR window (560–720 nm) is where the gold-film plasmon dip falls. Pixels outside this range are excluded from peak-finding. Phase Photonics units have a shorter effective range due to valid data starting at 570 nm.

#### 5.6.4 Suppliers

| Priority | Supplier | Models | Status |
|----------|----------|--------|--------|
| **Primary** | Ocean Optics (now Ocean Insight) | Flame-T, USB4000 | ✅ Production — all current instruments |
| **Backup** | Phase Photonics | Custom (SensorT series, serial prefix `ST`) | ⚠️ Legacy — limited fleet, no new provisioning |

Both are supported via a common `detector_factory.create_detector()` interface. Detection is by USB serial number prefix (`FLMT` = Flame-T, `USB4` = USB4000, `ST` = Phase Photonics).

#### 5.6.5 Communication Protocol

| Detector | Library / Driver | Transport |
|----------|-----------------|-----------|
| **Flame-T** | SeaBreeze (via `python-seabreeze`) — auto-detect string `FLMT`; USB VID `0x2457`, PID `0x1002` | USB |
| **USB4000** | SeaBreeze (via `python-seabreeze`) — auto-detect string `USB4`; USB VID `0x2457`, PID `0x1002` | USB |
| **Phase Photonics** | `SensorT.dll` via `FTD2xx` (FTDI D2XX driver); wrapped in `phase_photonics_api.py` | USB (FTDI) |

> **Isolation requirement:** Flame-T/USB4000 use `SpectrometerAPI` (3,648 or 3,700 pixel buffer); Phase Photonics uses `PhasePhotonicsAPI` (1,848 pixel buffer). These must **never share the same driver instance** — buffer size mismatch causes silent data corruption. `phase_photonics_wrapper.py` is kept strictly isolated.

**Suppressed warning:** `seabreeze.use has to be called` is suppressed at startup via `warnings.filterwarnings` — this is intentional.

#### 5.6.6 Onboard Memory & Averaging

| Detector | Hardware averaging | Software averaging |
|----------|-------------------|-------------------|
| **Flame-T** | ✅ Supported (onboard scan averaging up to N scans before USB readout) | ✅ Supported |
| **USB4000** | ✅ Supported | ✅ Supported |
| **Phase Photonics** | ❌ **BROKEN** — `usb_set_averaging()` ignores integration time; runs scans at ~1 ms regardless of configured integration time | ✅ Required — software loop only |

**Current approach:** Software averaging (Python loop, `num_scans` repeats, then `numpy.mean()`). Hardware averaging is not used — even for Flame-T/USB4000 — to keep driver paths identical and avoid the Phase Photonics bug causing silent under-exposure.

`num_scans` is set during LED calibration and stored in `CalibrationData.num_scans`. Typical value: 1–5 scans per polarization position per LED channel.

**Host-side buffer:** `SPECTRUM_QUEUE_SIZE = 200` (≈ 5 seconds at 40 Hz) — spectra are queued in a `queue.Queue` between the acquisition thread and the processing worker thread. This is host RAM, not detector memory.

**Implementation refs:** `affilabs/utils/phase_photonics_wrapper.py`, `affilabs/hardware/spectrometer_adapter.py`, `detector_profiles/ocean_optics_flame_t.json`, `detector_profiles/ocean_optics_usb4000.json`, `affilabs/utils/detector_factory.py`

---

### 5.7 Flow Cell & Sensor Chip

#### 5.7.1 Flow Cell Architecture

Each of the four optical channels (A, B, C, D) maps to an **independent fluidic flow cell** on the sensor chip. There is no shared fluidic path between channels and no cross-talk — each channel can carry a completely different sample, buffer, or ligand surface.

| Property | Value |
|----------|-------|
| **Channels** | 4 (A, B, C, D) |
| **Isolation** | Fully independent — no cross-channel fluidic connection |
| **Volume per cell** | ~1–5 µL (geometry-dependent) |
| **Illumination** | Each LED illuminates one flow cell region (~1 mm spot) |
| **Signal crosstalk** | None — sequential LED firing prevents optical cross-channel contamination |

**P4SPR:** All 4 channels are independently injectable via manual syringe. Each channel has its own inlet port.

**P4PRO / P4PROPLUS:** Channels are grouped into two fluidic pairs (AC and BD) by the 6-port rotary valve. Both channels in a pair receive the same sample simultaneously; to inject different samples, the operator runs two sequential injection cycles.

#### 5.7.2 Sensor Chip

The sensor chip is a glass substrate (~12 × 24 mm) coated with a thin gold film (~47–50 nm Au on 1–2 nm Cr adhesion layer). The chip sits flush against the prism flat face, optically coupled via refractive-index-matching immersion oil or optical contact. Binding chemistry (e.g., SAM carboxymethyl dextran, streptavidin, NiNTA) is applied on top of the gold by the end user or during chip preparation.

| Parameter | Spec |
|-----------|------|
| **Substrate** | Borosilicate glass |
| **Gold thickness** | ~47–50 nm (tuned for SPR at 560–720 nm) |
| **Adhesion layer** | 1–2 nm Cr |
| **Footprint** | ~12 × 24 mm (fits 4 flow cell regions) |
| **Coupling** | Index-matching oil or optical contact |
| **Regeneratable** | Yes — standard SPR chip chemistry applies |

**Software implication:** The chip ID can be logged to the `Metadata` sheet on export (key: `chip_id`). Chip type is not programmatically validated — it is the user's responsibility to use a chip with the correct gold thickness for this prism geometry.

---

### 5.8 Data Output Format

#### 5.8.1 Export Overview

At the end of a recording session (or on demand), the software exports a **single `.xlsx` workbook** containing all measurement data for that session. This is the canonical data format for the system.

**Key properties:**
- Single file per session — no fragmentation
- All data in one workbook (sensorgrams, cycles, flags, events, analysis, metadata, alignment)
- Must be importable by **TracerDrawer** (external kinetics analysis software) — this is a hard interoperability requirement
- Readable directly in Excel/LibreOffice Calc
- Compatible with GraphPad Prism, MATLAB, Python (openpyxl/pandas), Origin

**Implementation:** `affilabs/services/excel_exporter.py` → `ExcelExporter.export_to_excel()`  
**Library:** `openpyxl` via `pandas.ExcelWriter`

#### 5.8.2 Workbook Sheet Structure

| # | Sheet Name | Description | Key Columns |
|---|-----------|-------------|-------------|
| 1 | **Raw Data** | Long-format sensorgram — all channels, all time points | `elapsed`, `channel`, `wavelength_nm`, `pipeline`, ... |
| 2 | **Channel Data** or **Channels XY** | Wide-format per-channel — one time column per channel; or XY-paired format for TracerDrawer | `Time A (s)`, `Channel A (nm)`, `Time B (s)`, `Channel B (nm)`, ... |
| 3 | **Cycles** | Cycle annotation table — binding cycles, regeneration, blank, reference | `cycle_id`, `cycle_num`, `type`, `name`, `start_time`, `duration`, `concentration` |
| 4 | **Flags** | Manual/automated flags placed during acquisition | `flag_id`, `time`, `label`, `color`, `note` |
| 5 | **Events** | System event log — injections, valve switches, recording start/stop | `elapsed`, `timestamp`, `event` |
| 6 | **Analysis** | Kinetic analysis results (if run) — ka, kd, KD, Rmax | `measurement_id`, `channel`, `Ka`, `Kd`, `KD`, `Rmax` |
| 7 | **Metadata** | Session metadata — user, experiment name, chip ID, model | `key`, `value` pairs (e.g., `chip_id`, `user`, `temperature_c`) |
| 8 | **Alignment** | Edits-tab alignment settings — per-cycle time shifts and channel filters | `Cycle_Index`, `Channel_Filter`, `Time_Shift_s` |

> **Sheet 2 note:** If `channels_xy_dataframe` is provided at export time, the sheet is named **"Channels XY"** (TracerDrawer-compatible wide format). Otherwise it falls back to "Channel Data" (internal wide format). The "Channels XY" format is what TracerDrawer expects.

#### 5.8.3 TracerDrawer Compatibility (Hard Requirement)

TracerDrawer is an external SPR analysis tool used by customers for kinetic fitting. The export format **must** produce an Excel file that TracerDrawer can import without modification.

Requirements imposed by TracerDrawer compatibility:
- Sheet 2 must use the **"Channels XY"** format (time-paired wide format per channel)
- Column naming convention must match TracerDrawer's import parser (e.g., `Time A (s)`, `Channel A (nm)`)
- No merged cells, no header rows beyond row 1
- Numeric values must be plain floats (no formatted strings in data columns)

Non-compliance breaks TracerDrawer import silently — the file opens but data imports incorrectly.

#### 5.8.4 Cycles Sheet Schema

The `Cycles` sheet is the primary mechanism for recreating analysis context from a saved file. Each row is one cycle segment.

```
cycle_id   | cycle_num | type    | name     | start_time | duration | concentration | notes
1          | 1         | Bind    | IgG      | 120.0      | 300.0    | 100 nM        | ...
2          | 2         | Regen   | Glycine  | 420.0      | 60.0     | —             | pH 1.7
```

Cycle data is re-read from this sheet by `CYCLE_RECREATION_GUIDE.md`'s workflow:  
```python
df_cycles = pd.read_excel(excel_path, sheet_name='Cycles', engine='openpyxl')
```

#### 5.8.5 Metadata Sheet Keys

Standard keys written to Sheet 7:

| Key | Value |
|-----|-------|
| `user` | Active user profile name |
| `experiment` | Experiment name (from session dialog) |
| `chip_id` | Sensor chip identifier (user-entered) |
| `temperature_c` | Buffer temperature (if sensor present) |
| `model` | Instrument model (P4SPR / P4PRO / P4PROPLUS) |
| `firmware_version` | Controller firmware string |
| `session_start` | ISO 8601 timestamp of recording start |
| `session_end` | ISO 8601 timestamp of recording stop |
| `pipeline` | Active peak-finding pipeline (centroid / fourier / etc.) |

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
| **Integration time** | 1–60 ms | Outside range — detector saturation or too dim |

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
| **Single-channel LED control** | ✅ Complete | `PicoP4SPRHAL`, `data_acquisition_manager.py` |
| **All-off mode (dark acquisition)** | ✅ Complete | Dark frame at calibration; `SpectrumPreprocessor` |
| **All-on diagnostic mode** | ✅ Complete | LED controller command; blocked from SPR acquisition path |
| **Sequential custom pattern (channel subset)** | ✅ Complete | `CHANNEL_INDICES` config in `settings.py` |
| **250 ms per-LED timing floor** | ✅ Complete | Acquisition loop timing; cycle sync mode |
| **Overnight / continuous operation** | ✅ Complete (partial) | No session time limit; LED drift compensated; USB reconnect recovery not yet implemented |
| **LED boost correction (target spectral profile)** | ✅ Complete | `SpectrumPreprocessor`; stored in calibration checkpoint |
| **LED failure detection** | ✅ Complete | `led_detected` quality flag in `QualityValidator` |
| **Batch LED command (`set_batch_intensities`)** | ✅ Complete | `PicoP4SPRAdapter`, `PicoP4PROAdapter`; sequential fallback in `PicoEZSPRAdapter` |
| **`execute_batch()` with capability dispatch** | ✅ Complete | `CtrlLEDAdapter.execute_batch()` in `adapters.py` |
| **P4PRO pre-enable (`enable_multi_led`)** | ✅ Complete | `PicoP4PROAdapter.enable_multi_led()` |
| **LED rank sequence (firmware V2.4+)** | ✅ Complete | `PicoP4SPRAdapter.led_rank_sequence()`; Python-controlled fallback for older firmware |
| **Cross-controller compatibility (P4SPR / EZSPR / P4PRO)** | ✅ Complete | Three HAL adapters in `controller_hal.py`; capability properties (`supports_batch_leds`, `supports_rank_sequence`) |
| **Single-LED communications (`set_intensity`)** | ✅ Complete | All adapters; used for live Settings tab edits |
| **`get_all_led_intensities()` query** | ✅ Complete | V1.1+ firmware; used at connect + Settings tab population |
| **Brightness mapping (calibration-derived intensity equalization)** | ✅ Complete | Rank → scale → store in calibration checkpoint; `calibration_service.py` |
| **Per-channel brightness setup per batch** | ✅ Complete | Independent A/B/C/D values in every batch command |
| **Brightness Settings UI (live edit, 0–255 per channel)** | ✅ Complete | `AL_settings_builder.py`, `led_brightness_changed` signal, `_on_led_brightness_changed()` in `main.py` |
| **Cycle sync mode (firmware-timed acquisition)** | ✅ Complete | `USE_CYCLE_SYNC` flag; `DataAcquisitionManager` |
| **Event rank fallback mode** | ✅ Complete | Python-driven timing when `USE_CYCLE_SYNC = False` or V2.4 firmware unavailable |
| **GC disable during acquisition** | ✅ Complete | `gc.disable()` in `data_acquisition_manager.py` |

### 🔄 Known Limitations

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| **Single spectrometer = sequential channel readout** | 4-channel acquisition takes 1–2 sec | Not fixable (hardware) — use cycle sync timing |
| **Broad spectral dip (~30 nm FWHM)** | Lower resolution than angular SPR | Fourier/Consensus pipelines compensate |
| **Lensless = large spot size (~1 mm)** | No spatial imaging, single-spot per channel | Multi-channel independence compensates |
| **Manual injection (P4SPR)** | ±15 sec inter-channel timing skew | P4PRO/PLUS solve with automated injection |
| **Afterglow (LED phosphor decay)** | Creates temporal bias if integration time changes | OEM calibration corrects (optional feature) |

---

## 11. Potential Improvements & Future Directions

These are hardware and architecture changes that would meaningfully expand the system's capabilities. None are currently implemented. Each item notes the primary constraint that would need to be solved.

### Temperature Control

| Aspect | Detail |
|--------|--------|
| **What** | Active temperature regulation of the prism / flow cell region |
| **Why** | Buffer refractive index (RI) is temperature-dependent (~1.5 × 10⁻⁴ RIU/°C for water). Uncontrolled temperature drift produces apparent SPR signal drift indistinguishable from binding. Currently impacts long kinetic runs and low-concentration measurements. |
| **Implementation path** | Peltier element + NTC thermistor at prism holder; PID loop in firmware; temperature readback channel to software; new UI widget for setpoint and live readout |
| **Software requirement** | New `TemperatureController` service; temperature logged alongside sensorgram data; calibration gated on temperature stability |

---

### Shift LED Spectral Profile Further Into Red

| Aspect | Detail |
|--------|--------|
| **What** | Replace current white broadband LEDs with sources weighted toward 650–850 nm |
| **Why** | The SPR dip for gold moves to longer wavelengths as the medium RI increases (protein layers, thick coatings, high-RI buffers). Red-shifted LEDs improve SNR in the 700–850 nm window that the current white LEDs under-illuminate. Also reduces shot noise contribution from the blue/green portion of the spectrum that falls outside the SPR window. |
| **Constraint** | LED PCB redesign; new LED characterization and boost calibration; spectrometer range must extend to ~850 nm (USB4000 partially covers this) |

---

### Faster LED Switching — Eliminate Phosphor Afterglow

| Aspect | Detail |
|--------|--------|
| **What** | Replace white phosphor-converted LEDs with direct-emission narrowband LEDs (e.g., red/amber, ~620–700 nm) or monochromatic laser diodes |
| **Why** | White LEDs use a blue InGaN chip + yellow phosphor. The phosphor has a slow decay tail (τ ~ 5–30 ms). In time-multiplexed acquisition, this cross-contaminates channels (channel N+1 lit by channel N's phosphor) and prevents sub-250 ms per-channel timing. Direct-emission LEDs turn off in microseconds — no afterglow, no cross-channel contamination, no calibration correction needed. |
| **Constraint** | Narrowband sources reduce available signal; LED PCB redesign; may require different optical filtering; afterglow correction subsystem becomes unnecessary |
| **Unlocks** | Sub-100 ms per-channel timing, firmware-autonomous LED loop without timing floor constraints |

---

### 5 or 6 Channel Expansion

| Aspect | Detail |
|--------|--------|
| **What** | Expand from 4 LED channels (A–D) to 5 or 6 independent flow cell channels |
| **Why** | More flow cells per chip increases throughput — more analytes or more replicates per run without physically swapping chips. Academic / high-throughput screening use cases. |
| **Constraint** | Controller firmware LED count; fiber bundle redesign (4-branch → 5/6-branch); sensor chip geometry; per-channel calibration storage changes; UI channel labelling |
| **Software requirement** | `CHANNEL_INDICES` generalization; all per-channel data structures must be channel-count-agnostic rather than hard-coded to 4 |

---

### Always-On LEDs with Digital Mirror (DMD) Channel Selection

| Aspect | Detail |
|--------|--------|
| **What** | Run all LEDs continuously at full brightness; use a Digital Micromirror Device (DMD) or liquid-crystal spatial light modulator to steer light to one channel at a time without LED switching |
| **Why** | LED thermal equilibrium is reached faster and held more stably when LEDs are always on. Eliminates the LED turn-on transient and phosphor warm-up. Channel selection becomes electronic (µs switching) rather than mechanical (ms LED switching). Removes the fundamental throughput floor imposed by LED settle time. |
| **Constraint** | DMD cost and size; optical alignment complexity; significantly increased LED drive power (all 4 on simultaneously); heat management |
| **Unlocks** | kHz-rate channel switching; no afterglow (channels never actually off); separates LED stability from channel switching rate |

---

### Imaging Instead of Spectroscopy (Next-Generation Architecture)

| Aspect | Detail |
|--------|--------|
| **What** | Replace the fiber + point spectrometer with a 2D imaging detector (sCMOS or CCD camera); use a monochromatic laser or filtered LED source at fixed wavelength; detect SPR as a spatial dark spot or angle-shift across a 2D gold film |
| **Why** | Imaging SPR enables **spatial resolution** — hundreds to thousands of spots detected simultaneously on a single chip. This makes array-based binding assays (e.g., protein microarrays, DNA hybridization arrays) possible at high throughput. |
| **Trade-offs** | Loses spectral information; returns to being angle-based or wavelength-fixed; requires lens; loses the lensless simplicity; requires laser or monochromator; far more complex optical alignment; high-end camera cost |
| **Relationship to current system** | This would be a different product line, not an upgrade. The current lensless spectral architecture is incompatible with imaging SPR — they represent different fundamental design choices. |

---

## 12. References

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

## 13. Validation & Testing

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
