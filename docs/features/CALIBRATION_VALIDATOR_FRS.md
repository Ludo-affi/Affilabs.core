# Calibration Validator — Feature Reference Specification

**Source:** `affilabs/services/calibration_validator.py`
**Status:** Implemented (v2.0.5)
**Layer:** Layer 2 — Business / Services
**Depends on:** numpy only — no Qt, fully unit-testable

---

## 1. Purpose

Pure business logic service that validates calibration data quality before it is accepted as the live calibration reference. Catches bad spectra (empty, saturated, too noisy, wrong shape) and inconsistent LED or integration settings before they corrupt the calibration baseline.

---

## 2. Class: `CalibrationValidator`

```python
CalibrationValidator(
    min_signal: float = 5000.0,        # Minimum acceptable mean signal (counts)
    max_counts: int = 65535,           # Detector full scale
    saturation_threshold: float = 0.95, # Fraction of max_counts = saturation
    min_snr: float = 10.0,             # Minimum SNR (mean/std)
)
```

All thresholds are configurable at construction — default values suit Flame-T / USB4000 at normal operating conditions.

---

## 3. Validation Methods

### `validate_spectrum(spectrum, channel) → list[ValidationResult]`

Validates a single raw spectrum array. Checks (in order):

1. Non-empty array
2. All values finite (no NaN/Inf)
3. Signal strength ≥ `min_signal`
4. Saturation < 5% of pixels (error) / < 1% (warning)
5. SNR (mean/std) ≥ `min_snr`
6. Not all-zero

Returns a list of `ValidationResult` — may contain multiple entries (one per check).

### `validate_calibration_set(s_pol_ref, wavelengths, p_mode_intensities, s_mode_intensities, integration_time_s, integration_time_p) → tuple[bool, list[ValidationResult]]`

Validates a complete calibration dataset (all 4 channels + metadata). Checks:

1. All 4 channels present in `s_pol_ref`, `p_mode_intensities`, `s_mode_intensities`
2. Wavelength array non-empty
3. Each spectrum length matches wavelength array length
4. Per-spectrum quality via `validate_spectrum()` for each channel
5. LED intensity validity (0–255, not zero, warn if < 20)
6. Integration time validity (3–10000ms, warn if < 10ms)

Returns `(all_passed, results)`. `all_passed` is True if there are no `"error"` severity results (warnings don't block).

---

## 4. Data Class: `ValidationResult`

```python
@dataclass
class ValidationResult:
    passed: bool
    message: str
    severity: str    # 'info' | 'warning' | 'error'
    value: float | None = None
    threshold: float | None = None
```

---

## 5. Severity Levels

| Level | Meaning | Blocks calibration? |
|-------|---------|-------------------|
| `info` | Nominal — value within expected range | No |
| `warning` | Marginal — value is borderline but acceptable | No |
| `error` | Failed — value out of range or invalid | Yes |

---

## 6. Individual Check Thresholds

### Signal strength
| Condition | Severity |
|-----------|---------|
| mean < `min_signal` | error |
| `min_signal` ≤ mean < `min_signal × 1.5` | warning |
| mean ≥ `min_signal × 1.5` | info |

### Saturation (pixels ≥ 95% of max_counts)
| Condition | Severity |
|-----------|---------|
| > 5% of pixels saturated | error |
| 1–5% saturated | warning |
| < 1% saturated | info |

### SNR (mean / std)
| Condition | Severity |
|-----------|---------|
| SNR < `min_snr` | error |
| `min_snr` ≤ SNR < `min_snr × 2` | warning |
| SNR ≥ `min_snr × 2` | info |

### LED intensity (0–255)
| Condition | Severity |
|-----------|---------|
| Out of range or == 0 | error |
| < 20 | warning |
| ≥ 20 | info |

### Integration time (ms)
| Condition | Severity |
|-----------|---------|
| < 3ms or > 10,000ms | error |
| 3–10ms | warning |
| ≥ 10ms | info |

---

## 7. Utility

### `format_validation_report(results) → str`

Formats a list of `ValidationResult` into a human-readable report grouped by severity (errors → warnings → info) with a pass/fail summary line. Used in logs and calibration QC dialogs.

---

## 8. Integration

Called in `calibration_service.py` after the convergence engine produces a calibration dataset, before writing the calibration result to disk or accepting it as the live reference. If `validate_calibration_set()` returns `all_passed = False`, the calibration is rejected and `calibration_failed` signal is emitted with the formatted validation report as the error message.

---

## 9. Key Gotchas

- SNR is calculated as `mean / std` across the **entire** spectrum array — this is a global spectral SNR, not a per-region or peak SNR. It's a noise floor indicator, not a biosensing sensitivity measure.
- The saturation check uses `>= saturation_counts` (i.e. `>= max_counts × 0.95` = 62258 for a 16-bit detector) — not `== max_counts`. This catches near-saturation before full clipping occurs.
- `validate_calibration_set()` passes `all_passed = True` if only warnings are present — warnings are non-blocking. Only errors block calibration acceptance.
- No Qt imports — safe to test in isolation without a display.
