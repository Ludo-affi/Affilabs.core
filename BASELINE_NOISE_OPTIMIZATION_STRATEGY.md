# Baseline Noise Optimization Strategy

## Goal
Achieve 2 nm peak-to-peak baseline noise (as observed before) by optimizing:
1. **Savitzky-Golay filter** parameters (window, polyorder)
2. **Fourier weight alpha** parameter (controls smoothing strength)
3. **Zero-crossing window size** (refinement accuracy)

## Current State Analysis

### Pipeline Architecture
```
Raw Spectrum (P-mode)
  ↓
Dark Noise Subtraction
  ↓
Afterglow Correction
  ↓
Transmission = (P - dark - afterglow) / S_ref × LED_correction
  ↓
Baseline Correction (polynomial detrending)
  ↓
✨ SAVITZKY-GOLAY FILTER ← OPTIMIZATION POINT 1
  ↓
DST (Discrete Sine Transform with Fourier weights ← OPTIMIZATION POINT 2)
  ↓
IDCT (derivative calculation)
  ↓
Zero-crossing search ← OPTIMIZATION POINT 3
  ↓
Linear regression refinement (window_size ← OPTIMIZATION POINT 3)
  ↓
Resonance Wavelength
```

### Current Parameters (src/core/data_acquisition_manager.py line 1038)
- **SG Filter**: `savgol_filter(transmission_spectrum, 21, 3)`
  - Window: 21 points
  - Polynomial order: 3
  - Applied BEFORE pipeline processing

### Current Parameters (src/utils/pipelines/fourier_pipeline.py)
- **Fourier alpha**: `2e3` (line 30) - controls noise suppression strength
- **Window size**: `165` (line 29) - zero-crossing refinement window
- **Baseline correction**: Enabled by default (polynomial degree 2)

### Problem: Dual SG Filtering
**CRITICAL**: SG filter is applied TWICE!
1. In `data_acquisition_manager.py` line 1038: `savgol_filter(transmission, 21, 3)`
2. In `spr_signal_processing.py` line 112: `savgol_filter(spectrum, 21, 3)` (if apply_sg_filter=True)

**Current state**: apply_sg_filter defaults to False, so only ONE pass happens ✅

---

## Optimization Strategy

### Phase 1: Live Parameter Tuning (Interactive)

**Approach**: Create real-time tuning widget that allows adjustment during live acquisition

**Implementation**:
1. Add tunable parameters to settings
2. Create UI slider panel for live adjustment
3. Display peak-to-peak noise metric in real-time
4. Record optimal parameters

**Tunable Parameters**:
```python
# SG Filter (Pre-transmission smoothing)
SG_WINDOW_LENGTH = 21       # Range: 5-51 (must be odd)
SG_POLYORDER = 3            # Range: 2-5

# Fourier Transform
FOURIER_ALPHA = 2e3         # Range: 500-10000 (logarithmic scale)
FOURIER_WINDOW_SIZE = 165   # Range: 50-300

# Baseline Correction
BASELINE_CORRECTION = True  # Enable/disable
BASELINE_DEGREE = 2         # Range: 1-4
```

**Live Feedback Metrics**:
- **Peak-to-Peak Noise**: Max - Min wavelength in stable baseline segment
- **Standard Deviation**: σ of wavelength over moving window (100 points)
- **SNR Estimate**: Signal range / noise floor
- **Update Rate**: Hz (affected by processing complexity)

---

### Phase 2: Automated Grid Search (Offline Analysis)

**Approach**: Record stable baseline data, then systematically test parameter combinations

**Method**:
1. Record 30-60 seconds of stable baseline (no sample injection)
2. Save raw transmission spectra to disk
3. Replay data offline with different parameter combinations
4. Measure noise for each combination
5. Identify optimal parameters

**Grid Search Parameters**:
```python
sg_windows = [11, 15, 21, 25, 31]      # Odd values
sg_polyorders = [2, 3, 4]
alphas = [500, 1000, 2000, 5000, 10000]
window_sizes = [100, 130, 165, 200, 250]

# Total combinations: 5 × 3 × 5 × 5 = 375 tests
# At 10ms per test = 3.75 seconds
```

**Optimization Metrics**:
- **Primary**: Peak-to-peak noise (nm)
- **Secondary**: Standard deviation (nm)
- **Constraint**: Processing time < 20ms per spectrum

---

### Phase 3: Dynamic Adaptive Optimization (Real-Time)

**Approach**: Automatically adjust parameters based on signal quality during acquisition

**Concept**: Similar to adaptive_multifeature_pipeline.py but for baseline noise optimization

