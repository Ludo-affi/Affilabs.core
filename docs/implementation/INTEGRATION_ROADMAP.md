# Main Application Integration Roadmap
**Date**: October 11, 2025
**Status**: Ready to Begin
**Goal**: Integrate device configuration system into main application

---

## 🎯 Overview

Now that the workspace is clean and the device configuration system is complete, we need to integrate it into the main application so it can use device-specific parameters for optimization.

---

## ✅ What's Ready

### Device Configuration System:
- ✅ GUI widget (`widgets/device_settings.py`)
- ✅ Hardware detection (`utils/hardware_detection.py`)
- ✅ Config management (`utils/device_configuration.py`)
- ✅ Calibration loader (`utils/calibration_data_loader.py`)
- ✅ Settings menu integration (Device Configuration tab added)

### Current Configuration:
```json
{
  "device_id": "USB4000-FLMT09788-E6614864D3147C21",
  "optical_fiber": {
    "diameter_um": 100,
    "options": [100, 200]
  },
  "led_pcb_model": "4LED",
  "hardware": {
    "spectrometer": "USB4000",
    "spectrometer_serial": "FLMT09788",
    "controller": "PicoP4SPR",
    "controller_serial": "E6614864D3147C21"
  }
}
```

---

## 🔍 Integration Points

### 1. Application Startup (`widgets/mainwindow.py`)

**Current State**: App starts without checking device config
**Need**: Load device config on startup

**Changes Required**:
```python
# In MainWindow.__init__()
from utils.device_configuration import DeviceConfiguration

# Load device config
self.device_config = DeviceConfiguration.load()

# Log configuration
logger.info(f"Device Config: Fiber={self.device_config.optical_fiber_diameter}µm, LED={self.device_config.led_pcb_model}")

# Pass to calibrator
self.calibrator = SPRCalibrator(
    optical_fiber_diameter=self.device_config.optical_fiber_diameter,
    led_model=self.device_config.led_pcb_model
)
```

**Benefits**:
- Device-specific parameters available app-wide
- Calibration uses correct fiber diameter
- Hardware info available for diagnostics

---

### 2. Calibration System (`utils/spr_calibrator.py`)

**Current State**: Uses hardcoded parameters
**Need**: Use device-specific optical fiber diameter

**Changes Required**:
```python
class SPRCalibrator:
    def __init__(self, optical_fiber_diameter=100, led_model="4LED"):
        """
        Initialize calibrator with device-specific parameters.

        Args:
            optical_fiber_diameter: Fiber diameter in µm (100 or 200)
            led_model: LED PCB model ("4LED" or "8LED")
        """
        self.optical_fiber_diameter = optical_fiber_diameter
        self.led_model = led_model

        # Adjust calibration parameters based on fiber diameter
        if optical_fiber_diameter == 200:
            # 200µm fiber collects more light - adjust saturation thresholds
            self.saturation_threshold = 60000  # Higher threshold
            self.min_signal_threshold = 1000   # Higher minimum
        else:
            # 100µm fiber (default)
            self.saturation_threshold = 55000
            self.min_signal_threshold = 500

        logger.info(f"Calibrator initialized: {optical_fiber_diameter}µm fiber, {led_model}")
```

**Benefits**:
- Accurate calibration for each fiber type
- Prevents saturation with 200µm fiber
- Better signal range utilization

---

### 3. Hardware Manager (`utils/hardware_manager.py`)

**Current State**: Manual hardware initialization
**Need**: Use hardware detection on startup

**Changes Required**:
```python
from utils.hardware_detection import detect_spectrometer, detect_controller

class HardwareManager:
    def __init__(self):
        # Auto-detect hardware
        self.spectrometer_info = detect_spectrometer()
        self.controller_info = detect_controller()

        if not self.spectrometer_info:
            raise RuntimeError("No spectrometer detected!")
        if not self.controller_info:
            raise RuntimeError("No controller detected!")

        logger.info(f"Detected: {self.spectrometer_info['name']} + {self.controller_info['port']}")
```

