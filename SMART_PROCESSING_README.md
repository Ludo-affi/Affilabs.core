# Smart Processing Module

## Overview

The **Smart Processing** module is a standalone GUI application that implements intelligent, automated processing of SPR (Surface Plasmon Resonance) time series data. It addresses the key limitations in the existing workflow by providing:

- **Automatic cycle detection** from continuous time series data
- **Smart concentration assignment** based on response patterns
- **One-click processing pipeline** from raw data to kinetic analysis
- **Intelligent segmentation** of association/dissociation phases

## Key Features

### 🚀 **Automated Workflow**
- Import SPR time series files with one click
- Automatic detection of injection cycles
- Smart baseline correction and noise filtering
- Direct export to kinetic analysis

### 🧠 **Intelligent Processing**
- **Signal Processing**: Savitzky-Golay filtering for noise reduction
- **Peak Detection**: Derivative-based injection point identification
- **Phase Classification**: Automatic association/dissociation segmentation
- **Pattern Recognition**: Concentration series detection and assignment

### 📊 **Comprehensive Visualization**
- Real-time raw data plotting
- Detected cycles overlay with color coding
- Detailed cycle table with quality metrics
- Progress tracking for long processing jobs

### 🔧 **Flexible Configuration**
- Adjustable sensitivity parameters
- Multiple file format support
- Quality control options
- Export capabilities

## Installation & Usage

### Quick Start

1. **Generate Sample Data** (for testing):
   ```bash
   python generate_sample_data.py
   ```

2. **Launch Smart Processing**:
   ```bash
   python launch_smart_processing.py
   ```

3. **Process Your Data**:
   - Click "Browse..." to select your SPR time series file
   - Click "Import Data" to load the file
   - Adjust detection parameters if needed
   - Click "🚀 Start Smart Processing"
   - Review results and export or launch kinetic analysis

### Supported File Formats

#### Multi-Channel Format (Recommended)
```
Time_A    Channel_A    Time_B    Channel_B    Time_C    Channel_C    Time_D    Channel_D
0.000     0.125        0.000     0.089        0.000     0.045        0.000     0.012
0.100     0.128        0.100     0.092        0.100     0.047        0.100     0.015
...
```

#### Single Channel Format
```
Time      Response
0.000     0.125
0.100     0.128
0.200     0.135
...
```

## Technical Implementation

### Core Algorithms

#### 1. **Cycle Detection Pipeline**
```
Raw Time Series → Preprocessing → Injection Detection → Cycle Segmentation → Phase Classification → Concentration Assignment
```

#### 2. **Signal Preprocessing**
- **Savitzky-Golay filtering** for noise reduction while preserving features
- **Baseline correction** using moving window statistics
- **Outlier detection** and removal options

#### 3. **Injection Point Detection**
- **Derivative analysis** to find significant signal changes
- **Peak finding** with configurable thresholds
- **Distance constraints** to prevent false positives

#### 4. **Phase Classification**
- **Association detection**: Rising signal with exponential characteristics
- **Plateau identification**: Low derivative regions indicating equilibrium
- **Dissociation detection**: Falling signal with exponential decay
- **Automatic boundary setting** based on signal characteristics

#### 5. **Concentration Assignment**
- **Pattern recognition** for common concentration series
- **Response correlation** analysis
- **Automatic scaling** to appropriate units (nM, μM, etc.)

### Background Processing

Smart Processing uses **QThread-based background processing** to keep the UI responsive during intensive computations:

- **Progress tracking** with real-time updates
- **Error handling** with graceful recovery
- **Cancellation support** for long-running operations

## Configuration Parameters

### Detection Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Injection Sensitivity** | 2.0 | Threshold multiplier for injection detection |
| **Min Cycle Distance** | 100 | Minimum data points between cycles |
| **Smoothing Window** | 51 | Savitzky-Golay filter window size |

### Processing Options

