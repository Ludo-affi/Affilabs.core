# SPR Signal Processing Pipeline — Functional Specification

**Version:** 2.0.5 beta  
**Verified against source:** Yes (all code references checked against live files)  
**Last updated:** 2026-02-18  
**Scope:** Live acquisition processing path from raw detector counts to resonance wavelength

---

## 1. Overview

The signal processing pipeline converts raw spectrometer counts (from HAL `read_roi()`) into a resonance wavelength in nanometers, which forms the Y-axis of the sensorgram. This pipeline runs once per LED channel per acquisition cycle.

There are **two contexts** in which this pipeline runs:

| Context | Caller | Purpose | Dark reference source |
|---------|--------|---------|----------------------|
| **Live acquisition** | `SpectrumProcessor.process_spectrum()` | Sensorgram Y-axis | `CalibrationData.dark_p[ch]` |
| **Calibration QC** | `calibration_orchestrator.py` | Step 5 QC display | `calibration_data.dark_p/dark_s` |

Both contexts share `TransmissionProcessor` and the active pipeline. The calibration path additionally calls `calculate_transmission_qc()` for FWHM and dip-depth reporting.

---

## 2. Complete Processing Chain

```
Hardware: spectrometer ROI (raw counts, already wavelength-calibrated by HAL)
  │
  ▼
[Stage 1] SpectrumPreprocessor.process_polarization_data()
  │   Dark subtraction — P-pol, then S-pol separately
  │   Output: clean_p_pol, clean_s_pol (ndarray, same length)
  │
  ▼
[Stage 2] SpectrumProcessor.process_spectrum()  ← live acquisition entry point
  │   LED-on guard (raw_peak < dark_peak × 3.0 → warning)
  │   Dark ref resolution (dark_p[ch] preferred; fallback dark_noise)
  │   Calls Stage 1 (dark subtraction)
  │   Calls Stage 3 (transmission calculation)
  │   Finds minimum_hint_nm (argmin in SPR region)
  │   Returns dict: {intensity, raw_spectrum, transmission_spectrum,
  │                   peak_input, minimum_hint_nm}
  │
  ▼
[Stage 3] TransmissionProcessor.process_single_channel()
  │   Step 1: P/S ratio  →  (clean_p / max(clean_s, 1)) × 100.0
  │   Step 2: Savitzky-Golay filter (window=11, polyorder=3)
  │           [skipped if apply_sg_filter=False or len < 11]
  │   Output: transmission spectrum (%)
  │
  ▼
[Stage 4] FourierPipeline.find_resonance_wavelength()
  │   Operate on SPR region only (detector-specific nm range)
  │   DST with linear detrending + Fourier weights for denoising
  │   IDCT → derivative signal
  │   Zero-crossing search near minimum_hint_nm
  │   Linear regression refinement (±7.3 nm window)
  │   Output: resonance wavelength (nm) or np.nan
  │
  ▼
Resonance wavelength → SensogramPresenter → sensorgram Y-axis
```

---

## 3. Stage 1 — Dark Subtraction (`SpectrumPreprocessor`)

**Source:** `affilabs/core/spectrum_preprocessor.py`

### 3.1 `process_polarization_data(raw_spectrum, dark_noise, channel_name, verbose)`

Performs dark subtraction for a single polarization mode on one channel.

```
clean_spectrum = raw_spectrum.copy()
clean_spectrum = clean_spectrum - dark_noise
```

**Critical constraint — strict length check:**
```python
if len(dark_noise) != len(clean_spectrum):
    raise ValueError(
        f"Dark noise length {len(dark_noise)} != spectrum length {len(clean_spectrum)}. "
        "ROI mismatch — verify HAL read_roi() returns same slice as calibration."
    )
```
This will fire if the ROI pixel range changes between calibration and live acquisition.

### 3.2 `process_batch_channels(raw_spectra, dark_noise, ch_list)`

Calls `process_polarization_data()` per channel in sequence. Used in calibration context.

---

## 4. Stage 2 — Live Acquisition Orchestration (`SpectrumProcessor`)

**Source:** `affilabs/core/spectrum_processor.py`

### 4.1 Entry Point

```python
result_dict = spectrum_processor.process_spectrum(channel, spectrum_data)
# spectrum_data = {"wavelength": ndarray, "raw_intensity": ndarray}
# channel       = "a" | "b" | "c" | "d"
```

Returns `None` on any fatal guard failure, or a dict on success.

### 4.2 Guard Chain

