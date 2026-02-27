# Affilabs.core v2.0.5 — Hardware Compatibility

**Last Updated:** February 24, 2026

---

## Supported Instruments

### Primary Target: P4SPR

| Component | Model | Status |
|-----------|-------|--------|
| **Instrument** | P4SPR (4-channel Surface Plasmon Resonance) | **Fully supported** |
| **Injection** | Manual syringe injection | **Fully supported** |
| **Channels** | 4 independent fluidic channels (A, B, C, D) | **Fully supported** |
| **Controller** | PicoP4SPR | **Fully supported** |

### Compatible: P4PRO + AffiPump

| Component | Model | Status |
|-----------|-------|--------|
| **Instrument** | P4PRO (4-channel with automated fluidics) | **Compatible** — basic injection works |
| **Pump** | AffiPump (external Tecan/Cavro syringe pump) | **Compatible** — basic commands work |
| **Valve** | 6-port rotary valve (controller-actuated) | **Compatible** |
| **Channels** | 4 optical channels; 2 fluidic pairs per cycle (AC or BD) | **Compatible** |

> **Note:** Full P4PRO semi-automated protocol suite is planned for v3.0.

### Compatible: P4PROPLUS

| Component | Model | Status |
|-----------|-------|--------|
| **Instrument** | P4PROPLUS (with built-in peristaltic pumps) | **Compatible** — pump commands work |
| **Pumps** | Internal peristaltic (dispense only, preset flow rates) | **Compatible** |

> **Note:** Full P4PROPLUS workflow orchestration is planned for v3.0.

### Legacy (End-of-Life)

| Model | Status |
|-------|--------|
| EzSPR | Code present, not actively tested (<5 units in field) |
| KNX2 | Code present, not actively tested (<5 units in field) |

---

## Supported Spectrometers

| Spectrometer | Manufacturer | Status | Notes |
|-------------|-------------|--------|-------|
| **Flame-T** | Ocean Insight (formerly Ocean Optics) | **Primary** — recommended for all new systems | ~2048 pixels, spectral range 350–1000 nm |
| **USB4000** | Ocean Insight (formerly Ocean Optics) | **Supported** | Legacy detector; functional but Flame-T preferred |

Other Ocean Insight or third-party spectrometers are **not supported**.

### Spectrometer Driver

| Driver | Required For | Installation |
|--------|-------------|-------------|
| **WinUSB** (via Zadig) | Both Flame-T and USB4000 | See [Installation Guide](INSTALLATION_GUIDE.md) |

> **Important:** The spectrometer must use the **WinUSB** driver, not the default Ocean Optics driver. Install via Zadig (bundled with the installer).

---

## Controller Firmware

| Firmware Version | Status | Features |
|-----------------|--------|----------|
| **V2.4** | **Recommended** | Full CYCLE_SYNC acquisition mode, all LED/servo commands |
| V2.2 | Supported | EVENT_RANK fallback mode (reduced timing precision) |
| < V2.2 | Not supported | Contact Affinite Instruments for upgrade |

### Firmware ID Strings

| Controller | Firmware ID | `ctrl_type` |
|-----------|------------|-------------|
| P4SPR | `PicoP4SPR` | `"PicoP4SPR"` |
| P4PRO | `PicoP4PRO` or detected by `ctrl_type` | `"PicoP4PRO"` |
| P4PROPLUS | Contains `p4proplus` in firmware string | `"PicoP4PRO"` + pump flag |

---

## Operating Environment

| Condition | Specification |
|-----------|--------------|
| **Operating temperature** | 15–25 °C (optimal) ; 0–40 °C (functional) |
| **Storage temperature** | 0–50 °C |
| **Humidity** | 10–90% non-condensing |
| **Warm-up time** | 30 minutes recommended for best baseline stability |

---

## Software Requirements

| Requirement | Specification |
|------------|--------------|
| **Operating System** | Windows 10 (build 19041+) or Windows 11, 64-bit |
| **RAM** | 8 GB minimum, 16 GB recommended |
| **Disk** | 2 GB free (5 GB recommended for data) |
| **Display** | 1366 × 768 minimum, 1920 × 1080 recommended |
| **USB** | 2× USB ports (spectrometer + controller) |

> macOS and Linux are **not supported**.

---

## Optical Specifications

| Parameter | Value |
|-----------|-------|
| **SPR method** | Lensless spectral SPR (Kretschmann configuration) |
| **Interrogation** | Wavelength (spectral), not angular |
| **SPR-active window** | 560–720 nm |
| **Light source** | 4× white LEDs (channels A, B, C, D) — time-multiplexed, sequential |
| **Polarization** | Servo polarizer (P-pol for SPR, S-pol for reference) |
| **Sensor** | Gold-coated glass chip |
| **Signal unit** | nm (resonance wavelength shift) |
| **Typical dip width** | 20–40 nm FWHM |

---

## Support

For hardware compatibility questions:

- **Email:** info@affiniteinstruments.com
- **Firmware updates:** Contact Affinite Instruments with your device serial number

---

**© 2026 Affinite Instruments Inc.**
