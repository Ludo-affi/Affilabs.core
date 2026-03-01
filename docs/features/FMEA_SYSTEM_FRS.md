# FMEA System — Feature Reference Specification

**Sources:**
- `affilabs/core/fmea_tracker.py` — core tracker, failure modes, severity, event log, scenario detection
- `affilabs/core/fmea_integration.py` — integration helpers wiring FMEA checks into calibration/live data

**Status:** Implemented (v2.0.5)
**Layer:** Layer 2 — Business / Core
**Depends on:** numpy (for trend checks), no Qt dependencies

---

## 1. Purpose

Failure Mode and Effects Analysis (FMEA) tracking system. Logs quality events across three phases of instrument operation and detects failure scenarios by correlating events across phases.

**Three monitored phases:**

| Phase | Events monitored |
|-------|----------------|
| **Calibration** | LED intensity, LED saturation, dark noise quality |
| **Afterglow validation** | Exponential decay tau, amplitude, fit R² |
| **Live data** | Signal quality (peak intensity, FWHM, SNR), pump artifacts, FWHM trend |

---

## 2. Core Components (`fmea_tracker.py`)

### `FMEATracker`

Main stateful tracker. One instance per session (or per device, depending on scope).

| Method | Purpose |
|--------|---------|
| `log_calibration_event(...)` | Record a calibration quality event |
| `log_afterglow_event(...)` | Record an afterglow validation event |
| `log_live_data_event(...)` | Record a live data quality event |
| `get_system_health()` | Aggregate health summary: overall status, active failure count |
| `get_active_scenarios()` | List currently active failure scenarios with mitigations |
| `query_events(phase, event_type, passed, time_window_minutes)` | Filter event history |
| `mark_calibration_complete()` | Phase lifecycle marker |
| `mark_afterglow_validation_complete()` | Phase lifecycle marker |
| `export_session_report()` | Write FMEA session report to file, return path |

### `FailureMode` (Enum)

Categorized failure modes:

| Category | Modes |
|----------|-------|
| Calibration | `LED_SATURATION`, `LED_DRIFT`, `LED_TIMING_ISSUE`, `DARK_NOISE_HIGH`, `DARK_NOISE_UNSTABLE`, `SPECTRAL_CORRECTION_FAIL` |
| Afterglow | `AFTERGLOW_TAU_OUT_OF_RANGE`, `AFTERGLOW_AMPLITUDE_HIGH`, `AFTERGLOW_FIT_POOR`, `AFTERGLOW_BASELINE_HIGH`, `AFTERGLOW_TREND_ABNORMAL` |
| Live data | `SIGNAL_LOSS`, `SIGNAL_DRIFT`, `PEAK_QUALITY_DEGRADED`, `FWHM_DEGRADATION`, `PUMP_INTERFERENCE`, `FLOW_INSTABILITY` |
| Hardware | `USB_DISCONNECT`, `CONTROLLER_ERROR`, `PUMP_ERROR`, `OPTICS_LEAK` |
| Correlation | `CALIBRATION_AFTERGLOW_MISMATCH`, `LIVE_DATA_DEGRADATION_POST_CALIBRATION` |

### `Severity` (Enum)

`INFO` → `LOW` → `MEDIUM` → `HIGH` → `CRITICAL`

---

## 3. Integration Helpers (`fmea_integration.py`)

`FMEAIntegrationHelper` wraps `FMEATracker` with domain-specific check methods. These apply thresholds and determine pass/fail, then delegate logging to the tracker.

### Calibration checks

| Method | Checks |
|--------|-------|
| `check_led_calibration(channel, intensity, target, tolerance, r_squared)` | Saturation (>60000), deviation from target, R² linearity |
| `check_dark_noise(channel, dark_mean, dark_std, expected, max_std)` | High dark level, unstable dark noise |

### Afterglow checks

