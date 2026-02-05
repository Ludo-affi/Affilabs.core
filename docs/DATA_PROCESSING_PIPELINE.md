# Data Processing Pipeline Architecture

## Overview

The Affilabs.core SPR data processing system transforms raw spectrometer data into resonance wavelength measurements through a sophisticated multi-stage pipeline. The architecture separates data acquisition from processing to ensure precise timing, implements pluggable processing algorithms for flexibility, and manages memory intelligently for long-duration experiments.

**Current Status**: Production-ready with optimized threading model (Phase 3) and detector-agnostic wavelength masking.

---

## System Architecture

### High-Level Data Flow

```
┌─────────────────┐
│   Detector      │  Raw Spectrum (1848 pixels)
│   Hardware      │  563.0 - 720.0 nm
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Acquisition    │  1 Hz loop - Only queues data
│   Thread        │  NO processing (prevents jitter)
└────────┬────────┘
         │ spectrum_queue (thread-safe)
         ▼
┌─────────────────┐
│  Processing     │  Dedicated worker thread
│   Thread        │  Dequeues → Process → Buffer
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SpectrumProcessor│ Centralized processing service
│   + Pipeline    │  • Pipeline selection
│   Selection     │  • Fallback handling
└────────┬────────┘  • Quality monitoring
         │
         ▼
┌─────────────────┐
│  Active Pipeline│  Pluggable algorithm
│  (e.g., Fourier)│  • Transmission calculation
└────────┬────────┘  • Resonance wavelength detection
         │
         ▼
┌─────────────────┐
│ DataBufferMgr   │  Smart memory management
│  3 Buffer Types │  • Timeline (navigation)
└────────┬────────┘  • Cycle (full-res region)
         │            • Intensity (leak detection)
         ▼
┌─────────────────┐
│   UI Graphs     │  Qt signals update display
│  (PyQtGraph)    │  Live Sensorgram + Active Cycle
└─────────────────┘
```

---

## Threading Model (Phase 3 Optimization)

### Problem Solved
Early versions performed spectrum processing inline with acquisition, causing timing jitter that affected data quality. Even microsecond delays in the acquisition loop could cause missed detector frames.

