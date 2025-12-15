# Processing Pipeline Architecture

## Overview

The SPR processing pipeline has been refactored into a flexible, pluggable architecture that allows switching between different processing algorithms while maintaining backward compatibility with existing code.

## Architecture Components

### 1. Core Pipeline Interface (`utils/processing_pipeline.py`)

**ProcessingPipeline (Abstract Base Class)**
- Defines interface for all pipelines
- Methods:
  - `get_metadata()` - Returns pipeline info for UI display
  - `calculate_transmission()` - Computes transmission spectrum
  - `find_resonance_wavelength()` - Finds resonance wavelength
  - `process()` - Complete pipeline (transmission + resonance)

**PipelineRegistry**
- Manages all available pipelines
- Handles pipeline switching
- Maintains active pipeline state

**ProcessingResult**
- Standardized output from pipelines
- Contains transmission, resonance, metadata, success status

### 2. Pipeline Implementations

#### Fourier Pipeline (Default) - `utils/pipelines/fourier_pipeline.py`
- **Method**: Discrete Sine Transform + zero-crossing detection
- **Use case**: Current default, well-tested for SPR
- **Parameters**:
  - `window_size`: Window for linear regression (default: 165)
  - `alpha`: Fourier weight parameter (default: 2e3)

#### Centroid Pipeline - `utils/pipelines/centroid_pipeline.py`
- **Method**: Center of mass of inverted transmission dip
- **Use case**: Simple, robust method for symmetric peaks
- **Parameters**:
  - `smoothing_sigma`: Gaussian smoothing (default: 2.0)
  - `search_window`: Pixels around minimum (default: 100)
  - `min_dip_depth`: Minimum dip depth % (default: 5.0)

#### Polynomial Pipeline - `utils/pipelines/polynomial_pipeline.py`
- **Method**: Polynomial fitting with analytical minimum
- **Use case**: High precision for smooth, well-defined dips
- **Parameters**:
  - `poly_degree`: Polynomial degree (default: 4)
  - `fit_window`: Fitting window pixels (default: 80)
  - `use_weighted`: Weight near minimum (default: True)

### 3. UI Integration

**PipelineSelector Widget** (`widgets/pipeline_selector.py`)
- Dropdown to select active pipeline
- Displays pipeline description and parameters
- Emits `pipeline_changed` signal when switched
- Can be integrated into main UI or advanced settings

### 4. Backward Compatibility

**Compatibility Wrapper** (`utils/spr_signal_processing_compat.py`)
- Drop-in replacements for old functions
- Uses active pipeline internally
- Existing code works without modification

## Usage

### For End Users (UI)

1. **Open Pipeline Selector**
   - Available in Advanced Settings or Tools menu
   - Shows all available pipelines with descriptions

2. **Select Pipeline**
   - Choose from dropdown
   - View parameters and details
   - Switch takes effect immediately

3. **Compare Results**
   - Switch between pipelines during acquisition
   - Observe differences in real-time
   - Export data includes pipeline information

### For Developers

#### Adding a New Pipeline

```python
# 1. Create new pipeline class
from utils.processing_pipeline import ProcessingPipeline, PipelineMetadata

class MyCustomPipeline(ProcessingPipeline):
    def get_metadata(self):
        return PipelineMetadata(
            name="My Custom Method",
            description="Brief description",
            version="1.0",
            author="Your Name",
            parameters={'param1': value1}
        )

    def calculate_transmission(self, intensity, reference):
        # Your transmission calculation
        return transmission

    def find_resonance_wavelength(self, transmission, wavelengths, **kwargs):
        # Your resonance finding algorithm
        return wavelength

# 2. Register in utils/pipelines/__init__.py
from utils.pipelines.my_custom import MyCustomPipeline

def initialize_pipelines():
    registry = get_pipeline_registry()
    registry.register('my_custom', MyCustomPipeline)
    # ...
```

#### Using Pipelines Programmatically

```python
from utils.processing_pipeline import get_pipeline_registry

# Get registry
registry = get_pipeline_registry()

# Switch pipeline
registry.set_active_pipeline('centroid')

# Get active pipeline
pipeline = registry.get_active_pipeline()

# Process data
result = pipeline.process(
    intensity=intensity_data,
    reference=reference_data,
    wavelengths=wavelength_array
)

# Access results
transmission = result.transmission
resonance = result.resonance_wavelength
```

#### Backward Compatible Usage