| Method | Checks |
|--------|-------|
| `check_afterglow_tau(channel, tau_ms, led_type, expected_range, warn_range)` | Tau within expected range (LED-type specific) |
| `check_afterglow_amplitude(channel, amplitude, integration_time_ms)` | Amplitude < 10000 counts |
| `check_afterglow_fit_quality(channel, r_squared)` | R² ≥ 0.85 (pass), ≥ 0.95 (optimal) |

### Live data checks

| Method | Checks |
|--------|-------|
| `check_signal_quality(channel, peak_intensity, fwhm_nm, snr)` | Intensity ≥ 1000, FWHM ≤ 60nm, SNR ≥ 10 |
| `check_pump_correlation(channel, flow_rate, signal_change, time_delta)` | Unexpected pump artifacts (Δsignal >100 within 2s of pump change) |
| `check_fwhm_trend(channel, current_fwhm, cal_fwhm, rate_nm_per_min)` | Rate ≤ 0.5nm/min |

### Cross-phase correlation checks

| Method | When to call |
|--------|-------------|
| `check_calibration_afterglow_correlation()` | After both calibration and afterglow validation complete |
| `check_afterglow_live_correlation()` | Periodically during live acquisition |

Cross-phase checks detect scenarios like: calibration passed but afterglow failed (LED timing issue), or afterglow passed but live data degrading (optical leak, temperature drift).

---

## 4. Thresholds Summary

| Metric | Threshold | Severity |
|--------|-----------|---------|
| LED intensity at saturation (>60000 counts) | Always fail | HIGH |
| LED intensity deviation from target | > 10% = fail, > 20% = HIGH | MEDIUM/HIGH |
| LED response R² | < 0.95 = warning | MEDIUM |
| Dark noise mean | > expected + 100 = fail | MEDIUM |
| Dark noise std | > 50 = fail, > 100 = HIGH | MEDIUM/HIGH |
| Afterglow tau | Outside LED-specific warn range = fail | MEDIUM |
| Afterglow amplitude | > 10000 counts = fail | MEDIUM |
| Afterglow fit R² | < 0.85 = fail, < 0.95 = low warning | MEDIUM |
| Live peak intensity | < 1000 counts = fail | HIGH |
| Live FWHM | > 60nm = fail | MEDIUM |
| Live SNR | < 10 = fail | LOW |
| Pump artifact | > 100 signal change within 2s of pump change (unexpected) | LOW |
| FWHM trend | > 0.5nm/min = fail | MEDIUM |

---

## 5. Usage Pattern

```python
from affilabs.core.fmea_tracker import FMEATracker
from affilabs.core.fmea_integration import FMEAIntegrationHelper

fmea = FMEATracker()
helper = FMEAIntegrationHelper(fmea)

# During calibration:
helper.check_led_calibration('a', intensity=35000, target_intensity=35000)
fmea.mark_calibration_complete()

# After afterglow validation:
helper.check_afterglow_tau('a', tau_ms=3.2, led_type='LCW', expected_range=(2.5, 4.0), warn_range=(1.5, 5.0))
fmea.mark_afterglow_validation_complete()
helper.check_calibration_afterglow_correlation()

# During live acquisition (periodic):
helper.check_signal_quality('a', peak_intensity=45000, fwhm_nm=28.5, snr=85.0)

# Get health status for UI:
health = fmea.get_system_health()
scenarios = fmea.get_active_scenarios()
```

---

## 6. Key Gotchas

- `FMEATracker` is **not** integrated into the main app signal path as of v2.0.5 — it's instantiated and called from within calibration/validation code directly. There is no live Qt signal emitted from FMEA events.
- The integration helper methods are standalone — they are not called automatically. The caller (e.g. `calibration_service.py`) must invoke them at the right points.
- `query_events()` with `time_window_minutes` uses wall-clock time from event timestamps — safe to use for cross-phase correlation.
- Session reports are written to the path returned by `export_session_report()` — typically `_data/logs/fmea_session_*.json`.