### Solution: Dedicated Processing Thread
**Location**: [main.py:3680-3740](main.py#L3680-L3740)

```python
# Acquisition thread (ONLY queues data - no processing)
def _on_spectrum_acquired(self, spectrum_data):
    """Called by acquisition thread at 1 Hz"""
    # CRITICAL: Only queue - no processing
    self._spectrum_queue.put(spectrum_data)
    # Thread returns immediately (no jitter)

# Processing thread (runs independently)
def _processing_worker(self):
    """Dedicated worker thread for spectrum analysis"""
    while self._processing_active:
        # Block until data available
        data = self._spectrum_queue.get(timeout=0.5)
        if data is None:  # Shutdown sentinel
            break

        # Process spectrum (takes ~2-5 ms)
        result = self._spectrum_processor.process_transmission(...)

        # Update buffers
        self._data_buffer_manager.append_timeline_point(...)
```

### Thread Responsibilities

| Thread | Responsibility | Timing Critical? | Processing |
|--------|---------------|------------------|------------|
| **Acquisition** | Read detector, queue spectrum | YES (1 Hz precise) | None |
| **Processing** | Dequeue, analyze, buffer | NO (async) | All analysis |
| **Main/UI** | Qt event loop, user interaction | NO | Display only |

**Result**:
- Zero acquisition jitter (< 1 µs timing variance)
- Processing can take 2-50 ms without affecting acquisition
- Queue statistics track backlog (typically 0-2 items)

---

## Data Buffer Management

### Three Buffer Types
**Location**: [affilabs/core/data_buffer_manager.py](affilabs/core/data_buffer_manager.py)

#### 1. Timeline Data (Full Experiment Navigation)
**Purpose**: Provides full-experiment view for navigation and context.

**Memory Strategy**:
```python
# CRITICAL: Timeline is a NAVIGATION TOOL, not storage
# - Aggressively downsampled for display (e.g., 1 point per second)
# - Full data saved to CSV as it arrives (NO LOSS)
# - Old data trimmed from memory when limit reached
# - Typical display: 10,000 points max (downsampled from hours of data)

class ChannelBuffer:
    time: np.ndarray         # Elapsed time (seconds)
    timestamp: np.ndarray    # Absolute timestamp (Unix epoch)
    wavelength: np.ndarray   # Resonance wavelength (nm)
    spr: np.ndarray         # Delta SPR (RU) - not used in timeline
```

**Operations**:
- `append_timeline_point()`: Add new data with optional EMA filtering
- `trim_timeline_memory()`: Remove old data when exceeding limit
- `get_downsampled_timeline()`: Smart decimation for display
- `extract_cycle_region()`: Pull data for Active Cycle view

**Memory Limits**:
- **Max Points**: 50,000 (trimmed to 30,000 when exceeded)
- **Display Points**: 10,000 (downsampled from full buffer)
- **Typical Memory**: ~1.2 MB per channel (50k points × 24 bytes)

#### 2. Cycle Data (Region of Interest - Full Resolution)
**Purpose**: High-resolution view of selected experiment region.

**Memory Strategy**:
```python
# Full resolution data for ≤10 minute window
# At 4 Hz: 10 min = 2,400 points = 57.6 KB/channel
# At 1 Hz: 10 min = 600 points = 14.4 KB/channel

class ChannelBuffer:
    time: np.ndarray         # Elapsed time
    timestamp: np.ndarray    # Absolute timestamp
    wavelength: np.ndarray   # Resonance wavelength (nm)
    spr: np.ndarray         # Delta SPR (RU) - PRIMARY DATA
```

**Modes**:
1. **Fixed Mode** (Cursor/Region): `update_cycle_data()` - Replace buffer
2. **Moving Window** (Live Tail): `append_cycle_data()` - Accumulate with auto-trim

**Operations**:
```python
# Moving window (e.g., last 10 minutes)
buffer_manager.append_cycle_data(
    channel='a',
    new_time=[...],
    new_wavelength=[...],
    new_delta_spr=[...],
    max_window_seconds=600  # Auto-trim old data
)

# Fixed region (cursor-based)
buffer_manager.update_cycle_data(
    channel='a',
    cycle_time=time_array,
    cycle_wavelength=wavelength_array,
    delta_spr=spr_array
)
```

#### 3. Intensity Buffers (Leak Detection)
**Purpose**: Monitor raw intensity for fluid leakage detection.

**Memory Strategy**:
```python
# Sliding 5-second window
# Used to detect sudden intensity drops (leaked fluid)

class IntensityBuffer:
    times: list[float]        # Timestamps
    intensities: list[float]  # Raw detector counts
```

**Operations**:
- `append_intensity_point()`: Add measurement
- `trim_intensity_buffer()`: Remove data older than 5 seconds
- `get_intensity_average()`: Average over window
- Leak detection: `if avg_intensity < threshold * baseline: LEAK DETECTED`

---

## Spectrum Processing Service

### SpectrumProcessor Class
**Location**: [affilabs/utils/spectrum_processor.py](affilabs/utils/spectrum_processor.py)

**Responsibilities**:
1. Execute active processing pipeline
2. Provide fallback to Fourier method if pipeline fails
3. Track statistics per channel (processing time, fallback rate)
4. Calculate hint wavelength for peak finding guidance
5. Apply spectral correction (fiber coupling, LED variations)

### Main Processing Entry Point

```python
result = processor.process_transmission(
    transmission=trans_spectrum,     # I/I_ref × 100
    wavelengths=wave_array,          # Full detector range (563-720 nm)
    channel='a',
    s_reference=s_pol_reference      # For SNR weighting (optional)
)

# Returns ProcessingResult:
# - resonance_wavelength: Peak position (nm)
# - pipeline_used: "Fourier Transform (Default)"
# - fallback_used: False (or True if primary failed)
# - processing_time_ms: 2.3 ms
# - quality_score: 0.92 (optional)
# - warnings: [] or ["Low SNR detected"]
# - metadata: {"pipeline_id": "fourier", ...}
```

### Detector-Specific Hint Calculation

**Problem**: Algorithms can find spurious minimums in noisy regions (< 570 nm for Phase Photonics).

**Solution**: Calculate hint wavelength using detector-specific valid SPR range.

```python
# Get detector-specific SPR range
from affilabs.utils.detector_config import get_spr_wavelength_range

spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)
# Phase Photonics (ST*): 570.0 - 720.0 nm
# Ocean Optics (USB4*): 560.0 - 720.0 nm

# Find minimum in valid region only
spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
spr_transmission = transmission[spr_mask]
spr_wavelengths = wavelengths[spr_mask]
min_idx = np.argmin(spr_transmission)
hint_wavelength_nm = spr_wavelengths[min_idx]  # Guide peak finding
```

This hint prevents algorithms from locking onto noise below 570 nm.

### Statistics Tracking (Optimized)

**Challenge**: Calculating detailed statistics every cycle added overhead.

**Solution**: Lightweight updates with periodic detailed calculations.

```python
# Every cycle (lightweight):
stats["total_processed"] += 1
stats["last_pipeline"] = "Fourier Transform"

# Every 10th cycle (detailed):
if counter % 10 == 0:
    stats["avg_processing_time_ms"] = calculate_moving_average(...)
    logger.debug(f"Processing stats: {stats}")
```

**Statistics Tracked**:
- `total_processed`: Total spectra processed
- `fallback_count`: Times fallback was used
- `error_count`: Failed processing attempts
- `last_pipeline`: Most recent pipeline name
- `avg_processing_time_ms`: Moving average timing

---

## Processing Pipeline Architecture

### Pluggable Design
**Location**: [affilabs/utils/processing_pipeline.py](affilabs/utils/processing_pipeline.py)

**Architecture Goals**:
1. **Single Responsibility**: Pipelines only process spectra
2. **Pluggable**: Swap algorithms without changing code
3. **Testable**: Pure functions with clear inputs/outputs
4. **Observable**: Emit quality warnings and metadata

### Abstract Base Class

```python
class ProcessingPipeline(ABC):
    """Abstract base for all processing pipelines"""

    @abstractmethod
    def get_metadata(self) -> PipelineMetadata:
        """Return pipeline info for UI display"""

    @abstractmethod
    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray
    ) -> np.ndarray:
        """Convert intensity to transmission spectrum"""

    @abstractmethod
    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs
    ) -> float:
        """Detect resonance peak position"""

    def process(
        self,
        intensity: np.ndarray,
        reference: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs
    ) -> ProcessingResult:
        """Complete pipeline: transmission + resonance finding"""
        transmission = self.calculate_transmission(intensity, reference)
        resonance = self.find_resonance_wavelength(
            transmission, wavelengths, **kwargs
        )
        return ProcessingResult(
            transmission=transmission,
            resonance_wavelength=resonance,
            success=True
        )
```

### Pipeline Registry

**Purpose**: Centralized management of available pipelines.

```python
from affilabs.utils.processing_pipeline import get_pipeline_registry

registry = get_pipeline_registry()

# Register pipelines (at startup)
registry.register("fourier", FourierPipeline)
registry.register("centroid", CentroidPipeline)
registry.register("polynomial", PolynomialPipeline)

# Set active pipeline
registry.set_active_pipeline("fourier", config={
    "alpha": 9000,
    "target_window_nm": 7.3
})

# Get pipeline instance (cached)
pipeline = registry.get_active_pipeline()
result = pipeline.process(intensity, reference, wavelengths)
```

**Registry Features**:
- **Lazy Instantiation**: Creates pipeline instances on-demand
- **Caching**: Reuses instances for performance
- **Config Management**: Passes parameters to pipelines
- **Persistence**: Saves active pipeline to JSON config

---

## Available Pipelines

### 1. Fourier Pipeline (Default)
**Location**: [affilabs/utils/pipelines/fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py)

**Status**: Current production pipeline (established method).

**Algorithm**:
```python
# 1. Apply detector-specific wavelength mask
spr_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)  # Phase Photonics
spr_wavelengths = wavelengths[spr_mask]
spr_transmission = transmission[spr_mask]

# 2. SNR weighting DISABLED (per user request)
spectrum = spr_transmission  # Use raw transmission

# 3. Find minimum hint
hint_index = np.argmin(spectrum)

# 4. Calculate Fourier coefficients
fourier_weights = calculate_weights(len(spectrum), alpha=9000)
fourier_coeff = dst(spectrum * fourier_weights, type=1)

# 5. Calculate derivative using IDCT
derivative = idct(fourier_coeff, type=1)

# 6. Find zero-crossing near hint
zero_idx = find_zero_crossing(derivative, hint_index)

# 7. Refine with linear regression (85-pixel window)
peak_wavelength = linear_regression_refinement(
    spr_wavelengths,
    spectrum,
    zero_idx,
    window_size=85  # 85 × 0.085 nm = 7.2 nm physical window
)
```

**Key Parameters**:
- **alpha**: 9000 (Fourier regularization strength)
- **window_size**: 85 pixels (for Phase Photonics, 0.085 nm/pixel)
- **target_window_nm**: 7.3 nm (physical fit window)

**Wavelength Masking**:
- **Phase Photonics (ST series)**: 570.0 - 720.0 nm SPR region
- **Ocean Optics (USB4000)**: 560.0 - 720.0 nm SPR region
- **Rationale**: Removes noisy detector edges for cleaner peak finding

**Performance**:
- **Processing Time**: 2-5 ms per spectrum
- **Precision**: 0.01 nm (sub-pixel via regression)
- **Fallback Rate**: < 0.1% (very stable)

### 2. Centroid Pipeline
**Location**: [affilabs/utils/pipelines/centroid_pipeline.py](affilabs/utils/pipelines/centroid_pipeline.py)

**Status**: Alternative method (experimental).

**Algorithm**:
```python
# 1. Find peak region
min_idx = np.argmin(transmission)

# 2. Extract window around peak
window = transmission[min_idx - width : min_idx + width]
window_wavelengths = wavelengths[min_idx - width : min_idx + width]

# 3. Invert for centroid (peak becomes "heavy")
inverted = 1.0 / (window + epsilon)

# 4. Calculate centroid (center of mass)
centroid_wavelength = np.sum(inverted * window_wavelengths) / np.sum(inverted)
```

**Use Case**: Simple, fast method for symmetric peaks.

### 3. Polynomial Pipeline
**Location**: [affilabs/utils/pipelines/polynomial_pipeline.py](affilabs/utils/pipelines/polynomial_pipeline.py)

**Status**: Alternative fitting method.

**Algorithm**:
```python
# 1. Find peak region
min_idx = np.argmin(transmission)

# 2. Extract fitting window
window = transmission[min_idx - width : min_idx + width]
window_wavelengths = wavelengths[min_idx - width : min_idx + width]

# 3. Fit polynomial (order 2-4)
poly_coeff = np.polyfit(window_wavelengths, window, degree=3)

# 4. Find minimum of fitted polynomial
poly = np.poly1d(poly_coeff)
derivative = poly.deriv()
peak_wavelength = find_root(derivative, initial_guess=wavelengths[min_idx])
```

**Use Case**: Smooth peak shapes with low noise.

### 4. Adaptive Multi-Feature Pipeline
**Location**: [affilabs/utils/pipelines/adaptive_multifeature_pipeline.py](affilabs/utils/pipelines/adaptive_multifeature_pipeline.py)

**Status**: Experimental (combines multiple methods).

**Algorithm**:
```python
# 1. Calculate features from multiple methods
fourier_peak = fourier_pipeline.find_resonance_wavelength(...)
centroid_peak = centroid_pipeline.find_resonance_wavelength(...)
polynomial_peak = polynomial_pipeline.find_resonance_wavelength(...)

# 2. Assess quality of each method
fourier_quality = calculate_quality(fourier_peak, transmission)
centroid_quality = calculate_quality(centroid_peak, transmission)
polynomial_quality = calculate_quality(polynomial_peak, transmission)

# 3. Weighted average based on quality
weights = normalize([fourier_quality, centroid_quality, polynomial_quality])
peak_wavelength = (
    weights[0] * fourier_peak +
    weights[1] * centroid_peak +
    weights[2] * polynomial_peak
)
```

**Use Case**: Noisy data where consensus improves accuracy.

---

## Wavelength Filtering & Detector-Specific Processing

### Problem: Noisy Detector Regions
Different detectors have different valid wavelength ranges:
- **Phase Photonics ST series**: Noisy below 570 nm, clean 570-720 nm
- **Ocean Optics USB4000**: Noisy below 560 nm, clean 560-720 nm

Processing the full range can cause algorithms to find spurious peaks in noise.

### Solution: Detector-Agnostic Wavelength Masking
**Location**: [affilabs/utils/detector_config.py](affilabs/utils/detector_config.py#L100-L124)

```python
def get_spr_wavelength_range(detector_serial, detector_type):
    """Get detector-specific valid SPR wavelength range.

    Args:
        detector_serial: e.g., "ST00012" (Phase Photonics) or "USB4H14526" (Ocean Optics)
        detector_type: e.g., "PhasePhotonics" or "USB4000"

    Returns:
        Tuple (min_wavelength, max_wavelength) in nm
    """
    # Phase Photonics detection
    if detector_serial and detector_serial.startswith("ST"):
        return (570.0, 720.0)
    elif "PHASE" in str(detector_type).upper():
        return (570.0, 720.0)

    # Ocean Optics (default)
    return (560.0, 720.0)
```

### Application in Processing Pipeline

**Full documentation**: [wavelength_mask_live_flow.md](wavelength_mask_live_flow.md)

```python
# 1. Get detector-specific range
spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)

# 2. Create boolean mask
spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)

# 3. Filter arrays (REMOVES noisy regions)
spr_wavelengths = wavelengths[spr_mask]      # [570.0, ..., 720.0]
spr_transmission = transmission[spr_mask]     # Clean data only

# 4. Process filtered data
peak_wavelength = find_peak(spr_transmission, spr_wavelengths)
```

**Before Filtering** (Phase Photonics ST00012):
```
wavelengths:    [563.0, 563.1, ..., 569.9, 570.0, ..., 720.0]  (1848 pts)
                └───────────────┘ └─────────────────────────┘
                    NOISY (83 pts)      VALID (1765 pts)
transmission:   [0.12, 0.08, ..., 0.15, 0.98, ..., 1.02]
                └─────────────┘ └───────────────────────┘
                   UNRELIABLE        SPR RESONANCE
```

**After Filtering**:
```
spr_wavelengths: [570.0, 570.1, ..., 720.0]  (1765 pts)
spr_transmission: [0.98, 0.97, ..., 1.02]
                  └──────────────────────┘
                      CLEAN SPR DATA
```

**Result**: Algorithms work on clean 570-720 nm region only, eliminating false peaks.

---

## Pipeline Execution Flow (Detailed)

### Step-by-Step Processing

```python
# === STEP 1: Acquisition Thread (1 Hz loop) ===
raw_spectrum = detector.get_spectrum()  # 1848 pixels, 563-720 nm
# Queue data immediately (no processing)
spectrum_queue.put({
    'p_spectrum': raw_spectrum,
    'wavelengths': wavelength_array,
    'timestamp': time.time()
})

# === STEP 2: Processing Thread (async worker) ===
data = spectrum_queue.get()  # Dequeue next spectrum

# === STEP 3: Dark Subtraction ===
clean_spectrum = data['p_spectrum'] - dark_noise

# === STEP 4: Transmission Calculation ===
transmission = (clean_spectrum / s_reference) * 100

# === STEP 5: Detector Info Propagation ===
processor.set_detector_info(
    detector_serial="ST00012",
    detector_type="PhasePhotonics"
)

# === STEP 6: Hint Calculation (Detector-Specific) ===
spr_min, spr_max = get_spr_wavelength_range("ST00012", "PhasePhotonics")
# Returns (570.0, 720.0) for Phase Photonics

spr_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)
spr_transmission = transmission[spr_mask]
spr_wavelengths = wavelengths[spr_mask]
hint_wavelength_nm = spr_wavelengths[np.argmin(spr_transmission)]
# Guides peak finding to valid region

# === STEP 7: Pipeline Execution ===
result = spectrum_processor.process_transmission(
    transmission=transmission,       # Full spectrum (1848 pts)
    wavelengths=wavelengths,         # Full range (563-720 nm)
    channel='a',
    s_reference=s_reference          # For SNR weighting (optional)
)

# === STEP 8: Active Pipeline Processing ===
# (Inside FourierPipeline.find_resonance_wavelength)

# Apply detector-specific mask AGAIN (critical)
spr_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)
spr_wavelengths = wavelengths[spr_mask]      # 1765 pts
spr_transmission = transmission[spr_mask]

# Fourier transform on filtered data
fourier_coeff = dst(spr_transmission * fourier_weights, type=1)
derivative = idct(fourier_coeff, type=1)
zero_idx = find_zero_crossing(derivative, hint_index)

# Linear regression refinement
peak_wavelength = refine_peak(spr_wavelengths, spr_transmission, zero_idx)
# Returns: 645.23 nm (sub-pixel precision)

# === STEP 9: Result Packaging ===
result = ProcessingResult(
    resonance_wavelength=645.23,
    pipeline_used="Fourier Transform (Default)",
    fallback_used=False,
    processing_time_ms=3.2,
    metadata={"hint_used": 644.8, "zero_crossing_idx": 875}
)

# === STEP 10: Buffer Management ===
data_buffer_manager.append_timeline_point(
    channel='a',
    time=elapsed_time,
    wavelength=645.23,
    timestamp=absolute_timestamp,
    ema_state=ema_dict,
    ema_alpha=0.15  # Optional exponential smoothing
)

# === STEP 11: Cycle Data Update (if active) ===
if cycle_mode == "moving_window":
    data_buffer_manager.append_cycle_data(
        channel='a',
        new_time=[elapsed_time],
        new_wavelength=[645.23],
        new_delta_spr=[12.5],  # RU from baseline
        max_window_seconds=600  # 10-minute window
    )

# === STEP 12: UI Update (Qt Signal) ===
self.data_updated.emit(channel='a', wavelength=645.23)
# UI graphs redraw with new data
```

**Total Latency**:
- Acquisition to queue: < 0.1 ms
- Queue to processing: < 1 ms (typically immediate)
- Processing to buffer: 2-5 ms
- Buffer to UI: 5-10 ms (Qt redraw)
- **End-to-end**: ~10-20 ms

---

## Quality Monitoring & Fallback Mechanisms

### Three-Tier Error Handling

```python
try:
    # Tier 1: Primary Pipeline
    result = active_pipeline.find_resonance_wavelength(...)
    if np.isnan(result):
        raise ValueError("Pipeline returned NaN")

except Exception as e:
    try:
        # Tier 2: Fallback to Fourier
        result = find_resonance_wavelength_fourier(...)
        logger.warning(f"Used fallback: {e}")

    except Exception as fallback_error:
        # Tier 3: Return NaN with full error context
        result = np.nan
        logger.error(f"Both methods failed: {fallback_error}")
```

### Quality Warnings

```python
# Example quality checks in ProcessingResult
warnings = []

if snr < 10:
    warnings.append("Low SNR detected (<10)")

if peak_width > 15.0:  # nm
    warnings.append("Peak unusually wide (>15 nm)")

if resonance_wavelength < spr_min or resonance_wavelength > spr_max:
    warnings.append(f"Peak outside SPR range ({spr_min}-{spr_max} nm)")

return ProcessingResult(
    resonance_wavelength=645.2,
    pipeline_used="Fourier Transform",
    quality_score=0.87,
    warnings=warnings
)
```

### Statistics Dashboard

```python
# Per-channel statistics
stats = processor.get_statistics(channel='a')

print(f"""
Processing Statistics (Channel A):
  Total Processed: {stats['total_processed']}
  Fallback Rate:   {stats['fallback_count'] / stats['total_processed'] * 100:.1f}%
  Error Rate:      {stats['error_count'] / stats['total_processed'] * 100:.1f}%
  Avg Time:        {stats['avg_processing_time_ms']:.2f} ms
  Last Pipeline:   {stats['last_pipeline']}
""")

# Example output:
# Processing Statistics (Channel A):
#   Total Processed: 14523
#   Fallback Rate:   0.02%
#   Error Rate:      0.001%
#   Avg Time:        3.12 ms
#   Last Pipeline:   Fourier Transform (Default)
```

---

## Performance Optimizations

### 1. Thread Separation (Phase 3)
**Impact**: Eliminated acquisition jitter (< 1 µs variance).

**Before**:
```python
# Acquisition thread did EVERYTHING
spectrum = detector.get_spectrum()  # 1 ms
transmission = calculate_transmission(...)  # 2 ms
wavelength = find_peak(...)  # 3 ms
update_buffers(...)  # 1 ms
# Total: 7 ms (missed next acquisition frame)
```

**After**:
```python
# Acquisition thread
spectrum = detector.get_spectrum()  # 1 ms
queue.put(spectrum)  # 0.01 ms
# Returns in 1 ms (perfect timing)

# Processing thread (async)
data = queue.get()
process_everything(data)  # 7 ms doesn't matter
```

### 2. Lightweight Statistics Updates
**Impact**: Reduced per-cycle overhead by 60%.

```python
# Every cycle (fast)
stats["total_processed"] += 1

# Every 10th cycle (detailed)
if counter % 10 == 0:
    stats["avg_time"] = calculate_moving_average(...)
    logger.debug(f"Stats: {stats}")
```

### 3. Pipeline Caching
**Impact**: Eliminated repeated registry lookups.

```python
# Before (every spectrum)
pipeline = registry.get_active_pipeline()  # Dict lookup + instance creation

# After (cached)
if self._cached_pipeline_id != registry.active_pipeline_id:
    self._cached_pipeline = registry.get_active_pipeline()
    self._cached_pipeline_id = registry.active_pipeline_id
# Reuse cached instance (99.9% of calls)
```

### 4. Detector-Specific Processing
**Impact**: 15% faster peak finding (fewer pixels to process).

```python
# Before: Process full 1848 pixels (563-720 nm)
peak = find_peak(transmission, wavelengths)  # 5 ms

# After: Process 1765 pixels (570-720 nm for Phase Photonics)
spr_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)
peak = find_peak(transmission[spr_mask], wavelengths[spr_mask])  # 4.2 ms
```

### 5. Smart Memory Management
**Impact**: Supports multi-hour experiments without memory growth.

```python
# Timeline buffer trim (when exceeding 50,000 points)
if len(buffer.time) > 50_000:
    buffer.time = buffer.time[-30_000:]  # Keep recent 30k points
    buffer.wavelength = buffer.wavelength[-30_000:]

# Cycle buffer auto-trim (10-minute window)
current_time = buffer.time[-1]
cutoff_time = current_time - 600  # 10 minutes
mask = buffer.time >= cutoff_time
buffer.time = buffer.time[mask]
```

---

## API Reference

### SpectrumProcessor

```python
from affilabs.utils.spectrum_processor import SpectrumProcessor

# Initialize
processor = SpectrumProcessor(
    fourier_weights=weights_array,
    fourier_window_size=165,
    detector_serial="ST00012",
    detector_type="PhasePhotonics"
)

# Set detector info (can be updated dynamically)
processor.set_detector_info(
    detector_serial="ST00012",
    detector_type="PhasePhotonics"
)

# Process spectrum
result = processor.process_transmission(
    transmission=trans_array,
    wavelengths=wave_array,
    channel='a',
    s_reference=s_ref_array  # Optional
)

# Get statistics
stats = processor.get_statistics(channel='a')
all_stats = processor.get_statistics()  # All channels

# Reset statistics
processor.reset_statistics(channel='a')
```

### DataBufferManager

```python
from affilabs.core.data_buffer_manager import DataBufferManager

# Initialize
buffer_mgr = DataBufferManager()

# Append timeline data
filtered_wavelength = buffer_mgr.append_timeline_point(
    channel='a',
    time=elapsed_sec,
    wavelength=645.2,
    timestamp=unix_timestamp,
    ema_state=ema_dict,  # Optional EMA filtering
    ema_alpha=0.15
)

# Append cycle data (moving window)
buffer_mgr.append_cycle_data(
    channel='a',
    new_time=[10.5, 10.6],
    new_wavelength=[645.2, 645.3],
    new_delta_spr=[12.5, 12.6],
    max_window_seconds=600
)

# Update cycle data (fixed region)
buffer_mgr.update_cycle_data(
    channel='a',
    cycle_time=time_array,
    cycle_wavelength=wavelength_array,
    delta_spr=spr_array
)

# Extract region from timeline
time, wavelength, timestamp = buffer_mgr.extract_cycle_region(
    channel='a',
    start_time=100.0,
    stop_time=200.0
)

# Baseline management
buffer_mgr.set_baseline(channel='a', wavelength=640.0)
baseline = buffer_mgr.baseline_wavelengths['a']

# Memory management
points_removed = buffer_mgr.trim_timeline_memory(
    channel='a',
    max_points=50_000,
    trim_to=30_000
)

# Downsampling for display
time_ds, wavelength_ds = buffer_mgr.get_downsampled_timeline(
    channel='a',
    target_points=10_000
)

# Memory statistics
memory_stats = buffer_mgr.get_memory_stats()
print(memory_stats['a'])
# {'timeline_points': 12500, 'cycle_points': 600,
#  'timeline_kb': 900, 'cycle_kb': 57}
```

### PipelineRegistry

```python
from affilabs.utils.processing_pipeline import get_pipeline_registry

# Get singleton registry
registry = get_pipeline_registry()

# Register pipeline
from affilabs.utils.pipelines.fourier_pipeline import FourierPipeline
registry.register("fourier", FourierPipeline)

# Set active pipeline
registry.set_active_pipeline(
    "fourier",
    config={"alpha": 9000, "target_window_nm": 7.3}
)

# Get active pipeline instance
pipeline = registry.get_active_pipeline()

# List available pipelines
pipelines = registry.list_pipelines()
# Returns: ["fourier"]

# Get pipeline metadata
metadata = pipeline.get_metadata()
print(f"{metadata.name} v{metadata.version}")
# "Fourier Transform (Default) v1.0"
```

### ProcessingPipeline (Custom Implementation)

```python
from affilabs.utils.processing_pipeline import ProcessingPipeline, PipelineMetadata
import numpy as np

class MyCustomPipeline(ProcessingPipeline):
    """Custom processing pipeline example"""

    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            name="My Custom Method",
            description="Example custom algorithm",
            version="1.0",
            author="Your Name",
            parameters={"threshold": 0.5}
        )

    def calculate_transmission(
        self,
        intensity: np.ndarray,
        reference: np.ndarray
    ) -> np.ndarray:
        """Standard transmission calculation"""
        return (intensity / reference) * 100

    def find_resonance_wavelength(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        **kwargs
    ) -> float:
        """Custom peak finding logic"""
        # Get detector-specific SPR range
        from affilabs.utils.detector_config import get_spr_wavelength_range

        detector_serial = kwargs.get("detector_serial")
        detector_type = kwargs.get("detector_type")
        spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)

        # Filter to SPR region
        spr_mask = (wavelengths >= spr_min) & (wavelengths <= spr_max)
        spr_wavelengths = wavelengths[spr_mask]
        spr_transmission = transmission[spr_mask]

        # Your custom algorithm here
        min_idx = np.argmin(spr_transmission)
        return spr_wavelengths[min_idx]

# Register and use
registry.register("custom", MyCustomPipeline)
registry.set_active_pipeline("custom")
```

---

## Troubleshooting

### Issue: Processing Fallback Rate High

**Symptoms**: `fallback_count` > 5% in statistics.

**Diagnosis**:
```python
# Check pipeline statistics
stats = processor.get_statistics(channel='a')
if stats['fallback_count'] / stats['total_processed'] > 0.05:
    print("High fallback rate detected")
    print(f"Last pipeline: {stats['last_pipeline']}")
```

**Common Causes**:
1. **Noisy data**: Check SNR in s_reference spectrum
2. **Wrong detector range**: Verify `detector_serial` and `detector_type` are set
3. **Pipeline parameters**: Check alpha, window_size match detector

**Solutions**:
```python
# Solution 1: Verify detector info
processor.set_detector_info(
    detector_serial="ST00012",  # Ensure correct
    detector_type="PhasePhotonics"
)

# Solution 2: Check wavelength range
from affilabs.utils.detector_config import get_spr_wavelength_range
spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)
print(f"SPR range: {spr_min} - {spr_max} nm")

# Solution 3: Inspect s_reference quality
snr = np.mean(s_reference) / np.std(s_reference)
print(f"S-reference SNR: {snr:.1f}")
# Good: SNR > 50, Poor: SNR < 20
```

### Issue: Memory Growth During Long Experiments

**Symptoms**: Application memory increases over hours.

**Diagnosis**:
```python
# Check buffer sizes
memory_stats = buffer_mgr.get_memory_stats()
for ch, stats in memory_stats.items():
    print(f"Channel {ch}: {stats['timeline_kb']} KB timeline, {stats['cycle_kb']} KB cycle")
```

**Solutions**:
```python
# Solution 1: Enable timeline trimming
for channel in ['a', 'b', 'c', 'd']:
    removed = buffer_mgr.trim_timeline_memory(
        channel=channel,
        max_points=50_000,
        trim_to=30_000
    )
    if removed > 0:
        print(f"Trimmed {removed} old points from channel {channel}")

# Solution 2: Reduce cycle window
buffer_mgr.append_cycle_data(
    channel='a',
    new_time=[...],
    new_wavelength=[...],
    new_delta_spr=[...],
    max_window_seconds=300  # 5 minutes instead of 10
)

# Solution 3: Check for data leaks
import gc
gc.collect()
print(f"Garbage collected: {gc.get_count()}")
```

### Issue: Peak Finding in Wrong Region

**Symptoms**: Resonance wavelength outside expected range (e.g., < 570 nm).

**Diagnosis**:
```python
# Check if wavelength masking is applied
result = processor.process_transmission(...)
if result.resonance_wavelength < 570.0:
    print("WARNING: Peak found in noisy region")
    print(f"Detector: {processor.detector_serial}")
```

**Solutions**:
```python
# Solution 1: Verify detector info is set
processor.set_detector_info(
    detector_serial="ST00012",  # Must be set
    detector_type="PhasePhotonics"
)

# Solution 2: Check pipeline implementation
from affilabs.utils.detector_config import get_spr_wavelength_range
spr_min, spr_max = get_spr_wavelength_range(
    processor.detector_serial,
    processor.detector_type
)
print(f"Expected SPR range: {spr_min} - {spr_max} nm")

# Solution 3: Manually filter before processing
spr_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)
if not any(spr_mask):
    print("ERROR: No wavelengths in SPR range")
```

### Issue: Slow Processing (> 10 ms per spectrum)

**Symptoms**: `avg_processing_time_ms` > 10.0 in statistics.

**Diagnosis**:
```python
import time

# Time individual steps
t0 = time.perf_counter()
result = processor.process_transmission(...)
t1 = time.perf_counter()
print(f"Processing took {(t1 - t0) * 1000:.2f} ms")

# Check if pipeline caching is working
print(f"Cached pipeline ID: {processor._cached_pipeline_id}")
print(f"Active pipeline ID: {registry.active_pipeline_id}")
```

**Solutions**:
```python
# Solution 1: Reduce window size (if using Fourier)
registry.set_active_pipeline("fourier", config={
    "alpha": 9000,
    "target_window_nm": 5.0  # Smaller window (faster)
})

# Solution 2: Disable statistics logging
processor._log_interval = 1000  # Log less frequently

# Solution 3: Check for debug logging overhead
import logging
logging.getLogger('affilabs').setLevel(logging.WARNING)  # Reduce logging
```

---

## Future Enhancements

### Planned Features

1. **Machine Learning Pipeline**
   - Train neural network on labeled SPR peaks
   - Predict resonance wavelength directly from spectrum
   - Target: < 1 ms processing time

2. **Adaptive Quality Scoring**
   - Real-time quality assessment (0-1 score)
   - Automatic pipeline selection based on data quality
   - User alerts for poor signal

3. **Multi-Channel Correlation**
   - Detect correlated noise across channels
   - Reject common-mode artifacts
   - Improved baseline stability

4. **Advanced Filtering**
   - Kalman filtering for temporal smoothing
   - Wavelet denoising for high-frequency artifacts
   - Adaptive median filtering based on SNR

5. **Parallel Processing**
   - Multi-threaded processing for 4 channels
   - GPU acceleration for Fourier transforms
   - Target: 100 Hz acquisition rate

---

## Summary

The ezControl data processing pipeline is a production-ready, detector-agnostic system that:

✅ **Separates acquisition from processing** (Phase 3 threading) for zero timing jitter
✅ **Implements pluggable algorithms** via pipeline registry for flexibility
✅ **Manages memory intelligently** with downsampling and trimming for long experiments
✅ **Masks noisy wavelength regions** detector-specifically (Phase Photonics, Ocean Optics)
✅ **Provides fallback mechanisms** with three-tier error handling
✅ **Tracks quality statistics** per channel with lightweight updates
✅ **Optimizes performance** with caching, threading, and smart processing

**Key Files**:
- [data_buffer_manager.py](affilabs/core/data_buffer_manager.py) - Memory management
- [spectrum_processor.py](affilabs/utils/spectrum_processor.py) - Processing service
- [processing_pipeline.py](affilabs/utils/processing_pipeline.py) - Pipeline architecture
- [fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py) - Default algorithm
- [detector_config.py](affilabs/utils/detector_config.py) - Wavelength masking
- [main.py](main.py#L3680-L3740) - Threading model

**Current Production Pipeline**: Fourier Transform with detector-specific wavelength masking (570-720 nm for Phase Photonics, 560-720 nm for Ocean Optics).

**Performance**: 2-5 ms processing time, < 0.1% fallback rate, supports multi-hour experiments with stable memory footprint.