**Logic**:
```python
class AdaptiveFourierOptimizer:
    """Dynamically tune Fourier parameters based on real-time noise"""

    def __init__(self):
        self.noise_history = []  # Rolling window of noise measurements
        self.alpha = 2e3         # Start with default
        self.sg_window = 21

    def update(self, wavelength_trace, peak_wavelength):
        """Called every acquisition cycle"""
        # Measure current noise
        noise_ppk = self._calculate_noise(wavelength_trace[-100:])
        self.noise_history.append(noise_ppk)

        # If noise exceeds threshold, increase smoothing
        if noise_ppk > 3.0:  # nm threshold
            self.alpha = min(self.alpha * 1.2, 10000)  # Increase 20%
            self.sg_window = min(self.sg_window + 2, 51)

        # If noise very low, reduce smoothing (preserve dynamic response)
        elif noise_ppk < 1.0:
            self.alpha = max(self.alpha * 0.9, 500)  # Decrease 10%
            self.sg_window = max(self.sg_window - 2, 11)

        return self.alpha, self.sg_window
```

**Benefits**:
- Automatically adapts to changing signal conditions
- Balances noise suppression vs. dynamic response
- No manual tuning required

**Risks**:
- Could be unstable if not tuned carefully
- May reduce baseline during dynamic events
- Requires extensive validation

---

## Implementation Plan

### Step 1: Add Configurable Parameters (15 min)

**File**: `src/settings/settings.py`

Add:
```python
# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL PROCESSING PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

# Savitzky-Golay Filter (applied to transmission before peak finding)
SG_WINDOW_LENGTH = 21          # Must be odd, range: 5-51
SG_POLYORDER = 3               # Polynomial order, range: 2-5

# Fourier Transform Peak Detection
FOURIER_ALPHA = 2e3            # Smoothing strength, range: 500-10000
FOURIER_WINDOW_SIZE = 165      # Zero-crossing refinement window, range: 50-300
FOURIER_BASELINE_CORRECTION = True   # Enable polynomial baseline correction
FOURIER_BASELINE_DEGREE = 2    # Polynomial degree for baseline

# Real-time Noise Monitoring
ENABLE_NOISE_MONITORING = False   # Display real-time peak-to-peak noise
NOISE_WINDOW_SIZE = 100          # Points to use for noise calculation
```

### Step 2: Modify Pipeline to Use Settings (20 min)

**File**: `src/core/data_acquisition_manager.py` (line ~1038)

Replace:
```python
# Old (hardcoded)
transmission_spectrum = savgol_filter(transmission_spectrum, 21, 3)
```

With:
```python
# New (configurable)
from settings.settings import SG_WINDOW_LENGTH, SG_POLYORDER
if len(transmission_spectrum) >= SG_WINDOW_LENGTH:
    transmission_spectrum = savgol_filter(
        transmission_spectrum,
        SG_WINDOW_LENGTH,
        SG_POLYORDER
    )
```

**File**: `src/utils/pipelines/fourier_pipeline.py` (lines 29-32)

Replace:
```python
# Old (hardcoded in __init__)
self.window_size = self.config.get('window_size', 165)
self.alpha = self.config.get('alpha', 2e3)
self.baseline_correction = self.config.get('baseline_correction', False)
self.baseline_degree = self.config.get('baseline_degree', 2)
```

With:
```python
# New (read from settings as defaults)
from settings.settings import (
    FOURIER_ALPHA, FOURIER_WINDOW_SIZE,
    FOURIER_BASELINE_CORRECTION, FOURIER_BASELINE_DEGREE
)
self.window_size = self.config.get('window_size', FOURIER_WINDOW_SIZE)
self.alpha = self.config.get('alpha', FOURIER_ALPHA)
self.baseline_correction = self.config.get('baseline_correction', FOURIER_BASELINE_CORRECTION)
self.baseline_degree = self.config.get('baseline_degree', FOURIER_BASELINE_DEGREE)
```

### Step 3: Create Live Tuning Panel (45 min)

**File**: `src/widgets/pipeline_tuning_dialog.py` (NEW)

Create dialog with:
- Sliders for each parameter
- Real-time noise display (peak-to-peak, std dev)
- "Apply" button to update settings
- "Reset to Default" button
- "Save Optimal" button to write to settings.py

**Integration**: Add menu item "Advanced → Pipeline Tuning" to main window

### Step 4: Add Noise Metrics Display (30 min)

**File**: `src/core/data_acquisition_manager.py`

Add noise calculation:
```python
def _calculate_baseline_noise(self, channel: str) -> dict:
    """Calculate baseline noise metrics for quality assessment"""
    if len(self.lambda_times[channel]) < NOISE_WINDOW_SIZE:
        return {'ppk': np.nan, 'std': np.nan, 'ready': False}

    # Get last N wavelength points
    recent_wavelengths = self.lambda_values[channel][-NOISE_WINDOW_SIZE:]

    # Calculate metrics
    ppk = np.ptp(recent_wavelengths)  # Peak-to-peak
    std = np.std(recent_wavelengths)  # Standard deviation

    return {
        'ppk': ppk,
        'std': std,
        'ready': True,
        'channel': channel
    }
```