- **Auto-assign concentrations**: Enable intelligent concentration detection
- **Apply baseline correction**: Normalize signals to baseline
- **Remove outlier cycles**: Filter low-quality cycles automatically

## Output Formats

### CSV Export
Complete cycle data with metadata:
- Channel information
- Cycle numbers and concentrations
- Timing data (start/end times, durations)
- Response measurements (association/dissociation shifts)
- Quality scores

### Kinetic Analysis Integration
Direct launch into KA/KD Wizard with:
- Pre-segmented cycle data
- Assigned concentrations
- Formatted for immediate kinetic analysis

## Algorithm Details

### Injection Detection Algorithm
```python
def detect_injections(signal_data):
    # 1. Calculate signal derivative
    derivative = np.gradient(signal_data)

    # 2. Find peaks exceeding threshold
    threshold = np.std(derivative) * sensitivity_factor
    peaks = find_peaks(derivative, height=threshold, distance=min_distance)

    # 3. Validate peaks and return injection points
    return validated_injection_points
```

### Concentration Pattern Recognition
```python
def detect_concentration_pattern(response_magnitudes):
    # Analyze response trends
    correlation = np.corrcoef(range(len(responses)), responses)[0,1]

    if correlation > 0.7:
        return 'increasing'  # Standard concentration series
    elif correlation < -0.7:
        return 'decreasing'  # Reverse concentration series
    elif len(set(responses)) == 1:
        return 'replicate'   # Same concentration repeats
    else:
        return 'mixed'       # Mixed or complex pattern
```

## Quality Control

### Cycle Quality Metrics
- **Signal-to-noise ratio**: Response range vs noise level
- **Phase completeness**: Presence of both association and dissociation
- **Kinetic consistency**: Expected exponential behavior
- **Temporal integrity**: Appropriate cycle timing

### Automatic Filtering
- Cycles below quality threshold can be auto-removed
- Manual review options for borderline cases
- Quality scores displayed in results table

## Integration with Main Application

While Smart Processing operates as a standalone module, it integrates seamlessly with the main SPR control application:

- **Data compatibility**: Outputs standard segment format
- **Direct launching**: Can call KA/KD Wizard directly
- **Settings inheritance**: Uses main application preferences when available
- **Logging integration**: Unified error reporting and debugging

## Future Enhancements

### Planned Features
- **Machine learning** cycle classification
- **Advanced baseline** correction algorithms
- **Multi-format import** (Biacore, other SPR systems)
- **Batch processing** for multiple files
- **Cloud processing** for large datasets

### Algorithm Improvements
- **Adaptive thresholding** based on signal characteristics
- **Context-aware** concentration assignment
- **Real-time processing** for live data streams
- **Cross-validation** of detected patterns

## Troubleshooting

### Common Issues

**No cycles detected:**
- Reduce injection sensitivity (try 1.0-1.5)
- Check file format and data quality
- Verify signal has actual binding events

**False cycle detection:**
- Increase minimum cycle distance
- Increase injection sensitivity
- Check for electronic noise or artifacts

**Poor concentration assignment:**
- Disable auto-assignment and set manually
- Check for consistent response patterns
- Verify signal baseline is stable

**Processing errors:**
- Check file encoding (should be UTF-8)
- Ensure numeric data format
- Verify sufficient data points per cycle

### Debug Mode
Enable detailed logging by setting environment variable:
```bash
export SPR_DEBUG=1
python launch_smart_processing.py
```

## Dependencies

### Required Packages
- **PySide6**: GUI framework
- **NumPy**: Numerical computations
- **SciPy**: Signal processing and optimization
- **PyQtGraph**: Fast plotting and visualization

### Optional Integration
- **Main SPR Application**: For direct kinetic analysis launch
- **Pandas**: Enhanced data manipulation (if available)
- **Matplotlib**: Additional plotting options (if needed)

---

**Smart Processing** represents a significant step forward in SPR data analysis automation, transforming what was previously a manual, time-consuming process into an intelligent, one-click workflow.