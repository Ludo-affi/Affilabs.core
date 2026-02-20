# Calibration Orchestrator — Functional Requirements Specification

**Document type:** Functional Requirements Specification  
**Status:** Code-verified (Feb 19 2026)  
**Replaces:** `docs/calibration/CALIBRATION_MASTER.md` (Nov 2025, stale)  
**Source files:**
- `affilabs/core/calibration_service.py` — `CalibrationService` (2067 lines)
- `affilabs/core/calibration_orchestrator.py` — `run_startup_calibration()` (1276 lines)
- `affilabs/core/simple_led_calibration.py` — `SimpleLEDCalibration`
- `affilabs/managers/calibration_manager.py` — `CalibrationManager` (thin UI delegate)

---

## 1. Overview

The calibration system has two entry points:

| Entry Point | Trigger | What it does |
|-------------|---------|-------------|
| **Full Calibration** | "Full Calibration" button → dialog | 6-step optical calibration; optional pump prime (P4PRO) |
| **Simple LED Calibration** | "Simple LED Calibration" button | Fast LED intensity adjustment only; no servo movement |

Both paths are coordinated by `CalibrationService`. The 6-step core runs in `run_startup_calibration()` inside `calibration_orchestrator.py`.

---

## 2. Signals

`CalibrationService` emits Qt signals (cross-thread safe, `QObject` subclass):

| Signal | Type | Payload | When |
|--------|------|---------|------|
| `calibration_started` | `Signal()` | — | Thread starts |
| `calibration_progress` | `Signal(str, int)` | `(message, percent)` | Throughout |
| `calibration_complete` | `Signal(object)` | `CalibrationData` | Success |
| `calibration_failed` | `Signal(str)` | error message | Failure |

---

## 3. Full Calibration Flow

### 3.1 Entry: `CalibrationService.start_calibration(force_oem_retrain=False)`

1. Guards against double-start (`_running` flag).
2. **Stops live acquisition** — calls `data_mgr.stop_acquisition()` if acquiring.
3. **LED model pre-check** — loads `LEDCalibrationModelLoader` for the detector serial. If no model found and `force_oem_retrain=False`, asks user: "Run OEM Calibration?" and routes to `_on_oem_led_calibration()` if Yes.
4. Resets state: `_calibration_completed = False`, `_retry_count = 0`, `_prime_pump_completed = False`.
5. Shows `StartupCalibProgressDialog` — user must click **Start**.
6. Dialog connects `start_clicked` → `_on_start_button_clicked` → starts `_run_calibration()` thread.

> **Headless mode:** If `CALIBRATION_HEADLESS=1` env var and no UI context, skips dialog and starts thread directly.

### 3.2 Thread: `CalibrationService._run_calibration()`

Runs in a `daemon=True` `threading.Thread` named `"CalibrationService"`.

**Pre-flight:**
- Enables verbose console logging for the thread.
- Creates a timestamped log file in `logs/calibration_*.log`.
- Validates `ctrl` and `usb` are connected — raises immediately if not.

**Branch: Pump present (`hardware_mgr.pump is not None`) and not already primed:**

```
asyncio loop: prime_with_optical_cal()
│
├─ Initialize pumps (move to zero position)
│
├─ Pump cycle 1/6 (8% progress)
│   Aspirate + dispense 1000 µL
│
├─ Pump cycle 2/6 (13%)
│   Aspirate + dispense
│
├─ Pump cycle 3/6 (19%)
│   Open 6-port valves to INJECT position  ← raw_ctrl.knx_six(state=1, ch=1 and 2)
│   Aspirate + dispense
│
├─ Pump cycle 4/6  ← START optical calibration in parallel thread
│   optical_cal_thread = threading.Thread(target=run_optical_calibration, ...)
│   Aspirate + dispense
│
├─ Pump cycle 5/6 (26%)
│   Open 3-way valves to LOAD position  ← raw_ctrl.knx_three(state=1, ch=1 and 2)
│   Aspirate + dispense
│
├─ Pump cycle 6/6 (32%)
│   Aspirate + dispense
│
└─ Close ALL valves (safety — prevents device heating)
     raw_ctrl.knx_three(state=0, ch=1 and 2)
     raw_ctrl.knx_six(state=0, ch=1 and 2)

optical_cal_complete.wait(timeout=300s)  ← wait for optical thread to finish
```