**Benefits**:
- Automatic hardware detection on startup
- Validates hardware is connected
- Provides hardware info for diagnostics

---

### 4. Data Acquisition (`utils/spr_data_acquisition.py`)

**Current State**: Uses fixed integration times
**Need**: Adjust for fiber diameter and LED model

**Changes Required**:
```python
class SPRDataAcquisition:
    def __init__(self, device_config):
        self.device_config = device_config

        # Adjust integration times based on fiber diameter
        if device_config.optical_fiber_diameter == 200:
            # 200µm collects 4x more light - reduce integration time
            self.base_integration_time = 5  # ms (vs 10ms for 100µm)
        else:
            self.base_integration_time = 10  # ms

        # Adjust LED intensity ranges
        if device_config.led_pcb_model == "8LED":
            self.max_led_intensity = 100  # 8LED board supports full range
        else:
            self.max_led_intensity = 80   # 4LED board limited range
```

**Benefits**:
- Optimal integration times for each fiber
- Faster measurements with 200µm fiber
- Device-specific LED control

---

### 5. Processing Pipeline (`utils/spr_data_processor.py`)

**Current State**: Fixed noise thresholds
**Need**: Adjust based on fiber diameter

**Changes Required**:
```python
class SPRDataProcessor:
    def __init__(self, device_config):
        self.device_config = device_config

        # Adjust noise filtering based on fiber
        if device_config.optical_fiber_diameter == 200:
            # 200µm has better SNR - less aggressive filtering
            self.noise_threshold = 0.001  # Less filtering
            self.savgol_window = 5        # Smaller window
        else:
            # 100µm needs more filtering
            self.noise_threshold = 0.002  # More filtering
            self.savgol_window = 9        # Larger window
```

**Benefits**:
- Better signal quality for each fiber type
- Preserve signal detail with 200µm
- Reduce noise with 100µm

---

## 📋 Implementation Checklist

### Phase 1: Core Integration (Priority: HIGH)
- [ ] **1.1** Import DeviceConfiguration in mainwindow.py
- [ ] **1.2** Load config on startup
- [ ] **1.3** Pass config to calibrator
- [ ] **1.4** Update SPRCalibrator to accept fiber diameter
- [ ] **1.5** Adjust calibration parameters based on fiber
- [ ] **1.6** Test with 100µm fiber
- [ ] **1.7** Test with 200µm fiber (if available)

### Phase 2: Hardware Detection (Priority: HIGH)
- [ ] **2.1** Update HardwareManager to use auto-detection
- [ ] **2.2** Remove manual hardware selection (if any)
- [ ] **2.3** Add hardware validation on startup
- [ ] **2.4** Show detected hardware in app status
- [ ] **2.5** Test with both devices connected

### Phase 3: Optimization (Priority: MEDIUM)
- [ ] **3.1** Update SPRDataAcquisition with fiber-specific times
- [ ] **3.2** Add LED model-specific control
- [ ] **3.3** Update SPRDataProcessor with fiber-specific filtering
- [ ] **3.4** Benchmark performance improvements
- [ ] **3.5** Compare 100µm vs 200µm results

### Phase 4: UI Enhancements (Priority: LOW)
- [ ] **4.1** Show device config in main window status bar
- [ ] **4.2** Add "Device Info" dialog (show detected hardware)
- [ ] **4.3** Link to Device Configuration from main menu
- [ ] **4.4** Show fiber diameter in calibration dialog

---

## 🔧 Testing Strategy

### Unit Tests:
1. **Config Loading**: Test DeviceConfiguration.load() with valid/invalid configs
2. **Hardware Detection**: Test with/without hardware connected
3. **Calibrator**: Test with 100µm and 200µm parameters
4. **Data Acquisition**: Test integration time adjustment

### Integration Tests:
1. **Startup**: Test app startup with config loaded
2. **Calibration**: Test full calibration with device config
3. **Measurement**: Test measurement with fiber-specific parameters
4. **Hardware**: Test hardware detection + initialization

