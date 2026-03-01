# Spectrum Processing Pipelines — Functional Requirements Specification

**Source:** `affilabs/utils/pipelines/` (9 pipeline files) + `affilabs/utils/processing_pipeline.py` (base classes)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Pipelines convert raw transmission spectra into a single resonance wavelength value (nm). Each pipeline implements a different algorithm for finding the SPR dip position. The `PipelineRegistry` singleton manages registration and runtime selection.

---

## 2. Base Classes (`affilabs/utils/processing_pipeline.py`)

| Class | Type | Purpose |
|-------|------|---------|
| `PipelineMetadata` | `@dataclass` | `name`, `description`, `version`, `author`, `parameters` |
| `ProcessingResult` | `@dataclass` | `transmission`, `resonance_wavelength`, `metadata`, `success`, `error_message` |
| `ProcessingPipeline` | `ABC` | Abstract base — defines the interface |
| `PipelineRegistry` | Singleton | Registration, selection, active pipeline tracking |

### 2.1 Common Interface

All pipelines implement:

```python
get_metadata() -> PipelineMetadata
calculate_transmission(intensity: np.ndarray, reference: np.ndarray) -> np.ndarray
find_resonance_wavelength(transmission: np.ndarray, wavelengths: np.ndarray, **kwargs) -> float
process(intensity, reference, wavelengths, **kwargs) -> ProcessingResult  # default in base
```

### 2.2 PipelineRegistry

| Method | Purpose |
|--------|---------|
| `register(pipeline_id, pipeline_class)` | Register a pipeline |
| `get_pipeline(pipeline_id)` | Get pipeline instance |
| `set_active_pipeline(pipeline_id)` | Switch active pipeline |
| `get_active_pipeline()` | Get active pipeline instance |
| `list_pipelines()` | List all registered |
| `active_pipeline_id` | Current active ID |

**Initialization:** `initialize_pipelines()` in `__init__.py` registers `FourierPipeline` as default. Reads saved preference from `settings/pipeline_config.json`.

---

## 3. Pipeline Catalog

### 3.1 FourierPipeline — **DEFAULT / ACTIVE**

**File:** `affilabs/utils/pipelines/fourier_pipeline.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `alpha` | 9000 | Fourier weighting coefficient |
| `target_window_nm` | 7.3 | Target dip window |

**Algorithm:** DST (Discrete Sine Transform) + IDCT (Inverse DCT) derivative zero-crossing. Frequency-domain filtering suppresses noise while preserving the broad SPR dip shape.

**Extra methods:** `_calculate_fourier_weights(n)`, `_calculate_snr_weights(s_reference, snr_strength)`

---

### 3.2 CentroidPipeline

**File:** `affilabs/utils/pipelines/centroid_pipeline.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `smoothing_sigma` | 2.0 | Gaussian smoothing |
| `search_window` | 100 px | Window around dip |

**Algorithm:** Center-of-mass of inverted dip. Simple, fast, and robust for broad dips.

---

### 3.3 PolynomialPipeline

**File:** `affilabs/utils/pipelines/polynomial_pipeline.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `fit_window` | 80 px | Window around dip |
| degree | 4 | Polynomial degree |

**Algorithm:** Polynomial fit (degree 4) around dip region, analytical minimum via derivative roots.

---

### 3.4 HybridPipeline

**File:** `affilabs/utils/pipelines/hybrid_pipeline.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `alpha` | 2000 | Fourier weighting |
| `gaussian_sigma` | 1.0 | Gaussian smoothing |

**Algorithm:** Optimized Fourier + light Gaussian + temporal smoothing. Claims 90% noise reduction vs standard pipeline.

---

### 3.5 HybridOriginalPipeline

**File:** `affilabs/utils/pipelines/hybrid_original_pipeline.py`

**Algorithm:** Original hybrid: Fourier + Savitzky-Golay + Gaussian refinement. Preserved for comparison/benchmarking.

---

### 3.6 BatchSavgolPipeline — **GOLD STANDARD**

**File:** `affilabs/utils/pipelines/batch_savgol_pipeline.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| batch size | 12 spectra | Spectra to accumulate before batch filtering |

**Algorithm:** 3-stage pipeline: hardware averaging + batch Savitzky-Golay filtering + Fourier. Achieves 0.008 nm P2P baseline noise.

**Extra methods:** `add_to_batch(wavelength, timestamp)`, `process_batch()`, `is_batch_ready()`, `clear_batch()`

**Note:** Requires batch accumulation — adds latency but gives best noise performance.

---

### 3.7 DirectArgminPipeline

**File:** `affilabs/utils/pipelines/direct_argmin_pipeline.py`

**Algorithm:** `np.argmin()` within SPR wavelength range. Sub-0.1 ms execution. Top 2 in pipeline comparison study. Use when speed matters more than sub-0.01nm precision.

---

### 3.8 ConsensusPipeline

**File:** `affilabs/utils/pipelines/consensus_pipeline.py`

| Weight | Method |
|--------|--------|
| 60% | Centroid |
| 30% | Parabolic fit |
| 10% | Fourier |

**Algorithm:** Weighted multi-method consensus with outlier detection. Three independent estimates are weighted and combined.

**Extra methods:** `_find_peak_parabolic()`, `_calculate_simple_weights()`, `reset_temporal_state()`

---

### 3.9 AdaptiveMultiFeaturePipeline

**File:** `affilabs/utils/pipelines/adaptive_multifeature_pipeline.py`

**Algorithm:** Tracks position + FWHM + depth simultaneously. Kalman filtering, jitter rejection, asymmetric peak model. Most sophisticated pipeline — designed for noisy or rapidly changing signals.

**Extra methods:** `_extract_features_fast()`, `_refine_peak()`, `_temporal_filter()`, `_detect_jitter()`, `_calculate_temporal_coherence()`, `reset_temporal_state()`

---

## 4. Pipeline Selection

| Context | Recommended Pipeline |
|---------|---------------------|
| General live acquisition | `FourierPipeline` (default) |
| Lowest noise / offline | `BatchSavgolPipeline` |
| Fastest execution | `DirectArgminPipeline` |
| Noisy environments | `AdaptiveMultiFeaturePipeline` |
| Cross-validation | `ConsensusPipeline` |

---

## 5. Configuration

Pipeline config persists to `settings/pipeline_config.json`. The active pipeline and its parameters (baseline_method, baseline_degree) are loaded from this file at startup by `initialize_pipelines()`.

Baseline correction method and polynomial degree are read from `affilabs.settings` module-level constants:
- `TRANSMISSION_BASELINE_METHOD` (default: `"percentile"`)
- `TRANSMISSION_BASELINE_POLYNOMIAL_DEGREE` (default: `2`)