Pump aspiration speed: 24000 µL/min = 400 µL/s.  
Pump dispense speed: 5000 µL/min = 83.3 µL/s.  
Pump stall → recovery: switch valve to INPUT, push plunger home, raise RuntimeError.

**Branch: No pump (P4SPR or already primed):**
- USB buffer clear: 3 dummy reads with 5-second timeouts. If all fail → device close/reopen.
- Loads `DeviceConfiguration(device_serial)` freshly.
- Calls `run_startup_calibration()` directly.

### 3.3 Servo Auto-Calibration Fallback

If `run_startup_calibration()` raises a `RuntimeError` containing any of:

| Trigger string | Meaning |
|---------------|---------|
| `"Servo positions not found"` | `get_servo_positions()` returned None |
| `"ServoCalibrationRequired"` | Custom exception from orchestrator |
| `"Polarizer blocking light"` | Pre-convergence signal test <3% |
| `"positions are INCORRECT"` | Convergence diagnoses wrong S/P |
| `"Signal is extremely low"` | All signals near dark |
| `"Signal is too low"` | Signal below 50% of target |

→ Service **automatically triggers servo calibration** without user interaction:

```
Import: servo_polarizer_calibration.calibrate_polarizer.run_calibration_with_hardware()

HardwareManagerWrapper (usb, ctrl) → run_calibration_with_hardware(hw_wrapper, progress_callback)

On success:
  1. Re-read DeviceConfiguration from disk (new positions saved by servo cal)
  2. Sync positions to app.main_window.device_config.set_servo_positions(s, p)
  3. Force save device_config to disk
  4. Update controller RAM: ctrl.set_servo_positions(s, p)
  5. Retry run_startup_calibration() with updated positions

On servo cal failure → raise RuntimeError (shown to user as dialog)
```

### 3.4 Post-Calibration

On success:
1. Converts `LEDCalibrationResult` → `CalibrationData` domain model via `led_calibration_result_to_domain()`.
2. Sets `_calibration_completed = True`, stores result.
3. Saves calibration JSON to `OpticalSystem_QC/<serial>/spr_calibration/` via `save_calibration_result_json()`.
4. Propagates `calibration_data.wavelengths` → `data_mgr.wave_data`.
5. Evaluates sensor readiness: `_evaluate_sensor_ready(calibration_data)` — sets `hardware_mgr._sensor_verified = True` if QC passes.
6. Emits `calibration_complete(CalibrationData)`.

On failure:
- Emits `calibration_failed(error_message)`.
- Dialog shows Retry / Continue Anyway buttons.
- Retry increments `_retry_count` (max 3). After 3 failures, blocks retry.

---

## 4. Core: `run_startup_calibration()` — 6-Step Orchestrator

**Signature:**
```python
def run_startup_calibration(
    usb,                         # Spectrometer HAL
    ctrl,                        # Controller HAL
    device_type: str,            # 'PicoP4SPR', 'PicoEZSPR', etc.
    device_config,               # DeviceConfiguration instance
    detector_serial: str,
    progress_callback=None,      # callback(message: str, percent: int)
    single_mode: bool = False,   # calibrate one channel only
    single_ch: str = "a",
    stop_flag=None,              # threading.Event for cancellation
    use_convergence_engine: bool = True,
    force_oem_retrain: bool = False,
) -> LEDCalibrationResult
```

> **Note:** `use_convergence_engine=False` is no longer supported and raises `RuntimeError`. The legacy convergence algorithm was removed. Only the `production_wrapper` engine is valid.

---

### Step 1: Hardware Validation & LED Preparation (5%)