| Guard | Condition | Action |
|-------|-----------|--------|
| None check | `raw_intensity is None` | Return `None` |
| Empty check | `len(raw_intensity) == 0` | Return `None` |
| All-zero check | `np.all(raw_intensity == 0)` | Return `None` |
| ROI legacy fallback | Data not already ROI-sliced | Slice to ROI (legacy guard, should not fire with HAL `read_roi()`) |
| LED-on guard | `raw_peak < dark_peak × 3.0` | Log warning, continue |

**LED-on guard dark peak:**
- `dark_peak = max(calibration_data.dark_p[channel])` (preferred)
- Fallback if no calibration dark: `dark_peak = 3000` counts

### 4.3 Dark Reference Resolution

| Priority | Source | Condition |
|----------|--------|-----------|
| 1st | `calibration_data.dark_p[channel]` | Always tried first |
| 2nd | `calibration_data.dark_noise` (legacy, with ROI slice) | Fallback if dark_p unavailable |

### 4.4 SPR Region Minimum Hint

After `TransmissionProcessor` returns, `process_spectrum()` calculates:
```python
spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)
spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
minimum_hint_nm = wavelengths[spr_mask][np.argmin(transmission[spr_mask])]
```

This hint is forwarded to `FourierPipeline` to anchor the zero-crossing search.

### 4.5 Transmission Fallback

If `TransmissionProcessor` returns `None`, empty array, all-NaN, or all-zeros:
```python
peak_input = intensity  # Use dark-subtracted P-pol intensity directly
```

### 4.6 Return Dict

```python
{
    "intensity":             ndarray,  # Dark-subtracted P-pol (=peak_input when transmission OK)
    "raw_spectrum":          ndarray,  # Raw P-pol before dark subtraction
    "transmission_spectrum": ndarray,  # Transmission % (Stage 3 output)
    "peak_input":            ndarray,  # Input to FourierPipeline (= transmission, or fallback intensity)
    "minimum_hint_nm":       float,    # argmin wavelength in SPR region
}
```

**Note:** `"wavelength"` is intentionally absent from the return dict — the key would shadow the resonance wavelength output from the pipeline.

---

## 5. Stage 3 — Transmission Calculation (`TransmissionProcessor`)

**Source:** `affilabs/core/transmission_processor.py`

### 5.1 `process_single_channel(...)` — Signature

```python
TransmissionProcessor.process_single_channel(
    p_pol_clean:              np.ndarray,      # CLEAN P-pol (dark subtracted)
    s_pol_ref:                np.ndarray,      # CLEAN S-pol reference (dark subtracted)
    led_intensity_s:          int = 200,       # S-mode LED intensity (counts)
    led_intensity_p:          int = 255,       # P-mode LED intensity (counts)
    wavelengths:              np.ndarray|None, # For logging and off-SPR baseline
    apply_sg_filter:          bool = True,
    baseline_method:          str = "percentile",
    baseline_percentile:      float = 95.0,
    baseline_polynomial_degree: int = 2,
    off_spr_wavelength_range: tuple|None = None,
    verbose:                  bool = False,
) -> np.ndarray
```

**Call site defaults (live acquisition):**
```python
TransmissionProcessor.process_single_channel(
    apply_sg_filter=True,
    baseline_method="percentile",
    baseline_percentile=95.0,
)
```

### 5.2 Processing Steps

**Step 1 — P/S ratio:**
```python
s_pol_safe = np.where(s_pol_ref < 1, 1, s_pol_ref)   # Clamp denominator
transmission = (p_pol_clean / s_pol_safe) * 100.0      # Percentage
```

**Step 2 — Savitzky-Golay smoothing (default: on):**
```python
from scipy.signal import savgol_filter
transmission = savgol_filter(transmission, window_length=11, polyorder=3)
```
Skipped if `apply_sg_filter=False` or `len(transmission) < 11`.

**Important mismatch between docstring and code:**  
The docstring lists LED boost correction (`P_LED / S_LED`), polynomial/percentile/off_spr baseline correction, and 0–100% clipping as steps 2–4. These parameters exist in the signature but **the implemented code path only does P/S ratio + SG filter**. The `baseline_method` parameter and `led_intensity_*` parameters are accepted but not applied in `process_single_channel()`. The `diagnose_spectral_tilt()` method is a separate QC diagnostic that is not part of the live pipeline.

### 5.3 SPR Region Wavelength Ranges

From `affilabs/utils/detector_config.get_spr_wavelength_range()`:

| Detector | SPR min (nm) | SPR max (nm) |
|----------|-------------|-------------|
| Ocean Optics (default) | 560 | 720 |
| Phase Photonics / USB4000 | 570 | 720 |