### System Tests:
1. **100µm Fiber**: Complete workflow with 100µm fiber
2. **200µm Fiber**: Complete workflow with 200µm fiber (if available)
3. **Config Change**: Change config and verify app uses new values
4. **Factory Fresh**: Test with no config (should prompt setup)

---

## 📊 Expected Benefits

### Performance:
- **200µm Fiber**: 2x faster measurements (reduced integration time)
- **Calibration**: Device-specific thresholds reduce failures
- **Startup**: Hardware auto-detection faster than manual selection

### Reliability:
- **No Manual Config**: Eliminates user error in config file editing
- **Hardware Validation**: Catches connection issues early
- **Fiber-Specific**: Prevents saturation/signal issues

### User Experience:
- **Automatic**: No manual hardware selection needed
- **Transparent**: User sees device config in UI
- **Easy Setup**: Device Configuration GUI for changes

---

## 🚀 Quick Start Integration

### Step 1: Load Config in MainWindow

```python
# In widgets/mainwindow.py, at the top of __init__():
from utils.device_configuration import DeviceConfiguration

# Load device configuration
try:
    self.device_config = DeviceConfiguration.load()
    logger.info(f"Loaded device config: {self.device_config.optical_fiber_diameter}µm fiber")
except FileNotFoundError:
    logger.warning("No device config found - using defaults")
    self.device_config = DeviceConfiguration()
    self.device_config.save()  # Create default config
```

### Step 2: Pass to Calibrator

```python
# When creating SPRCalibrator:
self.calibrator = SPRCalibrator(
    optical_fiber_diameter=self.device_config.optical_fiber_diameter,
    led_model=self.device_config.led_pcb_model
)
```

### Step 3: Update SPRCalibrator

```python
# In utils/spr_calibrator.py:
def __init__(self, optical_fiber_diameter=100, led_model="4LED"):
    self.optical_fiber_diameter = optical_fiber_diameter
    self.led_model = led_model

    # Adjust parameters
    if optical_fiber_diameter == 200:
        self.saturation_threshold = 60000
    else:
        self.saturation_threshold = 55000
```

### Step 4: Test

```bash
# Run app
python run_app.py

# Check logs for:
# "Loaded device config: 100µm fiber"
# "Calibrator initialized: 100µm fiber, 4LED"
```

---

## 📝 Files to Modify

| File | Priority | Changes |
|------|----------|---------|
| `widgets/mainwindow.py` | HIGH | Load config on startup |
| `utils/spr_calibrator.py` | HIGH | Accept fiber diameter parameter |
| `utils/hardware_manager.py` | HIGH | Use hardware detection |
| `utils/spr_data_acquisition.py` | MEDIUM | Fiber-specific integration times |
| `utils/spr_data_processor.py` | MEDIUM | Fiber-specific filtering |

---

## 🎯 Success Criteria

✅ **Integration Complete When**:
1. App loads device config on startup
2. Calibration uses correct fiber diameter
3. Hardware is auto-detected
4. Measurements use fiber-specific parameters
5. User can change config via GUI
6. App reflects config changes immediately

✅ **Performance Improved When**:
1. 200µm fiber measurements 2x faster
2. Calibration success rate > 95%
3. No saturation issues
4. Better signal quality

---

## 🔍 Where to Start

**Recommended Order**:
1. ✅ Start with `widgets/mainwindow.py` - load config on startup
2. ✅ Update `utils/spr_calibrator.py` - fiber diameter parameter
3. ✅ Test calibration with 100µm fiber
4. ✅ Update `utils/hardware_manager.py` - auto-detection
5. ✅ Test complete startup workflow

**Time Estimate**: 2-3 hours for core integration + testing

---

## 💡 Next Action

**Ready to begin integration!**

Let's start with the most critical part:
1. Load device config in mainwindow.py
2. Pass to calibrator
3. Test and verify

Would you like to proceed with Step 1?

---

*Integration roadmap created: October 11, 2025*