- `ctrl.turn_off_channels()` → wait `LED_OFF_SETTLING_S = 0.2s`
- If `ctrl.supports_batch_leds`: enable batch mode → wait `LED_BATCH_ENABLE_S = 0.1s`
- Failures here are **non-fatal** — logged as warnings, calibration continues

---

### Step 2: Wavelength Calibration (17%)

- `usb.read_wavelength()` → reads wavelength array from detector EEPROM
- Defines SPR ROI using `MIN_WAVELENGTH` and `MAX_WAVELENGTH` from `settings.py` (default: 560–720 nm)
- Stores: `result.wave_data` (ROI slice), `result.wave_min_index`, `result.wave_max_index`
- Failure: raises `RuntimeError("Failed to read wavelength data from detector")`

---

### Step 3: LED Brightness Measurement & Model Validation (30%)

**Determine channel list:**
- `determine_channel_list(device_type, single_mode, single_ch)` from `affilabs/utils/calibration_helpers.py`
- Single mode: `[single_ch]`; Full mode: `["a","b","c","d"]`

**Model load attempt (unless `force_oem_retrain`):**
```
LEDCalibrationModelLoader().load_model(detector_serial)
```

| Outcome | Action |
|---------|--------|
| Model found | Extract `model_slopes_s` and `model_slopes_p` (per-channel, lowercase keys) |
| `ModelNotFoundError` | Set `model_exists = False` |
| `ModelValidationError` | Set `model_exists = False` (corrupt model → recreate) |
| `force_oem_retrain = True` | Skip load, set `model_exists = False` |

**If `model_exists = False`:** Run `run_oem_model_training_workflow()`:
- Trains a new LED calibration model (~2 minutes) 
- Scans LED intensities at multiple integration times for all channels
- Saves model to `OpticalSystem_QC/<serial>/spr_calibration/`
- Reloads model after training to get fresh slopes
- Failure here raises `RuntimeError` (hard stop)

**Weakest channel detection:**
- `weakest_ch = min(model_slopes_s, key=lambda c: model_slopes_s[c])`
- Used to set integration time and normalize LED intensities

**Servo position load and EEPROM sync:**
- `device_config.get_servo_positions()` → `{"s": int, "p": int}` (PWM units)
- Missing positions → raises `ServoCalibrationRequired(RuntimeError)`
- Default values (S=10, P=100) → logged as warning but not blocked
- `device_config.sync_to_eeprom(raw_ctrl)` → EEPROM sync with readback verification
  - Readback mismatch → raises `RuntimeError("EEPROM sync verification failed")`

**Servo movement to S-position:**
1. `ctrl.turn_off_channels()`
2. If `ctrl.supports_polarizer`: park servo to PWM=1 first (eliminate backlash, 0.8s settle)
3. `ctrl.set_servo_positions(s_pos, p_pos)` → loads into controller RAM
4. `ctrl.set_mode("s")` → sends 'ss' command
5. Fallback if 'ss' fails: `ctrl.servo_move_raw_pwm(s_pos)` directly
6. Finally: wait 1.0s for servo to settle

---

### Step 4: S-Mode LED Convergence + Reference Capture (45%)

**Pre-convergence polarizer check:**
- All 4 LEDs @ 5% (`int(0.05 × 255) = 12`) for 5ms
- Reads test spectrum, calculates ROI mean
- Threshold: `detector_params.max_counts × 0.03` (3% of detector range)
- Below threshold → raises `RuntimeError("Polarizer blocking light: ...")` 
  - This is caught by `CalibrationService` to trigger automatic servo calibration

**Channel enable (P4PRO flow-mode controllers only):**
- `ctrl.turn_on_channel(ch)` for each channel in `ch_list`
- Static controllers (P4SPR) skip this

