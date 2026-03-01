# OEM Calibration FRS
## Factory Device Provisioning — Complete Workflow

**Version:** 2.0 (rewritten 2026-02-28 — replaces stale afterglow doc)
**Audience:** Factory / OEM / Service personnel
**Entry point:** `scripts/provisioning/oem_calibrate.py`
**Source files:**
- `scripts/provisioning/oem_calibrate.py` — CLI orchestrator
- `affilabs/core/oem_model_training.py` — Phase 1b LED model training
- `calibrations/servo_polarizer/calibrate_polarizer.py` — Phase 1a servo cal
- `affilabs/core/calibration_orchestrator.py` — Phase 2 startup cal
- `affilabs/utils/device_configuration.py` — device config R/W
- `affilabs/utils/oem_calibration_tool.py` — DeviceProfileManager (save profile + device_config)

---

## 1. When to Run OEM Calibration

Run `oem_calibrate.py` on every new device before shipment, and after hardware replacement:

| Trigger | What to run |
|---------|-------------|
| New device assembly | Full run (both phases) |
| Controller replacement | Full run |
| Spectrometer replacement | Full run |
| LED PCB replacement | `--skip-phase2` to redo servo + LED model; then full run |
| Servo/polarizer replacement | Full run (servo cal is Phase 1a) |
| Fiber replacement | Phase 2 only (`--skip-oem-model`) |
| Calibration data corrupted | Full run |

---

## 2. Prerequisites

- Controller (PicoP4SPR V2.4+) connected via USB — enumerated as COM port
- Spectrometer (Flame-T or USB4000) connected via USB
- Optical path fully assembled: fiber seated in SMA port, LED PCB facing prism, polarizer barrel installed
- `device_config.json` for the serial exists at `affilabs/config/devices/{SERIAL}/device_config.json` (created from template when device is provisioned)
- venv active: `.venv\Scripts\activate`

---

## 3. Running

```bash
# Standard: full calibration (both phases)
.venv/Scripts/python.exe scripts/provisioning/oem_calibrate.py

# Phase 1 only (servo + LED model; skip startup cal)
.venv/Scripts/python.exe scripts/provisioning/oem_calibrate.py --skip-phase2

# Phase 2 only (LED model + startup cal already exists)
.venv/Scripts/python.exe scripts/provisioning/oem_calibrate.py --skip-oem-model

# Force serial (if auto-detect picks wrong device)
.venv/Scripts/python.exe scripts/provisioning/oem_calibrate.py --serial FLMT10979
```

Exit codes: `0` = success, `1` = hardware not found, `2` = Phase 1 failed, `3` = Phase 2 failed, `4` = --skip-oem-model but no servo positions.

---

## 4. Full Workflow — Phase by Phase

### Phase 1a — Servo Polarizer Calibration
**Source:** `calibrations/servo_polarizer/calibrate_polarizer.py` → `run_servo_calibration_from_hardware_mgr()`
**Duration:** 2–5 minutes
**Applies to:** All devices with servo polarizer (P4SPR, P4PRO, EZSPR)

#### Stage 1: Bidirectional sweep
- Sets LED intensity to 20% (auto-reduces to 5%/2%/1% if saturated)
- Sweeps servo across full range: forward `[1, 65, 128, 191, 255]` then backward `[255, 223, 159, 96, 32, 1]`
- At each position: measures mean of top-20 pixel values (noise-robust)
- Detects whether servo is physically moving (`servo_moved` flag)

#### Stage 2: Polarizer type detection
Classifies as **BARREL** or **CIRCULAR** based on intensity profile:

| Type | Characteristic | Detection |
|------|---------------|-----------|
| BARREL | 2 bright windows + extinction regions near dark current | `min_signal < dark × 3`, dynamic range > 3.5× |
| CIRCULAR | All positions above dark threshold | No extinction region |

BARREL geometry: S-window (stronger) and P-window (weaker) separated by ~60–100 PWM (≈42–70°). Dark "walls" between and behind windows.

#### Stage 3: Refine positions
- Scans ±10 PWM around each detected window center in 3-PWM steps
- S metric: mean intensity (want max light throughput)
- P metric: min in SPR ROI 570–680 nm (want minimum = resonance position)
- Finds stable range: positions within 1% of peak
- Optimal position = center of stable range

#### Validation
```
Separation = abs(s_pwm - p_pwm)
BARREL: must be 60–120° (60–170 PWM). Fails otherwise.
```
If primary P fails, tries `alternate_p` (±90 PWM offset).

#### Outputs written
- `calibrations/active/{SERIAL}/device_profile.json` — polarizer results
- `affilabs/config/devices/{SERIAL}/device_config.json` — hardware section updated:
  - `servo_s_position`, `servo_p_position` (PWM integers)
- EEPROM write attempted (non-fatal if it fails — JSON is source of truth)

---

