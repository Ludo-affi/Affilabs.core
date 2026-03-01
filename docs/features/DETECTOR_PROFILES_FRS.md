# Detector Profiles — Functional Requirements Specification

**Source:** `detector_profiles/ocean_optics_flame_t.json`, `detector_profiles/ocean_optics_usb4000.json`
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

JSON-based hardware profiles that provide detector-specific parameters. Override deprecated constants in `settings.py` at runtime via `get_current_detector_profile()`. Each supported detector model has one profile file.

---

## 2. Supported Detectors

| Profile File | Detector Model |
|-------------|----------------|
| `ocean_optics_flame_t.json` | Flame-T (primary) |
| `ocean_optics_usb4000.json` | USB4000 (legacy) |

---

## 3. Schema (7 sections)

### 3.1 `detector_info`

| Field | Type | Example |
|-------|------|---------|
| `manufacturer` | string | `"Ocean Optics"` |
| `model` | string | `"Flame-T"` / `"USB4000"` |
| `serial_number` | string | `"FLMT00000"` (template) |
| `description` | string | Human-readable description |

### 3.2 `hardware_specs`

| Field | Type | Example |
|-------|------|---------|
| `pixel_count` | int | `3648` |
| `wavelength_range.min_nm` | float | `441.0` |
| `wavelength_range.max_nm` | float | `773.0` |
| `wavelength_range.calibration_coefficients` | string | `"Auto-detected"` |
| `detector_type` | string | `"CCD"` |
| `grating` | string | `"600 lines/mm"` |
| `slit_width_um` | int | `25` |

### 3.3 `acquisition_limits`

| Field | Flame-T | USB4000 | Purpose |
|-------|---------|---------|---------|
| `max_intensity_counts` | 65535 | 65535 | ADC max |
| `saturation_counts` | 65535 | 65535 | Saturation threshold |
| `min_integration_time_ms` | 1.0 | 1.0 | Minimum integration |
| `max_integration_time_ms` | 60.0 | 60.0 | Maximum integration |
| `recommended_integration_time_ms` | 10.0 | 10.0 | Default |
| `integration_step_ms` | 2.5 | *(absent)* | Flame-T only: step granularity |

### 3.4 `calibration_targets`

| Field | Flame-T | USB4000 | Purpose |
|-------|---------|---------|---------|
| `target_signal_counts` | 50000 | 55000 | LED calibration target |
| `signal_tolerance_counts` | 5000 | 5000 | Acceptable range |
| `dark_noise_scans` | 30 | 30 | Dark reference scans |
| `led_characterization_points` | [20,128,255] | [20,128,255] | LED response curve |
| `max_calibration_iterations` | 20 | 20 | Convergence limit |

### 3.5 `spr_settings`

| Field | Flame-T | USB4000 | Purpose |
|-------|---------|---------|---------|
| `wavelength_range_nm.min` | 560 | 580 | SPR window start |
| `wavelength_range_nm.max` | 720 | 720 | SPR window end |
| `expected_filtered_pixels` | 1591 | — | Expected pixel count in SPR range |
| `typical_spr_peak_range_nm.min` | 600 | 600 | Typical dip location |
| `typical_spr_peak_range_nm.max` | 680 | 680 | Typical dip location |

### 3.6 `performance`

| Field | Type | Example |
|-------|------|---------|
| `typical_snr` | int | `300` |
| `dark_noise_mean_counts` | int | `3500` |
| `dark_noise_std_counts` | int | `50` |
| `read_time_ms` | int | `100` |

### 3.7 `communication`

| Field | Flame-T | USB4000 |
|-------|---------|---------|
| `interface` | `"USB"` | `"USB"` |
| `driver` | `"SeaBreeze (USB4000)"` | `"SeaBreeze"` |
| `auto_detect_string` | `"FLMT"` | `"USB4"` |
| `auto_detect_method` | `"serial_number"` | `"serial_number"` |
| `vendor_id` | `"0x2457"` | `"0x2457"` |
| `product_id` | `"0x1002"` | `"0x1002"` |

---

## 4. Key Differences Between Detectors

| Parameter | Flame-T | USB4000 |
|-----------|---------|---------|
| Calibration target | 50,000 counts | 55,000 counts |
| SPR range start | 560 nm | 580 nm |
| Auto-detect serial prefix | `FLMT` | `USB4` |
| Integration step granularity | 2.5 ms | N/A |

---

## 5. Runtime Loading

Profiles are loaded at startup and accessed via `get_current_detector_profile()`. The detected detector's serial number prefix determines which profile to load. Profile values override the deprecated constants in `settings.py` (§3.6: `MIN_WAVELENGTH`, `MAX_WAVELENGTH`, etc.).

---

## 6. Adding a New Detector

1. Create `detector_profiles/<manufacturer>_<model>.json` following the schema above
2. Add auto-detect string to the profile's `communication.auto_detect_string`
3. The hardware scanner uses this string to match detected serial numbers to profiles