**Initial LED / integration time calculation (model-based):**
```
target_counts = 0.85 × detector_params.max_counts
optimal_integration_ms = (target_counts / (weakest_slope × 255)) × 10
optimal_integration_ms = clamp(min_integration, max_integration)

initial_leds:
  weakest_ch → 255
  other ch   → int((weakest_slope / ch_slope) × 255) × optional_0.917_correction
               correction applied if ch_slope > weakest_slope × 1.5
               min 10, max 255
```

Fallback if no model: `initial_integration_ms=30`, all LEDs=255.

**Convergence call (`LEDconverge_engine` from `production_wrapper`):**

```python
ConvergenceRecipe(
    channels          = ch_list,
    initial_leds      = initial_leds,
    initial_integration_ms = initial_integration_ms,
    target_percent    = 0.85,
    tolerance_percent = 0.15,
    max_iterations    = 12,
    prefer_led_over_integration = True,
    led_optimization_target     = 200.0,
    min_integration_for_led_max = detector_params.min_integration_time,
)
```

Returns: `(s_integration_time, s_final_signals, s_success, s_converged_leds, s_iterations)`

**Partial convergence acceptance:**
- If not `s_success` but `max_signal > target×0.75` AND `min_signal > target×0.50` → override to success

**Failure analysis:**
- If `max_signal < 0.03 × detector_params.max_counts` or any LED=255 with signal <10% → diagnoses polarizer blocking → raises `RuntimeError("Polarizer blocking light: ...")`

**S-pol reference capture:**
```
num_scans_s = min(10, max(1, int(180.0 / s_integration_time)))

For each channel:
  acquire_raw_spectrum(usb, ctrl, ch, s_mode_leds[ch], s_integration_time, num_scans=num_scans_s)
  → result.s_raw_data[ch] = spectrum[wave_min_index:wave_max_index]
```

Saturation in reference (≥ `saturation_threshold`) → raises `RuntimeError`. 

---

### Step 5: P-Mode LED Convergence + Reference + Dark (65%)

**Servo motion to P-position:**
1. `ctrl.turn_off_channels()` → wait 50ms
2. Park servo to PWM=1 (eliminates backlash, 0.8s)
3. Convert PWM to degrees: `degrees = 5 + (pwm / 255) × 170`
4. Send raw serial command: `sv{s_deg:03d}{p_deg:03d}\n` (NOTE: uses `raw_ctrl._ser.write()` directly)
5. Send `sp\n` → wait 0.5s

> **Architecture note:** Step 5 servo movement bypasses HAL and writes directly to `raw_ctrl._ser`. This is a known inconsistency with the HAL-compliant design.

**Initial P-mode LED calculation:**
```
initial_p_leds[ch] = clamp(10, 255, int(s_mode_leds[ch] × 1.08))
```
P-pol needs ~8% more brightness than S-pol due to SPR absorption.

**Convergence call:**
```python
ConvergenceRecipe(
    target_percent    = 0.75,
    tolerance_percent = 0.05,
    max_iterations    = 12,
    min_signal_for_model = 0.95,   # disables ML model predictions
    max_led_change    = 80,
    led_small_step    = 8,
    prefer_est_after_iters = 1,
    near_window_percent = 0.10,
    prefer_led_over_integration = True,
    FREEZE_INTEGRATION = False,
    ALLOW_INTEGRATION_INCREASE_ONLY = True,
    WEAKEST_CHANNEL_OVERRIDE = s_weakest_ch,
)
model_slopes = None  # disabled — P/S ratios vary too much per channel
initial_integration_ms = s_integration_time  # frozen at S-pol value
```

**P-mode failsafe:** If convergence fails to fully converge, uses **last iteration's LEDs** (closest to target), not initial guess. Does not raise on P-pol convergence failure — calibration continues.

**P-pol dark check:**
- `DARK_THRESHOLD = 1000` counts
- If `max(p_final_signals) < 1000` → raises `RuntimeError("SERVO_RECALIBRATION_REQUIRED: P-pol position is dark/blocked...")`
  - Caught by `CalibrationService` → automatic servo recalibration

