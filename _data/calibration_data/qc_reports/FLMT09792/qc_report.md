---
serial: FLMT09792
device_type: PicoP4SPR
detector_model: Flame-T
status: in-house
qc_date: 2026-02-28
technician: ""
provisioning_pc: ""
calibration_file: device_FLMT09792_20260228.json
qc_pass: null
---

# QC Report — FLMT09792

## Device Identity

| Field | Value |
|-------|-------|
| Serial number | FLMT09792 |
| Device type | PicoP4SPR |
| Detector model | Flame-T |
| QC date | 2026-02-28 |
| Technician | — |
| Provisioning PC | — |

---

## 1. Optical Calibration (from calibration JSON)

| Parameter | Value | Pass? |
|-----------|-------|-------|
| Calibration date | 2026-02-28 | ✅ |
| Calibration success | false | ❌ |
| Polarizer type | — | — |
| S-position (PWM) | — | — |
| P-position (PWM) | — | — |
| S/P ratio | — | — |

> **Note:** Calibration failed during provisioning. Polarizer was initially misclassified as CIRCULAR due to a dark_current threshold error — fixed in `calibrate_polarizer.py`. Re-run calibration after fix is applied.

---

## 2. SPR Performance (Au sensor, PBS running buffer)

> All values in **RU** (355 RU = 1 nm). Measured over a 5-minute stable baseline window.

| Metric | Measured | Spec | Pass? |
|--------|----------|------|-------|
| Drift (RU/5 min) | — | < 50 RU | — |
| Noise (RU std) | — | < 10 RU | — |
| Resolution (3 × noise, RU) | — | < 30 RU | — |

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
| **PASS / FAIL** | PENDING |
| Reason (if FAIL) | Calibration failed at provisioning |
| Action taken | Bug fixed in calibrate_polarizer.py — re-run required |
| Ready to ship | No — Korea distributor demo unit, in-house |

---

## 5. Sign-off

| Role | Name | Date |
|------|------|------|
| QC Technician | — | — |
| Reviewer | — | — |

---

## Notes

<!-- Free-form notes: any anomalies, retests, observations -->
- Korea distributor demo unit with barrel polarizer and OWW LEDs (P4SPR 2.0).
- Previously paired with ST00012 Phase Photonics controller — detector extracted and re-provisioned as standalone Flame-T unit 2026-02-28.
- Calibration bug: polarizer misclassified as CIRCULAR due to dark_current threshold error — fixed in calibrate_polarizer.py.
- Full re-calibration required before this unit can be shipped.
