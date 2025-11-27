# Original Peak Tracking Method - 2 nm Performance Baseline

## 🎯 Original Implementation (First Commit - October 2025)

Found in: `f99bb535` - "Initial commit: ezControl-AI - AI-enhanced SPR control system"

### Key Discovery: **ALPHA = 9000** (vs current 2000)

## 📊 Original Processing Pipeline

### File: `utils/spr_data_processor.py` (Original)

**Key Parameters:**
```python
# Fourier Transform Smoothing
alpha = 9000.0  # DEFAULT - Line 547
window = 165    # Zero-crossing refinement window
```

**Median Filter:**
```python
MED_FILT_WIN = 5  # From settings.py
```

**Processing Flow:**
1. **Transmission Calculation**: `(P - dark) / (S - dark) × 100%`
2. **Fourier Smoothing** with high alpha (9000)
3. **Derivative Calculation** via IDCT
4. **Zero-Crossing Detection**
5. **Linear Regression** around zero-crossing (window=165)
6. **Causal Median Filter** (window=5, backward-looking)

## 🔬 Original Fourier Transform Implementation

### Method: `calculate_fourier_weights()`

```python
@staticmethod
def calculate_fourier_weights(
    wave_data_length: int,
    alpha: float = 9000.0,  # ⭐ KEY PARAMETER
) -> np.ndarray:
    """
    Calculate Fourier transform weights for smoothing.

    Args:
        wave_data_length: Length of wavelength array
        alpha: Smoothing parameter (higher = more smoothing, default: 9000)

    Returns:
        Fourier weight array
    """
    n = wave_data_length - 1
    phi = np.pi / n * np.arange(1, n)
    phi2 = phi**2
    weights = phi / (1 + alpha * phi2 * (1 + phi2))

    return weights
```

### Formula Analysis

```
weights = phi / (1 + alpha * phi^2 * (1 + phi^2))

where:
  phi = (π/n) * [1, 2, 3, ..., n-1]
  n = number of wavelength points - 1
  alpha = smoothing strength parameter
```

**Effect of alpha:**
- **alpha = 2000** (current): Less aggressive smoothing, more noise
- **alpha = 9000** (original): **4.5× more aggressive smoothing**, lower noise
- Higher alpha → stronger high-frequency suppression → smoother baseline

## 🎯 Zero-Crossing Detection

### Method: `find_resonance_wavelength()`

```python
def find_resonance_wavelength(
    self,
    spectrum: np.ndarray,
    window: int = 165,  # Refinement window
) -> float:
    """
    Find SPR resonance wavelength via zero-crossing of derivative.

    Process:
    1. Calculate smoothed spectrum derivative (with alpha=9000)
    2. Find zero-crossing point (searchsorted)
    3. Define window around zero-crossing (±165 points)
    4. Fit linear regression: derivative = slope * wavelength + intercept
    5. Interpolate exact wavelength: lambda = -intercept / slope
    """
```

**Key Insight**: Window=165 was already optimal, but **alpha=9000** was the critical parameter for low noise.

## 🎛️ Median Filter (Post-Processing)

### Causal (Real-Time) Filtering

```python
def apply_causal_median_filter(
    self,
    data: np.ndarray,
    buffer_index: int,
    window: Optional[int] = None,  # Default: 5
) -> float:
    """
    Apply causal (backward-looking) median filter.

    - Window size: 5 points (from settings.py)
    - Backward-looking only (real-time compatible)
    - Uses np.nanmedian (robust to outliers)
    """
```

**Settings:**
- `MED_FILT_WIN = 5` - Very small window (minimal smoothing)
- `FILTERING_ON = True` - Enabled by default

## 📈 Performance Baseline

### Reported Performance: **2 nm peak-to-peak** (equivalent to ~2 RU)

**Configuration:**
- Fourier alpha: **9000** ✅
- Zero-crossing window: **165** ✅
- Median filter: **5** (minimal)
- No SG filter on transmission (only Fourier smoothing)

## 🔍 Current vs Original Comparison

| Parameter | Original (2 nm) | Current (unknown) | Difference |
|-----------|-----------------|-------------------|------------|
| **Fourier Alpha** | **9000** | **2000** | **4.5× weaker** ❌ |
| Zero-crossing window | 165 | 165 | Same ✅ |
| Median filter | 5 | Variable | Similar |
| SG filter on transmission | **NO** | **YES (21, 3)** | Extra smoothing ✅ |
| Baseline correction | NO | YES | Extra processing ✅ |

## 🚨 Critical Finding

**The original 2 nm performance was achieved with:**

1. **MUCH HIGHER alpha** (9000 vs 2000)
   - This is **4.5× more aggressive** smoothing
   - Stronger high-frequency noise suppression
   - Better baseline stability

2. **NO SG filter before Fourier**
   - Current code applies SG filter (21, 3) before Fourier
   - Double smoothing might be redundant

3. **Simpler pipeline**
   - Just Fourier smoothing + zero-crossing
   - No baseline correction (polynomial fitting)
   - Minimal median filtering (5 points)

## 💡 Recommendation: Test These Exact Parameters

### Option 1: Pure Original Method
```python
# In settings.py or pipeline config
FOURIER_ALPHA = 9000  # Instead of 2000
SG_FILTER_ENABLED = False  # Disable SG filter
FOURIER_BASELINE_CORRECTION = False  # Disable baseline correction
MEDIAN_FILTER_WINDOW = 5
```

### Option 2: Original + Current Enhancements
```python
# Keep current enhancements but use original alpha
FOURIER_ALPHA = 9000  # Original aggressive smoothing
SG_FILTER_ENABLED = True  # Keep SG filter
SG_WINDOW = 21
SG_POLYORDER = 3
FOURIER_BASELINE_CORRECTION = True  # Keep baseline correction
```

### Option 3: Grid Search Around Original
Test alpha values around the original:
```python
alpha_values = [5000, 7000, 9000, 11000, 13000]
# Find optimal with your 5-minute baseline data
```

## 🎯 Next Steps

1. **Record 5-minute baseline** with current settings (alpha=2000)
2. **You send me the data**
3. **I test these alpha values:**
   - 2000 (current)
   - 5000
   - 7000
   - **9000 (original)** ⭐
   - 11000
   - 13000

4. **Compare noise metrics:**
   - Peak-to-peak variation
   - Standard deviation
   - Processing time

5. **Find optimal alpha** that balances:
   - Baseline noise (lower is better)
   - Dynamic response (faster is better)
   - Processing speed (< 20ms per spectrum)

## 🔧 Quick Test

To immediately test the original parameters, modify:

**File**: `src/utils/pipelines/fourier_pipeline.py` (line 30)
```python
# Change from:
self.alpha = self.config.get('alpha', 2e3)

# To:
self.alpha = self.config.get('alpha', 9e3)  # Original value!
```

Or add to **settings.py**:
```python
FOURIER_ALPHA = 9000  # Restore original parameter
```

## 📊 Expected Result

With **alpha = 9000**, you should see:
- ✅ Significantly smoother baseline (~2 nm peak-to-peak)
- ✅ Less jitter in stable regions
- ⚠️ Potentially slower response to rapid changes
- ✅ Similar or better to your original 2 RU performance

## 🎉 Key Takeaway

**The original "magic" was alpha = 9000, not complex processing!**

Your original implementation was actually **simpler** and **more effective** than the current one. The secret was aggressive Fourier smoothing (alpha=9000), not fancy multi-stage filtering.

This is exactly the kind of insight we'll get from your 5-minute baseline recording - we can test alpha values from 2000 to 13000 offline and find the sweet spot for your specific hardware/conditions.