### Phase 1b — LED Response Model Training
**Source:** `affilabs/core/oem_model_training.py` → `train_led_model()`
**Duration:** 5–15 minutes depending on device sensitivity
**Prerequisites:** Servo at S-position (Phase 1a must complete first)

#### What it measures
For each LED channel (A, B, C, D) at each integration time:
- Ramps intensity through a set of levels
- At each level: measures `corrected_counts = raw_peak − dark_counts[time_ms]`
- Stops at first saturation
- Fits: `counts = slope × intensity` (linear through origin, dark-subtracted)
- Stores `slope` per (LED, time_ms) — the model

#### Normal device path
Integration times: `[10, 20, 30, 45, 60]ms`
Base intensities: `[30, 60, 90, 120, 150]` (scaled down at longer times to avoid saturation)

| time_ms | intensities used |
|---------|-----------------|
| 10 | [30, 60, 90, 120, 150] |
| 20 | [20, 40, 60, 80, 100] |
| 30 | [24, 48, 72, 96, 120] |
| 45 | [20, 40, 60, 80, 100] |
| 60 | [15, 30, 45, 60, 75] |

#### Ultra-sensitive device auto-detection
If any LED saturates at intensity ≤ 60 at 10ms, the device is flagged as ultra-sensitive:
- Restarts training with integration times: `[5, 10, 15]ms`
- Uses intensities: `[10, 20, 30, 40, 60]`
- Dark current for these times is pre-measured at startup (no extra time cost)
- `ultra_sensitive = True` written to `led_model.json` and `device_config.json hardware.ultra_sensitive`

#### Adaptive intermediate collection
If exactly 1 data point before saturation at a given time_ms, tries 3 intermediate intensity levels between last good and saturation point to get a 2nd point for the linear fit. This maximises the usable slope range.

#### Validation
All 4 LEDs must have a slope entry for every integration time in the set. Any missing entry raises `ModelTrainingError`.

#### Outputs written
- `calibrations/active/{SERIAL}/led_model.json` — primary model (used by main app)
- `led_calibration_official/spr_calibration/data/led_calibration_3stage_{timestamp}.json` — timestamped archive
- `affilabs/config/devices/{SERIAL}/device_config.json` — `hardware.ultra_sensitive` updated

##### led_model.json structure
```json
{
  "detector_serial": "FLMT09792",
  "timestamp": "20260228_173826",
  "model_type": "3-stage-linear",
  "model_equation": "counts = slope_10ms × intensity × (time_ms / 10)",
  "integration_times": [5, 10, 15],
  "dark_counts_per_time": {"5": 2964.7, "10": 2976.9, "15": 2986.6, ...},
  "led_models": {
    "A": [{"time_ms": 5, "slope": 379.3}, {"time_ms": 10, "slope": 758.4}, {"time_ms": 15, "slope": 1138.0}],
    "B": [...],
    "C": [...],
    "D": [...]
  },
  "training_method": "automatic_oem_workflow",
  "detector_wait_ms": 50,
  "ultra_sensitive": true,
  "led_type": "OWW"
}
```

---

### Phase 2 — Startup Calibration
**Source:** `affilabs/core/calibration_orchestrator.py` → `run_startup_calibration()`
**Duration:** 3–8 minutes
**Prerequisites:** Phase 1 complete, servo positions in device_config.json

This is the same function called by the main app on every startup. Running it here constitutes factory calibration.

#### Steps
1. Load LED model from `calibrations/active/{SERIAL}/led_model.json`
2. Read servo S/P positions from device_config → sync to EEPROM → move servo to S
3. **Pre-convergence polarizer check:** all 4 LEDs @ 5%, 5ms — signal must exceed 3% of detector range. Fail-fast if blocking detected.
4. **S-mode LED convergence:** proportional control loop adjusts per-LED intensity to reach 85% of detector target. Convergence engine uses LED model to predict starting point.
5. **S-pol reference capture:** captures reference spectra at converged intensities — used as baseline for all subsequent P/S ratio calculations.
6. Move servo to P position.
7. **P-mode LED convergence:** same proportional control, same 85% target.
8. **Dark spectrum capture.**
9. QC validation: FWHM, SNR, P/S ratio checks.
10. Write `calibrations/active/{SERIAL}/startup_config.json`
11. Update `device_config.json` calibration section (integration_time_ms, led_intensity_a–d, dates).

#### Polarizer blocking detection
If max signal across all LEDs and channels < 3% of detector range after convergence:
```
POLARIZER BLOCKING DETECTED
Device config servo positions: S={s_pos}, P={p_pos} are INCORRECT
```
This means servo positions don't correspond to a transmission window. Root causes:
1. **Optical path not assembled** (fiber disconnected, chip not seated) — most common on new devices
2. **Wrong servo positions** (servo cal found positions without fiber connected)

Fix: verify optical assembly, clear servo positions to null, re-run full OEM cal.

---

## 5. Outputs Summary

