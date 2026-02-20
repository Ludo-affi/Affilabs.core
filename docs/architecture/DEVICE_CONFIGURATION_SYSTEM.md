# Device Configuration System — Architecture Specification

**Document type:** Architecture Specification  
**Status:** Code-verified (Feb 19 2026)  
**Source files:**
- `affilabs/utils/device_configuration.py` (2078 lines — `DeviceConfiguration` class)
- `affilabs/managers/device_config_manager.py` (672 lines — `DeviceConfigManager` class)
- `affilabs/dialogs/device_config_dialog.py` — dialog for user-facing field entry

---

## 1. Purpose

The Device Configuration System provides **per-device persistent storage** of hardware identity, optical parameters, timing constants, and calibration results. Each physical unit (identified by spectrometer serial number) has its own `device_config.json` file. This JSON is the **single source of truth**; EEPROM is a portable backup that shadows the JSON.

---

## 2. File Layout

### Per-Device Config

```
config/
  devices/
    <SPECTROMETER_SERIAL>/
      device_config.json        ← primary per-device config
      optical_calibration.json  ← separate afterglow/optical calibration file (if run)
  device_config.json            ← default fallback (no serial known)
  device_config.json.backup_*   ← timestamped backups from the Oct 2025 migration
```

**Known serials in production (as of Feb 2026):**  
`FLMT09116`, `FLMT09788`, `FLMT09792`, `ST00012`, `ST00014`

`ST*` = Ocean Optics USB4000; `FLMT*` = Ocean Optics Flame-T.

### Default Fallback

If no `device_serial` is provided at init, the class uses `config/device_config.json`. This is the boot-time fallback before the spectrometer serial is known. All production flows must pass `device_serial` once the detector connects.

---

## 3. Config File Schema

The JSON is structured into five top-level sections:

```json
{
  "device_info": { ... },
  "hardware":    { ... },
  "timing_parameters": { ... },
  "frequency_limits":  { ... },
  "calibration": { ... },
  "maintenance": { ... }
}
```

Plus ephemeral sections that may appear from subsystems:
- `"led_calibration"` — written by convergence engine (dark snapshots, model slopes, LED targets)
- `"oem_calibration"` — written by OEM calibration workflow  
- `"optical_calibration"` — referenced via separate `optical_calibration.json` file

### 3.1 `device_info`

| Field | Type | Notes |
|-------|------|-------|
| `config_version` | str | `"1.0"` |
| `created_date` | ISO datetime | Set on first creation |
| `last_modified` | ISO datetime | Updated on every `save()` |
| `device_id` | str or null | User-defined label; defaults to spectrometer serial |

### 3.2 `hardware`

| Field | Type | Valid Values | Notes |
|-------|------|-------------|-------|
| `led_pcb_model` | str | `"luminus_cool_white"`, `"osram_warm_white"` | LED chip type |
| `led_type_code` | str | `"LCW"`, `"OWW"` | Short code, kept in sync with `led_pcb_model` |
| `led_pcb_serial` | str or null | — | Optional LED board serial |
| `spectrometer_model` | str | `"Flame-T"`, `"USB4000"` | |
| `spectrometer_serial` | str or null | `FLMT*`, `ST*` | Primary device identifier |
| `controller_model` | str | see table | Human-readable model name |
| `controller_type` | str | `"Arduino"`, `"PicoP4SPR"`, `"PicoEZSPR"`, `"PicoP4PRO"`, `"PicoP4PROPLUS"` | Programmatic type |
| `controller_serial` | str or null | — | Optional |
| `optical_fiber_diameter_um` | int | `100`, `200` | µm |
| `polarizer_type` | str | `"barrel"`, `"round"` | barrel = 2 fixed windows; round = continuous rotation |
| `servo_model` | str | `"HS-55MG"`, `"Alternate"` | |
| `servo_s_position` | int or null | 1–255 (PWM) | **MUST be calibrated. No default.** |
| `servo_p_position` | int or null | 1–255 (PWM) | **MUST be calibrated. No default.** |

> **Critical:** Servo positions are stored in **PWM units (1–255)**, not degrees. See `SERVO_POSITIONS_CLEAN.md` for the PWM mapping.

**Controller model strings:**

| `controller_type` | `controller_model` |
|-------------------|--------------------|
| `"Arduino"` | `"Arduino P4SPR"` |
| `"PicoP4SPR"` | `"Raspberry Pi Pico P4SPR"` |
| `"PicoEZSPR"` | `"Raspberry Pi Pico EZSPR"` |
| `"PicoP4PRO"` | `"pico_p4pro"` |
| `"PicoP4PROPLUS"` | `"pico_p4proplus"` |

**Polarizer type by controller:**

