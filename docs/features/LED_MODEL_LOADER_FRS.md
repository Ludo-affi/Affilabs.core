# LED Model Loader — Feature Reference Specification

**Source:** `affilabs/services/led_model_loader.py`
**Status:** Implemented (v2.0.5)
**Layer:** Layer 2 — Business / Services
**Depends on:** `affilabs/utils/resource_path.py`, `calibrations/active/{SERIAL}/led_model.json`

---

## 1. Purpose

Replaces iterative LED intensity search during startup calibration with a direct mathematical lookup using a pre-measured per-device LED response model.

**Before this system:** Calibration converged intensity by trial-and-error (measure → adjust → repeat) — slow and prone to overshoot.
**After this system:** Given a target count level and integration time, the required intensity is calculated in one step.

---

## 2. Model Equation

```
counts = slope_10ms × intensity × (time_ms / 10)
```

- `slope_10ms` — measured during OEM factory calibration (counts per intensity unit at 10ms)
- `intensity` — LED brightness value (0–255)
- `time_ms` — spectrometer integration time in milliseconds

This is a **3-stage linear model** — three integration times (e.g. 10ms, 20ms, 30ms) are measured at OEM calibration time to characterise the linear response of each LED channel. The model is stored as a JSON file per device.

---

## 3. Model File Locations (priority order)

| Priority | Path | Notes |
|----------|------|-------|
| 1 (preferred) | `calibrations/active/{SERIAL}/led_model.json` | Written by OEM calibration script |
| 2 (legacy) | `led_calibration_official/spr_calibration/data/led_calibration_3stage_*.json` | Older location, serial matched by reading file content |

`load_model()` always checks the active path first. Falls back to legacy only if active path is absent.

---

## 4. Classes

### `LEDCalibrationModelLoader`

Main class. Stateful — holds the loaded model in `self.model_data` after `load_model()`.

| Method | Purpose |
|--------|---------|
| `load_model(detector_serial)` | Load model for a specific device serial |
| `calculate_intensity(channel, target_counts, integration_time_ms)` | Predict required LED intensity |
| `calculate_counts(channel, intensity, integration_time_ms)` | Predict output counts |
| `get_model_info()` | Return metadata dict (serial, timestamp, equation) |
| `validate_model()` | Check model completeness — all 4 channels present, slopes > 0 |

### Exceptions

| Exception | When raised |
|-----------|------------|
| `ModelNotFoundError` | No model file found for the requested serial |
| `ModelValidationError` | Model file found but content fails validation |

---

## 5. Model JSON Format

### Active calibration format (`calibrations/active/{SERIAL}/led_model.json`)

```json
{
  "detector_serial": "FLMT09788",
  "timestamp": "2026-02-20T14:30:00",
  "led_models": {
    "A": [
      {"time_ms": 10, "slope": 1250.5},
      {"time_ms": 20, "slope": 2498.3},
      {"time_ms": 30, "slope": 3745.1}
    ],
    "B": [...],
    "C": [...],
    "D": [...]
  },
  "correction_factors": {"A": 1.02, "B": 0.98, "C": 1.01, "D": 0.99},
  "average_corrections": {"A": 1.01, "B": 0.99, "C": 1.00, "D": 1.00},
  "dark_counts_per_time": {"A": 120, "B": 115, "C": 118, "D": 122}
}
```

### Legacy format (`led_calibration_3stage_*.json`)

Old format used `[[time_ms, slope], ...]` arrays instead of dicts. The loader handles both transparently during format conversion.

---

## 6. Format Conversion (legacy → standard)

On load, both old and new JSON formats are normalized to a standard internal dict:

```python
{
    "detector_serial": str,
    "timestamp": str,
    "model_equation": "counts = slope_10ms × intensity × (time_ms / 10)",
    "calibration_type": "3-Stage Linear",
    "detector_max": 65535,
    "dark": {...},
    "led_models": {
        "A": {"S": {"slope_10ms": float, "r_squared": float}},
        ...
    },
    "correction_factors": {...},
    "average_corrections": {...}
}
```

The `r_squared` in the internal format is synthesised from the linearity ratio of 20ms/10ms stages (expected ~2.0). This is an indicator, not a true R².

---

## 7. Ultra-Sensitive Device Detection

Some devices saturate at very low intensity (I=60 at 10ms). The OEM calibration script auto-detects this and uses shorter integration times `[5, 10, 15]ms` + lower intensities `[10, 20, 30, 40, 60]`. The loader is agnostic to which time range was used — it reads whatever stages are in the file.

---

## 8. Consumers

| Consumer | Usage |
|---------|-------|
| `affilabs/core/oem_model_training.py` | Writes the model file during OEM calibration |
| `affilabs/core/calibration_service.py` | Loads model at startup; uses `calculate_intensity()` to set LED targets |
| `scripts/provisioning/oem_calibrate.py` | Orchestrates OEM cal → calls model training → saves result |

---

## 9. Error Handling

- `ModelNotFoundError` is caught in `calibration_service.py` — calibration proceeds without model (falls back to iterative convergence)
- `ModelValidationError` is logged as warning — missing channels or zero slopes cause fallback to iterative mode
- File read errors are logged; never bubble up to UI

---

## 10. Key Gotchas

- Serial matching is **case-insensitive and trimmed** — `"flmt09788"` and `"FLMT09788 "` both match
- Legacy files are matched by reading `detector_serial` inside the file, not by filename — filename has no serial suffix in the old format
- The `correction_factors` field is per-channel empirical adjustment from QC validation runs — applied on top of the raw model in some consumers
- Do not confuse `led_model.json` (this system) with `startup_config.json` (S-pol reference spectra from startup cal)