These same ranges are used by `SpectrumProcessor` for `minimum_hint_nm` and by `FourierPipeline` for the operating region.

---

## 6. Stage 4 — Fourier Peak Detection (`FourierPipeline`)

**Source:** `affilabs/utils/pipelines/fourier_pipeline.py`  
**Status:** Only registered/active pipeline (registered in `affilabs/utils/pipelines/__init__.py`)

### 6.1 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `alpha` | `9000` | Fourier regularization strength (higher = stronger denoising) |
| `target_window_nm` | `7.3` | Linear regression window half-width (nm) for zero-crossing refinement |

Parameters can be overridden via `settings/pipeline_config.json`.

### 6.2 Algorithm

```
Input: transmission (full array), wavelengths (full array), minimum_hint_nm, detector_serial
```

**Step 1 — Restrict to SPR region:**
```python
spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
spr_wavelengths = wavelengths[spr_mask]
spr_transmission = transmission[spr_mask]
```

**Step 2 — Locate hint index:**  
Map `minimum_hint_nm` to nearest index in `spr_wavelengths`. If no hint provided: fallback to `argmin(spr_transmission)`.

**Step 3 — Calculate Fourier weights:**  
For SPR region of length `n`:
```python
n_inner = n - 1
phi = π / n_inner * np.arange(1, n_inner)
phi2 = phi²
weights = phi / (1 + alpha × phi2 × (1 + phi2))
```
Higher-frequency components are down-weighted by `alpha`. At `alpha=9000`, high-frequency noise is strongly suppressed while the broad SPR dip shape is preserved.

**Step 4 — DST with detrending:**
```python
fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])          # DC
detrended = spectrum[1:-1] - linspace(spectrum[0], spectrum[-1], n)[1:-1]
fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)     # Apply weights
```

**Step 5 — IDCT derivative:**
```python
derivative = idct(fourier_coeff, 1)
```
The SPR dip minimum corresponds to a zero-crossing of the derivative.

**Step 6 — Zero-crossing search:**
```python
search_window = min(int(len(derivative) * 0.15), len(derivative) // 4)
# ~15% of SPR pixels, bounded by ¼ of array
# Phase Photonics ~750 SPR pixels → ±112 pts
# Ocean Optics ~1500 SPR pixels → ±225 pts
search_region = derivative[hint_index - search_window : hint_index + search_window]
zero_local = search_region.searchsorted(0)   # Binary search for sign change
```

**Step 7 — Linear regression refinement:**
```python
wavelength_spacing = (spr_wavelengths[-1] - spr_wavelengths[0]) / (len(spr_wavelengths) - 1)
window_size = int(target_window_nm / wavelength_spacing)  # ≈ 7.3nm / spacing
line = linregress(spr_wavelengths[zero - window_size : zero + window_size],
                  derivative [zero - window_size : zero + window_size])
fit_lambda = -line.intercept / line.slope
```

**Step 8 — Boundary validation:**
```python
if fit_lambda < spr_min or fit_lambda > spr_max:
    fit_lambda = spr_wavelengths[hint_index]  # Fall back to hint wavelength
```

### 6.3 Disabled Feature: SNR Weighting

`_calculate_snr_weights()` exists and is documented but is **disabled per user request**. When active, it would weight regions with higher S-pol intensity more heavily during DST processing. It is not called anywhere in the live pipeline.

### 6.4 AbstractBase / Registry Architecture

```
ProcessingPipeline (ABC)
├── calculate_transmission()     [abstract]
├── find_resonance_wavelength()  [abstract]
├── get_metadata()              [abstract]
└── process()                   [concrete — calls calculate_transmission + find_resonance_wavelength]

FourierPipeline(ProcessingPipeline)   ← ONLY registered pipeline
```

Registry (`PipelineRegistry` singleton in `processing_pipeline.py`) persists the selected pipeline to `settings/pipeline_config.json`. UI can switch pipelines dynamically. The other 8 pipeline files (`centroid`, `polynomial`, `hybrid`, `consensus`, `adaptive_multifeature`, etc.) exist in `affilabs/utils/pipelines/` but are **not registered** — they are development artifacts.

---

## 7. Calibration QC Path — `calculate_transmission_qc()`

**Source:** `affilabs/core/transmission_processor.py`

Called by the calibration orchestrator at Step 5 (QC display only — does not affect calibration acceptance/rejection).

### 7.1 Signature