| Controller | Polarizer |
|-----------|-----------|
| Arduino P4SPR | always `"round"` |
| PicoP4SPR | always `"round"` |
| PicoEZSPR | typically `"barrel"` |
| PicoP4PRO / PROPLUS | user-defined |

> **Rule:** `polarizer_type` is **NEVER auto-set by hardware detection**. Only the user (via dialog or explicit call) sets it. `_sync_controller_from_hardware()` explicitly skips this field.

### 3.3 `timing_parameters`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `led_off_period_ms` | float | 5.0 | LED transition time between channels |
| `detector_wait_before_ms` | float | 35.0 | Wait for LED to stabilize before acquisition |
| `detector_window_ms` | float | 210.0 | Spectrum acquisition window |
| `detector_wait_after_ms` | float | 5.0 | Gap after acquisition completes |
| `led_a_delay_ms` – `led_d_delay_ms` | float | 0 | Per-channel fine-tuning delays (future use) |
| `min_integration_time_ms` | float | 50 | Minimum safe integration time |
| `led_rise_fall_time_ms` | float | 5 | LED stabilization time |
| `pre_led_delay_ms` | float | 35.0 | **DEPRECATED** — maps to `detector_wait_before_ms` |
| `post_led_delay_ms` | float | 5.0 | **DEPRECATED** — maps to `led_off_period_ms` |

Timing values are read from `settings.py` constants as fallback (`LED_OFF_PERIOD_MS`, `DETECTOR_WAIT_BEFORE_MS`, etc.) when the JSON field is absent.

**Per-channel cycle time:**  
`led_off + detector_wait + detector_window + detector_after` = nominal cycle time per channel

### 3.4 `frequency_limits`

| Field | Default | Notes |
|-------|---------|-------|
| `4_led_target_hz` | 1.0 | Target acquisition frequency for 4-LED mode |

### 3.5 `calibration`

| Field | Type | Notes |
|-------|------|-------|
| `dark_calibration_date` | ISO or null | Date of last dark subtraction calibration |
| `s_mode_calibration_date` | ISO or null | Date of last S-pol reference calibration |
| `p_mode_calibration_date` | ISO or null | Date of last P-pol calibration |
| `polarizer_calibration_date` | ISO or null | Date of last servo calibration |
| `polarizer_extinction_ratio_percent` | float or null | `(S-P)/S` in best bucket |
| `factory_calibrated` | bool | True if any non-zero LED intensities were set from EEPROM or OEM flow |
| `user_calibrated` | bool | True after any user-initiated s_mode or p_mode calibration |
| `preferred_calibration_mode` | str | `"global"` or `"per_channel"` |
| `integration_time_ms` | float or null | Calibrated integration time from LED convergence |
| `num_scans` | int or null | Calibrated number of scans to average |
| `led_intensity_a` – `led_intensity_d` | int | Calibrated LED intensities (0–255) |
| `spr_model_path` | str or null | Path to `led_calibration_spr_processed_latest.json` |
| `spr_model_calibration_date` | ISO or null | Date of last SPR model generation |

### 3.6 `maintenance`

| Field | Default | Notes |
|-------|---------|-------|
| `last_maintenance_date` | null | |
| `total_measurement_cycles` | 0 | Incremented by usage tracking |
| `led_on_hours` | 0.0 | Accumulated LED-on time |
| `next_maintenance_due` | Nov of current/next year | Set at creation time |

---

## 4. Initialization Flow

```
DeviceConfigManager.initialize_device_config(device_serial)
  │
  ├─ Resolve controller reference from hardware_mgr._ctrl_raw
  │
  └─ DeviceConfiguration(device_serial=serial, controller=ctrl)
       │
       ├─ Resolve config path:
       │    device_serial given → config/devices/<serial>/device_config.json
       │    no serial           → config/device_config.json  (fallback, warns)
       │
       ├─ _load_or_create_config()
       │    ┌─ JSON exists? → load + _merge_with_defaults()
       │    │    └─ loaded_from_eeprom = False, created_from_scratch = False
       │    │
       │    └─ JSON missing → _try_load_from_eeprom_or_default()
       │         ├─ controller.is_config_valid_in_eeprom() == True?
       │         │    └─ _create_config_from_eeprom(eeprom_config)
       │         │         loaded_from_eeprom = True → auto-save JSON on __init__ exit
       │         │
       │         └─ no EEPROM → _create_partial_config_with_known_info()
       │              created_from_scratch = True → triggers OEM workflow
       │
       └─ _sync_controller_from_hardware()  [best-effort, never fails init]
            └─ Updates controller_model + controller_type from live firmware
               NEVER touches polarizer_type
```