| File | Written by | Purpose |
|------|-----------|---------|
| `affilabs/config/devices/{S}/device_config.json` | Phase 1a, 1b, 2 | Single source of truth for all device config |
| `calibrations/active/{S}/device_profile.json` | Phase 1a | Polarizer cal results (S/P positions, ratio, type) |
| `calibrations/active/{S}/led_model.json` | Phase 1b | LED response model (slopes per time per LED) |
| `calibrations/active/{S}/startup_config.json` | Phase 2 | LED intensities + S-pol reference spectra |
| `_data/calibration_data/device_{S}_{date}.json` | Post-Phase 2 | Calibration record for audit/registry |
| `_data/calibration_data/device_registry.json` | Post-Phase 2 | Auto-adds device if not already present |
| `led_calibration_official/spr_calibration/data/led_calibration_3stage_{ts}.json` | Phase 1b | Timestamped archive |

---

## 6. device_config.json — Fields Written by OEM Cal

```json
{
  "hardware": {
    "servo_s_position":         int,    // Phase 1a — S-window PWM
    "servo_p_position":         int,    // Phase 1a — P-window PWM
    "ultra_sensitive":          bool,   // Phase 1b — true if [5,10,15]ms path used
    "controller_firmware_version": str  // Set manually or auto-detected
  },
  "calibration": {
    "polarizer_calibration_date": ISO,  // Phase 1a
    "integration_time_ms":      float,  // Phase 2
    "led_intensity_a/b/c/d":    int,    // Phase 2
    "s_mode_calibration_date":  ISO,    // Phase 2
    "p_mode_calibration_date":  ISO     // Phase 2
  },
  "polarizer": {
    "s_position":               int,
    "p_position":               int,
    "sp_ratio":                 float,
    "polarizer_type":           "BARREL" | "CIRCULAR",
    "method":                   "servo_calibration_barrel_detection",
    "led_intensity_used":       "5%",
    "s_intensity":              float,
    "p_intensity":              float,
    "s_stable_range":           [min, max],
    "p_stable_range":           [min, max],
    "angular_separation_deg":   float,
    "calibration_date":         ISO
  },
  "calibration_date":           ISO     // Phase 2 completion
}
```

Fields that remain null until their phase runs:
- `servo_s/p_position` → null until Phase 1a
- `integration_time_ms`, `led_intensity_*` → null until Phase 2
- `ultra_sensitive` → false (default); overwritten by Phase 1b

---

## 7. Device Registry

After a successful run, `_data/calibration_data/device_registry.json` is updated. If the serial is already present (from device creation), the existing entry is preserved. If new, a minimal entry is added:
```json
"FLMT10979": {
  "serial": "FLMT10979",
  "device_type": "PicoP4SPR",
  "detector_model": "Flame-T",
  "status": "in-house",
  "added_date": "2026-02-28"
}
```
Always fill in `customer`, `order.invoice`, `shipped_date` manually before shipment.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "Controller not found" | Pico in REPL/bootloader mode | Re-flash V2.4 firmware, wait for COM port |
| "Detector not found" | USB driver not loaded | Unplug/replug, check OmniDriver installed |
| Phase 1a: servo not moving | Old firmware (<V2.1) | Update firmware |
| Phase 1a: SATURATED at 1% | Fiber too close to LEDs | Adjust fiber distance or use ND filter |
| Phase 1b: ModelTrainingError at 10ms | Ultra-sensitive + saturation at I=30 | Fixed in v2.0.5 (time_ms >= 10 guard) |
| Phase 2: POLARIZER BLOCKING | Optical path not assembled | Check fiber, chip seating; clear servo positions to null; re-run |
| Phase 2: POLARIZER BLOCKING | Wrong servo positions (cal ran without fiber) | Same fix |
| Phase 2: convergence fails after 50+ iterations | LED PCB weak or dirty prism | Clean prism, check LED PCB |
| Any phase: `insufficient data` | Ultra-sensitive device on wrong path | Should auto-correct; if not, check time_ms threshold in oem_model_training.py:270 |

---

## 9. LED Type Codes

| Code | Full name | Hardware |
|------|-----------|---------|
| `OWW` | Osram Warm White | Current production (default) |
| `LCW` | Luminus Cool White | Legacy — do not use for new devices |

Always use `OWW` for new devices. The `led_type` field in device_config, led_model.json, and device_profile.json must all match.

---

## 10. Post-Calibration Checklist

After `oem_calibrate.py` completes successfully:

- [ ] Open `affilabs/config/devices/{SERIAL}/device_config.json` — verify servo positions and LED intensities are non-null
- [ ] Open `calibrations/active/{SERIAL}/led_model.json` — verify all 4 LEDs have 3 slope entries, slopes are > 100
- [ ] Open `_data/calibration_data/device_registry.json` — fill in customer name, country, invoice
- [ ] Run main app with device connected — verify live acquisition starts without calibration errors
- [ ] If `ml_training_include: true`, retrain models: `python tools/ml_training/train_all_models.py`