**P-pol reference capture:**
```
num_scans_p = min(10, max(1, int(180.0 / p_integration_time)))

For each channel:
  spectrum = acquire_raw_spectrum(usb, ctrl, ch, p_mode_leds[ch], p_integration_time, num_scans_p)
  result.p_raw_data[ch] = spectrum[wave_min_index:wave_max_index]
```

Saturation in P-pol reference → logs WARNING but does NOT raise (failsafe: continue).  
Failed channel → uses S-pol data as fallback.

**Dark spectrum capture:**
```
ctrl.turn_off_channels() → wait 100ms
spectra = [usb.read_intensity() for _ in range(num_scans_s)]
dark_roi = mean(spectra)[wave_min_index:wave_max_index]
result.dark_s = {ch: dark_roi for ch in ch_list}
result.dark_p = {ch: dark_roi for ch in ch_list}
```

Dark integration time matches P-pol integration time (last `usb.set_integration()` call before dark).

---

### Step 6: QC Validation & Result Packaging (85%)

**Polarization processing:**
```python
s_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
    raw_spectrum = result.s_raw_data[ch],
    dark_noise   = result.dark_s[ch],
)
p_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
    raw_spectrum = result.p_raw_data[ch],
    dark_noise   = result.dark_p[ch],
)
```

**Transmission calculation:**
```python
TransmissionProcessor.process_single_channel(
    p_pol_clean      = p_pol_ref[ch],
    s_pol_ref        = s_pol_ref[ch],
    led_intensity_s  = result.s_mode_intensity[ch],
    led_intensity_p  = result.p_mode_intensity[ch],
    wavelengths      = result.wave_data,
    apply_sg_filter  = True,
    baseline_method  = "percentile",
    baseline_percentile = 95.0,
)
```

**QC metrics per channel:**
```python
TransmissionProcessor.calculate_transmission_qc(
    transmission_spectrum = transmission[ch],
    wavelengths           = result.wave_data,
    channel               = ch,
    p_spectrum            = p_pol_ref[ch],
    s_spectrum            = s_pol_ref[ch],
    detector_max_counts   = detector_params.max_counts,
    saturation_threshold  = detector_params.saturation_threshold,
)
```
QC output keys: `dip_wavelength (nm)`, `dip_depth (%)`, `fwhm (nm)`.

**Result finalization:**
- Sets `result.success = True`
- Always: `ctrl.turn_off_channels()` in `finally` block (runs even on failure)

---

## 5. `LEDCalibrationResult` Schema

Key fields populated by orchestrator:

| Field | Type | Contents |
|-------|------|---------|
| `success` | bool | Overall pass/fail |
| `wave_data` | ndarray | Wavelength axis (ROI only, 560–720 nm) |
| `wave_min_index` | int | Pixel index for ROI start |
| `wave_max_index` | int | Pixel index for ROI end |
| `s_mode_intensity` | dict[str, int] | `{"a":int,...}` converged S-pol LEDs |
| `p_mode_intensity` | dict[str, int] | Converged P-pol LEDs |
| `s_integration_time` | float | S-pol integration time (ms) |
| `p_integration_time` | float | P-pol integration time (ms) |
| `num_scans` | int | Number of scans (computed from S-pol; applies to live acq) |
| `s_raw_data` | dict[str, ndarray] | S-pol reference spectra per channel (ROI) |
| `p_raw_data` | dict[str, ndarray] | P-pol reference spectra per channel (ROI) |
| `dark_s` | dict[str, ndarray] | Dark per channel (used for S reference subtraction) |
| `dark_p` | dict[str, ndarray] | Dark per channel (used for live P acquisition) |
| `s_pol_ref` | dict[str, ndarray] | Dark-subtracted S-pol references |
| `p_pol_ref` | dict[str, ndarray] | Dark-subtracted P-pol references |
| `transmission` | dict[str, ndarray] | Transmission spectra per channel |
| `qc_results` | dict[str, dict] | QC metrics per channel |
| `s_iterations` | int | Convergence iterations used for S-pol |
| `p_iterations` | int | Convergence iterations used for P-pol |
| `detector_serial` | str | Detector serial |
| `detector_max_counts` | float | Detector full-scale |
| `detector_saturation_threshold` | float | Saturation threshold from profile |
| `error` | str | Error message on failure |