```python
TransmissionProcessor.calculate_transmission_qc(
    transmission_spectrum: np.ndarray,
    wavelengths:           np.ndarray,
    channel:               str,              # 'a'|'b'|'c'|'d'
    p_spectrum:            np.ndarray|None,  # For P/S ratio + saturation check
    s_spectrum:            np.ndarray|None,  # For P/S ratio + saturation check
    detector_max_counts:   float = 65535,    # Consumed but reserved — not used
    saturation_threshold:  float = 62259,    # 95% of max
) -> dict
```

### 7.2 Return Dict

```python
{
    "fwhm":               float|None,  # FWHM in nm
    "dip_detected":       bool,        # dip_depth > 5.0%
    "transmission_min":   float,       # Minimum transmission %
    "dip_wavelength":     float,       # nm at minimum
    "dip_depth":          float,       # 100.0 - transmission_min
    "ratio":              float|None,  # Mean P/S in ±20nm ROI around dip
    "orientation_correct":bool|None,   # True / False / None (indeterminate)
    "status":             str,         # "[OK] PASS" | "[ERROR] FAIL" | "[WARN] WARNING"
    "fwhm_quality":       str,         # "excellent" | "good" | "acceptable" | "poor" | "unknown"
    "warnings":           list[str],   # Warning messages
    "s_saturated":        bool,        # S-pol max >= saturation_threshold
    "p_saturated":        bool,        # P-pol max >= saturation_threshold
    "s_max_counts":       float|None,
    "p_max_counts":       float|None,
    "overall_pass":       bool,        # Added during processing (not in initial dict)
}
```

### 7.3 FWHM Quality Thresholds

FWHM quality is assessed relative to dip depth (deeper dip = more tolerance for wider FWHM):

| Dip depth | Excellent | Good | Acceptable | Poor |
|-----------|-----------|------|-----------|------|
| > 70% | FWHM < 80 nm | — | else | — |
| 50–70% | FWHM < 75 nm | FWHM < 85 nm | else | — |
| 30–50% | — | FWHM < 60 nm | FWHM < 70 nm | else |
| < 30% | — | — | FWHM < 50 nm | else |

FWHM: half-max threshold = `(100.0 + transmission_min) / 2.0`

### 7.4 P/S Ratio Orientation Check

| Ratio | `orientation_correct` | Interpretation |
|-------|-----------------------|----------------|
| ≥ 1.15 | `False` | Polarizer may be inverted |
| 0.95 – 1.15 | `None` | Indeterminate |
| 0.10 – 0.95 | `True` | Correct (P absorbed by SPR, so P < S) |
| < 0.10 | `None` | Unusual — verify sensor |

### 7.5 Overall PASS/FAIL Logic

```python
passed = (
    dip_detected                          # dip_depth > 5%
    and fwhm is not None and fwhm < 100.0
    and orientation_correct is not False
    and not s_saturated
    and not p_saturated
)

failed = (
    not dip_detected
    or (fwhm is not None and fwhm >= 120.0)
    or orientation_correct is False
    or s_saturated
    or p_saturated
)
# If neither passed nor failed: status = "[WARN] WARNING"
```

---

## 8. Pipeline Registry Architecture

**Source:** `affilabs/utils/processing_pipeline.py`, `affilabs/utils/pipelines/__init__.py`

### 8.1 DataClasses

```python
@dataclass
class PipelineMetadata:
    name:        str
    description: str
    version:     str
    author:      str
    parameters:  dict[str, Any]

@dataclass
class ProcessingResult:
    transmission:         np.ndarray
    resonance_wavelength: float
    metadata:             dict[str, Any]
    success:              bool = True
    error_message:        str|None = None
```

### 8.2 Abstract Interface

```python
class ProcessingPipeline(ABC):
    def calculate_transmission(intensity, reference) -> np.ndarray: ...
    def find_resonance_wavelength(transmission, wavelengths, **kwargs) -> float: ...
    def get_metadata() -> PipelineMetadata: ...
    def process(intensity, reference, wavelengths, **kwargs) -> ProcessingResult: ...  # concrete
```

### 8.3 Registered Pipelines

| ID | Class | File | Status |
|----|-------|------|--------|
| `"fourier"` | `FourierPipeline` | `fourier_pipeline.py` | **ACTIVE (only one)** |
| — | `CentroidPipeline` | `centroid_pipeline.py` | Exists, not registered |
| — | `PolynomialPipeline` | `polynomial_pipeline.py` | Exists, not registered |
| — | `HybridPipeline` | `hybrid_pipeline.py` | Exists, not registered |
| — | `ConsensusPipeline` | `consensus_pipeline.py` | Exists, not registered |
| — | `AdaptiveMultifeaturePipeline` | `adaptive_multifeature_pipeline.py` | Exists, not registered |
| — | `BatchSavgolPipeline` | `batch_savgol_pipeline.py` | Exists, not registered |
| — | `HybridOriginalPipeline` | `hybrid_original_pipeline.py` | Exists, not registered |
| — | `DirectArgminPipeline` | `direct_argmin_pipeline.py` | Exists, not registered |

