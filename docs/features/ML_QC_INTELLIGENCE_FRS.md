# ML QC Intelligence — Feature Reference Specification

**Source:** `affilabs/core/ml_qc_intelligence.py`
**Status:** Implemented (v2.0.5)
**Layer:** Layer 2 — Business / Core
**Depends on:** `affilabs/core/calibration_data.py`, numpy, per-device JSON history files

---

## 1. Purpose

Predictive analytics system that learns from calibration history to warn users before problems occur. Runs after each successful calibration and generates four independent predictions.

**Scope boundary:** This system operates on **calibration QC data only** — it never analyzes live SPR sensorgram data during experiments. This is by design to avoid interfering with dynamic biological responses.

---

## 2. Four Prediction Models

| Model | What it predicts | Data source |
|-------|-----------------|------------|
| **Model 1** — Calibration quality | Failure probability for the next calibration + predicted FWHM per channel | Last 10 calibration records |
| **Model 2** — LED health | Per-LED intensity trend, health score (0–1), estimated days until replacement | LED intensity history across all calibrations |
| **Model 3** — Sensor coating life | FWHM degradation trend, estimated experiments remaining before chip replacement needed | FWHM history across all calibrations |
| **Model 4** — Optical alignment | P/S ratio deviation from historical baseline — detects polarizer drift or fiber movement | P/S ratio from calibration QC (not live SPR) |

---

## 3. Class: `MLQCIntelligence`

```python
MLQCIntelligence(device_serial: str, data_dir: Path | None = None)
```

Per-device instance. History persisted in `data_dir` (default: `data/devices/{serial}/ml_qc/`).

### Public API

| Method | Returns | Notes |
|--------|---------|-------|
| `update_from_calibration(cal_data)` | None | Call after every successful calibration — updates all history files |
| `predict_next_calibration()` | `CalibrationPrediction` | Risk level + failure probability + per-channel predicted FWHM |
| `predict_led_health()` | `list[LEDHealthStatus]` | One entry per channel (a/b/c/d) |
| `predict_sensor_coating_life()` | `SensorCoatingStatus` | Coating quality + replacement warning |
| `check_optical_alignment(cal_data)` | `OpticalAlignmentStatus` | Updates baseline, returns drift detection result |
| `generate_intelligence_report()` | `str` | Formatted multi-section report for all 4 models |

---

## 4. Data Classes

### `CalibrationPrediction`
```python
failure_probability: float   # 0–1
predicted_fwhm: dict[str, float]  # channel → nm
confidence: float            # 0–1 (based on history depth)
warnings: list[str]
recommendations: list[str]
risk_level: str              # 'low' | 'medium' | 'high'
```
Requires ≥ 3 calibrations for meaningful output. Returns conservative defaults with 0.3 confidence if insufficient history.

### `LEDHealthStatus`
```python
channel: str                 # 'a'|'b'|'c'|'d'
current_intensity: int       # 0–255
intensity_trend: float       # change per calibration (positive = degrading)
days_until_replacement: int | None
health_score: float          # 0–1 (1 = excellent, 0 = needs replacement)
status: str                  # 'excellent'|'good'|'degrading'|'critical'
replacement_recommended: bool
```
LED intensity ≥ 250/255 → `critical`. ≥ 230 → `degrading`.

### `SensorCoatingStatus`
```python
current_fwhm_avg: float      # nm (average across all 4 channels)
fwhm_trend: float            # nm per calibration (positive = widening)
estimated_experiments_remaining: int | None
coating_quality: str         # 'excellent'|'good'|'acceptable'|'poor'
replacement_warning: bool    # True if FWHM > 55nm or < 10 experiments remaining
confidence: float
```
Replacement threshold: FWHM > 60nm (broad dip = degraded coating / contamination).

### `OpticalAlignmentStatus`
```python
ps_ratio_baseline: float     # Historical mean P/S ratio from calibrations
ps_ratio_deviation: float    # Deviation from baseline
orientation_confidence: float  # 0–1
alignment_drift_detected: bool  # True if deviation > 3σ from baseline
maintenance_recommended: bool
warning_message: str | None
```

---

## 5. Failure Probability Factors (Model 1)

Three weighted factors combined into a 0–1 probability:

| Factor | Weight | Trigger |
|--------|--------|---------|
| Recent calibration failure rate | 40% | From last 10 calibration records |
| FWHM trend | 40% | > 2nm/calibration → full weight; 1–2nm → half weight |
| LED critical status | 20% | Any channel in `critical` state |

Risk levels: `low` < 0.4 ≤ `medium` < 0.7 ≤ `high`

---

## 6. History Files (per device)

All stored in `data_dir` (default `data/devices/{serial}/ml_qc/`):

| File | Content | Max records |
|------|---------|------------|
| `calibration_history.json` | Array of calibration records (timestamp, FWHM, LED intensities, pass/fail) | 100 |
| `led_health.json` | LED intensity tracking (currently unused — data extracted from calibration_history) | — |
| `sensor_coating.json` | Coating history (currently unused — data extracted from calibration_history) | — |
| `alignment_baseline.json` | `{"ps_ratio_history": [...]}` — rolling list of P/S ratios | 50 |

History append is non-destructive (old records are not rewritten). Files are created automatically on first use.

---

## 7. Integration Point

`MLQCIntelligence.update_from_calibration(cal_data)` is called in `calibration_service.py` after a successful calibration completes. The `CalibrationData` object passed in contains `transmission_validation`, `p_mode_intensity`, `s_integration_time`, etc.

The `check_optical_alignment()` method also receives `CalibrationData` and should be called at the same time as `update_from_calibration()`.

---

## 8. Key Gotchas

- Model 4 (optical alignment) uses **calibration P/S ratios only** — not live SPR data. Calling it with live data would produce meaningless results and could mask real SPR responses.
- Prediction quality scales with history depth — the system returns low-confidence defaults until ≥ 3 calibrations are recorded. Full confidence (1.0) reached at 10 calibrations.
- `generate_intelligence_report()` calls all 4 models internally — do not call this in a hot path.
- History files silently reset to empty on JSON parse error (safe degradation).