---

## 6. Progress Percent Map

| Step | Percent |
|------|---------|
| Thread start | 5 |
| Step 2: Wavelength | 17 |
| Step 3: Model | 30 |
| Step 4: S-mode convergence | 45 |
| Step 5: P-mode convergence | 65 |
| Step 6: QC | 85 |
| Storing results | 95 |
| Done → `calibration_complete` | 100 |

With pump (P4PRO): pump progress maps 8–40%; optical maps 40–95% via `adjusted_pct = 40 + int(pct × 0.55)`.

---

## 7. Simple LED Calibration

Entry point: `CalibrationManager.handle_simple_led_calibration()` → `app._on_simple_led_calibration()`

- Does **not** move the servo
- Does **not** run the 6-step orchestrator
- Runs convergence only (fast LED intensity re-optimization)
- Used post-calibration when signal drifts (e.g., LED aging, temperature change)
- Referenced in the LED Convergence Engine doc as the "re-convergence" path

---

## 8. OEM LED Calibration

Entry point: `app._on_oem_led_calibration()` → `CalibrationService.start_calibration(force_oem_retrain=True)`

- Same 6-step flow but Step 3 **always** runs OEM model training
- Creates/overwrites `led_calibration_spr_processed_latest.json` in `OpticalSystem_QC/<serial>/spr_calibration/`
- Use case: new device, post-repair, LED replacement

---

## 9. Calibration Type Summary

| Type | Entry Point | Servo Movement | LED Model | Duration |
|------|------------|--------------|-----------|---------|
| Full Calibration | "Full Calibration" button | Yes (S then P) | Load or fail | ~3–5 min |
| OEM Calibration | "OEM LED Calibration" button | Yes | Retrain (~2 min) + load | ~10–15 min |
| Simple LED Cal | "Simple LED Calibration" button | No | Load (required) | ~30–60 s |
| Servo Calibration | Auto-triggered on block or "Servo Calibration" button | Yes (full scan) | N/A | ~2–3 min |

---

## 10. Key Gotchas

1. **Step 5 uses raw serial for servo motion.** `raw_ctrl._ser.write(b"sv...\n")` bypasses HAL. The rest of the orchestrator is HAL-compliant; Step 5 is the exception.

2. **Dark is captured at P-pol integration time.** Both `dark_s` and `dark_p` contain the same spectrum captured at `p_integration_time`. For S-pol calibration this is an approximation (typically acceptable since S and P integration times are similar).

3. **`num_scans`** is computed from S-pol integration time only (`floor(180 / s_integration_time)`, capped at 10) and applies to live acquisition. P-pol uses its own `num_scans_p` for reference capture only.

4. **P-pol failsafe does not raise.** Saturation or failed reference reads in Step 5 log warnings but let calibration complete. S-pol saturation raises.

5. **Servo positions in EEPROM must match device_config.** The orchestrator syncs `device_config → EEPROM` at the start of Step 3. If this sync fails (mismatch on readback), calibration raises. The `set_mode('ss')` command reads servo positions from controller EEPROM, not from `device_config` directly.

6. **Convergence engine is mandatory.** `use_convergence_engine=False` raises immediately. There is no legacy convergence fallback path.

7. **Pump optical calibration starts at cycle 4** (not the beginning) to maximize pipeline overlap — typically pump takes 3–4 minutes, optical takes 2–3 minutes.

8. **Retry counter max = 3.** After 3 failures, `_on_retry_calibration()` is blocked. User must close and reopen the dialog to retry.

9. **`_calibration_completed` flag.** Set to `True` only on full success. Used by `data_mgr` and main app to gate live acquisition start after calibration.