Config persisted to: `settings/pipeline_config.json`  
Config params from `settings.py`: `TRANSMISSION_BASELINE_METHOD`, `TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE`

---

## 9. SPR Physics Context

The pipeline output (resonance wavelength) and its interpretation:

| Physics | Effect on pipeline output |
|---------|--------------------------|
| Analyte binding to gold surface | **Blue shift** — resonance wavelength decreases |
| Rising bulk refractive index | Red shift — resonance wavelength increases |
| Binding signal convention | Sensorgram **drops** during injection (opposite to angular SPR) |
| SPR dip shape | Broad (~20–40 nm FWHM) — `argmin()` alone is noisy, hence Fourier method |
| Transmission dip | P/S ratio < 1.0 at resonance — `dip_depth = 100 - transmission_min` |
| S-pol role | Reference only — S does not couple to surface plasmons |

---

## 10. Key Constants

| Constant | Value | Source | Description |
|----------|-------|--------|-------------|
| `LED_ON_THRESHOLD_FACTOR` | `3.0` | `spectrum_processor.py` | raw_peak ≥ dark_peak × 3.0 = LED on |
| `DARK_PEAK_FALLBACK` | `3000` counts | `spectrum_processor.py` | Used when no calibration dark available |
| `SG_WINDOW_LENGTH` | `11` pixels | `transmission_processor.py` | Savitzky-Golay window |
| `SG_POLYORDER` | `3` | `transmission_processor.py` | Savitzky-Golay polynomial order |
| `SATURATION_THRESHOLD` | `62259` counts | `transmission_processor.py` | 95% of 65535 (16-bit max) |
| `DIP_DETECTED_THRESHOLD` | `5.0%` | `transmission_processor.py` | Minimum dip depth for dip_detected=True |
| `FOURIER_ALPHA` | `9000` | `fourier_pipeline.py` | Regularization strength |
| `TARGET_WINDOW_NM` | `7.3 nm` | `fourier_pipeline.py` | Linear regression fit window half-width |
| `SEARCH_WINDOW_FRACTION` | `15%` of SPR pixels | `fourier_pipeline.py` | Zero-crossing search width |
| `S_POL_SAFE_FLOOR` | `1` count | `transmission_processor.py` | Denominator clamp to avoid div-by-zero |
| `SPR_MIN_OCEAN` | `560 nm` | `detector_config.py` | Ocean Optics SPR lower bound |
| `SPR_MIN_PHASE` | `570 nm` | `detector_config.py` | Phase Photonics / USB4000 lower bound |
| `SPR_MAX` | `720 nm` | `detector_config.py` | Common upper bound |
| `BASELINE_PERCENTILE_DEFAULT` | `95.0` | call site default | Passed to `process_single_channel` but not applied in current code |

---

## 11. Gotchas and Known Issues

1. **LED intensity parameters accepted but not applied:** `led_intensity_s` and `led_intensity_p` are in the `process_single_channel()` signature but the current implementation does not apply LED boost correction. The docstring describes this step; the code does not implement it.

2. **`baseline_method` has no effect in live path:** The `"percentile"` baseline method is passed by `SpectrumProcessor` but `process_single_channel()` does not apply any baseline correction in its current implementation.

3. **`minimum_hint_nm` is the critical link:** The Fourier pipeline's zero-crossing search is anchored on this value. If `TransmissionProcessor` returns a degraded (fallback) transmission, `minimum_hint_nm` is still computed from it — the Fourier pipeline may drift without a reliable hint.

4. **Blue-shift convention:** Binding events produce a wavelength decrease. Injection detection algorithms must look for a drop in the sensorgram, not a rise.

5. **SG filter applied before baseline (not after):** The code applies SG smoothing in step 2, immediately after the P/S ratio. If baseline correction were re-enabled, it would need to run after SG smoothing.

6. **`calculate_transmission_qc()` `detector_max_counts` param is consumed but unused:** The docstring states "Consume reserved parameter to keep signature stable" — do not remove it.

7. **Unregistered pipelines exist on disk:** 8 non-fourier pipeline files in `affilabs/utils/pipelines/` are development artifacts. Do not register them without validation — some may have diverged from the current `ProcessingPipeline` API.
