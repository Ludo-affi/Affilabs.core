# Spectroscopy Presenter — Functional Requirements Specification

**Source:** `affilabs/presenters/spectroscopy_presenter.py` (280 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Pure presenter for the transmission spectrum and raw spectrum plots. Updates plots with per-channel spectral data. Handles wavelength filtering for noisy detector regions.

---

## 2. Class

**`SpectroscopyPresenter`**

### Constructor
```python
def __init__(self, main_window)
```
Stores `main_window` ref, init flags, channel mapping.

---

## 3. Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `set_detector_info` | `(detector_serial=None, detector_type=None)` | Sets detector info for wavelength filtering (Phase Photonics noisy below 570 nm) |
| `check_plots_available` | `() -> bool` | Checks `transmission_curves` and `raw_data_curves` exist on main_window; logs once if missing |
| `update_transmission` | `(channel: str, wavelengths: np.ndarray, transmission: np.ndarray)` | Filters wavelengths, updates `transmission_curves[idx]`. Fallback: `sidebar.update_transmission_plot()` |
| `update_raw_spectrum` | `(channel: str, wavelengths: np.ndarray, raw_spectrum: np.ndarray)` | Filters wavelengths, updates `raw_data_curves[idx]`. Fallback: `sidebar.update_raw_data_plot()` |
| `clear_transmission` | `(channel: str = None)` | Clears one or all transmission curves |
| `clear_raw_spectrum` | `(channel: str = None)` | Clears one or all raw curves |
| `clear_all` | `()` | Clears both + resets `_first_update_logged` |

---

## 4. Channel Mapping

```python
{"a": 0, "b": 1, "c": 2, "d": 3}
```

**Note:** Keys are **lowercase** (unlike SensogramPresenter which uses uppercase).

---

## 5. Wavelength Filtering

Uses `filter_valid_wavelength_data()` from `detector_config` to remove noisy data below 570 nm for Phase Photonics detectors. Applied on every update call.

---

## 6. Dual Access Path

Each update method has two paths:
1. **Direct**: `transmission_curves[idx].setData(wavelengths, data)` on main_window
2. **Fallback**: `sidebar.update_transmission_plot(channel, wavelengths, data)` if direct curves unavailable

---

## 7. Key Patterns

- **No signals/slots** — pure presentation, no QObject inheritance
- **First-update logging**: logs first transmission update per channel at INFO level for diagnostics
- **Detector-aware**: Phase Photonics detector gets additional wavelength filtering below 570 nm
