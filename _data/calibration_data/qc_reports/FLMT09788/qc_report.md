---
serial: FLMT09788
device_type: PicoP4SPR
detector_model: USB4000
status: shipped
qc_date: 2026-02-20
technician: ""
provisioning_pc: ""
calibration_file: device_FLMT09788_20260220.json
qc_pass: null
---

# QC Report — FLMT09788

## Device Identity

| Field | Value |
|-------|-------|
| Serial number | FLMT09788 |
| Device type | PicoP4SPR |
| Detector model | USB4000 |
| QC date | 2026-02-20 |
| Technician | — |
| Provisioning PC | — |

---

## 1. Optical Calibration (from calibration JSON)

| Parameter | Value | Pass? |
|-----------|-------|-------|
| Calibration date | 2026-02-20 | ✅ |
| Calibration success | true | ✅ |
| Polarizer type | BARREL | ✅ |
| S-position (PWM) | 133 | — |
| P-position (PWM) | 35 | — |
| S/P ratio | 2.38 | ⚠️ below 3.0 |

> **Spec:** Polarizer type must be `LINEAR` or `BARREL`. S/P ratio ≥ 3.0.
> S/P ratio 2.38 — note for review.

---

## 2. SPR Performance (Au sensor, PBS running buffer)

> All values in **RU** (355 RU = 1 nm). Measured over a 5-minute stable baseline window.

| Metric | Measured | Spec | Pass? |
|--------|----------|------|-------|
| Drift (RU/5 min) | — | < 50 RU | — |
| Noise (RU std) | — | < 10 RU | — |
| Resolution (3 × noise, RU) | — | < 30 RU | — |

**Calculation notes:**
- **Drift** = max − min of the 5-min baseline window
- **Noise** = standard deviation of the same window
- **Resolution** = 3 × noise

---

## 3. Sensorgram Photos

> Place image files in `photos/` subfolder next to this report.

### Baseline window (5 min, used for drift/noise measurement)

![Baseline sensorgram](photos/baseline.png)

### Full QC run (if applicable)

![Full QC sensorgram](photos/full_run.png)

---

## 4. Overall QC Decision

| Result | — |
|--------|---|
| **PASS / FAIL** | — |
| Reason (if FAIL) | — |
| Action taken | — |
| Ready to ship | Shipped 2026-02-20 to Amit Pandey (Switzerland), Invoice #1325 |

---

## 5. Sign-off

| Role | Name | Date |
|------|------|------|
| QC Technician | — | — |
| Reviewer | — | — |

---

## Notes

<!-- Free-form notes: any anomalies, retests, observations -->
- S/P ratio 2.38 is below the ≥3.0 spec threshold — document whether this was accepted and why.
- 9 calibration runs on record between 2025-12-17 and 2026-02-20 before final approval.