```python
# Old code continues to work
from utils.spr_signal_processing import (
    calculate_transmission,
    find_resonance_wavelength_fourier
)

transmission = calculate_transmission(intensity, reference)
resonance = find_resonance_wavelength_fourier(
    transmission, wavelengths, fourier_weights
)
```

## Integration with Main Application

### Adding Pipeline Selector to UI

**Option 1: Advanced Settings Dialog**
```python
from widgets.pipeline_selector import PipelineSelector

# In advanced settings dialog
self.pipeline_selector = PipelineSelector()
layout.addWidget(self.pipeline_selector)

# Connect signal
self.pipeline_selector.pipeline_changed.connect(self.on_pipeline_changed)
```

**Option 2: Main Window Menu**
```python
# Add to Tools menu
pipeline_action = QAction("Processing Pipelines...", self)
pipeline_action.triggered.connect(self.show_pipeline_selector)
tools_menu.addAction(pipeline_action)

def show_pipeline_selector(self):
    dialog = QDialog(self)
    layout = QVBoxLayout(dialog)
    selector = PipelineSelector(dialog)
    layout.addWidget(selector)
    dialog.exec()
```

### Processing Loop Integration

The processing in `main.py` already works through the compatibility layer:

```python
# Current code (line ~1467)
fit_lambda = find_resonance_wavelength_fourier(
    transmission_spectrum=self.trans_data[ch],
    wavelengths=self.wave_data,
    fourier_weights=self.fourier_weights,
    window_size=165,
)
```

This automatically uses the active pipeline! To make it explicit:

```python
from utils.processing_pipeline import get_pipeline_registry

# Get active pipeline
pipeline = get_pipeline_registry().get_active_pipeline()

# Process
result = pipeline.process(
    intensity=int_data_ch,
    reference=self.ref_sig[ch],
    wavelengths=self.wave_data
)

fit_lambda = result.resonance_wavelength
self.trans_data[ch] = result.transmission
```

## Performance Considerations

- **Pipeline Switching**: Instant (no reprocessing of old data)
- **Overhead**: Minimal (~0.1ms per call for registry lookup)
- **Memory**: Each pipeline instance is cached
- **Thread Safety**: Registry is thread-safe for reading

## Data Export

When exporting data, include pipeline information:

```python
# In export metadata
metadata['processing_pipeline'] = pipeline.get_metadata().name
metadata['pipeline_version'] = pipeline.get_metadata().version
metadata['pipeline_params'] = pipeline.get_metadata().parameters
```

## Testing

Test pipeline selector:
```bash
cd "Old software"
python -m widgets.pipeline_selector
```

Test pipelines programmatically:
```python
from utils.pipelines import initialize_pipelines
from utils.processing_pipeline import get_pipeline_registry

initialize_pipelines()
registry = get_pipeline_registry()

# Test each pipeline
for pid in ['fourier', 'centroid', 'polynomial']:
    registry.set_active_pipeline(pid)
    pipeline = registry.get_active_pipeline()
    result = pipeline.process(intensity, reference, wavelengths)
    print(f"{pid}: {result.resonance_wavelength:.2f} nm")
```

## Future Enhancements

Potential additions to the pipeline system:

1. **More Pipelines**
   - Gaussian fitting
   - Spline interpolation
   - Machine learning methods

2. **Pipeline Comparison Mode**
   - Run multiple pipelines simultaneously
   - Side-by-side comparison view
   - Statistical analysis of differences

3. **Pipeline Configuration UI**
   - Adjust parameters in real-time
   - Save/load pipeline configurations
   - Per-channel pipeline selection

4. **Performance Profiling**
   - Measure pipeline execution time
   - Compare computational cost
   - Optimize bottlenecks

5. **Validation Framework**
   - Known reference samples
   - Accuracy metrics
   - Automated testing

## Benefits

✅ **Flexibility**: Easy to add new processing methods
✅ **Comparison**: Switch pipelines to evaluate performance
✅ **Backward Compatible**: Existing code works unchanged
✅ **Maintainable**: Clean separation of concerns
✅ **Testable**: Each pipeline can be tested independently
✅ **Documented**: Metadata includes parameters and descriptions
✅ **UI Integration**: User-friendly pipeline selection

## Migration Path

**Phase 1** (Current): Backward compatible wrappers
- Old code works unchanged
- New pipelines available
- UI can switch pipelines

**Phase 2** (Optional): Explicit pipeline usage
- Update main.py to use pipeline directly
- Remove compatibility layer
- Full control over pipeline features

**Phase 3** (Future): Advanced features
- Pipeline comparison mode
- Per-channel pipelines
- Configuration persistence