Display in UI corner or intelligence bar.

### Step 5: Offline Grid Search Tool (60 min)

**File**: `src/diagnostics/optimize_baseline_noise.py` (NEW)

```python
"""Offline baseline noise optimization tool

Usage:
1. Run live acquisition for 60 seconds with stable baseline
2. Click "Record Baseline Data" button
3. This tool loads the recorded spectra
4. Tests all parameter combinations
5. Outputs optimal parameters
"""

import numpy as np
from scipy.signal import savgol_filter
import pandas as pd
from pathlib import Path

def load_baseline_data(filepath: str):
    """Load recorded baseline transmission spectra"""
    pass

def test_parameter_combination(spectra, wavelengths,
                               sg_window, sg_poly,
                               alpha, window_size):
    """Process all spectra with given parameters"""
    pass

def run_grid_search():
    """Test all parameter combinations"""
    results = []

    for sg_win in [11, 15, 21, 25, 31]:
        for sg_poly in [2, 3, 4]:
            for alpha in [500, 1000, 2000, 5000, 10000]:
                for win_size in [100, 130, 165, 200, 250]:
                    # Test combination
                    noise_ppk, noise_std, proc_time = test_parameter_combination(...)

                    results.append({
                        'sg_window': sg_win,
                        'sg_polyorder': sg_poly,
                        'alpha': alpha,
                        'window_size': win_size,
                        'noise_ppk': noise_ppk,
                        'noise_std': noise_std,
                        'processing_time_ms': proc_time
                    })

    df = pd.DataFrame(results)
    df.to_csv('optimization_results.csv')

    # Find optimal
    optimal = df.loc[df['noise_ppk'].idxmin()]
    print(f"Optimal parameters: {optimal}")
```

---

## Expected Results

### Baseline Noise Targets
- **Current**: Unknown (needs measurement)
- **Previous Best**: ~2 nm peak-to-peak
- **Target**: ≤2 nm peak-to-peak
- **Stretch Goal**: ≤1.5 nm peak-to-peak

### Parameter Expectations

**SG Filter**:
- Larger window → More smoothing → Lower noise BUT slower response
- Higher polyorder → Better feature preservation BUT less noise reduction
- **Optimal guess**: window=25-31, polyorder=3

**Fourier Alpha**:
- Higher alpha → More aggressive noise suppression
- Too high → Loss of dynamic response, peak rounding
- **Optimal guess**: 3000-5000 (higher than current 2000)

**Window Size**:
- Larger window → More stable zero-crossing detection
- Too large → Slower convergence
- **Optimal guess**: 165-200 (current 165 likely good)

---

## Dynamic Testing Strategy

Once baseline noise is optimized, test dynamic response:

### Test 1: Step Response
- Inject sample with known binding
- Measure rise time (10-90%)
- Verify no overshoot or oscillation
- Target: <5 second rise time

### Test 2: Ramp Response
- Inject sample with gradual binding
- Verify smooth tracking (no staircasing)
- Check for lag vs. true signal

### Test 3: High-Frequency Injection
- Rapid on/off cycles
- Verify no ringing or artifacts
- Check filter doesn't introduce phase delay

### Adaptive Optimization (Future)
```python
# Pseudo-code for dynamic parameter adjustment
class DynamicNoiseOptimizer:
    def __init__(self):
        self.baseline_mode = True  # Start conservative
        self.alpha = 2e3

    def update(self, is_dynamic_event: bool):
        """Adjust parameters based on signal state"""
        if is_dynamic_event:
            # Reduce smoothing for fast response
            self.alpha = 1000
            self.sg_window = 15
            self.baseline_mode = False
        else:
            # Increase smoothing for low noise
            self.alpha = 5000
            self.sg_window = 31
            self.baseline_mode = True
```

**Dynamic event detection**:
- Monitor rate of change: `d(wavelength)/dt`
- If `|dλ/dt| > threshold`, switch to dynamic mode
- After signal stable for N seconds, return to baseline mode

---

## Next Steps

**Immediate** (you choose):
1. 🔧 **Interactive Tuning**: Create live parameter adjustment dialog
2. 📊 **Baseline Recording**: Add "Record Baseline Data" button to capture spectra
3. 🤖 **Grid Search**: Build offline optimization tool
4. 📈 **Noise Display**: Add real-time noise metrics to UI

**My Recommendation**: Start with #2 (baseline recording), then #3 (grid search). This gives us data-driven optimization without guessing. Once we find optimal parameters, implement #1 (live tuning) for validation and future tweaking.

What's your preference? Should I start implementing the baseline recording system?