After `DeviceConfiguration.__init__`:
- `self.loaded_from_eeprom = True` → auto-called `save()` (JSON created from EEPROM)
- `self.created_from_scratch = True` → `DeviceConfigManager` logs OEM workflow notice; triggers `start_oem_calibration_workflow()`
- Otherwise → logged success; servo positions auto-loaded into sidebar

---

## 5. Controller Sync (`_sync_controller_from_hardware`)

Called on every `__init__` when `controller` is not None. Detects `controller_type` and `controller_model` from `controller.name` and `controller.firmware_id`:

| Detection string | Sets `controller_type` | Sets `controller_model` |
|-----------------|----------------------|------------------------|
| `"arduino"` or `name == "p4spr"` | `"Arduino"` | `"Arduino P4SPR"` |
| `"pico_p4spr"` or `"picop4spr"` | `"PicoP4SPR"` | `"Raspberry Pi Pico P4SPR"` |
| `"pico_p4pro"` / `"p4pro"` in firmware | `"PicoP4PRO"` or `"PicoP4PROPLUS"` | `"pico_p4pro"` / `"pico_p4proplus"` |
| `"pico_ezspr"` or `"picoezspr"` | `"PicoEZSPR"` | `"Raspberry Pi Pico EZSPR"` |

P4PROPLUS is detected by `"p4proplus" in firmware_id` or `controller.has_internal_pumps()` returning `True`. If detection changes `controller_model` or `controller_type`, `save()` is called immediately to persist the correction.

> **Note:** `hardware_mgr._ctrl_raw` (raw controller) must be passed — not `hardware_mgr.ctrl` (HAL adapter) — so `firmware_id` is accessible.

---

## 6. Config Load Priority

```
1. JSON file  (config/devices/<serial>/device_config.json)
2. EEPROM     (controller.read_config_from_eeprom())
3. Partial    (_create_partial_config_with_known_info())
```

On every load, `_merge_with_defaults()` deep-merges the loaded dict into a fresh `DEFAULT_CONFIG` copy, ensuring new fields introduced in code updates are populated with defaults without overwriting user values. Sections not in `DEFAULT_CONFIG` (e.g., `oem_calibration`, `led_calibration`) are **preserved** by the merge.

---

## 7. Missing Field Validation

`DeviceConfigManager.check_missing_config_fields()` checks three required fields:

| Field | Missing if |
|-------|-----------|
| `hardware.led_pcb_model` | falsy |
| `hardware.controller_type` AND `hardware.controller_model` | both falsy |
| `hardware.optical_fiber_diameter_um` | falsy |

> `polarizer_type` is **not** in the missing check — it has a coded default of `"barrel"` for backward compatibility. Servo positions are also not checked here; they are validated separately by the calibration system.

If missing fields exist, `DeviceConfigManager.prompt_device_config()` opens `DeviceConfigDialog`.

---

## 8. Device Config Dialog

`DeviceConfigDialog` collects:
- LED model (LCW / OWW combo)
- Controller type (combo: Arduino, PicoP4SPR, PicoEZSPR, PicoP4PRO, PicoP4PROPLUS)
- Fiber diameter (A = 100 µm / B = 200 µm)
- Polarizer type (combo)
- Device ID (free text, defaults to serial)

On `Accept`, the manager:
1. Updates `hardware.*` fields in `device_config.config`
2. Sets `led_type_code` from `led_pcb_model`
3. Calls `device_config.save()`
4. If no missing fields remain → calls `start_oem_calibration_workflow()`

---

## 9. OEM Calibration Workflow

Triggered when `created_from_scratch=True` and all required fields are set. Runs in a `daemon=True` background thread:

```
Step 1: app._run_servo_auto_calibration()
         → finds optimal S/P servo positions
         → saves to device_config.json via calibration system

Step 2: device_config.reload()
         → re-reads JSON to pick up updated servo positions

Step 3: app._on_simple_led_calibration()
         → LED convergence engine runs
         → calibrates LED intensities + integration time

Step 4: Pull results from data_mgr.leds_calibrated, integration_time_ms, num_scans
         → write to device_config.calibration section
         → set spr_model_path if OpticalSystem_QC/<serial>/spr_calibration/... exists
         → device_config.save()

Step 5: device_config.sync_to_eeprom(controller)
         → EEPROM now mirrors current JSON

Step 6: data_mgr.start_acquisition()
         → return to live view
```

All steps run in sequence in one thread. Each step logs progress. `show_message()` dialogs inform the user at key milestones. Any exception stops the workflow and shows an error dialog.

---

## 10. EEPROM Synchronization

`sync_to_eeprom(controller)` extracts a subset of `device_config` for EEPROM storage:

| EEPROM field | Source |
|-------------|--------|
| `led_pcb_model` | `hardware.led_pcb_model` |
| `controller_type` | derived from controller instance type string |
| `fiber_diameter_um` | `hardware.optical_fiber_diameter_um` |
| `polarizer_type` | `hardware.polarizer_type` |
| `servo_s_position` | `hardware.servo_s_position` |
| `servo_p_position` | `hardware.servo_p_position` |
| `led_intensity_a–d` | `calibration.led_intensity_a–d` |
| `integration_time_ms` | `calibration.integration_time_ms` |
| `num_scans` | `calibration.num_scans` |

`None` values are converted to hardware-safe defaults (`0` for intensities, `10`/`100` for servo, `100`/`3` for integration/scans) before writing.

`save(auto_sync_eeprom=True)` triggers EEPROM sync automatically after writing the JSON. Called explicitly by the OEM workflow; not set on routine saves.

---

## 11. Key Getters Used by Other Systems

| Method | Returns | Caller |
|--------|---------|--------|
| `get_servo_positions()` | `{"s": int, "p": int}` or `None` | `DeviceConfigManager.initialize_device_config()` → sidebar auto-load |
| `get_led_intensities()` | `{"a":int,"b":int,"c":int,"d":int}` | sidebar auto-load, convergence engine |
| `get_integration_time()` | `float or None` | convergence engine, calibration |
| `get_num_scans()` | `int or None` | calibration service |
| `get_polarizer_type()` | `"barrel"` or `"round"` | servo calibration, hardware manager |
| `get_timing_tracks()` | dict of 4 timing floats | timing calculations |
| `get_calibration_mode()` | `"global"` or `"per_channel"` | LED convergence engine |
| `get_spr_model_path()` | `str or None` | ML predictor loading |
| `is_factory_calibrated()` | `bool` | calibration service gating |
| `is_user_calibrated()` | `bool` | UI calibration status display |

---

## 12. Reference Sharing Pattern

After `DeviceConfigManager.initialize_device_config()` completes, the **same `DeviceConfiguration` instance** is pushed to three references:

```python
self.device_config             # DeviceConfigManager own ref
main_window.device_config      # main.py access
sidebar.device_config          # S/P position inputs
hardware_mgr.device_config     # hardware layer access
```

All callers share one object. Mutating any section and calling `save()` persists changes globally. There is no event or signal fired when the config changes — consumers read directly.

---

## 13. Validation

`DeviceConfiguration.validate()` checks:
- `led_pcb_model` in `["luminus_cool_white", "osram_warm_white"]`
- `optical_fiber_diameter_um` in `[100, 200]`
- `polarizer_type` in `["barrel", "round"]`
- `min_integration_time_ms` between 1–1000
- `frequency_limits.4_led_max_hz` between 0–10

Returns `(is_valid: bool, errors: list[str])`. Not called automatically; must be invoked explicitly (e.g., from UI or tests).

---

## 14. `optical_calibration.json` (Separate File)

The afterglow/optical calibration data lives in a **separate file** in the same device directory:

```
config/devices/<serial>/optical_calibration.json
```

This file contains per-channel, per-integration-time exponential decay fit data used by the afterglow correction pipeline. It is written by `run_afterglow_calibration.py` and read by the afterglow correction service. The `device_config.json` `optical_calibration.afterglow_correction_enabled` flag gates whether the correction is applied.

---

## 15. Key Gotchas

1. **Servo positions are PWM units, not degrees.** Values 1–255. The UI may label them "degrees" colloquially but the stored and firmware values are PWM.
2. **`polarizer_type` is never auto-detected.** It is user-defined only. Hardware sync explicitly skips it.
3. **`_ctrl_raw` not `ctrl.`** The raw controller (not HAL adapter) must be passed to `DeviceConfiguration.__init__()` so `firmware_id` is accessible for P4PRO/PROPLUS disambiguation.
4. **`_merge_with_defaults` preserves unknown sections.** Loading an old config file will not strip `oem_calibration`, `led_calibration`, or other non-default sections — they are preserved by the merge.
5. **`"circular"` vs `"round"` mismatch.** Some on-disk JSON files (e.g., FLMT09788, ST00014) have `"polarizer_type": "circular"` — this pre-dates the `VALID_POLARIZER_TYPES = ["barrel", "round"]` constraint. Validation will flag these as invalid. A data migration is needed for these files.
6. **`integration_time_ms` in `calibration` is the convergence-selected time**, not the `timing_parameters.detector_window_ms`. They serve different purposes: one is the spectrometer exposure time, the other is the firmware acquisition window.
7. **4-LED-only system.** `VALID_LED_MODES = [4]` — the code only supports 4 LEDs. The `frequency_limits` section only has `4_led_*` keys; any call to `get_frequency_limits(num_leds)` with a value other than 4 raises `ValueError`.
