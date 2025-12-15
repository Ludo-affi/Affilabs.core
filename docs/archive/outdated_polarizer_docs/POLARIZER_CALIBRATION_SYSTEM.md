# Polarizer Calibration System Documentation

## Overview

The polarizer calibration system in the SPR (Surface Plasmon Resonance) setup automatically determines optimal polarizer positions for both S-mode and P-mode operations. This is critical for SPR measurements as the polarization state directly affects the plasmon coupling and measurement sensitivity.

## System Architecture

### 1. Auto-Polarization Algorithm (`auto_polarize` method)

The auto-polarization system uses an intelligent sweep-and-peak-detection approach:

```python
def auto_polarize(self, ctrl, usb):
    """Automatically find optimal polarizer positions for P and S modes.

    Uses peak detection to find angles where maximum light transmission
    occurs for both polarization modes.
    """
```

#### Algorithm Steps:

1. **Initialization**:
   - Set LED to maximum intensity (255)
   - Configure optimal integration time
   - Define angular sweep range (10° to 170°)

2. **Angular Sweep**:
   - Step size: 5° increments
   - Range: 160° total sweep
   - Measurements: Both S and P modes at each position

3. **Peak Detection**:
   - Uses `scipy.signal.find_peaks()` for intensity maxima
   - `peak_prominences()` identifies most significant peaks
   - `peak_widths()` calculates optimal position ranges

4. **Position Calculation**:
   - Selects two most prominent peaks
   - Calculates optimal S and P positions from peak centers
   - Returns tuple `(s_pos, p_pos)`

### 2. Polarization Mode Control

#### Hardware Interface:
```python
# Switch to S-mode (typically 0° or optimized angle)
ctrl.set_mode("s")

# Switch to P-mode (typically 90° or optimized angle)
ctrl.set_mode("p")

# Set specific servo positions
ctrl.servo_set(s_pos, p_pos)
```

#### Position Management:
- **S-mode**: Optimized for reference measurements
- **P-mode**: Optimized for sample analysis (enhanced sensitivity)
- **Manual override**: User can set specific angles via UI

### 3. Integration with Calibration Sequence

The polarizer calibration is integrated into the main calibration workflow:

```
Step 1: Wavelength calibration
Step 2: Auto-polarizer alignment ← POLARIZER CALIBRATION
Step 3: Integration time optimization
Step 4: LED intensity calibration (S-mode adaptive)
Step 5: Dark noise measurement (S-mode)
Step 6: Reference signal measurement (S-mode)
Step 7: LED intensity calibration (P-mode adaptive)
Step 8: Final validation
```

### 4. Calibration Usage in LED Optimization

#### S-Mode LED Calibration:
```python
def calibrate_led_s_mode_adaptive(self, ch):
    """Calibrate LED intensity for S-polarization mode."""
    # Sets polarizer to S-mode
    # Optimizes LED intensity for target counts
    # Uses adaptive convergence algorithm
```

#### P-Mode LED Calibration:
```python
def calibrate_led_p_mode_adaptive(self, ch):
    """Adaptive LED intensity calibration for P-polarization mode."""
    # Sets polarizer to P-mode
    # Uses S-mode result as baseline
    # Applies P_MAX_INCREASE multiplier (1.33x)
    # Targets higher intensity (66,500 counts vs 50,000)
```

## Technical Parameters

### Angular Sweep Configuration:
```python
min_angle = 10          # Start angle (degrees)
max_angle = 170         # End angle (degrees)
angle_step = 5          # Step size (degrees)
steps = 16              # Total steps in half range
```

### Target Intensities:
```python
ADAPTIVE_TARGET_INTENSITY = 50000    # S-mode target
P_MAX_INCREASE = 1.33               # P-mode multiplier
P_MODE_TARGET = 66500               # P-mode target (50000 × 1.33)
```

### Peak Detection Parameters:
- **Peak prominence**: Identifies significant intensity peaks
- **Peak width**: 5% threshold for optimal position calculation
- **Convergence**: Selects top 2 most prominent peaks

## Manual Control Interface

### UI Integration:
```python
# Spectroscopy widget polarization control
self.ui.polarization.currentIndexChanged.connect(self.set_polarizer)

def set_polarizer(self):
    """Set polarizer mode from UI selection."""
    mode = self.ui.polarization.currentText().lower()
    self.polarizer_sig.emit(mode)
```

### Direct Hardware Control:
```python
# Set specific angle
controller.set_polarizer_angle(45)

# Get current position
current_pos = controller.get_polarizer_angle()
```

## Diagnostic Capabilities

### Polarizer Testing:
- **Command validation**: Tests various polarizer commands
- **Position feedback**: Verifies movement and positioning
- **Motor detection**: Checks hardware connectivity
- **Step control**: Manual stepping for fine adjustment

### Error Handling:
```python
try:
    result = self.calibrator.auto_polarize(ctrl=self.ctrl, usb=self.usb)
    if result is not None:
        s_pos, p_pos = result
        logger.debug(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
except Exception as e:
    logger.exception(f"Error in auto_polarization: {e}")
```

## Dependencies

### Required Libraries:
```python
from scipy.signal import find_peaks, peak_prominences, peak_widths
import numpy as np
```

### Hardware Requirements:
- **PicoP4SPR Controller**: Servo-controlled polarizer
- **USB4000 Spectrometer**: Intensity measurements
- **LED System**: Light sources for each channel

## Integration Points

### 1. Main Application:
```python
def auto_polarization(self):
    """Find polarizer positions using calibrator."""
    result = self.calibrator.auto_polarize(ctrl=self.ctrl, usb=self.usb)
```

### 2. Parameter Manager:
```python
def _update_servo_positions(self):
    """Update servo polarizer positions if changed."""
    polarizer_pos = self.hardware.ctrl.servo_get()
    s_pos = int(polarizer_pos["s"][0:3])
    p_pos = int(polarizer_pos["p"][0:3])
```

### 3. Hardware Manager:
```python
def _safe_hardware_cleanup(self):
    """Safe hardware state reset."""
    # Reset polarizer to S-mode
    self.ctrl.set_mode("s")
```

## Calibration Workflow

### Automatic Mode:
1. **Trigger**: Called during full calibration if `auto_polarize=True`
2. **Execution**: Sweeps through angular range measuring intensities
3. **Optimization**: Uses peak detection to find optimal positions
4. **Application**: Sets hardware to optimal S and P positions
5. **Validation**: Verifies positioning and updates parameters

### Manual Mode:
1. **User Selection**: Choose S or P mode from UI
2. **Position Setting**: System moves to predefined/calibrated positions
3. **Feedback**: Position confirmation and status updates

## Performance Characteristics

### Speed:
- **Sweep time**: ~30-60 seconds (depends on mechanical response)
- **Peak detection**: Near-instantaneous (computational)
- **Mode switching**: 2-3 seconds per position change

### Accuracy:
- **Angular resolution**: 5° steps during calibration
- **Position repeatability**: Hardware-dependent (typically ±1°)
- **Intensity sensitivity**: Detects peaks with high signal-to-noise ratio

## System Status

✅ **Fully Implemented**: Auto-polarization with peak detection
✅ **Hardware Integrated**: Servo control and position feedback
✅ **UI Available**: Manual mode selection and control
✅ **Calibration Integrated**: Part of main calibration sequence
✅ **Error Handling**: Comprehensive exception management
✅ **Diagnostics**: Dedicated testing and validation tools

The polarizer calibration system provides both automatic optimization and manual control, ensuring optimal SPR measurement conditions for both S-mode (reference) and P-mode (sample) operations.
