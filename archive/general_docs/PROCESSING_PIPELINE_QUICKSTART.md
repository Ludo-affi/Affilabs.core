# Processing Pipeline System - Quick Start

## What's New

A flexible, pluggable architecture for SPR data processing that allows you to:
- **Switch between different processing algorithms in real-time**
- **Compare results from different methods**
- **Add new processing pipelines without modifying existing code**

## Available Pipelines

### 1. **Fourier Transform (Default)**
- Current/established method
- Uses DST/IDCT for derivative zero-crossing detection
- Best for: Standard SPR measurements

### 2. **Centroid Method**
- Finds center of mass of transmission dip
- Best for: Symmetric peaks, quick comparison

### 3. **Polynomial Fitting**
- Fits polynomial and finds minimum analytically
- Best for: Smooth, well-defined dips

## How to Use

### For Users

**From UI** (when integrated):
1. Open "Processing Pipelines" from Tools menu or Advanced Settings
2. Select desired pipeline from dropdown
3. Pipeline activates immediately
4. View pipeline description and parameters

### For Developers

**Switching pipelines programmatically**:
```python
from utils.processing_pipeline import get_pipeline_registry

registry = get_pipeline_registry()
registry.set_active_pipeline('centroid')  # or 'fourier', 'polynomial'
```

**Using pipelines directly**:
```python
pipeline = registry.get_active_pipeline()
result = pipeline.process(intensity, reference, wavelengths)

transmission = result.transmission
resonance = result.resonance_wavelength
```

**Existing code continues to work** (backward compatible):
```python
from utils.spr_signal_processing import (
    calculate_transmission,
    find_resonance_wavelength_fourier
)
# These functions now use the active pipeline internally
```

## Test Results

All three pipelines tested on synthetic SPR data (620 nm resonance):
- **Fourier**: 620.01 nm (0.01 nm error) ✓
- **Centroid**: 619.91 nm (0.09 nm error) ✓
- **Polynomial**: 620.01 nm (0.01 nm error) ✓

Maximum difference between pipelines: **0.10 nm**

## Files Added

```
Old software/
├── utils/
│   ├── processing_pipeline.py          # Core architecture
│   ├── spr_signal_processing_compat.py # Backward compatibility
│   └── pipelines/
│       ├── __init__.py                  # Pipeline registration
│       ├── fourier_pipeline.py          # Default method
│       ├── centroid_pipeline.py         # Alternative method
│       └── polynomial_pipeline.py       # Alternative method
├── widgets/
│   └── pipeline_selector.py            # UI widget for switching
test_pipelines.py                        # Test script
PROCESSING_PIPELINE_ARCHITECTURE.md      # Complete documentation
```

## Quick Test

```bash
python test_pipelines.py
```

Should show:
- ✓ 3 pipelines registered
- ✓ All pipelines process synthetic data successfully
- ✓ Results within 0.1 nm of each other

## Integration with Main App

The processing loop in `main.py` (line ~1467) already works through the compatibility layer. To make it explicit:

```python
# Replace this:
fit_lambda = find_resonance_wavelength_fourier(
    transmission_spectrum=self.trans_data[ch],
    wavelengths=self.wave_data,
    fourier_weights=self.fourier_weights
)

# With this (optional, for explicit pipeline usage):
pipeline = get_pipeline_registry().get_active_pipeline()
result = pipeline.find_resonance_wavelength(
    transmission=self.trans_data[ch],
    wavelengths=self.wave_data,
    fourier_weights=self.fourier_weights  # For Fourier pipeline
)
fit_lambda = result
```

## Adding to UI

Add pipeline selector to advanced settings or create menu item:

```python
# In advanced settings dialog
from widgets.pipeline_selector import PipelineSelector

self.pipeline_selector = PipelineSelector()
layout.addWidget(self.pipeline_selector)

# Connect to signal if needed
self.pipeline_selector.pipeline_changed.connect(self.on_pipeline_changed)
```

## Next Steps

1. **Test with real data**: Run application with different pipelines
2. **UI Integration**: Add PipelineSelector to advanced settings
3. **Export metadata**: Include pipeline info in data exports
4. **Add more pipelines**: Gaussian fitting, spline interpolation, etc.

## Benefits

✅ **Backward Compatible** - Existing code works unchanged
✅ **Flexible** - Easy to add new methods
✅ **User-Friendly** - Switch pipelines from UI
✅ **Testable** - Each pipeline independently verifiable
✅ **Documented** - Metadata describes each method

---

**Need help?** See `PROCESSING_PIPELINE_ARCHITECTURE.md` for complete documentation.
