---
serial: SERIALXXX
device_type: PicoP4SPR
detector_model: Flame-T
status: in-house
qc_date: YYYY-MM-DD
technician: ""
provisioning_pc: ""
calibration_file: device_SERIALXXX_YYYYMMDD.json
qc_pass: null
---

# QC Report — SERIALXXX

## Device Identity

| Field | Value |
|-------|-------|
| Serial number | SERIALXXX |
| Device type | PicoP4SPR |
| Detector model | Flame-T |
| QC date | YYYY-MM-DD |
| Technician | — |
| Provisioning PC | — |

---

## 1. Optical Calibration (from calibration JSON)

| Parameter | Value | Pass? |
|-----------|-------|-------|
| Calibration date | — | — |
| Calibration success | — | — |
| Polarizer type | — | — |
| S-position (PWM) | — | — |
| P-position (PWM) | — | — |
| S/P ratio | — | — |

> **Spec:** Polarizer type must be `LINEAR`. S/P ratio ≥ 3.0.

---

## 2. SPR Performance (Au sensor, PBS running buffer)

> All values in **RU** (355 RU = 1 nm). Measured over a 5-minute stable baseline window.

| Metric | Measured | Spec | Pass? |
|--------|----------|------|-------|
| Drift (RU/5 min) | — | < 50 RU | — |
| Noise (RU std) | — | < 10 RU | — |
| Resolution (3 × noise, RU) | — | < 30 RU | — |

**Calculation notes:**
- **Drift** = max − min of the 5-min baseline window (worst-case linear drift in RU)
- **Noise** = standard deviation of the same window (high-frequency noise floor)
- **Resolution** = 3 × noise (smallest detectable binding event, signal-to-noise ≥ 3)

---

## 3. Sensorgram Photos

> Place image files in `photos/` subfolder next to this report.
> Supported formats: PNG, JPG. Naming convention: `SERIALXXX_YYYYMMDD_description.png`

### Baseline window (5 min, used for drift/noise measurement)

![Baseline sensorgram](photos/baseline.png)

### Full QC run (if applicable)

![Full QC sensorgram](photos/full_run.png)

### Hardware photos (optional)

| Description | File |
|-------------|------|
| Front panel | `photos/front.jpg` |
| Fiber connection | `photos/fiber.jpg` |
| Flow cell | `photos/flowcell.jpg` |

---

## 4. Overall QC Decision

| Result | — |
|--------|---|
| **PASS / FAIL** | — |
| Reason (if FAIL) | — |
| Action taken | — |
| Ready to ship | — |

---

## 5. Sign-off

| Role | Name | Date |
|------|------|------|
| QC Technician | — | — |
| Reviewer | — | — |

---

## Notes

<!-- Free-form notes: any anomalies, retests, observations -->

